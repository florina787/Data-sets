"""Free trial, credits and Unlimited for the desktop app (client of cloud/billing).

DISABLED unless VEENA_BILLING_URL is set (it is empty until the owner approves payments): then every
feature works exactly as before. When enabled:

* Before an AI operation the app asks the server to *authorise* it (Unlimited, a free use, or credits).
* Only after the operation SUCCEEDS is it *committed* (charged). Failed or cancelled operations are
  *released* and cost nothing.
* Meeting and interview sessions are charged in 30-minute blocks: one block covers every answer in that
  session for 30 minutes.
* Sent to the server: a random installation id, the feature name, an operation id and minutes.
  Never prompts, answers, transcripts, screenshots, documents or resumes.

Offline: if the server can't be reached, the app allows a small grace (OFFLINE_GRACE operations per
feature) that is not charged; commits/releases already queued are replayed when it is back online. This is honest about its limits: VEENA is
open-source software running on the user's computer, so this metering is not tamper-proof.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

FEATURES = ("chat", "documents", "screen", "meeting", "interview")
SESSION_FEATURES = ("meeting", "interview")
BLOCK_S = 30 * 60
OFFLINE_GRACE = 3


def billing_url() -> str | None:
    u = os.environ.get("VEENA_BILLING_URL", "").strip().rstrip("/")
    return u if u.startswith("https://") else None


@dataclass
class Decision:
    allowed: bool
    op_id: str | None = None
    kind: str | None = None  # unlimited | trial | credits | offline | disabled
    message: str | None = None
    reuse: bool = False  # a session block already authorised


def feature_for(mode: str, has_image: bool, has_collections: bool) -> str:
    if has_image:
        return "screen"
    if has_collections:
        return "documents"
    return {"meeting": "meeting", "interview": "interview"}.get(mode, "chat")


class Billing:
    def __init__(self, data_dir: Path, url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.url = url if url is not None else billing_url()
        self.path = Path(data_dir) / "billing.json"
        self.transport = transport
        self._lock = threading.Lock()
        self.state = self._load()
        self._blocks: dict[str, tuple[str, float]] = {}  # session_id -> (op_id, started)

    @property
    def enabled(self) -> bool:
        return self.url is not None

    def _load(self) -> dict:
        try:
            s = json.loads(self.path.read_text())
        except (OSError, ValueError):
            s = {}
        s.setdefault("install_id", str(uuid.uuid4()))  # random; survives sign-out, not a hardware id
        s.setdefault("token", None)
        s.setdefault("pending", [])  # [{"op_id", "action"}] to replay when online
        s.setdefault("offline_used", {})
        s.setdefault("cached", None)
        return s

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state))
        try:
            os.chmod(tmp, 0o600)  # holds the sign-in token
        except OSError:
            pass
        tmp.replace(self.path)

    def _client(self) -> httpx.Client:
        h = {"user-agent": "VEENA.AI"}
        if self.state["token"]:
            h["authorization"] = "Bearer " + self.state["token"]
        return httpx.Client(base_url=self.url, timeout=8.0, transport=self.transport, headers=h)

    # ---------- account ----------
    def start_sign_in(self, email: str) -> dict:
        with self._client() as c:
            r = c.post("/v1/auth/start", json={"email": email, "install_id": self.state["install_id"]})
        if r.status_code != 200:
            raise ValueError(r.json().get("error", "could not send the code"))
        return {"sent": True}

    def verify(self, email: str, code: str) -> dict:
        with self._client() as c:
            r = c.post("/v1/auth/verify", json={"email": email, "code": code, "install_id": self.state["install_id"]})
        if r.status_code != 200:
            raise ValueError(r.json().get("error", "sign-in failed"))
        with self._lock:
            self.state["token"] = r.json()["token"]
            self._save()
        return self.status()

    def sign_out(self) -> dict:
        with self._lock:
            self.state.update(token=None, cached=None)  # install_id and trial usage stay
            self._save()
        return self.status()

    def status(self) -> dict:
        if not self.enabled:
            return {"enabled": False}
        out = {"enabled": True, "signed_in": bool(self.state["token"]), "pending": len(self.state["pending"])}
        if self.state["token"]:
            try:
                with self._client() as c:
                    r = c.get("/v1/me")
                if r.status_code == 200:
                    with self._lock:
                        self.state["cached"] = r.json()
                        self._save()
                elif r.status_code == 401:
                    self.sign_out()
                    out["signed_in"] = False
            except httpx.HTTPError:
                out["offline"] = True
            out["account"] = self.state.get("cached")
        return out

    # ---------- metering ----------
    def authorize(self, feature: str, session_id: str | None = None) -> Decision:
        if not self.enabled:
            return Decision(True, kind="disabled")
        if feature in SESSION_FEATURES and session_id in self._blocks:
            op, started = self._blocks[session_id]
            if time.monotonic() - started < BLOCK_S:
                return Decision(True, op_id=op, kind="session", reuse=True)
        if not self.state["token"]:
            return Decision(False, message="Sign in (Settings → Plan & free uses) to start your free uses.")
        op_id = str(uuid.uuid4())
        try:
            with self._client() as c:
                r = c.post("/v1/usage/authorize", json={"op_id": op_id, "feature": feature, "minutes": 30})
            d = r.json()
        except httpx.HTTPError:
            used = self.state["offline_used"].get(feature, 0)
            if used >= OFFLINE_GRACE:
                return Decision(False, message="VEENA can't reach the billing server. Connect to the internet to continue.")
            with self._lock:
                self.state["offline_used"][feature] = used + 1
                self._save()
            return Decision(True, op_id=None, kind="offline")
        if r.status_code == 401:
            self.sign_out()
            return Decision(False, message="Please sign in again (Settings → Plan & free uses).")
        if not d.get("allowed"):
            msg = d.get("message") or (
                "Not enough credits for a 30-minute block." if d.get("reason") == "not_enough_credits" else "This feature needs a plan."
            )
            return Decision(False, message=msg + " See pricing: https://florina787.github.io/Data-sets/pricing.html")
        if feature in SESSION_FEATURES and session_id:
            self._blocks[session_id] = (op_id, time.monotonic())
        return Decision(True, op_id=op_id, kind=d.get("kind"))

    def finish(self, decision: Decision, success: bool) -> None:
        """Commit after success, release after failure/cancel. Never raises; retried later if offline."""
        if not self.enabled or not decision.op_id:
            return
        if decision.reuse and success:
            return  # the block was committed when first used
        if decision.reuse and not success:
            return
        action = "commit" if success else "release"
        if not success:
            for k, (op, _) in list(self._blocks.items()):
                if op == decision.op_id:
                    del self._blocks[k]
        self._send(decision.op_id, action)

    def _send(self, op_id: str, action: str) -> None:
        try:
            with self._client() as c:
                r = c.post(f"/v1/usage/{action}", json={"op_id": op_id})
            if r.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        with self._lock:
            self.state["pending"].append({"op_id": op_id, "action": action})
            self._save()

    def replay(self) -> int:
        """Send commits/releases queued while offline. Returns how many were delivered."""
        if not self.enabled or not self.state["pending"]:
            return 0
        done = 0
        for p in list(self.state["pending"]):
            try:
                with self._client() as c:
                    r = c.post(f"/v1/usage/{p['action']}", json={"op_id": p["op_id"]})
            except httpx.HTTPError:
                break
            if r.status_code < 500:
                with self._lock:
                    self.state["pending"].remove(p)
                    self._save()
                done += 1
        if done:
            with self._lock:
                self.state["offline_used"] = {}
                self._save()
        return done
