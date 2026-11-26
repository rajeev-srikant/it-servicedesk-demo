import os
import json
import html
import io
import uuid
import datetime
import re
import time

from i18n import tr, tr_sla, EXAMPLES
from urllib.parse import unquote
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
import sharepoint
import kb
import incidents
import catalog
import trending
import benefits
import org
import insights

load_dotenv()

BRAND = "TestBank"
MINUTES_PER_TICKET = lambda: int(db.get_setting("minutes_per_ticket", "60"))   # IT admin can change it
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
.st-key-tbhead { background:#fff; border:1px solid var(--line); border-top:3px solid var(--navy); border-radius:4px;
  padding:12px 18px; margin-bottom:14px; overflow:visible; }
.st-key-tbhead [data-testid="stHorizontalBlock"] { min-height:44px; align-items:center; }
.st-key-tbhead .tb-user { white-space:nowrap; line-height:1.35; }
.st-key-tbhead [data-testid="stMarkdownContainer"] p { margin:0; }
.st-key-langbox [data-baseweb="select"] > div { min-height:34px; font-size:13px; }
.st-key-bell button { min-height:34px; padding:0 10px; }
.note-item { font-size:13px; line-height:1.45; padding:8px 0; border-bottom:1px solid var(--line); min-width:300px; }
.note-item span { display:block; font-size:11.5px; color:var(--ink2); }
.note-item.note-new { font-weight:600; }
.welcome [data-testid="stHeaderActionElements"], .welcome h3 a { display:none !important; }
.st-key-sp_badge button { min-height:0 !important; padding:3px 10px !important; background:var(--navy-l) !important;
  border:1px solid #C9D7E8 !important; color:var(--navy) !important; border-radius:3px !important; }
.st-key-sp_badge button p { font-size:12px !important; }
.st-key-sp_badge button:hover { border-color:var(--navy) !important; }
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

[class*="st-key-apr_"] { background:#fff; border:1px solid var(--line); border-left:3px solid #6B4FBB; border-radius:4px; padding:12px 16px; margin-bottom:8px; }
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
/* SharePoint */
.tb-sp { font-size:12px; color:var(--navy); background:var(--navy-l); border:1px solid #C9D7E8; padding:2px 8px; border-radius:3px; }
.sp-saved { display:flex; gap:10px; align-items:center; background:#F3F7FC; border:1px solid #C9D7E8;
  border-left:3px solid var(--navy); border-radius:4px; padding:8px 12px; font-size:13px; color:var(--ink); margin:4px 0; }
.sp-saved span { font-size:12px; color:var(--ink2); }
.sp-ico { flex-shrink:0; width:26px; height:26px; border-radius:3px; background:var(--navy); color:#fff !important;
  font-weight:700; font-size:11px !important; display:flex; align-items:center; justify-content:center; }
.sp-flow { display:grid; grid-template-columns: 120px 1fr; gap:8px 12px; align-items:center; margin:2px 0 14px 0; }
.sp-flow .lbl { font-size:12px; font-weight:600; color:var(--ink2); text-transform:uppercase; letter-spacing:.5px; }
.sp-row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.sp-step { background:#fff; border:1px solid var(--line); border-radius:4px; padding:6px 10px; font-size:13px; color:var(--ink); }
.sp-step.ai { background:var(--navy-l); border-color:var(--navy); font-weight:600; color:var(--navy); }
.sp-step.list { border-color:var(--ok); color:var(--ok); font-weight:600; background:#F2F9F3; }
.sp-arrow { color:var(--ink3); }
.inc-banner { display:flex; gap:10px; align-items:flex-start; background:#FFF6E5; border:1px solid #F0D9A8;
  border-left:3px solid var(--warn); border-radius:4px; padding:9px 14px; font-size:13.5px; color:var(--ink);
  margin-bottom:10px; }
.inc-banner .live-dot { color:var(--warn); margin-top:6px; }
.inc-banner span { font-size:12.5px; color:var(--ink2); }
[class*="st-key-outage_"], [class*="st-key-inc_"], [class*="st-key-gap_"] { background:#fff; border:1px solid var(--line);
  border-left:3px solid var(--bad); border-radius:4px; padding:12px 16px 12px 16px; margin-bottom:10px; }
[class*="st-key-gap_"] { border-left-color:var(--warn); }
.kb-box { background:#F7F4FC; border-color:#DCD3F0; border-left-color:var(--purple); }
.kb-ico { background:var(--purple) !important; }
[class*="st-key-kbd_"] { background:#fff; border:1px solid var(--line); border-left:3px solid var(--purple);
  border-radius:4px; padding:12px 16px 4px 16px; margin-bottom:10px; }
.sp-tag { font-size:11.5px; color:var(--ink3); margin-top:2px; }
.sp-crumb { font-size:13px; color:var(--ink2); margin:2px 0 10px 0; }
.sp-crumb b { color:var(--ink); }
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
  padding:8px 10px !important; box-shadow:none !important; margin-bottom:-1px; }
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
    st.markdown(f'<div class="login"><div class="tb-logo">TB</div><h2>{BRAND} {tr("IT Service Desk")}</h2>'
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
        login_card(tr("Sign in with your Google account to continue."))
        _, mid, _ = st.columns([1, 1, 1])
        mid.button(tr("Sign in with Google"), type="primary", width="stretch", on_click=st.login)
        st.stop()
    email = st.user.email.lower()
    tools.register_user(email, st.user.get("name"), admin=email in ADMIN_EMAILS)
    if st.session_state.get("user") != email:
        st.session_state.user = email
        new_conversation()
else:
    APP_PASSWORD = os.getenv("APP_PASSWORD")
    if APP_PASSWORD and not st.session_state.get("signed_in"):
        login_card(tr("Sign in to the demo environment with the access code you were given."))
        _, mid, _ = st.columns([1, 1.2, 1])
        with mid:
            entered = st.text_input(tr("Access code"), type="password")
            if entered:
                if entered == APP_PASSWORD:
                    st.session_state.signed_in = True
                    st.rerun()
                st.error(tr("That access code is not correct."))
        st.stop()
    if "user" not in st.session_state:
        st.session_state.user = "rajeev@testbank.com"
        new_conversation()

USER = st.session_state.user
me = tools.EMPLOYEES[USER]
is_admin = tools.is_admin(USER)
is_management = tools.EMPLOYEES.get(USER, {}).get("role") == "management"   # senior management: Benefits page only
role_label = tr("IT Admin") if is_admin else tr("Management") if is_management else tr("Employee")
LANG = st.session_state.get("lang", "en")     # "en" or "ja", chosen in the language box at the top
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
    started = time.time()
    with st.spinner(tr("Working on it…")):          # no step-by-step progress: just a short waiting message
        try:
            out = step_fn(lambda label: None)
            db.log_timing(USER, time.time() - started, agent.CHAT_MODEL, LANG)
        except Exception as ex:
            msg = str(ex)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                msg = tr("The AI service is busy or the usage limit was reached. Please try again in a minute.")
            out = {"type": "answer", "text": tr("Sorry, something went wrong: {msg}", msg=msg),
                   "trace": {"steps": [], "sources": []}}
    if out["type"] == "pending":
        st.session_state.pending = out
    else:
        sources = cited_sources(out["text"], out["trace"]["sources"])
        emails = out["trace"].get("emails", [])
        searched_self_help = any(x.startswith(("Self_Help_Guide", "KB-")) for x in out["trace"]["sources"])
        for src in sources:                            # knowledge base: count how often an article is suggested
            if src.startswith("KB-"):
                kb.count(src.split(" · ")[0], "suggested")
        is_self_help = not emails and (any(x.startswith(("Self_Help_Guide", "KB-")) for x in sources) or
                                       (searched_self_help and ("solve" in out["text"].lower() or "解決" in out["text"])))
        offers_ticket = not emails and not is_self_help and (
            out["trace"].get("offer_ticket") or OFFER_WORDS.search(out["text"]) is not None)
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "text": out["text"],
                                         "steps": out["trace"]["steps"], "sources": sources, "emails": emails,
                                         "self_help": "ask" if is_self_help else None,
                                         "offer": "ask" if offers_ticket else None,
                                         "kb": out["trace"].get("kb", []),
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
    prompt = prompt or tr("Here is a screenshot of my problem.")
    if not is_admin:                                  # counts towards "Most asked this week" (topic only, not the words)
        trending.log_question(USER, LANG, prompt)
    st.session_state.display.append({"id": uuid.uuid4().hex, "role": "user", "text": prompt, "image": image})
    parts = [types.Part.from_text(text=prompt)]
    if image:                                         # the AI can "see" the screenshot
        parts.append(types.Part.from_bytes(data=image, mime_type="image/png"))
    st.session_state.contents.append(types.Content(role="user", parts=parts))
    process(lambda on_step: agent.run(client, st.session_state.contents, USER, on_step, lang=LANG))


# The AI asked "Shall I raise a ticket?": show clear buttons instead of making the user type an answer
OFFER_WORDS = re.compile(r"raise (a|an|the)?\s*(support |new |IT )?ticket\?|create (a|an)?\s*(support |new )?ticket\?|"
                         r"チケットを(作成|起票|発行)しましょうか|チケットを(作成|起票)しますか", re.I)


def ticket_offer_answer(m, choice):
    """The user clicked one of the buttons under "Would you like me to raise a ticket?"."""
    m["offer"] = choice
    db.log_audit(USER, "ticket_offer_button", {"question": m.get("question", "")}, {"choice": choice}, "user action")
    if choice == "yes":
        ask(tr("Yes, please raise a ticket for this."))
    elif choice == "person":
        talk_to_person()
    else:
        text = tr("No problem, I won't raise a ticket. If you need anything else, just ask.")
        for role, t_ in (("user", tr("No, thanks.")), ("model", text)):
            st.session_state.contents.append(types.Content(role=role, parts=[types.Part.from_text(text=t_)]))
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "user", "text": tr("No, thanks.")})
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "text": text, "steps": [],
                                         "sources": [], "emails": [], "question": m.get("question", "")})


def self_help_answer(m, solved):
    """The user clicked "Yes, solved" or "No, raise a ticket" under a self-help answer."""
    m["self_help"] = "solved" if solved else "ticket"
    outcome = "solved" if solved else "needed a ticket"
    db.log_self_help(USER, m.get("question", ""), outcome)
    if solved:                                         # a KB article solved it: count it
        for src in m.get("sources", []):
            if src.startswith("KB-"):
                kb.count(src.split(" · ")[0], "solved")
    db.log_audit(USER, "self_help_result", {"question": m.get("question", "")}, {"outcome": outcome}, "user action")
    if solved:
        text = tr("Great, I'm glad that's sorted! No ticket needed. If anything else comes up, just ask.")
        for role, t in (("user", tr("Yes, that solved it.")), ("model", text)):
            st.session_state.contents.append(types.Content(role=role, parts=[types.Part.from_text(text=t)]))
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "user", "text": tr("Yes, that solved it.")})
        st.session_state.display.append({"id": uuid.uuid4().hex, "role": "assistant", "text": text, "steps": [],
                                         "sources": [], "emails": [], "question": m.get("question", "")})
    else:
        kb.log_gap(USER, m.get("question", ""), "self-help did not solve it")
        ask(tr("That didn't solve my problem. Please raise a ticket for me."))


