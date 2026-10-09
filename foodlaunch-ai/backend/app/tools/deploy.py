"""Local deployment: start the approved storefront revision as a real process.

The orchestrator runs independently of the storefront. Deploying exports the
exact approved commit into ``var/releases/<sha>``, stops the previous managed
process, verifies the port is free, starts uvicorn from that directory and
waits for a health check that reports the expected revision.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import new_id, now_iso, row, session
from app.records import audit, evidence
from app.tools import runner, workspace


def _pid_file() -> Path:
    return get_settings().run_dir / "storefront.json"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    cmdline = Path(f"/proc/{pid}/cmdline")
    if cmdline.exists():
        text = cmdline.read_bytes().decode(errors="replace")
        return "storefront.main" in text and "zombie" not in Path(f"/proc/{pid}/status").read_text()
    return True


def current_process() -> dict | None:
    path = _pid_file()
    if not path.exists():
        return None
    info = json.loads(path.read_text())
    if not _alive(info["pid"]):
        path.unlink(missing_ok=True)
        return None
    return info


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def stop_current(lifecycle: list[dict] | None = None) -> dict | None:
    info = current_process()
    if info is None:
        return None
    pid = info["pid"]
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.time() + 8
    while time.time() < deadline and _alive(pid):
        time.sleep(0.1)
    if _alive(pid):
        os.killpg(pid, signal.SIGKILL)
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    _pid_file().unlink(missing_ok=True)
    if lifecycle is not None:
        lifecycle.append({"ts": now_iso(), "event": "stopped", "pid": pid,
                          "release_id": info.get("release_id")})
    with session() as conn:
        conn.execute("UPDATE deployments SET status = 'stopped', finished_at = COALESCE(finished_at, ?)"
                     " WHERE pid = ? AND status = 'healthy'", (now_iso(), pid))
    return info


def health(timeout_s: float = 2.0) -> dict:
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.storefront_url}/health", timeout=timeout_s)
        return {"reachable": True, "status_code": response.status_code, **response.json()}
    except (httpx.HTTPError, ValueError) as exc:
        return {"reachable": False, "error": type(exc).__name__}


def _start(release_id: str, revision: str, deployment_id: str) -> tuple[int, Path]:
    settings = get_settings()
    release_dir = settings.releases_dir / revision
    if not (release_dir / "storefront").exists():
        workspace.export_revision(revision, release_dir)
    for d in (settings.run_dir, settings.telemetry_file.parent, settings.commerce_db.parent,
              settings.var_dir / "sandbox-home"):
        d.mkdir(parents=True, exist_ok=True)
    log_path = settings.run_dir / f"storefront-{deployment_id}.log"
    env = runner.scrubbed_env({
        "PYTHONPATH": str(release_dir),
        "STOREFRONT_COMMERCE_DB": str(settings.commerce_db),
        "STOREFRONT_INVENTORY_URL": settings.inventory_url,
        "STOREFRONT_DEMO_CLOCK": settings.demo_clock,
        "STOREFRONT_REVISION": revision,
        "STOREFRONT_RELEASE_ID": release_id,
        "STOREFRONT_TELEMETRY_PATH": str(settings.telemetry_file),
        "STOREFRONT_STATIC_DIR": str(settings.storefront_static),
    }, home=settings.var_dir / "sandbox-home")
    argv = [sys.executable, "-m", "uvicorn", "storefront.main:create_app", "--factory",
            "--host", "127.0.0.1", "--port", str(settings.storefront_port), "--log-level", "warning"]
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(argv, cwd=release_dir, env=env, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    return proc.pid, log_path


def deploy(release_id: str, revision: str, actor: str, action: str) -> dict:
    """Replace the running storefront with ``revision``. Returns the deployment record."""
    settings = get_settings()
    workspace.validate_revision(revision)
    deployment_id = new_id("DEP")
    lifecycle: list[dict] = [{"ts": now_iso(), "event": "requested", "action": action, "by": actor}]
    with session() as conn:
        conn.execute(
            "INSERT INTO deployments (id, release_id, revision, action, port, status, started_at,"
            " lifecycle_json, requested_by) VALUES (?, ?, ?, ?, ?, 'starting', ?, ?, ?)",
            (deployment_id, release_id, revision, action, settings.storefront_port, now_iso(),
             json.dumps(lifecycle), actor),
        )
    stop_current(lifecycle)
    deadline = time.time() + 6
    while not port_free(settings.storefront_port) and time.time() < deadline:
        time.sleep(0.2)
    status, health_info, pid, log_path = "failed", {}, None, None
    if not port_free(settings.storefront_port):
        lifecycle.append({"ts": now_iso(), "event": "port_in_use", "port": settings.storefront_port})
        health_info = {"error": f"port {settings.storefront_port} is held by an unmanaged process"}
    else:
        pid, log_path = _start(release_id, revision, deployment_id)
        lifecycle.append({"ts": now_iso(), "event": "started", "pid": pid})
        deadline = time.time() + 25
        while time.time() < deadline:
            health_info = health()
            if health_info.get("reachable"):
                break
            time.sleep(0.25)
        if health_info.get("reachable") and health_info.get("revision") == revision:
            status = "healthy"
            _pid_file().write_text(json.dumps({"pid": pid, "release_id": release_id, "revision": revision,
                                               "deployment_id": deployment_id, "started_at": now_iso()}))
            lifecycle.append({"ts": now_iso(), "event": "health_check_passed", "revision": revision})
        else:
            lifecycle.append({"ts": now_iso(), "event": "health_check_failed", "detail": health_info})
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    with session() as conn:
        conn.execute(
            "UPDATE deployments SET pid = ?, status = ?, finished_at = ?, health_json = ?, log_path = ?,"
            " lifecycle_json = ? WHERE id = ?",
            (pid, status, now_iso(), json.dumps(health_info), str(log_path) if log_path else None,
             json.dumps(lifecycle), deployment_id),
        )
    audit(actor, f"deployment.{action}", outcome="ok" if status == "healthy" else "failed",
          entity_type="deployment", entity_id=deployment_id, release_id=release_id, revision=revision)
    evidence("deployment", "local process manager",
             f"{action} of {revision[:10]} -> {status} (pid {pid})", "tool", revision=revision,
             ref_table="deployments", ref_id=deployment_id)
    return row("SELECT * FROM deployments WHERE id = ?", (deployment_id,))
