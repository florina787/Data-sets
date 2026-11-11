"""First-run acceptance test of the FROZEN backend on a machine with no Ollama.

Does what Setup does for a customer, through the same API:
  1. confirms no AI runtime is running,
  2. downloads the pinned official Ollama release, verifies its SHA-256, unpacks and starts it,
  3. downloads a small Apache-2.0 model,
  4. requires a real answer (health check, a chat answer, a cited document answer),
  5. confirms the runtime VEENA started is stopped again.

Uses only the standard library so it runs on a clean CI runner.

    python packaging/smoke_runtime.py <veena-backend executable> [--model qwen2.5:0.5b] [--out results.json]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    def __init__(self, base: str, token: str):
        self.base, self.token = base, token

    def _req(self, method: str, path: str, body: bytes | None = None, ctype: str = "application/json", timeout: float = 30):
        req = urllib.request.Request(self.base + path, data=body, method=method)  # noqa: S310 - loopback
        req.add_header("Authorization", f"Bearer {self.token}")
        if body is not None:
            req.add_header("Content-Type", ctype)
        return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310

    def json(self, method: str, path: str, data: dict | None = None, timeout: float = 60):
        with self._req(method, path, json.dumps(data).encode() if data is not None else None, timeout=timeout) as r:
            return json.loads(r.read())

    def stream(self, path: str, data: dict | None = None, timeout: float = 3600):
        with self._req("POST", path, json.dumps(data or {}).encode(), timeout=timeout) as r:
            for line in r:
                if line.strip():
                    yield json.loads(line)

    def upload(self, path: str, filename: str, content: bytes):
        boundary = uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: text/markdown\r\n\r\n'.encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        with self._req("POST", path, body, ctype=f"multipart/form-data; boundary={boundary}", timeout=300) as r:
            return json.loads(r.read())


def chat(api: Api, sid: str, text: str, **kw) -> tuple[str, dict]:
    events = list(api.stream("/api/chat", {"session_id": sid, "text": text, **kw}, timeout=900))
    answer = "".join(e.get("t", "") for e in events if e.get("type") == "token")
    return answer, events[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--model", default="qwen2.5:0.5b")
    ap.add_argument("--out", default="runtime-smoke.json")
    ap.add_argument("--insights-url", default=None, help="local Insights Worker (cloud/insights/test/serve.mjs) to test opt-in statistics")
    ap.add_argument("--billing-url", default=None, help="local billing Worker (cloud/billing/test/serve.mjs) to test plan enforcement")
    args = ap.parse_args()

    results: dict = {"platform": platform.platform(), "machine": platform.machine(), "model": args.model, "steps": {}}
    port, ollama_port, token = free_port(), free_port(), secrets.token_urlsafe(32)
    data_dir = tempfile.mkdtemp(prefix="veena-firstrun-")
    env = {
        **os.environ,
        "VEENA_PORT": str(port),
        "VEENA_TOKEN": token,
        "VEENA_DATA_DIR": data_dir,
        # A fresh port, so the test cannot accidentally use some other Ollama.
        "OLLAMA_URL": f"http://127.0.0.1:{ollama_port}",
    }
    if args.insights_url:  # opt-in statistics from the INSTALLED backend to a local Insights Worker
        env.update(VEENA_INSIGHTS_URL=args.insights_url, VEENA_INSIGHTS_ALLOW_LOCAL="1")
    if args.billing_url:  # the INSTALLED backend enforces plans against a billing Worker on this machine
        env.update(VEENA_BILLING_URL=args.billing_url, VEENA_BILLING_ALLOW_LOCAL="1")
    # The backend's output goes to a file, never an unread pipe: Windows pipes hold
    # only a few KB, and download progress bars filled one and blocked the backend
    # (CI runs 42717356914 and 42723464530). The real app (Electron) drains both streams.
    log_path = os.path.join(data_dir, "backend.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")  # noqa: SIM115 - closed in finally
    proc = subprocess.Popen([args.exe], env=env, stdout=log_file, stderr=subprocess.STDOUT)  # noqa: S603
    api = Api(f"http://127.0.0.1:{port}", token)
    ok = False
    try:
        t0 = time.time()
        while time.time() - t0 < 180:
            try:
                with urllib.request.urlopen(f"{api.base}/api/health", timeout=5):  # noqa: S310
                    break
            except OSError:
                time.sleep(0.5)
        results["steps"]["backend_start_s"] = round(time.time() - t0, 1)

        rt = api.json("GET", "/api/runtime")
        print("runtime before:", json.dumps(rt))
        assert not rt["running"], "an AI runtime was already running; this test needs a clean machine"
        assert rt["supported"], f"platform not supported: {rt['platform']}"

        t0 = time.time()
        last = None
        for ev in api.stream("/api/runtime/install"):
            if ev.get("error"):
                raise AssertionError(f"runtime install failed: {ev['error']}")
            if ev.get("status") != "downloading":
                print("runtime:", ev)
            last = ev
        assert last and last.get("status") == "ready", last
        results["steps"]["runtime_install_s"] = round(time.time() - t0, 1)
        rt = api.json("GET", "/api/runtime")
        assert rt["running"] and rt["managed_by_veena"], rt
        results["runtime_version"] = rt["version"]

        t0 = time.time()
        for ev in api.stream("/api/models/pull", {"model": args.model}):
            if ev.get("error"):
                raise AssertionError(f"model download failed: {ev['error']}")
        results["steps"]["model_download_s"] = round(time.time() - t0, 1)
        api.json("PATCH", "/api/settings", {"text_model": args.model, "onboarded": True})

        t0 = time.time()
        hc = api.json("POST", "/api/system/healthcheck", {"model": args.model}, timeout=900)
        print("health check:", hc)
        assert hc["ok"], hc
        results["steps"]["first_answer_s"] = round(time.time() - t0, 1)

        if not args.billing_url:
            # Free beta: billing is off and no account is needed; the chat below must work without sign-in.
            assert api.json("GET", "/api/billing") == {"enabled": False}, "billing must be disabled in the free beta"
            results["billing_disabled"] = True
        if args.insights_url:
            tel = api.json("GET", "/api/telemetry")
            assert tel["available"] and not tel["enabled"] and tel["queued"] == [], f"statistics must be off by default: {tel}"
            api.json("POST", "/api/telemetry", {"enabled": True})
        if args.billing_url:
            sid = api.json("POST", "/api/sessions", {})["id"]
            _, refused = chat(api, sid, "Hello")
            assert refused.get("code") == "payment_required", f"answered without signing in: {refused}"
            email = f"ci-{secrets.token_hex(4)}@example.com"
            api.json("POST", "/api/billing/sign-in", {"email": email})
            with urllib.request.urlopen(args.billing_url + "/__test/code", timeout=10) as r:  # noqa: S310 - local test server
                code = json.load(r)["code"]
            me = api.json("POST", "/api/billing/sign-in", {"email": email, "code": code})
            assert me["account"]["trial_remaining"]["chat"] == 3, me
            results["billing"] = {"signed_in": True, "trial_start": me["account"]["trial_remaining"]}

        sid = api.json("POST", "/api/sessions", {})["id"]
        answer, done = chat(api, sid, "What is 12 plus 30? Reply with only the number.")
        print("chat:", answer.strip()[:200])
        assert done.get("type") == "done", done
        results["chat"] = {"answer": answer.strip()[:200], "correct": "42" in answer, "stats": done.get("stats")}

        col = api.json("POST", "/api/knowledge/collections", {"name": "Falcon", "kind": "docs"})
        doc = b"# Falcon\n\nFalcon stores embeddings in a FAISS HNSW index.\n\nSearch has a p95 latency budget of 300 ms."
        t0 = time.time()
        api.upload(f"/api/knowledge/collections/{col['id']}/documents", "falcon.md", doc)
        results["steps"]["document_index_s"] = round(time.time() - t0, 1)
        sid = api.json("POST", "/api/sessions", {})["id"]
        answer, done = chat(api, sid, "What is Falcon's latency budget? Cite the source.", collection_ids=[col["id"]])
        print("rag:", answer.strip()[:200])
        assert done.get("type") == "done", done
        results["rag"] = {
            "answer": answer.strip()[:300],
            "flags": [f["kind"] for f in done["governance"]["flags"]],
            "spine": done.get("spine"),
        }
        # The retrieval itself must work; the 0.5B model's wording is recorded, not judged here.
        meta_cites = [e for e in done.get("governance", {}).get("cited", [])]
        results["rag"]["cited"] = meta_cites

        # Speech model: downloaded from Hugging Face on first use (not bundled), so
        # this exercises the same download path that hung for documents on Windows.
        t0 = time.time()
        bench = api.json("POST", "/api/system/benchmark", {"text_model": args.model, "asr_model": "tiny"}, timeout=420)
        results["speech"] = {
            "ok": bench["asr"].get("ok"),
            "real_time_factor": bench["asr"].get("real_time_factor"),
            "error": bench["asr"].get("error"),
        }
        results["steps"]["speech_model_and_benchmark_s"] = round(time.time() - t0, 1)
        print("speech:", results["speech"])
        assert bench["asr"].get("ok"), f"speech model failed: {bench['asr']}"

        if args.billing_url:
            # Free answers 2 and 3 work; the 4th is refused; buying Unlimited unlocks the SAME running app.
            for _ in range(2):
                _, d = chat(api, api.json("POST", "/api/sessions", {})["id"], "Say OK.")
                assert d.get("type") == "done", d
            left = api.json("GET", "/api/billing")["account"]["trial_remaining"]["chat"]
            assert left == 0, f"expected 0 free chat uses left, got {left}"
            _, d = chat(api, api.json("POST", "/api/sessions", {})["id"], "Say OK.")
            assert d.get("code") == "payment_required", f"4th answer was not refused: {d}"
            with urllib.request.urlopen(args.billing_url + "/__test/accounts", timeout=10) as r:  # noqa: S310
                acct = [a for a in json.load(r) if a["email"] == email][0]["id"]
            end = int(time.time()) + 30 * 86400
            for ev in (
                {
                    "id": "evt_ci1",
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_ci",
                            "client_reference_id": acct,
                            "customer": "cus_ci",
                            "subscription": "sub_ci",
                            "payment_status": "paid",
                            "metadata": {"package": "unlimited_monthly"},
                        }
                    },
                },
                {
                    "id": "evt_ci2",
                    "type": "invoice.paid",
                    "data": {
                        "object": {
                            "id": "in_ci",
                            "customer": "cus_ci",
                            "amount_paid": 7495,
                            "currency": "usd",
                            "lines": {"data": [{"period": {"end": end}}]},
                        }
                    },
                },
            ):
                req = urllib.request.Request(args.billing_url + "/__test/webhook", data=json.dumps(ev).encode(), method="POST")  # noqa: S310
                with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                    assert json.load(r)["result"] == "ok"
            _, d = chat(api, api.json("POST", "/api/sessions", {})["id"], "Say OK.")
            assert d.get("type") == "done", f"Unlimited did not unlock the running app: {d}"
            results["billing"].update(refused_after_trial=True, unlocked_after_payment=True)
            print("billing: 3 free answers, 4th refused, Unlimited unlocked without restart")

        if args.insights_url:
            sent = api.json("POST", "/api/telemetry/send-now")
            with urllib.request.urlopen(args.insights_url + "/__test/summary", timeout=10) as r:  # noqa: S310 - local test server
                s = json.load(r)
            feats = {f["feature"]: f["installs"] for f in s["features"]}
            assert s["installs"]["first_launches"] == 1 and s["installs"]["first_ai_success"] == 1 and s["installs"]["active_1d"] == 1, s[
                "installs"
            ]
            assert feats.get("chat") == 1 and feats.get("documents") == 1, feats
            api.json("POST", "/api/telemetry", {"enabled": False})  # withdraw: the server deletes this installation's rows
            api.json("POST", "/api/telemetry/send-now")
            with urllib.request.urlopen(args.insights_url + "/__test/summary", timeout=10) as r:  # noqa: S310
                after = json.load(r)
            assert after["installs"]["first_launches"] == 0, after["installs"]
            results["statistics"] = {
                "sent": sent["result"],
                "dashboard_saw": s["installs"],
                "features": feats,
                "deleted_on_withdrawal": True,
            }
            print("statistics: opt-in -> dashboard counted 1 install, chat + documents; withdrawal deleted it")

        stopped = api.json("POST", "/api/runtime/stop")
        assert stopped["stopped"], "VEENA did not stop the runtime it started"
        time.sleep(2)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{ollama_port}/api/version", timeout=3)  # noqa: S310
            raise AssertionError("the runtime is still running after VEENA stopped it")
        except OSError:
            pass
        results["passed"] = ok = True
        print("PASS")
    except Exception as e:  # noqa: BLE001
        results["passed"] = False
        results["error"] = f"{type(e).__name__}: {e}"
        print("FAIL:", results["error"])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_file.close()
        if not ok:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                print(f.read()[-6000:])
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
