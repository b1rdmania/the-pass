"""
The Pass: detection engine.

Three deterministic checks over Xero data, pulled via the standard
Accounting API:
  1. Duplicate payment detector - same contact + same amount within a
     short window.
  2. Variance detector - per-account monthly totals vs trailing 3-month
     average, flagged when the deviation is large and the amount is
     material. Catches wage spikes, bank-fee creep, and miscoded costs
     with one generic rule.
  3. Aged payables detector - unpaid bills sitting open past a threshold.

Outputs findings.json - a flat list of structured findings ready to be
handed to the narrative layer.
"""

import json
from collections import defaultdict
from datetime import date, datetime

import requests

with open("xero_tokens.json") as f:
    data = json.load(f)

TOKEN = data["tokens"]["access_token"]
TENANT = data["connections"][0]["tenantId"]
H = {
    "Authorization": f"Bearer {TOKEN}",
    "Xero-tenant-id": TENANT,
    "Accept": "application/json",
}
BASE = "https://api.xero.com/api.xro/2.0"

ACCOUNT_NAMES = {
    "200": "Sales",
    "310": "Cost of Goods Sold",
    "320": "Direct Wages",
    "404": "Bank Fees",
    "406": "Card Processing Fees",
    "407": "Comps & Complimentary",
    "433": "Insurance",
    "445": "Light, Power, Heating",
    "469": "Rent",
    "473": "Repairs & Maintenance",
    "WET": "Wet Cost of Sales (drinks)",
    "DRY": "Dry Cost of Sales (food)",
}

# classic pub KPI: cost of sales split by supplier type, not just one lumped
# COGS line - lets us flag "your drinks cost ratio moved" separately from food
WET_SUPPLIERS = {"Borough Wine & Spirits"}
DRY_SUPPLIERS = {"Billingsgate Fish Merchants", "Smithfield Meat Co", "Fresh Fields Greengrocer", "The Bakery Collective"}

RATIO_PAIRS = [
    ("320", "200", "Wages-to-sales ratio"),
    ("406", "200", "Card fee rate (of sales)"),
    ("407", "200", "Comps rate (of sales)"),
    ("WET", "200", "Wet cost ratio (drinks, of sales)"),
    ("DRY", "200", "Dry cost ratio (food, of sales)"),
]
RATIO_DEVIATION_THRESHOLD = 0.18  # 18% deviation from trailing ratio average

VARIANCE_THRESHOLD = 0.20  # 20% deviation
MIN_MATERIAL_AMOUNT = 150  # ignore noise below this
DUP_WINDOW_DAYS = 14
AGED_PAYABLE_DAYS = 180
AGED_RECEIVABLE_DAYS = 14  # money owed TO the business - a much shorter fuse than payables


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


def parse_xero_date(s):
    # Xero returns dates like "/Date(1700000000000+0000)/"
    if s.startswith("/Date("):
        ms = int(s[6:].split("+")[0].split("-")[0])
        return datetime.utcfromtimestamp(ms / 1000).date()
    return datetime.fromisoformat(s[:10]).date()


txns = get_all("BankTransactions", "BankTransactions", where='Status=="AUTHORISED"')
print(f"Pulled {len(txns)} bank transactions")

findings = []

# --- 1. Duplicate payment detector ------------------------------------------
by_contact = defaultdict(list)
for t in txns:
    if t["Type"] != "SPEND":
        continue
    contact = t["Contact"]["Name"]
    d = parse_xero_date(t["Date"])
    amount = t["Total"]
    by_contact[contact].append((d, amount, t))

for contact, entries in by_contact.items():
    entries.sort(key=lambda e: e[0])
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            d1, a1, t1 = entries[i]
            d2, a2, t2 = entries[j]
            if (d2 - d1).days > DUP_WINDOW_DAYS:
                break
            if abs(a1 - a2) < 0.01:
                findings.append({
                    "type": "duplicate_payment",
                    "severity": "high",
                    "contact": contact,
                    "amount": a1,
                    "estimated_impact": round(a1, 2),
                    "dates": [d1.isoformat(), d2.isoformat()],
                    "bank_transaction_ids": [t1["BankTransactionID"], t2["BankTransactionID"]],
                    "summary": f"{contact} paid twice: £{a1:,.2f} on {d1.isoformat()} and again on {d2.isoformat()}, {(d2-d1).days} days apart.",
                })

