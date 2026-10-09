"""Isolated platform state per test session: temp var dir and non-default ports."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from app import config  # noqa: E402


@pytest.fixture()
def platform(tmp_path, monkeypatch):
    """Fresh database, accounts, inventory simulator and storefront repository."""
    config.configure(var_dir=tmp_path / "var", api_port=18700, storefront_port=18801,
                     anthropic_api_key=None, anthropic_model=None)
    from app import auth, db
    from app.graph import flows
    from app.services import delivery
    from app.tools import inventory_sim, workspace

    monkeypatch.delenv("SDLC_COPILOT_CRASH_ONCE_AT", raising=False)
    flows.reset_graphs()
    db.init_db()
    auth.seed_accounts()
    inventory_sim.seed()
    base = workspace.init_repository()
    delivery.seed_baseline_release(base)
    yield {"base": base}
    from app.tools import deploy

    deploy.stop_current()
    flows.reset_graphs()


def user(username: str):
    from app import auth

    return auth.login(username, auth.DEMO_PASSWORD)[1]
