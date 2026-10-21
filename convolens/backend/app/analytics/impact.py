"""Impact review: compare a baseline and a follow-up selection with comparable denominators.

Never causal: the result always carries a warning, and is empty when follow-up data is unavailable.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.analytics.metrics import breakdown
from app.config import get_settings
from app.models.orm import Dataset
from app.models.schemas import Filters

WARNING = ("Observed change only. A before/after difference in this data does not show that the intervention caused it: "
           "seasonality, product changes, sampling, channel mix and labelling changes can all produce differences.")


def _rate(db: Session, ds: str, f: Filters) -> dict:
    r = breakdown(db, ds, f, "resolution_status", evidence_per_category=0)
    unresolved = next((i["count"] for i in r["items"] if i["key"] == "unresolved_explicit"), 0)
    known = r["denominator"] - r["unknown"]
    return {"conversations": r["denominator"], "known_outcomes": known, "unknown_outcomes": r["unknown"],
            "explicitly_unresolved": unresolved, "rate": round(unresolved / known, 4) if known else None,
            "coverage": round(known / r["denominator"], 4) if r["denominator"] else None, "scope": f.describe()}


def review(db: Session, *, baseline_dataset: str, followup_dataset: str | None, intervention_date: date,
           filters: Filters | None = None) -> dict:
    min_n = get_settings().min_group_size
    f = filters or Filters()
    b_ds, fu_id = db.get(Dataset, baseline_dataset), followup_dataset or baseline_dataset
    fu_ds = db.get(Dataset, fu_id)
    if b_ds is None or fu_ds is None:
        raise ValueError("Unknown dataset")
    base_f = f.model_copy(update={"date_to": intervention_date - timedelta(days=1)})
    fu_f = f.model_copy(update={"date_from": intervention_date})
    base = _rate(db, baseline_dataset, base_f)
    fu = _rate(db, fu_id, fu_f)
    checks = [
        {"check": "same analysis method", "passed": b_ds.active_analysis == fu_ds.active_analysis,
         "detail": f"{b_ds.active_analysis} vs {fu_ds.active_analysis}"},
        {"check": "same parser / eligibility rules", "passed": (b_ds.manifest or {}).get("parser_version") == (fu_ds.manifest or {}).get("parser_version")},
        {"check": f"baseline known outcomes >= {min_n}", "passed": base["known_outcomes"] >= min_n},
        {"check": f"follow-up known outcomes >= {min_n}", "passed": fu["known_outcomes"] >= min_n},
        {"check": "outcome coverage within 10 points",
         "passed": base["coverage"] is not None and fu["coverage"] is not None and abs(base["coverage"] - fu["coverage"]) <= 0.10},
        {"check": "synthetic status matches", "passed": b_ds.synthetic == fu_ds.synthetic},
    ]
    available = fu["conversations"] > 0
    comparable = available and all(c["passed"] for c in checks)
    change = None
    if comparable and base["rate"] is not None and fu["rate"] is not None:
        change = {"rate_difference_points": round((fu["rate"] - base["rate"]) * 100, 1), "direction": "lower" if fu["rate"] < base["rate"] else "higher" if fu["rate"] > base["rate"] else "unchanged"}
    return {"metric": "Explicitly unresolved share of conversations with a known outcome",
            "intervention_date": intervention_date.isoformat(), "baseline": {"dataset": b_ds.name, **base},
            "followup": {"dataset": fu_ds.name, **fu}, "followup_available": available, "comparable": comparable,
            "checks": checks, "observed_change": change, "warning": WARNING,
            "empty_state": None if available else "Follow-up data unavailable: no conversations on or after the intervention date in the selected follow-up dataset."}
