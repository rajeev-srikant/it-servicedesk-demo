"""Benefits page for senior management (CIO / CTO).

No invented results on this page. Every number is one of three things:
  1. the client's OWN figure, typed into the calculator (defaults are placeholders, marked as such)
  2. a PUBLISHED industry range: AI typically solves ~25-45% of service desk issues in its first year
  3. a pilot TARGET, with how and when it will be measured
Part 1 "What could this be worth for you?" = calculator with three scenarios.
Part 2 "What the pilot will prove"          = scorecard of targets, filled with real data during the pilot.
"""
import html
import altair as alt
import pandas as pd
import streamlit as st
from i18n import tr

e = html.escape
INK, INK2, GRID = "#1B2430", "#5B6B7F", "#EEF0F3"
NAVY, ORANGE, TODAY = "#1F4E8C", "#E07A2E", "#B8C2CE"
FONT = "IBM Plex Sans, Noto Sans JP, Segoe UI, Arial, sans-serif"

FTE_HOURS = 1800             # working hours of one full-time person in a year
SCENARIOS = [("Conservative", 0.25), ("Expected", 0.35), ("Ambitious", 0.45)]   # share of issues the AI solves

# Placeholders until the client gives its own figures
DEFAULTS = {"tickets": 1200, "agent_min": 12, "agent_cost": 2500}

SCORECARD = [   # (benefit, pilot target, how it is measured, how often)
    ("Tickets reaching IT", "▼ 15–25% vs the 3 months before the pilot", "Counted in the ticket system", "Monthly"),
    ("Issues solved by the AI alone", "25–35% by month 3", "Conversations marked “solved” with no ticket raised", "Weekly"),
    ("Time to resolve", "▼ 10% for tickets that reach IT", "Ticket open and close times", "Monthly"),
    ("Employee satisfaction", "75% or more find the answer helpful", "👍 / 👎 on every AI answer", "Weekly"),
    ("Help outside office hours", "Reported (no target)", "Time of each conversation", "Monthly"),
    ("Safety", "0 changes without a person’s confirmation", "Audit log of every action", "Continuous"),
]

CSS = """<style>
.bn-meta { font-size:12.5px; color:#5B6B7F; margin:-4px 0 16px; }
.bn-sec { font-size:18px; font-weight:600; color:#1B2430; margin:18px 0 2px; }
.bn-secsub { font-size:13px; color:#5B6B7F; margin-bottom:12px; }
.bn-scen { display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; margin:6px 0 14px; }
.bn-card { background:#fff; border:1px solid var(--line); border-radius:6px; padding:16px 18px; }
.bn-card.mid { border:2px solid #1F4E8C; }
.bn-name { font-size:13px; font-weight:600; color:#5B6B7F; letter-spacing:.3px; }
.bn-pct { font-size:13px; color:#5B6B7F; margin-bottom:8px; }
.bn-big { font-size:30px; font-weight:600; color:#1B2430; line-height:1.15; }
.bn-bigl { font-size:12.5px; color:#5B6B7F; margin-bottom:10px; }
.bn-row { display:flex; justify-content:space-between; font-size:13.5px; padding:6px 0; border-top:1px solid #EEF0F3; }
.bn-row b { color:#1B2430; }
.bn-row span { color:#5B6B7F; }
[class*="st-key-bn_"] { background:#fff; border:1px solid var(--line); border-radius:6px; padding:16px 18px 6px; }
.bn-h { font-size:16px; font-weight:600; color:#1B2430; }
.bn-n { font-size:12.5px; color:#5B6B7F; margin-bottom:4px; }
.bn-table { width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:6px; font-size:13.5px; }
.bn-table th { text-align:left; font-weight:600; color:#5B6B7F; font-size:12.5px; padding:10px 14px; border-bottom:1px solid var(--line); background:#F7F8FA; }
.bn-table td { padding:10px 14px; border-bottom:1px solid #EEF0F3; color:#1B2430; vertical-align:top; }
.bn-table td.k { font-weight:600; }
.bn-pill { display:inline-block; font-size:12px; color:#5B6B7F; background:#EEF0F3; border-radius:10px; padding:2px 9px; white-space:nowrap; }
.bn-src { font-size:12px; color:#5B6B7F; margin-top:10px; }
</style>"""


