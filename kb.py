"""Knowledge loop: fixes from resolved tickets become knowledge base (KB) articles the agent can suggest.

1. IT resolves a ticket and writes how it was fixed (the resolution note).
2. The AI drafts a short KB article from the ticket: symptoms + steps, with names and personal data removed.
3. An IT admin reviews, edits and approves it (human in the loop: only checked fixes reach employees).
4. Approved articles are added to the agent's search, next to the policy documents.
5. The next person with the same problem gets the fix as self-help, before any ticket is raised.
"""
import json
import re
import numpy as np
import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS kb_articles (id TEXT PRIMARY KEY, title TEXT, symptoms TEXT, steps TEXT, team TEXT,
    category TEXT, source_ticket TEXT, resolution_note TEXT, status TEXT, created_at TEXT, created_by TEXT,
    reviewed_by TEXT, reviewed_at TEXT, vector TEXT, suggested INTEGER DEFAULT 0, solved INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS kb_gaps (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, user TEXT, question TEXT,
    source TEXT, status TEXT DEFAULT 'open');
"""
STATUS_DRAFT, STATUS_APPROVED, STATUS_REJECTED = "Waiting for review", "Approved", "Rejected"

# Two articles that already exist when the demo starts (dummy content)
SEED = [
    {"title": "Outlook stuck on 'Updating Inbox'", "team": "Service Desk", "category": "Email",
     "symptoms": "Outlook opens but the inbox stays on 'Updating' and new emails do not arrive.",
     "steps": ["Close Outlook completely (check the system tray).",
               "Open Outlook again while holding Ctrl, and choose 'Yes' to start in safe mode.",
               "Wait until the inbox updates, then close and open Outlook normally.",
               "If it still does not update after 15 minutes, reply 'not solved' to raise a ticket."],
     "source_ticket": "T-0912", "resolution_note": "Rebuilt profile not needed: safe mode start cleared the stuck sync."},
    {"title": "Teams add-in missing in Outlook", "team": "Apps Team", "category": "Software",
     "symptoms": "The 'New Teams Meeting' button is missing from the Outlook calendar.",
     "steps": ["Close Outlook and Teams.", "Start Teams first and wait until it has fully signed in.",
               "Start Outlook again: the Teams Meeting add-in loads after Teams.",
               "If the button is still missing, reply 'not solved' to raise a ticket."],
     "source_ticket": "T-0957", "resolution_note": "Add-in loads correctly when Teams starts before Outlook."},
]


SEED_GAPS = [
    ("How do I add the office printer on my Mac?", "kenji.sato@testbank.com"),
    ("My MacBook can't find the 5th floor printer", "yuki.nakamura@testbank.com"),
    ("Printer setup for macOS?", "taro.yamada@testbank.com"),
    ("What is the guest Wi-Fi password for visitors?", "emi.watanabe@testbank.com"),
    ("Can my visitor use the office Wi-Fi?", "mai.saito@testbank.com"),
    ("How do I connect the meeting room screen to my laptop?", "hana.suzuki@testbank.com"),
    ("The meeting room display shows no signal", "takumi.kobayashi@testbank.com"),
    ("How do I share my screen on the conference room TV?", "kenji.sato@testbank.com"),
    ("How do I set up email signature with the new logo?", "yuki.nakamura@testbank.com"),
]


def init():
    with db._conn() as c:
        c.executescript(SCHEMA)
        empty = c.execute("SELECT COUNT(*) FROM kb_articles").fetchone()[0] == 0
        no_gaps = c.execute("SELECT COUNT(*) FROM kb_gaps").fetchone()[0] == 0
    if empty:
        for a in SEED:
            _insert(dict(a, status=STATUS_APPROVED, created_by="demo data", reviewed_by="Aiko Tanaka"))
    if empty and no_gaps:                          # demo: questions the agent could not answer last week
        import datetime
        with db._conn() as c:
            for i, (q, who) in enumerate(SEED_GAPS):
                at = (db.now() - datetime.timedelta(hours=7 * i + 3)).strftime("%Y-%m-%d %H:%M")
                c.execute("INSERT INTO kb_gaps (at, user, question, source) VALUES (?,?,?,?)",
                          (at, who, q, "agent could not answer"))


def reset():
    with db._conn() as c:
        c.executescript(SCHEMA)
        c.execute("DELETE FROM kb_articles")
        c.execute("DELETE FROM kb_gaps")
    init()


def _next_id(c):
    nums = [int(r[0].split("-")[1]) for r in c.execute("SELECT id FROM kb_articles")]
    return f"KB-{max(nums, default=0) + 1:03d}"


def _insert(a):
    stamp = db.now().strftime("%Y-%m-%d %H:%M")
    with db._conn() as c:
        new_id = _next_id(c)
        c.execute("INSERT INTO kb_articles (id, title, symptoms, steps, team, category, source_ticket, resolution_note,"
                  " status, created_at, created_by, reviewed_by, reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (new_id, db.redact(a["title"]), db.redact(a["symptoms"]), json.dumps(a["steps"], ensure_ascii=False),
                   a.get("team"), a.get("category"), a.get("source_ticket"), db.redact(a.get("resolution_note", "")),
                   a["status"], stamp, a.get("created_by", "AI agent"), a.get("reviewed_by"),
                   stamp if a["status"] == STATUS_APPROVED else None))
    return new_id


def _row(r):
    a = dict(r)
    a["steps"] = json.loads(a["steps"] or "[]")
    return a


def list_articles(status=None):
    with db._conn() as c:
        q = "SELECT * FROM kb_articles" + (" WHERE status=?" if status else "") + " ORDER BY id DESC"
        return [_row(r) for r in c.execute(q, (status,) if status else ())]


def get(article_id):
    with db._conn() as c:
        r = c.execute("SELECT * FROM kb_articles WHERE id=?", (article_id,)).fetchone()
    return _row(r) if r else None


def draft_for_ticket(ticket_id):
    with db._conn() as c:
        r = c.execute("SELECT id FROM kb_articles WHERE source_ticket=? AND status!=?",
                      (ticket_id, STATUS_REJECTED)).fetchone()
    return r[0] if r else None


# ---------------------------------------------------------------- 2. the AI drafts the article
_PROMPT = """You write short IT knowledge base articles for employees, based on a resolved helpdesk ticket.
Write in English. Remove all names, email addresses, ticket numbers, device IDs and other personal data.
Only use what the ticket says. Do not invent steps. Steps must be safe for a normal employee to do
(no admin rights, no changing security settings). If the fix needs IT staff, say so in the last step.
Return JSON with keys: title (max 60 characters, describes the problem), symptoms (one sentence),
steps (list of 2 to 6 short steps; the last step says to reply 'not solved' to raise a ticket if it still fails).

Ticket title: {title}
Team: {team}
Category: {category}
Ticket history:
{history}
Resolution note from IT: {note}"""


def _ai_draft(t, note):
    import agent
    import tools
    history = "\n".join(f"- {h['text']}" for h in t["history"])[-3000:]
    resp = agent.generate(
        tools._client,
        contents=_PROMPT.format(title=t["title"], team=t["team"], category=t["category"], history=history, note=note),
        config={"response_mime_type": "application/json", "temperature": 0})
    agent._usage("kb-draft", resp)
    data = json.loads(resp.text)
    return {"title": str(data["title"])[:80], "symptoms": str(data["symptoms"]),
            "steps": [str(s) for s in data["steps"]][:8]}


def _simple_draft(t, note):
    """Used when the AI is not available: a plain template the admin then edits."""
    return {"title": t["title"][:80], "symptoms": f"Employees report: {t['title'].lower()}.",
            "steps": [s.strip().rstrip(".") + "." for s in re.split(r"[.;]\s+", note) if s.strip()][:5]
            + ["If it still does not work, reply 'not solved' to raise a ticket."]}


def create_draft(ticket_id, note, created_by="AI agent"):
    """Called when a ticket is resolved with a note. Returns the draft's ID (or the existing one)."""
    existing = draft_for_ticket(ticket_id)
    if existing:
        return existing
    t = db.get_ticket(ticket_id)
    if not t or not (note or "").strip():
        return None
    try:
        d = _ai_draft(t, note)
    except Exception:
        d = _simple_draft(t, note)
    new_id = _insert(dict(d, team=t["team"], category=t["category"], source_ticket=ticket_id,
                          resolution_note=note, status=STATUS_DRAFT, created_by=created_by))
    db.log_audit(created_by, "kb_draft_created", {"ticket_id": ticket_id}, {"article": new_id}, "done")
    return new_id


# ---------------------------------------------------------------- 3. review by an IT admin
def approve(article_id, reviewer, title, symptoms, steps):
    with db._conn() as c:
        c.execute("UPDATE kb_articles SET title=?, symptoms=?, steps=?, status=?, reviewed_by=?, reviewed_at=?, "
                  "vector=NULL WHERE id=?", (db.redact(title), db.redact(symptoms),
                                             json.dumps(steps, ensure_ascii=False), STATUS_APPROVED, reviewer,
                                             db.now().strftime("%Y-%m-%d %H:%M"), article_id))
    db.log_audit(reviewer, "kb_approved", {"article": article_id}, {"status": STATUS_APPROVED}, "user action")
    try:
        import sharepoint                      # SharePoint: the article becomes an item of the KB list
        a = get(article_id)
        sharepoint.on_kb(a)
    except Exception:
        pass


def reject(article_id, reviewer):
    with db._conn() as c:
        c.execute("UPDATE kb_articles SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
                  (STATUS_REJECTED, reviewer, db.now().strftime("%Y-%m-%d %H:%M"), article_id))
    db.log_audit(reviewer, "kb_rejected", {"article": article_id}, {"status": STATUS_REJECTED}, "user action")


# ---------------------------------------------------------------- 4. search (used by the agent's search tool)
def text_of(a):
    return (f"{a['title']}. Symptoms: {a['symptoms']} Fix steps: "
            + " ".join(f"{i}. {s}" for i, s in enumerate(a["steps"], 1)))


def approved_with_vectors(embed):
    """Approved articles + their embedding vectors (computed once, then stored)."""
    out = []
    for a in list_articles(STATUS_APPROVED):
        if not a["vector"]:
            vec = embed(text_of(a))
            with db._conn() as c:
                c.execute("UPDATE kb_articles SET vector=? WHERE id=?", (json.dumps(vec), a["id"]))
            a["vector"] = json.dumps(vec)
        v = np.array(json.loads(a["vector"]), dtype=np.float32)
        out.append((a, v / np.linalg.norm(v)))
    return out


def count(article_id, field):
    if field in ("suggested", "solved"):
        with db._conn() as c:
            c.execute(f"UPDATE kb_articles SET {field} = {field} + 1 WHERE id=?", (article_id,))


# ---------------------------------------------------------------- knowledge gaps: what the agent could NOT answer
def log_gap(user, question, source):
    with db._conn() as c:
        c.execute("INSERT INTO kb_gaps (at, user, question, source) VALUES (?,?,?,?)",
                  (db.now().strftime("%Y-%m-%d %H:%M"), user, db.redact(question)[:500], source))


def open_gaps():
    with db._conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM kb_gaps WHERE status='open' ORDER BY id DESC")]


_GROUP_PROMPT = """These are questions employees asked an IT helpdesk agent that it could NOT answer from its documents.
Group them into topics. Return JSON: a list of objects with keys
"topic" (2-5 words), "ids" (list of the question ids in this group), "suggested_title" (a knowledge base
article title that would answer them, max 60 characters). Biggest groups first. Every id in exactly one group.

Questions (id: text):
{rows}"""


def group_gaps():
    """The AI groups the open questions into topics. Saved, so the page shows the last grouping."""
    gaps = open_gaps()
    if not gaps:
        db.set_setting("kb_gap_groups", "[]")
        return []
    try:
        import agent
        import tools
        resp = agent.generate(
            tools._client, contents=_GROUP_PROMPT.format(
                rows="\n".join(f"{g['id']}: {g['question']}" for g in gaps)),
            config={"response_mime_type": "application/json", "temperature": 0})
        agent._usage("kb-gaps", resp)
        groups = [{"topic": str(x["topic"]), "ids": [int(i) for i in x["ids"]],
                   "suggested_title": str(x["suggested_title"])[:80]} for x in json.loads(resp.text)]
    except Exception:                              # no AI: one group per question
        groups = [{"topic": g["question"][:40], "ids": [g["id"]], "suggested_title": g["question"][:80]}
                  for g in gaps]
    known = {g["id"] for g in gaps}
    groups = [dict(x, ids=[i for i in x["ids"] if i in known]) for x in groups]
    groups = sorted([x for x in groups if x["ids"]], key=lambda x: -len(x["ids"]))
    db.set_setting("kb_gap_groups", json.dumps(groups, ensure_ascii=False))
    return groups


def saved_groups():
    gaps = {g["id"]: g for g in open_gaps()}
    groups = json.loads(db.get_setting("kb_gap_groups", "[]") or "[]")
    out = []
    for x in groups:
        items = [gaps[i] for i in x["ids"] if i in gaps]
        if items:
            out.append(dict(x, questions=items))
    return out


def start_article_from_gap(group, by):
    """IT starts an article for a gap topic. The AI does not invent the fix: IT writes the steps."""
    examples = "; ".join(q["question"] for q in group["questions"][:3])
    new_id = _insert({"title": group["suggested_title"], "symptoms": f"Employees ask: {examples}",
                      "steps": ["(IT: write the steps here before approving)"], "team": None,
                      "category": "Knowledge gap", "source_ticket": f"{len(group['questions'])} questions",
                      "resolution_note": "Created from knowledge gaps", "status": STATUS_DRAFT, "created_by": by})
    with db._conn() as c:
        c.executemany("UPDATE kb_gaps SET status='article started' WHERE id=?",
                      [(q["id"],) for q in group["questions"]])
    db.log_audit(by, "kb_gap_article", {"topic": group["topic"]}, {"article": new_id}, "user action")
    return new_id
