"""``python -m app`` starts the control-room API (single worker; owns the storefront process)."""

import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, workers=1, log_level="info")
