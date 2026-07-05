"""Deletes previously-seeded BankTransactions and Bills so we can reseed cleanly."""

import json

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


def get_all(path, key, **params):
    items = []
    page = 1
    while True:
        p = dict(params)
        p["page"] = page
        r = requests.get(f"{BASE}/{path}", headers=H, params=p)
        r.raise_for_status()
        batch = r.json().get(key, [])
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


txns = get_all("BankTransactions", "BankTransactions")
print(f"Deleting {len(txns)} bank transactions...")
for i in range(0, len(txns), 50):
    batch = txns[i:i + 50]
    body = {"BankTransactions": [
        {"BankTransactionID": t["BankTransactionID"], "Status": "DELETED"} for t in batch
    ]}
    r = requests.post(f"{BASE}/BankTransactions", headers=H, json=body)
    if not r.ok:
        print("  error deleting batch:", r.status_code, r.text[:300])
    else:
        print(f"  deleted batch of {len(batch)}")

bills = get_all("Invoices", "Invoices", where='Type=="ACCPAY"')
print(f"Voiding {len(bills)} bills...")
for b in bills:
    if b["Status"] in ("AUTHORISED", "SUBMITTED"):
        r = requests.post(f"{BASE}/Invoices/{b['InvoiceID']}", headers=H, json={"Status": "VOIDED"})
        if not r.ok:
            print("  error voiding bill:", r.status_code, r.text[:300])
        else:
            print(f"  voided bill {b['InvoiceID']}")

print("Cleanup done.")
