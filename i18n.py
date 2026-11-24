"""English / Japanese screen texts.

How it works: the code writes every screen text in English, wrapped in tr("...").
When the user picks 日本語 in the language box, tr() looks the text up in the JA dictionary below.
A text that is not in the dictionary simply stays in English (nothing breaks).
To translate a new text: add one line  "English text": "日本語のテキスト",  to JA.
"""
import re

import streamlit as st


def lang():
    return st.session_state.get("lang", "en")


def tr(text, **values):
    """Translate one screen text. Values in {curly brackets} are filled in after translating."""
    out = JA.get(text, text) if lang() == "ja" else text
    return out.format(**values) if values else out


# ---------- Response-time (SLA) labels: they contain numbers, so they are translated with patterns ----------
def _dur(s):
    s = re.sub(r"(\d+)h (\d+)m", r"\1時間\2分", s)
    s = re.sub(r"(\d+) min", r"\1分", s)
    s = re.sub(r"(\d+)h\b", r"\1時間", s)
    return re.sub(r"(\d+) days?", r"\1日", s)


_SLA = [
    (r"^Response overdue by (.+)$", "初回対応期限を{0}超過"),
    (r"^Response due in (.+)$", "初回対応まで残り{0}"),
    (r"^Resolution overdue by (.+)$", "解決期限を{0}超過"),
    (r"^Resolve by (.+)$", "解決期限 {0}"),
    (r"^(\w+): respond within (.+) · resolve within (.+)$", "{0}: {1}以内に初回対応 · {2}以内に解決"),
]


def tr_sla(text):
    if lang() != "ja" or not text:
        return text
    if text in JA:
        return JA[text]
    for pattern, ja in _SLA:
        m = re.match(pattern, text)
        if m:
            parts = [JA.get(g, g) for g in m.groups()]
            return _dur(ja.format(*parts))
    return text


