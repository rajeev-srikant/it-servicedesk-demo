"""Outage detection: when many people report the same problem in a short time, it is probably one outage.

1. Detect: open tickets created in the last 60 minutes are grouped by team + category. 3 or more people with
   the same kind of problem = a possible outage (both numbers are settings the IT admin can change).
2. Declare: an IT admin turns the group into one major incident (INC-001). The tickets are linked to it.
3. Inform: while the incident is active, the agent tells anyone with the same problem that it is a known issue
   and records them as affected, instead of creating another ticket. Employees also see a banner.
4. Resolve: closing the incident resolves all linked tickets at once, and the fix can become a KB draft.
"""
import json
import datetime
import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, title TEXT, team TEXT, category TEXT, message TEXT,
    status TEXT, created_at TEXT, created_by TEXT, resolved_at TEXT, resolution TEXT);
CREATE TABLE IF NOT EXISTS incident_reports (incident_id TEXT, user TEXT, at TEXT, via TEXT,
    PRIMARY KEY (incident_id, user));
"""
ACTIVE, RESOLVED = "Active", "Resolved"


def init():
    with db._conn() as c:
        c.executescript(SCHEMA)
        cols = [r[1] for r in c.execute("PRAGMA table_info(tickets)")]
        if "incident_id" not in cols:
            c.execute("ALTER TABLE tickets ADD COLUMN incident_id TEXT")


def reset():
    init()
    with db._conn() as c:
        c.execute("DELETE FROM incidents")
        c.execute("DELETE FROM incident_reports")
        c.execute("UPDATE tickets SET incident_id=NULL")


def settings():
    return int(db.get_setting("outage_window_min", "60")), int(db.get_setting("outage_threshold", "3"))


# ---------------------------------------------------------------- 1. detect
def detect():
    """Groups of similar open tickets in the time window, with at least `threshold` different people."""
    window, threshold = settings()
    since = (db.now() - datetime.timedelta(minutes=window)).isoformat(timespec="seconds")
    groups = {}
    for t in db.list_tickets():
        if t["status"] in ("Resolved", "Closed") or t.get("incident_id") or (t["created_at"] or "") < since:
            continue
        if t["category"] == "Chat handoff":
            continue
        groups.setdefault(topic_of(t), []).append(t)
    out = []
    for category, items in groups.items():
        people = {t["requester_email"] for t in items}
        if len(people) >= threshold:
            teams = [t["team"] for t in items]
            team = max(set(teams), key=teams.count)          # the team most of these tickets went to
            out.append({"team": team, "category": category, "tickets": sorted(items, key=lambda t: t["created_at"]),
                        "people": len(people), "window": window})
    return sorted(out, key=lambda g: -g["people"])


# Words that tell us what a ticket is about, whatever category or team the AI chose for it
TOPICS = [("Email & Outlook", ("outlook", "email", "e-mail", "mailbox", "outbox", "inbox", "exchange")),
          ("VPN & Remote Access", ("vpn", "tb connect", "remote access")),
          ("Wi-Fi & Network", ("wi-fi", "wifi", "wireless", "network", "internet")),
          ("Microsoft Teams", ("teams",)),
          ("Printing", ("printer", "printing", "print ")),
          ("Sign-in & Passwords", ("password", "locked", "sign in", "sign-in", "login", "log in", "mfa",
                                   "authenticator")),
          ("SAP", ("sap",)),
          ("SharePoint & OneDrive", ("sharepoint", "onedrive"))]


def topic_of(t):
    text = f" {t['title']} {t['category'] or ''} ".lower()
    for name, words in TOPICS:
        if any(w in text for w in words):
            return name
    return t["category"] or "Other"


# ---------------------------------------------------------------- 2. declare
def _next_id(c):
    nums = [int(r[0].split("-")[1]) for r in c.execute("SELECT id FROM incidents")]
    return f"INC-{max(nums, default=0) + 1:03d}"


def declare(title, team, category, message, ticket_ids, by):
    with db._conn() as c:
        new_id = _next_id(c)
        c.execute("INSERT INTO incidents (id, title, team, category, message, status, created_at, created_by) "
                  "VALUES (?,?,?,?,?,?,?,?)", (new_id, db.redact(title), team, category, db.redact(message), ACTIVE,
                                               db.now().strftime("%Y-%m-%d %H:%M"), by))
        for tid in ticket_ids:
            c.execute("UPDATE tickets SET incident_id=? WHERE ticket_id=?", (new_id, tid))
    for tid in ticket_ids:
        db.update_ticket(tid, status="In progress")
        db.mark_responded(tid)
        db.add_history(tid, f"{team}: linked to major incident {new_id} ({title}). We are working on it.")
        t = db.get_ticket(tid)
        _add_report(new_id, t["requester_email"], "ticket")
    db.log_audit(by, "declare_incident", {"title": title, "tickets": ticket_ids}, {"incident": new_id}, "user action")
    return new_id


# ---------------------------------------------------------------- 3. inform
def list_incidents(status=None):
    with db._conn() as c:
        q = "SELECT * FROM incidents" + (" WHERE status=?" if status else "") + " ORDER BY id DESC"
        rows = [dict(r) for r in c.execute(q, (status,) if status else ())]
        for r in rows:
            r["tickets"] = [x[0] for x in c.execute("SELECT ticket_id FROM tickets WHERE incident_id=?", (r["id"],))]
            r["affected"] = c.execute("SELECT COUNT(*) FROM incident_reports WHERE incident_id=?",
                                      (r["id"],)).fetchone()[0]
            r["via_agent"] = c.execute("SELECT COUNT(*) FROM incident_reports WHERE incident_id=? AND via='agent'",
                                       (r["id"],)).fetchone()[0]
    return rows


def active():
    return list_incidents(ACTIVE)


def _add_report(incident_id, user, via):
    with db._conn() as c:
        return c.execute("INSERT OR IGNORE INTO incident_reports VALUES (?,?,?,?)",
                         (incident_id, user, db.now().strftime("%Y-%m-%d %H:%M"), via)).rowcount


def report(incident_id, user):
    """The agent found that this user's problem is an active incident: count them as affected (no new ticket)."""
    inc = next((i for i in active() if i["id"].upper() == incident_id.strip().upper()), None)
    if not inc:
        return {"error": f"No active incident {incident_id}"}
    added = _add_report(inc["id"], user, "agent")
    return {"incident": inc["id"], "title": inc["title"], "message": inc["message"],
            "recorded": "You were added to the list of affected people." if added else "You were already on the list.",
            "affected_people": inc["affected"] + added}


