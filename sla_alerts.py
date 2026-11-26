"""Proactive SLA alerts: warn the assigned IT team BEFORE a ticket misses its target.

1. WATCH   every open ticket against its response and resolution targets (sla.py)
           - "At risk"  = 75% of the time used (less than 25% left)
           - "Breached" = past the deadline
2. WRITE   the AI writes each alert: what the problem is, why it is stuck, similar solved tickets,
           and a suggested next step. (Plain rules can say "T-1023 is late"; the AI says what to do.)
3. NOTIFY  the members of the assigned team (bell). Breached tickets are also escalated to the
           Service Desk manager (IT admin). Each ticket is alerted only ONCE per level - no spam.

In the PoC the check runs when a team member or IT admin opens the app (at most every 5 minutes),
or with the "Run SLA check now" button. In a pilot a scheduler runs it every 10-15 minutes and the
alerts go to the team's Microsoft Teams channel.
"""
import datetime
import json

import db
import sla

SCHEMA = """CREATE TABLE IF NOT EXISTS sla_alerts (ticket_id TEXT, level TEXT, at TEXT, team TEXT, target TEXT,
            text TEXT, PRIMARY KEY (ticket_id, level));"""
EVERY_MINUTES = 5
MAX_PER_RUN = 5          # never flood a team: the most urgent new alerts first
FRESH_HOURS = 24         # a breach older than this was already known before the watcher saw it: no alert

PROMPT = """You are helping an IT support team at a bank. A ticket is {level_words}.
Write a short alert for the team (max 60 words, plain English, no greeting, no markdown headings):
1) one line: what the problem is and who is affected,
2) one line: why it matters now (time left or how late, and whether the user is still waiting for a first reply),
3) one line starting "Suggested next step:" - a concrete action. If a similar solved ticket below fits, use its fix.

Ticket: {ticket}
Similar solved tickets (may be empty): {similar}
"""


def init():
    with db._conn() as c:
        c.executescript(SCHEMA)
    if db.get_setting("sla_demo_seeded", "") == "":     # first start: add the two demo tickets once
        db.set_setting("sla_demo_seeded", "1")
        _seed_demo()


def reset():
    with db._conn() as c:
        c.executescript(SCHEMA)
        c.execute("DELETE FROM sla_alerts")
    db.set_setting("sla_demo_seeded", "1")
    db.set_setting("last_sla_check", "")
    _seed_demo()


def team_members(team, employees):
    return [e for e, p in employees.items() if p.get("role") == "agent" and p.get("agent_team") == team]


def admins(employees):
    return [e for e, p in employees.items() if p.get("role") == "admin"]


def _overdue_hours(due_text):
    due = datetime.datetime.strptime(due_text, "%Y-%m-%d %H:%M")
    return (db.now().replace(tzinfo=None) - due).total_seconds() / 3600


def _state(t):
    """('breached'|'at_risk'|None, which target, label) - the worst of response and resolution."""
    r, res = sla.status(t), sla.resolution(t)
    if r["state"] == "overdue":
        return "breached", "response", r["label"]
    if res["state"] == "overdue":
        return "breached", "resolution", res["label"]
    if r["state"] == "soon":
        return "at_risk", "response", r["label"]
    if res["state"] == "soon":
        due = datetime.datetime.strptime(res["due"], "%Y-%m-%d %H:%M")
        left = due - db.now().replace(tzinfo=None)
        return "at_risk", "resolution", f"Resolution due in {sla._human(left)}"
    return None, None, ""


def urgency(t):
    """Sort key for a team queue: breached first, then at risk, then the rest by time left."""
    level, _, _ = _state(t)
    rank = {"breached": 0, "at_risk": 1}.get(level, 2)
    due = sla.resolution(t).get("due") or "9999"
    return (rank, {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}.get(t["priority"], 4), due)


def _similar(t, tickets):
    """Up to 3 solved tickets of the same category, with their last note (the fix)."""
    out = []
    for s in tickets:
        if s["ticket_id"] != t["ticket_id"] and s["status"] in ("Resolved", "Closed") \
                and s["category"] == t["category"] and s.get("history"):
            out.append({"title": s["title"], "fix": s["history"][-1]["text"][:200]})
        if len(out) == 3:
            break
    return out


