"""Most-asked questions of the week (shown on the employee start screen).

How it works:
1. Every question an employee types is logged with its TOPIC (passwords, VPN, Outlook, ...).
   English and Japanese questions about the same thing land in the same topic.
2. The start screen ranks topics by how many DIFFERENT people asked about them in the last 7 days.
3. For each top topic it shows a standard, neatly worded question - never a colleague's own words,
   so nobody can see what someone else asked (privacy).
4. A topic is only shown when at least 2 different people asked about it.
If there is not enough data yet, the app falls back to the fixed suggestions.
The demo database starts with about one week of example activity, so the list is not empty.
"""
import random
from datetime import timedelta

import db

SCHEMA = """CREATE TABLE IF NOT EXISTS question_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, user TEXT,
            lang TEXT, topic TEXT);"""
DAYS, MIN_PEOPLE, SHOW = 7, 2, 6

# topic -> (words that identify it, standard question in English, standard question in Japanese)
TOPICS = {
    "password": (("password", "locked out", "reset my", "sign in", "log in", "login", "mfa", "authenticator",
                  "パスワード", "ログイン", "サインイン", "ロック"),
                 "I forgot my password", "パスワードを忘れました"),
    "vpn": (("vpn", "remote access", "tb connect", "リモート"),
            "I can't connect to the VPN", "VPNに接続できません"),
    "outlook": (("outlook", "email", "e-mail", "mailbox", "inbox", "メール"),
                "Outlook isn't receiving emails", "Outlook でメールを受信できません"),
    "software": (("acrobat", "visio", "install", "licence", "license", "software", "ソフト", "インストール", "ライセンス"),
                 "I need Adobe Acrobat Pro", "Adobe Acrobat Pro が必要です"),
    "hardware": (("keyboard", "mouse", "monitor", "laptop", "headset", "screen", "キーボード", "マウス", "モニター",
                  "パソコン", "ノートPC"),
                 "My keyboard stopped working", "キーボードが動きません"),
    "printer": (("print", "printer", "プリンター", "印刷"),
                "I can't print", "印刷できません"),
    "teams": (("teams",), "Teams calls keep dropping", "Teams の通話が切れます"),
    "wifi": (("wi-fi", "wifi", "wireless", "network", "internet", "ネットワーク", "インターネット"),
             "The Wi-Fi is very slow", "Wi-Fi がとても遅いです"),
    "access": (("shared drive", "access to", "permission", "共有ドライブ", "アクセス権"),
               "I need access to the shared drive", "共有ドライブのアクセス権が必要です"),
    "phone": (("phone", "mobile", "スマートフォン", "携帯"),
              "I lost my company phone", "会社のスマートフォンをなくしました"),
    "status": (("status", "my ticket", "my request", "状況", "申請はどう"),
               "What's the status of my request?", "申請の状況を教えてください"),
}


def init():
    with db._conn() as c:
        c.executescript(SCHEMA)
        empty = c.execute("SELECT COUNT(*) FROM question_log").fetchone()[0] == 0
    if empty:
        _seed_demo()


def reset():
    with db._conn() as c:
        c.executescript(SCHEMA)
        c.execute("DELETE FROM question_log")
    _seed_demo()


def topic_of(text):
    t = (text or "").lower()
    for topic, (words, _, _) in TOPICS.items():
        if any(w in t for w in words):
            return topic
    return None


def log_question(user, lang, text):
    """Called for every question an employee types. Only the topic is kept, not the words."""
    topic = topic_of(text)
    if topic:
        with db._conn() as c:
            c.execute("INSERT INTO question_log (at, user, lang, topic) VALUES (?,?,?,?)",
                      (db.now().isoformat(timespec="seconds"), user, lang, topic))


def most_asked(lang="en"):
    """[(standard question, number of people)] for the top topics of the last 7 days."""
    since = (db.now() - timedelta(days=DAYS)).isoformat(timespec="seconds")
    with db._conn() as c:
        rows = c.execute("SELECT topic, COUNT(DISTINCT user) AS people FROM question_log WHERE at >= ? "
                         "GROUP BY topic HAVING people >= ? ORDER BY people DESC, MAX(at) DESC LIMIT ?",
                         (since, MIN_PEOPLE, SHOW)).fetchall()
    return [(TOPICS[r["topic"]][2 if lang == "ja" else 1], r["people"]) for r in rows if r["topic"] in TOPICS]


# ---------------------------------------------------------------- demo data: about one week of activity
DEMO_WEEK = {"password": 17, "vpn": 13, "outlook": 9, "software": 8, "hardware": 6, "printer": 5, "teams": 4,
             "status": 4, "wifi": 3}


def _seed_demo():
    import json
    with open("employees.json", encoding="utf-8") as f:
        people = [p["email"] for p in json.load(f) if not p.get("role")]
    rnd = random.Random(7)                              # same demo data every time
    now = db.now()
    with db._conn() as c:
        for topic, n in DEMO_WEEK.items():
            for user in rnd.sample(people, min(n, len(people))):
                at = now - timedelta(days=rnd.uniform(0.2, 6.8))
                c.execute("INSERT INTO question_log (at, user, lang, topic) VALUES (?,?,?,?)",
                          (at.isoformat(timespec="seconds"), user, rnd.choice(["en", "en", "ja"]), topic))