def prompt_text():
    """For the agent's instructions: the incidents that are active right now."""
    items = active()
    if not items:
        return "There are no active major incidents right now."
    return "ACTIVE MAJOR INCIDENTS (known problems IT is already fixing):\n" + "\n".join(
        f"- {i['id']}: {i['title']} (team: {i['team']}, category: {i['category']}). Message: {i['message']}"
        for i in items)


# ---------------------------------------------------------------- 4. resolve
def resolve(incident_id, resolution, by, make_kb=True):
    inc = next(i for i in list_incidents() if i["id"] == incident_id)
    with db._conn() as c:
        c.execute("UPDATE incidents SET status=?, resolved_at=?, resolution=? WHERE id=?",
                  (RESOLVED, db.now().strftime("%Y-%m-%d %H:%M"), db.redact(resolution), incident_id))
    for tid in inc["tickets"]:
        db.add_history(tid, f"{inc['team']}: major incident {incident_id} resolved. {resolution}")
        db.update_ticket(tid, status="Resolved")
    import catalog                                     # tell everyone affected (in-app notification)
    with db._conn() as c:
        people = {r[0] for r in c.execute("SELECT user FROM incident_reports WHERE incident_id=?", (incident_id,))}
    people |= {t["requester_email"] for t in (db.get_ticket(x) for x in inc["tickets"]) if t}
    for user in people:
        catalog.notify(user, "Fixed: {title} ({inc}). {fix}", None, title=inc["title"], inc=incident_id,
                       fix=resolution)
    draft = None
    if make_kb and inc["tickets"] and resolution.strip():
        import kb
        draft = kb.create_draft(inc["tickets"][0], resolution, created_by=by)
    db.log_audit(by, "resolve_incident", {"incident": incident_id, "resolution": resolution},
                 {"tickets_resolved": len(inc["tickets"]), "kb_draft": draft}, "user action")
    return len(inc["tickets"]), draft


# ---------------------------------------------------------------- demo
DEMO_OUTAGES = {
    "VPN": ("Network Team", "VPN & Remote Access", [
        ("VPN not connecting: error 809", "mai.saito@testbank.com"),
        ("TB Connect VPN fails to connect from home", "takumi.kobayashi@testbank.com"),
        ("Cannot connect to VPN since this morning", "emi.watanabe@testbank.com"),
        ("VPN keeps saying 'connection failed'", "hana.suzuki@testbank.com")]),
    "Outlook": ("Service Desk", "Email & Outlook", [
        ("Outlook not receiving new emails", "taro.yamada@testbank.com"),
        ("Outlook shows 'Disconnected' at the bottom", "kenji.sato@testbank.com"),
        ("Emails stuck in the Outbox, cannot send", "yuki.nakamura@testbank.com"),
        ("Outlook keeps asking for my password", "mai.saito@testbank.com"),
        ("Outlook on the web not loading", "emi.watanabe@testbank.com")]),
}


def simulate_outage(kind="VPN"):
    """Demo button: several different people report the same kind of problem within minutes."""
    import tools
    team, category, reports = DEMO_OUTAGES[kind]
    made = []
    for title, user in reports:
        if user not in tools.EMPLOYEES:
            continue
        made.append(db.create_ticket(user, title, category, "High", team, "New",
                                     f"Ticket created by AI agent for the user. {title}."))
    return made
