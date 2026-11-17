"""SharePoint connector: how the IT agent plugs into a SharePoint helpdesk.

A SharePoint helpdesk is usually:
  - a SharePoint List of tickets (here: "IT Helpdesk"), one list item per ticket,
  - a second List for ticket updates (here: "IT Helpdesk Updates"),
  - a document library with the IT policies (here: "IT Policies").
Programs talk to SharePoint Online through the Microsoft Graph API.

Two modes, chosen with SHAREPOINT_MODE in .env (or Streamlit secrets):
  "simulated" (default)  Tickets are kept in the app's own database, shaped exactly like items of the
                          SharePoint List. Every change records the Graph request that WOULD be sent.
                          No Microsoft 365 account is needed: this is the demo mode.
  "graph"                The same requests are really sent to SharePoint Online. Needs a Microsoft 365
                          tenant, the two Lists, and an app registration in Microsoft Entra ID
                          (see SHAREPOINT_SETUP.md). The app's database stays as a local copy (cache).

The rest of the app does not care which mode is on: db.py calls the functions below whenever a ticket
is created or changed, so the agent, the screens and the dashboard stay exactly the same.
"""
import os
import json
import time
import db

MODE = os.getenv("SHAREPOINT_MODE", "simulated").strip().lower()
SITE_URL = os.getenv("SHAREPOINT_SITE_URL", "https://testbank.sharepoint.com/sites/ITHelpdesk")
SITE_ID = os.getenv("SHAREPOINT_SITE_ID", "{site-id}")
LIST_NAME = os.getenv("SHAREPOINT_LIST", "IT Helpdesk")
UPDATES_LIST = os.getenv("SHAREPOINT_UPDATES_LIST", "IT Helpdesk Updates")
LIBRARY_NAME = os.getenv("SHAREPOINT_LIBRARY", "IT Policies")
KB_LIST = os.getenv("SHAREPOINT_KB_LIST", "IT Knowledge Base")
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")          # never show or log this
GRAPH = "https://graph.microsoft.com/v1.0"

# Our ticket field -> SharePoint column (display name, internal name, column type)
COLUMNS = [
    ("ticket_id", "Ticket ID", "TicketID", "Single line of text"),
    ("title", "Title", "Title", "Single line of text"),
    ("status", "Status", "Status", "Choice"),
    ("priority", "Priority", "Priority", "Choice"),
    ("category", "Category", "Category", "Single line of text"),
    ("team", "Assigned team", "AssignedTeam", "Choice"),
    ("requester_email", "Requested by", "RequesterEmail", "Single line of text"),
    ("channel", "Channel", "Channel", "Choice"),
    ("waiting_for", "Waiting for", "WaitingFor", "Single line of text"),
    ("first_response_at", "First response", "FirstResponse", "Date and time"),
    ("resolved_at", "Resolved on", "ResolvedOn", "Date and time"),
]
INTERNAL = {field: internal for field, _, internal, _ in COLUMNS}
DISPLAY = {field: display for field, display, _, _ in COLUMNS}


def is_live():
    return MODE == "graph"


def mode_label():
    return "Connected to SharePoint Online" if is_live() else "Simulated SharePoint List"


def _items_path(list_name=None):
    from urllib.parse import quote
    return f"/sites/{SITE_ID}/lists/{quote(list_name or LIST_NAME)}/items"


def item_id(t):
    """The SharePoint list item ID. Simulated: the ticket number (T-1027 -> 1027)."""
    return t.get("sp_item_id") or str(int(t["ticket_id"].split("-")[1]))


def fields_of(t, only=None):
    out = {}
    for field, internal in INTERNAL.items():
        if only is not None and field not in only:
            continue
        value = t.get(field)
        if value not in (None, "") or only is not None:
            out[internal] = value if value not in ("",) else None
    return out


