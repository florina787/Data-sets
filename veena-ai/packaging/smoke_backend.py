"""Smoke test for the frozen backend executable (no Ollama needed).

python packaging/smoke_backend.py packaging/backend-dist/veena-backend/veena-backend[.exe]
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url: str, token: str | None = None, timeout: float = 10) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - loopback URL built above
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    exe = sys.argv[1]
    port, token = free_port(), secrets.token_urlsafe(32)
    env = {**os.environ, "VEENA_PORT": str(port), "VEENA_TOKEN": token, "VEENA_DATA_DIR": tempfile.mkdtemp()}
    # The backend's log goes to a file, never an unread pipe: once a pipe's buffer
    # fills (small on Windows) the backend blocks on logging and requests hang.
    log_path = os.path.join(env["VEENA_DATA_DIR"], "smoke-backend.log")
    log = open(log_path, "w", encoding="utf-8", errors="replace")  # noqa: SIM115 - closed in finally
    proc = subprocess.Popen([exe], env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        t0 = time.time()
        while time.time() - t0 < 120:
            if proc.poll() is not None:
                log.flush()
                print(open(log_path, encoding="utf-8", errors="replace").read()[-4000:])
                print("FAIL: backend exited")
                return 1
            try:
                if get(f"{base}/api/health")[0] == 200:
                    break
            except OSError:
                time.sleep(0.5)
        else:
            print("FAIL: backend did not become healthy")
            return 1
        print(f"healthy after {time.time() - t0:.1f} s")
        assert get(f"{base}/api/sessions")[0] == 401, "request without token was accepted"
        code, body = get(f"{base}/api/status", token)
        assert code == 200, body
        print(f"status: {body[:200]!r}")
        # First hardware probe can be slow on a fresh Windows runner (WMI warm-up).
        code, body = get(f"{base}/api/system/hardware", token, timeout=60)
        assert code == 200, body
        print("PASS")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
