"""
The Pass: accountant / financial controller reconciliation report.

A second, distinct output from the same findings.json - not the owner-
facing plain-English dashboard, but a technical action list grouped by
what a bookkeeper/controller actually needs to DO: reclassify, verify,
chase, or review a trend. Full detail (including monitor-tier findings
the owner dashboard summarises away), real Xero record links, precise
figures - written for someone who reconciles books for a living.
"""

import json
import urllib.parse
from collections import defaultdict
from datetime import date

import requests

with open("findings.json") as f:
    findings = json.load(f)

with open("xero_tokens.json") as f:
    _tok = json.load(f)
_token = _tok["tokens"]["access_token"]
_tenant = _tok["connections"][0]["tenantId"]
_h = {"Authorization": f"Bearer {_token}", "Xero-tenant-id": _tenant, "Accept": "application/json"}
try:
    _org = requests.get("https://api.xero.com/api.xro/2.0/Organisation", headers=_h).json()["Organisations"][0]
    ORG_NAME = _org["Name"]
    SHORT_CODE = _org["ShortCode"]
except Exception:
    ORG_NAME, SHORT_CODE = "Hackathon Test", None


def _deep_link(inner_path):
    if not SHORT_CODE:
        return None
    return f"https://go.xero.com/organisationlogin/default.aspx?shortcode={SHORT_CODE}&redirecturl={urllib.parse.quote(inner_path, safe='')}"


def bank_txn_link(txn_id):
    return _deep_link(f"/Bank/ViewTransaction.aspx?bankTransactionID={txn_id}")


def invoice_link(invoice_id):
    return _deep_link(f"/AccountsPayable/Edit.aspx?InvoiceID={invoice_id}")


def links_for(f):
    links = []
    if f.get("invoice_id"):
        u = invoice_link(f["invoice_id"])
        if u:
            links.append((u, "invoice"))
    for txn_id in (f.get("bank_transaction_ids") or [])[:5]:  # cap for brevity in a formal doc
        u = bank_txn_link(txn_id)
        if u:
            links.append((u, "transaction"))
    return links


# --- group by required accounting action, not by owner-facing theme --------
ACTION_GROUPS = [
    {
        "heading": "Requires reclassification",
        "match": lambda f: f["type"] == "novel_account_activity",
        "note": "Transaction sitting in an account code with no other history this period - confirm correct coding.",
    },
    {
        "heading": "Requires verification / possible reversal",
        "match": lambda f: f["type"] == "duplicate_payment",
        "note": "Two payments to the same payee, same amount, within 14 days - confirm not a duplicate before next reconciliation.",
    },
    {
        "heading": "Requires collection action (receivables)",
        "match": lambda f: f["type"] == "aged_receivable",
        "note": "Customer invoice overdue - action per credit control policy.",
    },
    {
        "heading": "Requires payment / dispute resolution (payables)",
        "match": lambda f: f["type"] == "aged_payable",
        "note": "Supplier bill unpaid past normal terms - confirm status (paid outside system, disputed, or genuinely outstanding).",
    },
    {
        "heading": "Cost trend review",
        "match": lambda f: f["type"] in ("variance", "drift", "ratio_anomaly"),
        "note": "Statistical deviation from trailing average - not necessarily an error, but worth a look during review.",
    },
    {
        "heading": "Revenue / customer relationship flag (for controller awareness)",
        "match": lambda f: f["type"] == "customer_churn",
        "note": "Not a bookkeeping item - flagged for revenue forecasting and credit-control awareness.",
    },
]

grouped = defaultdict(list)
for f in findings:
    for g in ACTION_GROUPS:
        if g["match"](f):
            grouped[g["heading"]].append(f)
            break

today_str = date.today().isoformat()
total_flagged = len(findings)
total_impact_all = sum(f.get("estimated_impact", 0) for f in findings)

# all categories render on one page - a controller scans the whole review
# top to bottom, and one scroll beats seven clicks
category_pages = []
for g in ACTION_GROUPS:
    items = grouped.get(g["heading"], [])
    if not items:
        continue
    rows_html = ""
    for f in items:
        links = links_for(f)
        links_html = " &middot; ".join(f'<a href="{u}" target="_blank">{label} &#8599;</a>' for u, label in links) or "&mdash;"
        impact = f.get("estimated_impact")
        impact_str = f"£{impact:,.2f}" if impact is not None else "&mdash;"
        rows_html += f"""
        <tr>
          <td>{f['type']}</td>
          <td>{f['severity']}</td>
          <td>{f['summary']}</td>
          <td>{impact_str}</td>
          <td>{links_html}</td>
        </tr>"""
    category_pages.append(f"""
    <section>
      <h2>{g['heading']} <span class="count">({len(items)})</span></h2>
      <p class="note">{g['note']}</p>
      <table>
        <thead><tr><th>Type</th><th>Severity</th><th>Detail</th><th>£ Impact</th><th>Xero record</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>
    """)

header_html = f"""
  <h1>Reconciliation Review — {ORG_NAME}</h1>
  <div class="meta">Prepared by The Pass · {today_str} · 36-month period reviewed ·
    <a href="index.html">&larr; owner dashboard</a></div>
  <div class="summary">
    <strong>{total_flagged}</strong> items flagged for review across {len(category_pages)} categories,
    <strong>£{total_impact_all:,.2f}</strong> aggregate value referenced in this review (includes both
    confirmed and monitor-tier items — see individual severity ratings; not all items represent an
    error or loss, some are statistical deviations worth a second look during your normal review cycle).
  </div>
"""

pages_html = header_html + "".join(category_pages)

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reconciliation Review — {ORG_NAME}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html {{ color-scheme: light; background: #ffffff; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 900px; margin: 0 auto; padding: 3rem 2rem; color: #1a1a1a; line-height: 1.5; background: #ffffff; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.2rem; }}
  .meta {{ color: #555; font-size: 0.9rem; margin-bottom: 2rem; font-family: Arial, sans-serif; }}
  .summary {{ background: #f4f4f2; border: 1px solid #ccc; padding: 1rem 1.5rem; margin-bottom: 2.5rem; font-family: Arial, sans-serif; font-size: 0.95rem; }}
  section {{ margin-bottom: 2.5rem; }}
  h2 {{ font-size: 1.15rem; border-bottom: 2px solid #1a1a1a; padding-bottom: 0.3rem; margin-bottom: 0.4rem; font-family: Arial, sans-serif; }}
  .count {{ color: #777; font-weight: normal; }}
  .note {{ font-style: italic; color: #555; font-size: 0.9rem; margin-bottom: 0.8rem; font-family: Arial, sans-serif; }}
  table {{ width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 0.85rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #ddd; vertical-align: top; }}
  th {{ background: #eee; font-weight: 700; }}
  a {{ color: #1a4b7a; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ccc; font-size: 0.8rem; color: #777; font-family: Arial, sans-serif; }}

</style>
</head>
<body>
  {pages_html}

  <footer>
    Methodology: deterministic detection over the Xero Accounting API (duplicate-payment matching,
    3-month trailing-average variance, 6-month baseline drift, cross-account ratio analysis, aged
    payables/receivables). Xero record links use the organisation's short-code redirect and open
    directly into the live record. This document does not replace professional judgement or a full
    audit - treat it as a triage list for your next reconciliation pass.
  </footer>

</body>
</html>
"""

with open("accountant_report.html", "w") as f:
    f.write(html)

print(f"Rendered accountant_report.html — {total_flagged} items across {sum(1 for g in ACTION_GROUPS if grouped.get(g['heading']))} categories")
