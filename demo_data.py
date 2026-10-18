"""Realistic DUMMY history for the admin dashboard: about 12 weeks of tickets, self-help outcomes
and answer ratings. Dates are relative to "now", so the demo always looks current after a reset.

Nothing here is real data. The same random seed gives the same history every time.
"""
import random
import datetime

TEAM_WEIGHTS = {"Service Desk": 34, "Network Team": 20, "Hardware Team": 21, "Apps Team": 15, "Security Team": 10}

# Per team: how often the first response / the fix misses its target (shapes the SLA story)
RESPONSE_MISS = {"Service Desk": 0.05, "Network Team": 0.08, "Hardware Team": 0.22, "Apps Team": 0.10, "Security Team": 0.03}
RESOLVE_MISS = {"Service Desk": 0.06, "Network Team": 0.26, "Hardware Team": 0.14, "Apps Team": 0.20, "Security Team": 0.05}
STUCK = {"Service Desk": 0.02, "Network Team": 0.09, "Hardware Team": 0.05, "Apps Team": 0.08, "Security Team": 0.0}

# (title, category, priority weights Low/Medium/High/Urgent, first response text, fix text)
TEMPLATES = {
    "Service Desk": [
        ("Password reset not working", "Passwords", (2, 6, 2, 0), "checked the account, reset link sent", "password reset completed"),
        ("Account locked out", "Accounts", (1, 5, 4, 0), "verifying identity before unlock", "account unlocked"),
        ("Move Authenticator to new phone", "MFA", (4, 5, 1, 0), "sent MFA re-registration steps", "MFA moved to the new phone"),
        ("Printer shows paper jam error", "Printer", (5, 4, 1, 0), "engineer booked to check the printer", "printer sensor cleaned"),
        ("Cannot print to floor printer", "Printer", (5, 5, 0, 0), "re-added the printer remotely", "print queue cleared"),
        ("Shared drive access request", "Access", (6, 4, 0, 0), "access request sent to the data owner", "access granted"),
        ("Outlook not syncing", "Email", (3, 6, 1, 0), "rebuilding the Outlook profile", "mailbox syncing again"),
    ],
    "Network Team": [
        ("VPN disconnects every hour", "VPN & Remote Access", (2, 6, 2, 0), "collecting TB Connect logs", "VPN client profile updated"),
        ("TB Connect error 809", "VPN & Remote Access", (1, 6, 3, 0), "checking the VPN gateway", "firewall rule corrected"),
        ("Wi-Fi slow on the 4th floor", "Wi-Fi", (3, 6, 1, 0), "site survey scheduled", "access point replaced"),
        ("Teams calls dropping in branch", "Network", (2, 5, 3, 0), "checking branch bandwidth", "QoS settings fixed"),
    ],
    "Hardware Team": [
        ("Laptop battery drains quickly", "Hardware", (6, 4, 0, 0), "battery health check booked", "battery replaced"),
        ("Laptop very slow", "Hardware", (5, 5, 0, 0), "remote diagnostics running", "SSD replaced"),
        ("Keyboard not working", "Hardware", (3, 6, 1, 0), "replacement keyboard ordered", "keyboard replaced"),
        ("Request: second monitor", "Equipment request", (8, 2, 0, 0), "waiting for manager approval", "monitor delivered"),
        ("Headset request", "Equipment request", (8, 2, 0, 0), "headset ordered", "headset delivered"),
        ("Lost company phone", "Lost device", (0, 0, 0, 10), "device locked and wiped remotely", "replacement phone issued"),
    ],
    "Apps Team": [
        ("Install request: Power BI", "Software", (6, 4, 0, 0), "licence request raised", "software installed"),
        ("Excel crashes on open", "Software", (2, 6, 2, 0), "collecting crash logs", "Office repaired"),
        ("SAP login error", "Business apps", (1, 5, 4, 0), "checking SAP role assignment", "SAP role fixed"),
        ("Teams add-in missing", "Software", (5, 5, 0, 0), "re-deploying the add-in", "add-in restored"),
    ],
    "Security Team": [
        ("Suspicious email reported", "Phishing", (2, 6, 2, 0), "email quarantined and analysed", "sender blocked"),
        ("Clicked a phishing link", "Security incident", (0, 0, 2, 8), "password reset forced, sessions revoked", "incident closed, no data loss"),
        ("USB exception request", "USB", (6, 4, 0, 0), "exception sent for manager approval", "30-day USB exception granted"),
    ],
}
PRIORITIES = ["Low", "Medium", "High", "Urgent"]
RESPONSE_HOURS = {"Urgent": 1, "High": 4, "Medium": 24, "Low": 72}
RESOLVE_HOURS = {"Urgent": 4, "High": 24, "Medium": 72, "Low": 240}
SELF_HELP_TOPICS = ["I forgot my password", "My account is locked", "VPN won't connect", "Printer paper jam",
                    "Outlook is not updating", "New phone, how do I move MFA?", "Teams keeps freezing"]


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _stamp(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def generate(now, requesters, first_new_id, days=84, seed=7):
    """Returns (old_tickets, recent_tickets, self_help_rows, feedback_rows).
    Old tickets (older than 7 days) are numbered up to T-1000; recent ones from first_new_id."""
    rng = random.Random(seed)
    tickets = []
    start = (now - datetime.timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    for d in range(days + 1):
        day = start + datetime.timedelta(days=d)
        weekday = day.weekday() < 5
        trend = 1 + 0.15 * d / days
        n = max(0, round(rng.gauss(3.4 * trend if weekday else 0.5, 1.1)))
        for _ in range(n):
            created = day + datetime.timedelta(hours=8.5 + rng.random() * (10 if weekday else 6))
            if created >= now - datetime.timedelta(minutes=30):
                continue
            team = rng.choices(list(TEAM_WEIGHTS), weights=TEAM_WEIGHTS.values())[0]
            title, category, pw, reply, fix = rng.choice(TEMPLATES[team])
            priority = rng.choices(PRIORITIES, weights=pw)[0]
            share_agent = 0.10 + 0.45 * d / days                       # the virtual agent's share grows
            channel = "Virtual agent" if rng.random() < share_agent else rng.choices(
                ["Email", "Portal", "Phone"], weights=[45, 35, 20])[0]
            tickets.append(_one_ticket(rng, now, created, team, title, category, priority, reply, fix, channel))
    tickets.sort(key=lambda t: t["created_at"])
    cutoff = _iso(now - datetime.timedelta(days=7))
    old = [t for t in tickets if t["created_at"] < cutoff]
    recent = [t for t in tickets if t["created_at"] >= cutoff]
    for i, t in enumerate(old):
        t["ticket_id"] = f"T-{1000 - len(old) + 1 + i:04d}"
    for i, t in enumerate(recent):
        t["ticket_id"] = f"T-{first_new_id + i}"
    for t in old + recent:
        t["requester_email"] = rng.choice(requesters)

    self_help, feedback = [], []
    for d in range(days + 1):
        day = start + datetime.timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for _ in range(max(0, round(rng.gauss(1 + 4 * d / days, 1)))):
            at = day + datetime.timedelta(hours=9 + rng.random() * 9)
            if at < now:
                self_help.append((_stamp(at), rng.choice(requesters), rng.choice(SELF_HELP_TOPICS),
                                  "solved" if rng.random() < 0.72 else "needed a ticket"))
        for k in range(max(0, round(rng.gauss(2 + 3 * d / days, 1)))):
            at = day + datetime.timedelta(hours=9 + rng.random() * 9)
            if at < now:
                feedback.append((f"demo-{d}-{k}", _stamp(at), rng.choice(requesters),
                                 rng.choice(SELF_HELP_TOPICS), "(demo history)", 1 if rng.random() < 0.86 else 0))
    return old, recent, self_help, feedback


def _one_ticket(rng, now, created, team, title, category, priority, reply, fix, channel):
    resp_target, fix_target = RESPONSE_HOURS[priority], RESOLVE_HOURS[priority]
    resp_h = resp_target * (rng.uniform(1.2, 3.0) if rng.random() < RESPONSE_MISS[team] else rng.uniform(0.05, 0.8))
    fix_h = fix_target * (rng.uniform(1.15, 2.5) if rng.random() < RESOLVE_MISS[team] else rng.uniform(0.35, 0.95))
    fix_h = max(fix_h, resp_h + 0.5)
    first_response = created + datetime.timedelta(hours=resp_h)
    resolved = created + datetime.timedelta(hours=fix_h)
    age_days = (now - created).total_seconds() / 86400
    stuck = 5 < age_days < 35 and rng.random() < STUCK[team]
    history = [(created, f"Ticket created via {channel.lower()}.")]
    t = {"title": title, "category": category, "priority": priority, "team": team, "channel": channel,
         "created_at": _iso(created), "created": created.date().isoformat(), "first_response_at": None,
         "resolved_at": None, "paused_since": None, "waiting_for": None}
    if first_response < now:
        t["first_response_at"] = _iso(first_response)
        history.append((first_response, f"{team}: {reply}."))
    if resolved < now and not stuck:
        t["resolved_at"] = _iso(resolved)
        t["status"] = "Closed" if rng.random() < 0.3 else "Resolved"
        history.append((resolved, f"{team}: {fix}. Resolved."))
    elif not t["first_response_at"]:
        t["status"] = "New"
    elif title.startswith("Request:") or "exception" in title:
        t["status"] = "Waiting for approval"
        t["paused_since"] = t["first_response_at"]
        t["waiting_for"] = "Manager approval"
    else:
        t["status"] = "In progress"
        if not stuck and now - first_response > datetime.timedelta(hours=12):
            update = first_response + (now - first_response) * rng.uniform(0.5, 0.95)
            history.append((update, f"{team}: work in progress, user updated."))
    t["history"] = [{"at": _stamp(at), "text": text} for at, text in history]
    return t
