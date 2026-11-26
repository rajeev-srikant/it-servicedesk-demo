"""The page an IT team member sees (for example Kenta Ito, Apps Team).

- The team's open tickets, most urgent first: breached, then at risk, then on track
- The proactive SLA alerts the AI wrote for this team, with a suggested next step
- Simple actions: reply to the user, resolve
The employee who raised the ticket gets an in-app notification for every reply or resolution.
"""
import html

import streamlit as st

import catalog
import db
import sla
import sla_alerts
from i18n import tr, tr_sla

e = html.escape
LEVEL = {"breached": ("Breached", "#B42318", "#FDEEEE"), "at_risk": ("At risk", "#B54708", "#FFF6E5"),
         None: ("On track", "#067647", "#ECFDF3")}

CSS = """<style>
.tv-kpis { display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin:6px 0 16px; }
.tv-kpi { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px 16px; }
.tv-kpi b { display:block; font-size:28px; color:#1B2430; line-height:1.2; }
.tv-kpi span { font-size:12.5px; color:#5B6B7F; }
.tv-lvl { display:inline-block; font-size:11.5px; font-weight:600; border-radius:3px; padding:1px 8px; }
[class*="st-key-tq_"] { background:#fff; border:1px solid var(--line); border-radius:4px; padding:12px 16px; margin-bottom:8px; }
.tv-alert { background:#fff; border:1px solid var(--line); border-radius:4px; padding:12px 14px; margin-bottom:8px; font-size:13.5px; }
.tv-alert .head { display:flex; justify-content:space-between; gap:8px; margin-bottom:6px; }
.tv-alert .txt { color:#1B2430; line-height:1.5; white-space:pre-line; }
.tv-alert .when { font-size:12px; color:#5B6B7F; }
.tv-note { font-size:12.5px; color:#5B6B7F; margin:-6px 0 12px; }
</style>"""


def _lvl(level):
    name, fg, bg = LEVEL[level]
    return f'<span class="tv-lvl" style="color:{fg};background:{bg}">{e(tr(name))}</span>'


def render(user, team, employees, names, client):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="dash-title">{e(tr("{team} queue", team=team))}</div>'
                f'<div class="dash-sub">{e(tr("Open tickets for your team, most urgent first. The AI warns you before a ticket misses its target."))}</div>',
                unsafe_allow_html=True)
    if st.button(tr("Run SLA check now"), icon=":material/notifications_active:",
                 help=tr("In the pilot this runs automatically every 10–15 minutes.")):
        with st.spinner(tr("Checking service targets…")):
            n = sla_alerts.check(client, employees, force=True)
        st.toast(tr("{n} new SLA alerts", n=n) if n else tr("No new SLA alerts"))
        st.rerun()

    tickets = [t for t in db.list_tickets() if t["team"] == team and t["status"] not in ("Resolved", "Closed")]
    tickets.sort(key=sla_alerts.urgency)
    levels = [sla_alerts._state(t)[0] for t in tickets]
    st.markdown('<div class="tv-kpis">'
                f'<div class="tv-kpi"><b>{len(tickets)}</b><span>{e(tr("Open tickets"))}</span></div>'
                f'<div class="tv-kpi"><b style="color:#B54708">{levels.count("at_risk")}</b><span>{e(tr("At risk"))}</span></div>'
                f'<div class="tv-kpi"><b style="color:#B42318">{levels.count("breached")}</b><span>{e(tr("Breached"))}</span></div>'
                '</div>', unsafe_allow_html=True)

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown(f'<div class="section-title">{e(tr("Team queue"))}</div>', unsafe_allow_html=True)
        if not tickets:
            st.caption(tr("No open tickets. Well done."))
        for t, level in zip(tickets, levels):
            _queue_card(t, level, team, user, names)
    with right:
        st.markdown(f'<div class="section-title">{e(tr("SLA alerts written by the AI"))}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tv-note">{e(tr("Sent to your team in the 🔔 bell. Breached tickets are also escalated to the Service Desk manager."))}</div>',
                    unsafe_allow_html=True)
        alerts = sla_alerts.alerts_for(team)
        if not alerts:
            st.caption(tr("No SLA alerts yet."))
        status = {t["ticket_id"]: t["status"] for t in db.list_tickets()}
        for a in alerts:
            done = status.get(a["ticket_id"]) in ("Resolved", "Closed")
            st.markdown(f'<div class="tv-alert"><div class="head"><span>{_lvl(a["level"])} '
                        f'<b>{e(a["ticket_id"])}</b>{" · " + e(tr("Resolved")) + " ✓" if done else ""}</span>'
                        f'<span class="when">{e(a["at"][5:])}</span></div>'
                        f'<div class="txt">{e(a["text"])}</div></div>', unsafe_allow_html=True)


