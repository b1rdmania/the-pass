"""Refreshes the Xero access token using the stored refresh_token."""

import json

import requests

CLIENT_ID = "BB1B37FAC79147ED917D74744B8120D4"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"

with open("xero_tokens.json") as f:
    data = json.load(f)

refresh_token = data["tokens"]["refresh_token"]

resp = requests.post(TOKEN_URL, data={
    "grant_type": "refresh_token",
    "client_id": CLIENT_ID,
    "refresh_token": refresh_token,
})
resp.raise_for_status()
tokens = resp.json()

conn_resp = requests.get(CONNECTIONS_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
conn_resp.raise_for_status()
connections = conn_resp.json()

with open("xero_tokens.json", "w") as f:
    json.dump({"tokens": tokens, "connections": connections}, f, indent=2)

print("Token refreshed. Orgs:", [c["tenantName"] for c in connections])
