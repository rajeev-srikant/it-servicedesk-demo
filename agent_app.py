import os
import json
import html
import io
import uuid
import datetime
from PIL import Image
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
import tools
import agent
import db
import sla
import analytics as an
import dashboard

load_dotenv()

BRAND = "TestBank"
MINUTES_PER_TICKET = 15            # assumption for "IT time saved": average handling time of a simple ticket
st.set_page_config(page_title=f"{BRAND} IT Service Desk", page_icon=":material/support_agent:", layout="wide",
                   initial_sidebar_state="expanded")


# ======================================================================
# 0. LOOK AND FEEL (only changes how the screen looks, not what the agent does)
# ======================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700&display=swap');
:root { --ink:#1A2230; --ink2:#5A6575; --ink3:#8A94A3; --line:#DADFE6; --line2:#EBEEF2; --bg:#F4F5F7;
  --navy:#0F3D6E; --navy-d:#0A2C52; --navy-l:#E8EEF5; --ok:#1E7B34; --warn:#A65F00; --bad:#B42318; --purple:#5B3FA0; }
html, body, [class*="css"], .stMarkdown, button, input, textarea, select {
  font-family: 'IBM Plex Sans', 'Noto Sans JP', 'Meiryo', sans-serif; }
.stApp { background: var(--bg); }
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stExpandSidebarButton"] { visibility: visible !important; }   /* keep the "open sidebar" button */
[data-testid="stDecoration"] { display: none; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; }
button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] { border-radius: 4px !important; }
[data-testid="stBaseButton-primary"] { background: var(--navy) !important; border-color: var(--navy) !important; }
[data-testid="stBaseButton-primary"]:hover { background: var(--navy-d) !important; }
[data-testid="stExpander"] details { border-radius: 4px; border-color: var(--line); }

/* Top bar: flat, white, thin line */
.tb-header { display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap;
  background:#fff; border:1px solid var(--line); border-top:3px solid var(--navy); border-radius:4px;
  padding:10px 18px; margin-bottom:14px; }
.tb-brand { display:flex; align-items:center; gap:12px; }
.tb-logo { width:30px; height:30px; border-radius:3px; background:var(--navy); color:#fff; font-weight:700;
  display:flex; align-items:center; justify-content:center; font-size:12px; letter-spacing:.3px; }