def _queue_card(t, level, team, user, names):
    r, res = sla.status(t), sla.resolution(t)
    who = names.get(t["requester_email"], t["requester_email"]).split("(")[0].strip()
    first = next((h["text"] for h in t.get("history", [])), "")
    with st.container(key=f"tq_{t['ticket_id']}"):
        st.markdown(f'<div class="tk-top"><span class="tk-id">{e(t["ticket_id"])}</span> {_lvl(level)}</div>'
                    f'<div class="tk-title">{e(t["title"])}</div>'
                    f'<div class="tk-meta">{e(who)} ({e(t.get("department") or "—")}) · '
                    f'{e(tr("{team} · {pr} priority · Opened {when}", team=tr(t["status"]), pr=tr(t["priority"]), when=t["created"]))}</div>'
                    f'<div style="margin-top:6px"><span class="sla sla-{r["state"]}">{e(tr_sla(r["label"]))}</span> '
                    + (f'<span class="sla sla-{res["state"]}">{e(tr_sla(res["label"]))}</span>' if res["label"] else "")
                    + '</div>', unsafe_allow_html=True)
        if first:
            st.caption(first[:160])
        b1, b2 = st.columns(2)
        with b1.popover(tr("Reply to user"), icon=":material/reply:", width="stretch"):
            with st.form(f"rp_{t['ticket_id']}", border=False):
                msg = st.text_area(tr("Message"), height=90, placeholder=tr("e.g. I'm checking this now and will call you in 10 minutes."))
                if st.form_submit_button(tr("Send"), type="primary") and msg.strip():
                    db.add_history(t["ticket_id"], f"{team}: {msg.strip()}")
                    db.mark_responded(t["ticket_id"])
                    if t["status"] == "New":
                        db.update_ticket(t["ticket_id"], status="In progress")
                    catalog.notify(t["requester_email"], "IT updated your ticket {tid}: {changes}.", t["ticket_id"],
                                   changes=msg.strip()[:120].rstrip("."))
                    db.log_audit(user, "team_reply", {"ticket_id": t["ticket_id"]}, {"text": msg.strip()}, "user action")
                    st.toast(tr("Reply sent to {name}.", name=who))
                    st.rerun()
        with b2.popover(tr("Resolve"), icon=":material/task_alt:", width="stretch"):
            with st.form(f"rs_{t['ticket_id']}", border=False):
                fix = st.text_area(tr("How was it fixed?"), height=90)
                if st.form_submit_button(tr("Resolve"), type="primary") and fix.strip():
                    db.add_history(t["ticket_id"], f"{team}: Resolved. {fix.strip()}")
                    db.mark_responded(t["ticket_id"])
                    db.update_ticket(t["ticket_id"], status="Resolved")
                    db.clear_waiting(t["ticket_id"])
                    catalog.notify(t["requester_email"], "IT updated your ticket {tid}: {changes}.", t["ticket_id"],
                                   changes=tr("Resolved") + " – " + fix.strip()[:100].rstrip("."))
                    db.log_audit(user, "team_resolve", {"ticket_id": t["ticket_id"]}, {"fix": fix.strip()}, "user action")
                    st.toast(tr("{id} resolved.", id=t["ticket_id"]))
                    st.rerun()