# --- 2. Variance detector (per account, per month) --------------------------
monthly = defaultdict(lambda: defaultdict(float))  # account_code -> "YYYY-MM" -> total
monthly_txn_ids = defaultdict(lambda: defaultdict(list))  # account_code -> "YYYY-MM" -> [BankTransactionID]
for t in txns:
    # include both SPEND and RECEIVE - Sales (a RECEIVE) is needed as the
    # denominator for ratio checks, and each account code here only ever
    # appears on one side anyway.
    contact_name = t["Contact"]["Name"]
    if contact_name in WET_SUPPLIERS:
        wet_dry_code = "WET"
    elif contact_name in DRY_SUPPLIERS:
        wet_dry_code = "DRY"
    else:
        wet_dry_code = None

    for li in t.get("LineItems", []):
        code = li.get("AccountCode")
        d = parse_xero_date(t["Date"])
        key = f"{d.year:04d}-{d.month:02d}"
        amount = li.get("LineAmount", li.get("UnitAmount", 0))
        monthly[code][key] += amount
        monthly_txn_ids[code][key].append(t["BankTransactionID"])

        # also split cost of sales by supplier type - a lumped "310" total
        # hides whether it's the bar or the kitchen driving a cost move
        if wet_dry_code:
            monthly[wet_dry_code][key] += amount
            monthly_txn_ids[wet_dry_code][key].append(t["BankTransactionID"])

DRIFT_THRESHOLD = 0.5  # 50% drift vs 6-months-ago baseline

for code, series in monthly.items():
    months_sorted = sorted(series.keys())

    # (a) sudden month-on-month variance vs trailing 3-month average
    for idx, m in enumerate(months_sorted):
        if idx < 3:
            continue
        trailing = [series[months_sorted[idx - k]] for k in (1, 2, 3)]
        avg = sum(trailing) / 3
        current = series[m]
        if avg <= 0:
            continue
        deviation = (current - avg) / avg
        if abs(deviation) >= VARIANCE_THRESHOLD and current >= MIN_MATERIAL_AMOUNT and code != "200":
            # skip Sales (200) for £-impact framing - a sales dip isn't "leakage",
            # it still shows up via the ratio checks where relevant
            findings.append({
                "type": "variance",
                "severity": "medium" if abs(deviation) < 0.4 else "high",
                "account_code": code,
                "account_name": ACCOUNT_NAMES.get(code, code),
                "month": m,
                "current": round(current, 2),
                "trailing_avg": round(avg, 2),
                "deviation_pct": round(deviation * 100, 1),
                "estimated_impact": round(abs(current - avg), 2),
                "bank_transaction_ids": monthly_txn_ids[code][m],
                "summary": f"{ACCOUNT_NAMES.get(code, code)} in {m}: £{current:,.2f} vs trailing 3-month average £{avg:,.2f} ({deviation*100:+.0f}%).",
            })

    # (b) slow creep vs a distant baseline (6 months back), catches gradual drift
    #     that a 3-month trailing average smooths away
    if len(months_sorted) >= 7:
        latest_m = months_sorted[-1]
        baseline_m = months_sorted[-7]
        latest_val = series[latest_m]
        baseline_val = series[baseline_m]
        if baseline_val > 0:
            drift = (latest_val - baseline_val) / baseline_val
            if drift >= DRIFT_THRESHOLD and latest_val >= MIN_MATERIAL_AMOUNT and code != "200":
                # rough cumulative excess over the creep window vs the old baseline
                creep_months = [series[months_sorted[-k]] for k in range(1, 7) if len(months_sorted) >= k]
                cumulative_excess = sum(max(0, v - baseline_val) for v in creep_months)
                findings.append({
                    "type": "drift",
                    "severity": "medium",
                    "account_code": code,
                    "account_name": ACCOUNT_NAMES.get(code, code),
                    "from_month": baseline_m,
                    "to_month": latest_m,
                    "from_value": round(baseline_val, 2),
                    "to_value": round(latest_val, 2),
                    "drift_pct": round(drift * 100, 1),
                    "estimated_impact": round(cumulative_excess, 2),
                    "bank_transaction_ids": monthly_txn_ids[code][latest_m] + monthly_txn_ids[code][baseline_m],
                    "summary": f"{ACCOUNT_NAMES.get(code, code)} has crept up £{baseline_val:,.2f} ({baseline_m}) to £{latest_val:,.2f} ({latest_m}), a slow {drift*100:+.0f}% rise a monthly snapshot wouldn't catch.",
                })

    # (c) novel account activity: a code with only 1-2 months of any history ever,
    #     and a material amount - classic sign of a one-off miscoded transaction
    non_zero_months = [k for k, v in series.items() if v > 0]
    if 0 < len(non_zero_months) <= 2:
        for m in non_zero_months:
            amt = series[m]
            if amt >= MIN_MATERIAL_AMOUNT and code != "200":
                findings.append({
                    "type": "novel_account_activity",
                    "severity": "medium",
                    "account_code": code,
                    "account_name": ACCOUNT_NAMES.get(code, code),
                    "month": m,
                    "amount": round(amt, 2),
                    "estimated_impact": round(amt, 2),
                    "bank_transaction_ids": monthly_txn_ids[code][m],
                    "summary": f"{ACCOUNT_NAMES.get(code, code)} almost never has activity, but £{amt:,.2f} was coded there in {m} - worth checking it's not miscoded.",
                })

