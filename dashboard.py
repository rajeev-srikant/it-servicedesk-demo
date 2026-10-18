"""The IT Admin's service dashboard: KPIs, charts, team scorecard, SLA breaches and tickets needing attention.
All numbers come from analytics.py; this file only draws them (Streamlit + Altair charts)."""
import html
import altair as alt
import pandas as pd
import streamlit as st
import analytics as an
import db

e = html.escape
INK, INK2, GRID = "#1B2430", "#5B6B7F", "#EEF0F3"
# Fixed team colours (validated categorical order; colour follows the team, never its rank)
TEAM_COLOR = dict(zip(an.TEAMS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
STAGE_COLOR = {"New": "#86b6ef", "In progress": "#2a78d6", "Waiting": "#184f95", "Stalled": "#ec835a"}
PRIORITY_COLOR = {"Low": "#86b6ef", "Medium": "#3987e5", "High": "#1c5cab", "Urgent": "#0d366b"}
FONT = "IBM Plex Sans, Noto Sans JP, Segoe UI, Arial, sans-serif"
GOOD, BAD, NEUTRAL = "#0a7a0a", "#b42318", "#5B6B7F"
TARGET = 90


def _style(chart, height=260):
    return (chart.properties(height=height, background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelColor=INK2, titleColor=INK2, gridColor=GRID, domain=False, tickColor=GRID,
                            labelFontSize=12, titleFontSize=12, titleFontWeight="normal", labelFont=FONT,
                            titleFont=FONT)
            .configure_legend(orient="top", title=None, labelColor=INK, labelFontSize=12, symbolSize=110,
                              labelFont=FONT)
            .configure_text(font=FONT))


def _show(chart, height=260):
    st.altair_chart(_style(chart, height), width="stretch", theme=None)


def _card_title(title, note=""):
    st.markdown(f'<div class="dash-h">{e(title)}</div>' + (f'<div class="dash-n">{e(note)}</div>' if note else ""),
                unsafe_allow_html=True)


def _delta(now_v, prev_v, good_when_up, unit="%", is_rate=False):
    if now_v is None or prev_v is None:
        return '<span class="kd" style="color:#5B6B7F">no earlier data</span>'
    diff = now_v - prev_v
    if abs(diff) < (0.5 if is_rate else 1e-9):
        return '<span class="kd" style="color:#5B6B7F">→ no change vs previous period</span>'
    up = diff > 0
    color = GOOD if up == good_when_up else BAD
    word = "better" if up == good_when_up else "worse"
    if is_rate:
        txt = f"{'▲' if up else '▼'} {abs(diff):.0f} pts vs previous · {word}"
    else:
        rel = f"{abs(diff) / prev_v * 100:.0f}%" if prev_v else f"{abs(diff):.0f}"
        txt = f"{'▲' if up else '▼'} {rel} vs previous · {word}"
    return f'<span class="kd" style="color:{color}">{txt}</span>'


def _kpi(label, value, delta_html, hint=""):
    return (f'<div class="kpi2"><div class="kl">{e(label)}</div><div class="kv">{value}</div>{delta_html}'
            + (f'<div class="kh">{e(hint)}</div>' if hint else "") + "</div>")


def _fmt_pct(v):
    return "–" if v is None else f"{v:.0f}%"


def render(names):
    df_all = an.tickets_frame(names)

    # ---------- Header + filters (one row) ----------
    h1, f1, f2, f3 = st.columns([1.6, 1.25, 1.5, 1.05], vertical_alignment="bottom")
    h1.markdown(f'<div class="dash-title">Service desk dashboard</div>'
                f'<div class="dash-sub">As of {db.now():%d %b %Y, %H:%M} JST · demo data</div>',
                unsafe_allow_html=True)
    period_label = f1.segmented_control("Period", ["7 days", "30 days", "90 days"], default="30 days",
                                        key="dash_period") or "30 days"
    days = int(period_label.split()[0])
    teams = f2.multiselect("Teams", an.TEAMS, key="dash_teams", placeholder="All teams") or an.TEAMS
    gran = f3.segmented_control("Trend", ["Weekly", "Monthly"], default="Weekly", key="dash_gran") or "Weekly"

    df = df_all[df_all.Team.isin(teams)]
    cur, start, end = an.window(df, days)
    prev, pstart, pend = an.window(df, days, offset=1)
    resolved_cur = an.resolved_in(df, start, end)
    resolved_prev = an.resolved_in(df, pstart, pend)
    resp, res = an.sla_rates(cur)
    presp, pres = an.sla_rates(prev)
    open_now = df[df.open]
    stalled = open_now[open_now.stalled]

    # ---------- KPI row ----------
    pl = f"previous {days} days"
    st.markdown('<div class="kpis6">' + "".join([
        _kpi("Open tickets", len(open_now), f'<span class="kd" style="color:#5B6B7F">{len(stalled)} stalled · '
             f'{int((open_now.res_breach | open_now.resp_breach).sum())} overdue</span>'),
        _kpi(f"New tickets · {days}d", len(cur), _delta(len(cur), len(prev), good_when_up=False), f"vs {pl}"),
        _kpi(f"Resolved · {days}d", len(resolved_cur), _delta(len(resolved_cur), len(resolved_prev), True)),
        _kpi("Response SLA met", _fmt_pct(resp), _delta(resp, presp, True, is_rate=True), f"target {TARGET}%"),
        _kpi("Resolution SLA met", _fmt_pct(res), _delta(res, pres, True, is_rate=True), f"target {TARGET}%"),
        _kpi("Median time to fix", f"{resolved_cur.resolve_hours.median():.0f} h" if len(resolved_cur) else "–",
             _delta(resolved_cur.resolve_hours.median() if len(resolved_cur) else None,
                    resolved_prev.resolve_hours.median() if len(resolved_prev) else None, good_when_up=False)),
    ]) + "</div>", unsafe_allow_html=True)

    # ---------- Row: volume trend | open backlog by team ----------
    c1, c2 = st.columns([1.7, 1], gap="medium")
    with c1, st.container(key="card_trend"):
        created, resolved, order = an.trend(df, gran, 10 if gran == "Weekly" else 3)
        created = created[created.Team.isin(teams)]
        _card_title(f"Ticket volume · {gran.lower()}", "New tickets by team (bars) and tickets resolved (line)")
        bars = alt.Chart(created).mark_bar(cornerRadiusEnd=0, stroke="#ffffff", strokeWidth=1.5).encode(
            x=alt.X("Period:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("sum(Tickets):Q", title="Tickets"),
            color=alt.Color("Team:N", scale=alt.Scale(domain=an.TEAMS + ["Resolved (all teams)"],
                                                      range=list(TEAM_COLOR.values()) + [INK]),
                            legend=alt.Legend(columns=3, symbolType="square")),
            order=alt.Order("team_order:Q"),
            tooltip=["Period", "Team", alt.Tooltip("Tickets:Q", title="New tickets")],
        ).transform_calculate(team_order=f"indexof({an.TEAMS}, datum.Team)")
        line = alt.Chart(resolved).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=55, filled=True)).encode(
            x=alt.X("Period:N", sort=order), y="Tickets:Q",
            color=alt.Color("Series:N"),
            tooltip=["Period", alt.Tooltip("Tickets:Q", title="Resolved")])
        _show(bars + line, 270)
    with c2, st.container(key="card_backlog"):
        _card_title("Open tickets by team", "Where the backlog sits today, by stage")
        ob = (open_now.groupby(["Team", "Stage"]).size().reset_index(name="Tickets"))
        if ob.empty:
            st.caption("No open tickets.")
        else:
            chart = alt.Chart(ob).mark_bar(stroke="#ffffff", strokeWidth=1.5, cornerRadiusEnd=0).encode(
                y=alt.Y("Team:N", sort=an.TEAMS, title=None),
                x=alt.X("sum(Tickets):Q", title="Open tickets", axis=alt.Axis(tickMinStep=1, format="d")),
                color=alt.Color("Stage:N", scale=alt.Scale(domain=an.STAGES, range=list(STAGE_COLOR.values())),
                                legend=alt.Legend(columns=2, symbolType="square")),
                order=alt.Order("stage_order:Q"),
                tooltip=["Team", "Stage", "Tickets"],
            ).transform_calculate(stage_order=f"indexof({an.STAGES}, datum.Stage)")
            _show(chart, 270)

    # ---------- Team scorecard ----------
    with st.container(key="card_score"):
        _card_title(f"Team scorecard · last {days} days",
                    "Created and resolved in the period; open, waiting and stalled as of now. "
                    f"Red SLA cells are below the {TARGET}% target.")
        sc = an.team_scorecard(df, cur, start, end)
        sc = sc[sc.Team.isin(teams)]

        def flag(v):
            return "" if v is None or pd.isna(v) else (f"color:{BAD};font-weight:600" if v < TARGET else "")
        styled = (sc.style.format({"Response SLA %": lambda v: "–" if pd.isna(v) else f"{v:.0f}%",
                                   "Resolution SLA %": lambda v: "–" if pd.isna(v) else f"{v:.0f}%",
                                   "Median fix (h)": lambda v: "–" if pd.isna(v) else f"{v:.0f}"})
                  .map(flag, subset=["Response SLA %", "Resolution SLA %"])
                  .map(lambda v: f"color:{BAD};font-weight:600" if v else "", subset=["Stalled"]))
        st.dataframe(styled, hide_index=True, width="stretch")

    # ---------- Row: SLA by team | backlog age ----------
    c3, c4 = st.columns(2, gap="medium")
    with c3, st.container(key="card_sla"):
        _card_title("Where SLAs are missed", f"% of tickets meeting the target, last {days} days · "
                                             f"dashed line = {TARGET}% target")
        rows = []
        for _, r in sc.iterrows():
            for metric in ("Response", "Resolution"):
                v = r[f"{metric} SLA %"]
                if v is not None and not pd.isna(v):
                    rows.append({"Team": r.Team, "Measure": f"{metric} SLA", "Met %": round(v),
                                 "Status": "Below target" if v < TARGET else "On target"})
        sd = pd.DataFrame(rows)
        if sd.empty:
            st.caption("Not enough tickets in this period.")
        else:
            base = alt.Chart(sd).encode(y=alt.Y("Team:N", sort=an.TEAMS, title=None))
            rule = alt.Chart(pd.DataFrame({"x": [TARGET]})).mark_rule(strokeDash=[5, 4], color=BAD, strokeWidth=1.5
                                                                       ).encode(x=alt.X("x:Q", scale=alt.Scale(domain=[40, 100]), axis=None))
            pts = base.mark_point(size=150, filled=True, strokeWidth=2, opacity=1).encode(
                x=alt.X("Met %:Q", scale=alt.Scale(domain=[40, 100]), title="SLA met (%)",
                      axis=alt.Axis(values=[40, 50, 60, 70, 80, 90, 100])),
                shape=alt.Shape("Measure:N", scale=alt.Scale(domain=["Response SLA", "Resolution SLA"],
                                                             range=["circle", "square"])),
                color=alt.Color("Measure:N", scale=alt.Scale(domain=["Response SLA", "Resolution SLA"],
                                                             range=["#86b6ef", "#184f95"])),
                yOffset=alt.YOffset("Measure:N", scale=alt.Scale(domain=["Response SLA", "Resolution SLA"])),
                tooltip=["Team", "Measure", alt.Tooltip("Met %:Q", title="Met (%)"), "Status"])
            _show(rule + pts, 250)
    with c4, st.container(key="card_age"):
        _card_title("Age of open tickets", "How long open tickets have been waiting, by priority")
        if open_now.empty:
            st.caption("No open tickets.")
        else:
            ag = open_now.assign(Age=open_now.age_days.map(an.age_bucket)).groupby(["Age", "Priority"]).size(
                ).reset_index(name="Tickets")
            chart = alt.Chart(ag).mark_bar(stroke="#ffffff", strokeWidth=1.5).encode(
                x=alt.X("Age:N", sort=an.AGE_BUCKETS, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("sum(Tickets):Q", title="Open tickets", axis=alt.Axis(tickMinStep=1, format="d")),
                color=alt.Color("Priority:N", scale=alt.Scale(domain=list(PRIORITY_COLOR),
                                                              range=list(PRIORITY_COLOR.values()))),
                order=alt.Order("p_order:Q"),
                tooltip=["Age", "Priority", "Tickets"],
            ).transform_calculate(p_order=f"indexof({list(PRIORITY_COLOR)}, datum.Priority)")
            _show(chart, 250)

    # ---------- Row: top categories | AI impact ----------
    c5, c6 = st.columns(2, gap="medium")
    with c5, st.container(key="card_cat"):
        _card_title("What people need help with", f"Top request categories, last {days} days")
        cat = cur.groupby("Category").size().reset_index(name="Tickets").sort_values("Tickets", ascending=False)
        cat = cat.head(8)
        if cat.empty:
            st.caption("No tickets in this period.")
        else:
            b = alt.Chart(cat).encode(y=alt.Y("Category:N", sort="-x", title=None),
                                      x=alt.X("Tickets:Q", title="Tickets", axis=alt.Axis(tickMinStep=1, format="d")))
            _show(b.mark_bar(color="#2a78d6", cornerRadiusEnd=4, height=16)
                  .encode(tooltip=["Category", "Tickets"])
                  + b.mark_text(align="left", dx=6, color=INK, fontSize=12).encode(text="Tickets:Q"), 250)
    with c6, st.container(key="card_ai"):
        _card_title("AI virtual agent impact", f"Last {days} days, all teams")
        sh = pd.DataFrame(db.list_self_help())
        if not sh.empty:
            sh["at"] = pd.to_datetime(sh["at"]).dt.tz_localize(db.TOKYO)
            sh = sh[(sh["at"] >= start) & (sh["at"] < end)]
        solved = int((sh.outcome == "solved").sum()) if not sh.empty else 0
        asked = len(sh)
        all_cur, _, _ = an.window(df_all, days)
        va = int((all_cur.Channel == "Virtual agent").sum())
        st.markdown('<div class="kpis3">' + "".join([
            _kpi("Solved by self-help", solved, f'<span class="kd" style="color:#5B6B7F">'
                 f'{an.pct(solved, asked) or 0:.0f}% of self-help chats</span>'),
            _kpi("Tickets via the agent", f"{an.pct(va, len(all_cur)) or 0:.0f}%",
                 f'<span class="kd" style="color:#5B6B7F">{va} of {len(all_cur)} new tickets</span>'),
            _kpi("IT time saved (est.)", f"{solved * 15 / 60:.0f} h",
                 '<span class="kd" style="color:#5B6B7F">15 min per avoided ticket</span>'),
        ]) + "</div>", unsafe_allow_html=True)
        _, share, order = an.trend(df_all, "Weekly", 10)
        lc = alt.Chart(share).mark_line(color="#2a78d6", strokeWidth=2,
                                        point=alt.OverlayMarkDef(size=50, filled=True, color="#2a78d6")).encode(
            x=alt.X("Period:N", sort=order, title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True)),
            y=alt.Y("Agent share %:Q", title="New tickets via agent (%)", scale=alt.Scale(domain=[0, 100])),
            tooltip=["Period", alt.Tooltip("Agent share %:Q", format=".0f", title="Via agent (%)")])
        _show(lc, 150)

    # ---------- Needs attention ----------
    with st.container(key="card_attn"):
        att = open_now[open_now.res_breach | open_now.resp_breach | open_now.stalled].copy()
        _card_title(f"Needs attention · {len(att)}", "Open tickets that are overdue or have had no update for "
                                                    f"{an.STALL_DAYS}+ days, most urgent first")
        if att.empty:
            st.caption("Nothing needs attention right now.")
        else:
            def issue(r):
                parts = []
                if r.res_breach:
                    parts.append("Resolution overdue")
                elif r.resp_breach:
                    parts.append("No response in time")
                if r.stalled:
                    parts.append(f"No update {r.idle_days:.0f} days")
                return " · ".join(parts)
            att["Issue"] = att.apply(issue, axis=1)
            att["rank"] = att.Priority.map({"Urgent": 0, "High": 1, "Medium": 2, "Low": 3})
            att["Age (days)"] = att.age_days.round(0).astype(int)
            att = att.sort_values(["rank", "age_days"], ascending=[True, False])
            st.dataframe(att[["ID", "Issue", "Team", "Priority", "Status", "Title", "Requester", "Age (days)"]],
                         hide_index=True, width="stretch", height=min(38 + 35 * len(att), 320))
        export = df[["ID", "Title", "Team", "Priority", "Status", "Stage", "Category", "Channel", "Requester",
                     "created", "responded", "resolved", "resp_breach", "res_breach", "stalled"]]
        st.download_button("Download all tickets (CSV)", icon=":material/download:", data=export.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"testbank_tickets_{db.now():%Y%m%d}.csv", mime="text/csv")

    st.markdown(f'<div class="dash-n" style="margin-top:6px">Definitions: <b>Stalled</b> = open with no update for '
                f'{an.STALL_DAYS}+ days. <b>Response SLA</b> = first IT reply within Urgent 1h · High 4h · '
                'Medium 1 day · Low 3 days. <b>Resolution SLA</b> = fixed within Urgent 4h · High 1 day · '
                'Medium 3 days · Low 10 days (time waiting for approval not counted). Demo data only.</div>',
                unsafe_allow_html=True)


DASH_CSS = """
.dash-title { font-size:20px; font-weight:600; color:#1A2230; line-height:1.2; }
.dash-sub { font-size:12.5px; color:#5A6575; margin-top:3px; }
.dash-h { font-size:14.5px; font-weight:600; color:#1A2230; }
.dash-n { font-size:12.5px; color:#5A6575; margin:2px 0 8px 0; }
.kpis6 { display:grid; grid-template-columns:repeat(6, 1fr); margin:14px 0 14px 0; background:#fff;
  border:1px solid #DADFE6; border-radius:4px; }
.kpis6 .kpi2 { padding:12px 16px; border-right:1px solid #EBEEF2; }
.kpis6 .kpi2:last-child { border-right:none; }
.kpis3 { display:grid; grid-template-columns:repeat(3, 1fr); margin:4px 0 8px 0; border:1px solid #EBEEF2; border-radius:4px; }
.kpis3 .kpi2 { padding:10px 12px; border-right:1px solid #EBEEF2; }
.kpis3 .kpi2:last-child { border-right:none; }
.kl { font-size:11.5px; color:#5A6575; font-weight:500; text-transform:uppercase; letter-spacing:.5px; }
.kv { font-size:26px; font-weight:600; color:#1A2230; line-height:1.35; }
.kpis3 .kv { font-size:21px; }
.kd { font-size:12px; font-weight:500; display:block; }
.kh { font-size:11.5px; color:#8A94A3; }
[class*="st-key-card_"] { background:#fff; border:1px solid #DADFE6; border-radius:4px; padding:14px 18px 8px 18px;
  margin-bottom:4px; }
@media (max-width: 1100px) { .kpis6 { grid-template-columns:repeat(3, 1fr); } }
"""
