"""
Proves the webhook signature verification in server.py is actually correct,
using a simulated payload signed the same way Xero signs real webhooks -
base64(HMAC-SHA256(raw_body, webhook_key)).

We can't fire a real Xero webhook without a public HTTPS endpoint, so this
is the honest substitute: same crypto, a payload shaped like Xero's real
webhook contract, sent to our own local server.
"""

import base64
import hashlib
import hmac
import json

import requests

TEST_KEY = "test-webhook-signing-key"
URL = "http://localhost:5050/webhooks/xero"

payload = {
    "events": [{
        "resourceUrl": "https://api.xero.com/api.xro/2.0/BankTransactions/5174ed58-46f6-4332-95df-a97efa10d3d8",
        "resourceId": "5174ed58-46f6-4332-95df-a97efa10d3d8",
        "eventDate": "2026-07-04T21:00:00.000",
        "eventType": "UPDATE",
        "eventCategory": "BANKTRANSACTION",
        "tenantId": "e69041b8-29a2-4bea-916f-cb843046b726",
    }],
    "firstEventSequence": 1,
    "lastEventSequence": 1,
    "entropy": "abc123",
}

raw_body = json.dumps(payload).encode()
signature = base64.b64encode(hmac.new(TEST_KEY.encode(), raw_body, hashlib.sha256).digest()).decode()

print("Sending correctly-signed payload...")
r = requests.post(URL, data=raw_body, headers={
    "Content-Type": "application/json",
    "x-xero-signature": signature,
})
print(f"  status: {r.status_code} (expect 200 - accepted)")

print("\nSending tampered payload with the same signature (should be rejected)...")
tampered = raw_body.replace(b"UPDATE", b"DELETE")
r2 = requests.post(URL, data=tampered, headers={
    "Content-Type": "application/json",
    "x-xero-signature": signature,
})
print(f"  status: {r2.status_code} (expect 401 - rejected, signature no longer matches)")
