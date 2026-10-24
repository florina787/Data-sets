"""Deterministic, inspectable scenario simulation.

Every output lists its inputs, assumptions and formulas. Monte Carlo runs use
a fixed seed and resample the *synthetic* supplier delivery history, so the
same inputs always yield the same numbers. Cost figures are modeled from
editable fictional assumptions, never customer actuals.
"""

from __future__ import annotations

import random
import statistics
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import SEED
from app.core.util import DEMO_TODAY
from app.services import data

SIM_VERSION = "sim-1.2.0"


class DelayScenarioInputs(BaseModel):
    aircraft_id: str = Field(default="AC-204", pattern=r"^AC-\d{3}$")
    part_number: str = Field(default="P-7731", pattern=r"^P-[0-9A-Z]{3,8}$")
    base: str = "MAIN-HUB"
    delays_hours: list[int] = Field(default_factory=lambda: [24, 48, 72], min_length=1, max_length=6)
    install_hours: float = Field(default=9.0, ge=1, le=72, description="DOC-004 (fictional): 7.5h labor + 1.5h ground run")
    downtime_cost_per_hour_low: float = Field(default=4000, ge=0, le=100000)
    downtime_cost_per_hour_high: float = Field(default=9000, ge=0, le=100000)
    monte_carlo_runs: int = Field(default=2000, ge=0, le=20000)
    start: str = Field(default=f"{DEMO_TODAY}T09:00:00")


def _first_slot_after(slots: list[dict[str, Any]], t: datetime) -> dict[str, Any] | None:
    for s in slots:
        if datetime.fromisoformat(s["start"]) >= t:
            return s
    return None


