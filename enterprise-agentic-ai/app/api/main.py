"""FastAPI application factory.

Run with:  uvicorn app.api.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config.logging_config import configure_logging
from app.config.settings import Settings, get_settings
from app.container import Container, build_container

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Container] = build_container,
) -> FastAPI:
    """Create the API. ``container_factory`` is injectable for tests."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Starting %s in %s mode", settings.app_name, settings.app_mode.value.upper())
        app.state.container = container_factory(settings)
        yield
        logger.info("Shutting down")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="From scattered enterprise knowledge to trusted action.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    from app.api.routes import router

    app.include_router(router)
    return app


app = create_app()