def decide(confirmed, final_args=None):
    p = st.session_state.pending
    st.session_state.pending = None
    process(lambda on_step: agent.resume(client, st.session_state.contents, p, confirmed, final_args, USER, on_step, lang=LANG))


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
    text = tr("I've passed our conversation to the Service Desk as ticket **{tid}**. Please stay on this page: "
              "a member of the IT team will join this chat shortly. They can see our conversation, so you won't "
              "need to repeat anything. If you leave, they will follow up through the ticket.", tid=tid)
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
        return t.get("waiting_for") or tr("An approval (see the history for details)")
    if t["status"] == "Waiting for agent":
        return tr("A Service Desk agent to contact you")
    return None


def my_ticket_action(kind, t, text):
    """The employee updates or closes their own ticket with the buttons on the card (no AI involved)."""
    if t["requester_email"] != USER or t["status"] in ("Resolved", "Closed"):
        st.toast(tr("You can only change your own open tickets."))
        return
    if kind == "update":
        db.add_history(t["ticket_id"], f"Update from the user: {text}")
        tools.resume_if_waiting(t)
        db.log_audit(USER, "add_update (button)", {"ticket_id": t["ticket_id"], "update": text},
                     {"updated": t["ticket_id"]}, "user action")
        st.toast(tr("Update added to {id}.", id=t['ticket_id']))
    else:
        db.update_ticket(t["ticket_id"], status="Closed")
        db.clear_waiting(t["ticket_id"])
        db.add_history(t["ticket_id"], f"Closed by the user. Reason: {text or 'not given'}")
        db.log_audit(USER, "close_ticket (button)", {"ticket_id": t["ticket_id"], "reason": text},
                     {"closed": t["ticket_id"]}, "user action")
        st.toast(tr("{id} has been closed.", id=t['ticket_id']))
    st.rerun()


def ticket_card(t, show_requester=False, key_prefix="tk", actions=False):
    """One ticket as a card, with its full history in a fold-out section."""
    with st.container(key=f"{key_prefix}_{t['ticket_id']}"):
        r, res = sla.status(t), sla.resolution(t)
        pr = t["priority"]
        pr_html = f'<span class="p-{pr.lower()}">{e(tr(pr))}</span>' if pr in ("High", "Urgent") else e(tr(pr))
        who = (f'{e(short_name(names.get(t["requester_email"], t["requester_email"])))} '
               f'({e(t.get("department") or "—")}) · ' if show_requester else "")
        st.markdown(f'<div class="tk-top"><span class="tk-id">{e(t["ticket_id"])}</span>'
                    f'<span class="badge {STATUS_CLASS.get(t["status"], "s-new")}">{e(tr(t["status"]))}</span></div>'
                    f'<div class="tk-title">{e(t["title"])}</div>'
                    f'<div class="tk-meta">{who}' + tr("{team} · {pr} priority · Opened {when}", team=e(t["team"]), pr=pr_html, when=e(t["created"])) + '</div>'
                    f'<div><span class="sla sla-{r["state"]}">{e(tr_sla(r["label"]))}</span> '
                    + (f'<span class="sla sla-{res["state"]}">{e(tr_sla(res["label"]))}</span>' if res["label"] else "")
                    + f'</div><div class="sla-t">{e(tr_sla(sla.targets_text(t)))}</div>'
                    + (f'<div class="wait"><b>{tr("Waiting for:")}</b> {e(waiting_text(t))}</div>' if waiting_text(t) else ""),
                    unsafe_allow_html=True)
        if actions and t["status"] not in ("Resolved", "Closed"):
            b1, b2 = st.columns(2)
            with b1.popover(tr("Add update"), icon=":material/edit_note:"):
                with st.form(f"upd_{key_prefix}_{t['ticket_id']}", border=False, clear_on_submit=True):
                    upd = st.text_area(tr("Your update"), placeholder=tr("e.g. My manager approved this by email today."),
                                       height=80)
                    if st.form_submit_button(tr("Add update"), type="primary") and upd.strip():
                        my_ticket_action("update", t, upd.strip())
            with b2.popover(tr("Close ticket"), icon=":material/task_alt:"):
                with st.form(f"cls_{key_prefix}_{t['ticket_id']}", border=False):
                    reason = st.text_input(tr("Reason (optional)"), placeholder=tr("e.g. It works again"))
                    st.caption(tr("Close this ticket if you no longer need help."))
                    if st.form_submit_button(tr("Close ticket"), type="primary"):
                        my_ticket_action("close", t, reason.strip())
        n = len(t["history"])
        with st.expander(tr("History ({n} updates)", n=n)):
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
        "created": ("[{tid}] We've received your request: {title}",
                    "Thank you for contacting the IT Service Desk. We have received your request and it has been "
                    "assigned to the team below."),
        "updated": ("[{tid}] Your update has been added",
                    "We've added your update to the ticket below. The assigned team has been notified."),
        "admin_update": ("[{tid}] Your ticket has been updated",
                         "The IT team has updated your ticket. Here are the latest details."),
        "closed": ("[{tid}] Your ticket has been closed",
                   "As you requested, we have closed your ticket. If the problem comes back, just ask the virtual "
                   "agent and we'll help again."),
        "handoff": ("[{tid}] A member of the IT team will contact you",
                    "You asked to talk to a person. Your conversation has been passed to the Service Desk, "
                    "and someone will contact you soon. You won't need to repeat anything."),
    }[kind]
    subject, intro = tr(subject, tid=tid, title=title), tr(intro)       # the email in the user's language
    last = t["history"][-1]["text"] if t["history"] else ""
    rows = [("Ticket", tid), ("Title", title), ("Status", tr(t["status"])), ("Priority", tr(t["priority"])),
            ("Assigned to", t["team"]), ("First response by", f'{r["due"]} (JST)'),
            ("Resolve by", tr("Paused while waiting for approval") if res["state"] == "paused"
             else f'{res["due"]} (JST)' if res["due"] else "—"),
            ("Service targets", tr_sla(sla.targets_text(t)))]
    if kind in ("updated", "admin_update", "closed"):
        rows.append(("Latest update", last[:200]))
    table = "".join(f"<tr><td>{e(tr(k))}</td><td>{e(str(v))}</td></tr>" for k, v in rows)
    desk = f'TestBank {tr("IT Service Desk")}'
    with st.expander(tr("Email preview · to {to}", to=t['requester_email'])):
        st.markdown(f'<div class="mail"><div class="mail-h"><span class="mail-tag">{tr("PREVIEW ONLY · NOT SENT")}</span><br>'
                    f'<b>{tr("From:")}</b> {e(desk)} &lt;it-servicedesk@testbank.com&gt;<br>'
                    f'<b>{tr("To:")}</b> {e(person["name"])} &lt;{e(t["requester_email"])}&gt;<br>'
                    f'<b>{tr("Subject:")}</b> {e(subject)}</div>'
                    f'<div class="mail-b">{e(tr("Dear {name},", name=first))}<br><br>{e(intro)}<table>{table}</table>'
                    + e(tr("You can check this ticket at any time in the TestBank IT Service Desk.")) + '<br><br>'
                    + e(tr("Kind regards,")) + f'<br>{e(desk)}</div>'
                    '<div class="mail-f">' + e(tr("This is an automated message. Please do not reply to this email. "
                                                 "Never share your password with anyone, including IT.")) + '</div></div>',
                    unsafe_allow_html=True)


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


