"""Token usage is persisted honestly and /metrics serves valid Prometheus text without personal data."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from test_local_llm import mock_model  # noqa: F401  (pytest fixture)

from app import config, observability
from app.copilot import engine
from app.enterprise import data

from conftest import user


@pytest.fixture()
def enterprise(platform):
    data.seed()
    return platform


def live(q: str, who: str = "val.viewer") -> dict:
    return engine.ask(q, user(who), mode="live")


def test_token_usage_is_recorded_per_call(enterprise, mock_model):  # noqa: F811
    first = live("How did our sales do in the last 4 weeks?")
    assert first["mode"] == "live", first.get("notice")
    live("How did our sales do in the last 4 weeks?")  # identical prompt: served from cache
    u = observability.token_usage()
    assert u["totals"]["calls"] == 2 and u["totals"]["cached"] == 1
    assert u["totals"]["prompt_tokens"] == 120 and u["totals"]["completion_tokens"] == 20  # cache adds none
    assert u["by_purpose"][0]["purpose"] == "copilot.answer"
    assert mock_model.requests[0]["stream_options"] == {"include_usage": True}
    assert observability.token_usage(username="maya.marketing")["totals"]["calls"] == 0
    assert observability.token_usage(username="val.viewer")["totals"]["calls"] == 2


def test_unreported_tokens_are_never_estimated(enterprise, mock_model):  # noqa: F811
    mock_model.send_usage = False
    live("Which listings have allergen issues?")
    u = observability.token_usage()["totals"]
    assert u["calls"] == 1 and u["unreported"] == 1 and u["prompt_tokens"] == 0 and u["prompt_chars"] > 0


def test_failures_are_recorded(enterprise, mock_model):  # noqa: F811
    mock_model.status = 500
    answer = live("How did our sales do in the last 4 weeks?")
    assert answer["mode"] == "demo"
    u = observability.token_usage()
    assert u["totals"]["failed"] == 1 and u["totals"]["ok"] == 0


def test_stream_usage_option_can_be_disabled(enterprise, mock_model):  # noqa: F811
    config.configure(llm_stream_usage=False)
    try:
        live("How did our sales do in the last 4 weeks?")
        assert "stream_options" not in mock_model.requests[0]
    finally:
        config.configure(llm_stream_usage=True)


def test_metrics_endpoint_is_valid_prometheus_text_without_personal_data(enterprise, mock_model):  # noqa: F811
    from app.main import app

    live("How did our sales do in the last 4 weeks?")
    with TestClient(app) as client:
        client.get("/api/health")
        resp = client.get("/metrics")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/plain")
    text = resp.text
    assert "foodcare_up 1" in text
    assert re.search(r'foodcare_llm_tokens_total\{model="[^"]+",purpose="copilot.answer",type="prompt"\} 120', text)
    health_inf = r'foodcare_http_request_duration_seconds_bucket\{method="GET",route="/api/health",le="\+Inf"\} \d+'
    assert re.search(health_inf, text)
    assert "val.viewer" not in text and "How did our sales" not in text
    sample = re.compile(r'^[a-z_:][a-z0-9_:]*(\{([a-z_]+="[^"]*",?)*\})? -?[0-9.e+]+$')
    for line in text.splitlines():
        assert line.startswith("# HELP ") or line.startswith("# TYPE ") or sample.match(line), line


def test_metrics_can_be_disabled(enterprise):
    from app.main import app

    config.configure(metrics_enabled=False)
    try:
        with TestClient(app) as client:
            assert client.get("/metrics").status_code == 404
    finally:
        config.configure(metrics_enabled=True)
