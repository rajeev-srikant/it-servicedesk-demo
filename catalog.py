"""Service requests with manager approval, and in-app notifications.

1. Request: the employee asks for something from the catalogue (software, access, equipment).
   The agent fills in the request (tool request_item); the employee confirms it, as with every action.
2. Approve: items that need approval wait for the employee's manager. The manager sees them under
   "Approvals waiting for you" and clicks Approve or Reject. No AI is involved in the decision.
3. Act: an approved request goes to the IT team as a normal ticket; a rejected one is closed.
4. Notify: the employee (and the manager) get a notification in the app (the bell at the top).
   In this demo nothing is sent outside the app.
"""
import json
import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (ticket_id TEXT PRIMARY KEY, requester TEXT, approver TEXT, item TEXT,
    reason TEXT, status TEXT, created_at TEXT, decided_at TEXT, comment TEXT);
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, at TEXT,
    template TEXT, params TEXT, ticket_id TEXT, read INTEGER DEFAULT 0);
"""

# Demo manager for everyone (dummy person). In a real company this comes from the HR system / Entra ID.
DEFAULT_MANAGER = "keiko.mori@testbank.com"

# The request catalogue: what employees can ask for, which team does it, and whether a manager must approve.
CATALOG = {
    "Adobe Acrobat Pro": {"type": "Software", "team": "Apps Team", "approval": True, "cost": "¥2,500 / month"},
    "Microsoft Visio": {"type": "Software", "team": "Apps Team", "approval": True, "cost": "¥1,900 / month"},
    "Shared drive access": {"type": "Access", "team": "Security Team", "approval": True, "cost": "—"},
    "VPN access": {"type": "Access", "team": "Network Team", "approval": True, "cost": "—"},
    "Second monitor": {"type": "Equipment", "team": "Hardware Team", "approval": True, "cost": "¥32,000"},
    "Laptop replacement": {"type": "Equipment", "team": "Hardware Team", "approval": True, "cost": "¥180,000"},
    "Headset": {"type": "Equipment", "team": "Hardware Team", "approval": False, "cost": "¥6,000"},
    "Keyboard and mouse": {"type": "Equipment", "team": "Hardware Team", "approval": False, "cost": "¥4,000"},
}


def init():
    with db._conn() as c:
        c.executescript(SCHEMA)
        empty = c.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    if empty:
        _seed_demo()


def reset():
    init()
    with db._conn() as c:
        c.execute("DELETE FROM approvals")
        c.execute("DELETE FROM notifications")
    _seed_demo()


def _seed_demo():
    """The starting monitor request (T-1004) is already waiting for the demo manager's approval."""
    t = db.get_ticket("T-1004")
    if t and t["status"] == db.PAUSE_STATUS:
        with db._conn() as c:
            c.execute("INSERT OR IGNORE INTO approvals (ticket_id, requester, approver, item, reason, status, "
                      "created_at) VALUES (?,?,?,?,?,?,?)", ("T-1004", t["requester_email"], DEFAULT_MANAGER,
                      "Second monitor", "Working from home 3 days a week", "Pending", t["created"] + " 09:00"))


def manager_of(email, employees):
    """The manager who approves this person's requests (None for the manager herself)."""
    m = employees.get(email, {}).get("manager", DEFAULT_MANAGER)
    return None if m == email else m


def find_item(name):
    """Match what the AI wrote ('acrobat', 'Adobe Acrobat') to a catalogue item."""
    name = (name or "").strip().lower()
    for item in CATALOG:
        if name == item.lower():
            return item
    for item in CATALOG:
        if name and (name in item.lower() or item.lower() in name):
            return item
    return None


