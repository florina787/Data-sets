"""Optional, anonymous usage statistics (VEENA Insights). OFF by default.

Nothing is recorded or sent unless the user turns on "Share anonymous usage statistics".
When on, VEENA sends only allow-listed facts, never content:

    install_id   random UUID created at opt-in, deleted at opt-out (identifies an installation, not a person)
    os           windows | macos | linux
    app_version  e.g. 0.1.0
    events       first_launch, ai_first_success, active (once a day), feature (which of 6 features was used,
                 once a day), error (one of a few codes, never a message)
    day          the UTC date only

Never sent: prompts, answers, screenshots, documents, file names, audio, transcripts, resumes, IP-derived
data (the server stores none), error messages, hardware details.

The app works identically when statistics are off, offline, or the server is unreachable:
sending happens in the background, with a short timeout, and failures are silently retried later.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .. import __version__

log = logging.getLogger("veena.telemetry")

FEATURES = ("chat", "documents", "screen", "meeting", "interview", "agents")
ERROR_CODES = ("backend_start", "runtime_download", "model_download", "model_error", "asr_error", "screen_capture", "crash", "other")
ONCE = ("first_launch", "ai_first_success")
MAX_QUEUE = 200
FLUSH_EVERY_S = 600


def endpoint() -> str | None:
    """The VEENA Insights server. None (statistics unavailable) until the owner deploys one."""
    url = os.environ.get("VEENA_INSIGHTS_URL", "").strip().rstrip("/")
    if url.startswith("https://"):
        return url
    # Test-only: CI points an INSTALLED build at an Insights Worker on the same machine.
    if os.environ.get("VEENA_INSIGHTS_ALLOW_LOCAL") == "1" and url.startswith("http://127.0.0.1:"):
        return url
    return None


def os_name() -> str:
    s = platform.system().lower()
    return "windows" if s.startswith("win") else "macos" if s == "darwin" else "linux"


def today() -> str:
    return datetime.now(UTC).date().isoformat()


class Telemetry:
    def __init__(self, store, data_dir: Path, url: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.store = store
        self.url = url if url is not None else endpoint()
        self.path = Path(data_dir) / "telemetry.json"
        self.transport = transport
        self._lock = threading.Lock()
        self._state = self._load()

    # ---------- state (only enums and dates; safe to show the user verbatim) ----------
    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {"queue": [], "sent_once": [], "last_day": {}, "pending_delete": None}

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state))
        tmp.replace(self.path)

    @property
    def available(self) -> bool:
        return self.url is not None

    @property
    def enabled(self) -> bool:
        s = self.store.get_settings()
        return bool(s.get("share_usage_stats")) and bool(s.get("telemetry_id")) and self.available

    def status(self) -> dict:
        s = self.store.get_settings()
        return {
            "available": self.available,
            "enabled": self.enabled,
            "server": self.url.split("/")[2] if self.url else None,
            "queued": list(self._state["queue"]),  # exactly what would be sent next
            "install_id": s.get("telemetry_id") if self.enabled else None,
        }

    # ---------- consent ----------
    def opt_in(self) -> dict:
        if not self.available:
            raise RuntimeError("anonymous statistics are not available in this build")
        s = self.store.get_settings()
        if not s.get("telemetry_id"):
            self.store.update_settings({"telemetry_id": str(uuid.uuid4())})
        self.store.update_settings({"share_usage_stats": True})
        with self._lock:
            self._state.update(queue=[], sent_once=[], last_day={})
            self._save()
        self.track("first_launch")
        self.track("active")
        return self.status()

    def opt_out(self) -> dict:
        """Stops collection immediately, drops anything unsent and asks the server to delete this installation's data."""
        s = self.store.get_settings()
        old = s.get("telemetry_id")
        self.store.update_settings({"share_usage_stats": False, "telemetry_id": None})
        with self._lock:
            self._state.update(queue=[], sent_once=[], last_day={}, pending_delete=old)
            self._save()
        return self.status()

    # ---------- recording ----------
    def track(self, event: str, *, feature: str | None = None, error_code: str | None = None) -> None:
        if not self.enabled:
            return  # declined or unavailable: nothing is recorded at all
        if event == "feature" and feature not in FEATURES:
            return
        if event == "error" and error_code not in ERROR_CODES:
            error_code = "other"
        day = today()
        key = f"{event}:{feature or error_code or ''}"
        with self._lock:
            if event in ONCE:
                if event in self._state["sent_once"]:
                    return
                self._state["sent_once"].append(event)
            elif event in ("active", "feature") and self._state["last_day"].get(key) == day:
                return  # at most once a day
            self._state["last_day"][key] = day
            e = {"event": event, "day": day}
            if event == "feature":
                e["feature"] = feature
            if event == "error":
                e["error_code"] = error_code
            self._state["queue"] = (self._state["queue"] + [e])[-MAX_QUEUE:]
            self._save()

    def ai_success(self, feature: str) -> None:
        self.track("ai_first_success")
        self.track("feature", feature=feature)

    def error(self, code: str) -> None:
        self.track("error", error_code=code)

    # ---------- sending (background, best effort) ----------
    async def flush(self) -> str:
        if not self.available:
            return "unavailable"
        async with httpx.AsyncClient(timeout=5.0, transport=self.transport, headers={"user-agent": "VEENA.AI"}) as client:
            pending = self._state.get("pending_delete")
            if pending:
                try:
                    r = await client.post(self.url + "/v1/delete", json={"install_id": pending})
                    if r.status_code < 500:
                        with self._lock:
                            self._state["pending_delete"] = None
                            self._save()
                except httpx.HTTPError:
                    return "offline"
            if not self.enabled or not self._state["queue"]:
                return "nothing"
            batch = list(self._state["queue"][:50])
            body = {"install_id": self.store.get_settings()["telemetry_id"], "os": os_name(), "app_version": __version__, "events": batch}
            try:
                r = await client.post(self.url + "/v1/events", json=body)
            except httpx.HTTPError:
                return "offline"  # keep the queue; try again later
            if r.status_code < 500:  # sent, or rejected for good (4xx): either way do not resend
                with self._lock:
                    self._state["queue"] = self._state["queue"][len(batch) :]
                    self._save()
            return f"http {r.status_code}"

    async def loop(self) -> None:
        while True:
            try:
                self.track("active")
                await self.flush()
            except Exception:  # noqa: BLE001 - statistics must never affect the app
                log.debug("telemetry flush failed", exc_info=True)
            await asyncio.sleep(FLUSH_EVERY_S)
