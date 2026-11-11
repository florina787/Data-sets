"""Integration test against Stripe's official stripe-mock server (validates requests against Stripe's OpenAPI spec).
Runs in CI where the stripe/stripe-mock service container is available; SKIPPED elsewhere — never reported as passed
without the integration actually executing."""
import os

import pytest

from app.config import get_settings

STRIPE_MOCK = os.environ.get("STRIPE_MOCK_URL")
pytestmark = pytest.mark.skipif(not STRIPE_MOCK, reason="STRIPE_MOCK_URL not set (stripe-mock runs in CI)")


@pytest.fixture
def stripe_mock(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_API_BASE", STRIPE_MOCK)
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def test_checkout_and_portal_requests_accepted_by_stripe_spec(client, user, stripe_mock):
    h, _ = user
    r = client.post("/api/billing/checkout", headers=h, json={"plan": "pro"})
    assert r.status_code == 200, r.text
    assert r.json()["url"]
    assert client.post("/api/billing/portal", headers=h).status_code == 200
