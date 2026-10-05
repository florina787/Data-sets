"""Claims Simulation Lab runner (SIMULATED, DETERMINISTIC).

Runs the SAME seeded synthetic claims through two versioned rulesets and compares the
outcomes. No agent or LLM is invoked inside claim loops.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from app.claims.adjudicator import adjudicate_frame
from app.claims.rulesets import RuleSet
from app.models.domain import SimulationResult
from app.simulation.comparison import ChangeSpec, classify_changes, financial_impact, merge_results, rate
from app.simulation.generator import SyntheticDataset, generate_dataset


@lru_cache(maxsize=8)
def cached_dataset(n_claims: int, seed: int) -> SyntheticDataset:
    """Synthetic datasets are immutable for a given (n, seed); cache them."""
    return generate_dataset(n_claims, seed)


@dataclass
class SimulationRun:
    result: SimulationResult
    merged: pd.DataFrame  # per-claim current vs proposed, with change classification


def run_simulation(current: RuleSet, proposed: RuleSet, spec: ChangeSpec, *, n_claims: int = 10_000,
                   seed: int = 42, annual_claim_volume: int = 250_000) -> SimulationRun:
    t0 = time.perf_counter()
    ds = cached_dataset(n_claims, seed)
    res_cur = adjudicate_frame(ds.claims, ds.members, ds.providers, current)
    res_new = adjudicate_frame(ds.claims, ds.members, ds.providers, proposed)
    merged = merge_results(ds.claims, res_cur, res_new)
    merged["change_class"] = classify_changes(merged, spec)

    changed = merged[merged.change_class != "UNCHANGED"]
    unexpected = changed[changed.change_class.str.startswith("UNEXPECTED")]
    expected_counts = changed[changed.change_class.str.startswith("EXPECTED")].change_class.value_counts().to_dict()

    by_benefit = []
    for bt, g in merged.groupby("benefit_type"):
        by_benefit.append({
            "benefit_type": bt, "claims": int(len(g)),
            "denial_rate_current": round(rate(g.status_cur, "DENIED"), 4),
            "denial_rate_proposed": round(rate(g.status_new, "DENIED"), 4),
            "reimbursement_current": round(float(g.reimbursement_amount_cur.sum()), 2),
            "reimbursement_proposed": round(float(g.reimbursement_amount_new.sum()), 2),
            "changed": int((g.change_class != "UNCHANGED").sum()),
        })
    reasons = (pd.concat([merged.reason_code_cur.value_counts().rename("current"),
                          merged.reason_code_new.value_counts().rename("proposed")], axis=1)
               .fillna(0).astype(int).reset_index().rename(columns={"index": "reason_code"}))
    if "reason_code" not in reasons.columns:
        reasons = reasons.rename(columns={reasons.columns[0]: "reason_code"})

    sim_id = "SIM-" + hashlib.sha256(f"{current.ruleset_id}|{proposed.ruleset_id}|{n_claims}|{seed}".encode()).hexdigest()[:10].upper()
    samples = unexpected.head(25)[["claim_id", "member_id", "benefit_type", "prior_completed_visits",
                                   "prior_cancelled_visits", "authorization_present", "reason_code_cur",
                                   "reason_code_new", "change_class"]].to_dict(orient="records")
    result = SimulationResult(
        simulation_id=sim_id,
        current_ruleset=current.ruleset_id,
        proposed_ruleset=proposed.ruleset_id,
        claims_simulated=int(len(merged)),
        seed=seed,
        outcomes_changed=int(len(changed)),
        approved_to_denied=int(((merged.status_cur == "APPROVED") & (merged.status_new == "DENIED")).sum()),
        denied_to_approved=int(((merged.status_cur == "DENIED") & (merged.status_new == "APPROVED")).sum()),
        payment_changed=int(((merged.reimbursement_amount_cur - merged.reimbursement_amount_new).abs() > 0.005).sum()),
        approval_rate_current=round(rate(merged.status_cur, "APPROVED"), 4),
        approval_rate_proposed=round(rate(merged.status_new, "APPROVED"), 4),
        denial_rate_current=round(rate(merged.status_cur, "DENIED"), 4),
        denial_rate_proposed=round(rate(merged.status_new, "DENIED"), 4),
        auth_required_current=int((merged.reason_code_cur == "AUTH_REQUIRED").sum()),
        auth_required_proposed=int((merged.reason_code_new == "AUTH_REQUIRED").sum()),
        expected_changes={k: int(v) for k, v in expected_counts.items()},
        unexpected_changes=int(len(unexpected)),
        unexpected_samples=[{k: (bool(v) if k == "authorization_present" else v) for k, v in s.items()} for s in samples],
        by_benefit=by_benefit,
        reason_distribution=reasons.to_dict(orient="records"),
        financial=financial_impact(float(merged.reimbursement_amount_cur.sum()),
                                   float(merged.reimbursement_amount_new.sum()), int(len(merged)),
                                   annual_claim_volume),
        runtime_ms=round((time.perf_counter() - t0) * 1000, 1),
    )
    return SimulationRun(result=result, merged=merged)
