"""Agent Containment Supervisor (deterministic; independent of any model).

For each session: issue a short-lived synthetic credential, build a disposable workspace (plus a decoy secret
outside it), run the workload under ``agent_guard`` inside a network namespace with an empty environment and
rlimits, then decide from facts only: the guard's event file, the exit status and the time taken. On violation:
terminate (already done by the guard or by the supervisor's kill), revoke the credential, preserve forensic
evidence (events, output tails, workspace file hashes) and notify by audit event.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from florome.config import Settings
from florome.models import new_id, utcnow
from florome.security import audit
from florome.security.rbac import Principal
from florome.shield.containment.scenarios import SCENARIOS
from florome.shield.control import authorize
from florome.shield.models import ContainmentEvent, TemporaryCredential
from florome.shield.range.sandbox import netns_available

GUARD = Path(__file__).with_name("agent_guard.py")
CPU_SECONDS = 3
WALL_SECONDS = 10


def _limits() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024**2, 5 * 1024**2))


def run_scenario(db: Session, settings: Settings, p: Principal, scenario: str) -> ContainmentEvent:
    authorize(db, settings, p, "containment.run", {"id": scenario})
    if scenario not in SCENARIOS:
        raise KeyError(scenario)
    sc = SCENARIOS[scenario]
    session_id = new_id("agsess")
    token = secrets.token_urlsafe(24)
    cred = TemporaryCredential(tenant_id=p.tenant_id, session_id=session_id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               expires_at=utcnow() + timedelta(minutes=5))
    db.add(cred)
    db.flush()
    netns = netns_available()
    with tempfile.TemporaryDirectory(prefix="florome-agent-") as tmp:
        home = Path(tmp)
        work = home / "workspace"
        work.mkdir()
        (home / ".ssh").mkdir()
        (home / ".ssh" / "id_ed25519").write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nSYNTHETIC-DECOY-NOT-A-REAL-KEY\n-----END OPENSSH PRIVATE KEY-----\n")
        (work / "input.txt").write_text("synthetic quarterly figures for a contained analysis agent\n")
        (work / "agent.py").write_text(sc["code"])
        events = home / "guard-events.jsonl"
        stdlib = [os.path.dirname(os.__file__), sys.prefix, sys.base_prefix, "/usr/lib", "/dev/urandom", "/dev/null", "/proc/self"]
        policy = {"event_file": str(events), "workdir": str(work), "read_roots": stdlib, "script": str(work / "agent.py")}
        env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "FLOROME_GUARD_POLICY": json.dumps(policy), "FLOROME_SESSION_TOKEN": token}
        cmd = (["unshare", "-n"] if netns else []) + [sys.executable, "-I", str(GUARD)]
        t0 = time.perf_counter()
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=_limits,
                                start_new_session=True)
        killed = False
        try:
            out, err = proc.communicate(timeout=WALL_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            killed = True
        secs = time.perf_counter() - t0
        guard_events = [json.loads(x) for x in events.read_text().splitlines()] if events.exists() else []
        workspace = {str(f.relative_to(work)): hashlib.sha256(f.read_bytes()).hexdigest() for f in work.rglob("*") if f.is_file()}
        escaped = (home / "escape_marker.txt").exists()
        shutil.rmtree(home / ".ssh", ignore_errors=True)

    violation = guard_events[0]["violation"] if guard_events else None
    if violation is None and (killed or proc.returncode in (-signal.SIGXCPU, -signal.SIGKILL, 152, 137)):
        violation = "resource_limit"
    if escaped and violation is None:
        violation = "write_outside_workdir"
    actions: list[str] = []
    if violation:
        actions.append("session_terminated" if proc.returncode is not None else "session_killed")
        cred.revoked, cred.revoked_reason = True, f"containment: {violation}"
        actions.append("credential_revoked")
        actions.append("forensics_preserved")
        actions.append("operators_notified_via_audit")
    outcome = "contained" if violation else ("completed" if proc.returncode == 0 else "error")
    ev = ContainmentEvent(tenant_id=p.tenant_id, session_id=session_id, scenario=scenario, violation=violation, actions_taken=actions,
                          outcome=outcome,
                          forensics={"guard_events": guard_events, "returncode": proc.returncode, "seconds": round(secs, 3), "wall_timeout_hit": killed,
                                     "stdout_tail": out[-400:], "stderr_tail": err[-400:], "workspace_sha256": workspace,
                                     "isolation": {"network_namespace": netns, "environment": "empty except policy + session token",
                                                   "cpu_seconds": CPU_SECONDS, "wall_seconds": WALL_SECONDS},
                                     "expected": sc["expected"], "matched_expectation": (violation or "completed") == sc["expected"]})
    db.add(ev)
    audit.record(db, p.tenant_id, p.user_id, "shield.containment", session_id, "denied" if violation else "success",
                 {"scenario": scenario, "violation": violation, "actions": actions})
    db.flush()
    return ev
