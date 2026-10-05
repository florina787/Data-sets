"""Synthetic data, simulation reproducibility and financial impact."""

import pandas as pd
import pytest

from app.claims.rulesets import RULESET_V1, RULESET_V2
from app.requirements.analyzer import DEMO_CLARIFICATIONS, DEMO_REQUIREMENT, analyze_requirement_text, change_spec_for
from app.simulation.comparison import financial_impact
from app.simulation.generator import generate_dataset
from app.simulation.runner import run_simulation


def test_33_synthetic_data_generation_reproducible():
    a, b = generate_dataset(1_000, 42), generate_dataset(1_000, 42)
    pd.testing.assert_frame_equal(a.claims, b.claims)
    pd.testing.assert_frame_equal(a.members, b.members)
    assert len(a.claims) == 1_000
    c = generate_dataset(1_000, 7)
    assert not a.claims[["billed_amount"]].equals(c.claims[["billed_amount"]])
    assert a.claims.claim_id.str.startswith("CLM-SYN-").all() and a.members.member_id.str.startswith("MBR-SYN-").all()
    assert a.members.display_label.str.startswith("Synthetic Member").all()


def test_11_old_vs_new_rules_reproducible_differences():
    spec = change_spec_for(analyze_requirement_text(DEMO_REQUIREMENT, DEMO_CLARIFICATIONS))
    r1 = run_simulation(RULESET_V1, RULESET_V2, spec, n_claims=1_000, seed=42).result
    r2 = run_simulation(RULESET_V1, RULESET_V2, spec, n_claims=1_000, seed=42).result
    assert r1.outcomes_changed == r2.outcomes_changed > 0
    assert r1.financial == r2.financial
    assert r1.unexpected_changes == 0  # correct V2 only produces expected changes
    assert r1.expected_changes.get("EXPECTED_ANNUAL_MAX_OR_ACCUMULATOR", 0) > 0


def test_12_financial_impact_calculation_correct():
    f = financial_impact(1_000.0, 1_250.5, n_claims=1_000, annual_claim_volume=250_000)
    assert f.difference == pytest.approx(250.5)
    assert f.projected_annual_impact == pytest.approx(250.5 * 250)
    assert f.projected_monthly_impact == pytest.approx(250.5 * 250 / 12, abs=0.01)
    assert "SIMULATED ESTIMATE" in f.disclaimer
    spec = change_spec_for(analyze_requirement_text(DEMO_REQUIREMENT, DEMO_CLARIFICATIONS))
    run = run_simulation(RULESET_V1, RULESET_V2, spec, n_claims=1_000, seed=42)
    assert run.result.financial.difference == pytest.approx(
        run.merged.reimbursement_amount_new.sum() - run.merged.reimbursement_amount_cur.sum(), abs=0.01)