@st.dialog(tr("How the TestBank virtual agent works"), width="large")
def how_it_works():
    test, test_when = latest_test_result()
    totals = db.usage_totals()
    calls = totals.get("chat", {}).get("calls", 0)
    per_call = f"≈ ₹{agent.estimated_cost_usd(totals) / calls * agent.USD_TO_INR:.2f}" if calls else "≈ ₹0.2"
    overview, safety, limits = st.tabs([tr("How it works"), tr("Safety rules"), tr("Limits of this demo")])

    with overview:
        box = lambda title, sub, cls="": f'<div class="hw-box {cls}"><b>{tr(title)}</b><span>{tr(sub)}</span></div>'
        st.markdown(
            '<div class="hw-flow">'
            + box("Employee", "asks in English or 日本語")
            + '<div class="hw-arrow">→</div>'
            + box("AI agent", "Gemini · understands &amp; decides", "hw-ai")
            + '<div class="hw-arrow">→</div>'
            + box("Tools", "our software · does the work", "hw-tools")
            + '<div class="hw-arrow">→</div>'
            + box("Tickets &amp; documents", "database · IT policies")
            + '</div><div class="hw-loop">' + tr("Results go back to the AI, which decides the next step · "
                                                 "the employee confirms every change") + '</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.markdown(tr("##### What the AI does\n"
                       "- Understands requests in plain English or Japanese, and reads screenshots\n"
                       "- Finds answers in IT policies and the self-help guide, with sources\n"
                       "- Decides the next step: look up, offer self-help, or prepare a ticket\n"
                       "- Picks the right team and priority, and writes clear tickets"))
        c2.markdown(tr("##### What normal software does\n"
                       "- Creates, updates and closes tickets, only after confirmation\n"
                       "- Checks who may see and change what\n"
                       "- Response-time targets, overdue alerts, email previews\n"
                       "- Audit log, feedback, self-help and cost tracking"))
        tiles = [("Automatic test set", test, test_when), ("Cost per AI request", per_call, "estimate"),
                 ("AI model", "Google Gemini", "flash")]
        st.markdown('<div class="kpis" style="grid-template-columns:repeat(3,1fr)">' + "".join(
            f'<div class="kpi"><div class="kpi-v">{e(v)}</div><div class="kpi-l">{e(tr(l))} · {e(tr(n))}</div></div>'
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
                f'{e(org.label(USER))}<br>{e(me["location"])}</div></div></div>', unsafe_allow_html=True)
    st.write("")
    if not is_management and st.button(tr("New conversation"), icon=":material/add:", type="primary", width="stretch", key="new_side"):
        new_conversation()
        st.rerun()
    if GOOGLE:
        st.button(tr("Sign out"), width="stretch", on_click=st.logout)
    else:
        listed = [p["email"] for p in tools.EMPLOYEES.values() if p.get("listed", True) or p["email"] == USER]
        chosen = st.selectbox(tr("Switch user (demo only)"), listed, index=listed.index(USER),
                              format_func=lambda m: names[m])
        if chosen != USER:
            st.session_state.user = chosen
            new_conversation()
            st.rerun()
    if is_admin and st.button(tr("Reset demo data"), icon=":material/restart_alt:", width="stretch",
                              help="Deletes all new tickets, logs and feedback, and restores the starting tickets."):
        db.reset()
        new_conversation()
        st.rerun()
    st.write("")
    if st.button(tr("How it works & safety"), icon=":material/verified_user:", width="stretch", key="how"):
        how_it_works()
    st.markdown(f'<div class="side-foot">{tr("Demo environment.")}<br>'
                f'{tr("Actions only change demo tickets.")}<br>'
                + (tr("Conversations are saved for {days} days for quality and audit.", days=RETENTION_DAYS)
                   if HISTORY_ON else tr("Conversations are not saved.")) + '</div>', unsafe_allow_html=True)

# ---------- Top bar ----------
def go_sharepoint(view=None):
    """Button callback: open the admin's SharePoint page (optionally on a given List view)."""
    st.session_state.nav = "SharePoint"
    if view:
        st.session_state.sp_view = view


with st.container(key="tbhead"):
    h1, h2, h3, hb, h4 = st.columns([3.4, 1.3, 1.3, 0.8, 2.0], vertical_alignment="center", gap="small")
    h1.markdown(f'<div class="tb-brand"><div class="tb-logo">TB</div>'
                f'<div class="tb-title">{BRAND}<span>{tr("IT Service Desk")}</span></div></div>', unsafe_allow_html=True)
    h2.markdown(f'<div style="text-align:right"><span class="tb-env">{tr("Demo environment")}</span></div>',
                unsafe_allow_html=True)
    with h3, st.container(key="langbox"):        # language switch: English / 日本語
        st.selectbox("Language", ["en", "ja"], key="lang", label_visibility="collapsed",
                     format_func=lambda x: "English" if x == "en" else "日本語")
    with hb, st.container(key="bell"):              # in-app notifications (nothing is sent outside the app)
        unread = catalog.unread_count(USER)
        with st.popover(str(unread) if unread else "", icon=":material/notifications:", type="primary" if unread else "secondary"):
            notes = catalog.list_notifications(USER)
            if not notes:
                st.caption(tr("No notifications yet."))
            for x in notes:
                p_ = x["params"]
                st.markdown(f'<div class="note-item{" note-new" if not x["read"] else ""}"><span>{e(x["at"][5:])}</span>'
                            f'{e(tr(x["template"], **p_))}</div>', unsafe_allow_html=True)
            if unread and st.button(tr("Mark all as read"), key="bell_read", width="stretch"):
                catalog.mark_all_read(USER)
                st.rerun()
    h4.markdown(f'<div class="tb-user"><div class="tb-avatar">{e(initials(me["name"]))}</div><div>'
                f'<div class="tb-uname">{e(short_name(me["name"]))}</div>'
                f'<div class="tb-urole">{e(role_label)} · {e(org.info(USER)["department"])}'
                f'{" / " + e(org.info(USER)["team"]) if org.info(USER)["team"] != org.info(USER)["department"] else ""}'
                '</div></div></div>',
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
                st.markdown(f'<div class="live-who">{e(who)} · {tr("Service Desk")}</div>', unsafe_allow_html=True)
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
                                     "text": tr("You're back with the virtual agent. Ask me anything else.")})
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
        st.markdown('<div class="live-bar live-wait"><span class="live-dot"></span>' + tr("Waiting for a Service Desk "
                    "agent · you can keep typing, your messages will be passed on") + '</div>', unsafe_allow_html=True)
    else:
        agent_name = short_name(names.get(lc["agent"], lc["agent"] or "IT agent"))
        st.markdown('<div class="live-bar live-on"><span class="live-dot"></span>' + tr("You are chatting with {name} "
                    "(Service Desk) · the AI assistant is paused", name=e(agent_name)) + '</div>', unsafe_allow_html=True)



SP_ACTION = {"created": "New item", "handoff": "New item", "updated": "Item updated", "admin_update": "Item updated",
             "closed": "Item updated (Closed)"}


def go_kb():
    st.session_state.nav = "Knowledge base"


