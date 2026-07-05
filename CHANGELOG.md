# Changelog

## v0.1 — 2026-07-05

First release. Built in 24 hours at the Xero App & Agent Hackathon, London.

- Five deterministic detectors over 36 months of Xero data: duplicate payments,
  variance vs 3-month trailing average, drift vs 6-month baseline, cross-account
  ratios (wages/sales, card fees/sales, comps/sales), aged payables/receivables
  + customer churn
- Claude language layer: plain-English narrative, drafted chase and win-back
  emails, live agent with tools over the Xero REST API and Remote MCP server
  (full Streamable HTTP handshake)
- Owner dashboard (mission control, 4 pages) and accountant reconciliation
  report, cross-linked; every finding deep-links into the live Xero record
- Live re-scan endpoint that re-runs detection against Xero from scratch,
  streaming the log
- OAuth2 PKCE with refresh and RFC 7009 revocation; HMAC-SHA256 webhook
  signature verification, tested against signed and tampered payloads
- Demo org seeded with 3 years of realistic trading history through the API
  (477 bank transactions), with deliberate anomalies — all of them found
