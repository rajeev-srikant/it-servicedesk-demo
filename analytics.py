"""Numbers for the admin dashboard, computed from the ticket database with pandas.

Definitions (shown on the dashboard too):
- Open: any status except Resolved / Closed.
- Stalled: open, and no update for 3 days or more.
- Response SLA met: first IT response within the priority's target (Urgent 1h, High 4h, Medium 1 day, Low 3 days).
- Resolution SLA met: resolved within the target (Urgent 4h, High 1 day, Medium 3 days, Low 10 days),
  not counting time spent waiting for approval.
"""
import datetime
import pandas as pd
import db
import sla

STALL_DAYS = 3
TEAMS = ["Service Desk", "Network Team", "Hardware Team", "Apps Team", "Security Team"]
STAGES = ["New", "In progress", "Waiting", "Stalled"]


def _dt(value):
    if not value:
        return None
    if len(value) <= 10:
        value += "T09:00:00+09:00"
    elif "T" not in value:
        value = value.replace(" ", "T") + ":00+09:00"
    return datetime.datetime.fromisoformat(value)


def tickets_frame(names):
    now = db.now()
    rows = []
    for t in db.list_tickets():
        created = _dt(t["created_at"]) or _dt(t["created"])
        responded = _dt(t.get("first_response_at"))
        resolved = _dt(t.get("resolved_at"))
        is_open = t["status"] not in ("Resolved", "Closed")
        if not responded and any(h["text"].startswith(sla.RESPONDERS) for h in t["history"]):
            responded = max(_dt(h["at"]) for h in t["history"] if h["text"].startswith(sla.RESPONDERS))
        if not responded and resolved:
            responded = resolved
        last = max([_dt(h["at"]) for h in t["history"]] or [created])
        paused_h = (t.get("paused_hours") or 0) + (
            (now - _dt(t["paused_since"])).total_seconds() / 3600 if t.get("paused_since") else 0)
        resp_due = created + datetime.timedelta(hours=sla.RESPONSE_HOURS.get(t["priority"], 24))
        res_due = created + datetime.timedelta(hours=sla.RESOLVE_HOURS.get(t["priority"], 72) + paused_h)
        resp_breach = (responded > resp_due) if responded else (now > resp_due)
        resp_known = bool(responded) or now > resp_due
        res_breach = (resolved > res_due) if resolved else (is_open and now > res_due and not t.get("paused_since"))
        res_known = bool(resolved) or res_breach
        stalled = is_open and (now - last) >= datetime.timedelta(days=STALL_DAYS)
        stage = ("Resolved" if not is_open else "Stalled" if stalled else "New" if t["status"] == "New"
                 else "Waiting" if t["status"].startswith("Waiting") else "In progress")
        rows.append({
            "ID": t["ticket_id"], "Title": t["title"], "Team": t["team"], "Priority": t["priority"],
            "Status": t["status"], "Stage": stage, "Category": t["category"] or "Other",
            "Channel": t.get("channel") or "Portal",
            "Requester": names.get(t["requester_email"], t["requester_email"]).split("(")[0].strip(),
            "created": created, "responded": responded, "resolved": resolved, "last_update": last,
            "open": is_open, "stalled": stalled,
            "resp_known": resp_known, "resp_breach": bool(resp_breach) and resp_known,
            "res_known": res_known, "res_breach": bool(res_breach),
            "age_days": (now - created).total_seconds() / 86400,
            "idle_days": (now - last).total_seconds() / 86400,
            "resolve_hours": (resolved - created).total_seconds() / 3600 if resolved else None,
        })
    return pd.DataFrame(rows)


def window(df, days, offset=0):
    """Tickets CREATED in the window [now - days*(offset+1), now - days*offset)."""
    now = db.now()
    end = now - datetime.timedelta(days=days * offset)
    start = end - datetime.timedelta(days=days)
    return df[(df.created >= start) & (df.created < end)], start, end


def resolved_in(df, start, end):
    return df[df.resolved.notna() & (df.resolved >= start) & (df.resolved < end)]


def pct(part, whole):
    return None if whole == 0 else 100 * part / whole


def sla_rates(df):
    resp = df[df.resp_known]
    res = df[df.res_known]
    return (pct((~resp.resp_breach).sum(), len(resp)), pct((~res.res_breach).sum(), len(res)))


def team_scorecard(df_all, df_period, start, end):
    rows = []
    for team in TEAMS:
        p = df_period[df_period.Team == team]
        a = df_all[df_all.Team == team]
        open_t = a[a.open]
        resp, res = sla_rates(p)
        done = resolved_in(a, start, end)
        rows.append({
            "Team": team, "Created": len(p), "Resolved": len(done), "Open": len(open_t),
            "New": int((open_t.Stage == "New").sum()), "In progress": int((open_t.Stage == "In progress").sum()),
            "Waiting": int((open_t.Stage == "Waiting").sum()), "Stalled": int((open_t.Stage == "Stalled").sum()),
            "Response SLA %": resp, "Resolution SLA %": res,
            "SLA breaches": int(p.resp_breach.sum() + p.res_breach.sum()),
            "Median fix (h)": done.resolve_hours.median() if len(done) else None,
        })
    return pd.DataFrame(rows)


def trend(df, granularity, periods):
    """Created per period per team + resolved per period (all teams)."""
    now = db.now()
    if granularity == "Weekly":
        this = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [this - datetime.timedelta(weeks=i) for i in range(periods - 1, -1, -1)]
        nxt = lambda s: s + datetime.timedelta(weeks=1)
        label = lambda s: "This week" if s == this else s.strftime("%b %d").replace(" 0", " ")
    else:
        this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starts = []
        s = this
        for _ in range(periods):
            starts.insert(0, s)
            s = (s - datetime.timedelta(days=1)).replace(day=1)
        nxt = lambda s: (s + datetime.timedelta(days=32)).replace(day=1)
        label = lambda s: s.strftime("%b %Y") + (" (to date)" if s == this else "")
    created, resolved = [], []
    for s in starts:
        e = nxt(s)
        part = df[(df.created >= s) & (df.created < e)]
        for team in TEAMS:
            created.append({"Period": label(s), "Team": team, "Tickets": int((part.Team == team).sum())})
        resolved.append({"Period": label(s), "Series": "Resolved (all teams)",
                         "Tickets": len(resolved_in(df, s, e))})
        va = part[part.Channel == "Virtual agent"]
        resolved[-1]["Agent share %"] = pct(len(va), len(part)) or 0
    return pd.DataFrame(created), pd.DataFrame(resolved), [label(s) for s in starts]


def age_bucket(days):
    for limit, name in ((1, "< 1 day"), (3, "1–3 days"), (7, "3–7 days"), (14, "1–2 weeks")):
        if days < limit:
            return name
    return "> 2 weeks"


AGE_BUCKETS = ["< 1 day", "1–3 days", "3–7 days", "1–2 weeks", "> 2 weeks"]
