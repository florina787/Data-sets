"""Cyber Range: run a verification probe against an authorised target in an isolated, disposable process.

Isolation layers (all deterministic, none rely on the model):
  * a fresh temporary copy of the target (the original is never touched); deleted afterwards
  * `unshare -n`: a new network namespace with no interfaces (no egress, no ingress). Refuses to run without it
    unless ``shield_require_network_namespace`` is explicitly disabled
  * empty environment (no inherited credentials), HOME inside the copy, Python isolated mode (-I)
  * rlimits: CPU seconds, address space, open files, file size; own process group; wall-clock timeout
This is process-level isolation, adequate for the bundled training targets. Hostile third-party code needs a
microVM (e.g. Firecracker/gVisor), which is not implemented. See docs/CYBER_RANGE.md.
"""

from __future__ import annotations

import json
import os
import resource
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from florome.config import Settings

RUNNER = Path(__file__).with_name("probe_runner.py")
LIMITS = {"cpu_seconds": 20, "address_space_bytes": 2 * 1024**3, "open_files": 256, "file_size_bytes": 20 * 1024**2}


def netns_available() -> bool:
    try:
        return subprocess.run(["unshare", "-n", "true"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (LIMITS["cpu_seconds"], LIMITS["cpu_seconds"]))
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS["address_space_bytes"], LIMITS["address_space_bytes"]))
    resource.setrlimit(resource.RLIMIT_NOFILE, (LIMITS["open_files"], LIMITS["open_files"]))
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS["file_size_bytes"], LIMITS["file_size_bytes"]))


def run_isolated(settings: Settings, argv_after_python: list[str], workdir: Path, timeout: float) -> dict[str, Any]:
    netns = netns_available()
    if not netns and settings.shield_require_network_namespace:
        return {"outcome": "error", "error": "network namespace unavailable; refusing to run (fail closed)", "isolation": {"network_namespace": False}}
    cmd = (["unshare", "-n"] if netns else []) + [sys.executable, "-I", *argv_after_python]
    env = {"HOME": str(workdir), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    isolation = {"network_namespace": netns, "environment": sorted(env), "python_isolated_mode": True, "rlimits": LIMITS,
                 "workdir": "temporary copy, deleted after run", "timeout_seconds": timeout}
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=workdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            preexec_fn=_limits, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
        return {"outcome": "timeout", "isolation": isolation, "seconds": time.perf_counter() - t0, "stderr_tail": stderr[-800:]}
    return {"outcome": "exited", "returncode": proc.returncode, "stdout": stdout, "stderr_tail": stderr[-800:],
            "isolation": isolation, "seconds": time.perf_counter() - t0}


def run_probe(settings: Settings, target_root: Path, spec: dict[str, Any], source_override: dict[str, str] | None = None) -> dict[str, Any]:
    """Copy the target, plant a canary, optionally overlay patched sources, run the probe. Returns a transcript."""
    canary = secrets.randbelow(9_000_000) + 1_000_000
    with tempfile.TemporaryDirectory(prefix="florome-range-") as tmp:
        work = Path(tmp)
        copy = work / "target"
        shutil.copytree(target_root, copy, ignore=shutil.ignore_patterns("*.db", "__pycache__"))
        for rel, text in (source_override or {}).items():
            (copy / rel).write_text(text)
        (copy / "secret_canary.txt").write_text(f"CANARY {canary}\n")  # outside the file base: reading it proves traversal
        shutil.copy(RUNNER, work / "probe_runner.py")
        spec_file = work / "spec.json"
        spec_file.write_text(json.dumps({**spec, "root": str(copy), "canary": canary}))
        res = run_isolated(settings, [str(work / "probe_runner.py"), str(spec_file)], work, settings.shield_probe_timeout_seconds)
    if res["outcome"] != "exited":
        return {**res, "reproduced": None}
    try:
        payload = json.loads(res["stdout"].strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {**res, "outcome": "error", "reproduced": None, "error": "probe produced no result"}
    return {"outcome": "reproduced" if payload.get("reproduced") else "not_reproduced", "reproduced": bool(payload.get("reproduced")),
            "probe": payload, "isolation": res["isolation"], "seconds": res["seconds"], "stderr_tail": res["stderr_tail"][-300:]}
