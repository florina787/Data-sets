"""Runtime configuration for the VEENA.AI local backend.

Everything is read from environment variables so the Electron main process can
launch the backend with a per-launch auth token and a per-user data directory.
"""

from __future__ import annotations

import ipaddress
import os
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _default_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "veena-ai"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    data_dir: Path = field(default_factory=_default_data_dir)
    ollama_url: str = "http://127.0.0.1:11434"
    allowed_origins: tuple[str, ...] = ()
    max_upload_mb: int = 50

    @classmethod
    def from_env(cls) -> Settings:
        s = cls()
        s.host = os.environ.get("VEENA_HOST", s.host)
        s.port = int(os.environ.get("VEENA_PORT", s.port))
        s.token = os.environ.get("VEENA_TOKEN") or s.token
        if os.environ.get("VEENA_DATA_DIR"):
            s.data_dir = Path(os.environ["VEENA_DATA_DIR"])
        s.ollama_url = os.environ.get("OLLAMA_URL", s.ollama_url).rstrip("/")
        origins = os.environ.get("VEENA_ALLOWED_ORIGINS", "")
        s.allowed_origins = tuple(o.strip() for o in origins.split(",") if o.strip())
        s.max_upload_mb = int(os.environ.get("VEENA_MAX_UPLOAD_MB", s.max_upload_mb))
        s.validate()
        return s

    def validate(self) -> None:
        # The backend is a local service for one desktop user. Refuse to bind
        # anywhere a neighbour on the network could reach it.
        if not _is_loopback(self.host):
            raise ValueError(f"VEENA_HOST must be a loopback address, got {self.host!r}")
        if not _is_loopback(_host_of(self.ollama_url)):
            raise ValueError("OLLAMA_URL must point at a loopback address (local inference only)")
        if len(self.token) < 16:
            raise ValueError("VEENA_TOKEN must be at least 16 characters")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "veena.db"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "indexes"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.index_dir, self.uploads_dir):
            d.mkdir(parents=True, exist_ok=True)


def _host_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    hostport = rest.split("/", 1)[0]
    if hostport.startswith("["):
        return hostport[1:].split("]", 1)[0]
    return hostport.rsplit(":", 1)[0] if ":" in hostport else hostport
