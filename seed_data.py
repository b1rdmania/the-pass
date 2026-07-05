"""
Seeds the Hackathon Test Xero org with 3 years of realistic hospitality
transaction history via the standard Accounting API, with eight deliberate
anomalies planted for The Pass to catch:

 1. Duplicate insurance payment (same payee, same amount, days apart)
 2. Wage spike vs flat sales in one month (absolute £ variance)
 3. Bank charges creeping up over the trailing 6 months (slow drift)
 4. A 2+ year unpaid electric bill sitting in payables
 5. A miscoded entertainment cost hitting Repairs & Maintenance
 6. Wage-to-sales ratio spike: sales dip but wages don't follow (ratio-only)
 7. Card processing fee rate hike: merchant fee % jumps for several months
 8. Comps blowout: complimentary food/drink given away spikes one month
"""

import json
import random
from datetime import date, timedelta

import requests

random.seed(7)

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
        print("ERROR", path, r.status_code, r.text[:800])
    r.raise_for_status()
    return r.json()


def post(path, body):
    r = requests.post(f"{BASE}/{path}", headers=H, json=body)
    if not r.ok:
        print("ERROR", path, r.status_code, r.text[:800])
    r.raise_for_status()
    return r.json()


# 1. Bank account -------------------------------------------------------------
accounts = get("Accounts")["Accounts"]
bank_acct = next((a for a in accounts if a.get("Type") == "BANK"), None)
if not bank_acct:
    resp = put("Accounts", {
        "Code": "090", "Name": "Business Current Account", "Type": "BANK",
        "BankAccountNumber": "12345678", "BankAccountType": "BANK", "CurrencyCode": "GBP",
    })
    bank_acct = resp["Accounts"][0]
BANK_ACCOUNT_ID = bank_acct["AccountID"]
print("Bank account:", bank_acct["Name"], BANK_ACCOUNT_ID)

# 2. Extra accounts not in the default chart ----------------------------------
by_code = {a["Code"]: a for a in accounts if a.get("Code")}
for code, name in [
    ("406", "Card Processing Fees"),
    ("407", "Comps & Complimentary"),
    ("820", "VAT Payments to HMRC"),
]:
    if code not in by_code:
        resp = put("Accounts", {"Code": code, "Name": name, "Type": "OVERHEADS", "TaxType": "NONE"})
        print("Created account", code, name)

# 3. Contacts -------------------------------------------------------------------
COGS_SUPPLIERS = {
    "Borough Wine & Spirits": 0.28,
    "Billingsgate Fish Merchants": 0.22,
    "Smithfield Meat Co": 0.20,
    "Fresh Fields Greengrocer": 0.18,
    "The Bakery Collective": 0.12,
}

CONTACT_NAMES = [
    "Zurich Insurance", "Bright Electric Co",
    "Staff Payroll", "Landlord Estates Ltd", "Metro Bank", "Daily Till Takings",
    "Card Payments Ltd", "The Riverside Trust - Private Dining", "HMRC",
] + list(COGS_SUPPLIERS.keys())
existing = {c["Name"]: c for c in get("Contacts")["Contacts"]}
contacts = {}
for name in CONTACT_NAMES:
    if name in existing:
        contacts[name] = existing[name]
    else:
        resp = put("Contacts", {"Contacts": [{"Name": name}]})
        contacts[name] = resp["Contacts"][0]
print("Contacts ready:", list(contacts.keys()))


def contact_ref(name):
    return {"ContactID": contacts[name]["ContactID"]}


# 4. Generate 3 years of monthly history ----------------------------------------
def month_range(start_year, start_month, n_months):
    y, m = start_year, start_month
    for _ in range(n_months):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


N_MONTHS = 36
months = list(month_range(2023, 7, N_MONTHS))  # Jul 2023 -> Jun 2026

bank_txns = []
sales_history = []  # trailing sales, used to size quarterly VAT payments

