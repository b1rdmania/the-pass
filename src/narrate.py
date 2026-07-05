"""
The Pass: narrative layer.

Reads findings.json (deterministic output from detect.py) and asks Sonnet
to turn it into a plain-English owner-facing report - no accounting
jargon, concrete pound figures, and a clear "what to do about it" per
finding. This is the layer that turns a spreadsheet of anomalies into
something a busy hospitality operator will actually read.

Requires ANTHROPIC_API_KEY in the environment.
"""

import json
import os

import anthropic

with open("findings.json") as f:
    findings = json.load(f)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are The Pass: a line check for a hospitality or commercial
property operator's books, run over their Xero data. You are writing directly to a
busy, non-accountant owner - someone running sites, managing staff, and definitely
not reading a trial balance for fun.

Rules:
- Plain English. No jargon like "variance", "trailing average", or "materiality".
- Every finding gets: what happened, in pounds, and why it matters to them as an
  owner - not to their accountant.
- End each finding with one concrete next action.
- Group similar findings together rather than repeating near-duplicates.
- Open with a one-paragraph summary: how many issues, roughly how much money is
  involved in total, and the single most urgent one to look at first.
- Tone: direct, a bit dry, respectful of their time. Not chirpy. Not alarmist.
"""

USER_PROMPT = f"""Here are the raw findings from a line check of the books:

{json.dumps(findings, indent=2)}

Write the owner-facing report.
"""

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=2000,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": USER_PROMPT}],
)

report = response.content[0].text

with open("report.md", "w") as f:
    f.write(report)

print(report)
print("\n\nSaved to report.md")