# ---------------------------------------------------------------- hooks called by db.py
def on_create(ticket_id):
    t = db.get_ticket(ticket_id)
    result = _send("POST", _items_path(), {"fields": fields_of(t)}, ticket_id)
    if is_live() and isinstance(result, dict) and result.get("id"):
        db.set_sp_item_id(ticket_id, result["id"])


def on_update(ticket_id, changed):
    """changed: our field names -> new values (only the columns SharePoint has)."""
    changed = {k: v for k, v in changed.items() if k in INTERNAL}
    if not changed:
        return
    t = db.get_ticket(ticket_id)
    _send("PATCH", f"{_items_path()}/{item_id(t)}/fields", fields_of(dict(t, **changed), only=changed), ticket_id)


def on_note(ticket_id, text):
    _send("POST", _items_path(UPDATES_LIST),
          {"fields": {"TicketID": ticket_id, "Title": text[:255], "Note": text}}, ticket_id)


def on_kb(article):
    """An approved knowledge base article becomes an item of the SharePoint list "IT Knowledge Base"."""
    _send("POST", _items_path(KB_LIST), {"fields": {"Title": article["title"], "ArticleID": article["id"],
                                                    "Symptoms": article["symptoms"],
                                                    "Steps": "\n".join(article["steps"]),
                                                    "SourceTicket": article["source_ticket"]}}, article["source_ticket"])


def on_read(what, ticket_id=None, requester=None):
    """Reads the agent makes. Simulated: answered from the local copy, recorded for the log."""
    if what == "mine":
        path = f"{_items_path()}?$expand=fields&$filter=fields/RequesterEmail eq '{requester}'"
    elif what == "one":
        path = f"{_items_path()}?$expand=fields&$filter=fields/TicketID eq '{ticket_id}'"
    else:
        path = f"{_items_path()}?$expand=fields&$filter=fields/Status ne 'Resolved' and fields/Status ne 'Closed'"
    _send("GET", path, None, ticket_id, record_only=True)


# ---------------------------------------------------------------- sending (or simulating) a Graph request
_token = {"value": None, "expires": 0}


def _get_token():
    """App-only token from Microsoft Entra ID (client credentials). Cached until it expires."""
    import requests
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    r = requests.post(f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token", timeout=20,
                      data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                            "client_secret": CLIENT_SECRET, "scope": "https://graph.microsoft.com/.default"})
    r.raise_for_status()
    data = r.json()
    _token.update(value=data["access_token"], expires=time.time() + data.get("expires_in", 3600))
    return _token["value"]


def _send(method, path, body, ticket_id=None, record_only=False):
    """Simulated: record the request and return a SharePoint-like answer. Graph: really send it."""
    if not is_live() or record_only:
        db.log_graph(method, path, body, ticket_id, "simulated" if not is_live() else "read from cache", 200)
        return {"id": None}
    import requests
    try:
        r = requests.request(method, GRAPH + path, json=body, timeout=20,
                             headers={"Authorization": f"Bearer {_get_token()}",
                                      "Prefer": "HonorNonIndexedQueriesWarningMayFailRandomly"})
        db.log_graph(method, path, body, ticket_id, "sent", r.status_code)
        return r.json() if r.content else {}
    except Exception as ex:                        # SharePoint down: the local copy keeps working
        db.log_graph(method, path, body, ticket_id, f"error: {type(ex).__name__}", 0)
        return {"error": str(ex)}


def check_connection():
    """Graph mode only: can we reach the site and the List? Returns (ok, message)."""
    if not is_live():
        return False, "Simulated mode: no connection is needed."
    import requests
    try:
        r = requests.get(f"{GRAPH}/sites/{SITE_ID}/lists/{LIST_NAME}", timeout=20,
                         headers={"Authorization": f"Bearer {_get_token()}"})
        return r.ok, f"HTTP {r.status_code}" + ("" if r.ok else f": {r.text[:200]}")
    except Exception as ex:
        return False, f"{type(ex).__name__}: {ex}"
