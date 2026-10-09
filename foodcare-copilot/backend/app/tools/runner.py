"""Restricted command execution.

Agents never get a shell. Each tool maps a typed request onto a fixed argv
built here, with validated arguments, a timeout, an output cap, a scrubbed
environment (no credentials, no developer HOME) and a working directory that
must sit inside the platform's var directory.

No container runtime is required. When none is available (the default), only
trusted seeded patches are executed; see docs/SECURITY_AND_SANDBOX.md.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.errors import ToolRejected

SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TZ", "SYSTEMROOT")


@dataclass
class CommandResult:
    argv: list[str]
    exit_code: int
    output: str
    duration_s: float
    timed_out: bool
    truncated: bool

    @property
    def command(self) -> str:
        return " ".join(self.argv)


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root = root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ToolRejected("Path escapes the permitted directory", path=str(path), root=str(root))
    return resolved


def scrubbed_env(extra: dict[str, str] | None = None, home: Path | None = None) -> dict[str, str]:
    env = {k: os.environ[k] for k in SAFE_ENV_KEYS if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    if home is not None:
        env["HOME"] = str(home)
    for key, value in (extra or {}).items():
        if "KEY" in key.upper() or "TOKEN" in key.upper() or "SECRET" in key.upper():
            raise ToolRejected("Credentials may not be passed to tool processes", key=key)
        env[key] = value
    return env


def _limits() -> None:  # runs in the child before exec (POSIX only)
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
        resource.setrlimit(resource.RLIMIT_FSIZE, (200 * 1024 * 1024, 200 * 1024 * 1024))
    except (ImportError, ValueError, OSError):
        pass


def run(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_s: int | None = None,
) -> CommandResult:
    settings = get_settings()
    ensure_within(cwd, settings.var_dir)
    if argv[0] not in (sys.executable, "git"):
        raise ToolRejected("Executable is not on the tool allow-list", executable=argv[0])
    timeout_s = timeout_s or settings.tool_timeout_s
    started = time.perf_counter()
    posix = os.name == "posix"
    proc = subprocess.Popen(
        argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=posix,
        preexec_fn=_limits if posix else None,  # noqa: PLW1509 - no threads touched
    )
    timed_out = False
    try:
        raw, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        if posix:
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        raw, _ = proc.communicate()
    text = raw.decode("utf-8", errors="replace")
    limit = settings.tool_output_limit
    truncated = len(text) > limit
    if truncated:
        text = text[:limit // 4] + "\n…[output truncated]…\n" + text[-limit // 2:]
    return CommandResult(argv, -9 if timed_out else proc.returncode, text,
                         round(time.perf_counter() - started, 3), timed_out, truncated)