def _outcome(t0: datetime, delay_h: float, slots: list[dict[str, Any]], install_h: float) -> dict[str, Any]:
    arrival = t0 + timedelta(hours=delay_h)
    slot = _first_slot_after(slots, arrival)
    if slot is None:
        # Beyond the 10-day slot horizon: assume next-day 06:00 start (explicit assumption).
        start = (arrival + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        slot_id = "beyond-horizon"
    else:
        start = datetime.fromisoformat(slot["start"])
        slot_id = slot["id"]
    done = start + timedelta(hours=install_h)
    return {"arrival": arrival.isoformat(), "slot_id": slot_id, "slot_start": start.isoformat(),
            "slot_wait_hours": round((start - arrival).total_seconds() / 3600, 1),
            "completion": done.isoformat(), "downtime_hours": round((done - t0).total_seconds() / 3600, 1)}


def compare_delays(inputs: DelayScenarioInputs) -> dict[str, Any]:
    t0 = datetime.fromisoformat(inputs.start)
    slots = data.hangar_slots(inputs.base)
    part = data.part(inputs.part_number) or {}
    supplier = part.get("supplier_id", "SUP-03")
    promised_days = max(1, int(part.get("lead_time_days", 6)))
    slips = data.supplier_slip_samples(supplier) or [0]
    ratios = [max(0.5, (promised_days + s) / promised_days) for s in slips]

    scenarios = []
    for delay in sorted(set(inputs.delays_hours)):
        o = _outcome(t0, delay, slots, inputs.install_hours)
        low = o["downtime_hours"] * inputs.downtime_cost_per_hour_low
        high = o["downtime_hours"] * inputs.downtime_cost_per_hour_high
        mc = None
        if inputs.monte_carlo_runs:
            rng = random.Random(f"{SEED}:{delay}:{inputs.part_number}:{inputs.base}")
            sims = sorted(_outcome(t0, delay * rng.choice(ratios), slots, inputs.install_hours)["downtime_hours"]
                          for _ in range(inputs.monte_carlo_runs))
            mc = {"runs": inputs.monte_carlo_runs, "p50_hours": sims[len(sims) // 2], "p90_hours": sims[int(len(sims) * 0.9)],
                  "mean_hours": round(statistics.mean(sims), 1),
                  "method": f"Resampled actual/promised delivery ratio from {len(ratios)} synthetic {supplier} deliveries (seeded)."}
        scenarios.append({"delay_hours": delay, **o, "cost_low_usd": round(low), "cost_high_usd": round(high), "monte_carlo": mc})

    base = scenarios[0]
    for s in scenarios:
        s["incremental_downtime_vs_first"] = round(s["downtime_hours"] - base["downtime_hours"], 1)
        s["incremental_cost_low_usd"] = s["cost_low_usd"] - base["cost_low_usd"]
        s["incremental_cost_high_usd"] = s["cost_high_usd"] - base["cost_high_usd"]

    sensitivity = _sensitivity(inputs, t0, slots)
    return {
        "version": SIM_VERSION,
        "inputs": inputs.model_dump(),
        "scenarios": scenarios,
        "sensitivity": sensitivity,
        "formulas": [
            "arrival = start + delay_hours",
            "slot_start = first available hangar slot at base with start >= arrival",
            "downtime_hours = (slot_start + install_hours) - start",
            "cost_range = downtime_hours x [cost_per_hour_low, cost_per_hour_high]",
            "Monte Carlo: delay_hours x resampled(actual_days / promised_days) from synthetic supplier history",
        ],
        "assumptions": [
            f"Downtime cost per hour is a fictional planning assumption (${inputs.downtime_cost_per_hour_low:,.0f}-${inputs.downtime_cost_per_hour_high:,.0f}), not a customer actual.",
            f"Install duration {inputs.install_hours} h taken from fictional DOC-004.",
            "Hangar availability comes from the synthetic 10-day slot plan; beyond it, next-day 06:00 is assumed.",
            "Qualified technicians are assumed rostered for the chosen slot (checked separately by the Planner Agent).",
        ],
        "deterministic": True,
        "seed": SEED,
    }


def _sensitivity(inputs: DelayScenarioInputs, t0: datetime, slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One-at-a-time sensitivity of modeled mid-point cost for the first delay scenario."""
    delay = sorted(set(inputs.delays_hours))[0]
    mid = (inputs.downtime_cost_per_hour_low + inputs.downtime_cost_per_hour_high) / 2

    def cost(delay_h: float, install_h: float, rate: float) -> float:
        return _outcome(t0, delay_h, slots, install_h)["downtime_hours"] * rate

    baseline = cost(delay, inputs.install_hours, mid)
    rows = []
    for name, lo, hi in [
        ("Cost per hour +/-25%", cost(delay, inputs.install_hours, mid * 0.75), cost(delay, inputs.install_hours, mid * 1.25)),
        ("Install hours +/-20%", cost(delay, inputs.install_hours * 0.8, mid), cost(delay, inputs.install_hours * 1.2, mid)),
        ("Part delay +/-12 h", cost(max(0, delay - 12), inputs.install_hours, mid), cost(delay + 12, inputs.install_hours, mid)),
    ]:
        rows.append({"factor": name, "low_usd": round(lo), "high_usd": round(hi), "baseline_usd": round(baseline),
                     "swing_usd": round(abs(hi - lo))})
    return sorted(rows, key=lambda r: -r["swing_usd"])


class RoiInputs(BaseModel):
    manual_hours_per_month: float = Field(default=320, ge=0, description="Planner/engineer hours spent reconciling systems and assembling evidence")
    loaded_labor_cost_per_hour: float = Field(default=95, ge=0)
    automation_fraction_low: float = Field(default=0.15, ge=0, le=1)
    automation_fraction_high: float = Field(default=0.35, ge=0, le=1)
    unscheduled_downtime_hours_per_year: float | None = Field(default=None, ge=0, description="Defaults to synthetic data")
    downtime_reduction_low: float = Field(default=0.01, ge=0, le=1)
    downtime_reduction_high: float = Field(default=0.04, ge=0, le=1)
    downtime_cost_per_hour: float = Field(default=6500, ge=0)
    avoided_rework_per_year: float = Field(default=40000, ge=0)
    pilot_engineering_cost: float = Field(default=2 * 13 * 40 * 120, ge=0, description="2 engineers x 13 weeks x 40 h x $120")
    annual_run_cost: float = Field(default=60000, ge=0, description="Support, hardware share, security review")
    incremental_software_license_cost: float = Field(default=0, ge=0)


def roi(inputs: RoiInputs) -> dict[str, Any]:
    from app.core import db

    if inputs.unscheduled_downtime_hours_per_year is None:
        since = f"{int(DEMO_TODAY[:4]) - 1}{DEMO_TODAY[4:]}"
        r = db.query_one("SELECT SUM(downtime_hours) h FROM maintenance_events WHERE type='unscheduled' AND date > ?", (since,))
        unscheduled = round(r["h"] or 0, 1)
        source = "Synthetic maintenance events, trailing 12 months (unscheduled)."
    else:
        unscheduled = inputs.unscheduled_downtime_hours_per_year
        source = "User-entered."

    def benefit(auto: float, red: float) -> dict[str, float]:
        labor = inputs.manual_hours_per_month * 12 * inputs.loaded_labor_cost_per_hour * auto
        downtime = unscheduled * red * inputs.downtime_cost_per_hour
        return {"labor": round(labor), "downtime": round(downtime), "rework": round(inputs.avoided_rework_per_year),
                "total": round(labor + downtime + inputs.avoided_rework_per_year)}

    low = benefit(inputs.automation_fraction_low, inputs.downtime_reduction_low)
    high = benefit(inputs.automation_fraction_high, inputs.downtime_reduction_high)
    first_year_cost = inputs.pilot_engineering_cost + inputs.annual_run_cost + inputs.incremental_software_license_cost

    def payback(total: float) -> float | None:
        net_monthly = (total - inputs.annual_run_cost) / 12
        return round(inputs.pilot_engineering_cost / net_monthly, 1) if net_monthly > 0 else None

    return {
        "inputs": inputs.model_dump(),
        "unscheduled_downtime_hours_per_year": unscheduled,
        "unscheduled_source": source,
        "annual_benefit": {"low": low, "high": high},
        "first_year_cost": round(first_year_cost),
        "first_year_net": {"low": round(low["total"] - first_year_cost), "high": round(high["total"] - first_year_cost)},
        "payback_months": {"low_case": payback(low["total"]), "high_case": payback(high["total"])},
        "formulas": [
            "labor = manual_hours_per_month x 12 x loaded_labor_cost x automation_fraction",
            "downtime = unscheduled_downtime_hours_per_year x downtime_reduction x downtime_cost_per_hour",
            "benefit = labor + downtime + avoided_rework",
            "first_year_cost = pilot_engineering_cost + annual_run_cost + incremental_software_license_cost",
            "payback_months = pilot_engineering_cost / ((benefit - annual_run_cost) / 12)",
        ],
        "disclaimer": "Illustrative, assumption-driven model. Not a promise of savings. Validate every input with the customer.",
    }
