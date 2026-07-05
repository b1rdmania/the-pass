"""
The Pass: live demo server.

Serves report.html and a /api/ask endpoint backed by a real agentic
tool-use loop (Anthropic's function calling) over LIVE Xero data - Claude
decides which Xero Reports/BankTransactions/findings tool to call to
answer the question, rather than us pre-computing everything and handing
over a static JSON blob. This is the "prove it's really an agent, not a
templated chatbot" moment for the pitch.

Run: ANTHROPIC_API_KEY=sk-... python3 server.py
Then open http://localhost:5050
"""

import base64
import hashlib
import hmac
import json
import os
import subprocess
import time

import requests
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
import anthropic

import xero_tools

app = Flask(__name__)

XERO_CLIENT_ID = "BB1B37FAC79147ED917D74744B8120D4"
XERO_REVOCATION_URL = "https://identity.xero.com/connect/revocation"
XERO_WEBHOOK_KEY = os.environ.get("XERO_WEBHOOK_KEY", "")

SYSTEM_PROMPT = """You are The Pass: an agent doing a line check on a hospitality
or commercial property operator's Xero books. You're answering a specific
question live, in front of someone looking at the dashboard - a judge, an owner,
an accountant.

You have tools that pull LIVE data straight from Xero (Reports API, live bank
transactions) plus The Pass's own pre-computed anomaly findings. Use them - don't
guess. Call whichever tool actually answers the question; call more than one if
you need to cross-check a claim against the raw ledger.

Rules:
- Answer only from tool results. If the data doesn't cover the question, say so.
- Plain English, concrete pound figures, no accounting jargon.
- Keep the final answer to 2-4 sentences unless the question genuinely needs more.
- Direct, a bit dry. Not chirpy, not padded with caveats.
"""


@app.route("/")
def index():
    return send_file(os.path.join(os.getcwd(), "report.html"))


@app.route("/api/ask", methods=["POST"])
def ask():
    question = request.json.get("question", "").strip()
    if not question:
        return jsonify({"error": "no question provided"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on the server"}), 500

    def generate():
        start = time.time()
        client = anthropic.Anthropic(api_key=api_key)
        messages = [{"role": "user", "content": question}]
        total_input_tokens = 0
        total_output_tokens = 0

        def emit(event, **data):
            return json.dumps({"event": event, **data}) + "\n"

        for _ in range(5):  # cap the agent loop
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                tools=xero_tools.TOOLS,
                messages=messages,
            )
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                final_text = "".join(b.text for b in response.content if b.type == "text")
                yield emit(
                    "answer",
                    text=final_text,
                    latency_ms=round((time.time() - start) * 1000),
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    model="claude-sonnet-4-5",
                )
                return

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                yield emit("tool_call", tool=block.name, input=block.input)
                t0 = time.time()
                try:
                    result = xero_tools.DISPATCH[block.name](block.input)
                except Exception as e:
                    result = {"error": str(e)}
                yield emit(
                    "tool_result", tool=block.name,
                    duration_ms=round((time.time() - t0) * 1000),
                    summary=_summarize(result),
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
            messages.append({"role": "user", "content": tool_results})

        yield emit("answer", text="took too many steps to answer - try a narrower question",
                    latency_ms=round((time.time() - start) * 1000),
                    input_tokens=total_input_tokens, output_tokens=total_output_tokens)

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


def _summarize(result):
    if isinstance(result, dict):
        if "count" in result:
            return f"{result['count']} result(s)"
        if "rows" in result:
            return f"{len(result['rows'])} row(s)"
    return "done"


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    """Real OAuth2 token revocation (RFC 7009) - matches Xero App Store
    certification checkpoint 4 (must provide a working disconnect that
    revokes tokens, not just a UI toggle)."""
    with open("xero_tokens.json") as f:
        data = json.load(f)
    refresh_token = data["tokens"]["refresh_token"]

    resp = requests.post(XERO_REVOCATION_URL, data={
        "client_id": XERO_CLIENT_ID,
        "token": refresh_token,
    })
    if resp.ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": f"{resp.status_code}: {resp.text[:200]}"}), 500


@app.route("/webhooks/xero", methods=["POST"])
def xero_webhook():
    """Real Xero webhook receiver - HMAC-SHA256 signature verification per
    Xero's actual spec (base64(HMAC-SHA256(raw_body, webhook_key)) compared
    against the x-xero-signature header). Not registered against a live
    Xero app yet (needs a public HTTPS endpoint we don't have tonight), but
    the verification logic itself is real and tested against a simulated
    signed payload - see verify_webhook.py.

    Once registered: this is what replaces polling. Instead of detect.py
    running on a schedule, a CREATE/UPDATE event on a bank transaction or
    invoice would trigger a targeted re-check of just that record.
    """
    raw_body = request.get_data()
    signature = request.headers.get("x-xero-signature", "")
    computed = base64.b64encode(
        hmac.new(XERO_WEBHOOK_KEY.encode(), raw_body, hashlib.sha256).digest()
    ).decode()

    if not hmac.compare_digest(computed, signature):
        return "", 401

    payload = request.get_json(silent=True) or {}
    for event in payload.get("events", []):
        print(f"[webhook] {event.get('eventCategory')} {event.get('eventType')} "
              f"resourceId={event.get('resourceId')} tenantId={event.get('tenantId')}")
        # would trigger a targeted re-check of just this resource here

    return "", 200


@app.route("/api/rescan", methods=["POST"])
def rescan():
    """Actually re-runs detect.py against live Xero data from scratch and
    streams its real stdout line by line, then rebuilds report.html. This
    is the difference between "an honest static snapshot of a past run"
    and "genuinely live" - a judge triggering this watches a real script
    hit the real Xero API in front of them, not a replay."""

    def generate():
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        proc = subprocess.Popen(
            ["python3", "-u", "src/detect.py"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, env=env,
        )
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line.strip():
                yield json.dumps({"event": "log", "text": line}) + "\n"
        proc.wait()

        yield json.dumps({"event": "log", "text": "rebuilding report.html..."}) + "\n"
        build_proc = subprocess.run(
            ["python3", "src/build_report.py"], capture_output=True, text=True, env=env
        )
        if build_proc.returncode == 0:
            yield json.dumps({"event": "log", "text": build_proc.stdout.strip()}) + "\n"
            yield json.dumps({"event": "done", "ok": True}) + "\n"
        else:
            yield json.dumps({"event": "done", "ok": False, "error": build_proc.stderr[-500:]}) + "\n"

    return Response(stream_with_context(generate()), mimetype="application/x-ndjson")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"The Pass demo server running on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
