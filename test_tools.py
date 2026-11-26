# Try the tools by hand, WITHOUT any AI. Tools are just normal Python functions.
import db
import tools

db.init()
tools.state["user"] = "rajeev@testbank.com"   # pretend Rajeev is logged in

print("1. lookup_employee:", tools.lookup_employee("rajeev@testbank.com"))
print()
print("2. list_my_tickets:", tools.list_my_tickets())
print()
print("3. check_ticket_status T-1004:", tools.check_ticket_status("T-1004")["status"])
print()
print("4. check_ticket_status T-1001 (Mai's ticket):", tools.check_ticket_status("T-1001"))
print()
print("5. list_all_tickets as Rajeev (not an admin):", tools.list_all_tickets())
print()
tools.state["user"] = "it_helpdesk@testbank.com"   # now pretend the IT admin is logged in
print("6. list_all_tickets as the IT admin:", len(tools.list_all_tickets()["tickets"]), "tickets")
print()
print("7. check_ticket_status T-1001 as the IT admin:", tools.check_ticket_status("T-1001")["status"])
print()
result = tools.search_policies("What should I do if my laptop is stolen?")
print("8. search_policies (uses Gemini embedding):")
for p in result["passages"]:
    print("   ", p["file"], "page", p["page"], "-", p["text"][:80], "...")
