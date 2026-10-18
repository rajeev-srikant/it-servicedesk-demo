"""Automatic test set for the agent (like PoC 4's accuracy check, but for an agent).

Runs every request in eval_cases.json through the REAL agent and checks:
  - which tools it used,
  - which action it proposed (and the important details, e.g. team and priority),
  - what the answer contains (or must NOT contain).
Proposed actions are confirmed automatically, so the whole flow is tested.
It uses a separate database (eval_test.db), so your demo tickets are not touched.

Run:   python eval_agent.py        (about 70 small AI requests, under ₹20)
"""
import os
os.environ["HELPDESK_DB"] = "eval_test.db"        # must be set before db is imported

import re
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
import db
import agent

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

with open("eval_cases.json", encoding="utf-8") as f:
    CASES = json.load(f)


def run_case(case):
    db.reset(demo_history=False)                                   # every case starts from the same tickets
    parts = [types.Part.from_text(text=case["message"])]
    if case.get("image"):                          # a test with a screenshot attached
        with open(case["image"], "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
    contents = [types.Content(role="user", parts=parts)]
    tools_used, actions = [], []
    out = agent.run(client, contents, case["user"])
    while out["type"] == "pending":                # confirm automatically and continue
        actions.append({"name": out["name"], "args": out["args"]})
        out = agent.resume(client, contents, out, True, out["args"], case["user"])
    tools_used = [x["tool"] for x in db.list_audit()]
    answer = out["text"]

    problems = []
    if case.get("tools_any") and not any(t in tools_used for t in case["tools_any"]):
        problems.append(f"expected one of {case['tools_any']}, used {tools_used or 'no tools'}")
    if case.get("tools_none") and tools_used:
        problems.append(f"expected no tools, used {tools_used}")
    if "action" in case:
        proposed = actions[0]["name"] if actions else None
        if proposed != case["action"]:
            problems.append(f"expected action {case['action']}, got {proposed}")
        elif case.get("args"):
            for k, v in case["args"].items():
                if str(actions[0]["args"].get(k, "")).lower() != v.lower():
                    problems.append(f"{k}: expected '{v}', got '{actions[0]['args'].get(k)}'")
    for text in case.get("answer_has", []):
        if text.lower() not in answer.lower():
            problems.append(f"answer should mention '{text}'")
    if case.get("answer_has_any") and not any(t.lower() in answer.lower() for t in case["answer_has_any"]):
        problems.append(f"answer should mention one of {case['answer_has_any']}")
    for text in case.get("args_not", []):          # e.g. a password must never end up in a ticket
        if any(text.lower() in json.dumps(x["args"], ensure_ascii=False).lower() for x in actions):
            problems.append(f"the ticket details must NOT contain '{text}'")
    for text in case.get("answer_not", []):
        if text.lower() in answer.lower():
            problems.append(f"answer must NOT mention '{text}'")
    for ticket_id, expected in case.get("status_after", {}).items():   # check the database afterwards
        actual = (db.get_ticket(ticket_id) or {}).get("status")
        if actual != expected:
            problems.append(f"{ticket_id} should be '{expected}' afterwards, but is '{actual}'")
    if case.get("japanese") and not re.search(r"[぀-ヿ一-鿿]", answer):
        problems.append("answer should be in Japanese")
    return problems, tools_used, actions, answer


def add_usage(total, part):
    for kind, v in part.items():
        t = total.setdefault(kind, {"calls": 0, "input": 0, "output": 0})
        for k in t:
            t[k] += v[k]


db.init()
passed, rows, totals = 0, [], {}
for case in CASES:
    try:
        problems, used, actions, answer = run_case(case)
    except Exception as ex:
        problems, used, actions, answer = [f"error: {ex}"], [], [], ""
    add_usage(totals, db.usage_totals())           # count usage before the next case resets the database
    ok = not problems
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'}  {case['id']}  {case['what_we_check']}")
    if not ok:
        for p in problems:
            print(f"        - {p}")
        print(f"        answer: {answer[:160]!r}")
    rows.append({"id": case["id"], "check": case["what_we_check"], "result": "PASS" if ok else "FAIL",
                 "problems": "; ".join(problems), "tools": ", ".join(used),
                 "action": json.dumps(actions[0], ensure_ascii=False) if actions else "", "answer": answer})
    time.sleep(1)                                  # be gentle with the per-minute limit

cost = agent.estimated_cost_usd(totals)
print(f"\nPassed {passed} of {len(CASES)} ({round(100 * passed / len(CASES))}%).")
print(f"AI requests: {totals.get('chat', {}).get('calls', 0)}, estimated cost ${cost:.4f} (≈ ₹{cost * agent.USD_TO_INR:.2f})")

with open("eval_results.json", "w", encoding="utf-8") as f:
    json.dump({"passed": passed, "total": len(CASES), "cases": rows}, f, ensure_ascii=False, indent=2)
print("Details saved to eval_results.json")
