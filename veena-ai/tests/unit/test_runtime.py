"""Managed AI runtime: download, verify, extract, start. A local HTTP server
stands in for GitHub Releases and a small script stands in for the Ollama
binary; the real download is exercised in CI on Windows, macOS and Linux."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import socket
import sys
import tarfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from backend.runtime import ollama_runtime as R

FAKE_SERVER = """#!{python}
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
host, port = os.environ["OLLAMA_HOST"].rsplit(":", 1)
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({{"version": "fake-1"}}).encode()
        self.send_response(200); self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
assert sys.argv[1] == "serve"
HTTPServer((host, int(port)), H).serve_forever()
"""


def _tgz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _RangeHandler(SimpleHTTPRequestHandler):
    """Serves files and honours a simple `Range: bytes=N-` header, like GitHub."""

    def do_GET(self):  # noqa: N802
        rng = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if not rng or not path.is_file():
            return super().do_GET()
        start = int(rng.split("=")[1].rstrip("-"))
        data = path.read_bytes()[start:]
        self.send_response(206)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def release(tmp_path):
    root = tmp_path / "release"
    root.mkdir()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_RangeHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


def _runtime(tmp_path, base, archive: bytes, *, sha: str | None = None, port: int | None = None) -> R.OllamaRuntime:
    asset = R.Asset("ollama-test.tgz", sha or hashlib.sha256(archive).hexdigest(), len(archive), "bin/ollama")
    rt = R.OllamaRuntime(
        tmp_path / "data", f"http://127.0.0.1:{port or _free_port()}", download_base=base, assets={R.platform_key(): asset}
    )
    return rt


async def _drain(rt) -> list[dict]:
    return [ev async for ev in rt.install()]


def test_install_verifies_and_extracts(tmp_path, release, monkeypatch):
    root, base = release
    archive = _tgz({"bin/ollama": b"#!/bin/sh\necho hi\n", "lib/x.so": b"lib"})
    (root / "ollama-test.tgz").write_bytes(archive)
    rt = _runtime(tmp_path, base, archive)
    events = asyncio.run(_drain(rt))
    assert events[-1]["status"] == "installed"
    assert {"verifying", "extracting"} <= {e["status"] for e in events}
    assert rt.managed_binary and rt.managed_binary.read_bytes().startswith(b"#!/bin/sh")
    assert not list(rt.root.glob("*.part"))  # the archive is removed after install


def test_checksum_mismatch_is_rejected_and_nothing_installed(tmp_path, release):
    root, base = release
    archive = _tgz({"bin/ollama": b"tampered"})
    (root / "ollama-test.tgz").write_bytes(archive)
    rt = _runtime(tmp_path, base, archive, sha="0" * 64)
    with pytest.raises(R.RuntimeError_, match="integrity check"):
        asyncio.run(_drain(rt))
    assert rt.managed_binary is None and not list(rt.root.glob("*.part"))


def test_unsafe_archive_paths_are_rejected(tmp_path):
    bad = tmp_path / "evil.zip"
    import zipfile

    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../../escape.txt", "x")
    with pytest.raises(R.RuntimeError_, match="unsafe path"):
        R._extract(bad, tmp_path / "out")
    assert not (tmp_path.parent / "escape.txt").exists()


def test_interrupted_download_resumes(tmp_path, release):
    root, base = release
    archive = _tgz({"bin/ollama": b"#!/bin/sh\n" + os.urandom(300_000)})
    (root / "ollama-test.tgz").write_bytes(archive)
    rt = _runtime(tmp_path, base, archive)
    rt.root.mkdir(parents=True)
    (rt.root / "ollama-test.tgz.part").write_bytes(archive[:1000])  # a previous attempt stopped here
    events = asyncio.run(_drain(rt))
    downloads = [e for e in events if e["status"] == "downloading"]
    assert downloads[-1]["completed"] == len(archive) and events[-1]["status"] == "installed"


def test_not_enough_disk_is_refused_before_downloading(tmp_path, release, monkeypatch):
    root, base = release
    rt = _runtime(tmp_path, base, b"x")
    monkeypatch.setattr(rt, "disk_free", lambda: 10)
    with pytest.raises(R.RuntimeError_, match="Not enough free disk space"):
        asyncio.run(_drain(rt))


def test_unsupported_platform(tmp_path):
    rt = R.OllamaRuntime(tmp_path, "http://127.0.0.1:1", assets={})
    with pytest.raises(R.RuntimeError_, match="cannot set up"):
        asyncio.run(_drain(rt))


def test_ensure_running_without_any_runtime_explains(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "_system_binary", lambda: None)
    rt = R.OllamaRuntime(tmp_path, f"http://127.0.0.1:{_free_port()}", assets={})
    with pytest.raises(R.RuntimeError_, match="not installed"):
        asyncio.run(rt.ensure_running())


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in server is a shebang script")
def test_installed_runtime_starts_serves_and_stops(tmp_path, release, monkeypatch):
    monkeypatch.setattr(R, "_system_binary", lambda: None)
    root, base = release
    archive = _tgz({"bin/ollama": FAKE_SERVER.format(python=sys.executable).encode()})
    (root / "ollama-test.tgz").write_bytes(archive)
    rt = _runtime(tmp_path, base, archive)

    async def go():
        await _drain(rt)
        st = await rt.ensure_running(wait_s=15)
        assert st["running"] and st["version"] == "fake-1" and st["managed_by_veena"]
        assert (tmp_path / "data" / "models").is_dir()  # VEENA's copy keeps models in VEENA's folder
        rt.stop()
        assert await rt.reachable() is None

    asyncio.run(go())


def test_pinned_assets_cover_customer_platforms():
    for key in [("windows", "amd64"), ("darwin", "arm64"), ("darwin", "amd64"), ("linux", "amd64")]:
        a = R.PINNED[key]
        assert len(a.sha256) == 64 and a.filename and a.binary