JA = {
    # ---- header, sign-in, sidebar ----
    "IT Service Desk": "ITサービスデスク",
    "Demo environment": "デモ環境",
    "IT Admin": "IT管理者",
    "Employee": "社員",
    "Sign in with your Google account to continue.": "続行するには Google アカウントでサインインしてください。",
    "Sign in to the demo environment with the access code you were given.": "配布されたアクセスコードでデモ環境にサインインしてください。",
    "Access code": "アクセスコード",
    "That access code is not correct.": "アクセスコードが正しくありません。",
    "Sign in with Google": "Google でサインイン",
    "New conversation": "新しい会話",
    "Sign out": "サインアウト",
    "Switch user (demo only)": "ユーザー切り替え（デモ用）",
    "Reset demo data": "デモデータをリセット",
    "How it works & safety": "仕組みと安全性",
    "Demo environment with dummy data.": "ダミーデータを使ったデモ環境です。",
    "Actions only change demo tickets.": "操作はデモ用チケットのみに反映されます。",
    "AI model: Google Gemini": "AIモデル: Google Gemini",
    "Conversations are saved for {days} days for quality and audit.": "会話は品質管理と監査のため {days} 日間保存されます。",
    "Conversations are not saved.": "会話は保存されません。",
    "Demo environment · Dummy data only · Powered by Google Gemini": "デモ環境 · ダミーデータのみ · Google Gemini を使用",

    # ---- chat ----
    "Working on it…": "回答を準備しています…",
    "Talk to a person": "担当者と話す",
    "Handed over": "引き継ぎ済み",
    "Hand this conversation to the Service Desk team": "この会話をサービスデスクの担当者に引き継ぎます",
    "Home": "ホーム",
    "Start a new conversation. Your tickets are kept.": "新しい会話を始めます。チケットはそのまま残ります。",
    "Good morning": "おはようございます",
    "Good afternoon": "こんにちは",
    "Good evening": "こんばんは",
    "{greet}, {name}": "{name}さん、{greet}",
    "I'm your IT virtual agent. Ask me about IT policies, check on your tickets, or tell me about a problem and "
    "I'll raise a ticket for you. I always ask before I change anything.":
        "IT バーチャルエージェントです。IT ポリシーについての質問、チケットの状況確認、トラブルのご相談に対応し、"
        "必要に応じてチケットを作成します。何かを変更する前には、必ず確認をお願いします。",
    "Policy answers with sources": "出典付きでポリシーを回答",
    "Ticket status": "チケットの状況確認",
    "Raise & update tickets": "チケットの作成・更新",
    "You confirm every action": "すべての操作はあなたが確認",
    "Chats are saved for {days} days": "会話は {days} 日間保存",
    "Suggested": "よくある質問",
    "Attached screenshot": "添付したスクリーンショット",
    "How I worked this out ({n} steps)": "回答までの手順（{n} ステップ）",
    "Did this solve your problem?": "問題は解決しましたか？",
    "Yes, solved": "はい、解決しました",
    "No, raise a ticket": "いいえ、チケットを作成",
    "Would you like me to raise a ticket?": "チケットを作成しますか？",
    "Yes, raise a ticket": "はい、作成する",
    "No, thanks": "いいえ",
    "No, thanks.": "いいえ、結構です。",
    "Yes, please raise a ticket for this.": "はい、この件でチケットを作成してください。",
    "No problem, I won't raise a ticket. If you need anything else, just ask.":
        "承知しました。チケットは作成しません。ほかに何かあれば、いつでもご質問ください。",
    "Solved with self-help · no ticket needed": "セルフヘルプで解決 · チケット不要",
    "Yes, that solved it.": "はい、解決しました。",
    "Great, I'm glad that's sorted! No ticket needed. If anything else comes up, just ask.":
        "解決してよかったです！チケットは不要です。ほかに何かあれば、いつでもご質問ください。",
    "That didn't solve my problem. Please raise a ticket for me.": "解決しませんでした。チケットを作成してください。",
    "Here is a screenshot of my problem.": "問題のスクリーンショットです。",
    "Ask about IT policies, your tickets, or describe a problem… (you can attach a screenshot)":
        "IT ポリシー、チケット、トラブルについて入力してください…（スクリーンショットも添付できます）",
    "Message the Service Desk…": "サービスデスクへのメッセージ…",
    "The AI service is busy or the usage limit was reached. Please try again in a minute.":
        "AI サービスが混み合っているか、利用上限に達しました。1分ほどしてから再度お試しください。",
    "Sorry, something went wrong: {msg}": "申し訳ありません。エラーが発生しました: {msg}",
    "Known issue": "既知の問題",
    "since": "発生",

    # ---- handoff / live chat ----
    "I've passed our conversation to the Service Desk as ticket **{tid}**. Please stay on this page: a member of "
    "the IT team will join this chat shortly. They can see our conversation, so you won't need to repeat anything. "
    "If you leave, they will follow up through the ticket.":
        "この会話をチケット **{tid}** としてサービスデスクに引き継ぎました。このページでお待ちください。"
        "まもなく IT チームの担当者がこのチャットに参加します。担当者はこれまでの会話を確認できるため、"
        "同じ説明を繰り返す必要はありません。ページを離れた場合は、チケットを通じて担当者からご連絡します。",
    "Service Desk": "サービスデスク",
    "Waiting for a Service Desk agent · you can keep typing, your messages will be passed on":
        "サービスデスク担当者を待っています · 入力を続けていただければ、メッセージは担当者に引き継がれます",
    "You are chatting with {name} (Service Desk) · the AI assistant is paused":
        "{name}（サービスデスク）とチャット中です · AI アシスタントは一時停止中です",
    "You're back with the virtual agent. Ask me anything else.":
        "バーチャルエージェントに戻りました。ほかにご質問があればどうぞ。",

    # ---- confirmation card ----
    "Please confirm your new ticket": "新しいチケットの内容を確認してください",
    "Please confirm this update to {id}": "{id} への更新内容を確認してください",
    "Please confirm the change to {id}": "{id} の変更内容を確認してください",
    "Please confirm: close ticket {id}": "確認: チケット {id} をクローズします",
    "Please confirm: {name}": "確認: {name}",
    "Check the details and change anything that's wrong. Nothing happens until you confirm.":
        "内容を確認し、誤りがあれば修正してください。確認するまで何も実行されません。",
    "Submit ticket": "チケットを送信",
    "Add update": "更新を追加",
    "Save changes": "変更を保存",
    "Close ticket": "クローズ",
    "Confirm": "確定",
    "Cancel": "キャンセル",
    "Title": "件名",
    "Details": "詳細",
    "Priority": "優先度",
    "Assign to": "担当チーム",
    "Category": "カテゴリ",
    "Update": "更新内容",
    "Reason": "理由",
    "Status": "ステータス",
    "Team": "チーム",
    "Note": "メモ",
    "(no change)": "（変更なし）",

    # ---- ticket cards ----
    "My open tickets · {n}": "対応中のチケット · {n}件",
    "You have no open tickets. Describe a problem in the chat and the agent can help or raise one for you.":
        "対応中のチケットはありません。チャットで問題を説明していただければ、エージェントがサポートまたはチケットを作成します。",
    "Past tickets ({n})": "過去のチケット（{n}件）",
    "History ({n} updates)": "履歴（{n}件）",
    "{team} · {pr} priority · Opened {when}": "{team} · 優先度 {pr} · 起票 {when}",
    "Waiting for:": "待ち:",
    "An approval (see the history for details)": "承認（詳細は履歴を参照）",
    "A Service Desk agent to contact you": "サービスデスク担当者からの連絡",
    "Your update": "更新内容",
    "e.g. My manager approved this by email today.": "例: 本日、上司からメールで承認を得ました。",
    "Reason (optional)": "理由（任意）",
    "e.g. It works again": "例: 再び使えるようになりました",
    "Close this ticket if you no longer need help.": "サポートが不要になった場合は、このチケットをクローズしてください。",
    "You can only change your own open tickets.": "変更できるのは、ご自身の対応中のチケットのみです。",
    "Update added to {id}.": "{id} に更新を追加しました。",
    "{id} has been closed.": "{id} をクローズしました。",
    # statuses and priorities (values stay in English inside the database; only the screen shows Japanese)
    "New": "新規",
    "In progress": "対応中",
    "Waiting for approval": "承認待ち",
    "Waiting for agent": "担当者待ち",
    "Resolved": "解決済み",
    "Closed": "クローズ",
    "Low": "低",
    "Medium": "中",
    "High": "高",
    "Urgent": "緊急",
    "IT responded": "IT 対応済み",
    "Clock paused: waiting for approval": "承認待ちのため期限を一時停止中",

    # ---- email preview ----
    "Email preview · to {to}": "メールのプレビュー · 宛先 {to}",
    "PREVIEW ONLY · NOT SENT": "プレビューのみ · 送信されません",
    "From:": "差出人:",
    "To:": "宛先:",
    "Subject:": "件名:",
    "Dear {name},": "{name} 様",
    "[{tid}] We've received your request: {title}": "[{tid}] お問い合わせを受け付けました: {title}",
    "Thank you for contacting the IT Service Desk. We have received your request and it has been assigned to "
    "the team below.": "IT サービスデスクへのお問い合わせありがとうございます。お問い合わせを受け付け、下記のチームに割り当てました。",
    "[{tid}] Your update has been added": "[{tid}] 更新内容を追加しました",
    "We've added your update to the ticket below. The assigned team has been notified.":
        "下記のチケットに更新内容を追加し、担当チームに通知しました。",
    "[{tid}] Your ticket has been updated": "[{tid}] チケットが更新されました",
    "The IT team has updated your ticket. Here are the latest details.": "IT チームがチケットを更新しました。最新の内容は以下のとおりです。",
    "[{tid}] Your ticket has been closed": "[{tid}] チケットをクローズしました",
    "As you requested, we have closed your ticket. If the problem comes back, just ask the virtual agent and "
    "we'll help again.": "ご依頼のとおりチケットをクローズしました。問題が再発した場合は、バーチャルエージェントにご相談ください。",
    "[{tid}] A member of the IT team will contact you": "[{tid}] IT チームの担当者からご連絡します",
    "You asked to talk to a person. Your conversation has been passed to the Service Desk, and someone will "
    "contact you soon. You won't need to repeat anything.":
        "担当者との会話をご希望いただきました。会話内容をサービスデスクに引き継ぎましたので、まもなく担当者からご連絡します。"
        "同じ説明を繰り返す必要はありません。",
    "Ticket": "チケット",
    "Assigned to": "担当チーム",
    "First response by": "初回対応期限",
    "Resolve by": "解決期限",
    "Paused while waiting for approval": "承認待ちのため一時停止中",
    "Service targets": "対応目標",
    "Latest update": "最新の更新",
    "You can check this ticket at any time in the TestBank IT Service Desk.":
        "このチケットは TestBank IT サービスデスクでいつでも確認できます。",
    "Kind regards,": "よろしくお願いいたします。",
    "This is an automated message. Please do not reply to this email. Never share your password with anyone, "
    "including IT.": "このメールは自動送信です。返信しないでください。パスワードは IT 部門を含め、誰にも教えないでください。",

    # ---- "How it works" window ----
    "How the TestBank virtual agent works": "TestBank バーチャルエージェントの仕組み",
    "How it works": "仕組み",
    "Safety rules": "安全ルール",
    "Limits of this demo": "このデモの制限事項",
    "Employee": "社員",
    "asks in English or 日本語": "英語または日本語で質問",
    "AI agent": "AI エージェント",
    "Gemini · understands &amp; decides": "Gemini · 理解して判断",
    "Tools": "ツール",
    "our software · does the work": "自社ソフトウェア · 実際の処理",
    "Tickets &amp; documents": "チケットと文書",
    "database · IT policies": "データベース · IT ポリシー",
    "Results go back to the AI, which decides the next step · the employee confirms every change":
        "結果は AI に戻り、AI が次の手順を判断します · すべての変更は社員が確認します",
    "##### What the AI does\n"
    "- Understands requests in plain English or Japanese, and reads screenshots\n"
    "- Finds answers in IT policies and the self-help guide, with sources\n"
    "- Decides the next step: look up, offer self-help, or prepare a ticket\n"
    "- Picks the right team and priority, and writes clear tickets":
        "##### AI が行うこと\n"
        "- 英語・日本語の問い合わせを理解し、スクリーンショットも読み取る\n"
        "- IT ポリシーとセルフヘルプガイドから、出典付きで回答を探す\n"
        "- 次の手順を判断する: 照会、セルフヘルプの提案、チケットの準備\n"
        "- 適切なチームと優先度を選び、わかりやすいチケットを作成する",
    "##### What normal software does\n"
    "- Creates, updates and closes tickets, only after confirmation\n"
    "- Checks who may see and change what\n"
    "- Response-time targets, overdue alerts, email previews\n"
    "- Audit log, feedback, self-help and cost tracking":
        "##### 通常のソフトウェアが行うこと\n"
        "- 確認後にのみ、チケットを作成・更新・クローズする\n"
        "- 誰が何を閲覧・変更できるかをチェックする\n"
        "- 対応時間の目標、期限超過アラート、メールのプレビュー\n"
        "- 監査ログ、フィードバック、セルフヘルプ、コストの記録",
    "Automatic test set": "自動テスト",
    "Cost per AI request": "AI 1回あたりのコスト",
    "AI model": "AI モデル",
    "estimate": "概算",

    # ---- admin menu and page titles ----
    "Dashboard": "ダッシュボード",
    "Tickets": "チケット",
    "Incidents": "インシデント",
    "Knowledge base": "ナレッジベース",
    "SharePoint": "SharePoint",
    "Live chats": "ライブチャット",
    "Assistant": "アシスタント",
    "Chats": "会話履歴",
    "Audit log": "監査ログ",
    "Quality & cost": "品質とコスト",
    "Open tickets": "未完了チケット",
    "Overdue": "期限超過",
    "Needs attention · {n}": "要対応 · {n}件",
    "Nothing urgent right now.": "現在、緊急の案件はありません。",
    "+ {n} more on the Tickets page.": "ほか {n} 件はチケット画面で確認できます。",
    "Average answer time": "平均回答時間",
    "High / Urgent": "高 / 緊急",
    "Waiting for a person": "担当者待ち",
    # ---- requests, approvals, notifications ----
    "Please confirm your request": "申請内容を確認してください",
    "Send request": "申請を送信",
    "Item": "申請品目",
    "Business reason": "業務上の理由",
    "Needs approval from {name}. You will get a notification when they decide.":
        "{name} さんの承認が必要です。承認・却下されると通知が届きます。",
    "No approval needed: it goes straight to the {team}.": "承認は不要です。そのまま {team} に送られます。",
    "Approvals waiting for you · {n}": "あなたの承認待ち · {n}件",
    "Reason:": "理由:",
    "Comment (optional)": "コメント（任意）",
    "Approve": "承認",
    "Requested by {name} · {unit}. The cost is charged to this cost center.":
        "申請者: {name} · {unit}。費用はこのコストセンターに計上されます。",
    "Reject": "却下",
    "{id} approved.": "{id} を承認しました。",
    "{id} rejected.": "{id} を却下しました。",
    "No notifications yet.": "通知はまだありません。",
    "Mark all as read": "すべて既読にする",
    "{who} requests {item} ({tid}). Please approve or reject it.":
        "{who} さんが {item} を申請しました（{tid}）。承認または却下してください。",
    "Good news: {approver} approved your request for {item} ({tid}). The {team} will now prepare it.":
        "{approver} さんが {item} の申請を承認しました（{tid}）。{team} が準備を進めます。",
    "{approver} did not approve your request for {item} ({tid}).{note}":
        "{approver} さんは {item} の申請を承認しませんでした（{tid}）。{note}",
    "IT updated your ticket {tid}: {changes}.": "IT がチケット {tid} を更新しました: {changes}",
    "Fixed: {title} ({inc}). {fix}": "復旧しました: {title}（{inc}）。{fix}",
}

# Suggested questions on the welcome screen
EXAMPLES = {
    "en": {
        "admin": ["Which tickets are still open?",
                  "Move T-1002 to the Apps Team and set it to In progress",
                  "Show me the history of T-1001",
                  "What does the policy say about USB drives?"],
        "employee": ["What's the status of my monitor request?",
                     "My keyboard stopped working, can you raise a ticket?",
                     "I forgot my password and need to reset it",
                     "I can't connect to the VPN. What should I do?",
                     "I need Adobe Acrobat Pro to edit contracts",
                     "Show me Mai Saito's tickets"],
    },
    "ja": {
        "admin": ["未完了のチケットを教えてください",
                  "T-1002 を Apps Team に移して、対応中にしてください",
                  "T-1001 の履歴を見せてください",
                  "USB メモリについてポリシーには何と書いてありますか？"],
        "employee": ["モニターの申請はどうなっていますか？",
                     "キーボードが動かなくなりました。チケットを作成してもらえますか？",
                     "パスワードを忘れたのでリセットしたいです",
                     "VPNに接続できません。どうすればいいですか？",
                     "契約書の編集のために Adobe Acrobat Pro が必要です",
                     "斎藤舞さんのチケットを見せてください"],
    },
}