def kb_draft_box(article_id, msg_id):
    a = kb.get(article_id)
    if not a:
        return
    c1, c2 = st.columns([3.2, 1], vertical_alignment="center")
    c1.markdown(f'<div class="sp-saved kb-box"><span class="sp-ico kb-ico">KB</span><div><b>Knowledge base draft '
                f'{e(a["id"])}</b> · {e(a["title"])}<br><span>Written by the AI from ticket {e(a["source_ticket"])} · '
                f'{e(a["status"])}</span></div></div>', unsafe_allow_html=True)
    if is_admin:
        c2.button("Review", key=f"kbr_{msg_id}_{article_id}", icon=":material/rate_review:", on_click=go_kb,
                  width="stretch")


def sharepoint_saved(mail, msg_id):
    """Shows where the ticket change went: the SharePoint List item."""
    t = db.get_ticket(mail["ticket_id"])
    if not t or mail["kind"] not in SP_ACTION:
        return
    c1, c2 = st.columns([3.2, 1], vertical_alignment="center")
    c1.markdown(f'<div class="sp-saved"><span class="sp-ico">SP</span><div><b>Saved to SharePoint</b> · '
                f'{e(sharepoint.LIST_NAME)} List · item {e(sharepoint.item_id(t))}<br><span>{SP_ACTION[mail["kind"]]} · '
                f'{e(t["ticket_id"])} · {e(t["status"])} · {e(t["team"])}'
                f'{"" if sharepoint.is_live() else " · simulated"}</span></div></div>', unsafe_allow_html=True)
    if is_admin:
        c2.button("View in List", key=f"spv_{msg_id}_{mail['ticket_id']}", icon=":material/list_alt:",
                  on_click=go_sharepoint, args=("Created today",), width="stretch")


def incident_banner():
    for inc in incidents.active():
        st.markdown(f'<div class="inc-banner"><span class="live-dot"></span><div><b>{tr("Known issue")} · {e(inc["id"])}: '
                    f'{e(inc["title"])}</b><br><span>{e(inc["message"])} · {tr("since")} {e(inc["created_at"][11:])}'
                    f'</span></div></div>', unsafe_allow_html=True)


