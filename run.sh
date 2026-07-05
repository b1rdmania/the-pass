#!/bin/bash
# Demo-day launcher for The Pass. One command, no forgotten env vars.
#
#   ANTHROPIC_API_KEY=sk-... ./run.sh
#
# Refuses to start without the key so the agent chat can't silently degrade
# in front of the judges.

set -e
cd "$(dirname "$0")"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "ANTHROPIC_API_KEY is not set - the live agent chat would return errors."
  echo "Run:  ANTHROPIC_API_KEY=sk-... ./run.sh"
  exit 1
fi

export XERO_WEBHOOK_KEY="${XERO_WEBHOOK_KEY:-test-webhook-signing-key}"

echo "Refreshing Xero token..."
python3 refresh_token.py

echo "Starting The Pass on http://localhost:5050"
python3 server.py
