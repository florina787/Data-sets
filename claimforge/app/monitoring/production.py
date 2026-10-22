"""Simulated production for ClaimIQ (SIMULATED).

Produces a synthetic benefit year of claims processed by the *deployed* ruleset schedule
(release 2.3 / RULESET_V1 before the release date, release 2.4 after). For the demo the
release 2.4 build can carry a CONTROLLED SYNTHETIC DEFECT (``RULESET_V2_DEFECTIVE``:
cancelled visits counted toward the authorization threshold).

A *shadow* adjudication of the same claims with the approved specification
(``RULESET_V2``) provides the release-aware expected baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.claims.adjudicator import adjudicate_frame
from app.claims.rulesets import RULESET_V1, RULESET_V2, RULESET_V2_DEFECTIVE, RuleSet
from app.simulation.generator import SyntheticDataset, generate_dataset

RELEASE_DATE = date(2026, 7, 6)
MONITOR_START = date(2026, 1, 5)
MONITOR_END = date(2026, 10, 4)
_EPOCH = date(2000, 1, 1)


@dataclass
class ProductionContext:
    dataset: SyntheticDataset
    actual: pd.DataFrame
    expected: pd.DataFrame
    release_date: date
    release_version: str
    deployed_ruleset: RuleSet
    approved_ruleset: RuleSet
    baseline_ruleset: RuleSet
    defect_injected: bool
    seed: int
    meta: dict = field(default_factory=dict)

    @property
    def post(self) -> pd.DataFrame:
        return self.actual[self.actual.service_date >= self.release_date]

    @property
    def pre(self) -> pd.DataFrame:
        return self.actual[self.actual.service_date < self.release_date]


def defective_variant(approved: RuleSet) -> RuleSet:
    """CONTROLLED SYNTHETIC DEFECT: same ruleset, but visit counter includes CANCELLED visits."""
    if approved.ruleset_id == RULESET_V2.ruleset_id:
        return RULESET_V2_DEFECTIVE
    if not any(b.auth_after_completed_visits is not None for b in approved.benefits.values()):
        return approved  # no authorization threshold → defect not applicable
    benefits = {bt: (replace(b, count_cancelled_visits=True) if b.auth_after_completed_visits is not None else b)
                for bt, b in approved.benefits.items()}
    return RuleSet(ruleset_id=f"{approved.ruleset_id}_DEFECTIVE", version=approved.version,
                   description="CONTROLLED SYNTHETIC DEFECT: cancelled visits counted.", benefits=benefits,
                   source_requirements=approved.source_requirements, changed_rules=approved.changed_rules,
                   synthetic_defect=True)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _enrich(claims: pd.DataFrame, members: pd.DataFrame, res: pd.DataFrame, release_date: date,
            version: str, rng: np.random.Generator) -> pd.DataFrame:
    df = claims.merge(res, on="claim_id").merge(members[["member_id", "plan_id"]], on="member_id")
    post = df.service_date >= release_date
    df["release_version"] = np.where(post, version, "2.3")
    df["week"] = [_week_start(d) for d in df.service_date]
    # Synthetic operational telemetry (identical distribution pre/post apart from +12ms auth lookup).
    df["latency_ms"] = np.round(rng.lognormal(mean=5.15, sigma=0.25, size=len(df)) + np.where(post, 12.0, 0.0), 1)
    df["rule_exception"] = rng.random(len(df)) < 0.002
    return df


def simulate_production(n_claims: int = 10_000, seed: int = 1042, *, inject_defect: bool = True,
                        release_date: date = RELEASE_DATE, approved: RuleSet = RULESET_V2,
                        release_version: str = "2.4") -> ProductionContext:
    key = (n_claims, seed, inject_defect, release_date, approved.ruleset_id, release_version)
    if key not in _CACHE:
        if len(_CACHE) >= 6:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = _simulate(n_claims, seed, inject_defect, release_date, release_version, approved)
    return _CACHE[key]


_CACHE: dict[tuple, ProductionContext] = {}


def _simulate(n_claims, seed, inject_defect, release_date, release_version, approved) -> ProductionContext:
    ds = generate_dataset(n_claims, seed)
    deployed = defective_variant(approved) if inject_defect else approved
    actual = adjudicate_frame(ds.claims, ds.members, ds.providers, [(_EPOCH, RULESET_V1), (release_date, deployed)])
    shadow = adjudicate_frame(ds.claims, ds.members, ds.providers, [(_EPOCH, RULESET_V1), (release_date, approved)])
    window = (ds.claims.service_date >= MONITOR_START) & (ds.claims.service_date <= MONITOR_END)
    claims = ds.claims[window]
    act = _enrich(claims, ds.members, actual, release_date, release_version, np.random.default_rng(seed + 7))
    exp = _enrich(claims, ds.members, shadow, release_date, release_version, np.random.default_rng(seed + 7))
    return ProductionContext(dataset=ds, actual=act, expected=exp, release_date=release_date,
                             release_version=release_version, deployed_ruleset=deployed, approved_ruleset=approved,
                             baseline_ruleset=RULESET_V1, defect_injected=inject_defect, seed=seed,
                             meta={"label": "SIMULATED PRODUCTION — synthetic claims; "
                                            + ("CONTROLLED SYNTHETIC DEFECT INJECTED" if inject_defect else "no defect injected"),
                                   "monitor_window": [MONITOR_START.isoformat(), MONITOR_END.isoformat()]})