def _write_alert(client, t, level, label, similar, names):
    words = "AT RISK of missing its target" if level == "at_risk" else "PAST its target (breached)"
    ticket = {"id": t["ticket_id"], "title": t["title"], "priority": t["priority"], "team": t["team"],
              "category": t["category"], "status": t["status"], "sla": label,
              "requester": names.get(t["requester_email"], t["requester_email"]).split("(")[0].strip(),
              "department": t.get("department"),
              "history": [h["text"][:200] for h in t.get("history", [])[-4:]]}
    try:
        import agent
        r = agent.generate(client, contents=PROMPT.format(level_words=words, ticket=json.dumps(ticket, ensure_ascii=False),
                                                          similar=json.dumps(similar, ensure_ascii=False)),
                           config={"temperature": 0.2})
        agent._usage("sla-alert", r)
        text = (r.text or "").strip()
        if text:
            return text
    except Exception:
        pass
    return (f"{t['title']} ({ticket['requester']}, {t.get('department') or '—'}). {label}. "   # fallback: plain rule text
            "Suggested next step: contact the user and update the ticket.")


def check(client, employees, force=False):
    """Look at every open ticket; create + send alerts that are new. Returns the number of new alerts."""
    if not force:
        last = db.get_setting("last_sla_check", "")
        if last and db.now() - datetime.datetime.fromisoformat(last) < datetime.timedelta(minutes=EVERY_MINUTES):
            return 0
    db.set_setting("last_sla_check", db.now().isoformat(timespec="seconds"))
    import catalog
    tickets = db.list_tickets()
    names = {e: p.get("name", e) for e, p in employees.items()}
    with db._conn() as c:
        done = {(r["ticket_id"], r["level"]) for r in c.execute("SELECT ticket_id, level FROM sla_alerts")}
    todo = []
    for t in tickets:
        if t["status"] in ("Resolved", "Closed"):
            continue
        level, target, label = _state(t)
        if not level or (t["ticket_id"], level) in done:
            continue
        if level == "breached":                     # only breaches that just happened
            due = (sla.status(t) if target == "response" else sla.resolution(t))["due"]
            if _overdue_hours(due) > FRESH_HOURS:
                continue
        todo.append((t, level, target, label))
    todo.sort(key=lambda x: urgency(x[0]))
    new = 0
    for t, level, target, label in todo[:MAX_PER_RUN]:
        text = _write_alert(client, t, level, label, _similar(t, tickets), names)
        with db._conn() as c:
            c.execute("INSERT OR IGNORE INTO sla_alerts (ticket_id, level, at, team, target, text) VALUES (?,?,?,?,?,?)",
                      (t["ticket_id"], level, db.now().strftime("%Y-%m-%d %H:%M"), t["team"], target, text))
        template = "SLA at risk · {tid}: {text}" if level == "at_risk" else "SLA breached · {tid}: {text}"
        to = team_members(t["team"], employees) + (admins(employees) if level == "breached" else [])
        for user in to:
            catalog.notify(user, template, t["ticket_id"], title=t["title"], text=text)
        db.log_audit("sla-watcher", "sla_alert", {"ticket_id": t["ticket_id"], "level": level},
                     {"team": t["team"], "notified": to}, "automatic")
        new += 1
    return new


def alerts_for(team=None, limit=30):
    q = "SELECT * FROM sla_alerts" + (" WHERE team=?" if team else "") + " ORDER BY at DESC LIMIT ?"
    with db._conn() as c:
        return [dict(r) for r in c.execute(q, ((team, limit) if team else (limit,)))]


# ---------------------------------------------------------------- demo: two tickets close to their targets
def _seed_demo():
    """One Apps Team ticket AT RISK and one Network Team ticket BREACHED, relative to now."""
    demo = [("mai.saito@testbank.com", "Excel crashes when opening the monthly sales report", "Software", "High",
             "Apps Team", 21, True),
            ("hana.suzuki@testbank.com", "Wi-Fi keeps dropping in meeting room 5B", "Network", "Medium",
             "Network Team", 26, False)]
    for who, title, cat, pr, team, hours_ago, responded in demo:
        tid = db.create_ticket(who, title, cat, pr, team, "In progress" if responded else "New",
                               f"Ticket created by AI agent. {title}.")
        created = db.now() - datetime.timedelta(hours=hours_ago)
        with db._conn() as c:
            c.execute("UPDATE tickets SET created_at=?, created=?, first_response_at=? WHERE ticket_id=?",
                      (created.isoformat(timespec="seconds"), created.strftime("%Y-%m-%d"),
                       (created + datetime.timedelta(hours=1)).isoformat(timespec="seconds") if responded else None,
                       tid))
        if responded:
            db.add_history(tid, f"{team}: Looking into it. Asked the user for the file and the error message.")
