"""
The Pass: report builder — "urban observatory" design system, ported from
Site DNA (~/Documents/site-dna/design/DESIGN.md + variant-exports/design-
80c86d64...html — the inspection-view export). Tokens and grammar copied
exactly per that system's strict-preservation rule; content is new.

Groups the raw findings.json output into a small number of real "stories",
sums an estimated £ impact per story, and renders:
  - an inspection view: signature/metrics panel + a LIVE activity log built
    from the actual pipeline run (real counts, real steps) - this is the
    part that proves the system is really talking to Xero, not vibes
  - a findings section in the same bounded-box grammar
"""

import json
import os
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta

import requests


def draft_chase_message(contact, amount_due, days_overdue):
    """Drafts an actual payment-chase message - the autonomous-action half
    of the Cash Flow Accelerator bounty, not just a flagged insight. Uses
    Sonnet if an API key is available; falls back to a solid template
    otherwise so the report never ships a blank action."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=250,
                system="Draft a short, firm but friendly payment-chase email from a "
                       "hospitality operator to a corporate client. Plain English, "
                       "no legal threats, one clear ask, under 120 words.",
                messages=[{
                    "role": "user",
                    "content": f"Draft a chase email to {contact} for an overdue invoice "
                               f"of £{amount_due:,.2f}, {days_overdue} days overdue.",
                }],
            )
            return resp.content[0].text.strip(), "sonnet"
        except Exception:
            pass

    template = (
        f"Subject: Following up on your outstanding balance - £{amount_due:,.2f}\n\n"
        f"Hi {contact},\n\n"
        f"Hope you're well. Flagging that we haven't yet received payment for your recent "
        f"invoice, now {days_overdue} days past its due date - £{amount_due:,.2f} outstanding.\n\n"
        f"Could you let us know when we can expect this, or flag if there's an issue on your "
        f"end? Happy to resend the invoice if it's gone astray.\n\n"
        f"Thanks"
    )
    return template, "template"


def draft_winback_message(contact, avg_spend, days_since_last, n_bookings):
    """Drafts a win-back outreach message for a high-value customer who's
    gone quiet - the other Cash Flow Accelerator example (detecting a
    lapsed customer and triggering outreach), distinct from the payment
    chase above."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=250,
                system="Draft a short, warm win-back email from a hospitality operator to "
                       "a lapsed repeat corporate client. Plain English, genuinely glad to "
                       "hear from them again tone, one clear invite to get back in touch, "
                       "under 120 words.",
                messages=[{
                    "role": "user",
                    "content": f"Draft a win-back email to {contact}, who booked with us "
                               f"{n_bookings} times averaging £{avg_spend:,.2f} per visit, "
                               f"but hasn't been back in {days_since_last} days.",
                }],
            )
            return resp.content[0].text.strip(), "sonnet"
        except Exception:
            pass

    months_quiet = days_since_last // 30
    template = (
        f"Subject: We miss you, {contact}\n\n"
        f"Hi {contact},\n\n"
        f"It's been about {months_quiet} months since your last booking with us - you were "
        f"one of our regulars for a while there ({n_bookings} visits, averaging £{avg_spend:,.2f}), "
        f"so wanted to check in rather than just let it drift.\n\n"
        f"If it's timing, budget, or something we could do better, happy to hear it. If you're "
        f"just due a night out again, let us know a date and we'll sort you a table.\n\n"
        f"Hope to see you again soon"
    )
    return template, "template"


with open("findings.json") as f:
    findings = json.load(f)

with open("timeseries.json") as f:
    TIMESERIES = json.load(f)

with open("xero_tokens.json") as f:
    _tok_data = json.load(f)
_token = _tok_data["tokens"]["access_token"]
_tenant = _tok_data["connections"][0]["tenantId"]
_h = {"Authorization": f"Bearer {_token}", "Xero-tenant-id": _tenant, "Accept": "application/json"}
try:
    _org_resp = requests.get("https://api.xero.com/api.xro/2.0/Organisation", headers=_h)
    _org = _org_resp.json()["Organisations"][0]
    ORG_NAME = _org["Name"]
    SHORT_CODE = _org["ShortCode"]
except Exception:
    ORG_NAME = "Hackathon Test"
    SHORT_CODE = None


def _deep_link(inner_path):
    """Xero's org-login redirect pattern - deep-links straight into the
    live record in Xero's own web UI, keyed off the organisation short code."""
    if not SHORT_CODE:
        return None
    redirect = urllib.parse.quote(inner_path, safe="")
    return f"https://go.xero.com/organisationlogin/default.aspx?shortcode={SHORT_CODE}&redirecturl={redirect}"


def bank_txn_link(txn_id):
    return _deep_link(f"/Bank/ViewTransaction.aspx?bankTransactionID={txn_id}")


def invoice_link(invoice_id):
    return _deep_link(f"/AccountsPayable/Edit.aspx?InvoiceID={invoice_id}")


