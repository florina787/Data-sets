"""End to end: the desktop app's API against the REAL billing Worker (served locally on SQLite with a
Stripe simulator by cloud/billing/test/serve.mjs). No network, no real Stripe, no real payments."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from backend.billing import Billing

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run the billing Worker")


@pytest.fixture(scope="module")
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    p = subprocess.Popen(["node", "--no-warnings", str(ROOT / "cloud/billing/test/serve.mjs"), str(port)], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    yield f"http://127.0.0.1:{port}"
    p.terminate()


def sign_in(client, server, email):
    assert client.post("/api/billing/sign-in", json={"email": email}).status_code == 200
    code = httpx.get(server + "/__test/code").json()["code"]
    r = client.post("/api/billing/sign-in", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return r.json()


def ask(client, text="Explain my project plan", mode="conversation"):
    sid = client.post("/api/sessions", json={"mode": mode}).json()["id"]
    events = [json.loads(line) for line in client.post("/api/chat", json={"session_id": sid, "text": text, "mode": mode}).text.splitlines() if line.strip()]
    return events, sid


@pytest.fixture
def billed(app, client, server, tmp_path):
    app.state.veena.billing = Billing(tmp_path / "b", url=server)
    (tmp_path / "b").mkdir(exist_ok=True)
    app.state.veena.billing = Billing(tmp_path / "b", url=server)
    return client


def test_disabled_by_default_everything_works(client):
    assert client.get("/api/billing").json() == {"enabled": False}
    events, _ = ask(client)
    assert any(e["type"] == "done" for e in events)


def test_not_signed_in_is_asked_to_sign_in(billed):
    events, _ = ask(billed)
    assert events[0]["code"] == "payment_required" and "Sign in" in events[0]["message"]


def test_three_free_answers_then_pricing(billed, server):
    me = sign_in(billed, server, "e2e@example.com")
    assert me["account"]["trial_remaining"]["chat"] == 3
    for left in (2, 1, 0):
        events, _ = ask(billed)
        assert any(e["type"] == "done" for e in events)
        assert billed.get("/api/billing").json()["account"]["trial_remaining"]["chat"] == left
    events, _ = ask(billed)
    assert events[0]["code"] == "payment_required" and "pricing" in events[0]["message"]
    # Other features have their own three uses.
    assert billed.get("/api/billing").json()["account"]["trial_remaining"]["documents"] == 3


def test_failed_answer_is_not_charged(billed, server, llm):
    sign_in(billed, server, "fail@example.com")
    llm.fail = True if hasattr(llm, "fail") else None

    async def broken(*a, **k):
        from backend.llm.ollama import LLMUnavailable

        raise LLMUnavailable("model crashed")
        yield  # pragma: no cover

    original = llm.chat_stream
    llm.chat_stream = broken
    try:
        events, _ = ask(billed)
    finally:
        llm.chat_stream = original
    assert any(e["type"] == "error" for e in events) and not any(e["type"] == "done" for e in events)
    assert billed.get("/api/billing").json()["account"]["trial_remaining"]["chat"] == 3


def test_new_email_on_same_install_does_not_reset_trial(billed, server):
    sign_in(billed, server, "one@example.com")
    for _ in range(3):
        ask(billed)
    billed.post("/api/billing/sign-out")
    me = sign_in(billed, server, "two@example.com")
    assert me["account"]["trial_remaining"]["chat"] == 0


def test_no_content_reaches_the_billing_server(billed, server, tmp_path):
    sign_in(billed, server, "privacy@example.com")
    sent = []
    b = billed.app.state.veena.billing if hasattr(billed, "app") else None
    real = httpx.HTTPTransport()

    class Spy(httpx.BaseTransport):
        def handle_request(self, request):
            sent.append(request.content.decode())
            return real.handle_request(request)

    bill = b or Billing(tmp_path / "b", url=server)
    bill.transport = Spy()
    ask(billed, text="My secret salary is 123456 and my resume says Acme")
    blob = " ".join(sent)
    assert sent and "secret" not in blob and "123456" not in blob and "Acme" not in blob


def test_offline_grace_then_blocked(billed, server):
    sign_in(billed, server, "offline@example.com")
    b = billed.app.state.veena.billing
    b.url = "http://127.0.0.1:9"  # nothing listens here
    for _ in range(3):
        events, _ = ask(billed)
        assert any(e["type"] == "done" for e in events)
    events, _ = ask(billed)
    assert events[0]["code"] == "payment_required" and "internet" in events[0]["message"]
    b.url = server


def test_meeting_session_block_charged_once_and_credits_used_after_trial(billed, server):
    sign_in(billed, server, "meet@example.com")
    acct = [a for a in httpx.get(server + "/__test/accounts").json() if a["email"] == "meet@example.com"][0]
    for _ in range(3):  # three free meeting sessions
        ask(billed, mode="meeting")
    assert billed.get("/api/billing").json()["account"]["trial_remaining"]["meeting"] == 0
    ev = {"id": "evt_e2e", "type": "checkout.session.completed", "data": {"object": {"id": "cs_e2e", "client_reference_id": acct["id"], "customer": "cus_e2e",
          "payment_status": "paid", "payment_intent": "pi_e2e", "amount_total": 1900, "currency": "usd", "metadata": {"package": "credits_1"}}}}
    assert httpx.post(server + "/__test/webhook", content=json.dumps(ev)).json()["result"] == "ok"
    sid = billed.post("/api/sessions", json={"mode": "meeting"}).json()["id"]
    for _ in range(3):  # three answers in ONE session within 30 minutes = one 30-minute block
        out = billed.post("/api/chat", json={"session_id": sid, "text": "Summarise", "mode": "meeting"}).text
        assert '"done"' in out
    assert billed.get("/api/billing").json()["account"]["credit_minutes"] == 30