def _yen(v):
    """¥ in the reader's language: ¥2.5M in English, ¥250万 in Japanese."""
    if st.session_state.get("lang") == "ja":
        return f"¥{v / 1e4:,.0f}万"
    return f"¥{v / 1e6:,.1f}M" if v >= 1e6 else f"¥{v / 1e3:,.0f}k"


def render():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="dash-title" style="margin-bottom:14px">{e(tr("Business value"))}</div>',
                unsafe_allow_html=True)

    # ================================================================ 1. calculator
    c1, c2, c3 = st.columns(3)
    tickets = c1.number_input(tr("Service desk tickets per month"), 50, 100000, DEFAULTS["tickets"], step=50, key="bn_t")
    agent_min = c2.number_input(tr("Helpdesk staff minutes per simple ticket"), 1, 240, DEFAULTS["agent_min"], step=1,
                                key="bn_m", help=tr("Time a helpdesk person spends on one simple ticket (password, VPN, how-to): reading, replying, fixing, closing."))
    agent_cost = c3.number_input(tr("Cost of one helpdesk staff hour (¥)"), 500, 50000, DEFAULTS["agent_cost"], step=100,
                                 key="bn_c", help=tr("Salary and overheads of one helpdesk person, per hour."))

    rows = []
    for name, rate in SCENARIOS:
        avoided = tickets * rate * 12
        agent_h = avoided * agent_min / 60
        rows.append({"Scenario": tr(name), "rate": rate, "avoided": avoided, "agent_h": agent_h,
                     "yen": agent_h * agent_cost, "fte": agent_h / FTE_HOURS,
                     "after": tickets * (1 - rate)})

    cards = ""
    for i, r in enumerate(rows):
        cards += (f'<div class="bn-card{" mid" if i == 1 else ""}">'
                  f'<div class="bn-name">{e(r["Scenario"].upper() if st.session_state.get("lang") != "ja" else r["Scenario"])}</div>'
                  f'<div class="bn-pct">{e(tr("AI solves {p}% of issues", p=round(r["rate"] * 100)))}</div>'
                  f'<div class="bn-big">{e(_yen(r["yen"]))}</div>'
                  f'<div class="bn-bigl">{e(tr("helpdesk staff time saved per year"))}</div>'
                  f'<div class="bn-row"><span>{e(tr("Tickets avoided per year"))}</span><b>{r["avoided"]:,.0f}</b></div>'
                  f'<div class="bn-row"><span>{e(tr("Helpdesk staff hours freed per year"))}</span><b>{r["agent_h"]:,.0f} h</b></div>'
                  f'<div class="bn-row"><span>{e(tr("Equal to full-time helpdesk staff"))}</span><b>{r["fte"]:.1f}</b></div>'
                  '</div>')
    st.markdown(f'<div class="bn-scen">{cards}</div>', unsafe_allow_html=True)

    # one simple picture: tickets reaching IT per month, today vs each scenario
    chart_df = pd.DataFrame([{"Label": tr("Today"), "Tickets": tickets, "Kind": "today"}]
                            + [{"Label": r["Scenario"], "Tickets": round(r["after"]), "Kind": "with AI"} for r in rows])
    order = list(chart_df["Label"])
    base = alt.Chart(chart_df).encode(y=alt.Y("Label:N", sort=order, title=None),
                                      x=alt.X("Tickets:Q", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)))
    chart = (base.mark_bar(height=26, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
             .encode(color=alt.Color("Kind:N", scale=alt.Scale(domain=["today", "with AI"], range=[TODAY, NAVY]),
                                     legend=None), tooltip=["Label", "Tickets"])
             + base.mark_text(align="left", dx=6, color=INK, fontSize=12).encode(text=alt.Text("Tickets:Q", format=",")))
    chart = (chart.properties(height=170, background="transparent").configure_view(stroke=None)
             .configure_axis(labelColor=INK2, gridColor=GRID, domain=False, tickColor=GRID, labelFontSize=12,
                             labelFont=FONT))
    with st.container(key="bn_chart"):
        st.markdown(f'<div class="bn-h">{e(tr("Tickets reaching IT per month"))}</div>'
                    f'<div class="bn-n">{e(tr("Today, and after the AI solves its share."))}</div>', unsafe_allow_html=True)
        st.altair_chart(chart, width="stretch", theme=None)
