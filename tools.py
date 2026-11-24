"""The agent's tools: plain Python functions the AI is allowed to ask us to run.

The docstring of each function is what the AI reads to decide WHEN and HOW to use it,
so it is written for the AI as much as for people.

Employees get 7 tools. IT admins get 2 more (list_all_tickets, update_ticket).
Every tool also checks permissions itself, so even a confused AI cannot cross the line.
"""
import os
import json
import numpy as np
from dotenv import load_dotenv
from google import genai
import db
import sla
import sharepoint
import kb
import incidents
import catalog

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TEAMS = ["Service Desk", "Network Team", "Security Team", "Hardware Team", "Apps Team"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]
STATUSES = ["New", "In progress", "Waiting for approval", "Waiting for agent", "Resolved", "Closed"]

with open("employees.json", encoding="utf-8") as f:
    EMPLOYEES = {e["email"].lower(): e for e in json.load(f)}

with open("index.json", encoding="utf-8") as f:
    _INDEX = json.load(f)
_VECTORS = np.array([c["vector"] for c in _INDEX["chunks"]], dtype=np.float32)
_VECTORS = _VECTORS / np.linalg.norm(_VECTORS, axis=1, keepdims=True)

# The app sets this before each agent run: the email of the person chatting.
state = {"user": None}


def register_user(email, name, admin=False):
    """Add a person who signed in with Google but is not in employees.json."""
    email = email.lower()
    if email not in EMPLOYEES:
        EMPLOYEES[email] = {"email": email, "name": name or email.split("@")[0], "employee_id": "—",
                            "department": "—", "location": "—"}
    if admin:
        EMPLOYEES[email]["role"] = "admin"
    return EMPLOYEES[email]


def is_admin(email=None):
    return EMPLOYEES.get((email or state["user"] or "").lower(), {}).get("role") == "admin"


def _can_access(t):
    return t["requester_email"] == state["user"] or is_admin()


def _response(t):
    r, res = sla.status(t), sla.resolution(t)
    return {"targets": sla.targets_text(t), "first_response_due": r["due"], "response_state": r["label"],
            "resolve_by": res["due"], "resolution_state": res["label"]}


def resume_if_waiting(t, who="the user"):
    """When the user sends the information IT was waiting for, the ticket goes back to In progress
    and the resolution clock starts again."""
    if t["status"] == db.PAUSE_STATUS:
        db.update_ticket(t["ticket_id"], status="In progress")
        db.clear_waiting(t["ticket_id"])
        db.add_history(t["ticket_id"], f"Status changed to In progress after the update from {who} "
                                       "(the resolution clock restarts).")


def _short(t):
    short = dict({k: t[k] for k in ("ticket_id", "title", "team", "priority", "status", "created")},
                 response=_response(t))
    if t.get("waiting_for"):
        short["waiting_for"] = t["waiting_for"]
    return short


# ======================================================================
# READ-ONLY TOOLS (safe: they only look things up)
# ======================================================================
_QUERY_CACHE = {}


