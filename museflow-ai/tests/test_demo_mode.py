"""Demo-mode guarantees: fixtures, metrics, themes, assets and the Streamlit app itself."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from services import metrics, scenario_loader as fixtures
from services.achievements import evaluate, session_stats
from ui.themes import THEMES, contrast_ratio

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["dashboard", "chat", "memory", "agents", "planner", "research", "email", "calendar", "documents", "browser",
         "galaxy", "approvals", "analytics", "governance", "achievements", "settings"]


# ---- fixtures --------------------------------------------------------------------------

def test_fixture_integrity():
    scenarios = fixtures.list_scenarios()
    assert len({s.id for s in scenarios}) == len(scenarios) >= 10
    assert sum(s.showcase for s in scenarios) >= 10
    assert {a.key for a in fixtures.list_agents()} == {
        "supervisor", "planning", "research", "memory", "email", "calendar", "document", "browser",
        "analytics", "governance", "approval", "audit"}
    for doc in fixtures.list_documents():
        text = fixtures.get_document_text(doc.id)
        assert "SYNTHETIC SAMPLE" in text
        found = {f.split(":")[0] for f in text.splitlines() if ":" in f}
        assert set(doc.key_fields) <= found, doc.id
    emails = fixtures.email_fixture()
    assert all(r["address"].endswith("@example.com") for r in emails["recipients"].values())
    assert all(".example/" in t["url"] for t in fixtures.browser_fixture()["tasks"].values())
    for event in fixtures.calendar_fixture()["events"]:
        assert re.fullmatch(r"\d\d:\d\d", event["start"]) and event["start"] < event["end"]
    research = fixtures.research_fixture()
    for key in research["studio_topics"]:
        topic = research["topics"][key]
        assert topic["evidence"] and topic["limitations"]
        assert all(e["id"].startswith("SYN-") for e in topic["evidence"])  # no fabricated real citations
        if topic.get("matrix"):
            for c in topic["matrix"]["criteria"]:
                assert len(c["scores"]) == len(topic["matrix"]["options"])


def test_fixtures_are_immutable_for_callers():
    first = fixtures.research_fixture()
    first["topics"]["ai_frameworks"]["title"] = "tampered"
    assert fixtures.research_fixture()["topics"]["ai_frameworks"]["title"] != "tampered"
    spec = fixtures.get_scenario("research")
    spec.default_params["topic"] = "tampered"
    assert fixtures.get_scenario("research").default_params["topic"] == "ai_frameworks"


def test_research_reports_carry_disclaimer(engine):
    run = engine.start("research", {"topic": "industry"})
    assert run.outputs["research"]["disclaimer"] == "Demo research — synthetic data, not live web results."


# ---- metrics & achievements -------------------------------------------------------------

def test_metrics_reflect_execution(engine):
    engine.start("research")
    pending = engine.start("email_followup")
    rejected = engine.start("schedule_meeting")
    engine.resume(rejected.run_id, "rejected")
    m = metrics.measured(engine)
    assert m["total_runs"] == 3 and m["completed"] == 1 and m["pending_approvals"] == 1
    assert m["status_counts"] == {"completed": 1, "awaiting_approval": 1, "rejected": 1}
    assert m["completion_rate"] == pytest.approx(0.5)
    assert m["approval_outcomes"] == {"rejected": 1}
    expected_invocations = sum(len(r.agent_events) for r in engine.runs.values())
    assert sum(m["agent_invocations"].values()) == expected_invocations
    assert m["llm_tokens"] == 0 and m["llm_cost_usd"] == 0.0
    est = metrics.illustrative(engine)
    assert est["minutes_saved"] == fixtures.get_scenario("research").minutes_saved_estimate
    assert est["token_equivalents"] > 0
    assert pending.run_id in {r.run_id for r in engine.pending()}


def test_achievements_follow_real_interactions(engine):
    assert not any(evaluate(session_stats(engine, 0)).values())
    run = engine.start("email_followup")
    engine.resume(run.run_id, "approved")
    unlocked = evaluate(session_stats(engine, 8))
    assert unlocked["first_task"] and unlocked["email"] and unlocked["explorer"]
    assert not unlocked["master"]


# ---- themes & assets --------------------------------------------------------------------

@pytest.mark.parametrize("name", list(THEMES))
def test_theme_contrast_meets_wcag_aa(name):
    theme = THEMES[name]
    for background in (theme.bg_start, theme.bg_mid, theme.bg_end, theme.surface_solid):
        assert contrast_ratio(theme.text, background) >= 4.5, (name, background)
        assert contrast_ratio(theme.text_muted, background) >= 4.5, (name, "muted", background)
    assert contrast_ratio(theme.accent_text, theme.accent) >= 4.5
    assert contrast_ratio(theme.accent_text, theme.accent_2) >= 4.5


def test_five_themes():
    assert list(THEMES) == ["Unicorn Dream", "Lavender Galaxy", "Rose Gold Luxury", "Midnight Mermaid", "Pearl Princess"]


def test_assets_exist_and_are_safe_svg():
    for name in ("unicorn.svg", "logo.svg"):
        svg = (ROOT / "assets" / name).read_text()
        assert svg.startswith("<svg") and "<script" not in svg.lower() and "href=\"http" not in svg
    assert "prefers-reduced-motion" in (ROOT / "assets" / "styles.css").read_text()


def test_missing_assets_fall_back_gracefully(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    import ui.components as components

    monkeypatch.setattr(components, "ASSETS", tmp_path)
    components._asset_text.cache_clear()
    components.asset_data_uri.cache_clear()
    try:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        assert not at.exception
        assert any("🦄" in m.value and "Lumi the unicorn" in m.value for m in at.markdown)
    finally:
        components._asset_text.cache_clear()
        components.asset_data_uri.cache_clear()


def test_reduced_motion_removes_animation_classes():
    from ui.animations import sky_markup

    assert "mf-anim" in sky_markup("Gentle", False)
    assert "mf-anim" not in sky_markup("Gentle", True)
    assert "mf-anim" not in sky_markup("Off", False)
    assert "<script" not in sky_markup("Sparkly", False)


# ---- the Streamlit app ------------------------------------------------------------------

@pytest.fixture
def app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()


def test_every_page_renders_without_errors(app):
    assert not app.exception
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, (page, [e.message for e in app.exception])
    assert any("PUBLIC DEMO · SIMULATED AI" in m.value for m in app.sidebar.markdown)
    assert any("not affiliated with Meta" in m.value for m in app.markdown)


def test_chat_end_to_end_with_approval(app):
    app.sidebar.radio[0].set_value("chat").run()
    app.chat_input[0].set_value("Draft a professional follow-up email.").run()
    assert not app.exception
    ctx = app.session_state["_museflow_ctx"]
    run = ctx.engine.latest()
    assert run.status == "awaiting_approval"
    assert any("Email Agent" in m.value for m in app.markdown)
    next(b for b in app.button if b.label == "💖 Approve").click().run()
    assert ctx.engine.runs[run.run_id].status == "completed"
    assert len(ctx.engine.stores.outbox) == 1


def test_chat_unsupported_request_is_honest(app):
    app.sidebar.radio[0].set_value("chat").run()
    app.chat_input[0].set_value("Write me a symphony").run()
    assert any("only understand a defined set" in m.value for m in app.markdown)
    assert app.session_state["_museflow_ctx"].engine.runs == {}


def test_settings_theme_switch(app):
    app.sidebar.radio[0].set_value("settings").run()
    theme_radio = next(r for r in app.radio if "Theme" in r.label)
    theme_radio.set_value("Midnight Mermaid").run()
    assert app.session_state["_museflow_ctx"].settings["theme"] == "Midnight Mermaid"
    assert any("--mf-text:#F4F0FF" in m.value for m in app.markdown)


def test_email_boutique_simulate_send_button(app):
    app.sidebar.radio[0].set_value("email").run()
    next(b for b in app.button if "Generate draft" in b.label).click().run()
    labels = [b.label for b in app.button]
    assert "📨 Simulate Send" in labels and not any(label.strip().lower() == "send" for label in labels)
