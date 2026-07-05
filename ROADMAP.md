# Roadmap

Guardrails were the first design decision and they stay that way: detection
remains deterministic at every stage below. The AI layer grows; it never gets
write access to the ledger.

## v0.2 — real time

- Register the webhook receiver against a live Xero subscription (the
  verification logic is already built and tested). A CREATE/UPDATE event on a
  bank transaction or invoice triggers a targeted re-check of just that record —
  detection the day it happens, not at month end.
- Scheduled full scans (nightly) with a diff against the previous run.

## v0.3 — multi-org

- One owner, ten sites, one report. Portfolio view for operators and fractional
  CFOs: the same detectors across every organisation, ranked by impact.
- Per-site baselines, cross-site comparison (why is site 3's wage ratio 4 points
  higher than site 5's?).

## v0.4 — payments and action

- Xero Payments data for cash-flow forecasting: predicted late payers, drafted
  follow-ups queued for approval.
- One-click send for chase/win-back drafts (human approves, always).

## Orchestration tier (exploratory)

The current agent is a single Claude with tools. An orchestration version — a
top-level model (Opus/Fable-class) planning multi-step investigations across
detectors, reports and the API — is the obvious expansion. The reason v0.1
doesn't do this: with historic books, hallucination risk compounds at each
step of a plan. The harness comes first, then the smarter planner inside it.