def render_chat():
    incident_banner()
    clicked = None
    if st.session_state.display or st.session_state.pending:
        _, b1, b2 = st.columns([1.6, 1.4, 1])
        done = st.session_state.get("handed_off", False)
        if b1.button(tr("Handed over") if done else tr("Talk to a person"), icon=":material/support_agent:", width="stretch", key="human",
                     disabled=done, help=tr("Hand this conversation to the Service Desk team")):
            talk_to_person()
            st.rerun()
        if b2.button(tr("Home"), icon=":material/home:", width="stretch", key="new_top", help=tr("Start a new conversation. Your tickets are kept.")):
            new_conversation()
            st.rerun()
    else:
        hour = db.now().hour
        greet = tr("Good morning") if hour < 12 else tr("Good afternoon") if hour < 18 else tr("Good evening")
        caps = ["Policy answers with sources", "Ticket status", "Raise & update tickets", "You confirm every action"]
        st.markdown(f'<div class="card welcome"><h3>'
                    f'{e(tr("{greet}, {name}", greet=greet, name=short_name(me["name"]).split()[0]))}</h3>'
                    '<p>' + e(tr("I'm your IT virtual agent. Ask me about IT policies, check on your tickets, or tell me "
                                 "about a problem and I'll raise a ticket for you. I always ask before I change anything."))
                    + '</p>'
                    '<div class="caps">' + "".join(f'<span class="cap">{e(tr(c))}</span>' for c in caps)
                    + (f'<span class="cap">{e(tr("Chats are saved for {days} days", days=RETENTION_DAYS))}</span>'
                       if HISTORY_ON else "")
                    + '</div></div>', unsafe_allow_html=True)
        top = [] if is_admin else trending.most_asked(LANG)       # employees: what colleagues ask most this week
        if len(top) >= 3:
            st.markdown(f'<div class="section-title">{tr("Most asked this week")}</div>', unsafe_allow_html=True)
            examples = [q for q, _ in top]
            helps = [tr("Asked by {n} people this week", n=n) for _, n in top]
        else:                                                     # not enough data yet: fixed examples
            st.markdown(f'<div class="section-title">{tr("Suggested")}</div>', unsafe_allow_html=True)
            examples = EXAMPLES.get(LANG, EXAMPLES["en"])["admin" if is_admin else "employee"]
            helps = [None] * len(examples)
        with st.container(key="chips"):
            cols = st.columns(2)
            for i, ex in enumerate(examples):
                if cols[i % 2].button(ex, key=f"ex{i}", width="stretch", help=helps[i]):
                    clicked = ex

    live = live_status()                              # first, so a just-ended live chat shows up in order
    self_help_click = None
    offer_click = None
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
                    st.image(m["image"], width=320, caption=tr("Attached screenshot"))
                if m["role"] == "assistant":
                    if m.get("sources"):
                        st.markdown('<div class="srcs">' + "".join(f'<span class="src">{e(s)}</span>'
                                    for s in m["sources"]) + "</div>", unsafe_allow_html=True)
                    for article_id in m.get("kb", []):
                        kb_draft_box(article_id, m["id"])
                    for mail in m.get("emails", []):
                        email_preview(mail["kind"], mail["ticket_id"])
                    if m.get("steps") and is_admin:            # employees just see the answer
                        n = len(m["steps"])
                        with st.expander(tr("How I worked this out ({n} steps)", n=n)):
                            st.markdown('<div class="steps">' + "<br>".join(e(s) for s in m["steps"]) + "</div>",
                                        unsafe_allow_html=True)
                    if m.get("self_help") == "ask" and m["id"] == last_assistant and not st.session_state.pending:
                        with st.container(key=f"sh_{m['id']}"):
                            st.markdown(f'<div class="sh-q">{tr("Did this solve your problem?")}</div>', unsafe_allow_html=True)
                            y, n_, _ = st.columns([1.2, 1.4, 1])
                            if y.button(tr("Yes, solved"), key=f"shy_{m['id']}", type="primary", width="stretch"):
                                self_help_click = (m, True)
                            if n_.button(tr("No, raise a ticket"), key=f"shn_{m['id']}", width="stretch"):
                                self_help_click = (m, False)
                    elif m.get("offer") == "ask" and m["id"] == last_assistant and not st.session_state.pending:
                        with st.container(key=f"of_{m['id']}"):
                            y, h_, n_ = st.columns([1.3, 1.3, 1])
                            if y.button(tr("Yes, raise a ticket"), key=f"ofy_{m['id']}", type="primary",
                                        icon=":material/confirmation_number:", width="stretch"):
                                offer_click = (m, "yes")
                            if h_.button(tr("Talk to a person"), key=f"ofp_{m['id']}",
                                         icon=":material/support_agent:", width="stretch",
                                         disabled=st.session_state.get("handed_off", False)):
                                offer_click = (m, "person")
                            if n_.button(tr("No, thanks"), key=f"ofn_{m['id']}", width="stretch"):
                                offer_click = (m, "no")
                    elif m.get("self_help") == "solved":
                        st.markdown(f'<div class="sh-done">{tr("Solved with self-help · no ticket needed")}</div>',
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
            "create_ticket": (tr("Please confirm your new ticket"), tr("Submit ticket")),
            "add_comment": (tr("Please confirm this update to {id}", id=a.get('ticket_id', '')), tr("Add update")),
            "update_ticket": (tr("Please confirm the change to {id}", id=a.get('ticket_id', '')), tr("Save changes")),
            "close_ticket": (tr("Please confirm: close ticket {id}", id=a.get('ticket_id', '')), tr("Close ticket")),
            "request_item": (tr("Please confirm your request"), tr("Send request")),
        }.get(p["name"], (tr("Please confirm: {name}", name=p['name']), tr("Confirm")))
        with st.container(key="approval"):
            st.markdown(f'<div class="ap-head">{e(heading)}</div>'
                        '<div class="ap-sub">' + e(tr("Check the details and change anything that's wrong. "
                                                     "Nothing happens until you confirm.")) + '</div>',
                        unsafe_allow_html=True)
            with st.form("confirm", border=False):
                if p["name"] == "create_ticket":
                    title = st.text_input(tr("Title"), a.get("title", ""))
                    desc = st.text_area(tr("Details"), a.get("description", ""), height=80)
                    c1, c2, c3 = st.columns(3)
                    pr = c1.selectbox(tr("Priority"), tools.PRIORITIES, index=pick(tools.PRIORITIES, a.get("priority")), format_func=tr)
                    team = c2.selectbox(tr("Assign to"), tools.TEAMS, index=pick(tools.TEAMS, a.get("team")))
                    cat = c3.text_input(tr("Category"), a.get("category", ""))
                    final = {"title": title, "description": desc, "category": cat, "priority": pr, "team": team}
                elif p["name"] == "request_item":
                    items = list(catalog.CATALOG)
                    found = catalog.find_item(a.get("item")) or items[0]
                    it = st.selectbox(tr("Item"), items, index=items.index(found),
                                      format_func=lambda x: f'{x} · {catalog.CATALOG[x]["cost"]}')
                    det = st.text_input(tr("Details"), a.get("details", ""))
                    why = st.text_area(tr("Business reason"), a.get("reason", ""), height=70)
                    st.caption(tr("Requested by {name} · {unit}. The cost is charged to this cost center.",
                                  name=short_name(me["name"]), unit=org.label(USER)))
                    mgr = catalog.manager_of(USER, tools.EMPLOYEES)
                    if catalog.CATALOG[it]["approval"] and mgr:
                        st.caption(tr("Needs approval from {name}. You will get a notification when they decide.",
                                      name=short_name(names.get(mgr, mgr))))
                    else:
                        st.caption(tr("No approval needed: it goes straight to the {team}.",
                                      team=catalog.CATALOG[it]["team"]))
                    final = {"item": it, "details": det, "reason": why}
                elif p["name"] == "add_comment":
                    comment = st.text_area(tr("Update"), a.get("comment", ""), height=80)
                    final = {"ticket_id": a.get("ticket_id", ""), "comment": comment}
                elif p["name"] == "close_ticket":
                    reason = st.text_area(tr("Reason"), a.get("reason", ""), height=70)
                    final = {"ticket_id": a.get("ticket_id", ""), "reason": reason}
                elif p["name"] == "update_ticket":
                    keep = "(no change)"                 # shown as （変更なし） in Japanese (format_func)
                    c1, c2, c3 = st.columns(3)
                    stt = c1.selectbox(tr("Status"), [keep] + tools.STATUSES, index=pick([keep] + tools.STATUSES, a.get("status")), format_func=tr)
                    tm = c2.selectbox(tr("Team"), [keep] + tools.TEAMS, index=pick([keep] + tools.TEAMS, a.get("team")), format_func=tr)
                    prr = c3.selectbox(tr("Priority"), [keep] + tools.PRIORITIES, index=pick([keep] + tools.PRIORITIES, a.get("priority")), format_func=tr)
                    note = st.text_area(tr("Note"), a.get("note", ""), height=70)
                    final = {"ticket_id": a.get("ticket_id", ""), "status": "" if stt == keep else stt,
                             "team": "" if tm == keep else tm, "priority": "" if prr == keep else prr, "note": note}
                else:
                    st.json(a)
                    final = dict(a)
                s, c, _ = st.columns([1.3, 1, 2])
                submitted = s.form_submit_button(button, type="primary", width="stretch")
                cancelled = c.form_submit_button(tr("Cancel"), width="stretch")
            if submitted:
                decide(True, final)
                st.rerun()
            if cancelled:
                decide(False)
                st.rerun()

    if self_help_click:
        self_help_answer(*self_help_click)
        st.rerun()
    if offer_click:
        ticket_offer_answer(*offer_click)
        st.rerun()

    if live:                                          # talking to a person: the AI is paused
        sent = st.chat_input(tr("Message the Service Desk…"), key="live_input")
        if sent:
            db.add_live_message(live["ticket_id"], "user", USER, sent)
            st.rerun()
        return
    sent = st.chat_input(tr("Ask about IT policies, your tickets, or describe a problem… (you can attach a screenshot)"),
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


def approval_cards():
    """Requests waiting for this person's decision (they are someone's manager). No AI involved."""
    waiting = catalog.pending_for(USER)
    if not waiting:
        return
    st.markdown(f'<div class="section-title">{tr("Approvals waiting for you · {n}", n=len(waiting))}</div>',
                unsafe_allow_html=True)
    for a in waiting:
        info = catalog.CATALOG.get(a["item"], {})
        with st.container(key=f"apr_{a['ticket_id']}"):
            st.markdown(f'<div class="tk-top"><span class="tk-id">{e(a["ticket_id"])}</span>'
                        f'<span class="badge s-waiting">{tr("Waiting for approval")}</span></div>'
                        f'<div class="tk-title">{e(a["item"])} · {e(info.get("cost", ""))}</div>'
                        f'<div class="tk-meta">{e(short_name(names.get(a["requester"], a["requester"])))} · '
                        f'{e(org.label(a["requester"]))} · {e(a["created_at"])}</div>'
                        f'<div class="wait"><b>{tr("Reason:")}</b> {e(a["reason"] or "—")}</div>', unsafe_allow_html=True)
            comment = st.text_input(tr("Comment (optional)"), key=f"aprc_{a['ticket_id']}")
            y, n_ = st.columns(2)
            choice = None
            if y.button(tr("Approve"), key=f"apry_{a['ticket_id']}", type="primary", icon=":material/check:",
                        width="stretch"):
                choice = True
            if n_.button(tr("Reject"), key=f"aprn_{a['ticket_id']}", icon=":material/close:", width="stretch"):
                choice = False
            if choice is not None:
                catalog.decide(a["ticket_id"], USER, choice, comment.strip(), short_name(me["name"]))
                st.toast(tr("{id} approved.", id=a["ticket_id"]) if choice else tr("{id} rejected.", id=a["ticket_id"]))
                st.rerun()


def render_my_tickets():
    approval_cards()
    mine = db.list_tickets(USER)
    current = [t for t in mine if t["status"] not in ("Resolved", "Closed")]
    past = [t for t in mine if t["status"] in ("Resolved", "Closed")]
    st.markdown(f'<div class="section-title">{tr("My open tickets · {n}", n=len(current))}</div>', unsafe_allow_html=True)
    if not current:
        st.markdown('<div class="card" style="color:#6B7A8C;font-size:14px">' + e(tr("You have no open tickets. "
                    "Describe a problem in the chat and the agent can help or raise one for you.")) + '</div>',
                    unsafe_allow_html=True)
    for t in reversed(current):
        ticket_card(t, actions=True)
    if past:
        with st.expander(tr("Past tickets ({n})", n=len(past))):
            for t in reversed(past):
                ticket_card(t, key_prefix="tkpast")


def needs_attention_cards(limit=None):
    open_t = [t for t in db.list_tickets() if t["status"] not in ("Resolved", "Closed")]
    hot = [t for t in open_t if t["priority"] in ("High", "Urgent")]
    handoffs = [t for t in open_t if t["status"] == "Waiting for agent"]
    overdue = [t for t in open_t if sla.is_overdue(t)]
    st.markdown(kpis([(tr("Open tickets"), len(open_t)), (tr("Overdue"), len(overdue)),
                      (tr("High / Urgent"), len(hot)), (tr("Waiting for a person"), len(handoffs))]),
                unsafe_allow_html=True)
    attention = [t for t in open_t if t in hot or t in handoffs or t in overdue]
    attention.sort(key=lambda t: (t["status"] != "Waiting for agent", not sla.is_overdue(t),
                                  {"Urgent": 0, "High": 1}.get(t["priority"], 2)))
    st.markdown(f'<div class="section-title">{tr("Needs attention · {n}", n=len(attention))}</div>', unsafe_allow_html=True)
    if not attention:
        st.caption(tr("Nothing urgent right now."))
    for t in attention[:limit]:
        ticket_card(t, show_requester=True, key_prefix="tkatt")
    if limit and len(attention) > limit:
        st.caption(tr("+ {n} more on the Tickets page.", n=len(attention) - limit))



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
    q = f5.text_input("Search", placeholder="ID, title, person, department or cost center", key="flt_q")
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
                | df.Requester.str.lower().str.contains(ql, regex=False)
                | df.Department.str.lower().str.contains(ql, regex=False)
                | df["Dept team"].str.lower().str.contains(ql, regex=False)
                | df["Cost center"].str.lower().str.contains(ql, regex=False)]
    df = df.sort_values("created", ascending=False)
    view = pd.DataFrame({
        "ID": df.ID, "Title": df.Title, "Requester": df.Requester,
        "Department": [d if t in ("", d) else f"{d} / {t}" for d, t in zip(df.Department, df["Dept team"])],
        "Cost center": df["Cost center"], "Team": df.Team, "Priority": df.Priority,
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
                      (f"IT time saved (est. {MINUTES_PER_TICKET()} min/ticket)", f"{solved * MINUTES_PER_TICKET() / 60:.0f} hours")]),
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

    ts = db.timing_stats(last=50)                         # how long employees waited for each answer
    st.markdown('<div class="section-title" style="margin-top:14px">Answer speed · last 50 answers</div>' +
                kpis(wide=True, items=[("Typical answer time (median)", f"{ts['median']:.1f} s" if ts else "–"),
                      ("Fastest", f"{ts['fastest']:.1f} s" if ts else "–"),
                      ("Slowest", f"{ts['slowest']:.1f} s" if ts else "–"),
                      ("Answers measured", ts["count"] if ts else 0)]), unsafe_allow_html=True)
    st.markdown(f'<div class="note">Model: {e(agent.CHAT_MODEL)} · thinking level: {e(agent.THINKING or "default")}. '
                'Time from pressing Enter to the answer on screen. The free Streamlit Cloud server is in the USA, '
                'so answers from Tokyo take a little longer than on a company server in Japan.</div>',
                unsafe_allow_html=True)

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
                    f'<span class="badge {STATUS_CLASS.get(t["status"], "s-new")}">{e(tr(t["status"]))}</span></div>'
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
    if solved and note:                                # knowledge loop: the fix becomes a draft KB article
        draft = kb.create_draft(tid, note, created_by=me_name)
        if draft:
            st.toast(f"Draft knowledge base article {draft} created. Review it under Knowledge base.")
    db.log_audit(USER, "end_live_chat", {"ticket_id": tid, "solved": solved, "note": note},
                 {"ended": tid}, "user action")
    st.session_state.live_open = None


