"""
One-off script to connect The Pass to a Xero org via standard OAuth 2.0
Authorization Code + PKCE flow (no MCP allow-list needed).

Run this, it'll open your browser to the Xero login/consent screen.
Log in, pick your demo org, click Allow access.
Tokens get saved to xero_tokens.json in this folder for reuse.
"""

import base64
import hashlib
import http.server
import json
import secrets
import ssl
import threading
import urllib.parse
import webbrowser

import requests

CLIENT_ID = "BB1B37FAC79147ED917D74744B8120D4"
REDIRECT_URI = "https://localhost:61234/callback"
SCOPES = (
    "openid profile email offline_access "
    "accounting.contacts accounting.settings "
    "accounting.invoices accounting.payments accounting.banktransactions accounting.manualjournals "
    "accounting.reports.profitandloss.read accounting.reports.balancesheet.read "
    "accounting.reports.trialbalance.read accounting.reports.aged.read "
    "accounting.reports.budgetsummary.read accounting.reports.banksummary.read"
)
AUTH_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"

TOKENS_FILE = "xero_tokens.json"

auth_code = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Connected. You can close this tab and go back to the terminal.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code received.")

    def log_message(self, format, *args):
        pass  # quiet


def make_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def main():
    verifier, challenge = make_pkce_pair()
    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    server = http.server.HTTPServer(("localhost", 61234), CallbackHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print("Opening browser for Xero login...")
    webbrowser.open(url)

    thread.join(timeout=180)

    if "code" not in auth_code:
        print("Timed out waiting for Xero login. Run again.")
        return

    code = auth_code["code"]

    token_resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    conn_resp = requests.get(
        CONNECTIONS_URL,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    conn_resp.raise_for_status()
    connections = conn_resp.json()

    with open(TOKENS_FILE, "w") as f:
        json.dump({"tokens": tokens, "connections": connections}, f, indent=2)

    print(f"\nConnected! Found {len(connections)} organisation(s):")
    for c in connections:
        print(f"  - {c['tenantName']} (tenantId: {c['tenantId']})")
    print(f"\nTokens saved to {TOKENS_FILE}")


if __name__ == "__main__":
    main()
