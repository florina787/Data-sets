"""Benchmark harness: three pipelines scored on the same labelled sites; LLM-only explicitly recorded as not run."""

from __future__ import annotations

from tests.conftest import H


def test_evaluation_compares_pipelines(client):
    rows = {r["pipeline"]: r for r in client.post("/api/v1/shield/evaluation/run", headers=H("admin")).json()}
    assert set(rows) == {"scanner_only", "graph_unverified", "hybrid_verified", "llm_only"}
    hy, sc, gr = rows["hybrid_verified"]["metrics"], rows["scanner_only"]["metrics"], rows["graph_unverified"]["metrics"]
    assert hy["precision"] == 1.0 and hy["recall"] == 1.0 and hy["fp"] == 0
    assert "echo:command_injection" in sc["false_positives"] and "get_invoice:broken_access_control" in sc["missed"]
    assert gr["tp"] >= sc["tp"]
    assert hy["patching"]["patches_generated"] == 5 and hy["patching"]["patches_verified"] == 5
    assert hy["verification_success_rate"] == 1.0 and hy["model_tokens"] == 0 and hy["sample_size_sites"] == 9
    assert rows["llm_only"]["status"] == "not_run" and "no authorised model" in rows["llm_only"]["note"]