@st.fragment(run_every=5)
def live_alert(current_page):
    """A notice on every admin page when someone is waiting for a person."""
    if current_page != "Incidents":
        for g in incidents.detect()[:1]:
            a, b = st.columns([5, 1], vertical_alignment="center")
            a.markdown(f'<div class="live-alert"><span class="live-dot"></span>Possible outage: {g["people"]} people '
                       f'reported {e(g["category"])} problems to the {e(g["team"])} in the last {g["window"]} min</div>',
                       unsafe_allow_html=True)
            if b.button("Review", key="go_inc", type="primary", width="stretch", icon=":material/warning:"):
                st.session_state.goto_inc = True
                st.rerun(scope="app")
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


def page_sharepoint():
    live = sharepoint.is_live()
    st.markdown(f'<div class="dash-title">SharePoint integration</div><div class="dash-sub">The agent reads and writes '
                f'tickets as items of the SharePoint List “{e(sharepoint.LIST_NAME)}” through Microsoft Graph. '
                f'Mode: <b>{e(sharepoint.mode_label())}</b>'
                + ('' if live else ' · requests are recorded here, not sent') + '</div>', unsafe_allow_html=True)
    arrow = '<span class="sp-arrow">→</span>'
    st.markdown('<div class="card"><div class="sp-flow">'
                '<div class="lbl">Today</div><div class="sp-row"><span class="sp-step">Employee</span>' + arrow +
                '<span class="sp-step">Email, phone or portal</span>' + arrow +
                '<span class="sp-step">IT staff type it into the List</span>' + arrow +
                '<span class="sp-step list">SharePoint List</span>' + arrow +
                '<span class="sp-step">IT team works the item</span></div>'
                '<div class="lbl">With the agent</div><div class="sp-row"><span class="sp-step">Employee</span>' + arrow +
                '<span class="sp-step ai">AI agent: self-help first, employee confirms</span>' + arrow +
                '<span class="sp-step list">SharePoint List (Graph API)</span>' + arrow +
                '<span class="sp-step">IT team works the item, as today</span></div></div>'
                '<div class="dash-n" style="margin:0">Nothing changes for the IT team: the agent writes the same '
                'List items they already use, with the details filled in correctly.</div></div>',
                unsafe_allow_html=True)
    t_list, t_log, t_lib, t_conn = st.tabs(["IT Helpdesk List", "Graph API log", "Document library",
                                             "Connection & column mapping"])
    with t_list:
        site = sharepoint.SITE_URL.split("//")[-1]
        st.markdown(f'<div class="sp-crumb">{e(site)} &nbsp;›&nbsp; Lists &nbsp;›&nbsp; '
                    f'<b>{e(sharepoint.LIST_NAME)}</b></div>', unsafe_allow_html=True)
        tickets = db.list_tickets()
        f1, f2, f3 = st.columns([2.2, 1.4, 1.6], vertical_alignment="bottom")
        st.session_state.setdefault("sp_view", "Open items")
        view = f1.segmented_control("View", ["All items", "Open items", "Created today"], key="sp_view") or "Open items"
        by_agent = {r["ticket_id"] for r in db.list_graph(100000) if r["method"] == "POST" and "Updates" not in r["path"]}
        team = f2.selectbox("Assigned team", ["All teams"] + tools.TEAMS, key="sp_team")
        q = f3.text_input("Search this list", key="sp_q", placeholder="Title, ticket or person")
        today = db.now().date().isoformat()
        rows = []
        for t in sorted(tickets, key=lambda x: x["created_at"] or "", reverse=True):
            if view == "Open items" and t["status"] in ("Resolved", "Closed"):
                continue
            if view == "Created today" and t["created"] != today:
                continue
            if team != "All teams" and t["team"] != team:
                continue
            who = short_name(names.get(t["requester_email"], t["requester_email"]))
            if q and q.lower() not in f'{t["ticket_id"]} {t["title"]} {who}'.lower():
                continue
            modified = t["history"][-1]["at"] if t["history"] else t["created"]
            rows.append({"Added by": "AI agent" if t["ticket_id"] in by_agent else "",
                         "ID": int(sharepoint.item_id(t)) if str(sharepoint.item_id(t)).isdigit() else sharepoint.item_id(t),
                         "Ticket ID": t["ticket_id"], "Title": t["title"], "Status": t["status"],
                         "Priority": t["priority"], "Assigned team": t["team"], "Requested by": who,
                         "Category": t["category"], "Channel": t.get("channel") or "Portal",
                         "Created": (t["created_at"] or t["created"])[:16].replace("T", " "), "Modified": modified})
        st.caption(f"{len(rows)} items" + ("" if live else " · simulated copy of the SharePoint List, same columns"))
        df = pd.DataFrame(rows)
        new = int((df["Added by"] != "").sum()) if len(df) else 0
        if new:
            st.markdown(f'<div class="sp-saved" style="margin-bottom:8px"><span class="sp-ico">SP</span><div>'
                        f'<b>{new} item{"s" if new != 1 else ""} added by the AI agent</b> since the demo was reset '
                        '<span>· highlighted below</span></div></div>', unsafe_allow_html=True)
        styled = df.style.apply(lambda r: ["background-color:#EAF3FB;font-weight:600" if r["Added by"] else ""
                                           for _ in r], axis=1) if len(df) else df
        st.dataframe(styled, hide_index=True, width="stretch", height=min(40 + 35 * max(len(rows), 1), 520),
                     column_config={"ID": st.column_config.NumberColumn(format="%d", width="small"),
                                    "Added by": st.column_config.TextColumn(width="small")})
    with t_log:
        log = db.list_graph()
        st.markdown(f'<div class="dash-n">Every ticket change becomes a Microsoft Graph request to SharePoint. '
                    f'{"These requests were sent." if live else "Simulated mode: these are the exact requests that would be sent; switching to live mode sends them."}'
                    '</div>', unsafe_allow_html=True)
        if not log:
            st.markdown('<div class="card" style="font-size:13.5px;color:#5A6575">No requests yet. Create a ticket in the '
                        'chat (for example “My keyboard stopped working, please raise a ticket”) and it appears here.</div>',
                        unsafe_allow_html=True)
        else:
            view = pd.DataFrame([{"Time": r["at"][11:], "Method": r["method"],
                                  "Request": unquote("/" + r["path"].split("/lists/")[-1]) if "/lists/" in r["path"] else r["path"],
                                  "Ticket": r["ticket_id"] or "", "Result": r["outcome"]} for r in log])
            st.dataframe(view, hide_index=True, width="stretch", height=min(40 + 35 * len(view), 330))
            pick = st.selectbox("Show the full request", range(len(log)), key="sp_pick",
                                format_func=lambda i: f'{log[i]["at"][11:]} · {log[i]["method"]} · {log[i]["ticket_id"] or ""}')
            r = log[pick]
            body = json.dumps(json.loads(r["body"]), indent=2, ensure_ascii=False) if r["body"] else ""
            st.code(f'{r["method"]} {sharepoint.GRAPH}{r["path"]}\nAuthorization: Bearer <token from Microsoft Entra ID>\n'
                    f'Content-Type: application/json\n\n{body}'.rstrip(), language="http")
    with t_lib:
        st.markdown(f'<div class="sp-crumb">{e(site)} &nbsp;›&nbsp; <b>{e(sharepoint.LIBRARY_NAME)}</b> '
                    '(document library)</div>', unsafe_allow_html=True)
        counts = {}
        for c in tools._INDEX["chunks"]:
            counts.setdefault(c["file"], set()).add(c["page"])
        lib = pd.DataFrame([{"Name": f, "Type": "PDF", "Pages indexed": len(p),
                             "Passages": sum(1 for c in tools._INDEX["chunks"] if c["file"] == f),
                             "Used by the agent for": "Self-help steps" if "Self_Help" in f else "Policy answers"}
                            for f, p in sorted(counts.items())])
        st.dataframe(lib, hide_index=True, width="stretch")
        st.markdown('<div class="dash-n">The agent answers only from these documents and cites the file and page. '
                    'With live SharePoint, the search index is rebuilt automatically when a document in the library '
                    'is added or changed (Microsoft Graph change notifications).</div>', unsafe_allow_html=True)
    with t_conn:
        c1, c2 = st.columns([1, 1.3], gap="large")
        with c1:
            st.markdown('<div class="section-title">Connection</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card" style="font-size:13.5px;line-height:1.9">'
                        f'<b>Mode:</b> {e(sharepoint.mode_label())}<br>'
                        f'<b>Site:</b> {e(sharepoint.SITE_URL)}<br>'
                        f'<b>Tickets List:</b> {e(sharepoint.LIST_NAME)}<br>'
                        f'<b>Updates List:</b> {e(sharepoint.UPDATES_LIST)}<br>'
                        f'<b>Document library:</b> {e(sharepoint.LIBRARY_NAME)}<br>'
                        f'<b>Sign-in for the app:</b> Microsoft Entra ID app registration '
                        f'({"configured" if sharepoint.CLIENT_ID else "not configured in this demo"})<br>'
                        f'<b>Graph permission:</b> Sites.Selected (only this one site)</div>', unsafe_allow_html=True)
            if live and st.button("Test the SharePoint connection", icon=":material/lan:"):
                ok, msg = sharepoint.check_connection()
                (st.success if ok else st.error)(msg)
            st.markdown('<div class="section-title" style="margin-top:14px">Going live takes configuration, not code</div>'
                        '<div class="hw-intro">1. Create the two Lists with the columns on the right.<br>'
                        '2. Register the app in Microsoft Entra ID and grant it access to this site only.<br>'
                        '3. Put the site, list names and app ID in the settings and set SHAREPOINT_MODE to graph.<br>'
                        '4. Run the test set, then pilot with one team.</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="section-title">Column mapping: agent field → SharePoint column</div>',
                        unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{"Agent field": f, "SharePoint column": d, "Internal name": i, "Type": ty}
                                       for f, d, i, ty in sharepoint.COLUMNS]), hide_index=True, width="stretch",
                         height=40 + 35 * len(sharepoint.COLUMNS))


