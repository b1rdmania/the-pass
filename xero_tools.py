"""
The Pass: agent tool layer.

Real, callable functions over LIVE Xero data - the Accounting API's
Reports endpoints (ProfitAndLoss, AgedPayablesByContact) plus direct
BankTransactions/Invoices queries. These are exposed to Claude as tool
definitions in server.py so the model decides what to fetch, rather than
us pre-computing everything and handing over a static JSON blob.

Also includes one tool routed through Xero's actual Remote MCP Server
(xero_mcp_client.py) rather than the plain REST API - both integration
paths are real and live, not just the REST one.
"""

import json

import requests

import xero_mcp_client

BASE = "https://api.xero.com/api.xro/2.0"

_mcp_client = None


def _get_mcp_client():
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = xero_mcp_client.connect()
    return _mcp_client


def _headers():
    with open("xero_tokens.json") as f:
        data = json.load(f)
    return {
        "Authorization": f"Bearer {data['tokens']['access_token']}",
        "Xero-tenant-id": data["connections"][0]["tenantId"],
        "Accept": "application/json",
    }


def _flatten_report(report):
    """Flattens a Xero Reports API response (nested Rows/Cells) into a
    simple list of {label, values} rows - much easier for an LLM to reason
    over than the raw nested structure."""
    flat = []

    def walk(rows):
        for row in rows:
            if row.get("RowType") == "Section":
                walk(row.get("Rows", []))
            else:
                cells = row.get("Cells", [])
                if cells:
                    label = cells[0].get("Value", "")
                    values = [c.get("Value", "") for c in cells[1:]]
                    if label:
                        flat.append({"label": label, "values": values})

    for r in report.get("Reports", []):
        walk(r.get("Rows", []))
    return flat


def get_profit_and_loss(from_date, to_date):
    """Pulls Xero's own computed Profit & Loss report for a date range."""
    r = requests.get(f"{BASE}/Reports/ProfitAndLoss", headers=_headers(),
                      params={"fromDate": from_date, "toDate": to_date})
    r.raise_for_status()
    return {"period": f"{from_date} to {to_date}", "rows": _flatten_report(r.json())}


def get_aged_payables_for_contact(contact_name):
    """Pulls Xero's own Aged Payables report for a named contact."""
    contacts = requests.get(f"{BASE}/Contacts", headers=_headers(),
                             params={"where": f'Name=="{contact_name}"'}).json()["Contacts"]
    if not contacts:
        return {"error": f"no contact found matching '{contact_name}'"}
    contact_id = contacts[0]["ContactID"]
    r = requests.get(f"{BASE}/Reports/AgedPayablesByContact", headers=_headers(),
                      params={"contactID": contact_id})
    r.raise_for_status()
    return {"contact": contact_name, "rows": _flatten_report(r.json())}


def get_aged_receivables_for_contact(contact_name):
    """Pulls Xero's own Aged Receivables report for a named contact - money
    owed TO the business, the revenue/cash-flow side of things."""
    contacts = requests.get(f"{BASE}/Contacts", headers=_headers(),
                             params={"where": f'Name=="{contact_name}"'}).json()["Contacts"]
    if not contacts:
        return {"error": f"no contact found matching '{contact_name}'"}
    contact_id = contacts[0]["ContactID"]
    r = requests.get(f"{BASE}/Reports/AgedReceivablesByContact", headers=_headers(),
                      params={"contactID": contact_id})
    r.raise_for_status()
    return {"contact": contact_name, "rows": _flatten_report(r.json())}


def list_bank_transactions(account_code=None, contact_name=None, month=None, transaction_type=None):
    """Lists bank transactions, optionally filtered by account code, contact
    name, month (YYYY-MM), or type (SPEND/RECEIVE)."""
    # NB: the list endpoint silently omits LineItems unless "page" is passed
    # explicitly (undocumented Xero quirk) - always paginate to get full detail.
    txns = []
    page = 1
    while True:
        r = requests.get(f"{BASE}/BankTransactions", headers=_headers(),
                          params={"where": 'Status=="AUTHORISED"', "page": page})
        r.raise_for_status()
        batch = r.json().get("BankTransactions", [])
        txns.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    def date_of(t):
        s = t["Date"]
        if s.startswith("/Date("):
            import datetime
            ms = int(s[6:].split("+")[0].split("-")[0])
            return datetime.datetime.utcfromtimestamp(ms / 1000).date()
        return None

    results = []
    for t in txns:
        if transaction_type and t["Type"] != transaction_type:
            continue
        if contact_name and contact_name.lower() not in t["Contact"]["Name"].lower():
            continue
        d = date_of(t)
        if month and (not d or f"{d.year:04d}-{d.month:02d}" != month):
            continue
        for li in t.get("LineItems", []):
            if account_code and li.get("AccountCode") != account_code:
                continue
            results.append({
                "date": d.isoformat() if d else t["Date"],
                "type": t["Type"],
                "contact": t["Contact"]["Name"],
                "account_code": li.get("AccountCode"),
                "amount": li.get("LineAmount", li.get("UnitAmount")),
                "description": li.get("Description"),
            })
    return {"count": len(results), "transactions": results[:50]}


