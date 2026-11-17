# Connecting the IT agent to real SharePoint (for the pilot)

The demo runs in **simulated** mode: no Microsoft 365 account is needed. To connect a real
SharePoint Online site, an administrator of a Microsoft 365 tenant does the steps below.
No code changes are needed: only settings.

> Note: live mode was written against the Microsoft Graph documentation but has not yet been
> tested against a real tenant. Test it on a test site before the pilot.

## 1. Create the site and two Lists
On a SharePoint site (for example "IT Helpdesk"):

**List "IT Helpdesk"** (one item per ticket). Add these columns:

| Column | Internal name | Type |
|---|---|---|
| Title | Title | (built in) |
| Ticket ID | TicketID | Single line of text |
| Status | Status | Choice: New, In progress, Waiting for approval, Waiting for agent, Resolved, Closed |
| Priority | Priority | Choice: Low, Medium, High, Urgent |
| Category | Category | Single line of text |
| Assigned team | AssignedTeam | Choice: Service Desk, Network Team, Security Team, Hardware Team, Apps Team |
| Requested by | RequesterEmail | Single line of text |
| Channel | Channel | Choice: Virtual agent, Email, Portal, Phone |
| Waiting for | WaitingFor | Single line of text |
| First response | FirstResponse | Date and time |
| Resolved on | ResolvedOn | Date and time |

Tip: create each column first with the internal name (no spaces), then rename the display name.

**List "IT Helpdesk Updates"** (one item per ticket update): Title (built in), TicketID (text), Note (multiple lines of text).

**Document library "IT Policies"**: upload the policy PDFs, then run `python build_index.py`.

## 2. Register the app in Microsoft Entra ID
1. Entra admin center → App registrations → New registration (name: "IT Virtual Agent").
2. Certificates & secrets → New client secret. Copy the value (shown once).
3. API permissions → Microsoft Graph → Application permission **Sites.Selected** → Grant admin consent.
4. Give the app write access to this one site only (an admin grants it through the Graph
   `/sites/{site-id}/permissions` endpoint, role "write").

## 3. Settings (in `.env`, or Streamlit secrets in the cloud)
```
SHAREPOINT_MODE=graph
SHAREPOINT_SITE_URL=https://<tenant>.sharepoint.com/sites/ITHelpdesk
SHAREPOINT_SITE_ID=<site id from GET https://graph.microsoft.com/v1.0/sites/<tenant>.sharepoint.com:/sites/ITHelpdesk>
SHAREPOINT_LIST=IT Helpdesk
SHAREPOINT_UPDATES_LIST=IT Helpdesk Updates
SHAREPOINT_LIBRARY=IT Policies
AZURE_TENANT_ID=<tenant id>
AZURE_CLIENT_ID=<application (client) id>
AZURE_CLIENT_SECRET=<client secret>
```
Never upload `.env` to GitHub and never share the client secret.

## 4. Check
Admin console → SharePoint → Connection → **Test the SharePoint connection**. Then create a ticket in
the chat and check that it appears in the SharePoint List and in the Graph API log as "sent".

## Production notes
- The pilot can switch from app-only access to the signed-in user's own access (single sign-on with
  Entra ID), so SharePoint permissions apply per person.
- In this version the app's database is a local copy; production would read open tickets back from
  SharePoint so changes made directly in SharePoint also appear in the agent.
