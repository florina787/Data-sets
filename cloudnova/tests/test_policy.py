"""Approval-gated financial policy (Decisions page / journey scene 6). Runs in isolated data + runtime dirs."""
import shutil

import pytest

from app import db
from app.config import get_settings
from app.errors import AppError


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    from app.pipeline.build import build
    monkeypatch.setenv("CLOUDNOVA_DATA_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("CLOUDNOVA_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("FINANCE_APPROVER_PIN", "4321")
    get_settings.cache_clear(); db.reset_connections()
    build(force=True, quiet=True)
    yield tmp_path
    db.reset_connections(); get_settings.cache_clear()


def _q1():
    return float(db.connection().execute("SELECT SUM(amount_usd) FROM invoices WHERE status='paid' AND invoice_year=2024").fetchone()[0])


def _approve(key, option, **kw):
    from app.policy import approve, impact
    args = dict(approver="Dana Finance", role="finance_owner", rationale="Price book reconciles 1,421/1,421 under inverse.",
                impact_hash=impact(key)["impact_hash"], pin="4321")
    args.update(kw)
    return approve(key, option, **args)


def test_original_policy_is_active_and_unmodified(isolated):
    from app.policy import active, original
    assert active()["version"] == "1.0" and active()["rules"] == original()["rules"]
    assert original()["rules"]["fx_direction"] == "documented"


def test_fx_impact_evidence(isolated):
    from app.policy import impact
    im = impact("fx_direction")
    assert im["non_usd_invoices_checked"] == 1421
    assert im["price_book_matches"] == {"documented": 0, "inverse": 1421}
    assert im["answers"]["documented"]["q1_paid_2024"] == pytest.approx(32686371.16)
    assert im["answers"]["inverse"]["q1_paid_2024"] == pytest.approx(29595624.38)


@pytest.mark.parametrize("override, code", [({"pin": "0000"}, "approval_denied"), ({"role": "analyst"}, "approval_denied"),
                                            ({"impact_hash": "deadbeef"}, "stale_impact"), ({"rationale": "too short"}, "invalid_decision"),
                                            ({"approver": ""}, "invalid_decision")])
def test_approval_failures(isolated, override, code):
    with pytest.raises(AppError) as e:
        _approve("fx_direction", "inverse", **override)
    assert e.value.code == code


def test_approvals_disabled_without_pin(isolated, monkeypatch):
    monkeypatch.delenv("FINANCE_APPROVER_PIN")
    with pytest.raises(AppError) as e:
        _approve("fx_direction", "inverse")
    assert e.value.code == "approvals_disabled"


def test_approval_alone_changes_nothing_then_apply_rebuilds_and_revert_restores(isolated):
    from app.policy import active, apply
    before = _q1()
    d = _approve("fx_direction", "inverse")
    assert d["status"] == "approved_pending_rebuild" and _q1() == before and active()["version"] == "1.0"
    r = apply(d["decision_id"])
    assert r["fx_direction_in_build"] == "inverse" and _q1() == pytest.approx(29595624.38)
    assert active()["rules"]["fx_direction"] == "inverse" and active()["decision_id"] == d["decision_id"]
    with pytest.raises(AppError):
        apply(d["decision_id"])  # cannot apply twice
    back = _approve("fx_direction", "documented", rationale="Reverting to the brief's literal rule for the audit trail.")
    r2 = apply(back["decision_id"])
    assert r2["restored_original"] and _q1() == pytest.approx(32686371.16) and active()["version"] == "1.0"


def test_identity_confirm_and_blocked_option(isolated):
    from app.policy import apply
    ok = _approve("account_identity", "account_id")
    assert ok["status"] == "confirmed_no_change"
    blocked = _approve("account_identity", "account_name")
    assert blocked["status"] == "recorded_blocked" and "master-data" in blocked["blocked_reason"]
    with pytest.raises(AppError):
        apply(blocked["decision_id"])