def get_findings(finding_type=None):
    """Returns pre-computed deterministic findings from The Pass's own
    detection engine (duplicate payments, variance, drift, ratio anomalies,
    aged payables), optionally filtered by type."""
    with open("findings.json") as f:
        findings = json.load(f)
    if finding_type:
        findings = [f for f in findings if f["type"] == finding_type]
    return {"count": len(findings), "findings": findings}


def get_trial_balance_via_mcp(date=None):
    """Pulls the trial balance through Xero's Remote MCP Server
    (builders.xero.com/beta/mcp) rather than the plain Accounting API -
    demonstrates the actual Agentic SDK / MCP integration path, not just
    direct REST calls."""
    with open("xero_tokens.json") as f:
        data = json.load(f)
    tenant_id = data["connections"][0]["tenantId"]
    client = _get_mcp_client()
    args = {"xeroTenantId": tenant_id}
    if date:
        args["date"] = date
    return client.call_tool("list_trial_balance", args)


TOOLS = [
    {
        "name": "get_profit_and_loss",
        "description": "Pull Xero's own computed Profit & Loss report for a date range. Use for questions about overall revenue, cost, or margin over a period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "YYYY-MM-DD"},
                "to_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "get_aged_payables_for_contact",
        "description": "Pull Xero's own Aged Payables report for a specific supplier/contact by name. Use for questions about unpaid bills owed to a specific supplier.",
        "input_schema": {
            "type": "object",
            "properties": {"contact_name": {"type": "string"}},
            "required": ["contact_name"],
        },
    },
    {
        "name": "get_aged_receivables_for_contact",
        "description": "Pull Xero's own Aged Receivables report for a specific customer by name - money owed TO the business. Use for questions about late-paying customers or drafting a payment chase.",
        "input_schema": {
            "type": "object",
            "properties": {"contact_name": {"type": "string"}},
            "required": ["contact_name"],
        },
    },
    {
        "name": "list_bank_transactions",
        "description": "List live bank transactions, optionally filtered by Xero account code, contact name, month (YYYY-MM), or type (SPEND/RECEIVE). Use to verify a specific claim (e.g. a duplicate payment) against the raw ledger.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_code": {"type": "string"},
                "contact_name": {"type": "string"},
                "month": {"type": "string", "description": "YYYY-MM"},
                "transaction_type": {"type": "string", "enum": ["SPEND", "RECEIVE"]},
            },
        },
    },
    {
        "name": "get_findings",
        "description": "Get The Pass's own pre-computed anomaly findings (duplicate_payment, variance, drift, ratio_anomaly, aged_payable, novel_account_activity), optionally filtered by type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "finding_type": {
                    "type": "string",
                    "enum": ["duplicate_payment", "variance", "drift", "ratio_anomaly", "aged_payable", "novel_account_activity"],
                },
            },
        },
    },
    {
        "name": "get_trial_balance_via_mcp",
        "description": "Pull the trial balance through Xero's own Remote MCP Server (not the plain REST API) - use when asked to cross-check a figure via Xero's official agent tooling, or when asked specifically about the MCP integration.",
        "input_schema": {
            "type": "object",
            "properties": {"date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"}},
        },
    },
]

DISPATCH = {
    "get_profit_and_loss": lambda i: get_profit_and_loss(i["from_date"], i["to_date"]),
    "get_aged_payables_for_contact": lambda i: get_aged_payables_for_contact(i["contact_name"]),
    "get_aged_receivables_for_contact": lambda i: get_aged_receivables_for_contact(i["contact_name"]),
    "list_bank_transactions": lambda i: list_bank_transactions(
        i.get("account_code"), i.get("contact_name"), i.get("month"), i.get("transaction_type")),
    "get_findings": lambda i: get_findings(i.get("finding_type")),
    "get_trial_balance_via_mcp": lambda i: get_trial_balance_via_mcp(i.get("date")),
}
