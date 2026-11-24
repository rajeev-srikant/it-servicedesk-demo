"""Who belongs where: department, team and cost center for every employee (dummy data).

Each employee's department comes from employees.json. A person can also have:
  "team"        - their team inside the department (for example "ISO 5")
  "cost_center" - who pays for their requests (for example "CC-4105")
If those are missing, the team is the department and the cost center comes from the department table below.
In a real bank this information comes from the HR system / Microsoft Entra ID, not from a file.

Every ticket stores a COPY of department, team and cost center at the moment it is created,
so billing stays correct even if the person moves to another department later.
"""
import json

COST_CENTERS = {
    "IT": "CC-4100", "IT Operations": "CC-4200", "Engineering": "CC-4300",
    "Sales": "CC-1100", "Marketing": "CC-1200",
    "Finance": "CC-2100", "Legal": "CC-2200", "HR": "CC-2300",
    "Customer Support": "CC-3100", "Operations": "CC-3200",
    "Retail Banking": "CC-5100", "Treasury": "CC-5200", "Corporate Banking": "CC-5300",
    "Risk": "CC-6100", "Compliance": "CC-6200",
}
UNKNOWN = {"department": "Unassigned", "team": "Unassigned", "cost_center": "CC-0000"}

with open("employees.json", encoding="utf-8") as f:
    _PEOPLE = {e["email"].lower(): e for e in json.load(f)}


def info(email):
    """{"department", "team", "cost_center"} for one person."""
    p = _PEOPLE.get((email or "").lower())
    if not p or p.get("department") in (None, "", "—"):
        return dict(UNKNOWN)
    dept = p["department"]
    return {"department": dept, "team": p.get("team") or dept,
            "cost_center": p.get("cost_center") or COST_CENTERS.get(dept, UNKNOWN["cost_center"])}


def label(email):
    """Short text for screens, for example "IT / ISO 5 · CC-4105"."""
    o = info(email)
    unit = o["department"] if o["team"] == o["department"] else f'{o["department"]} / {o["team"]}'
    return f'{unit} · {o["cost_center"]}'
