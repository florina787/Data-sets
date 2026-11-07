"""Enhancement branch: leakage investigator, what-if simulator, legacy billing integration."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.api import app
from app.enhancements.leakage import run_checks, set_status
from app.enhancements.simulator import Scenario, observed_mrr_check, simulate
from app.errors import AppError
from app.sources.legacy_billing import LegacyBillingAdapter, preview



def _fingerprint():
    return db.connection().execute("SELECT (SELECT COUNT(*) FROM invoices), (SELECT SUM(amount_usd) FROM invoices), "
                                   "(SELECT SUM(current_mrr_usd) FROM accounts)").fetchone()


# ------------------------------------------------------------------ leakage
def test_leakage_findings_match_independent_counts():
    f = {x["id"]: x for x in run_checks()}
    assert f["pricing_discrepancy"]["kind"] == "control_passed" and f["pricing_discrepancy"]["count"] == 0
    assert f["status_conflict"]["count"] == 16 and f["status_conflict"]["exposure_usd"] == pytest.approx(200301.54)
    q = lambda s: db.connection().execute(s).fetchone()[0]  # noqa: E731
    assert f["refund_without_payment"]["count"] == q(
        "SELECT COUNT(*) FROM invoices r WHERE status='refunded' AND account_id NOT IN (SELECT account_id FROM invoices WHERE status='paid')")
    assert f["future_dated_paid"]["count"] == q("SELECT COUNT(*) FROM invoices WHERE status='paid' AND invoice_date > current_date")
    assert f["discount_policy"]["kind"] == "needs_policy"  # no policy in the brief → never called leakage


def test_leakage_never_claims_losses_and_has_evidence():
    for x in run_checks():
        assert x["kind"] in {"control_passed", "rule_violation", "needs_investigation", "decision_required", "needs_policy"}
        assert "lost" not in x["summary"].lower() or "not a confirmed loss" in x["summary"]
        if x["count"]:
            assert x["sql"] and x["sample_invoice_ids"]


def test_discount_policy_when_configured(monkeypatch):
    monkeypatch.setenv("DISCOUNT_POLICY_MAX_PCT", "20")
    f = {x["id"]: x for x in run_checks()}["discount_policy"]
    paid25 = db.connection().execute("SELECT COUNT(*) FROM invoices WHERE status='paid' AND discount_pct > 20").fetchone()[0]
    assert f["kind"] == "rule_violation" and f["count"] == paid25 > 0


def test_investigation_status_is_validated_and_does_not_touch_ledger():
    before = _fingerprint()
    set_status("aged_receivables", "investigating", "test")
    assert {x["id"]: x for x in run_checks()}["aged_receivables"]["investigation"]["status"] == "investigating"
    set_status("aged_receivables", "open", "")
    with pytest.raises(AppError):
        set_status("aged_receivables", "deleted")
    with pytest.raises(AppError):
        set_status("drop table", "open")
    assert _fingerprint() == before


# ------------------------------------------------------------------ simulator
def test_noop_scenario_reconciles_to_observed_mrr():
    r = simulate(Scenario())
    assert r["observed"]["mrr"] == pytest.approx(observed_mrr_check()) == pytest.approx(17045461.40)
    assert all(v == 0 for v in r["delta"].values())
    assert "HYPOTHETICAL" in r["label"]


def test_price_change_is_exact_and_isolated_to_plan():
    r = simulate(Scenario(list_price_usd={"Pro": 109}))
    pro = next(p for p in r["by_plan"] if p["plan"] == "Pro")
    assert pro["delta_mrr"] == pytest.approx(pro["observed"]["mrr"] * (109 / 99 - 1), rel=1e-9)
    others = [p for p in r["by_plan"] if p["plan"] != "Pro"]
    assert all(p["delta_mrr"] == pytest.approx(0) for p in others)


def test_churn_assumption_scales_mrr_and_annual_billings_use_10_months():
    r = simulate(Scenario(assumed_churn_pct=10))
    assert r["hypothetical"]["mrr"] == pytest.approx(r["observed"]["mrr"] * 0.9)
    assert r["observed"]["arr"] == pytest.approx(r["observed"]["mrr"] * 12)
    assert r["observed"]["billings_12m"] < r["observed"]["arr"]  # annual accounts bill 10 months


@pytest.mark.parametrize("bad", [{"list_price_usd": {"Gold": 1}}, {"discount_pct": {"all": 100}}, {"seat_change_pct": {"all": -101}},
                                 {"assumed_churn_pct": 101}, {"plan_filter": ["Platinum"]}])
def test_scenario_validation(bad):
    c = TestClient(app)
    r = c.post("/api/v1/simulator/scenarios", json=bad)
    assert r.status_code == 422 and r.json()["code"] == "invalid_scenario"


def test_simulator_never_modifies_ledger():
    before = _fingerprint()
    simulate(Scenario(list_price_usd={"Enterprise": 0}, seat_change_pct={"all": 500}, assumed_churn_pct=100))
    assert _fingerprint() == before


# ------------------------------------------------------------------ legacy billing integration
def test_legacy_preview_maps_validates_and_traces_lineage():
    p = preview(LegacyBillingAdapter.sample())
    assert p["control_total"]["matches"] and p["provenance"]["rows_in_file"] == 12
    reasons = {r["source_line"]: r["reason"] for r in p["rejected_at_mapping"]}
    assert set(reasons) == {8, 9, 10} and "not a known code" in reasons[8] and "cents" in reasons[9] and "YYYYMMDD" in reasons[10]
    assert [r["reason"] for r in p["rejected_by_pipeline"]] == ["lost_conflict"]  # LB-9010 PD vs PN → same precedence rule
    rows = {r["invoice_id"]: r for r in p["cleaned"]}
    assert rows["LB-9006"]["dq_flags"].count("pricing_violation") == 1        # planted 10x overbilling
    assert all("pricing_violation" not in r["dq_flags"] for k, r in rows.items() if k != "LB-9006")
    assert rows["LB-9003"]["amount_local"] == 24057.00 and rows["LB-9003"]["currency"] == "EUR"   # cents → units
    assert rows["LB-9005"]["status"] == "refunded" and rows["LB-9005"]["amount_usd"] == -490.0
    assert rows["LB-9001"]["lineage"] == {"source_system": "legacy_billing_v1", "source_file": "legacy_billing_export.psv",
                                          "source_line": 2, "source_sha256": p["provenance"]["sha256"][:16]}


def test_legacy_preview_errors_and_read_only():
    before = _fingerprint()
    with pytest.raises(AppError) as e:
        LegacyBillingAdapter("INV_NO|X\nA|B").extract()
    assert e.value.code == "schema_mismatch"
    hdr = open("data/samples/legacy_billing_export.psv").read().splitlines()[0]
    with pytest.raises(AppError) as e:
        LegacyBillingAdapter(hdr + "\nTRL|5").extract()
    assert e.value.code == "control_total_mismatch"
    with pytest.raises(AppError) as e:
        LegacyBillingAdapter("x" * (300 * 1024))
    assert e.value.code == "payload_too_large"
    assert _fingerprint() == before


def test_enhancement_endpoints():
    c = TestClient(app)
    assert c.get("/api/v1/leakage/findings").json()["summary"]["findings_by_kind"]["control_passed"] >= 1
    assert c.post("/api/v1/integrations/legacy-billing/preview", json={}).json()["mode"].startswith("preview (read-only)")
    assert c.patch("/api/v1/leakage/findings/aged_receivables", json={"status": "bogus"}).status_code == 422
