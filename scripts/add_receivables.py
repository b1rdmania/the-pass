"""
Adds genuine accounts-receivable data - customers who owe THE BUSINESS
money, as opposed to the aged_payable check (bills the business owes
suppliers). This is the real data behind the Cash Flow Accelerator
crossover: predicting late customer payments and drafting a chase,
not just cost-leakage detection.

Additive only - doesn't touch existing seeded bank transactions.
"""

import json
from datetime import date, timedelta

import requests

with open("xero_tokens.json") as f:
    data = json.load(f)

TOKEN = data["tokens"]["access_token"]
TENANT = data["connections"][0]["tenantId"]
H = {
    "Authorization": f"Bearer {TOKEN}",
    "Xero-tenant-id": TENANT,
    "Accept": "application/json",
    "Content-Type": "application/json",
}
BASE = "https://api.xero.com/api.xro/2.0"


def get(path, **params):
    r = requests.get(f"{BASE}/{path}", headers=H, params=params)
    r.raise_for_status()
    return r.json()


def put(path, body):
    r = requests.put(f"{BASE}/{path}", headers=H, json=body)
    if not r.ok:
        print("ERROR", path, r.status_code, r.text[:500])
    r.raise_for_status()
    return r.json()


def post(path, body):
    r = requests.post(f"{BASE}/{path}", headers=H, json=body)
    if not r.ok:
        print("ERROR", path, r.status_code, r.text[:500])
    r.raise_for_status()
    return r.json()


existing = {c["Name"]: c for c in get("Contacts")["Contacts"]}

NEW_CONTACTS = ["The Camden Collective - Corporate Events", "Northside Brewery Co-Marketing"]
for name in NEW_CONTACTS:
    if name not in existing:
        resp = put("Contacts", {"Contacts": [{"Name": name}]})
        existing[name] = resp["Contacts"][0]
        print("Created contact:", name)


def contact_ref(name):
    return {"ContactID": existing[name]["ContactID"]}


invoices = [
    # a genuinely overdue receivable - a repeat corporate client, 47 days
    # overdue on a private-dining invoice - this is the "predict a late
    # payment" signal
    {
        "date": date(2026, 5, 10),
        "due": date(2026, 5, 24),
        "contact": "The Camden Collective - Corporate Events",
        "amount": 3250.00,
        "desc": "Private dining event - 40 covers, 10 May 2026",
    },
    # a second, smaller overdue one from the same repeat client - pattern,
    # not a one-off
    {
        "date": date(2026, 4, 3),
        "due": date(2026, 4, 17),
        "contact": "The Camden Collective - Corporate Events",
        "amount": 1180.00,
        "desc": "Private dining event - 15 covers, 3 April 2026",
    },
    # a normal, not-yet-due invoice - control case, shouldn't be flagged
    {
        "date": date(2026, 6, 20),
        "due": date(2026, 7, 18),
        "contact": "Northside Brewery Co-Marketing",
        "amount": 600.00,
        "desc": "Co-marketing / tap takeover contribution",
    },
]

for inv in invoices:
    resp = post("Invoices", {
        "Invoices": [{
            "Type": "ACCREC",
            "Contact": contact_ref(inv["contact"]),
            "Date": inv["date"].isoformat(),
            "DueDate": inv["due"].isoformat(),
            "Status": "AUTHORISED",
            "LineItems": [{
                "Description": inv["desc"],
                "Quantity": 1.0,
                "UnitAmount": inv["amount"],
                "AccountCode": "200",
            }],
        }]
    })
    invoice_id = resp["Invoices"][0]["InvoiceID"]
    days_overdue = (date.today() - inv["due"]).days
    print(f"Created ACCREC invoice {invoice_id}: {inv['contact']} - £{inv['amount']:.2f}, "
          f"{'overdue by ' + str(days_overdue) + ' days' if days_overdue > 0 else 'not yet due'}")

print("\nDone. Real accounts-receivable data added for the Cash Flow Accelerator crossover.")
