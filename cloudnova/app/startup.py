"""`python -m app` — bring up the complete application with preflight + readiness checks.

Steps (each logged with timing): config → data (reuse or build) → local Qwen (connect, or start via LLM_START_CMD)
→ query-agent readiness (six stakeholder questions) → API + dashboard → /health → READY. Ctrl+C / SIGTERM shut
down gracefully (uvicorn drains, a Qwen process we started is stopped, DuckDB closed).
If Qwen is unavailable the app still starts in deterministic mode: approved-metric analytics, data quality and the
eval harness work; general chat / free-form text-to-SQL return a clear `llm_unavailable` error.
"""
from __future__ import annotations

import shlex
import signal
import socket
import subprocess
import sys
import threading
import time

from .config import get_settings

T0 = time.perf_counter()


def log(icon: str, msg: str) -> None:
    print(f"[{time.perf_counter() - T0:6.1f}s] {icon} {msg}", flush=True)


class StartupError(Exception):
    pass


def check_config():
    s = get_settings()
    if not s.raw_csv.exists():
        raise StartupError(f"raw CSV not found at {s.raw_csv} (set CLOUDNOVA_RAW_CSV)")
    if s.llm_provider not in ("qwen", "none"):
        raise StartupError(f"LLM_PROVIDER must be 'qwen' or 'none', got {s.llm_provider!r}")
    if not 0 < s.max_result_rows <= 10000:
        raise StartupError("MAX_RESULT_ROWS must be between 1 and 10000")
    return s


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def ensure_qwen(s, allow_start: bool) -> tuple[dict, subprocess.Popen | None]:
    from .llm.provider import provider_status
    if s.llm_provider == "none":
        return provider_status(), None
    st = provider_status()
    if st["reachable"]:
        return st, None
    if not (allow_start and s.llm_start_cmd):
        return st, None
    log("…", f"Qwen not answering at {s.llm_base_url}; starting it with LLM_START_CMD (timeout {s.llm_start_timeout_s:.0f}s)")
    logf = open(s.runtime_dir / "qwen-server.log", "ab")
    proc = subprocess.Popen(shlex.split(s.llm_start_cmd), stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.time() + s.llm_start_timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise StartupError(f"LLM_START_CMD exited with code {proc.returncode}; see {s.runtime_dir / 'qwen-server.log'}")
        st = provider_status()
        if st["reachable"]:
            return st, proc
        time.sleep(1.0)
    proc.terminate()
    raise StartupError(f"Qwen did not become ready within {s.llm_start_timeout_s:.0f}s; see {s.runtime_dir / 'qwen-server.log'}")


def readiness(s, llm: dict) -> dict:
    """Run the six stakeholder questions through the real agent (deterministic path) + one tiny Qwen generation."""
    from .__main__ import STAKEHOLDER_QUESTIONS
    from .agent import supervisor
    sid = supervisor.new_session()
    rows = []
    for i, q in enumerate(STAKEHOLDER_QUESTIONS, 1):
        r = supervisor.ask(q, sid)
        first = r["answer"].replace("**", "").split("\n")[0]
        rows.append((i, r["latency_ms"], first[:110]))
    out = {"stakeholder": rows, "qwen_generation": None}
    if llm.get("reachable"):
        from .llm.provider import get_provider
        try:
            resp = get_provider().complete("Reply with exactly one word.", [{"role": "user", "content": "Say ready."}], max_tokens=5)
            out["qwen_generation"] = (resp.text.strip()[:20], resp.latency_ms)
        except Exception as exc:  # reported, not fatal: analytics do not need the model
            out["qwen_generation"] = (f"error: {exc}", 0)
    return out


def up(host: str | None = None, port: int | None = None, allow_llm_start: bool = True, open_checks: bool = True) -> int:
    import uvicorn

    from . import db
    from .pipeline.build import build

    print("\n☁  CloudNova Revenue Intelligence Copilot — starting\n", flush=True)
    qwen_proc = None
    try:
        s = check_config()
        s.runtime_dir.mkdir(parents=True, exist_ok=True)
        host, port = host or s.host, port or s.port
        log("✓", f"config ok · FX rule={s.fx_direction} · LLM_PROVIDER={s.llm_provider} · {s.llm_base_url}")
        if not port_free(host, port):
            raise StartupError(f"port {port} on {host} is already in use (another CloudNova running? set CLOUDNOVA_PORT)")
        m = build(quiet=True)
        log("✓", f"data {'reused (raw CSV hash unchanged — no reprocessing)' if m['reused'] else 'built from raw CSV'}: {m['clean_invoices']:,} invoices · "
                 f"{m['accounts']:,} accounts · {m['rejected_rows']} rows audited in rejected_rows · {s.db_path.name} (read-only)")
        llm, qwen_proc = ensure_qwen(s, allow_llm_start)
        if s.llm_provider == "none":
            log("•", "LLM disabled (LLM_PROVIDER=none): deterministic mode")
        elif llm["reachable"]:
            log("✓", f"local Qwen reachable: {', '.join(llm['served_models']) or llm['model']}"
                     + (" (started by this process)" if qwen_proc else " (existing runtime)"))
        else:
            log("!", f"local Qwen NOT reachable at {s.llm_base_url} → deterministic mode. Approved-metric analytics, data quality "
                     f"and evals work; general chat / free-form SQL will return llm_unavailable. Start Qwen or set LLM_START_CMD.")
        if open_checks:
            r = readiness(s, llm)
            for i, ms, ans in r["stakeholder"]:
                log("✓", f"Q{i} ({ms:.0f} ms) {ans}")
            if r["qwen_generation"]:
                txt, ms = r["qwen_generation"]
                log("✓" if not txt.startswith("error") else "!", f"Qwen generation check: {txt!r} in {ms:.0f} ms")
        db.reset_connections()
    except StartupError as exc:
        log("✗", f"startup failed: {exc}")
        if qwen_proc:
            qwen_proc.terminate()
        return 2

    config = uvicorn.Config("app.api:app", host=host, port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)

    def announce():
        import httpx
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        try:
            h = httpx.get(f"http://{host}:{port}/health", timeout=5, trust_env=False).json()
            log("✓", f"API healthy · data={h['data']['ok']} · llm={h['llm']['mode']}")
        except Exception as exc:
            log("!", f"health check failed: {exc}")
        print(f"\n  READY in {time.perf_counter() - T0:.1f}s\n"
              f"  Dashboard   http://{host}:{port}/\n"
              f"  Ask (API)   POST http://{host}:{port}/ask   {{\"question\": \"...\"}}\n"
              f"  Health      http://{host}:{port}/health\n"
              f"  API docs    http://{host}:{port}/docs\n"
              f"  Press Ctrl+C to stop.\n", flush=True)

    threading.Thread(target=announce, daemon=True).start()

    def _sigterm(*_):  # uvicorn drains, restores this handler and re-raises SIGTERM → exit through `finally`
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _sigterm)
    try:
        server.run()  # installs SIGINT/SIGTERM handlers and drains in-flight requests
    except KeyboardInterrupt:  # uvicorn ≥0.30 re-raises the signal after draining; that is a normal stop
        pass
    finally:
        log("•", "shutting down")
        if qwen_proc and qwen_proc.poll() is None:
            qwen_proc.terminate()
            try:
                qwen_proc.wait(10)
            except subprocess.TimeoutExpired:
                qwen_proc.kill()
            log("•", "stopped the Qwen server this process started")
        db.reset_connections()
        log("✓", "stopped cleanly")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(up())