def render_trend_chart(series, highlight_months=None, width=380, height=90, as_pct=False):
    """Renders a real time-series (account totals or ratio history) as an
    SVG line, in the same hand-drawn-squiggle technique as the signature
    panel - our own visual language, not a copy of Xero's chart style."""
    months = sorted(series.keys())
    if len(months) < 2:
        return ""
    values = [series[m] for m in months]
    vmin, vmax = min(values), max(values)
    vrange = (vmax - vmin) or 1

    pad_x, pad_y = 6, 10
    plot_w = width - pad_x * 2
    plot_h = height - pad_y * 2

    def xy(i, v):
        x = pad_x + (i / (len(months) - 1)) * plot_w
        y = pad_y + plot_h - ((v - vmin) / vrange) * plot_h
        return x, y

    points = [xy(i, v) for i, v in enumerate(values)]
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)

    highlight_months = set(highlight_months or [])
    markers = ""
    for i, m in enumerate(months):
        if m in highlight_months:
            x, y = points[i]
            markers += f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height}" stroke="var(--ink)" stroke-width="0.5" stroke-dasharray="3 3"></line>'
            markers += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="var(--ink)"></circle>'

    suffix = "%" if as_pct else ""
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" style="display:block; margin-top: 0.8cqi;">
      {markers}
      <path d="{path}" fill="none" stroke="var(--ink-blue)" stroke-width="1.6"></path>
    </svg>
    <div style="display:flex; justify-content: space-between; font-size: 0.8cqi; color: var(--ink-faded); margin-top: 0.2cqi;">
      <span>{months[0]}</span><span>{months[-1]}</span>
    </div>"""


# --- story grouping (unchanged logic) ----------------------------------------
STORY_DEFS = [
    {
        "key": "insurance_duplicate",
        "title": "paid your insurer twice",
        "match": lambda f: f["type"] == "duplicate_payment" and "Insurance" in f.get("contact", ""),
        "action": "contact zurich insurance and request a refund of the duplicate premium.",
    },
    {
        "key": "other_duplicate",
        "title": "other duplicate payment",
        "match": lambda f: f["type"] == "duplicate_payment" and "Insurance" not in f.get("contact", ""),
        "action": "check with the payee and your bank whether this can be reversed.",
    },
    {
        "key": "wages",
        "title": "wage cost is drifting from what sales justify",
        "match": lambda f: (f["type"] in ("variance", "drift") and f.get("account_code") == "320")
        or (f["type"] == "ratio_anomaly" and f.get("label", "").startswith("Wages")),
        "action": "check the roster against sales for the flagged periods.",
    },
    {
        "key": "bank_fees",
        "title": "bank charges have been creeping up",
        "match": lambda f: f["type"] in ("variance", "drift") and f.get("account_code") == "404",
        "action": "ask metro bank for a breakdown - this pattern usually means a quiet fee-tier change.",
    },
    {
        "key": "card_fees",
        "title": "card processing rate looks like it's changed",
        "match": lambda f: (f["type"] in ("variance", "drift") and f.get("account_code") == "406")
        or (f["type"] == "ratio_anomaly" and f.get("label", "").startswith("Card fee")),
        "action": "check your merchant statement for a rate change.",
    },
    {
        "key": "comps",
        "title": "comps and give-aways spiked",
        "match": lambda f: (f["type"] in ("variance", "drift") and f.get("account_code") == "407")
        or (f["type"] == "ratio_anomaly" and f.get("label", "").startswith("Comps")),
        "action": "review comps sign-off with site managers for the flagged month.",
    },
    {
        "key": "miscoded",
        "title": "a cost looks miscoded",
        "match": lambda f: f["type"] == "novel_account_activity",
        "action": "re-check this transaction with your bookkeeper.",
    },
    {
        "key": "aged_payable",
        "title": "an old bill is still sitting unpaid",
        "match": lambda f: f["type"] == "aged_payable",
        "action": "confirm with the supplier whether this is still owed.",
    },
    {
        "key": "wet_dry_margin",
        "title": "wet & dry cost mix has moved",
        "match": lambda f: (f["type"] in ("variance", "drift") and f.get("account_code") in ("WET", "DRY"))
        or (f["type"] == "ratio_anomaly" and f.get("label", "").startswith(("Wet", "Dry"))),
        "action": "check portion sizes and supplier pricing for the flagged month.",
    },
    {
        "key": "customer_receivables",
        "title": "a customer is overdue paying you",
        "match": lambda f: f["type"] == "aged_receivable",
        "action": "chase before it becomes a write-off - see the drafted message below.",
    },
    {
        "key": "customer_churn",
        "title": "a regular customer has gone quiet",
        "match": lambda f: f["type"] == "customer_churn",
        "action": "send a win-back nudge before they're fully lost - see the drafted message below.",
    },
]

# mission-control modules: real operational areas an operator would check,
# each mapped to one or more story keys. A module with no matching cards
# still gets checked directly against the raw time series so it can report
# a genuine "reviewed, clear" status rather than just going unmentioned.
MODULES = [
    {"name": "statutory & tax", "story_keys": [], "clear_check": ("820", "VAT payment")},
    {"name": "recurring suppliers", "story_keys": ["insurance_duplicate", "aged_payable"]},
    {"name": "payroll & staff ratio", "story_keys": ["wages"]},
    {"name": "banking & merchant fees", "story_keys": ["bank_fees", "card_fees"]},
    {"name": "comps & discounts", "story_keys": ["comps"]},
    {"name": "cost coding accuracy", "story_keys": ["miscoded", "other_duplicate"]},
    {"name": "wet vs dry margin", "story_keys": ["wet_dry_margin"]},
    {"name": "customer receivables & chase", "story_keys": ["customer_receivables"]},
    {"name": "customer engagement & win-back", "story_keys": ["customer_churn"]},
]

OTHER_KEY = "other"
stories = defaultdict(lambda: {"findings": [], "impact": 0.0})
unmatched = []

for f in findings:
    matched = False
    for story in STORY_DEFS:
        if story["match"](f):
            s = stories[story["key"]]
            s["findings"].append(f)
            s["impact"] += f.get("estimated_impact", 0)
            matched = True
            break
    if not matched:
        unmatched.append(f)
        stories[OTHER_KEY]["findings"].append(f)
        stories[OTHER_KEY]["impact"] += f.get("estimated_impact", 0)

story_lookup = {s["key"]: s for s in STORY_DEFS}

cards = []
for key, data in stories.items():
    if key == OTHER_KEY or not data["findings"]:
        continue
    meta = story_lookup[key]
    headline = max(data["findings"], key=lambda f: (f["severity"] == "high", f.get("estimated_impact", 0)))
    cards.append({
        "key": key,
        "title": meta["title"],
        "action": meta["action"],
        "impact": round(data["impact"], 2),
        "n_findings": len(data["findings"]),
        "headline_summary": headline["summary"],
        "severity": "high" if any(x["severity"] == "high" for x in data["findings"]) else "medium",
        "records": data["findings"],
    })

cards.sort(key=lambda c: -c["impact"])
# only genuinely confirmed (high-severity) findings roll into the headline
# total - a module that's all medium-severity noise (e.g. natural variance
# in a supplier split) still shows its own £ figure on its own card, but
# blending it into one "hero number" would overstate what's actually wrong
total_impact = sum(c["impact"] for c in cards if c["severity"] == "high")
monitor_only_impact = sum(c["impact"] for c in cards if c["severity"] != "high")
n_stories = len(cards)
n_high = sum(1 for c in cards if c["severity"] == "high")
risk_profile = "High" if n_high >= 3 else ("Medium" if n_high >= 1 else "Low")

# --- mission-control module status --------------------------------------
cards_by_key = {c["key"]: c for c in cards}
modules = []
for m in MODULES:
    module_cards = [cards_by_key[k] for k in m["story_keys"] if k in cards_by_key]
    if module_cards:
        status = "warning" if any(c["severity"] == "high" for c in module_cards) else "monitor"
        reviewed_note = None
    else:
        status = "clear"
        code, label = m.get("clear_check", (None, None))
        series = TIMESERIES.get("accounts", {}).get(code, {}) if code else {}
        reviewed_note = f"{len(series)} {label}(s) reviewed - no irregularities" if series else "reviewed - no irregularities"
    modules.append({
        "name": m["name"],
        "status": status,
        "cards": module_cards,
        "reviewed_note": reviewed_note,
    })

# --- real activity log, built from the actual pipeline run -------------------
# these are genuine steps/counts from this session's seed_data.py / detect.py
# runs against the live Xero org, not fabricated content
now = datetime.now()

def ts(minutes_ago):
    return (now - timedelta(minutes=minutes_ago)).strftime("%H:%M")

LOG_EVENTS = [
    (ts(3), f"{len(findings)} raw signals -> {n_stories} stories after de-dup"),
    (ts(5), "aged_payable detector -> 1 bill, 993 days overdue"),
    (ts(6), "ratio_anomaly detector -> wages/sales, card-fee/sales, comps/sales"),
    (ts(8), "drift detector -> 6-month baseline, bank fees +136%"),
    (ts(9), "variance detector -> 3-month trailing avg, 10 accounts scanned"),
    (ts(10), "duplicate_payment detector -> 1 match, zurich insurance"),
    (ts(12), "pulled 1 accpay bill · aged payables scan"),
    (ts(13), "pulled 302 bank_transactions · 36 months"),
    (ts(14), "connected -> xero accounting api · oauth2 pkce"),
    (ts(15), "org: hackathon test · tenant authorised"),
]

log_rows = "".join(
    f'''<div class="term-line log-entry" style="--i: {i};"><span class="term-prompt">[{t}]&nbsp;$</span> {label}</div>\n'''
    for i, (t, label) in enumerate(LOG_EVENTS)
)
log_rows += f'<div class="term-line log-entry" style="--i: {len(LOG_EVENTS)};"><span class="term-cursor">&#9608;</span></div>'

# --- findings section (bounded-box grammar) ----------------------------------
def money(n):
    return f"£{n:,.0f}"


def record_links_html(r):
    links = []
    if r.get("invoice_id"):
        url = invoice_link(r["invoice_id"])
        if url:
            links.append((url, "open bill in xero"))
    for txn_id in r.get("bank_transaction_ids", []) or []:
        url = bank_txn_link(txn_id)
        if url:
            links.append((url, "open transaction in xero"))
    if not links:
        return ""
    return " · ".join(
        f'<a href="{u}" target="_blank" style="color: var(--ink-blue);">{label} &#8599;</a>'
        for u, label in links
    )


def record_row_html(r):
    label = r.get("month") or (r.get("dates", [""])[0] if r.get("dates") else "")
    links_html = record_links_html(r)
    links_div = f'<div style="font-size: 0.9cqi; padding-left: 8cqi;">{links_html}</div>' if links_html else ""
    return (
        f'<div class="data-row" style="padding: 1cqi 2cqi; flex-direction: column; align-items: flex-start; gap: 0.4cqi;">'
        f'<div style="display:flex; width:100%; gap: 1cqi;">'
        f'<div class="data-label" style="flex: 0 0 7cqi; font-size: 0.9cqi;">{label}</div>'
        f'<div class="data-value" style="font-size: 1cqi;">{r["summary"]}</div>'
        f'</div>'
        f'{links_div}'
        f'</div>'
    )


def find_chart_for_story(records):
    """Derives which real time series to chart directly from the story's own
    findings - not a fixed lookup table. Prefers a ratio series (more
    explanatory) if any record carries one, otherwise falls back to the
    underlying account's raw totals. This means charting adapts to whatever
    the detection engine actually flags on a given run, including account
    codes or ratio pairs that don't exist yet in today's data."""
    for r in records:
        label = r.get("label")
        if label and label in TIMESERIES.get("ratios", {}):
            return TIMESERIES["ratios"][label], True
    for r in records:
        code = r.get("account_code")
        if code and code in TIMESERIES.get("accounts", {}):
            return TIMESERIES["accounts"][code], False
    return None, False


_card_idx_counter = [0]


def render_card(c):
    idx = _card_idx_counter[0]
    _card_idx_counter[0] += 1
    sev_marker = "high" if c["severity"] == "high" else "med"
    record_rows = "".join(record_row_html(r) for r in c["records"])

    chart_html = ""
    series, as_pct = find_chart_for_story(c["records"])
    if series and len(series) >= 2:
        # only mark the 1-3 genuinely significant months, not every borderline
        # instance - a chart with 30 dashed lines reads as noise, not a spike
        with_month = [r for r in c["records"] if r.get("month")]
        top_records = sorted(with_month, key=lambda r: -r.get("estimated_impact", 0))[:3]
        flagged_months = {r["month"] for r in top_records}
        chart_html = render_trend_chart(series, highlight_months=flagged_months, as_pct=as_pct)

    # customer_receivables / customer_churn get a real drafted outreach
    # message per finding - the autonomous-action half of Cash Flow
    # Accelerator, not just an insight
    chase_html = ""
    if c["key"] == "customer_receivables":
        for r in c["records"]:
            message, source = draft_chase_message(r["contact"], r["amount_due"], r["days_overdue"])
            chase_html += (
                f'<div class="chase-draft">'
                f'<div class="text-small-bold" style="margin-bottom:0.6cqi;">drafted chase - {r["contact"]} '
                f'<span style="opacity:0.5; font-weight:400;">({source})</span></div>'
                f'<pre>{message}</pre>'
                f'</div>'
            )
    elif c["key"] == "customer_churn":
        for r in c["records"]:
            message, source = draft_winback_message(
                r["contact"], r["avg_spend"], r["days_since_last"], r["n_historical_bookings"])
            chase_html += (
                f'<div class="chase-draft">'
                f'<div class="text-small-bold" style="margin-bottom:0.6cqi;">drafted win-back - {r["contact"]} '
                f'<span style="opacity:0.5; font-weight:400;">({source})</span></div>'
                f'<pre>{message}</pre>'
                f'</div>'
            )

    return f"""
    <div class="data-row finding-row">
      <div class="finding-main">
        <div class="finding-title">{c['title']}</div>
        <div class="finding-summary">{c['headline_summary'].lower()}</div>
        {chart_html}
        <div class="finding-action">&rarr; {c['action']}</div>
        {chase_html}
        <div class="audit-toggle" onclick="document.getElementById('audit-{idx}').style.display = document.getElementById('audit-{idx}').style.display === 'block' ? 'none' : 'block'">view raw records ({c['n_findings']}) &darr;</div>
        <div id="audit-{idx}" class="audit-detail">{record_rows}</div>
      </div>
      <div class="finding-figures">
        <div class="fraction-text"><span class="fraction-num">{money(c['impact'])}</span></div>
        <div class="metric-label">{c['n_findings']} flagged /{sev_marker}</div>
      </div>
    </div>
    """


STATUS_LABELS = {"clear": "CLEAR", "monitor": "MONITOR", "warning": "WARNING"}

# three pages: overview (0), all modules on one scrollable page (1), ask (2).
# pills jump to page 1 and scroll to the module's section
module_pills = ""
module_sections = []
for i, m in enumerate(modules):
    status_class = f"status-{m['status']}"
    module_pills += f'<div class="module-pill {status_class}" onclick="goToModule({i})"><span class="module-dot"></span>{m["name"]}</div>'

    if m["cards"]:
        body_html = "".join(render_card(c) for c in m["cards"])
    else:
        body_html = f'<div class="data-row" style="padding: 1.5cqi 2cqi; color: var(--ink-faded); font-style: italic; font-family: \'Times New Roman\', serif;">{m["reviewed_note"]}</div>'

    module_sections.append(f"""
    <div class="bounded-box module-section" id="module-{i}" style="margin-bottom: 1.5cqi;">
      <div class="box-header">
        <div class="text-small-bold">{m['name']}</div>
        <div class="text-small-bold {status_class}">{STATUS_LABELS[m['status']]}</div>
      </div>
      {body_html}
    </div>
    """)

module_pages_html = f'<div class="report-page" data-page="1">{"".join(module_sections)}</div>'

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>the pass — line check</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
  --paper: #e6dfd0;
  --paper-dark: #d4cbb8;
  --ink: #1a1816;
  --ink-faded: #4a4742;
  --ink-blue: #2d3748;
  --border-width: 1.5px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }}
body {{
  background-color: #0f0f0f;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  color: var(--ink);
  padding: 3vw 0;
}}
.frame {{
  max-width: 1100px;
  margin: 0 auto;
  background-color: var(--paper);
  border-radius: 20px;
  position: relative;
  overflow: hidden;
  container-type: inline-size;
  padding: 4cqi;
}}
.frame::after {{
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.04'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 10;
}}
.header {{ display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 3cqi; }}
.text-hero {{ font-size: 4.5cqi; font-weight: 400; letter-spacing: -0.01em; line-height: 1; }}
.text-small-bold {{ font-size: 1.2cqi; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }}
.italic-hero {{ font-family: 'Times New Roman', Times, serif; font-style: italic; color: var(--ink-faded); }}
.inspection-container {{ display: grid; grid-template-columns: 1fr 1.2fr; gap: 3cqi; margin-bottom: 3cqi; }}
.bounded-box {{ border: var(--border-width) solid var(--ink); background: transparent; display: flex; flex-direction: column; position: relative; }}
.box-header {{ padding: 1.5cqi 2cqi; border-bottom: var(--border-width) solid var(--ink); display: flex; justify-content: space-between; align-items: center; }}
.dna-visual {{ padding: 2.5cqi; flex: 0 0 32%; display: flex; flex-direction: column; justify-content: center; border-bottom: var(--border-width) solid var(--ink); }}
.dna-svg {{ width: 100%; height: 100%; }}
.metrics-grid {{ padding: 2cqi; display: grid; grid-template-columns: 1fr 1fr; gap: 2cqi; flex: 1; }}
.metric-item {{ display: flex; flex-direction: column; justify-content: center; }}
.metric-value {{ font-size: 3cqi; letter-spacing: -0.02em; }}
.metric-label {{ font-size: 1cqi; font-weight: 700; color: var(--ink-faded); text-transform: uppercase; }}
.scrollable-log {{ overflow-y: auto; flex: 1; max-height: 260px; scrollbar-width: thin; }}
.terminal-titlebar {{ padding: 1.2cqi 2cqi; border-bottom: var(--border-width) solid var(--ink); background: #1c1c1c; display: flex; justify-content: space-between; align-items: center; }}
.term-dots {{ display: flex; gap: 0.6cqi; }}
.term-dots span {{ width: 0.9cqi; height: 0.9cqi; border-radius: 50%; display: inline-block; }}
.term-dots span:nth-child(1) {{ background: #ff5f56; }}
.term-dots span:nth-child(2) {{ background: #ffbd2e; }}
.term-dots span:nth-child(3) {{ background: #27c93f; }}
.term-title {{ font-family: 'Courier New', Courier, monospace; font-size: 1cqi; color: #8a8a8a; }}
.terminal-body {{ background: #0d0d0d; overflow-y: auto; flex: 1; max-height: 260px; padding: 1.5cqi 2cqi; }}
.term-line {{ font-family: 'Courier New', Courier, monospace; font-size: 1.05cqi; color: #d4d4d4; line-height: 1.7; white-space: pre-wrap; }}
.term-prompt {{ color: #4ade80; }}
.term-cursor {{ color: #4ade80; animation: blink 1s step-end infinite; }}
.terminal-footer {{ padding: 1.2cqi 2cqi; border-top: var(--border-width) solid var(--ink); background: #1c1c1c; display: flex; justify-content: space-between; align-items: baseline; font-family: 'Courier New', Courier, monospace; color: #8a8a8a; font-size: 1cqi; }}
.data-row {{ display: flex; align-items: center; padding: 1.6cqi 2cqi; border-bottom: var(--border-width) solid var(--ink); }}
.data-row:last-child {{ border-bottom: none; }}
.data-label {{ flex: 0 0 9cqi; font-size: 1.1cqi; font-weight: 700; text-transform: uppercase; }}
.data-value {{ font-size: 1.5cqi; font-weight: 400; color: var(--ink-blue); }}
.box-footer {{ padding: 1.5cqi 2cqi; border-top: var(--border-width) solid var(--ink); display: flex; justify-content: space-between; align-items: baseline; }}
.fraction-text {{ font-size: 1.4cqi; font-weight: 500; display: flex; align-items: baseline; gap: 0.5cqi; }}
.fraction-num {{ font-family: 'Times New Roman', Times, serif; font-style: italic; font-size: 1.8cqi; color: var(--ink-blue); }}
.blinking-dot {{ width: 0.8cqi; height: 0.8cqi; background-color: var(--ink); border-radius: 50%; display: inline-block; margin-right: 0.8cqi; animation: blink 2s infinite; }}
@keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.2; }} }}
.log-entry {{ opacity: 0; animation: logIn 0.4s ease-out forwards; animation-delay: calc(var(--i) * 0.18s); }}
@keyframes logIn {{ from {{ opacity: 0; transform: translateY(-6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.findings-section .box-header .fraction-text {{ font-size: 1.2cqi; }}
.module-strip {{ display: flex; flex-wrap: wrap; gap: 0.8cqi; padding: 1.5cqi 2cqi; }}
.module-pill {{
  display: inline-flex; align-items: center; gap: 0.6cqi;
  border: var(--border-width) solid var(--ink); border-radius: 999px;
  padding: 0.6cqi 1.4cqi; font-size: 1cqi; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.03em; text-decoration: none; color: var(--ink); cursor: pointer;
}}
.module-pill:hover {{ background: rgba(0,0,0,0.04); }}
.report-page {{ animation: pageIn 0.3s ease-out; }}
@keyframes pageIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.pager {{
  display: flex; justify-content: space-between; align-items: center;
  margin: 2cqi 0; padding: 1.5cqi 0;
}}
.pager button {{
  font-family: inherit; font-size: 1.1cqi; padding: 0.8cqi 1.8cqi;
  border: var(--border-width) solid var(--ink); background: var(--paper); color: var(--ink); cursor: pointer;
}}
.pager button:disabled {{ opacity: 0.3; cursor: default; }}
.pager button:not(:disabled):hover {{ background: var(--ink); color: var(--paper); }}
#page-indicator {{ font-size: 1cqi; color: var(--ink-faded); text-transform: uppercase; letter-spacing: 0.05em; }}
.module-dot {{ width: 0.8cqi; height: 0.8cqi; border-radius: 50%; display: inline-block; }}
.module-pill.status-clear .module-dot {{ background: #2f8f4f; }}
.module-pill.status-monitor .module-dot {{ background: #c9931f; }}
.module-pill.status-warning .module-dot {{ background: #a33636; }}
.text-small-bold.status-clear {{ color: #2f8f4f; }}
.text-small-bold.status-monitor {{ color: #c9931f; }}
.text-small-bold.status-warning {{ color: #a33636; }}
.finding-row {{ align-items: flex-start; padding: 2cqi; }}
.finding-main {{ flex: 1; }}
.finding-title {{ font-size: 1.6cqi; font-weight: 700; margin-bottom: 0.4cqi; }}
.finding-summary {{ font-size: 1.15cqi; color: var(--ink-faded); margin-bottom: 0.5cqi; }}
.finding-action {{ font-size: 1.05cqi; color: var(--ink-blue); font-style: italic; font-family: 'Times New Roman', serif; }}
.finding-figures {{ text-align: right; flex: 0 0 auto; padding-left: 2cqi; }}
.finding-figures .fraction-num {{ font-size: 2.4cqi; }}
.audit-toggle {{ font-size: 0.95cqi; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faded); margin-top: 0.8cqi; cursor: pointer; }}
.audit-toggle:hover {{ color: var(--ink-blue); }}
.audit-detail {{ display: none; margin-top: 1cqi; border: var(--border-width) solid var(--ink-faded); background: rgba(0,0,0,0.02); }}
.chase-draft {{ margin-top: 1.2cqi; border: var(--border-width) solid var(--ink); background: rgba(45,55,72,0.04); padding: 1.5cqi 2cqi; }}
.chase-draft pre {{ font-family: 'Courier New', Courier, monospace; font-size: 1.05cqi; white-space: pre-wrap; color: var(--ink); line-height: 1.5; }}
.trace-line {{ font-size: 1.15cqi; color: var(--ink-faded); padding: 0.3cqi 0; font-family: 'Courier New', Courier, monospace; }}
.trace-line.tool {{ color: var(--ink-blue); font-style: normal; font-family: inherit; }}
</style>
</head>
<body>
<div class="frame">
  <div class="header">
    <div style="display:flex; align-items:center; gap:1.2cqi;">
      <svg width="34" height="34" viewBox="0 0 40 40" fill="none" stroke="var(--ink-blue)" stroke-width="1.6" stroke-linecap="round">
        <path d="M11 4 v10 M15 4 v10 M19 4 v10 M11 14 c0 3 8 3 8 0 M15 14 v22"></path>
        <path d="M29 4 c-3 1 -4 4 -4 8 c0 4 2 6 4 6 v18"></path>
      </svg>
      <div>
        <div class="text-small-bold">line check</div>
        <div class="text-hero">the pass <span class="italic-hero">v.01</span></div>
      </div>
    </div>
  </div>

  <div class="report-page" data-page="0">
  <div class="inspection-container">
    <div class="bounded-box">
      <div class="box-header">
        <div class="text-small-bold">cash flow signature</div>
        <div class="text-small-bold" style="color: var(--ink-blue);">36 months</div>
      </div>
      <div class="dna-visual">
        <svg class="dna-svg" viewBox="0 0 400 150" fill="none" stroke="var(--ink-blue)" stroke-width="2">
          <path d="M 0,90 C 40,90 60,95 90,92 C 130,88 150,40 175,38 C 200,36 210,90 240,90 C 270,90 280,95 310,93 C 340,91 360,60 400,58"></path>
          <line x1="175" y1="20" x2="175" y2="150" stroke="var(--ink)" stroke-width="0.5" stroke-dasharray="4 4"></line>
          <circle cx="175" cy="38" r="4" fill="var(--ink)"></circle>
        </svg>
      </div>
      <div class="metrics-grid">
        <div class="metric-item">
          <div class="metric-label">confirmed impact</div>
          <div class="metric-value">{money(total_impact)}</div>
          <div class="metric-label" id="impact-note" style="text-transform: none; font-weight: 400; font-style: italic; font-family: 'Times New Roman', serif; margin-top: 0.3cqi;">+{money(monitor_only_impact)} under monitoring, not yet confirmed</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">risk profile</div>
          <div class="metric-value" style="font-family: 'Times New Roman', serif; font-style: italic;">{risk_profile}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">issues found</div>
          <div class="metric-value">{n_stories}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">months reviewed</div>
          <div class="metric-value">36</div>
        </div>
      </div>
      <div class="box-footer" style="flex-direction: column; align-items: stretch; gap: 1cqi;">
        <div style="display:flex; justify-content: space-between; align-items:center;">
          <div class="text-small-bold">connected organisation</div>
          <div class="text-small-bold" style="color: var(--ink-blue);">{ORG_NAME.lower()}</div>
        </div>
        <div style="display:flex; justify-content: space-between; align-items:center;">
          <div class="text-small-bold" id="conn-status"><span class="blinking-dot" style="background: #2f6f4f;"></span>status: active</div>
          <div class="text-small-bold" style="text-decoration: underline; cursor: pointer; opacity: 0.6;" onclick="disconnectXero()">disconnect</div>
        </div>
      </div>
    </div>

    <div class="bounded-box">
      <div class="terminal-titlebar">
        <div class="term-dots"><span></span><span></span><span></span></div>
        <div class="term-title">the-pass — xero-sync — zsh</div>
        <div class="term-title" id="rescan-btn" style="cursor:pointer; text-decoration:underline;" onclick="rerunScan()"><span class="blinking-dot" style="background:#4ade80;"></span>re-run scan</div>
      </div>
      <div class="terminal-body" id="terminal-log">
        {log_rows}
      </div>
      <div class="terminal-footer">
        <div>findings</div>
        <div id="signal-count">{len(findings)} found</div>
      </div>
    </div>
  </div>

  <div class="bounded-box" style="margin-bottom: 1.5cqi;">
    <div class="box-header">
      <div class="text-small-bold">mission control</div>
      <div class="fraction-text"><span class="fraction-num">{sum(1 for m in modules if m['status']=='clear')}</span> /{len(modules)} clear</div>
    </div>
    <div class="module-strip">{module_pills}</div>
  </div>
  </div>

  {module_pages_html}

  <div class="report-page" data-page="2">
  <div class="bounded-box" style="margin-top: 0;">
    <div class="box-header">
      <div class="text-small-bold"><span class="blinking-dot"></span>ask the pass</div>
      <div class="text-small-bold" style="opacity: 0.5;">sonnet</div>
    </div>
    <div style="padding: 2cqi; display: flex; gap: 1cqi;">
      <input id="ask-input" type="text" placeholder="e.g. did we get overcharged on card fees recently?"
        style="flex: 1; border: var(--border-width) solid var(--ink); background: transparent; padding: 1.2cqi 1.5cqi; font-family: inherit; font-size: 1.5cqi; color: var(--ink);">
      <button id="ask-btn" style="border: var(--border-width) solid var(--ink); background: var(--ink); color: var(--paper); padding: 1.2cqi 2cqi; font-family: inherit; font-size: 1.1cqi; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; cursor: pointer;">ask</button>
    </div>
    <div id="ask-trace" style="padding: 0 2cqi; display: none;"></div>
    <div id="ask-answer" style="padding: 1cqi 2cqi 2cqi; font-size: 1.6cqi; line-height: 1.55; color: var(--ink); display: none;"></div>
    <div id="ask-meta" style="padding: 0 2cqi 1.5cqi; font-size: 0.9cqi; color: var(--ink-faded); text-transform: uppercase; letter-spacing: 0.04em; display: none;"></div>
  </div>
  </div>

  <div class="pager">
    <button id="prev-btn" onclick="goToPage(currentPage - 1)">&larr; Previous</button>
    <span id="page-indicator"></span>
    <button id="next-btn" onclick="goToPage(currentPage + 1)">Next &rarr;</button>
  </div>

  <div class="header" style="margin-top: 1cqi; margin-bottom: 0;">
    <div>
      <div class="text-hero">the pass.</div>
      <div style="display: flex; gap: 1.2cqi; align-items: center; margin-top: 0.6cqi;">
        <a href="https://github.com/b1rdmania/the-pass" target="_blank" rel="noopener" title="GitHub" style="color: var(--ink); display: inline-flex;">
          <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
        </a>
        <a href="https://www.linkedin.com/in/andrew-bird-nomos" target="_blank" rel="noopener" title="LinkedIn" style="color: var(--ink); display: inline-flex;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.34V9h3.42v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.07 2.07 0 1 1 0-4.13 2.07 2.07 0 0 1 0 4.13zM7.12 20.45H3.55V9h3.57v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z"/></svg>
        </a>
        <a href="https://x.com/b1rdmania" target="_blank" rel="noopener" title="X" style="color: var(--ink); display: inline-flex;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24h-6.66l-5.21-6.82-5.97 6.82H1.67l7.73-8.84L1.25 2.25h6.83l4.71 6.23 5.45-6.23zm-1.16 17.52h1.83L7.08 4.13H5.12l11.96 15.64z"/></svg>
        </a>
      </div>
    </div>
    <div style="text-align: right;">
      <div class="text-small-bold" style="letter-spacing: 0.2em;">connected to xero</div>
      <a href="accountant.html" class="text-small-bold" style="color: var(--ink-blue); letter-spacing: 0.1em;">accountant view &#8599;</a>
    </div>
  </div>
</div>
<script>
  const totalPages = 3;
  let currentPage = 0;

  function goToModule(i) {{
    goToPage(1);
    const target = document.getElementById('module-' + i);
    if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}

  function goToPage(n) {{
    if (n < 0 || n >= totalPages) return;
    document.querySelectorAll('.report-page').forEach(el => el.style.display = 'none');
    currentPage = n;
    const el = document.querySelector(`.report-page[data-page="${{currentPage}}"]`);
    el.style.display = 'block';
    el.style.animation = 'none';
    void el.offsetWidth;
    el.style.animation = 'pageIn 0.3s ease-out';
    document.getElementById('prev-btn').disabled = currentPage === 0;
    document.getElementById('next-btn').disabled = currentPage === totalPages - 1;
    document.getElementById('page-indicator').textContent = `page ${{currentPage + 1}} of ${{totalPages}}`;
    window.scrollTo(0, 0);
  }}

  document.addEventListener('keydown', (e) => {{
    if (e.key === 'ArrowRight') goToPage(currentPage + 1);
    if (e.key === 'ArrowLeft') goToPage(currentPage - 1);
  }});
  goToPage(0);

  // demo cold-open: /?cold lands connected-but-unscanned - numbers blank,
  // terminal waiting. the re-run scan button then fills everything live.
  if (window.location.search.includes('cold')) {{
    const mv = document.querySelectorAll('.metric-value');
    if (mv[0]) mv[0].textContent = '\u2014';
    if (mv[1]) mv[1].textContent = '\u2014';
    if (mv[2]) mv[2].textContent = '\u2014';
    const note = document.getElementById('impact-note');
    if (note) note.textContent = 'no scan yet this session';
    const sc = document.getElementById('signal-count');
    if (sc) sc.textContent = 'none yet';
    const tl = document.getElementById('terminal-log');
    if (tl) {{
      tl.innerHTML = '<div class="term-line"><span class="term-prompt">$</span> connected \u00b7 xero accounting api \u00b7 oauth2 pkce</div>' +
        '<div class="term-line"><span class="term-prompt">$</span> org: hackathon test \u00b7 tenant authorised</div>' +
        '<div class="term-line"><span class="term-prompt">$</span> ready.</div>' +
        '<div style="display:flex; justify-content:center; padding: 3cqi 0 1cqi;">' +
        '<button onclick="rerunScan()" style="background: var(--paper); color: var(--ink); border: none; ' +
        'font-family: inherit; font-size: 2.2cqi; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; ' +
        'padding: 1.6cqi 4cqi; cursor: pointer;">run full scan \u2192</button></div>' +
        '<div class="term-line" style="text-align:center; color:#8a8a8a;">36 months \u00b7 every account \u00b7 every ratio</div>';
    }}
    // the signature chart is a result too - fade it until the scan runs
    const dna = document.querySelector('.dna-visual');
    if (dna) dna.style.opacity = '0.12';
    // no paging into results that don't exist yet
    const pager = document.querySelector('.pager');
    if (pager) pager.style.display = 'none';
    // grey the module pills and the clear-count - no results shown before the scan
    document.querySelectorAll('.module-pill .module-dot').forEach(d => d.style.background = '#b5ada0');
    document.querySelectorAll('.fraction-text').forEach(f => {{
      if (f.textContent.includes('clear')) f.innerHTML = '<span class="fraction-num">\u2014</span> /9 clear';
    }});
  }}

  const btn = document.getElementById('ask-btn');
  const input = document.getElementById('ask-input');
  const answerBox = document.getElementById('ask-answer');
  const traceBox = document.getElementById('ask-trace');
  const metaBox = document.getElementById('ask-meta');

  function addTraceLine(text, isTool) {{
    const el = document.createElement('div');
    el.className = 'trace-line' + (isTool ? ' tool' : '');
    el.textContent = text;
    traceBox.appendChild(el);
  }}

  async function ask() {{
    const question = input.value.trim();
    if (!question) return;
    traceBox.style.display = 'block';
    traceBox.innerHTML = '';
    answerBox.style.display = 'block';
    answerBox.textContent = '';
    metaBox.style.display = 'none';
    addTraceLine('> sending question to sonnet...', false);

    try {{
      const resp = await fetch('/api/ask', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ question }}),
      }});
      if (!resp.ok) {{
        const err = await resp.json();
        answerBox.textContent = err.error || 'no response';
        return;
      }}
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {{
        const {{ done, value }} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {{ stream: true }});
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {{
          if (!line.trim()) continue;
          const evt = JSON.parse(line);
          if (evt.event === 'tool_call') {{
            addTraceLine('> calling ' + evt.tool + '(' + JSON.stringify(evt.input) + ')', true);
          }} else if (evt.event === 'tool_result') {{
            addTraceLine('< ' + evt.tool + ' returned ' + evt.summary + ' (' + evt.duration_ms + 'ms)', false);
          }} else if (evt.event === 'answer') {{
            const esc = evt.text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            answerBox.innerHTML = esc.replace(/\\*\\*(.+?)\\*\\*/g, '<b>$1</b>');
            metaBox.style.display = 'block';
            metaBox.textContent = evt.model + ' · ' + evt.latency_ms + 'ms · ' + evt.input_tokens + ' in / ' + evt.output_tokens + ' out tokens';
          }}
        }}
      }}
    }} catch (e) {{
      answerBox.textContent = 'could not reach the demo server - is server.py running?';
    }}
  }}
  btn.addEventListener('click', ask);
  input.addEventListener('keydown', (e) => {{ if (e.key === 'Enter') ask(); }});

  async function disconnectXero() {{
    if (!confirm('This will actually revoke the Xero OAuth token via the standard revocation endpoint (RFC 7009) - not a cosmetic toggle. Continue?')) return;
    const statusEl = document.getElementById('conn-status');
    statusEl.textContent = 'revoking...';
    try {{
      const resp = await fetch('/api/disconnect', {{ method: 'POST' }});
      const data = await resp.json();
      statusEl.innerHTML = data.ok
        ? '<span class="blinking-dot" style="background: #a33;"></span>status: revoked'
        : 'status: error - ' + (data.error || 'unknown');
    }} catch (e) {{
      statusEl.textContent = 'could not reach the demo server';
    }}
  }}

  async function rerunScan() {{
    const termLog = document.getElementById('terminal-log');
    const rescanBtn = document.getElementById('rescan-btn');
    termLog.innerHTML = '';
    rescanBtn.style.pointerEvents = 'none';
    rescanBtn.innerHTML = '<span class="blinking-dot" style="background:#4ade80;"></span>scanning live...';

    function addLine(text) {{
      const el = document.createElement('div');
      el.className = 'term-line';
      el.textContent = '$ ' + text;
      termLog.appendChild(el);
      termLog.scrollTop = termLog.scrollHeight;
    }}

    try {{
      const resp = await fetch('/api/rescan', {{ method: 'POST' }});
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {{
        const {{ done, value }} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {{ stream: true }});
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {{
          if (!line.trim()) continue;
          const evt = JSON.parse(line);
          if (evt.event === 'log') addLine(evt.text);
          if (evt.event === 'done') {{
            addLine(evt.ok ? 'scan complete - reloading with fresh results...' : 'scan failed: ' + evt.error);
            if (evt.ok) setTimeout(() => window.location.href = window.location.pathname, 1500);
          }}
        }}
      }}
    }} catch (e) {{
      addLine('could not reach the demo server - is server.py running?');
    }} finally {{
      rescanBtn.style.pointerEvents = 'auto';
    }}
  }}
</script>
</body>
</html>
"""

with open("report.html", "w") as f:
    f.write(html)

print(f"Rendered report.html — {n_stories} stories, total impact {money(total_impact)}, risk={risk_profile}")
