"""LIVE-mode safety: model output is validated and cannot override policy.
These tests use a scripted fake provider; they make no network calls."""
from app.agents import providers
from app.agents.contracts import ActionPlanLLM, DiagnosisLLM, EvidencePlanLLM, HypothesisOut, TriageOutput
from app.agents.providers import Provider, ProviderUnavailable, Usage
from conftest import investigate


class FakeLive(Provider):
    mode = "LIVE"
    name = "fake-live"
    model = "fake-model"

    def __init__(self, diagnosis=None, action="create_technician_dispatch", fail=None):
        self.diagnosis = diagnosis
        self.action = action
        self.fail = fail
        self.calls = []

    def generate(self, *, system, user, schema, budget_used):
        self.calls.append(schema.__name__)
        if self.fail:
            raise ProviderUnavailable("scripted outage", self.fail)
        u = Usage(provider=self.name, model=self.model, available=True, input_tokens=100, output_tokens=20, calls=1)
        if schema is TriageOutput:
            return TriageOutput(symptom_pattern="intermittent_disconnection", frequency="several times a day",
                                affected_devices="unknown", onset="unknown", lookback_hours=24,
                                customer_reported_actions=["modem_restart", "made_up_action"],
                                special_requests=[], mentions_prior_incident=False,
                                clarifying_questions=[], missing_information=[]), u
        if schema is EvidencePlanLLM:
            return EvidencePlanLLM(knowledge_queries=["dispatch prerequisites"]), u
        if schema is DiagnosisLLM:
            return self.diagnosis, u
        if schema is ActionPlanLLM:
            return ActionPlanLLM(action_type=self.action, purpose="Live purpose text.",
                                 uncertainty="Live uncertainty."), u
        raise AssertionError(schema)


def test_invalid_citations_dropped_and_rules_win(client, login):
    bogus = DiagnosisLLM(hypotheses=[
        HypothesisOut(category="AREA_INCIDENT", statement="Outage in the area", supporting_refs=["INC-INC-7001"],
                      opposing_refs=[]),
        HypothesisOut(category="LINE_IMPAIRMENT", statement="Suspected cause: line",
                      supporting_refs=["DIAG-SNR", "NOT-A-REF"], opposing_refs=[])], summary="x")
    fake = FakeLive(diagnosis=bogus, action="apply_bill_credit")
    providers.set_provider(fake)
    d = investigate(client, login, "C-1003")
    ev = client.get("/api/cases/C-1003/evidence", headers=login("u-spec-ava")).json()
    errs = ev["diagnosis"]["validation_errors"]
    assert any("does not support" in e for e in errs) and any("does not exist" in e for e in errs)
    assert ev["diagnosis"]["conclusion"] == "LINE_IMPAIRMENT"
    # model proposed a non-permitted action: rejected, policy-permitted action kept
    assert d["recommendation"]["action_type"] == "create_technician_dispatch"
    assert d["recommendation"]["generation_mode"] == "LIVE"
    # unknown prior action invented by the model is dropped by the validator
    assert "made_up_action" not in d["reported_symptoms"]["customer_reported_actions"]
    audit = client.get("/api/cases/C-1003/audit", headers=login("u-spec-ava")).json()
    assert any(e["usage"].get("input_tokens") for e in audit)


def test_provider_outage_is_explicit_not_silent(client, login):
    providers.set_provider(FakeLive(fail="PROVIDER_UNAVAILABLE"))
    d = investigate(client, login, "C-1003")
    assert d["status"] == "FAILED"
    audit = client.get("/api/cases/C-1003/audit", headers=login("u-spec-ava")).json()
    failed = next(e for e in audit if e["to_status"] == "FAILED")
    assert failed["detail"]["errors"][0]["code"] == "PROVIDER_UNAVAILABLE"
    assert d["recommendation"] is None


def test_unconfigured_live_provider_reports_not_configured():
    from app.agents.providers import AnthropicProvider

    p = AnthropicProvider("LIVE")
    p._settings = type(p._settings)(**{**p._settings.__dict__, "llm_api_key": ""})
    try:
        p.generate(system="s", user="u", schema=EvidencePlanLLM, budget_used=0)
    except ProviderUnavailable as exc:
        assert exc.code == "NOT_CONFIGURED"
    else:
        raise AssertionError("expected ProviderUnavailable")


def test_budget_exhaustion_escalates(client, login, monkeypatch):
    from app.agents.providers import BudgetExceeded

    class Hungry(FakeLive):
        def generate(self, **kw):
            raise BudgetExceeded("Case token budget of 10 exhausted")

    providers.set_provider(Hungry())
    d = investigate(client, login, "C-1003")
    assert d["status"] == "FAILED"


def test_demo_mode_is_labelled_and_makes_no_calls(client, login):
    sysinfo = client.get("/api/system").json()
    assert sysinfo["generation"]["generation_mode"] == "DEMO" and sysinfo["generation"]["live_calls"] is False
    assert sysinfo["connector_mode"] == "SIMULATED"
    d = investigate(client, login, "C-1003")
    assert d["recommendation"]["generation_mode"] == "DEMO"
    msg = client.post("/api/cases/C-1003/messages", headers=login("u-spec-ava"),
                      json={"text": "Why are we not asking for another modem restart?"}).json()
    assert msg["generation_mode"] == "DEMO" and "not a generated answer" in msg["text"]
    assert msg["citations"]
