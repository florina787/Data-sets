"""Project B reuse: the AI Investment module calls Project B's unchanged decision engine."""

from __future__ import annotations

import pytest

from tests.conftest import H

pytest.importorskip("langgraph", reason="Project B dependencies not installed")


def test_lists_and_assesses_project_b_scenarios(client):
    scenarios = client.get("/api/v1/architecture/scenarios", headers=H("viewer")).json()
    assert len(scenarios) == 8
    sid = scenarios[0]["id"]
    result = client.post(f"/api/v1/architecture/scenarios/{sid}/assessment", headers=H("viewer"))
    assert result.status_code == 200
    body = result.json()
    assert "adr" in body and body["adr"]["markdown"]


def test_unknown_scenario_is_404(client):
    assert client.post("/api/v1/architecture/scenarios/nope/assessment", headers=H("viewer")).status_code == 404
