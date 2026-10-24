"""Entry point: ``python -m backend``. Launched by the Electron main process."""

from __future__ import annotations

import logging
import os
import sys

import uvicorn

from .api.app import create_app
from .config import Settings


def main() -> None:
    logging.basicConfig(level=os.environ.get("VEENA_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    app = create_app(settings)
    # The Electron main process waits for this line before opening the window.
    print(f"VEENA_BACKEND_READY port={settings.port}", flush=True)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning", ws_max_size=4 * 2**20)


if __name__ == "__main__":
    sys.exit(main())
