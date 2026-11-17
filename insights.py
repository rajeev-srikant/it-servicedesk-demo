"""AI weekly summary for management: the numbers are computed by code, the AI only writes them as plain sentences.

The AI is told to use ONLY the numbers it is given, so the summary cannot contain made-up figures.
"""
import json
import datetime
import db
import analytics as an


def weekly_stats(names):
    df = an.tickets_frame(names)
    cur, start, end = an.window(df, 7)
    prev, pstart, pend = an.window(df, 7, offset=1)
    resp, res = an.sla_rates(cur)
    sc = an.team_scorecard(df, cur, start, end)
    worst = sc.dropna(subset=["Resolution SLA %"]).sort_values("Resolution SLA %").head(1)
    cats_now = cur.groupby("Category").size()
    cats_prev = prev.groupby("Category").size()
    top = [{"category": c, "this_week": int(n), "last_week": int(cats_prev.get(c, 0))}
           for c, n in cats_now.sort_values(ascending=False).head(3).items()]
    sh = [r for r in db.list_self_help() if r["at"][:16] >= start.strftime("%Y-%m-%d %H:%M")]
    solved = sum(1 for r in sh if r["outcome"] == "solved")
    mins = int(db.get_setting("minutes_per_ticket", "60"))
    import kb
    import incidents
    arts = kb.list_articles(kb.STATUS_APPROVED)
    open_now = df[df.open]
    return {
        "period": f"{start:%d %b} to {end:%d %b %Y}",
        "new_tickets": len(cur), "new_tickets_previous_week": len(prev),
        "resolved_tickets": len(an.resolved_in(df, start, end)),
        "response_sla_met_pct": None if resp is None else round(resp), "resolution_sla_met_pct": None if res is None else round(res),
        "sla_target_pct": 90,
        "team_with_lowest_resolution_sla_met_pct": None if worst.empty else
            {"team": worst.iloc[0]["Team"], "resolution_sla_pct": round(worst.iloc[0]["Resolution SLA %"])},
        "top_categories": top,
        "open_tickets_now": len(open_now), "stalled_tickets_now": int(open_now.stalled.sum()),
        "share_of_new_tickets_raised_through_the_ai_chat_pct": round(100 * (cur.Channel == "Virtual agent").mean()) if len(cur) else 0,
        "problems_solved_by_self_help_without_a_ticket": solved, "estimated_it_hours_saved": round(solved * mins / 60),
        "knowledge_base_articles": len(arts), "times_kb_articles_were_suggested_to_employees": sum(a["suggested"] for a in arts),
        "major_incidents_active": len(incidents.active()),
        "knowledge_gap_questions_open": len(kb.open_gaps()),
    }


PROMPT = """You write a short weekly IT service desk summary for bank management (non-technical readers).
Use ONLY the numbers below. Do not invent numbers, causes or names. Plain English, no jargon.
Describe each number exactly as its name says (for example, the share of tickets raised through the AI chat is not
the share of tickets "handled" or "resolved" by the AI).
Format (Markdown):
**Headline:** one sentence.
Then 4 to 6 bullet points: volume and trend, SLA (mention the team below target if any), what people needed help
with (top categories and changes), AI agent impact (self-help, hours saved, knowledge base), risks (stalled tickets,
active incidents, knowledge gaps).
**Suggested action:** one sentence, based only on these numbers.

Numbers (JSON):
{stats}"""


def write(names):
    stats = weekly_stats(names)
    try:
        import agent
        import tools
        r = tools._client.models.generate_content(model=agent.CHAT_MODEL,
                                                  contents=PROMPT.format(stats=json.dumps(stats, ensure_ascii=False)),
                                                  config={"temperature": 0.2})
        agent._usage("weekly-summary", r)
        text = r.text.strip()
    except Exception:
        text = fallback(stats)
    db.set_setting("weekly_summary", json.dumps({"text": text, "at": db.now().strftime("%Y-%m-%d %H:%M"),
                                                 "period": stats["period"]}, ensure_ascii=False))
    return text


def fallback(s):
    trend = s["new_tickets"] - s["new_tickets_previous_week"]
    worst = s["team_with_lowest_resolution_sla_met_pct"]
    return (f"**Headline:** {s['new_tickets']} new tickets this week ({'+' if trend >= 0 else ''}{trend} vs last week).\n\n"
            f"- Resolution SLA met: {s['resolution_sla_met_pct']}% (target {s['sla_target_pct']}%)"
            + (f"; lowest: {worst['team']} at {worst['resolution_sla_pct']}%." if worst else ".") + "\n"
            f"- Self-help solved {s['problems_solved_by_self_help_without_a_ticket']} issues, about {s['estimated_it_hours_saved']} IT hours saved.\n"
            f"- {s['stalled_tickets_now']} tickets are stalled; {s['knowledge_gap_questions_open']} questions have no article yet.\n\n"
            f"**Suggested action:** review the stalled tickets and the knowledge gaps.")


def saved():
    raw = db.get_setting("weekly_summary", "")
    return json.loads(raw) if raw else None
