"""
The Pass: Xero Remote MCP Server client.

A minimal client for Xero's Remote MCP Server (builders.xero.com/beta/mcp),
implementing the actual MCP Streamable HTTP handshake:

  1. POST "initialize" -> server returns an Mcp-Session-Id header
  2. POST "notifications/initialized" (required before further calls)
  3. POST "tools/list" / "tools/call" with that session header attached

This is the "Agentic SDK" integration path Xero's own hackathon materials
point at, as distinct from calling the plain Accounting REST API directly
(see xero_tools.py) - both are real, both are used in this project.

Responses come back as Server-Sent Events (one "data: {...}" line per
message) even for what are logically single-shot request/response calls,
so parsing strips the "event:"/"data:" framing before decoding JSON.
"""

import json

import requests

MCP_URL = "https://builders.xero.com/beta/mcp"


def _parse_sse(text):
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    raise ValueError(f"no SSE data line found in response: {text[:200]}")


class XeroMCPClient:
    def __init__(self, access_token):
        self.token = access_token
        self.session_id = None
        self._next_id = 1

    def _headers(self):
        h = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _rpc_id(self):
        i = self._next_id
        self._next_id += 1
        return i

    def initialize(self):
        r = requests.post(MCP_URL, headers=self._headers(), json={
            "jsonrpc": "2.0",
            "id": self._rpc_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "the-pass", "version": "0.1"},
            },
        })
        r.raise_for_status()
        self.session_id = r.headers["mcp-session-id"]

        r2 = requests.post(MCP_URL, headers=self._headers(), json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        r2.raise_for_status()
        return _parse_sse(r.text)

    def list_tools(self):
        r = requests.post(MCP_URL, headers=self._headers(), json={
            "jsonrpc": "2.0",
            "id": self._rpc_id(),
            "method": "tools/list",
        })
        r.raise_for_status()
        return _parse_sse(r.text)["result"]["tools"]

    def call_tool(self, name, arguments):
        r = requests.post(MCP_URL, headers=self._headers(), json={
            "jsonrpc": "2.0",
            "id": self._rpc_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        r.raise_for_status()
        result = _parse_sse(r.text)
        if "error" in result:
            raise RuntimeError(result["error"])
        content = result["result"]["content"]
        text_blocks = [b["text"] for b in content if b.get("type") == "text"]
        joined = "\n".join(text_blocks)
        try:
            return json.loads(joined)
        except (json.JSONDecodeError, ValueError):
            return joined


def connect():
    """Loads the stored token and returns an initialised MCP client."""
    with open("xero_tokens.json") as f:
        data = json.load(f)
    client = XeroMCPClient(data["tokens"]["access_token"])
    client.initialize()
    return client


if __name__ == "__main__":
    client = connect()
    tools = client.list_tools()
    print(f"Connected. {len(tools)} tools available:")
    for t in tools:
        print(f"  - {t['name']}: {t['description'][:80]}")

    tenants = client.call_tool("get_connected_tenants", {})
    print("\nget_connected_tenants ->", tenants)