# --- 3. Ratio anomaly detector (cross-account) -------------------------------
# Catches issues that hide inside a ratio even when the raw £ looks fine:
# wages that don't fall when sales do, a merchant fee rate creeping up,
# comps blowing out relative to takings.
all_ratio_series = {}  # label -> {month: ratio} - exported for charting

for numerator_code, denominator_code, label in RATIO_PAIRS:
    num_series = monthly.get(numerator_code, {})
    den_series = monthly.get(denominator_code, {})
    common_months = sorted(set(num_series) & set(den_series))
    ratios = {}
    for m in common_months:
        if den_series[m] > 0:
            ratios[m] = num_series[m] / den_series[m]
    all_ratio_series[label] = ratios

    ratio_months = sorted(ratios.keys())
    for idx, m in enumerate(ratio_months):
        if idx < 3:
            continue
        trailing = [ratios[ratio_months[idx - k]] for k in (1, 2, 3)]
        avg_ratio = sum(trailing) / 3
        current_ratio = ratios[m]
        if avg_ratio <= 0:
            continue
        deviation = (current_ratio - avg_ratio) / avg_ratio
        if abs(deviation) >= RATIO_DEVIATION_THRESHOLD:
            # £ impact = the ratio-point gap applied back to that month's sales base
            excess_amount = (current_ratio - avg_ratio) * den_series[m]
            findings.append({
                "type": "ratio_anomaly",
                "severity": "medium" if abs(deviation) < 0.5 else "high",
                "label": label,
                "month": m,
                "current_ratio_pct": round(current_ratio * 100, 2),
                "trailing_avg_ratio_pct": round(avg_ratio * 100, 2),
                "deviation_pct": round(deviation * 100, 1),
                "estimated_impact": round(abs(excess_amount), 2),
                "bank_transaction_ids": monthly_txn_ids[numerator_code][m],
                "summary": f"{label} in {m}: {current_ratio*100:.1f}% vs usual {avg_ratio*100:.1f}% ({deviation*100:+.0f}%), even though the raw pound amounts alone might look fine.",
            })

# --- 4. Aged payables detector -----------------------------------------------
bills = get_all("Invoices", "Invoices", where='Type=="ACCPAY"')
today = date.today()
for b in bills:
    if b.get("Status") not in ("AUTHORISED", "SUBMITTED"):
        continue
    amount_due = b.get("AmountDue", 0)
    if amount_due <= 0:
        continue
    due = parse_xero_date(b["DueDate"])
    days_overdue = (today - due).days
    if days_overdue >= AGED_PAYABLE_DAYS:
        findings.append({
            "type": "aged_payable",
            "severity": "high",
            "contact": b["Contact"]["Name"],
            "amount_due": amount_due,
            "estimated_impact": round(amount_due, 2),
            "due_date": due.isoformat(),
            "days_overdue": days_overdue,
            "invoice_id": b["InvoiceID"],
            "summary": f"{b['Contact']['Name']}: £{amount_due:,.2f} unpaid, {days_overdue} days overdue (due {due.isoformat()}).",
        })

