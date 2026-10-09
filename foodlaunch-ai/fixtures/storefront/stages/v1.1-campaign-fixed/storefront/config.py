"""Runtime settings, read from environment variables set by the deployer."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    commerce_db: str = "commerce.db"
    inventory_url: str = "http://127.0.0.1:8700/sim/inventory"
    demo_clock: str | None = None
    revision: str = "unknown"
    release_id: str = "unreleased"
    telemetry_path: str | None = None
    static_dir: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            commerce_db=os.environ.get("STOREFRONT_COMMERCE_DB", "commerce.db"),
            inventory_url=os.environ.get(
                "STOREFRONT_INVENTORY_URL", "http://127.0.0.1:8700/sim/inventory"
            ),
            demo_clock=os.environ.get("STOREFRONT_DEMO_CLOCK") or None,
            revision=os.environ.get("STOREFRONT_REVISION", "unknown"),
            release_id=os.environ.get("STOREFRONT_RELEASE_ID", "unreleased"),
            telemetry_path=os.environ.get("STOREFRONT_TELEMETRY_PATH") or None,
            static_dir=os.environ.get("STOREFRONT_STATIC_DIR") or None,
        )
