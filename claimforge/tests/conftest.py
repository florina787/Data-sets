"""Shared fixtures. Tests always run in DEMO_MODE with no API key."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DEMO_MODE"] = "true"
os.environ.pop("ANTHROPIC_API_KEY", None)

from app.config.settings import load_settings  # noqa: E402
from app.requirements.analyzer import DEMO_CLARIFICATIONS, DEMO_REQUIREMENT  # noqa: E402
from app.services.platform import ClaimForgePlatform  # noqa: E402

APPROVAL = {"approver": "Test Release Manager", "role": "Release Manager", "decision": "APPROVED", "comment": "tests"}


@pytest.fixture(scope="session")
def settings():
    return load_settings(demo_mode=True, _anthropic_api_key=None)


@pytest.fixture(scope="session")
def platform(settings):
    return ClaimForgePlatform(settings)


@pytest.fixture(scope="session")
def closed_loop(platform):
    """Full closed-loop run: requirement → … → simulated release → ClaimIQ → defect → feedback."""
    platform.reset_production()
    return platform.run_workflow(DEMO_REQUIREMENT, clarifications=DEMO_CLARIFICATIONS, approval=APPROVAL)


@pytest.fixture()
def fresh_platform(settings):
    return ClaimForgePlatform(settings)