WAGE_SPIKE_MONTH = (2025, 10)          # absolute wage spike, flat sales
INSURANCE_DUP_MONTH = (2026, 3)        # paid Zurich twice
MISCODE_MONTH = (2025, 5)              # entertainment miscoded to repairs
FEE_CREEP_START_IDX = N_MONTHS - 6     # last 6 months: bank fees creep up
WAGE_RATIO_MONTH = (2024, 8)           # sales dip, wages stay flat -> ratio spike
CARD_FEE_HIKE_START = (2025, 12)       # card fee % jumps for a few months
CARD_FEE_HIKE_END = (2026, 2)
COMPS_BLOWOUT_MONTH = (2026, 1)        # comps spike

CARD_SHARE_OF_SALES = 0.65  # portion of takings paid by card, subject to processing fees
NORMAL_CARD_FEE_RATE = 0.014
HIKED_CARD_FEE_RATE = 0.027
NORMAL_COMPS_RATE = 0.008  # ~0.8% of sales given away as comps normally

for idx, (y, m) in enumerate(months):
    last_day = (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    mid = date(y, m, 15)

    seasonal = 1.15 if m in (12, 7, 8) else (0.9 if m in (1, 2) else 1.0)
    sales = round(45000 * seasonal * random.uniform(0.93, 1.07), 2)

    if (y, m) == WAGE_RATIO_MONTH:
        sales = round(sales * 0.72, 2)  # sales dip, unexplained

    if (y, m) == WAGE_SPIKE_MONTH:
        sales = round(45000 * random.uniform(0.95, 1.05), 2)  # flat vs prior month
        wages = round(12000 * 1.33, 2)
    else:
        base_wage_ratio = 12000 / 45000
        wages = round(sales * base_wage_ratio * random.uniform(0.97, 1.03), 2)
        if (y, m) == WAGE_RATIO_MONTH:
            wages = round(12000 * random.uniform(0.97, 1.03), 2)  # wages DON'T follow sales down

    cogs = round(sales * random.uniform(0.28, 0.32), 2)
    rent = round(4000.00 * (1.03 if idx > 24 else 1.0), 2)  # one rent review across 3 years

    if idx >= FEE_CREEP_START_IDX:
        step = idx - FEE_CREEP_START_IDX
        bank_fee = round(120 + step * 38 * random.uniform(0.9, 1.1), 2)
    else:
        bank_fee = round(120 * random.uniform(0.85, 1.15), 2)

    electric = round(1200 * (1 + idx * 0.008) * random.uniform(0.88, 1.12), 2)

    card_takings = round(sales * CARD_SHARE_OF_SALES, 2)
    if CARD_FEE_HIKE_START <= (y, m) <= CARD_FEE_HIKE_END:
        fee_rate = HIKED_CARD_FEE_RATE
    else:
        fee_rate = NORMAL_CARD_FEE_RATE * random.uniform(0.9, 1.1)
    card_fee = round(card_takings * fee_rate, 2)

    if (y, m) == COMPS_BLOWOUT_MONTH:
        comps = round(sales * NORMAL_COMPS_RATE * 4.5, 2)
    else:
        comps = round(sales * NORMAL_COMPS_RATE * random.uniform(0.7, 1.3), 2)

    # --- standard monthly lines ---
    bank_txns.append(("RECEIVE", "Daily Till Takings", last_day, "200", "Monthly till takings", sales))
    sales_history.append(sales)

    # split cost of sales across real suppliers rather than one generic line
    for supplier, share in COGS_SUPPLIERS.items():
        supplier_cost = round(cogs * share * random.uniform(0.92, 1.08), 2)
        supplier_day = date(y, m, random.randint(8, 24))
        bank_txns.append(("SPEND", supplier, supplier_day, "310", f"{supplier} - weekly delivery account", supplier_cost))

    # occasional private dining / corporate event booking (extra revenue on top of till takings)
    if random.random() < 0.35:
        booking_amount = round(random.uniform(1800, 4500), 2)
        bank_txns.append(("RECEIVE", "The Riverside Trust - Private Dining", date(y, m, random.randint(2, 27)), "200", "Private dining / corporate event booking", booking_amount))

    bank_txns.append(("SPEND", "Staff Payroll", last_day, "320", "Staff wages", wages))
    bank_txns.append(("SPEND", "Landlord Estates Ltd", date(y, m, 1), "469", "Monthly rent", rent))
    bank_txns.append(("SPEND", "Metro Bank", last_day, "404", "Bank charges", bank_fee))
    bank_txns.append(("SPEND", "Card Payments Ltd", last_day, "406", "Card processing fees", card_fee))
    bank_txns.append(("SPEND", "Daily Till Takings", last_day, "407", "Comps & complimentary items", comps))

    if (y, m) == MISCODE_MONTH:
        bank_txns.append(("SPEND", "The Riverside Trust - Private Dining", date(y, m, 20), "473", "Client hospitality - supplier launch dinner", 1850.00))

    bank_txns.append(("SPEND", "Bright Electric Co", date(y, m, 22), "445", "Electricity", electric))

    if m in (3, 6, 9, 12):
        bank_txns.append(("SPEND", "Zurich Insurance", date(y, m, 10), "433", "Quarterly insurance premium", 1800.00))
        if (y, m) == INSURANCE_DUP_MONTH:
            bank_txns.append(("SPEND", "Zurich Insurance", date(y, m, 13), "433", "Quarterly insurance premium", 1800.00))

        # quarterly VAT - deliberately clean, paid on time every quarter,
        # sized off trailing sales, no anomaly planted here on purpose
        trailing_sales = sum(sales_history[-3:])
        vat_amount = round(trailing_sales * 0.15 * random.uniform(0.97, 1.03), 2)
        bank_txns.append(("SPEND", "HMRC", date(y, m, 25), "820", "Quarterly VAT payment", vat_amount))

print(f"Generated {len(bank_txns)} bank transactions to post")


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


payload_txns = []
for (ttype, contact_name, d, code, desc, amount) in bank_txns:
    payload_txns.append({
        "Type": ttype,
        "Contact": contact_ref(contact_name),
        "Date": d.isoformat(),
        "BankAccount": {"AccountID": BANK_ACCOUNT_ID},
        "LineItems": [{
            "Description": desc, "Quantity": 1.0, "UnitAmount": amount, "AccountCode": code,
        }],
    })

posted = 0
for batch in chunk(payload_txns, 50):
    resp = post("BankTransactions", {"BankTransactions": batch})
    posted += len(resp.get("BankTransactions", []))
    print(f"  posted batch, running total {posted}")

print(f"Done: posted {posted} bank transactions")

# 5. Unpaid electric bill sitting for 2+ years --------------------------------
old_bill_date = date(2023, 9, 15)
due_date = old_bill_date + timedelta(days=30)
bill_resp = post("Invoices", {
    "Invoices": [{
        "Type": "ACCPAY",
        "Contact": contact_ref("Bright Electric Co"),
        "Date": old_bill_date.isoformat(),
        "DueDate": due_date.isoformat(),
        "Status": "AUTHORISED",
        "LineItems": [{
            "Description": "Site B - electricity account, never settled",
            "Quantity": 1.0, "UnitAmount": 2140.55, "AccountCode": "445",
        }],
    }]
})
print("Unpaid electric bill created:", bill_resp["Invoices"][0]["InvoiceID"], "- outstanding since", old_bill_date)

print("\nSEEDING COMPLETE. Anomalies planted:")
print(f"  1. Duplicate insurance payment: Zurich Insurance, {INSURANCE_DUP_MONTH}, £1,800 x2, 3 days apart")
print(f"  2. Wage spike: {WAGE_SPIKE_MONTH}, wages +33% on flat sales (absolute)")
print(f"  3. Bank fee creep: last 6 months, £120 -> ~£{bank_fee:.0f} (slow drift)")
print(f"  4. Unpaid electric bill: £2,140.55 outstanding since {old_bill_date}, still unpaid")
print(f"  5. Miscoded cost: {MISCODE_MONTH}, £1,850 client hospitality coded to Repairs & Maintenance (473)")
print(f"  6. Wage-to-sales ratio spike: {WAGE_RATIO_MONTH}, sales dip ~28% but wages held flat")
print(f"  7. Card fee rate hike: {CARD_FEE_HIKE_START} - {CARD_FEE_HIKE_END}, merchant fee {NORMAL_CARD_FEE_RATE*100:.1f}% -> {HIKED_CARD_FEE_RATE*100:.1f}%")
print(f"  8. Comps blowout: {COMPS_BLOWOUT_MONTH}, complimentary give-aways ~4.5x normal rate")
