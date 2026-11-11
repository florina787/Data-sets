"""Production-readiness tests: SPA serving, readiness, ops dashboard, Supabase JWKS auth, inference outages."""
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.config import get_settings
from app.llm import qwen
from app.security import auth as auth_mod

from .conftest import RESUME, admin_headers, register, search_jobs, upload_resume


# ---------------------------------------------------------------- single-origin SPA serving
def test_frontend_served_from_same_origin(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root>careerflo</div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    from app.main import create_app

    with TestClient(create_app()) as c:
        assert "careerflo" in c.get("/").text
        assert "careerflo" in c.get("/app/jobs").text              # client-side route falls back to index.html
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/favicon.svg").status_code == 200
        assert c.get("/api/health").json() == {"status": "ok"}     # API is not shadowed
        assert c.get("/api/does-not-exist").status_code == 404
        assert "careerflo" in c.get("/../../etc/passwd").text      # traversal never escapes dist


# ---------------------------------------------------------------- readiness
def test_readiness_reports_degraded_and_down(client, monkeypatch):
    r = client.get("/api/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"]["ok"]
    assert r.json()["checks"]["payments"]["mode"] == "off"
    import app.db as dbmod

    class Boom:
        def __enter__(self):
            raise ConnectionError("db down")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(dbmod, "SessionLocal", lambda: Boom())
    r = client.get("/api/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "down"


# ---------------------------------------------------------------- ops dashboard
def test_ops_dashboard_admin_only_and_labelled(client, user):
    h, _ = user
    client.get("/api/usage", headers=h)
    assert client.get("/api/admin/ops", headers=h).status_code == 403
    d = client.get("/api/admin/ops", headers=admin_headers(client)).json()
    assert d["measured"]["api"]["requests"] > 0 and d["measured"]["api"]["latency_ms"]["p50"] is not None
    assert d["measured"]["api"]["active_users_15m"] >= 1
    assert "estimates" in d["estimated"]["note"] and "Stripe" in d["revenue"]["note"]


# ---------------------------------------------------------------- Supabase Auth (ES256 + JWKS), real signatures
class _Jwks(BaseHTTPRequestHandler):
    body = b"{}"

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200 if self.path.endswith("/auth/v1/.well-known/jwks.json") else 404)
        self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(_Jwks.body)


@pytest.fixture
def supabase_mode(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk |= {"kid": "test-kid", "alg": "ES256", "use": "sig"}
    _Jwks.body = json.dumps({"keys": [jwk]}).encode()
    srv = HTTPServer(("127.0.0.1", 0), _Jwks)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "")
    get_settings.cache_clear(); auth_mod._jwks_client.cache_clear()
    yield key
    srv.shutdown()
    monkeypatch.undo()
    get_settings.cache_clear(); auth_mod._jwks_client.cache_clear()


def _token(key, sub, email, **over):
    claims = {"sub": sub, "email": email, "aud": "authenticated", "role": "authenticated", "exp": int(time.time()) + 600,
              "iat": int(time.time()), "email_confirmed_at": "2026-01-01T00:00:00Z"} | over
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-kid"})


def test_supabase_jwks_verification(client, supabase_mode):
    key = supabase_mode
    sub = str(uuid.uuid4())
    h = {"Authorization": f"Bearer {_token(key, sub, f'sb-{sub[:8]}@example.com')}"}
    me = client.get("/api/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["id"] == sub          # provisioned with id = auth.uid()
    assert client.get("/api/usage", headers=h).json()["features"][0]["trial_remaining"] == 2
    other = ec.generate_private_key(ec.SECP256R1())
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(other, sub, 'x@example.com')}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(key, sub, 'x@example.com', exp=int(time.time()) - 5)}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(key, sub, 'x@example.com', aud='anon')}"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": "a@b.co", "password": "CorrectHorse42"}).status_code == 400
    # email change keeps the same account (and trial counters)
    new = client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(key, sub, f'changed-{sub[:8]}@example.com')}"})
    assert new.json()["id"] == sub and new.json()["email"].startswith("changed-")


# ---------------------------------------------------------------- inference outage → graceful degradation
@pytest.fixture
def llm_down(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "llamacpp")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9")      # nothing listens here
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "3")
    get_settings.cache_clear(); qwen.reset_llm()
    yield
    monkeypatch.undo()
    get_settings.cache_clear(); qwen.reset_llm()


def test_features_degrade_when_model_is_down(client, user, llm_down):
    h, _ = user
    upload_resume(client, h)
    jid = search_jobs(client, h)["jobs"][0]["id"]
    r = client.post("/api/resumes/tailor", headers=h, json={"job_id": jid})
    assert r.status_code == 200 and "Qwen unavailable" in r.json()["summary_source"]
    assert r.json()["validation"]["final"]["valid"]
    assert client.get("/api/health/ready").json()["status"] == "degraded"
    cid = client.post("/api/chat/conversations", headers=h).json()["id"]
    with client.stream("POST", f"/api/chat/conversations/{cid}/messages", headers=h, json={"content": "hello, any tips?"}) as s:
        events = [json.loads(l[6:]) for l in s.iter_lines() if l.startswith("data: ")]
    assert any(e["type"] == "done" and e.get("charged") is False for e in events)
    feats = {f["id"]: f for f in client.get("/api/usage", headers=h).json()["features"]}
    assert feats["ai_chat"]["trial_remaining"] == 2                  # degraded chat is not charged
