"""Managed local AI runtime (Ollama) so customers never touch a terminal.

Order of preference:
1. An Ollama server already answering on the configured loopback URL: use it.
2. An Ollama binary already installed on the system: start it (`ollama serve`).
3. VEENA's own managed copy in its data folder: start it.
4. None: offer to download the pinned official release, with the user's consent.

The download is pinned to one Ollama release and checked against the SHA-256
published with that release (copied into PINNED below), so a corrupted or
substituted file is rejected before anything is extracted or executed.
Ollama is MIT licensed; redistribution and download are permitted.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import threading
import zipfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("veena.runtime")

OLLAMA_VERSION = "0.40.11"
_BASE = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/"


@dataclass(frozen=True)
class Asset:
    filename: str
    sha256: str
    size: int  # bytes, from the release; used for the disk check and progress
    binary: str  # path of the server binary inside the archive


# From https://github.com/ollama/ollama/releases/download/v0.40.11/sha256sum.txt
PINNED: dict[tuple[str, str], Asset] = {
    ("windows", "amd64"): Asset(
        "ollama-windows-amd64.zip", "bda4a493ba8a7c24d57263cd843cd68cee84f44aed4299eeed532acad7eda12a", 1_586_356_606, "ollama.exe"
    ),
    ("windows", "arm64"): Asset(
        "ollama-windows-arm64.zip", "a43eeaea23bef3157b0f7d42216fe8a8fecdd7a9f06722f7f8e623470308bd9a", 0, "ollama.exe"
    ),
    ("darwin", "amd64"): Asset(
        "ollama-darwin.tgz", "aea7d3f2e32371b7644a6e2ec8d4f26820a0e3965918cce8a46cef3e947f6291", 181_324_349, "ollama"
    ),
    ("darwin", "arm64"): Asset(
        "ollama-darwin.tgz", "aea7d3f2e32371b7644a6e2ec8d4f26820a0e3965918cce8a46cef3e947f6291", 181_324_349, "ollama"
    ),
    ("linux", "amd64"): Asset(
        "ollama-linux-amd64.tar.zst", "7bedab90dd122661be78798e9f0edf37fccf0cccf2699d2c58ea1a3afdc04b6d", 1_508_659_610, "bin/ollama"
    ),
    ("linux", "arm64"): Asset(
        "ollama-linux-arm64.tar.zst", "77b278837b9e62c172f77d703675be4c52c8054e9075639031a9a6d5a53f1924", 0, "bin/ollama"
    ),
}

# Extracted archives are larger than the download (GPU libraries are compressed).
EXTRACT_FACTOR = 2.5
HEADROOM_BYTES = 1_000_000_000


class RuntimeError_(Exception):
    """A setup failure with a message fit to show the customer."""


def platform_key() -> tuple[str, str]:
    os_name = {"win32": "windows", "darwin": "darwin"}.get(sys.platform, "linux")
    m = platform.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "amd64"
    return os_name, arch


def _system_binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.append(Path(local) / "Programs" / "Ollama" / "ollama.exe")
    elif sys.platform == "darwin":
        candidates += [
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path("/usr/local/bin/ollama"),
            Path("/opt/homebrew/bin/ollama"),
        ]
    else:
        candidates += [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]
    return next((str(c) for c in candidates if c.is_file()), None)


class OllamaRuntime:
    def __init__(self, data_dir: Path, base_url: str, download_base: str = _BASE, assets: dict | None = None):
        self.root = data_dir / "runtime" / "ollama"
        self.models_dir = data_dir / "models"
        self.base_url = base_url.rstrip("/")
        self.download_base = download_base
        self.assets = PINNED if assets is None else assets
        self.proc: subprocess.Popen | None = None
        self._cancel = threading.Event()
        self.installing = False

    # ---------------- state ----------------
    @property
    def asset(self) -> Asset | None:
        return self.assets.get(platform_key())

    @property
    def managed_binary(self) -> Path | None:
        a = self.asset
        if not a:
            return None
        p = self.root / OLLAMA_VERSION / a.binary
        return p if p.is_file() else None

    async def reachable(self) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as c:
                r = await c.get(self.base_url + "/api/version")
                return r.json().get("version")
        except (httpx.HTTPError, ValueError):
            return None

    def disk_free(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.root).free

    def required_bytes(self) -> int:
        a = self.asset
        size = a.size if a and a.size else 1_600_000_000
        return int(size * (1 + EXTRACT_FACTOR)) + HEADROOM_BYTES

    async def status(self) -> dict[str, Any]:
        version = await self.reachable()
        a = self.asset
        return {
            "running": version is not None,
            "version": version,
            "managed_by_veena": self.proc is not None and self.proc.poll() is None,
            "system_binary": _system_binary(),
            "managed_binary": str(self.managed_binary) if self.managed_binary else None,
            "installing": self.installing,
            "platform": "-".join(platform_key()),
            "supported": a is not None,
            "download": {
                "version": OLLAMA_VERSION,
                "file": a.filename if a else None,
                "bytes": a.size if a else None,
                "required_free_bytes": self.required_bytes(),
                "free_bytes": self.disk_free(),
                "license": "MIT",
                "source": self.download_base,
            },
        }

    # ---------------- start / stop ----------------
    async def ensure_running(self, wait_s: float = 30.0) -> dict[str, Any]:
        """Start a local Ollama if none is answering. Never downloads anything."""
        if await self.reachable():
            return await self.status()
        binary = _system_binary() or (str(self.managed_binary) if self.managed_binary else None)
        if not binary:
            raise RuntimeError_("The local AI runtime is not installed yet.")
        host = self.base_url.split("://", 1)[-1]
        env = {**os.environ, "OLLAMA_HOST": host}
        if not _system_binary():
            # VEENA's own copy keeps its models in VEENA's data folder.
            self.models_dir.mkdir(parents=True, exist_ok=True)
            env["OLLAMA_MODELS"] = str(self.models_dir)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # type: ignore[attr-defined]
        log.info("starting local AI runtime: %s serve", binary)
        self.proc = subprocess.Popen(  # noqa: S603 - fixed binary path, fixed arguments
            [binary, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_s
        while loop.time() < deadline:
            if await self.reachable():
                return await self.status()
            if self.proc.poll() is not None:
                break
            await asyncio.sleep(0.5)
        raise RuntimeError_("The local AI runtime did not start. Restart VEENA, or reinstall the runtime from Setup.")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    # ---------------- install ----------------
    def cancel(self) -> None:
        self._cancel.set()

    async def install(self) -> AsyncIterator[dict[str, Any]]:
        """Download, verify and unpack the pinned runtime, yielding progress events."""
        a = self.asset
        if not a:
            raise RuntimeError_(f"VEENA cannot set up the AI runtime on this platform ({'-'.join(platform_key())}).")
        if self.installing:
            raise RuntimeError_("The runtime is already being installed.")
        free, need = self.disk_free(), self.required_bytes()
        if free < need:
            raise RuntimeError_(
                f"Not enough free disk space: the AI runtime needs about {need / 1e9:.1f} GB and {free / 1e9:.1f} GB is free."
            )
        self.installing = True
        self._cancel.clear()
        target = self.root / OLLAMA_VERSION
        part = self.root / (a.filename + ".part")
        try:
            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def emit(ev: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, ev)

            fut = loop.run_in_executor(None, self._install_sync, a, part, target, emit)
            while True:
                getter = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait({getter, fut}, return_when=asyncio.FIRST_COMPLETED)
                if getter in done:
                    yield getter.result()
                    continue
                getter.cancel()
                while not queue.empty():
                    yield queue.get_nowait()
                fut.result()  # re-raises a failure from the worker
                break
            yield {"status": "installed", "binary": str(self.managed_binary)}
        finally:
            self.installing = False

    def _install_sync(self, a: Asset, part: Path, target: Path, emit: Callable[[dict], None]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._download(a, part, emit)
        emit({"status": "verifying"})
        if _sha256(part) != a.sha256:
            part.unlink(missing_ok=True)
            raise RuntimeError_("The downloaded runtime failed its integrity check and was deleted. Please try again.")
        emit({"status": "extracting"})
        tmp = target.with_name(target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        _extract(part, tmp)
        binary = tmp / a.binary
        if not binary.is_file():
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError_("The runtime archive did not contain the expected program.")
        if sys.platform != "win32":
            binary.chmod(0o755)
        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
        part.unlink(missing_ok=True)

    def _download(self, a: Asset, part: Path, emit: Callable[[dict], None]) -> None:
        done = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with httpx.stream(
                "GET", self.download_base + a.filename, headers=headers, follow_redirects=True, timeout=httpx.Timeout(60.0, connect=15.0)
            ) as r:
                if r.status_code == 416:  # already complete
                    return
                if r.status_code not in (200, 206):
                    raise RuntimeError_(
                        f"The runtime download failed (HTTP {r.status_code}). Check your internet connection and try again."
                    )
                if r.status_code == 200:
                    done = 0  # server ignored the range; start over
                total = done + int(r.headers.get("content-length") or 0) or a.size
                with open(part, "ab" if done else "wb") as f:
                    last = 0
                    for chunk in r.iter_bytes(1 << 20):
                        if self._cancel.is_set():
                            raise RuntimeError_("Download cancelled. It will resume from where it stopped.")
                        f.write(chunk)
                        done += len(chunk)
                        if done - last >= 8 << 20 or done == total:
                            last = done
                            emit({"status": "downloading", "completed": done, "total": total})
        except httpx.HTTPError as e:
            raise RuntimeError_(
                "The runtime download was interrupted. Check your internet connection and press Retry; it resumes where it stopped."
            ) from e


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _safe_member(dest: Path, name: str) -> Path:
    out = (dest / name).resolve()
    if not str(out).startswith(str(dest.resolve()) + os.sep) and out != dest.resolve():
        raise RuntimeError_("The runtime archive contained an unsafe path and was rejected.")
    return out


def _extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.removesuffix(".part")
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                _safe_member(dest, m)
            z.extractall(dest)  # noqa: S202 - every member path was checked above
        return
    if name.endswith(".tar.zst"):
        import zstandard

        with open(archive, "rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as zr, tarfile.open(fileobj=zr, mode="r|") as t:
            t.extractall(dest, filter="data")
        return
    with tarfile.open(archive, "r:*") as t:
        t.extractall(dest, filter="data")