# --- 5. Aged receivables detector (Cash Flow Accelerator crossover) ----------
# Money owed TO the business, not by it - this is the revenue-side check:
# predicting a late-paying customer so a chase can be sent before it becomes
# a write-off, not just tidying up cost leakage.
receivable_invoices = get_all("Invoices", "Invoices", where='Type=="ACCREC"')
for inv in receivable_invoices:
    if inv.get("Status") not in ("AUTHORISED", "SUBMITTED"):
        continue
    amount_due = inv.get("AmountDue", 0)
    if amount_due <= 0:
        continue
    due = parse_xero_date(inv["DueDate"])
    days_overdue = (today - due).days
    if days_overdue >= AGED_RECEIVABLE_DAYS:
        findings.append({
            "type": "aged_receivable",
            "severity": "high" if days_overdue >= 30 else "medium",
            "contact": inv["Contact"]["Name"],
            "amount_due": amount_due,
            "estimated_impact": round(amount_due, 2),
            "due_date": due.isoformat(),
            "days_overdue": days_overdue,
            "invoice_id": inv["InvoiceID"],
            "summary": f"{inv['Contact']['Name']} owes £{amount_due:,.2f}, {days_overdue} days overdue (due {due.isoformat()}) - worth chasing before it becomes a write-off.",
        })

# --- 6. Customer churn / win-back detector (Cash Flow Accelerator crossover) -
# The other revenue-side check the bounty names explicitly: a high-value
# repeat customer who's gone quiet, worth a win-back nudge before they're
# fully lost - as distinct from the aged-receivables chase (money already
# owed) or cost-leakage detection (money already spent).
EXCLUDE_FROM_CHURN_CHECK = {"Daily Till Takings"}
MIN_BOOKINGS_FOR_PATTERN = 3

receive_by_contact = defaultdict(list)
for t in txns:
    if t["Type"] != "RECEIVE":
        continue
    contact = t["Contact"]["Name"]
    if contact in EXCLUDE_FROM_CHURN_CHECK:
        continue
    d = parse_xero_date(t["Date"])
    receive_by_contact[contact].append((d, t["Total"], t["BankTransactionID"]))

for contact, entries in receive_by_contact.items():
    if len(entries) < MIN_BOOKINGS_FOR_PATTERN:
        continue
    entries.sort(key=lambda e: e[0])
    dates = [e[0] for e in entries]
    amounts = [e[1] for e in entries]
    intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    avg_interval = sum(intervals) / len(intervals)
    avg_spend = sum(amounts) / len(amounts)
    days_since_last = (today - dates[-1]).days
    threshold = max(90, avg_interval * 2)
    if days_since_last >= threshold:
        findings.append({
            "type": "customer_churn",
            "severity": "high" if avg_spend >= 1000 else "medium",
            "contact": contact,
            "avg_spend": round(avg_spend, 2),
            "n_historical_bookings": len(entries),
            "days_since_last": days_since_last,
            "last_booking_date": dates[-1].isoformat(),
            "estimated_impact": round(avg_spend, 2),
            "bank_transaction_ids": [e[2] for e in entries],
            "summary": f"{contact}: {len(entries)} bookings averaging £{avg_spend:,.2f}, then nothing for {days_since_last} days (last booked {dates[-1].isoformat()}) - a high-value customer who's gone quiet.",
        })

findings.sort(key=lambda f: {"high": 0, "medium": 1, "low": 2}[f["severity"]])

with open("findings.json", "w") as f:
    json.dump(findings, f, indent=2)

# export monthly time series for charting - real per-account totals and
# ratio series, not just the flagged deviation points
timeseries = {
    "accounts": {code: dict(series) for code, series in monthly.items()},
    "ratios": {label: dict(ratios) for label, ratios in all_ratio_series.items()},
}
with open("timeseries.json", "w") as f:
    json.dump(timeseries, f, indent=2)

print(f"\n{len(findings)} findings written to findings.json:\n")
for f in findings:
    print(f"  [{f['severity'].upper()}] {f['summary']}")