def search_policies(question: str) -> dict:
    """Search the company IT documents: the policies (IT security, remote work and VPN,
    laptops and equipment), the IT Self-Help Guide (step-by-step fixes for passwords, locked accounts,
    MFA, printers, VPN, Outlook and Teams) and the IT Knowledge Base (fixes approved by IT from past tickets,
    IDs like KB-003). Use this for 'how do I', 'what is the rule' and self-help questions, and for any problem
    the user describes. Returns the 3 most relevant passages with their source."""
    key = question.strip().lower()
    if key not in _QUERY_CACHE:                    # speed: the same question is only embedded once
        result = _client.models.embed_content(
            model=_INDEX["embed_model"], contents=[question],
            config={"task_type": "RETRIEVAL_QUERY", "output_dimensionality": _INDEX["embed_dim"]},
        )
        db.log_usage(state["user"], "embedding", len(question) // 4 + 1, 0)
        _QUERY_CACHE[key] = result.embeddings[0].values
    q = np.array(_QUERY_CACHE[key], dtype=np.float32)
    q = q / np.linalg.norm(q)
    found = [(float(score), {"file": _INDEX["chunks"][i]["file"], "page": _INDEX["chunks"][i]["page"],
                             "text": _INDEX["chunks"][i]["text"]})
             for i, score in enumerate(_VECTORS @ q)]
    for a, v in kb.approved_with_vectors(_embed_document):          # approved fixes from past tickets
        found.append((float(v @ q), {"file": a["id"], "source": "IT Knowledge Base", "kb": True,
                                     "text": kb.text_of(a)}))
    found.sort(key=lambda x: x[0], reverse=True)
    return {"passages": [p for _, p in found[:3]]}


def _embed_document(text):
    result = _client.models.embed_content(
        model=_INDEX["embed_model"], contents=[text],
        config={"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": _INDEX["embed_dim"]})
    db.log_usage(state["user"], "embedding", len(text) // 4 + 1, 0)
    return list(result.embeddings[0].values)


def lookup_employee(email: str) -> dict:
    """Look up a person in the employee directory by email address.
    Returns their name, employee ID, department and location."""
    person = EMPLOYEES.get(email.strip().lower())
    if not person:
        return {"error": f"No employee found with email {email}"}
    return {k: v for k, v in person.items() if k != "role"}


def list_my_tickets() -> dict:
    """List all tickets raised by the current user, with ID, title, team, priority and status.
    Use this when the user mentions an existing problem or asks about their tickets."""
    sharepoint.on_read("mine", requester=state["user"])
    return {"tickets": [_short(t) for t in db.list_tickets(state["user"])]}


def check_ticket_status(ticket_id: str) -> dict:
    """Get full details and history of one ticket by its ID (for example 'T-1004').
    Employees can only open their own tickets; IT admins can open any ticket."""
    sharepoint.on_read("one", ticket_id=ticket_id)
    t = db.get_ticket(ticket_id)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    if not _can_access(t):
        return {"error": "Access denied: you can only view your own tickets"}
    return dict(t, response=_response(t))


# ======================================================================
# ACTION TOOLS (change data: the app asks the user to confirm them first)
# ======================================================================
def create_ticket(title: str, description: str, category: str, priority: str, team: str) -> dict:
    """Create a new IT support ticket for the current user and assign it to a team.
    team must be one of: Service Desk, Network Team, Security Team, Hardware Team, Apps Team.
    priority must be one of: Low, Medium, High, Urgent.
    Write title and description in English.
    Only use this if the user has a problem that needs IT action and no existing ticket covers it."""
    if team not in TEAMS:
        return {"error": f"Unknown team '{team}'. Use one of: {', '.join(TEAMS)}"}
    if priority not in PRIORITIES:
        return {"error": f"Unknown priority '{priority}'. Use one of: {', '.join(PRIORITIES)}"}
    new_id = db.create_ticket(state["user"], title, category, priority, team, "New",
                              f"Ticket created by AI agent for the user. {description}")
    t = db.get_ticket(new_id)
    return {"created": new_id, "assigned_to": team, "priority": priority, "status": "New",
            "saved_to": f"SharePoint List '{sharepoint.LIST_NAME}' (item {sharepoint.item_id(t)})",
            "response": _response(t)}


def add_comment(ticket_id: str, comment: str) -> dict:
    """Add an update or comment from the user to one of their existing tickets
    (for example 'still not working after restart'). Write the comment in English."""
    t = db.get_ticket(ticket_id)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    if not _can_access(t):
        return {"error": "Access denied: you can only update your own tickets"}
    db.add_history(t["ticket_id"], f"Comment added by AI agent for the user: {comment}")
    resume_if_waiting(t)
    return {"updated": t["ticket_id"], "comment_added": comment}


def close_ticket(ticket_id: str, reason: str) -> dict:
    """Close one of the current user's own tickets because they no longer need help
    (for example 'it works again' or 'request no longer needed'). Write the reason in English."""
    t = db.get_ticket(ticket_id)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    if not _can_access(t):
        return {"error": "Access denied: you can only close your own tickets"}
    if t["status"] in ("Resolved", "Closed"):
        return {"error": f"Ticket {t['ticket_id']} is already {t['status']}"}
    db.update_ticket(t["ticket_id"], status="Closed")
    db.clear_waiting(t["ticket_id"])
    db.add_history(t["ticket_id"], f"Closed by the user via AI agent. Reason: {reason}")
    return {"closed": t["ticket_id"], "reason": reason}


# ======================================================================
# ADMIN-ONLY TOOLS (only given to the AI when an IT admin is signed in)
# ======================================================================
def list_all_tickets() -> dict:
    """IT admins only. List every OPEN ticket in the system with requester, team, priority, status and
    response/resolution targets, plus how many tickets are already resolved or closed."""
    if not is_admin():
        return {"error": "Access denied: only IT admins can list all tickets"}
    sharepoint.on_read("open")
    tickets = db.list_tickets()
    open_t = [t for t in tickets if t["status"] not in ("Resolved", "Closed")]
    return {"open_tickets": [dict(_short(t), requester=EMPLOYEES.get(t["requester_email"], {}).get(
                "name", t["requester_email"])) for t in open_t],
            "resolved_or_closed_count": len(tickets) - len(open_t)}


def update_ticket(ticket_id: str, status: str, team: str, priority: str, note: str) -> dict:
    """IT admins only. Change a ticket's status, team and/or priority, and add a note.
    Use an empty string "" for anything that should not change.
    status must be one of: New, In progress, Waiting for approval, Waiting for agent, Resolved, Closed.
    team must be one of: Service Desk, Network Team, Security Team, Hardware Team, Apps Team.
    priority must be one of: Low, Medium, High, Urgent."""
    if not is_admin():
        return {"error": "Access denied: only IT admins can update tickets"}
    t = db.get_ticket(ticket_id)
    if not t:
        return {"error": f"Ticket {ticket_id} not found"}
    for value, allowed, label in ((status, STATUSES, "status"), (team, TEAMS, "team"), (priority, PRIORITIES, "priority")):
        if value and value not in allowed:
            return {"error": f"Unknown {label} '{value}'. Use one of: {', '.join(allowed)}"}
    db.update_ticket(t["ticket_id"], status=status, team=team, priority=priority)
    db.mark_responded(t["ticket_id"])                  # an admin update counts as IT's response
    if status and status not in ("Resolved", "Closed"):
        db.reopen(t["ticket_id"])
    if status and status != "Waiting for approval":
        db.clear_waiting(t["ticket_id"])
    changes = ", ".join(f"{k} -> {v}" for k, v in (("status", status), ("team", team), ("priority", priority)) if v)
    admin_name = EMPLOYEES[state["user"]]["name"]
    db.add_history(t["ticket_id"], f"Updated by {admin_name} via AI agent" + (f" ({changes})" if changes else "")
                   + (f". Note: {note}" if note else ""))
    if t["requester_email"] != state["user"]:          # tell the employee (in-app notification)
        catalog.notify(t["requester_email"], "IT updated your ticket {tid}: {changes}.", t["ticket_id"],
                       changes=", ".join(x for x in (changes, note) if x) or "new note")
    result = {"updated": t["ticket_id"], "changes": changes or "none", "note": note}
    if status in ("Resolved", "Closed") and note:          # knowledge loop: the fix becomes a draft KB article
        draft = kb.create_draft(t["ticket_id"], note, created_by=admin_name)
        if draft:
            result["kb_draft"] = f"{draft} (draft knowledge base article, waiting for IT review)"
    return result


def list_request_catalog() -> dict:
    """List what employees can REQUEST (software licences, access, equipment), with the team that provides it,
    the cost, and whether the employee's manager must approve it. Use this when the user wants something new
    (not when something is broken)."""
    me = EMPLOYEES.get(state["user"], {})
    mgr = catalog.manager_of(state["user"], EMPLOYEES)
    return {"items": [dict(name=k, **v) for k, v in catalog.CATALOG.items()],
            "your_approving_manager": EMPLOYEES.get(mgr, {}).get("name") if mgr else None,
            "requested_for": me.get("name")}


def request_item(item: str, details: str, reason: str) -> dict:
    """Request an item from the request catalogue for the current user (software, access or equipment).
    item must be a name from list_request_catalog (for example "Adobe Acrobat Pro").
    details: what exactly is needed (in English). reason: the business reason (in English).
    Items that need approval are sent to the user's manager; the user is notified of the decision.
    Use this INSTEAD of create_ticket for requests. Ask for the business reason first if the user did not give one."""
    found = catalog.find_item(item)
    if not found:
        return {"error": f"'{item}' is not in the request catalogue. Items: {', '.join(catalog.CATALOG)}. "
                         "For anything else, offer a normal ticket."}
    return catalog.create_request(state["user"], found, details, reason, EMPLOYEES)


def report_to_incident(incident_id: str) -> dict:
    """Use when the user's problem matches an ACTIVE MAJOR INCIDENT listed in your instructions (for example INC-001).
    Records the user as affected so they are told when it is fixed. Do NOT create a ticket in that case."""
    return incidents.report(incident_id, state["user"])


def log_knowledge_gap(question: str) -> dict:
    """Use when an IT question cannot be answered from the IT documents or the knowledge base
    (search_policies found nothing relevant). Records the question in English so IT can write an article.
    Then tell the user you could not find it, and offer to raise a ticket or press "Talk to a person"."""
    kb.log_gap(state["user"], question, "agent could not answer")
    return {"recorded": True}


EMPLOYEE_TOOLS = [search_policies, lookup_employee, list_my_tickets, check_ticket_status, create_ticket, add_comment,
                  close_ticket, report_to_incident, log_knowledge_gap, list_request_catalog, request_item]
ADMIN_TOOLS = EMPLOYEE_TOOLS + [list_all_tickets, update_ticket]
TOOL_MAP = {f.__name__: f for f in ADMIN_TOOLS}
ACTION_NAMES = {"create_ticket", "add_comment", "close_ticket", "update_ticket", "request_item"}


def tools_for(email):
    """Least privilege: the AI is only shown the tools this person is allowed to use."""
    return ADMIN_TOOLS if is_admin(email) else EMPLOYEE_TOOLS