def page_kb():
    st.markdown('<div class="dash-title">Knowledge base</div><div class="dash-sub">Fixes from resolved tickets become '
                'articles the agent suggests to the next person with the same problem. IT approves every article '
                'first.</div>', unsafe_allow_html=True)
    arrow = '<span class="sp-arrow">→</span>'
    st.markdown('<div class="card"><div class="sp-row">'
                '<span class="sp-step">1. IT resolves a ticket and notes the fix</span>' + arrow +
                '<span class="sp-step ai">2. AI drafts a KB article</span>' + arrow +
                '<span class="sp-step list">3. IT reviews and approves</span>' + arrow +
                '<span class="sp-step ai">4. Agent suggests it as self-help</span>' + arrow +
                '<span class="sp-step">5. No repeat ticket</span></div></div>', unsafe_allow_html=True)
    approved, drafts = kb.list_articles(kb.STATUS_APPROVED), kb.list_articles(kb.STATUS_DRAFT)
    st.markdown(kpis(wide=True, items=[("Approved articles", len(approved)), ("Waiting for review", len(drafts)),
                                       ("Times suggested by the agent", sum(a["suggested"] for a in approved)),
                                       ("Solved without a ticket", sum(a["solved"] for a in approved))]),
                unsafe_allow_html=True)

    st.markdown(f'<div class="section-title">Waiting for review · {len(drafts)}</div>', unsafe_allow_html=True)
    if not drafts:
        st.caption("No drafts. When a ticket is resolved with a note on how it was fixed, the AI drafts an article "
                   "here. You can also draft one from a resolved ticket below.")
    for a in drafts:
        t = db.get_ticket(a["source_ticket"]) or {"title": "", "team": ""}
        with st.container(key=f"kbd_{a['id']}"):
            st.markdown(f'<div class="tk-top"><span class="tk-id">{e(a["id"])} · draft from {e(a["source_ticket"])} '
                        f'· {e(a["team"] or "")}</span><span class="badge s-waiting">Waiting for review</span></div>'
                        f'<div class="tk-meta">Ticket: {e(t["title"])} · Fix noted by IT: “{e(a["resolution_note"])}”'
                        f' · drafted by {e(a["created_by"])} on {e(a["created_at"])}</div>', unsafe_allow_html=True)
            with st.form(f"kbf_{a['id']}", border=False):
                title = st.text_input("Title", a["title"])
                symptoms = st.text_input("Symptoms (what the employee sees)", a["symptoms"])
                steps = st.text_area("Steps (one per line)", "\n".join(a["steps"]), height=140)
                b1, b2, _ = st.columns([1.3, 1, 3])
                ok = b1.form_submit_button("Approve and publish", type="primary", icon=":material/check:")
                no = b2.form_submit_button("Reject", icon=":material/close:")
            if ok and "(IT: write the steps" in steps:
                st.error("Write the fix steps first: replace the placeholder line.")
            elif ok:
                kb.approve(a["id"], short_name(me["name"]), title, symptoms,
                           [x.strip() for x in steps.splitlines() if x.strip()])
                st.toast(f"{a['id']} approved: the agent will now suggest it.")
                st.rerun()
            if no:
                kb.reject(a["id"], short_name(me["name"]))
                st.rerun()

    with st.expander("Draft an article from a resolved ticket"):
        done = [t for t in db.list_tickets() if t["status"] in ("Resolved", "Closed")
                and not kb.draft_for_ticket(t["ticket_id"])]
        done.sort(key=lambda t: t.get("resolved_at") or "", reverse=True)
        pick = st.selectbox("Resolved ticket", [t["ticket_id"] for t in done[:40]], key="kb_pick",
                            format_func=lambda i: next(f"{t['ticket_id']} · {t['title']} · {t['team']}"
                                                       for t in done if t["ticket_id"] == i))
        note = st.text_input("How was it fixed?", key="kb_note",
                             placeholder="e.g. Disabled and re-enabled the VPN client, then reconnected")
        if st.button("Draft with AI", icon=":material/auto_awesome:", disabled=not (pick and note)):
            with st.spinner("The AI is writing the draft…"):
                new = kb.create_draft(pick, note, created_by=short_name(me["name"]))
            st.toast(f"Draft {new} created.")
            st.rerun()

    gaps = kb.open_gaps()
    st.markdown(f'<div class="section-title" style="margin-top:14px">Knowledge gaps · {len(gaps)} questions the agent '
                'could not answer</div>', unsafe_allow_html=True)
    g1, g2 = st.columns([3, 1], vertical_alignment="center")
    g1.markdown('<div class="dash-n" style="margin:0">Questions with no answer in the documents, and self-help that did '
                'not work. The AI groups them so IT can see which articles are missing.</div>', unsafe_allow_html=True)
    if g2.button("Group with AI", icon=":material/auto_awesome:", disabled=not gaps, width="stretch"):
        with st.spinner("The AI is grouping the questions…"):
            kb.group_gaps()
        st.rerun()
    groups = kb.saved_groups()
    grouped = {q["id"] for grp in groups for q in grp["questions"]}
    new = [g for g in gaps if g["id"] not in grouped]
    if new:                                        # questions asked after the last grouping are always shown
        if groups:
            st.markdown(f'<div class="section-title" style="margin-top:6px">New since the last grouping · {len(new)}'
                        ' (click Group with AI to include them)</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"Asked on": g["at"], "Question": g["question"], "Asked by": short_name(
                                        names.get(g["user"], g["user"])), "Source": g["source"]} for g in new]),
                     hide_index=True, width="stretch")
    for i, grp in enumerate(groups):
        with st.container(key=f"gap_{i}"):
            c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
            c1.markdown(f'<div class="tk-top"><span class="tk-title">{e(grp["topic"])}</span>'
                        f'<span class="badge s-agent">asked {len(grp["questions"])}×</span></div>'
                        f'<div class="tk-meta">Missing article: <b>{e(grp["suggested_title"])}</b></div>'
                        + "".join(f'<div class="hist">“{e(q["question"])}” · {e(q["at"])}</div>'
                                  for q in grp["questions"][:3]), unsafe_allow_html=True)
            if c2.button("Start article", key=f"gapbtn_{i}", icon=":material/edit_note:", width="stretch"):
                new = kb.start_article_from_gap(grp, short_name(me["name"]))
                st.toast(f"Draft {new} created: write the fix steps, then approve it.")
                st.rerun()

    st.markdown(f'<div class="section-title" style="margin-top:12px">Published articles · {len(approved)}</div>',
                unsafe_allow_html=True)
    if approved:
        st.dataframe(pd.DataFrame([{"ID": a["id"], "Title": a["title"], "Team": a["team"], "From ticket": a["source_ticket"],
                                    "Approved by": a["reviewed_by"], "Approved on": a["reviewed_at"],
                                    "Suggested": a["suggested"], "Solved": a["solved"]} for a in approved]),
                     hide_index=True, width="stretch")
        show = st.selectbox("Read an article", [a["id"] for a in approved], key="kb_show",
                            format_func=lambda i: next(f"{a['id']} · {a['title']}" for a in approved if a["id"] == i))
        a = kb.get(show)
        st.markdown(f'<div class="card"><div class="tk-id">{e(a["id"])} · {e(a["team"] or "")}</div>'
                    f'<div class="tk-title" style="font-size:16px">{e(a["title"])}</div>'
                    f'<div class="tk-meta" style="margin:4px 0 8px 0"><b>Symptoms:</b> {e(a["symptoms"])}</div>'
                    + "".join(f'<div style="font-size:13.5px;margin:3px 0">{i}. {e(s)}</div>'
                              for i, s in enumerate(a["steps"], 1)) +
                    f'<div class="sp-tag" style="margin-top:8px">From ticket {e(a["source_ticket"])} · approved by '
                    f'{e(a["reviewed_by"] or "")} · saved to SharePoint list “{e(sharepoint.KB_LIST)}”</div></div>',
                    unsafe_allow_html=True)