.tb-title { font-size:16px; font-weight:600; color:var(--ink); line-height:1.2; }
.tb-title span { font-weight:400; color:var(--ink2); padding-left:10px; margin-left:8px; border-left:1px solid var(--line); }
.tb-right { display:flex; align-items:center; gap:18px; }
.tb-env { font-size:12px; color:var(--warn); background:#FFF6E5; border:1px solid #F0D9A8; padding:2px 8px; border-radius:3px; }
.tb-user { display:flex; align-items:center; gap:10px; }
.tb-avatar { width:30px; height:30px; border-radius:50%; background:var(--navy-l); color:var(--navy); font-weight:600;
  display:flex; align-items:center; justify-content:center; font-size:12px; flex-shrink:0; }
.tb-uname { font-size:13.5px; font-weight:600; color:var(--ink); }
.tb-urole { font-size:12px; color:var(--ink2); }

.card { background:#fff; border:1px solid var(--line); border-radius:4px; padding:16px 18px; margin-bottom:12px; }
.section-title { font-size:12px; font-weight:600; color:var(--ink2); text-transform:uppercase; letter-spacing:.6px; margin:6px 0 8px 0; }
.welcome h3 { margin:0 0 6px 0; font-size:19px; font-weight:600; color:var(--ink); }
.welcome p { margin:0; color:var(--ink2); font-size:14px; line-height:1.6; }
.caps { display:flex; gap:18px; flex-wrap:wrap; margin-top:12px; padding-top:10px; border-top:1px solid var(--line2); }
.cap { font-size:12.5px; color:var(--ink2); }
.cap::before { content:""; display:inline-block; width:6px; height:6px; background:var(--navy); margin-right:7px; vertical-align:middle; }

.st-key-chips button { border-radius:4px !important; border:1px solid var(--line) !important; background:#fff !important;
  color:var(--ink) !important; font-size:13.5px !important; justify-content:flex-start !important; text-align:left; }
.st-key-chips button:hover { border-color:var(--navy) !important; color:var(--navy) !important; }

[data-testid="stChatMessage"] { background:#fff; border:1px solid var(--line); border-radius:4px; padding:12px 16px; }
[class*="st-key-msg_user"] [data-testid="stChatMessage"] { background:var(--navy-l); border-color:#D2DDEA; margin-left:48px; width:calc(100% - 48px); }
[class*="st-key-msg_assistant"] [data-testid="stChatMessage"] { width:calc(100% - 24px); }
.srcs { display:flex; gap:6px; flex-wrap:wrap; margin:6px 0 2px 0; }
.src { font-size:12px; background:#F6F7F9; border:1px solid var(--line); color:var(--ink2); padding:2px 8px; border-radius:3px; }
.src::before { content:"Source: "; color:var(--ink3); }
.steps { font-size:13px; color:var(--ink2); line-height:1.9; }

.st-key-approval { background:#FFFCF5; border:1px solid #E9D3A0; border-left:3px solid var(--warn); border-radius:4px; padding:14px 16px; }
.ap-head { font-weight:600; color:var(--ink); font-size:15px; margin-bottom:2px; }
.ap-sub { color:var(--ink2); font-size:13px; margin-bottom:6px; }

[class*="st-key-tk"] { background:#fff; border:1px solid var(--line); border-left:3px solid var(--navy); border-radius:4px;
  padding:10px 14px 4px 14px; margin-bottom:4px; }
.tk-top { display:flex; justify-content:space-between; align-items:center; margin-bottom:2px; gap:8px; }
.tk-id { font-weight:600; color:var(--navy); font-size:13px; }
.tk-title { font-weight:500; color:var(--ink); font-size:14.5px; margin-bottom:3px; }
.tk-meta { color:var(--ink2); font-size:12.5px; }
.hist { font-size:12.5px; color:var(--ink2); border-left:2px solid var(--line); padding:2px 0 2px 10px; margin:6px 0; }
.hist b { color:var(--ink); font-weight:600; }
.badge { font-size:11.5px; font-weight:500; padding:1px 7px; border-radius:3px; white-space:nowrap; border:1px solid transparent; }
.s-new { background:#EEF3FA; color:#1F4E8C; border-color:#CBD9EC; }
.s-progress { background:#FFF6E5; color:var(--warn); border-color:#F0D9A8; }
.s-waiting { background:#F3F0FA; color:var(--purple); border-color:#DCD3F0; }
.s-agent { background:#FDEEEE; color:var(--bad); border-color:#F2CACA; }
.s-resolved { background:#EDF7EF; color:var(--ok); border-color:#C9E6CF; }
.s-closed { background:#F2F3F5; color:var(--ink2); border-color:var(--line); }
.p-urgent { color:var(--bad); font-weight:600; }
.p-high { color:#B54708; font-weight:600; }
.sla { display:inline-block; font-size:12px; font-weight:500; margin-top:6px; padding:1px 7px; border-radius:3px; }
.sla-ok { background:#F2F4F7; color:var(--ink2); }
.sla-soon { background:#FFF6E5; color:var(--warn); }
.sla-overdue { background:#FDEEEE; color:var(--bad); }
.sla-responded, .sla-closed { background:#EDF7EF; color:var(--ok); }
.sla-paused { background:#F3F0FA; color:var(--purple); }
.wait { font-size:12.5px; color:var(--purple); background:#F7F5FC; border-left:2px solid var(--purple); padding:4px 8px; margin-top:6px; }
.wait b { color:var(--purple); }
.sla-t { font-size:12px; color:var(--ink3); margin-top:4px; }
.sh-q { font-weight:600; color:var(--ink); font-size:14px; margin:8px 0 2px 0; }
.sh-done { display:inline-block; font-size:12.5px; font-weight:500; color:var(--ok); background:#EDF7EF;
  padding:2px 9px; border-radius:3px; margin:6px 0; }
.hw-flow { display:flex; align-items:stretch; gap:8px; flex-wrap:wrap; margin:4px 0 6px 0; }
.hw-box { flex:1; min-width:120px; background:#F6F7F9; border:1px solid var(--line); border-radius:4px; padding:12px;
  display:flex; flex-direction:column; gap:4px; text-align:center; }
.hw-box b { color:var(--ink); font-size:14.5px; }
.hw-box span { color:var(--ink2); font-size:12px; }
.hw-ai { background:var(--navy-l); border-color:#C9D7E8; }
.hw-tools { background:#EDF7EF; border-color:#C9E6CF; }
.hw-arrow { display:flex; align-items:center; color:var(--ink3); font-size:20px; }
.hw-loop { font-size:12.5px; color:var(--ink2); background:#FFFCF5; border:1px solid #E9D3A0; border-radius:4px;
  padding:6px 10px; margin-bottom:8px; }
.hw-intro { font-size:13px; color:var(--ink2); line-height:1.9; margin-bottom:6px; }
.hw-group { font-weight:600; color:var(--ink); font-size:14.5px; margin:14px 0 6px 0; }
.hw-rule { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:8px 12px;
  border:1px solid var(--line); border-radius:4px; margin-bottom:6px; background:#fff; }
.hw-rule b { color:var(--ink); font-size:14px; font-weight:600; }
.hw-rule span { color:var(--ink2); font-size:12.5px; }
.hw-badge { font-size:11px !important; font-weight:500; padding:2px 7px; border-radius:3px; white-space:nowrap; }
.hw-code { background:#EDF7EF; color:var(--ok) !important; }
.hw-test { background:var(--navy-l); color:var(--navy) !important; }
.hw-note { font-size:12.5px; color:var(--ink2); background:#FFFCF5; border:1px solid #E9D3A0; border-radius:4px;
  padding:8px 12px; margin-top:12px; line-height:1.6; }
.tr { font-size:13px; padding:6px 10px; border-radius:4px; margin:4px 0; line-height:1.5; }
.tr span { display:block; font-size:11px; color:var(--ink3); }
.tr-u { background:var(--navy-l); margin-left:30px; }
.tr-a { background:#F6F7F9; border:1px solid var(--line); margin-right:30px; }
.mail { background:#fff; border:1px solid var(--line); border-radius:4px; overflow:hidden; font-size:13.5px; }
.mail-h { background:#F6F7F9; border-bottom:1px solid var(--line); padding:10px 14px; color:var(--ink2); line-height:1.7; font-size:12.5px; }
.mail-h b { color:var(--ink); }
.mail-b { padding:14px 16px; color:var(--ink); line-height:1.6; }
.mail-b table { border-collapse:collapse; margin:10px 0; width:100%; }
.mail-b td { padding:5px 8px; border-bottom:1px solid var(--line2); font-size:13px; vertical-align:top; }
.mail-b td:first-child { color:var(--ink2); width:140px; }
.mail-f { font-size:11.5px; color:var(--ink3); padding:0 16px 12px 16px; }
.mail-tag { font-size:11px; font-weight:600; color:var(--warn); background:#FFF6E5; padding:1px 7px; border-radius:3px; }

/* Number strips: one white panel split by thin lines (no floating cards) */
.kpis { display:grid; grid-template-columns: repeat(2, 1fr); gap:0; margin-bottom:14px; background:#fff;
  border:1px solid var(--line); border-radius:4px; }
.kpis.wide { grid-template-columns: repeat(4, 1fr); }
.kpi { padding:12px 16px; border-right:1px solid var(--line2); border-bottom:1px solid var(--line2); }
.kpi-v { font-size:22px; font-weight:600; color:var(--ink); }
.kpi-l { font-size:12px; color:var(--ink2); }
.note { font-size:12px; color:var(--ink2); margin-top:-4px; margin-bottom:10px; }

[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
.prof { display:flex; gap:12px; align-items:center; padding:4px 0 12px 0; border-bottom:1px solid var(--line2); }
.prof .tb-avatar { width:38px; height:38px; }
.prof-n { font-weight:600; color:var(--ink); }
.prof-d { font-size:12px; color:var(--ink2); line-height:1.4; }
.side-foot { font-size:11.5px; color:var(--ink3); margin-top:18px; line-height:1.5; }
.foot { text-align:center; color:var(--ink3); font-size:12px; margin-top:26px; }

.login { max-width:440px; margin:60px auto 10px auto; text-align:center; }
.login .tb-logo { margin:0 auto 14px auto; width:44px; height:44px; font-size:16px; }
.login h2 { margin:0; color:var(--ink); font-weight:600; }
.login p { color:var(--ink2); font-size:14px; }

button[data-variant="segmented_control"][aria-checked="true"] { background:var(--navy-l) !important;
  color:var(--navy) !important; border-color:var(--navy) !important; }
/* Live chat with a person */
.live-sys { text-align:center; font-size:12.5px; color:var(--ink2); margin:8px 0; }
.live-sys::before, .live-sys::after { content:"—"; color:var(--ink3); margin:0 8px; }
.live-who { font-size:12px; font-weight:600; color:var(--ok); margin-bottom:2px; }
[class*="st-key-live_agent_"] [data-testid="stChatMessage"] { border-left:3px solid var(--ok); background:#F6FBF7;
  width:calc(100% - 24px); }
.live-bar { font-size:12.5px; color:var(--ink2); background:#fff; border:1px solid var(--line); border-radius:4px;
  padding:7px 12px; margin:8px 0; }
.live-wait { color:var(--warn); background:#FFFCF5; border-color:#E9D3A0; }
.live-on { color:var(--ok); background:#F6FBF7; border-color:#C9E6CF; }
.live-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:currentColor; margin-right:8px;
  animation: livepulse 1.4s ease-in-out infinite; }
@keyframes livepulse { 50% { opacity:.25; } }
.live-alert { font-size:13.5px; color:var(--bad); background:#FDF3F2; border:1px solid #F2CACA;
  border-left:3px solid var(--bad); border-radius:4px; padding:9px 14px; }
[class*="st-key-lq_"]:not([class*="st-key-lq_btn"]) { background:#fff; border:1px solid var(--line);
  border-left:3px solid var(--bad); border-radius:4px; padding:10px 14px 10px 14px; margin-bottom:4px; }
/* Admin menu: plain text tabs with a navy underline */
.st-key-adminnav { margin:-6px 0 16px 0; border-bottom:1px solid var(--line); }
.st-key-adminnav [data-testid="stButtonGroup"] > div { gap:4px !important; }
.st-key-adminnav button { background:transparent !important; border:none !important; border-radius:0 !important;
  border-bottom:2px solid transparent !important; color:var(--ink2) !important; font-size:14px !important;
  padding:8px 14px !important; box-shadow:none !important; margin-bottom:-1px; }
.st-key-adminnav button:hover { color:var(--ink) !important; }
.st-key-adminnav button[aria-checked="true"] { background:transparent !important; color:var(--navy) !important; font-weight:600 !important;
  border-bottom-color:var(--navy) !important; }
.st-key-adminnav button[aria-checked="true"] span { font-weight:600; }
</style>
"""
st.markdown(CSS.replace("</style>", dashboard.DASH_CSS + "</style>"), unsafe_allow_html=True)

e = html.escape            # makes any text safe to put inside our HTML


def initials(name):
    words = name.split("(")[0].split()
    return "".join(w[0] for w in words[:2]).upper() or "?"


def short_name(name):
    return name.split("(")[0].strip()


def login_card(text):
    st.markdown(f'<div class="login"><div class="tb-logo">TB</div><h2>{BRAND} IT Service Desk</h2>'
                f'<p>{text}</p></div>', unsafe_allow_html=True)


@st.cache_resource
def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


@st.cache_resource
def setup_database():
    db.init()                                         # creates helpdesk.db the first time
    return True


client = get_client()
setup_database()


# ======================================================================
# 1. SIGN-IN
#    Google sign-in is used when it is set up in secrets ([auth] section).
#    Otherwise the app runs in demo mode: optional access code + "switch user" list.
# ======================================================================
def google_sign_in_enabled():
    try:
        return hasattr(st, "login") and "auth" in st.secrets
    except Exception:
        return False


GOOGLE = google_sign_in_enabled()
ADMIN_EMAILS = {a.strip().lower() for a in os.getenv("ADMIN_EMAILS", "").split(",") if a.strip()}


def new_conversation():
    """Back to the home screen: clears the chat only. Tickets and the audit log stay."""
    tid = st.session_state.get("live_tid")
    if tid and (db.get_live_chat(tid) or {}).get("status") != "ended":      # leaving ends the live chat
        who = tools.EMPLOYEES.get(st.session_state.get("user"), {}).get("name", "the employee")
        db.end_live_chat(tid, who.split("(")[0].strip() + " (left the chat)")
    st.session_state.live_tid = None                  # a live chat with a person, if one is open
    st.session_state.live_seen = None
    st.session_state.contents = []                    # the conversation as the AI sees it
    st.session_state.display = []                     # the conversation as the user sees it
    st.session_state.pending = None                   # an action waiting for confirmation (dropped)
    st.session_state.handed_off = False               # "Talk to a person" used in this conversation?
    st.session_state.conv_id = uuid.uuid4().hex       # id for the (optional) conversation history
    st.session_state.conv_started = db.now().strftime("%Y-%m-%d %H:%M:%S")


if GOOGLE:
    if not st.user.is_logged_in:
        login_card("Sign in with your Google account to continue.")
        _, mid, _ = st.columns([1, 1, 1])
        mid.button("Sign in with Google", type="primary", width="stretch", on_click=st.login)
        st.stop()
    email = st.user.email.lower()
    tools.register_user(email, st.user.get("name"), admin=email in ADMIN_EMAILS)
    if st.session_state.get("user") != email:
        st.session_state.user = email
        new_conversation()
else:
    APP_PASSWORD = os.getenv("APP_PASSWORD")
    if APP_PASSWORD and not st.session_state.get("signed_in"):
        login_card("Sign in to the demo environment with the access code you were given.")
        _, mid, _ = st.columns([1, 1.2, 1])
        with mid:
            entered = st.text_input("Access code", type="password")
            if entered:
                if entered == APP_PASSWORD:
                    st.session_state.signed_in = True
                    st.rerun()
                st.error("That access code is not correct.")
        st.stop()
    if "user" not in st.session_state:
        st.session_state.user = "rajeev@testbank.com"
        new_conversation()

USER = st.session_state.user
me = tools.EMPLOYEES[USER]
is_admin = tools.is_admin(USER)
role_label = "IT Admin" if is_admin else "Employee"
names = {p["email"]: p["name"] for p in tools.EMPLOYEES.values()}
st.session_state.setdefault("feedback_saved", {})

# Conversation history (optional): the IT admin can switch it on/off and choose how long chats are kept
HISTORY_ON = db.get_setting("history_on", "1") == "1"
RETENTION_DAYS = int(db.get_setting("retention_days", "90"))
db.delete_old_conversations(RETENTION_DAYS)             # automatic deletion after the retention period


# ======================================================================
# 2. RUNNING THE AGENT (the brain is in agent.py)
# ======================================================================
def last_question():
    return next((m["text"] for m in reversed(st.session_state.display) if m["role"] == "user"), "")


def process(step_fn):
    """Runs the agent while showing each step live, then stores the answer or the pending action."""
    with st.status("Working on it…", expanded=True) as status:
        try:
            out = step_fn(lambda label: status.write(label))
            status.update(label="Done", state="complete", expanded=False)
        except Exception as ex:
            status.update(label="Something went wrong", state="error")
            msg = str(ex)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                msg = "The AI service is busy or the usage limit was reached. Please try again in a minute."
            out = {"type": "answer", "text": f"Sorry, something went wrong: {msg}",
                   "trace": {"steps": [], "sources": []}}
    if out["type"] == "pending":
        st.session_state.pending = out
    else:
        sources = cited_sources(out["text"], out["trace"]["sources"])
        emails = out["trace"].get("emails", [])
        searched_self_help = any(x.startswith("Self_Help_Guide") for x in out["trace"]["sources"])
        is_self_help = not emails and (any(x.startswith("Self_Help_Guide") for x in sources) or
                                       (searched_self_help and ("solve" in out["text"].lower() or "解決" in out["text"])))
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "text": out["text"],
                                         "steps": out["trace"]["steps"], "sources": sources, "emails": emails,
                                         "self_help": "ask" if is_self_help else None,
                                         "question": last_question()})


def cited_sources(answer, sources):
    """Only show the policy files the answer actually mentions (not every passage that was searched)."""
    text = answer.lower().replace("_", " ")
    return [s for s in sources if s.split(" · ")[0].lower().replace(".pdf", "").replace("_", " ") in text]


def shrink_image(uploaded):
    """Makes a screenshot smaller (max 1600 px) so it is quick and cheap to send to the AI."""
    img = Image.open(uploaded)
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def ask(prompt, image=None):
    prompt = prompt or "Here is a screenshot of my problem."
    st.session_state.display.append({"id": uuid.uuid4().hex, "role": "user", "text": prompt, "image": image})
    parts = [types.Part.from_text(text=prompt)]
    if image:                                         # the AI can "see" the screenshot
        parts.append(types.Part.from_bytes(data=image, mime_type="image/png"))
    st.session_state.contents.append(types.Content(role="user", parts=parts))
    process(lambda on_step: agent.run(client, st.session_state.contents, USER, on_step))


def self_help_answer(m, solved):
    """The user clicked "Yes, solved" or "No, raise a ticket" under a self-help answer."""
    m["self_help"] = "solved" if solved else "ticket"
    outcome = "solved" if solved else "needed a ticket"
    db.log_self_help(USER, m.get("question", ""), outcome)
    db.log_audit(USER, "self_help_result", {"question": m.get("question", "")}, {"outcome": outcome}, "user action")
    if solved:
        text = "Great, I'm glad that's sorted! No ticket needed. If anything else comes up, just ask."
        for role, t in (("user", "Yes, that solved it."), ("model", text)):
            st.session_state.contents.append(types.Content(role=role, parts=[types.Part.from_text(text=t)]))
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "user", "text": "Yes, that solved it."})
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "text": text, "steps": [],
                                         "sources": [], "emails": [], "question": m.get("question", "")})
    else:
        ask("That didn't solve my problem. Please raise a ticket for me.")


def decide(confirmed, final_args=None):
    p = st.session_state.pending
    st.session_state.pending = None
    process(lambda on_step: agent.resume(client, st.session_state.contents, p, confirmed, final_args, USER, on_step))


def talk_to_person():
    """Hands the conversation to a human: a ticket with the chat transcript. No AI involved."""
    st.session_state.pending = None
    transcript = " | ".join(f"{'User' if m['role'] == 'user' else 'Agent'}: {m['text']}"
                            for m in st.session_state.display)[-1500:]
    first = next((m["text"] for m in st.session_state.display if m["role"] == "user"), "Chat")
    tid = db.create_ticket(USER, f"Live chat handoff: {first[:60]}", "Chat handoff", "High", "Service Desk",
                           "Waiting for agent", f"User asked to talk to a person. Chat transcript: {transcript}")
    st.session_state.handed_off = True
    db.start_live_chat(tid, USER)                     # opens a live chat that an IT agent can join
    for m in st.session_state.display:                # the agent can read the chat with the virtual agent
        db.add_live_message(tid, "before_" + ("user" if m["role"] == "user" else "ai"), "", m["text"])
    st.session_state.live_tid = tid
    db.log_audit(USER, "talk_to_person", {"button": "Talk to a person"}, {"created": tid}, "user action")
    text = (f"I've passed our conversation to the Service Desk as ticket **{tid}**. Please stay on this page: "
            "a member of the IT team will join this chat shortly. They can see our conversation, so you won't "
            "need to repeat anything. If you leave, they will follow up through the ticket.")
    st.session_state.contents.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
    st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "text": text,
                                     "steps": [f"Handed over to the Service Desk ({tid})"], "sources": [],
                                     "emails": [{"kind": "handoff", "ticket_id": tid}],
                                     "question": "Talk to a person"})


# ======================================================================
# 3. THE SCREEN
# ======================================================================
STATUS_CLASS = {"New": "s-new", "In progress": "s-progress", "Waiting for approval": "s-waiting",
                "Waiting for agent": "s-agent", "Resolved": "s-resolved", "Closed": "s-closed"}


def waiting_text(t):
    if t["status"] == "Waiting for approval":
        return t.get("waiting_for") or "An approval (see the history for details)"
    if t["status"] == "Waiting for agent":
        return "A Service Desk agent to contact you"
    return None


def my_ticket_action(kind, t, text):
    """The employee updates or closes their own ticket with the buttons on the card (no AI involved)."""
    if t["requester_email"] != USER or t["status"] in ("Resolved", "Closed"):
        st.toast("You can only change your own open tickets.")
        return
    if kind == "update":
        db.add_history(t["ticket_id"], f"Update from the user: {text}")
        tools.resume_if_waiting(t)
        db.log_audit(USER, "add_update (button)", {"ticket_id": t["ticket_id"], "update": text},
                     {"updated": t["ticket_id"]}, "user action")
        st.toast(f"Update added to {t['ticket_id']}.")
    else:
        db.update_ticket(t["ticket_id"], status="Closed")
        db.clear_waiting(t["ticket_id"])
        db.add_history(t["ticket_id"], f"Closed by the user. Reason: {text or 'not given'}")
        db.log_audit(USER, "close_ticket (button)", {"ticket_id": t["ticket_id"], "reason": text},
                     {"closed": t["ticket_id"]}, "user action")
        st.toast(f"{t['ticket_id']} has been closed.")
    st.rerun()


def ticket_card(t, show_requester=False, key_prefix="tk", actions=False):
    """One ticket as a card, with its full history in a fold-out section."""
    with st.container(key=f"{key_prefix}_{t['ticket_id']}"):
        r, res = sla.status(t), sla.resolution(t)
        pr = t["priority"]
        pr_html = f'<span class="p-{pr.lower()}">{e(pr)}</span>' if pr in ("High", "Urgent") else e(pr)
        who = f'{e(short_name(names.get(t["requester_email"], t["requester_email"])))} · ' if show_requester else ""
        st.markdown(f'<div class="tk-top"><span class="tk-id">{e(t["ticket_id"])}</span>'
                    f'<span class="badge {STATUS_CLASS.get(t["status"], "s-new")}">{e(t["status"])}</span></div>'
                    f'<div class="tk-title">{e(t["title"])}</div>'
                    f'<div class="tk-meta">{who}{e(t["team"])} · {pr_html} priority · Opened {e(t["created"])}</div>'
                    f'<div><span class="sla sla-{r["state"]}">{e(r["label"])}</span> '
                    + (f'<span class="sla sla-{res["state"]}">{e(res["label"])}</span>' if res["label"] else "")
                    + f'</div><div class="sla-t">{e(sla.targets_text(t))}</div>'
                    + (f'<div class="wait"><b>Waiting for:</b> {e(waiting_text(t))}</div>' if waiting_text(t) else ""),
                    unsafe_allow_html=True)
        if actions and t["status"] not in ("Resolved", "Closed"):
            b1, b2 = st.columns(2)
            with b1.popover("Add update", icon=":material/edit_note:"):
                with st.form(f"upd_{key_prefix}_{t['ticket_id']}", border=False, clear_on_submit=True):
                    upd = st.text_area("Your update", placeholder="e.g. My manager approved this by email today.",
                                       height=80)
                    if st.form_submit_button("Add update", type="primary") and upd.strip():
                        my_ticket_action("update", t, upd.strip())
            with b2.popover("Close ticket", icon=":material/task_alt:"):
                with st.form(f"cls_{key_prefix}_{t['ticket_id']}", border=False):
                    reason = st.text_input("Reason (optional)", placeholder="e.g. It works again")
                    st.caption("Close this ticket if you no longer need help.")
                    if st.form_submit_button("Close ticket", type="primary"):
                        my_ticket_action("close", t, reason.strip())
        n = len(t["history"])
        with st.expander(f"History ({n} update{'s' if n != 1 else ''})"):
            st.markdown("".join(f'<div class="hist"><b>{e(h["at"])}</b> · {e(h["text"])}</div>'
                                for h in reversed(t["history"])), unsafe_allow_html=True)


def email_preview(kind, ticket_id):
    """Shows the email the employee WOULD receive. Nothing is sent in this demo."""
    t = db.get_ticket(ticket_id)
    if not t:
        return
    person = tools.EMPLOYEES.get(t["requester_email"], {"name": t["requester_email"]})
    first = short_name(person["name"]).split()[0]
    r, res = sla.status(t), sla.resolution(t)
    tid, title = t["ticket_id"], t["title"]
    subject, intro = {
        "created": (f"[{tid}] We've received your request: {title}",
                    "Thank you for contacting the IT Service Desk. We have received your request and it has been "
                    "assigned to the team below."),
        "updated": (f"[{tid}] Your update has been added",
                    "We've added your update to the ticket below. The assigned team has been notified."),
        "admin_update": (f"[{tid}] Your ticket has been updated",
                         "The IT team has updated your ticket. Here are the latest details."),
        "closed": (f"[{tid}] Your ticket has been closed",
                   "As you requested, we have closed your ticket. If the problem comes back, just ask the virtual "
                   "agent and we'll help again."),
        "handoff": (f"[{tid}] A member of the IT team will contact you",
                    "You asked to talk to a person. Your conversation has been passed to the Service Desk, "
                    "and someone will contact you soon. You won't need to repeat anything."),
    }[kind]
    last = t["history"][-1]["text"] if t["history"] else ""
    rows = [("Ticket", tid), ("Title", title), ("Status", t["status"]), ("Priority", t["priority"]),
            ("Assigned to", t["team"]), ("First response by", f'{r["due"]} (JST)'),
            ("Resolve by", "Paused while waiting for approval" if res["state"] == "paused"
             else f'{res["due"]} (JST)' if res["due"] else "—"),
            ("Service targets", sla.targets_text(t))]
    if kind in ("updated", "admin_update", "closed"):
        rows.append(("Latest update", last[:200]))
    table = "".join(f"<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>" for k, v in rows)
    with st.expander(f"Email preview · to {t['requester_email']}"):
        st.markdown(f'<div class="mail"><div class="mail-h"><span class="mail-tag">PREVIEW ONLY · NOT SENT</span><br>'
                    f'<b>From:</b> TestBank IT Service Desk &lt;it-servicedesk@testbank.com&gt;<br>'
                    f'<b>To:</b> {e(person["name"])} &lt;{e(t["requester_email"])}&gt;<br>'
                    f'<b>Subject:</b> {e(subject)}</div>'
                    f'<div class="mail-b">Dear {e(first)},<br><br>{e(intro)}<table>{table}</table>'
                    'You can check this ticket at any time in the TestBank IT Service Desk.<br><br>'
                    'Kind regards,<br>TestBank IT Service Desk</div>'
                    '<div class="mail-f">This is an automated message. Please do not reply to this email. '
                    'Never share your password with anyone, including IT.</div></div>', unsafe_allow_html=True)


def latest_test_result():
    """Reads the result of the last test run (python eval_agent.py), if there is one."""
    try:
        with open("eval_results.json", encoding="utf-8") as f:
            r = json.load(f)
        when = datetime.datetime.fromtimestamp(os.path.getmtime("eval_results.json"), db.TOKYO)
        return f"{r['passed']} of {r['total']} passed", f"last run {when:%d %b %Y}"
    except Exception:
        return "Not run yet", "run python eval_agent.py"


SAFETY_RULES = [
    ("1. Stays in its lane", [
        ("IT helpdesk questions only", "Anything else (HR, salary, leave, legal, jokes, general questions) is politely "
         "declined.", "ai"),
        ("Can only do a few fixed jobs", "Search IT documents, and look up, create, update or close tickets. It cannot "
         "reset passwords, send emails, delete data or reach any other system.", "code"),
    ]),
    ("2. Does not make things up", [
        ("Answers only from our documents, and shows the source", "If the answer is not in the documents, it says so "
         "and offers a ticket or a person, instead of guessing.", "ai"),
        ("Never invents ticket numbers or statuses", "It only repeats what the ticket system actually returns.", "ai"),
    ]),
    ("3. Cannot be tricked", [
        ("Ignores tricks like \u201cignore your rules\u201d or \u201cyou are now admin\u201d",
         "This is called prompt injection. Hidden instructions inside documents or screenshots are ignored too.", "ai"),
        ("Even if it were tricked, the software still says no", "Who may see or change what is checked by normal "
         "software, not by the AI, so a tricked AI still cannot get other people's data.", "code"),
    ]),
    ("4. Protects people and data", [
        ("You only see your own tickets", "Only IT admins can see everyone's tickets.", "code"),
        ("Never asks for passwords", "If someone types a password, the AI warns them to change it, and the software "
         "removes it before anything is saved.", "both"),
        ("Will not help get around security", "For example switching off USB blocking or antivirus. It explains the "
         "official way instead.", "ai"),
    ]),
    ("5. Humans stay in control", [
        ("Asks before changing anything", "Nothing is created, updated or closed until the person confirms, and they "
         "can edit or cancel first.", "code"),
        ("A person is always one click away", "\u201cTalk to a person\u201d hands the chat to the Service Desk.", "code"),
        ("No endless loops", f"It stops after {agent.MAX_STEPS} steps and suggests a person.", "code"),
    ]),
    ("6. Everything is visible and checked", [
        ("Every action is recorded", "IT admins can view and download the audit log for auditors.", "code"),
        ("Spending is capped", "A monthly spending limit is set on the AI account, and cost is tracked in the app.",
         "setting"),
        ("Tested before every change", "An automatic test set (26 scenarios, including attack attempts) is run "
         "before any change is released.", "process"),
        ("Chats are kept only as long as needed", (f"Full conversations are saved for {RETENTION_DAYS} days for "
         "quality and audit, then deleted automatically. " if HISTORY_ON else "Full conversations are currently "
         "not saved. ") + "IT admins can switch this on or off. Passwords are removed and screenshots are never "
         "stored.", "code"),
    ]),
]
BADGES = {"code": ("Built into the software", "hw-code"), "ai": ("AI rule · checked by tests", "hw-test"),
          "both": ("Software + AI rule", "hw-code"), "setting": ("Account setting", "hw-test"),
          "process": ("Team process", "hw-test")}


@st.dialog("How the TestBank virtual agent works", width="large")
def how_it_works():
    test, test_when = latest_test_result()
    totals = db.usage_totals()
    calls = totals.get("chat", {}).get("calls", 0)
    per_call = f"≈ ₹{agent.estimated_cost_usd(totals) / calls * agent.USD_TO_INR:.2f}" if calls else "≈ ₹0.2"
    overview, safety, limits = st.tabs(["How it works", "Safety rules", "Limits of this demo"])

    with overview:
        box = lambda title, sub, cls="": f'<div class="hw-box {cls}"><b>{title}</b><span>{sub}</span></div>'
        st.markdown(
            '<div class="hw-flow">'
            + box("Employee", "asks in English or 日本語")
            + '<div class="hw-arrow">→</div>'
            + box("AI agent", "Gemini · understands &amp; decides", "hw-ai")
            + '<div class="hw-arrow">→</div>'
            + box("Tools", "our software · does the work", "hw-tools")
            + '<div class="hw-arrow">→</div>'
            + box("Tickets &amp; documents", "database · IT policies")
            + '</div><div class="hw-loop">Results go back to the AI, which decides the next step · '
            + 'the employee confirms every change</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.markdown("##### What the AI does\n"
                    "- Understands requests in plain English or Japanese, and reads screenshots\n"
                    "- Finds answers in IT policies and the self-help guide, with sources\n"
                    "- Decides the next step: look up, offer self-help, or prepare a ticket\n"
                    "- Picks the right team and priority, and writes clear tickets")
        c2.markdown("##### What normal software does\n"
                    "- Creates, updates and closes tickets, only after confirmation\n"
                    "- Checks who may see and change what\n"
                    "- Response-time targets, overdue alerts, email previews\n"
                    "- Audit log, feedback, self-help and cost tracking")
        tiles = [("Automatic test set", test, test_when), ("Cost per AI request", per_call, "estimate"),
                 ("AI model", "Google Gemini", "flash")]
        st.markdown('<div class="kpis" style="grid-template-columns:repeat(3,1fr)">' + "".join(
            f'<div class="kpi"><div class="kpi-v">{e(v)}</div><div class="kpi-l">{e(l)} · {e(n)}</div></div>'
            for l, v, n in tiles) + "</div>", unsafe_allow_html=True)

    with safety:
        st.markdown('<div class="hw-intro">The safety rules that keep the AI assistant safe, and how each one is '
                    'protected:<br><span class="hw-badge hw-code">Built into the software</span> the AI cannot '
                    'change or skip it. <span class="hw-badge hw-test">AI rule · checked by tests</span> part of '
                    'the AI\'s instructions, checked by the automatic test set.</div>', unsafe_allow_html=True)
        for group, rules in SAFETY_RULES:
            rows = "".join(f'<div class="hw-rule"><div><b>{e(t)}</b><br><span>{e(d)}</span></div>'
                           f'<span class="hw-badge {BADGES[k][1]}">{BADGES[k][0]}</span></div>' for t, d, k in rules)
            st.markdown(f'<div class="hw-group">{e(group)}</div>{rows}', unsafe_allow_html=True)
        st.markdown('<div class="hw-note"><b>Honest note:</b> no AI is 100% perfect. That is why the most important '
                    'protections (permissions, confirmation before changes, the step limit, password removal and the '
                    'audit log) are enforced by normal software that the AI cannot change. The AI rules are checked '
                    'by automatic tests, and the test set grows whenever a new risk is found.</div>',
                    unsafe_allow_html=True)

    with limits:
        st.markdown("- **Dummy data only.** No real employees, tickets or company documents.\n"
                    "- **Messages are processed by Google Gemini** (a cloud AI service). A real pilot needs a "
                    "data-protection and security review of the AI provider.\n"
                    "- **Emails are previews only**, nothing is sent.\n"
                    "- **Not connected to a real ticket system** (e.g. ServiceNow) or company sign-in.\n"
                    "- **Demo database:** tickets are stored in a small local file.\n"
                    f"- **Conversation history:** {'saved for ' + str(RETENTION_DAYS) + ' days' if HISTORY_ON else 'off'}"
                    " (a real bank's compliance team would set the retention period).")


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(f'<div class="prof"><div class="tb-avatar">{e(initials(me["name"]))}</div><div>'
                f'<div class="prof-n">{e(short_name(me["name"]))}</div>'
                f'<div class="prof-d">{e(role_label)} · ID {e(me["employee_id"])}<br>'
                f'{e(me["department"])} · {e(me["location"])}</div></div></div>', unsafe_allow_html=True)
    st.write("")
    if st.button("New conversation", icon=":material/add:", type="primary", width="stretch", key="new_side"):
        new_conversation()
        st.rerun()
    if GOOGLE:
        st.button("Sign out", width="stretch", on_click=st.logout)
    else:
        listed = [p["email"] for p in tools.EMPLOYEES.values() if p.get("listed", True) or p["email"] == USER]
        chosen = st.selectbox("Switch user (demo only)", listed, index=listed.index(USER),
                              format_func=lambda m: names[m])
        if chosen != USER:
            st.session_state.user = chosen
            new_conversation()
            st.rerun()
    if is_admin and st.button("Reset demo data", icon=":material/restart_alt:", width="stretch",
                              help="Deletes all new tickets, logs and feedback, and restores the starting tickets."):
        db.reset()
        new_conversation()
        st.rerun()
    st.write("")
    if st.button("How it works & safety", icon=":material/verified_user:", width="stretch", key="how"):
        how_it_works()
    st.markdown('<div class="side-foot">Demo environment with dummy data.<br>'
                'Actions only change demo tickets.<br>AI model: Google Gemini<br>'
                + (f'Conversations are saved for {RETENTION_DAYS} days for quality and audit.' if HISTORY_ON
                   else 'Conversations are not saved.') + '</div>', unsafe_allow_html=True)

# ---------- Top bar ----------
st.markdown(f'<div class="tb-header"><div class="tb-brand"><div class="tb-logo">TB</div>'
            f'<div class="tb-title">{BRAND}<span>IT Service Desk</span></div></div>'
            '<div class="tb-right"><span class="tb-env">Demo environment</span>'
            f'<div class="tb-user"><div class="tb-avatar">{e(initials(me["name"]))}</div><div>'
            f'<div class="tb-uname">{e(short_name(me["name"]))}</div>'
            f'<div class="tb-urole">{e(role_label)} · {e(me["department"])}</div></div></div></div></div>',
            unsafe_allow_html=True)


# ---------- Live chat with a person (plain software, no AI) ----------
def live_message(role, sender, text, key):
    """One live-chat line: system notices in grey, IT agent messages with their name, employee messages as usual."""
    if role == "system":
        st.markdown(f'<div class="live-sys">{e(text)}</div>', unsafe_allow_html=True)
        return
    who = short_name(names.get(sender, sender))
    if role == "agent":
        with st.container(key=f"live_agent_{key}"):
            with st.chat_message("assistant", avatar=":material/headset_mic:"):
                st.markdown(f'<div class="live-who">{e(who)} · Service Desk</div>', unsafe_allow_html=True)
                st.markdown(e(text))
    else:
        with st.container(key=f"msg_user_live{key}"):
            with st.chat_message("user", avatar=":material/person:"):
                st.markdown(e(text))


def live_status():
    """The employee's open live chat (or None). When it has just ended, its messages move into the chat."""
    tid = st.session_state.get("live_tid")
    if not tid:
        return None
    lc = db.get_live_chat(tid)
    if lc and lc["status"] != "ended":
        st.session_state.live_seen = lc["status"]
        return lc
    msgs = [m for m in db.list_live_messages(tid) if m["role"] in ("system", "agent", "user")]
    for m in msgs:
        st.session_state.display.append({"id": f"live{m['id']}", "role": "user" if m["role"] == "user" else
                                         "assistant", "live": m["role"], "sender": m["sender"], "text": m["text"]})
    summary = " | ".join(f"{m['role']}: {m['text']}" for m in msgs)[-1500:]
    st.session_state.contents.append(types.Content(role="model", parts=[types.Part.from_text(
        text=f"[A live chat with a Service Desk person took place and has ended. Transcript: {summary}]")]))
    st.session_state.live_tid = None
    st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "live": "system", "sender": "",
                                     "text": "You're back with the virtual agent. Ask me anything else."})
    return None


@st.fragment(run_every=3)
def live_feed_employee(tid):
    """Refreshes every 3 seconds so the IT agent's replies appear without clicking anything."""
    lc = db.get_live_chat(tid)
    if not lc or lc["status"] != st.session_state.get("live_seen"):
        st.rerun(scope="app")                         # an agent joined or the chat ended: redraw everything
    for m in db.list_live_messages(tid):
        if m["role"] in ("system", "agent", "user"):
            live_message(m["role"], m["sender"], m["text"], m["id"])
    if lc["status"] == "waiting":
        st.markdown('<div class="live-bar live-wait"><span class="live-dot"></span>Waiting for a Service Desk agent '
                    '· you can keep typing, your messages will be passed on</div>', unsafe_allow_html=True)
    else:
        agent_name = short_name(names.get(lc["agent"], lc["agent"] or "IT agent"))
        st.markdown(f'<div class="live-bar live-on"><span class="live-dot"></span>You are chatting with '
                    f'{e(agent_name)} (Service Desk) · the AI assistant is paused</div>', unsafe_allow_html=True)



def render_chat():
    clicked = None
    if st.session_state.display or st.session_state.pending:
        _, b1, b2 = st.columns([1.6, 1.4, 1])
        done = st.session_state.get("handed_off", False)
        if b1.button("Handed over" if done else "Talk to a person", icon=":material/support_agent:", width="stretch", key="human",
                     disabled=done, help="Hand this conversation to the Service Desk team"):
            talk_to_person()
            st.rerun()
        if b2.button("Home", icon=":material/home:", width="stretch", key="new_top", help="Start a new conversation. Your tickets are kept."):
            new_conversation()
            st.rerun()
    else:
        hour = db.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        st.markdown(f'<div class="card welcome"><h3>{greet}, {e(short_name(me["name"]).split()[0])}</h3>'
                    '<p>I\'m your IT virtual agent. Ask me about IT policies, check on your tickets, '
                    'or tell me about a problem and I\'ll raise a ticket for you. I always ask before I change anything. '
                    'You can write in English or 日本語.</p>'
                    '<div class="caps"><span class="cap">Policy answers with sources</span>'
                    '<span class="cap">Ticket status</span><span class="cap">Raise &amp; update tickets</span>'
                    '<span class="cap">You confirm every action</span>'
                    + (f'<span class="cap">Chats are saved for {RETENTION_DAYS} days</span>' if HISTORY_ON else "")
                    + '</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Suggested</div>', unsafe_allow_html=True)
        if is_admin:
            examples = ["Which tickets are still open?",
                        "Move T-1002 to the Apps Team and set it to In progress",
                        "Show me the history of T-1001",
                        "What does the policy say about USB drives?"]
        else:
            examples = ["What's the status of my monitor request?",
                        "My keyboard stopped working, can you raise a ticket?",
                        "I forgot my password and need to reset it",
                        "VPNに接続できません。どうすればいいですか？",
                        "I think I lost my company phone on the train",
                        "Show me Mai Saito's tickets"]
        with st.container(key="chips"):
            cols = st.columns(2)
            for i, ex in enumerate(examples):
                if cols[i % 2].button(ex, key=f"ex{i}", width="stretch"):
                    clicked = ex

    live = live_status()                              # first, so a just-ended live chat shows up in order
    self_help_click = None
    last_assistant = next((x["id"] for x in reversed(st.session_state.display) if x["role"] == "assistant"), None)
    for m in st.session_state.display:
        if m.get("live"):                                 # a message from a live chat with a person
            live_message(m["live"], m.get("sender", ""), m["text"], m["id"])
            continue
        avatar = ":material/support_agent:" if m["role"] == "assistant" else ":material/person:"
        with st.container(key=f"msg_{m['role']}_{m['id']}"):
            with st.chat_message(m["role"], avatar=avatar):
                st.markdown(m["text"])
                if m.get("image"):
                    st.image(m["image"], width=320, caption="Attached screenshot")
                if m["role"] == "assistant":
                    if m.get("sources"):
                        st.markdown('<div class="srcs">' + "".join(f'<span class="src">{e(s)}</span>'
                                    for s in m["sources"]) + "</div>", unsafe_allow_html=True)
                    for mail in m.get("emails", []):
                        email_preview(mail["kind"], mail["ticket_id"])
                    if m.get("steps"):
                        n = len(m["steps"])
                        with st.expander(f"How I worked this out ({n} step{'s' if n != 1 else ''})"):
                            st.markdown('<div class="steps">' + "<br>".join(e(s) for s in m["steps"]) + "</div>",
                                        unsafe_allow_html=True)
                    if m.get("self_help") == "ask" and m["id"] == last_assistant and not st.session_state.pending:
                        with st.container(key=f"sh_{m['id']}"):
                            st.markdown('<div class="sh-q">Did this solve your problem?</div>', unsafe_allow_html=True)
                            y, n_, _ = st.columns([1.2, 1.4, 1])
                            if y.button("Yes, solved", key=f"shy_{m['id']}", type="primary", width="stretch"):
                                self_help_click = (m, True)
                            if n_.button("No, raise a ticket", key=f"shn_{m['id']}", width="stretch"):
                                self_help_click = (m, False)
                    elif m.get("self_help") == "solved":
                        st.markdown('<div class="sh-done">Solved with self-help · no ticket needed</div>',
                                    unsafe_allow_html=True)
                    rating = st.feedback("thumbs", key=f"fb_{m['id']}")
                    if rating is not None and st.session_state.feedback_saved.get(m["id"]) != rating:
                        db.save_feedback(m["id"], USER, m.get("question", ""), m["text"], rating)
                        st.session_state.feedback_saved[m["id"]] = rating

    if live:
        live_feed_employee(live["ticket_id"])

    # Confirmation card for a pending action: plain words, editable, nothing happens until confirmed
    if st.session_state.pending:
        p = st.session_state.pending
        a = p["args"]

        def pick(options, value):
            return options.index(value) if value in options else 0

        heading, button = {
            "create_ticket": ("Please confirm your new ticket", "Submit ticket"),
            "add_comment": (f"Please confirm this update to {a.get('ticket_id', '')}", "Add update"),
            "update_ticket": (f"Please confirm the change to {a.get('ticket_id', '')}", "Save changes"),
            "close_ticket": (f"Please confirm: close ticket {a.get('ticket_id', '')}", "Close ticket"),
        }.get(p["name"], (f"Please confirm: {p['name']}", "Confirm"))
        with st.container(key="approval"):
            st.markdown(f'<div class="ap-head">{e(heading)}</div>'
                        '<div class="ap-sub">Check the details and change anything that\'s wrong. '
                        'Nothing happens until you confirm.</div>', unsafe_allow_html=True)
            with st.form("confirm", border=False):
                if p["name"] == "create_ticket":
                    title = st.text_input("Title", a.get("title", ""))
                    desc = st.text_area("Details", a.get("description", ""), height=80)
                    c1, c2, c3 = st.columns(3)
                    pr = c1.selectbox("Priority", tools.PRIORITIES, index=pick(tools.PRIORITIES, a.get("priority")))
                    team = c2.selectbox("Assign to", tools.TEAMS, index=pick(tools.TEAMS, a.get("team")))
                    cat = c3.text_input("Category", a.get("category", ""))
                    final = {"title": title, "description": desc, "category": cat, "priority": pr, "team": team}
                elif p["name"] == "add_comment":
                    comment = st.text_area("Update", a.get("comment", ""), height=80)
                    final = {"ticket_id": a.get("ticket_id", ""), "comment": comment}
                elif p["name"] == "close_ticket":
                    reason = st.text_area("Reason", a.get("reason", ""), height=70)
                    final = {"ticket_id": a.get("ticket_id", ""), "reason": reason}
                elif p["name"] == "update_ticket":
                    keep = "(no change)"
                    c1, c2, c3 = st.columns(3)
                    stt = c1.selectbox("Status", [keep] + tools.STATUSES, index=pick([keep] + tools.STATUSES, a.get("status")))
                    tm = c2.selectbox("Team", [keep] + tools.TEAMS, index=pick([keep] + tools.TEAMS, a.get("team")))
                    prr = c3.selectbox("Priority", [keep] + tools.PRIORITIES, index=pick([keep] + tools.PRIORITIES, a.get("priority")))
                    note = st.text_area("Note", a.get("note", ""), height=70)
                    final = {"ticket_id": a.get("ticket_id", ""), "status": "" if stt == keep else stt,
                             "team": "" if tm == keep else tm, "priority": "" if prr == keep else prr, "note": note}
                else:
                    st.json(a)
                    final = dict(a)
                s, c, _ = st.columns([1.3, 1, 2])
                submitted = s.form_submit_button(button, type="primary", width="stretch")
                cancelled = c.form_submit_button("Cancel", width="stretch")
            if submitted:
                decide(True, final)
                st.rerun()
            if cancelled:
                decide(False)
                st.rerun()

    if self_help_click:
        self_help_answer(*self_help_click)
        st.rerun()

    if live:                                          # talking to a person: the AI is paused
        sent = st.chat_input("Message the Service Desk…", key="live_input")
        if sent:
            db.add_live_message(live["ticket_id"], "user", USER, sent)
            st.rerun()
        return
    sent = st.chat_input("Ask about IT policies, your tickets, or describe a problem… (you can attach a screenshot)",
                         disabled=bool(st.session_state.pending), accept_file=True, file_type=["png", "jpg", "jpeg"])
    if sent and (sent.text or sent.files):
        ask(sent.text, shrink_image(sent.files[0]) if sent.files else None)
        st.rerun()
    if clicked:
        ask(clicked)
        st.rerun()


# ---------- My tickets (employees) and the admin console pages ----------
def kpis(items, wide=False):
    return (f'<div class="kpis{" wide" if wide else ""}">' + "".join(f'<div class="kpi"><div class="kpi-v">{e(str(v))}</div>'
                                           f'<div class="kpi-l">{e(label)}</div></div>' for label, v in items) + "</div>")


def render_my_tickets():
    mine = db.list_tickets(USER)
    current = [t for t in mine if t["status"] not in ("Resolved", "Closed")]
    past = [t for t in mine if t["status"] in ("Resolved", "Closed")]
    st.markdown(f'<div class="section-title">My open tickets · {len(current)}</div>', unsafe_allow_html=True)
    if not current:
        st.markdown('<div class="card" style="color:#6B7A8C;font-size:14px">You have no open tickets. '
                    'Describe a problem in the chat and the agent can help or raise one for you.</div>',
                    unsafe_allow_html=True)
    for t in reversed(current):
        ticket_card(t, actions=True)
    if past:
        with st.expander(f"Past tickets ({len(past)})"):
            for t in reversed(past):
                ticket_card(t, key_prefix="tkpast")


def needs_attention_cards(limit=None):
    open_t = [t for t in db.list_tickets() if t["status"] not in ("Resolved", "Closed")]
    hot = [t for t in open_t if t["priority"] in ("High", "Urgent")]
    handoffs = [t for t in open_t if t["status"] == "Waiting for agent"]
    overdue = [t for t in open_t if sla.is_overdue(t)]
    st.markdown(kpis([("Open tickets", len(open_t)), ("Overdue", len(overdue)),
                      ("High / Urgent", len(hot)), ("Waiting for a person", len(handoffs))]),
                unsafe_allow_html=True)
    attention = [t for t in open_t if t in hot or t in handoffs or t in overdue]
    attention.sort(key=lambda t: (t["status"] != "Waiting for agent", not sla.is_overdue(t),
                                  {"Urgent": 0, "High": 1}.get(t["priority"], 2)))
    st.markdown(f'<div class="section-title">Needs attention · {len(attention)}</div>', unsafe_allow_html=True)
    if not attention:
        st.caption("Nothing urgent right now.")
    for t in attention[:limit]:
        ticket_card(t, show_requester=True, key_prefix="tkatt")
    if limit and len(attention) > limit:
        st.caption(f"+ {len(attention) - limit} more on the Tickets page.")



def page_tickets():
    df = an.tickets_frame(names)
    st.markdown('<div class="dash-title">All tickets</div><div class="dash-sub">Filter, search and open any ticket. '
                'To change a ticket, ask the assistant (you confirm every change).</div>', unsafe_allow_html=True)
    st.write("")
    f1, f2, f3, f4, f5 = st.columns([1.9, 1.3, 1.3, 1.1, 1.5], vertical_alignment="bottom")
    show = f1.segmented_control("Show", ["Open", "All", "Needs attention"], default="Open", key="flt_show") or "Open"
    teams = f2.multiselect("Team", an.TEAMS, key="flt_team", placeholder="All teams")
    stages = f3.multiselect("Stage", an.STAGES + ["Resolved"], key="flt_stage", placeholder="All stages")
    prios = f4.multiselect("Priority", tools.PRIORITIES, key="flt_prio", placeholder="All")
    q = f5.text_input("Search", placeholder="ID, title or person", key="flt_q")
    if show == "Open":
        df = df[df.open]
    elif show == "Needs attention":
        df = df[df.open & (df.res_breach | df.resp_breach | df.stalled)]
    if teams:
        df = df[df.Team.isin(teams)]
    if stages:
        df = df[df.Stage.isin(stages)]
    if prios:
        df = df[df.Priority.isin(prios)]
    if q:
        ql = q.lower()
        df = df[df.ID.str.lower().str.contains(ql, regex=False) | df.Title.str.lower().str.contains(ql, regex=False)
                | df.Requester.str.lower().str.contains(ql, regex=False)]
    df = df.sort_values("created", ascending=False)
    view = pd.DataFrame({
        "ID": df.ID, "Title": df.Title, "Requester": df.Requester, "Team": df.Team, "Priority": df.Priority,
        "Status": df.Status,
        "SLA": ["Resolution overdue" if r.res_breach else "Response late" if r.resp_breach
                else "Met" if not r.open else "On track" for r in df.itertuples()],
        "Idle": [f"{d:.0f} days idle" if s else "" for s, d in zip(df.stalled, df.idle_days)],
        "Opened": df.created.dt.strftime("%d %b %H:%M"),
    })
    st.caption(f"{len(view)} tickets")
    picked = st.dataframe(view, hide_index=True, width="stretch", height=min(40 + 35 * len(view), 460),
                          on_select="rerun", selection_mode="single-row", key="flt_table")
    rows = picked.selection.rows if picked and picked.selection else []
    c1, c2 = st.columns([1, 1.2], gap="large")
    with c1:
        chosen_id = view.ID.iloc[rows[0]] if rows else st.selectbox(
            "Open a ticket", list(view.ID), index=None, placeholder="Click a row above, or choose a ticket")
        if chosen_id:
            ticket_card(db.get_ticket(chosen_id), show_requester=True, key_prefix="tkopen")
    with c2:
        st.download_button(f"Download these {len(view)} tickets (CSV)", view.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"testbank_tickets_{db.now():%Y%m%d_%H%M}.csv", mime="text/csv")



def page_chats():
    with st.expander("Conversation history settings", icon=":material/settings:"):
        on = st.toggle("Save full conversations", value=HISTORY_ON,
                       help="When on, every chat is saved so IT can review quality, complaints and audits.")
        days = st.selectbox("Keep conversations for", [30, 90, 365], format_func=lambda d: f"{d} days",
                            index=[30, 90, 365].index(RETENTION_DAYS) if RETENTION_DAYS in (30, 90, 365) else 1)
        if on != HISTORY_ON or days != RETENTION_DAYS:
            db.set_setting("history_on", "1" if on else "0")
            db.set_setting("retention_days", days)
            db.log_audit(USER, "history_settings", {"save_conversations": on, "retention_days": days},
                         {"saved": True}, "user action")
            st.rerun()
        sure = st.checkbox("I understand this permanently deletes all saved conversations")
        if st.button("Delete all conversation history", icon=":material/delete:", disabled=not sure):
            db.delete_all_conversations()
            db.log_audit(USER, "delete_all_conversations", {}, {"deleted": True}, "user action")
            st.rerun()
    convs = db.list_conversations()
    status_note = (f"Saving is <b>on</b>: chats are kept for {RETENTION_DAYS} days, then deleted automatically."
                   if HISTORY_ON else "Saving is <b>off</b>: new chats are not saved.")
    st.markdown(f'<div class="note">{status_note} Passwords are removed; screenshots are not stored. '
                f'{len(convs)} saved.</div>', unsafe_allow_html=True)
    if convs:
        people = ["Everyone"] + sorted({c["user"] for c in convs}, key=lambda u: names.get(u, u))
        who_f = st.selectbox("Show chats from", people, format_func=lambda u: u if u == "Everyone"
                             else short_name(names.get(u, u)))
        rows = [{"Conversation": c["id"][:8], "Started (JST)": c["started_at"], "User": c["user"],
                 "Outcome": c["outcome"], "Time": m["at"], "From": "Employee" if m["role"] == "user" else "Agent",
                 "Message": m["text"] + (" [screenshot attached]" if m["screenshot"] else "")}
                for c in convs for m in c["messages"]]
        st.download_button(f"Download conversations (CSV, {len(convs)} chats)",
                           pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"), width="stretch",
                           file_name=f"testbank_conversations_{db.now():%Y%m%d_%H%M}.csv", mime="text/csv")
        for c in convs:
            if who_f != "Everyone" and c["user"] != who_f:
                continue
            who = short_name(names.get(c["user"], c["user"]))
            with st.expander(f"{c['started_at'][5:16]} · {who} · {c['outcome']} · {len(c['messages'])} messages"):
                st.markdown("".join(
                    f'<div class="tr tr-{"u" if m["role"] == "user" else "a"}"><span>{e(m["at"][11:16])} · '
                    f'{"Employee" if m["role"] == "user" else "Agent"}</span>{e(m["text"])}'
                    + (" <i>[screenshot attached]</i>" if m["screenshot"] else "") + "</div>"
                    for m in c["messages"]), unsafe_allow_html=True)


def page_audit():
    full = db.list_audit()
    csv = pd.DataFrame([{"Time (JST)": x["at"], "User email": x["user"],
                         "User name": short_name(names.get(x["user"], x["user"] or "")),
                         "Tool / action": x["tool"], "Status": x["status"],
                         "Details": json.dumps(x["args"], ensure_ascii=False),
                         "Result": json.dumps(x["result"], ensure_ascii=False)} for x in full],
                       columns=["Time (JST)", "User email", "User name", "Tool / action", "Status",
                                "Details", "Result"]).to_csv(index=False).encode("utf-8-sig")
    st.download_button(f"Download audit log (CSV, {len(full)} entries)", csv, width="stretch",
                       file_name=f"testbank_audit_log_{db.now():%Y%m%d_%H%M}.csv", mime="text/csv")
    log = full[:200]
    st.markdown(f'<div class="note">Every tool the agent used, for every user. Newest first. '
                f'Showing {len(log)} of {len(full)}.</div>', unsafe_allow_html=True)
    icons = {"done": "read ·", "approved": "approved ·", "approved (edited)": "approved (edited) ·", "rejected": "cancelled ·", "user action": "user action ·"}
    for x in log:
        who = short_name(names.get(x["user"], x["user"] or ""))
        args = ", ".join(f"{k}={v!r}" for k, v in x["args"].items())
        with st.expander(f"{x['at'][11:]} · {who} · {icons.get(x['status'], '•')} {x['tool']}({args})"):
            st.caption(f"{x['at']} · status: {x['status']}")
            st.json(x["result"] if isinstance(x["result"], (dict, list)) else {"result": x["result"]})


def page_quality():
    fb = db.list_feedback()
    ups = sum(1 for f in fb if f["rating"] == 1)
    score = f"{round(100 * ups / len(fb))}%" if fb else "–"
    st.markdown('<div class="section-title">Answer quality</div>' +
                kpis(wide=True, items=[("Helpful", ups), ("Not helpful", len(fb) - ups), ("Satisfaction", score),
                      ("Answers rated", len(fb))]), unsafe_allow_html=True)
    downs = [f for f in fb if f["rating"] == 0]
    if downs:
        with st.expander(f"Answers marked not helpful ({len(downs)})"):
            for f in downs:
                st.markdown(f"**Q:** {f['question']}\n\n**A:** {f['answer'][:300]}")
                st.caption(f"{f['at']} · {short_name(names.get(f['user'], f['user']))}")
                st.divider()

    sh = db.self_help_totals()
    solved, needed = sh.get("solved", 0), sh.get("needed a ticket", 0)
    rate = f"{round(100 * solved / (solved + needed))}%" if solved + needed else "–"
    st.markdown('<div class="section-title">Self-help · tickets avoided</div>' +
                kpis(wide=True, items=[("Solved without a ticket", solved), ("Still needed a ticket", needed),
                      ("Self-help success rate", rate),
                      (f"IT time saved (est. {MINUTES_PER_TICKET} min/ticket)", f"{solved * MINUTES_PER_TICKET / 60:.0f} hours")]),
                unsafe_allow_html=True)

    totals = db.usage_totals()
    chat = totals.get("chat", {"calls": 0, "input": 0, "output": 0})
    cost = agent.estimated_cost_usd(totals)
    per_call = cost / chat["calls"] if chat["calls"] else 0
    st.markdown('<div class="section-title">AI usage &amp; cost</div>' +
                kpis(wide=True, items=[("AI requests", chat["calls"]),
                      ("Tokens in / out", f"{chat['input']:,} / {chat['output']:,}"),
                      (f"Estimated cost · ≈ ₹{cost * agent.USD_TO_INR:.2f}", f"${cost:.4f}"),
                      ("Per AI request", f"${per_call:.5f}")]), unsafe_allow_html=True)
    st.markdown(f'<div class="note">Estimate at ${agent.PRICE_IN_PER_M}/M input and ${agent.PRICE_OUT_PER_M}/M '
                f'output tokens, plus {totals.get("embedding", {}).get("calls", 0)} policy searches. '
                'Your Google billing page shows the exact amount.</div>', unsafe_allow_html=True)

def waited(since):
    mins = int((db.now() - datetime.datetime.fromisoformat(since).replace(tzinfo=db.TOKYO)).total_seconds() // 60)
    return "just now" if mins < 1 else f"{mins} min ago" if mins < 60 else f"{mins // 60} h {mins % 60} min ago"


@st.fragment(run_every=4)
def live_queue():
    """The list of employees who asked for a person. Refreshes every 4 seconds."""
    chats = db.list_live_chats()
    if not chats:
        st.markdown('<div class="card" style="font-size:13.5px;color:#5A6575">No one is waiting right now.<br><br>'
                    '<b>To try it:</b> open the app in a second browser window, sign in as an employee, ask a '
                    'question and click <b>Talk to a person</b>. The request appears here within a few seconds.'
                    '</div>', unsafe_allow_html=True)
        return
    for c in chats:
        t = db.get_ticket(c["ticket_id"]) or {"title": ""}
        mine = c["status"] == "active" and c["agent"] == USER
        state = ("Waiting · " + waited(c["requested_at"])) if c["status"] == "waiting" else \
            ("With you" if mine else "With " + short_name(names.get(c["agent"], c["agent"] or "")))
        cls = "s-agent" if c["status"] == "waiting" else "s-progress"
        with st.container(key=f"lq_{c['ticket_id']}"):
            st.markdown(f'<div class="tk-top"><span class="tk-id">{e(c["ticket_id"])}</span>'
                        f'<span class="badge {cls}">{e(state)}</span></div>'
                        f'<div class="tk-title">{e(short_name(names.get(c["user"], c["user"])))}</div>'
                        f'<div class="tk-meta">{e(t["title"].replace("Live chat handoff: ", ""))}</div>',
                        unsafe_allow_html=True)
            label = "Join chat" if c["status"] == "waiting" else "Open"
            if (c["status"] == "waiting" or mine) and st.button(label, key=f"lq_btn_{c['ticket_id']}",
                                                                type="primary" if c["status"] == "waiting" else
                                                                "secondary", width="stretch"):
                if c["status"] == "waiting":
                    agent_join(c["ticket_id"])
                st.session_state.live_open = c["ticket_id"]
                st.rerun(scope="app")


def agent_join(tid):
    me_name = short_name(me["name"])
    db.join_live_chat(tid, USER, me_name)
    db.update_ticket(tid, status="In progress")
    db.mark_responded(tid)
    db.add_history(tid, f"Service Desk: {me_name} joined the live chat.")
    db.log_audit(USER, "join_live_chat", {"ticket_id": tid}, {"joined": tid}, "user action")


@st.fragment(run_every=3)
def live_feed_agent(tid):
    lc = db.get_live_chat(tid)
    for m in db.list_live_messages(tid):
        if m["role"] in ("system", "agent", "user"):
            live_message(m["role"], m["sender"], m["text"], m["id"])
    if lc and lc["status"] == "ended":
        st.markdown('<div class="live-bar">This chat has ended. The transcript is saved in the ticket history.</div>',
                    unsafe_allow_html=True)


def page_live():
    st.markdown('<div class="dash-title">Live chats</div><div class="dash-sub">Employees who clicked "Talk to a person". '
                'Join a chat to reply to them directly; the AI assistant stays out of the conversation.</div>',
                unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1, 2.3], gap="large")
    with left:
        st.markdown('<div class="section-title">Queue</div>', unsafe_allow_html=True)
        live_queue()
    with right:
        tid = st.session_state.get("live_open")
        lc = db.get_live_chat(tid) if tid else None
        if not lc:
            st.markdown('<div class="card" style="color:#5A6575;font-size:14px">Choose a chat from the queue.</div>',
                        unsafe_allow_html=True)
            return
        t = db.get_ticket(tid)
        who = short_name(names.get(lc["user"], lc["user"]))
        st.markdown(f'<div class="card"><div class="tk-top"><span class="tk-id">{e(tid)} · {e(who)}</span>'
                    f'<span class="badge {STATUS_CLASS.get(t["status"], "s-new")}">{e(t["status"])}</span></div>'
                    f'<div class="tk-meta">{e(tools.EMPLOYEES.get(lc["user"], {}).get("department", ""))} · '
                    f'{e(lc["user"])} · asked {e(waited(lc["requested_at"]))}</div></div>', unsafe_allow_html=True)
        before = [m for m in db.list_live_messages(tid) if m["role"].startswith("before_")]
        with st.expander(f"Conversation with the virtual agent before the handoff ({len(before)} messages)",
                         expanded=lc["status"] == "active" and len(before) <= 6):
            st.markdown("".join(f'<div class="tr tr-{"u" if m["role"] == "before_user" else "a"}"><span>'
                                f'{"Employee" if m["role"] == "before_user" else "Virtual agent"}</span>{e(m["text"])}'
                                '</div>' for m in before) or "No messages.", unsafe_allow_html=True)
        live_feed_agent(tid)
        if lc["status"] == "active" and lc["agent"] == USER:
            reply = st.chat_input(f"Reply to {who.split()[0]}…", key="agent_reply")
            if reply:
                db.add_live_message(tid, "agent", USER, reply)
                st.rerun()
            with st.popover("End chat", icon=":material/call_end:"):
                with st.form("end_live", border=False):
                    outcome = st.radio("Outcome", ["Solved: resolve the ticket", "Not solved yet: keep the ticket open"])
                    note = st.text_input("Note for the ticket (optional)", placeholder="e.g. Reset MFA on new phone")
                    if st.form_submit_button("End chat", type="primary"):
                        end_live(tid, outcome.startswith("Solved"), note)
                        st.rerun()


def end_live(tid, solved, note):
    me_name = short_name(me["name"])
    db.end_live_chat(tid, me_name)
    lines = [f"{'Employee' if m['role'] == 'user' else short_name(names.get(m['sender'], m['sender']))}: {m['text']}"
             for m in db.list_live_messages(tid) if m["role"] in ("user", "agent")]
    db.add_history(tid, "Live chat transcript: " + (" | ".join(lines) or "(no messages)"))
    db.add_history(tid, f"Service Desk: live chat ended by {me_name}. " + (note or "") +
                   (" Resolved." if solved else " Ticket kept open for follow-up."))
    db.update_ticket(tid, status="Resolved" if solved else "In progress")
    db.log_audit(USER, "end_live_chat", {"ticket_id": tid, "solved": solved, "note": note},
                 {"ended": tid}, "user action")
    st.session_state.live_open = None


@st.fragment(run_every=5)
def live_alert(current_page):
    """A notice on every admin page when someone is waiting for a person."""
    waiting = [c for c in db.list_live_chats() if c["status"] == "waiting"]
    if not waiting or current_page == "Live chats":
        return
    first = short_name(names.get(waiting[0]["user"], waiting[0]["user"]))
    text = f"{first} is waiting for a live chat" if len(waiting) == 1 else f"{len(waiting)} employees are waiting for a live chat"
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.markdown(f'<div class="live-alert"><span class="live-dot"></span>{e(text)} · asked '
               f'{e(waited(waiting[0]["requested_at"]))}</div>', unsafe_allow_html=True)
    if b.button("Open live chats", key="go_live", type="primary", width="stretch"):
        st.session_state.goto_live = True
        st.rerun(scope="app")


# ---------- Layout ----------
if not is_admin:                                          # employees: chat + my tickets (unchanged)
    chat_col, side_col = st.columns([3, 2], gap="large")
    with chat_col:
        render_chat()
    with side_col:
        render_my_tickets()
else:                                                     # IT admin: full-width console with a menu
    PAGES = ["Dashboard", "Tickets", "Live chats", "Assistant", "Chats", "Audit log", "Quality & cost"]
    st.session_state.setdefault("nav", "Dashboard")
    if st.session_state.pop("goto_live", False):
        st.session_state.nav = "Live chats"
    with st.container(key="adminnav"):
        NAV = st.segmented_control("Admin menu", PAGES, key="nav",
                                   label_visibility="collapsed") or "Dashboard"
    live_alert(NAV)
    if NAV == "Dashboard":
        dashboard.render(names)
    elif NAV == "Tickets":
        page_tickets()
    elif NAV == "Assistant":
        chat_col, side_col = st.columns([3, 2], gap="large")
        with chat_col:
            render_chat()
        with side_col:
            needs_attention_cards(limit=4)
    elif NAV == "Live chats":
        page_live()
    elif NAV == "Chats":
        page_chats()
    elif NAV == "Audit log":
        page_audit()
    else:
        page_quality()


def conversation_outcome(display):
    created = [x["ticket_id"] for m in display for x in m.get("emails", []) if x["kind"] == "created"]
    kinds = {x["kind"] for m in display for x in m.get("emails", [])}
    if "handoff" in kinds:
        return "Passed to a person"
    if created:
        return "Ticket created (" + ", ".join(created) + ")"
    if any(m.get("self_help") == "solved" for m in display):
        return "Solved by self-help"
    if "closed" in kinds:
        return "Ticket closed"
    if kinds & {"updated", "admin_update"}:
        return "Ticket updated"
    return "Answered"


if HISTORY_ON and st.session_state.display:            # save the whole chat (optional, see admin settings)
    st.session_state.setdefault("conv_id", uuid.uuid4().hex)
    st.session_state.setdefault("conv_started", db.now().strftime("%Y-%m-%d %H:%M:%S"))
    for m in st.session_state.display:
        m.setdefault("at", db.now().strftime("%Y-%m-%d %H:%M:%S"))
    db.save_conversation(st.session_state.conv_id, USER, st.session_state.conv_started,
                         conversation_outcome(st.session_state.display), st.session_state.display)

st.markdown(f'<div class="foot">{BRAND} IT Service Desk · Demo environment · Dummy data only · '
            'Powered by Google Gemini</div>', unsafe_allow_html=True)
