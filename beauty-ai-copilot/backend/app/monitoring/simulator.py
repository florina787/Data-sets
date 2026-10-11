"""Simulated post-release observations. Nothing here is customer traffic.

Each window draws simulated sessions per (device cohort, lighting) cell from the released model's
fixture profile. The released configuration's lighting-profile map is actually applied: if a device
maps a declared lighting category to a different preprocessing profile, the simulated success
probability is multiplied by MISMATCH_PENALTY (a documented simulator parameter). Reference labels
are available for LABEL_RATE of sessions. All draws are seeded, so windows are reproducible.
"""
from __future__ import annotations

import hashlib

import numpy as np

from app.evaluation.metrics import wilson
from app.services import fixtures

SESSIONS_PER_WINDOW_AT_100 = 20000
DEVICE_SHARE = {"DEV-T1": 0.50, "DEV-T2": 0.35, "DEV-T3": 0.15}
LIGHTING_SHARE = {"daylight_neutral": 0.40, "warm_indoor": 0.35, "cool_fluorescent": 0.25}
LABEL_RATE = 0.10
MISMATCH_PENALTY = 0.55
STRATA = ["TS-1", "TS-2", "TS-3", "TS-4"]


def _seed(*parts) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def simulate_window(release_id: str, model_id: str, lpm_id: str, index: int, allocation_pct: int) -> dict:
    mf = fixtures.models_file()
    prof = mf["fixture_profiles"][model_id]
    lpm = mf["lighting_profile_maps"][lpm_id]
    rng = np.random.default_rng(_seed("monitor", release_id, index))
    total = int(SESSIONS_PER_WINDOW_AT_100 * allocation_pct / 100)
    cells = {}
    exposures = labelled = 0
    for dev, ds in DEVICE_SHARE.items():
        for light, ls in LIGHTING_SHARE.items():
            n = int(rng.binomial(total, ds * ls))
            k = int(rng.binomial(n, LABEL_RATE))
            p = float(np.mean([prof[f"{s}|{light}"]["p1"] for s in STRATA]))
            effective = lpm[dev][light]
            if effective != light:
                p *= MISMATCH_PENALTY
            correct = int(rng.binomial(k, p))
            cells[f"{dev}|{light}"] = {"sessions": n, "labelled": k, "correct": correct, "effective_profile": effective}
            exposures += n
            labelled += k
    return {"simulated_sessions": total, "exposures": exposures, "labelled": labelled, "cells": cells}


def cumulative(windows: list[dict]) -> dict:
    agg: dict[str, dict] = {}
    for w in windows:
        for c, v in w["cells"].items():
            a = agg.setdefault(c, {"sessions": 0, "labelled": 0, "correct": 0})
            for k in ("sessions", "labelled", "correct"):
                a[k] += v[k]
    for c, a in agg.items():
        a["accuracy_pct"] = round(100 * a["correct"] / a["labelled"], 2) if a["labelled"] else None
        a["wilson95"] = wilson(a["correct"], a["labelled"])
    return agg


def detect(agg: dict, reference_by_lighting: dict, min_labels: int, drop_pp: float) -> list[dict]:
    """Alert when a cohort cell has enough labels, is below reference by > drop_pp, and its
    Wilson upper bound is below the reference. Statistical signal only — not root cause."""
    out = []
    for cell, a in agg.items():
        ref = reference_by_lighting[cell.split("|")[1]]
        if a["labelled"] < min_labels or a["accuracy_pct"] is None:
            continue
        if a["accuracy_pct"] < ref - drop_pp and a["wilson95"][1] < ref:
            out.append({"scope": cell, "observed": {"accuracy_pct": a["accuracy_pct"], "labelled": a["labelled"],
                                                    "wilson95": a["wilson95"], "reference_pct": ref}})
    return out
