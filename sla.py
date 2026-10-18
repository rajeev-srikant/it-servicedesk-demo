"""Service targets (SLA = service level agreement). Real service desks track two:

1. RESPONSE   - how fast an IT team first replies.     e.g. Low: within 3 days
2. RESOLUTION - how fast the problem is actually fixed. e.g. Low: within 10 days

While a ticket is "Waiting for approval" (waiting for the user or their manager), the resolution
clock is PAUSED, so IT is not marked late for something they cannot control.
Targets use calendar hours to keep the demo simple (real desks often use business hours).
"""
import datetime
import db

RESPONSE_HOURS = {"Urgent": 1, "High": 4, "Medium": 24, "Low": 72}
RESOLVE_HOURS = {"Urgent": 4, "High": 24, "Medium": 72, "Low": 240}
RESPONDERS = ("Service Desk:", "Network Team:", "Security Team:", "Hardware Team:", "Apps Team:", "Updated by")


def _human(delta):
    minutes = int(abs(delta.total_seconds()) // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h {minutes % 60:02d}m" if hours < 10 else f"{hours}h"
    return f"{hours // 24} days"


def _period(hours):
    return f"{hours}h" if hours < 24 else f"{hours // 24} day{'s' if hours > 24 else ''}"


def _created(t):
    return datetime.datetime.fromisoformat(t.get("created_at") or t["created"] + "T09:00:00+09:00")


def targets_text(t):
    p = t["priority"]
    return f"{p}: respond within {_period(RESPONSE_HOURS.get(p, 24))} · resolve within {_period(RESOLVE_HOURS.get(p, 72))}"


def status(t):
    """First-response target. Returns {"state": "responded"|"closed"|"ok"|"soon"|"overdue", "label", "due", "target"}."""
    target = RESPONSE_HOURS.get(t["priority"], 24)
    due = _created(t) + datetime.timedelta(hours=target)
    info = {"target": f"{t['priority']}: respond within {_period(target)}", "due": due.strftime("%Y-%m-%d %H:%M")}
    if t["status"] in ("Resolved", "Closed"):
        return dict(info, state="closed", label="Closed")
    if t.get("first_response_at") or any(h["text"].startswith(RESPONDERS) for h in t.get("history", [])):
        return dict(info, state="responded", label="IT responded")
    left = due - db.now()
    if left.total_seconds() < 0:
        return dict(info, state="overdue", label=f"Response overdue by {_human(left)}")
    if left.total_seconds() < target * 3600 * 0.25:
        return dict(info, state="soon", label=f"Response due in {_human(left)}")
    return dict(info, state="ok", label=f"Response due in {_human(left)}")


def resolution(t):
    """Resolution target, with the clock paused while waiting for approval."""
    target = RESOLVE_HOURS.get(t["priority"], 72)
    paused = t.get("paused_hours") or 0
    info = {"target": f"{t['priority']}: resolve within {_period(target)}"}
    if t["status"] in ("Resolved", "Closed"):
        return dict(info, state="closed", label="", due="")
    if t.get("paused_since"):
        return dict(info, state="paused", label="Clock paused: waiting for approval", due="paused")
    due = _created(t) + datetime.timedelta(hours=target + paused)
    info["due"] = due.strftime("%Y-%m-%d %H:%M")
    left = due - db.now()
    if left.total_seconds() < 0:
        return dict(info, state="overdue", label=f"Resolution overdue by {_human(left)}")
    if left.total_seconds() < target * 3600 * 0.25:
        return dict(info, state="soon", label=f"Resolve by {due:%d %b %H:%M}")
    return dict(info, state="ok", label=f"Resolve by {due:%d %b %H:%M}")


def is_overdue(t):
    return status(t)["state"] == "overdue" or resolution(t)["state"] == "overdue"