# ---------------------------------------------------------------- 1. request
def create_request(requester, item, details, reason, employees):
    info = CATALOG[item]
    approver = manager_of(requester, employees) if info["approval"] else None
    approver_name = employees.get(approver, {}).get("name", approver).split("(")[0].strip() if approver else ""
    status = db.PAUSE_STATUS if approver else "New"
    tid = db.create_ticket(requester, f"Request: {item}", f"{info['type']} request", "Low", info["team"], status,
                           f"Service request created by AI agent. Item: {item}. Details: {details or '—'}. "
                           f"Business reason: {reason or '—'}")
    if approver:
        db.update_ticket(tid, status=db.PAUSE_STATUS, waiting_for=f"Manager approval ({approver_name})")
        db.add_history(tid, f"Sent to {approver_name} for approval.")
        with db._conn() as c:
            c.execute("INSERT INTO approvals (ticket_id, requester, approver, item, reason, status, created_at) "
                      "VALUES (?,?,?,?,?,?,?)", (tid, requester, approver, item, db.redact(reason or ""), "Pending",
                                                  db.now().strftime("%Y-%m-%d %H:%M")))
        who = employees.get(requester, {}).get("name", requester).split("(")[0].strip()
        notify(approver, "{who} requests {item} ({tid}). Please approve or reject it.", tid, who=who, item=item)
    return {"created": tid, "item": item, "team": info["team"], "needs_approval": bool(approver),
            "approver": approver_name or None, "status": status}


# ---------------------------------------------------------------- 2. approve / reject
def pending_for(approver):
    with db._conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM approvals WHERE approver=? AND status='Pending' "
                                           "ORDER BY created_at", (approver,))]


def get(ticket_id):
    with db._conn() as c:
        r = c.execute("SELECT * FROM approvals WHERE ticket_id=?", (ticket_id,)).fetchone()
    return dict(r) if r else None


def decide(ticket_id, approver, approved, comment, approver_name):
    a = get(ticket_id)
    if not a or a["approver"] != approver or a["status"] != "Pending":
        return False                                   # only the right manager, only once
    with db._conn() as c:
        c.execute("UPDATE approvals SET status=?, decided_at=?, comment=? WHERE ticket_id=?",
                  ("Approved" if approved else "Rejected", db.now().strftime("%Y-%m-%d %H:%M"),
                   db.redact(comment or ""), ticket_id))
    note = f" Comment: {comment}" if comment else ""
    if approved:
        db.update_ticket(ticket_id, status="New")      # the IT team can start; the paused clock restarts
        db.clear_waiting(ticket_id)
        db.add_history(ticket_id, f"Approved by {approver_name}.{note} Passed to the {CATALOG[a['item']]['team']}.")
        notify(a["requester"], "Good news: {approver} approved your request for {item} ({tid}). "
                               "The {team} will now prepare it.", ticket_id,
               approver=approver_name, item=a["item"], team=CATALOG[a["item"]]["team"])
    else:
        db.update_ticket(ticket_id, status="Closed")
        db.clear_waiting(ticket_id)
        db.add_history(ticket_id, f"Rejected by {approver_name}.{note}")
        notify(a["requester"], "{approver} did not approve your request for {item} ({tid}).{note}", ticket_id,
               approver=approver_name, item=a["item"], note=note)
    db.log_audit(approver, "approve_request" if approved else "reject_request", {"ticket_id": ticket_id},
                 {"item": a["item"], "comment": comment}, "user action")
    return True


# ---------------------------------------------------------------- 3. notifications (in the app only)
def notify(user, template, ticket_id=None, **params):
    """Save a notification. The text is stored as an English template + values, so it can be shown in English
    or Japanese later. {tid} is always available."""
    if not user:
        return
    params["tid"] = ticket_id or ""
    with db._conn() as c:
        c.execute("INSERT INTO notifications (user, at, template, params, ticket_id) VALUES (?,?,?,?,?)",
                  (user, db.now().strftime("%Y-%m-%d %H:%M"), template, json.dumps(params, ensure_ascii=False),
                   ticket_id))


def list_notifications(user, limit=20):
    with db._conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM notifications WHERE user=? ORDER BY id DESC LIMIT ?",
                                           (user, limit))]
    for r in rows:
        r["params"] = json.loads(r["params"] or "{}")
    return rows


def unread_count(user):
    with db._conn() as c:
        return c.execute("SELECT COUNT(*) FROM notifications WHERE user=? AND read=0", (user,)).fetchone()[0]


def mark_all_read(user):
    with db._conn() as c:
        c.execute("UPDATE notifications SET read=1 WHERE user=?", (user,))
