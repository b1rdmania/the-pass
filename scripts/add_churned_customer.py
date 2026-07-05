"""
Adds a genuine customer-churn scenario: a corporate client who booked
private events monthly for 6 months, then went completely silent for
over a year. This is the other Cash Flow Accelerator bounty example we
hadn't covered - detecting a high-value customer who hasn't returned,
and triggering outreach, as distinct from the aged-receivables chase.

Additive only.
"""

import json
from datetime import date

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


accounts = get("Accounts")["Accounts"]
bank_acct = next(a for a in accounts if a.get("Type") == "BANK")
BANK_ACCOUNT_ID = bank_acct["AccountID"]

existing = {c["Name"]: c for c in get("Contacts")["Contacts"]}
CONTACT_NAME = "Borough Films Ltd - Wrap Parties"
if CONTACT_NAME not in existing:
    resp = put("Contacts", {"Contacts": [{"Name": CONTACT_NAME}]})
    existing[CONTACT_NAME] = resp["Contacts"][0]
    print("Created contact:", CONTACT_NAME)

contact_ref = {"ContactID": existing[CONTACT_NAME]["ContactID"]}

# 6 consecutive monthly bookings (Dec 2024 - May 2025), then nothing since -
# over a year of silence from what was a reliably monthly high-value client
BOOKING_DATES_AMOUNTS = [
    (date(2024, 12, 12), 2850.00),
    (date(2025, 1, 15), 3120.00),
    (date(2025, 2, 11), 2640.00),
    (date(2025, 3, 14), 3380.00),
    (date(2025, 4, 10), 2975.00),
    (date(2025, 5, 13), 3560.00),
]

txns = []
for d, amount in BOOKING_DATES_AMOUNTS:
    txns.append({
        "Type": "RECEIVE",
        "Contact": contact_ref,
        "Date": d.isoformat(),
        "BankAccount": {"AccountID": BANK_ACCOUNT_ID},
        "LineItems": [{
            "Description": "Wrap party / production event booking",
            "Quantity": 1.0,
            "UnitAmount": amount,
            "AccountCode": "200",
        }],
    })

resp = post("BankTransactions", {"BankTransactions": txns})
print(f"Posted {len(resp.get('BankTransactions', []))} historical bookings for {CONTACT_NAME}")
print(f"Last booking: {BOOKING_DATES_AMOUNTS[-1][0].isoformat()} - "
      f"{(date.today() - BOOKING_DATES_AMOUNTS[-1][0]).days} days ago, no bookings since.")
print(f"Average historical spend: £{sum(a for _, a in BOOKING_DATES_AMOUNTS) / len(BOOKING_DATES_AMOUNTS):,.2f}/visit")
