"""Runs INSIDE the contained process, before any agent code. Installs a Python audit hook that enforces policy.

On the first violation the hook writes one JSON line to the event file and terminates the process with
``os._exit(86)``. It never asks the agent to stop: termination is unconditional. Audit hooks cannot be removed
from Python code; native code (ctypes) could bypass them, so ctypes loading is itself a violation, and the
network namespace, empty environment and rlimits applied by the supervisor remain in force regardless.
"""

import json
import os
import sys

POLICY = json.loads(os.environ.get("FLOROME_GUARD_POLICY", "{}"))
EVENTS = POLICY["event_file"]
WORKDIR = os.path.realpath(POLICY["workdir"])
READ_ROOTS = [os.path.realpath(p) for p in POLICY["read_roots"]] + [WORKDIR]
_fired = False


def _violation(kind: str, detail: str) -> None:
    global _fired
    if _fired:
        os._exit(86)
    _fired = True
    with open(EVENTS, "a") as fh:  # opened before the hook rejects further file access
        fh.write(json.dumps({"violation": kind, "detail": detail[:300]}) + "\n")
    os._exit(86)


def _inside(path: str, roots: list[str]) -> bool:
    rp = os.path.realpath(path)
    return any(rp == r or rp.startswith(r + os.sep) for r in roots)


def hook(event: str, args: tuple) -> None:
    if _fired:
        return
    if event in ("socket.connect", "socket.getaddrinfo", "socket.bind", "socket.sendto"):
        _violation("network_egress", f"{event} {args[1:2]!r}")
    elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty"):
        _violation("subprocess_spawn", f"{event} {str(args)[:200]}")
    elif event.startswith("ctypes.") or event == "ctypes.dlopen":
        _violation("native_code_load", event)
    elif event == "open" and args and isinstance(args[0], str | bytes):
        path = os.fsdecode(args[0])
        if path == EVENTS:
            return
        mode = args[1] if len(args) > 1 and isinstance(args[1], str) else "r"
        writing = any(c in mode for c in "wax+")
        if writing and not _inside(path, [WORKDIR]):
            _violation("write_outside_workdir", path)
        if not writing and not _inside(path, READ_ROOTS):
            _violation("restricted_file_read", path)
    elif event in ("os.chmod", "os.chown", "os.setuid", "os.setgid") and args:
        _violation("privilege_change", event)


sys.addaudithook(hook)
script = POLICY["script"]
sys.argv = [script]
code = compile(open(script).read(), script, "exec")
exec(code, {"__name__": "__main__"})  # noqa: S102 - the agent workload, under the hook
