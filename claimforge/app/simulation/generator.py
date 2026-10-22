"""Seeded synthetic insurance-domain generator (SIMULATED DATA).

Generates fictional members, providers, appointment histories, authorizations and
claims. Identifiers are obviously synthetic (``MBR-SYN-000123``) and no names, addresses
or other real-looking personal data are generated. Same (n_claims, seed) ⇒ same data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.models.domain import BenefitType

ALLOWED_CLAIM_COUNTS = (1_000, 10_000, 50_000, 100_000)
YEAR = 2026
YEAR_START = date(YEAR, 1, 1)
YEAR_END = date(YEAR, 12, 31)

_BENEFIT_MIX = [
    (BenefitType.PHYSIOTHERAPY, 0.55, "PT-97110", (85.0, 140.0)),
    (BenefitType.CHIROPRACTIC, 0.20, "CH-98940", (55.0, 100.0)),
    (BenefitType.MASSAGE_THERAPY, 0.20, "MT-97124", (70.0, 120.0)),
    (BenefitType.ACUPUNCTURE, 0.05, "AC-97810", (60.0, 100.0)),
]
_PLANS = (["NSH-BRONZE", "NSH-SILVER", "NSH-GOLD"], [0.30, 0.45, 0.25])


@dataclass
class SyntheticDataset:
    members: pd.DataFrame
    providers: pd.DataFrame
    claims: pd.DataFrame
    authorizations: pd.DataFrame
    seed: int
    n_claims: int

    def summary(self) -> dict:
        return {
            "label": "SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION.",
            "seed": self.seed,
            "claims": int(len(self.claims)),
            "members": int(len(self.members)),
            "providers": int(len(self.providers)),
            "authorizations": int(len(self.authorizations)),
            "claims_by_benefit": self.claims["benefit_type"].value_counts().sort_index().to_dict(),
            "service_date_range": [str(self.claims["service_date"].min()), str(self.claims["service_date"].max())],
        }


def _providers(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    pid = 1
    for bt, _, _, _ in _BENEFIT_MIX:
        for _ in range(20):
            rows.append({"provider_id": f"PRV-SYN-{pid:04d}", "display_label": f"Synthetic Clinic {pid:04d}",
                         "specialty": bt.value, "active": True})
            pid += 1
    df = pd.DataFrame(rows)
    # One suspended provider per specialty (picked deterministically by seed).
    for bt, *_ in _BENEFIT_MIX:
        idx = df.index[df.specialty == bt.value].to_numpy()
        df.loc[int(rng.choice(idx)), "active"] = False
    return df


def _episode_visits(rng: np.random.Generator, bt: BenefitType) -> int:
    if bt is BenefitType.PHYSIOTHERAPY:
        lam = 3 if rng.random() < 0.78 else 10
    else:
        lam = 5
    return int(1 + rng.poisson(lam))


def generate_dataset(n_claims: int = 10_000, seed: int = 42) -> SyntheticDataset:
    """Generate a reproducible synthetic dataset with exactly ``n_claims`` claims."""
    if n_claims < 10 or n_claims > 200_000:
        raise ValueError("n_claims must be between 10 and 200,000")
    rng = np.random.default_rng(seed)
    providers = _providers(rng)
    providers_by_benefit = {}
    for bt, *_ in _BENEFIT_MIX:
        sub = providers.loc[providers.specialty == bt.value]
        weights = np.where(sub.active.to_numpy(), 1.0, 0.25)  # suspended clinics see few members
        providers_by_benefit[bt.value] = (sub.provider_id.to_numpy(), weights / weights.sum())

    n_dup = max(1, int(n_claims * 0.005))
    n_base = n_claims - n_dup
    # Allocate claim budget per benefit
    budgets = {bt: int(round(n_base * share)) for bt, share, _, _ in _BENEFIT_MIX}
    budgets[BenefitType.PHYSIOTHERAPY] += n_base - sum(budgets.values())

    member_pool = max(200, n_base // 3)
    cols: dict[str, list] = {k: [] for k in (
        "member_id", "provider_id", "benefit_type", "procedure_code", "service_date",
        "billed_amount", "prior_completed_visits", "prior_cancelled_visits", "visit_number")}
    auth_rows = []
    member_first_day: dict[str, int] = {}

    for bt, _, proc, (lo, hi) in _BENEFIT_MIX:
        budget = budgets[bt]
        perm = rng.permutation(member_pool)
        ep = 0
        produced = 0
        while produced < budget:
            member_id = f"MBR-SYN-{int(perm[ep % member_pool]) + 1:06d}"
            if ep >= member_pool:  # pool exhausted: extend deterministically
                member_id = f"MBR-SYN-{member_pool + ep + 1:06d}"
            ep += 1
            ids, weights = providers_by_benefit[bt.value]
            provider_id = str(rng.choice(ids, p=weights))
            n_completed = min(_episode_visits(rng, bt), budget - produced)
            p_cancel = float(rng.beta(1.5, 14.0))
            day = YEAR_START + timedelta(days=int(rng.integers(0, 300)))
            completed = cancelled = 0
            completed_dates: list[date] = []
            while completed < n_completed and day <= YEAR_END:
                if rng.random() < p_cancel:
                    cancelled += 1
                else:
                    cols["member_id"].append(member_id)
                    cols["provider_id"].append(provider_id)
                    cols["benefit_type"].append(bt.value)
                    cols["procedure_code"].append(proc)
                    cols["service_date"].append(day)
                    cols["billed_amount"].append(round(float(rng.uniform(lo, hi)), 2))
                    cols["prior_completed_visits"].append(completed)
                    cols["prior_cancelled_visits"].append(cancelled)
                    cols["visit_number"].append(completed + 1)
                    completed_dates.append(day)
                    completed += 1
                day += timedelta(days=int(rng.integers(4, 11)))
            produced += completed
            if completed:
                member_first_day[member_id] = min(member_first_day.get(member_id, 10**9), completed_dates[0].toordinal())
            # Authorization: obtained by ~65% of physio members who exceed 10 completed visits,
            # effective from the date of their 11th completed visit (when the spec requires it).
            if bt is BenefitType.PHYSIOTHERAPY and completed > 10 and rng.random() < 0.65:
                auth_rows.append({"authorization_id": f"AUT-SYN-{len(auth_rows) + 1:06d}", "member_id": member_id,
                                  "benefit_type": bt.value, "effective_from": completed_dates[10], "status": "APPROVED"})

    claims = pd.DataFrame(cols)
    # Authorization presence per claim
    claims["authorization_present"] = False
    if auth_rows:
        auth_df = pd.DataFrame(auth_rows)
        eff = dict(zip(zip(auth_df.member_id, auth_df.benefit_type), auth_df.effective_from))
        claims["authorization_present"] = [
            (m, b) in eff and d >= eff[(m, b)]
            for m, b, d in zip(claims.member_id, claims.benefit_type, claims.service_date)
        ]
    else:
        auth_df = pd.DataFrame(columns=["authorization_id", "member_id", "benefit_type", "effective_from", "status"])

    # A small number of late-submitted claims dated before the policy effective date.
    n_pre = max(1, int(len(claims) * 0.002))
    first_visits = claims.index[claims.visit_number == 1].to_numpy()
    pre_idx = rng.choice(first_visits, size=min(n_pre, len(first_visits)), replace=False)
    claims.loc[pre_idx, "service_date"] = [date(YEAR - 1, 12, int(d)) for d in rng.integers(15, 31, size=len(pre_idx))]

    # Duplicates (resubmissions) — exact copies with new claim ids, appended last.
    dup_src = rng.choice(len(claims), size=n_dup, replace=False)
    dups = claims.iloc[dup_src].copy()
    claims = pd.concat([claims, dups], ignore_index=True)
    claims.insert(0, "claim_id", [f"CLM-SYN-{i + 1:07d}" for i in range(len(claims))])
    claims["service_day"] = [d.toordinal() for d in claims["service_date"]]

    # Members
    member_ids = sorted(set(claims.member_id))
    plan_choice = rng.choice(_PLANS[0], size=len(member_ids), p=_PLANS[1])
    # Members mostly claim benefits their plan covers (a few NOT_COVERED claims remain).
    benefits_by_member = claims.groupby("member_id").benefit_type.agg(set).to_dict()
    for i, mid in enumerate(member_ids):
        used = benefits_by_member.get(mid, set())
        if "ACUPUNCTURE" in used and rng.random() < 0.9:
            plan_choice[i] = "NSH-GOLD"
        elif "MASSAGE_THERAPY" in used and plan_choice[i] == "NSH-BRONZE" and rng.random() < 0.9:
            plan_choice[i] = "NSH-SILVER"
    starts, ends = [], []
    for mid in member_ids:
        r = rng.random()
        if r < 0.01:  # new enrolment after first claim → early claims ineligible
            starts.append(date.fromordinal(member_first_day.get(mid, YEAR_START.toordinal()) + 21))
            ends.append(None)
        elif r < 0.025:  # terminated mid-year
            starts.append(date(2024, 1, 1))
            ends.append(date(YEAR, int(rng.integers(5, 10)), 1))
        else:
            starts.append(date(2024, 1, 1))
            ends.append(None)
    members = pd.DataFrame({
        "member_id": member_ids,
        "display_label": [f"Synthetic Member {m[-6:]}" for m in member_ids],
        "plan_id": plan_choice,
        "coverage_start": starts,
        "coverage_end": ends,
    })
    members["coverage_start_day"] = [d.toordinal() for d in members.coverage_start]
    members["coverage_end_day"] = [d.toordinal() if d else np.nan for d in members.coverage_end]

    return SyntheticDataset(members=members, providers=providers, claims=claims,
                            authorizations=auth_df, seed=seed, n_claims=len(claims))