def page_incidents():
    st.markdown('<div class="dash-title">Incidents</div><div class="dash-sub">When many people report the same problem in '
                'a short time, it is probably one outage. Declare it once: the agent then tells everyone it is a known '
                'issue instead of opening more tickets.</div>', unsafe_allow_html=True)
    window, threshold = incidents.settings()
    c1, c2, c3 = st.columns([2.6, 1.3, 1.3], vertical_alignment="center")
    c1.markdown(f'<div class="dash-n" style="margin:0">Detection rule: {threshold} or more people, same team and '
                f'category, within {window} minutes.</div>', unsafe_allow_html=True)
    for col, kind, n in ((c2, "Outlook", 5), (c3, "VPN", 4)):
        if col.button(f"Simulate {kind} outage", icon=":material/bolt:", width="stretch", key=f"sim_{kind}",
                      help=f"Demo: {n} different employees report {kind} problems within minutes"):
            made = incidents.simulate_outage(kind)
            st.toast(f"{len(made)} {kind} tickets created: {', '.join(made)}")
            st.rerun()

    found = incidents.detect()
    st.markdown(f'<div class="section-title">Possible outages · {len(found)}</div>', unsafe_allow_html=True)
    if not found:
        st.caption("Nothing detected right now.")
    for i, g in enumerate(found):
        with st.container(key=f"outage_{i}"):
            st.markdown(f'<div class="tk-top"><span class="tk-title">{g["people"]} people · {e(g["category"])} · '
                        f'{e(g["team"])}</span><span class="badge s-agent">in the last {g["window"]} min</span></div>'
                        + "".join(f'<div class="hist"><b>{e(t["ticket_id"])}</b> · '
                                  f'{e(short_name(names.get(t["requester_email"], t["requester_email"])))} · '
                                  f'{e(t["title"])} · {e(t["created_at"][11:16])}</div>' for t in g["tickets"]),
                        unsafe_allow_html=True)
            with st.form(f"declare_{i}", border=False):
                title = st.text_input("Incident title", f"{g['category']} problems for many users")
                msg = st.text_area("Message the agent gives to employees",
                                   f"Many people are having {g['category']} problems. The {g['team']} is working on "
                                   "it. You don't need to raise a new ticket: we will let you know when it is fixed.",
                                   height=80)
                if st.form_submit_button("Declare major incident", type="primary", icon=":material/campaign:"):
                    new = incidents.declare(title, g["team"], g["category"], msg,
                                            [t["ticket_id"] for t in g["tickets"]], short_name(me["name"]))
                    st.toast(f"{new} declared: {len(g['tickets'])} tickets linked. The agent now knows about it.")
                    st.rerun()

    act = incidents.active()
    st.markdown(f'<div class="section-title" style="margin-top:12px">Active major incidents · {len(act)}</div>',
                unsafe_allow_html=True)
    if not act:
        st.caption("No active incidents.")
    for inc in act:
        with st.container(key=f"inc_{inc['id']}"):
            st.markdown(f'<div class="tk-top"><span class="tk-title">{e(inc["id"])} · {e(inc["title"])}</span>'
                        f'<span class="badge s-agent">Active since {e(inc["created_at"][11:])}</span></div>'
                        f'<div class="tk-meta">{e(inc["team"])} · linked tickets: {e(", ".join(inc["tickets"]))}</div>'
                        f'<div class="hist">Message to employees: {e(inc["message"])}</div>', unsafe_allow_html=True)
            st.markdown(kpis(wide=True, items=[("Linked tickets", len(inc["tickets"])),
                                               ("People affected", inc["affected"]),
                                               ("Told by the agent (no new ticket)", inc["via_agent"]),
                                               ("Tickets avoided", inc["via_agent"])]), unsafe_allow_html=True)
            with st.form(f"resolve_{inc['id']}", border=False):
                fix = st.text_input("How was it fixed?", placeholder="e.g. VPN gateway certificate renewed; "
                                    "users disconnect and reconnect")
                make = st.checkbox("Create a knowledge base draft from this fix", value=True)
                if st.form_submit_button("Resolve incident and all linked tickets", icon=":material/task_alt:"):
                    n, draft = incidents.resolve(inc["id"], fix, short_name(me["name"]), make)
                    st.toast(f"{inc['id']} resolved: {n} tickets resolved" + (f", KB draft {draft} created." if draft
                                                                               else "."))
                    st.rerun()
    done = incidents.list_incidents(incidents.RESOLVED)
    if done:
        st.markdown('<div class="section-title" style="margin-top:12px">Resolved incidents</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{"ID": i["id"], "Title": i["title"], "Team": i["team"], "Started": i["created_at"],
                                    "Resolved": i["resolved_at"], "Tickets": len(i["tickets"]),
                                    "People affected": i["affected"], "Fix": i["resolution"]} for i in done]),
                     hide_index=True, width="stretch")


# ---------- Layout ----------
if is_management:                                         # senior management: one page with the benefits
    benefits.render()
elif not is_admin:                                        # employees: chat + my tickets (unchanged)
    chat_col, side_col = st.columns([3, 2], gap="large")
    with chat_col:
        render_chat()
    with side_col:
        render_my_tickets()
else:                                                     # IT admin: full-width console with a menu
    PAGES = ["Dashboard", "Business value", "Tickets", "Incidents", "Knowledge base", "Live chats", "Assistant", "Chats",
             "Audit log", "Quality & cost"]
    if os.getenv("SHOW_SHAREPOINT", "0") == "1":          # hidden since the management demo (was confusing)
        PAGES.insert(4, "SharePoint")
    if st.session_state.get("nav") not in PAGES:
        st.session_state.nav = "Dashboard"
    st.session_state.setdefault("nav", "Dashboard")
    if st.session_state.pop("goto_live", False):
        st.session_state.nav = "Live chats"
    if st.session_state.pop("goto_inc", False):
        st.session_state.nav = "Incidents"
    with st.container(key="adminnav"):
        NAV = st.segmented_control("Admin menu", PAGES, key="nav", format_func=tr,
                                   label_visibility="collapsed") or "Dashboard"
    live_alert(NAV)
    if NAV == "Dashboard":
        dashboard.render(names)
    elif NAV == "Business value":
        benefits.render()
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
    elif NAV == "SharePoint":
        page_sharepoint()
    elif NAV == "Knowledge base":
        page_kb()
    elif NAV == "Incidents":
        page_incidents()
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

st.markdown(f'<div class="foot">{BRAND} {tr("IT Service Desk")} · '
            f'{tr("Demo environment")}</div>', unsafe_allow_html=True)
