"""Fixed-seed synthetic fixture generator for Beauty AI Change Copilot.

Everything produced here is SYNTHETIC. Tone strata, lighting categories, devices,
shades, users and brands are fictional evaluation attributes for a prototype; they are
not an endorsed real-world classification method and no person is represented.

Prediction files are produced by deterministic *fixture profiles* (per-cell success
probabilities). No model was trained. The profiles are designed so that:
  * candidate rc1 raises aggregate top-1 accuracy but regresses one required cell
    beyond the demo threshold (computed later from the records, not asserted here);
  * candidate rc2 improves the target cell without breaching the demo gates;
  * rc2 ships a lighting-profile map with an incorrect entry for device cohort DEV-T3,
    which is absent from the evaluation snapshot and only appears in simulated
    post-release traffic.

Run:  python -m app.datagen.synthetic   (from backend/)
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from pathlib import Path

SEED = 20260917
ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "synthetic"

STRATA = ["TS-1", "TS-2", "TS-3", "TS-4"]
LIGHTING = ["daylight_neutral", "warm_indoor", "cool_fluorescent"]
EVAL_DEVICES = ["DEV-T1", "DEV-T2"]
FAMILIES = {"TS-1": "Light", "TS-2": "Medium", "TS-3": "Tan", "TS-4": "Deep"}
SHADES_PER_FAMILY = 10
RECORDS_PER_CELL = 130  # 10 validation + 120 held-out test
CATALOGUE_VERSION = "CAT-2026.1"
DATASET_SNAPSHOT_ID = "DS-2026.09-SHADE"


def _u(*parts: object) -> float:
    """Deterministic uniform draw in [0,1) keyed by the parts (stable across Python versions)."""
    h = hashlib.sha256(":".join(str(p) for p in (SEED, *parts)).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def _rng(*parts: object) -> random.Random:
    h = hashlib.sha256(":".join(str(p) for p in (SEED, *parts)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def catalogue() -> list[dict]:
    names = ["Porcelain", "Ivory", "Shell", "Linen", "Almond", "Honey", "Caramel", "Chestnut", "Cocoa", "Espresso"]
    shades = []
    for fi, stratum in enumerate(STRATA):
        family = FAMILIES[stratum]
        for k in range(SHADES_PER_FAMILY):
            idx = fi * SHADES_PER_FAMILY + k + 1
            shades.append({
                "shade_id": f"SH-{idx:02d}",
                "ordinal": idx,
                "family": family,
                "display_name": f"Lumen Veil {names[k]} {family} {idx:02d}",
                "brand": "Maison Fictive (fictional)",
                "catalogue_version": CATALOGUE_VERSION,
            })
    return shades


# ---------------------------------------------------------------------------
# Dataset records
# ---------------------------------------------------------------------------

def dataset() -> list[dict]:
    records = []
    n = 0
    for stratum in STRATA:
        for lighting in LIGHTING:
            for i in range(RECORDS_PER_CELL):
                n += 1
                sid = f"S-{n:05d}"
                r = _rng("record", sid)
                split = "validation" if i < 10 else "test"
                fam_index = STRATA.index(stratum)
                expected = fam_index * SHADES_PER_FAMILY + r.randint(1, SHADES_PER_FAMILY)
                consent_status = "granted"
                permitted_use = ["evaluation"]
                retention_until = "2027-12-31"
                quality = "pass"
                reasons: list[str] = []
                roll = r.random()
                if roll < 0.02:
                    consent_status = "withdrawn"
                    reasons.append("consent_withdrawn")
                elif roll < 0.035:
                    permitted_use = ["marketing_preview"]
                    reasons.append("evaluation_not_permitted")
                elif roll < 0.045:
                    retention_until = "2026-06-30"
                    reasons.append("retention_expired")
                elif roll < 0.06:
                    quality = "fail"
                    reasons.append("image_quality_below_protocol")
                if r.random() < 0.25 and consent_status == "granted" and "evaluation" in permitted_use:
                    permitted_use = ["evaluation", "model_training"]
                records.append({
                    "sample_id": sid,
                    "split": split,
                    "tone_stratum": stratum,
                    "lighting_category": lighting,
                    "device_category": EVAL_DEVICES[r.randint(0, 1)],
                    "expected_shade_id": f"SH-{expected:02d}",
                    "label_provenance": "LP-DEMO-PANEL-01: fictional three-reviewer synthetic panel (majority label)",
                    "consent_status": consent_status,
                    "consent_record_id": f"CR-{n:05d}",
                    "permitted_use": permitted_use,
                    "retention_until": retention_until,
                    "image_quality": quality,
                    "grouping_protocol": "GP-DEMO-1: synthetic stratum assigned at fixture creation; never inferred from a face",
                    "image_ref": f"synthetic://no-image/{sid}",
                    "declared_eligible": not reasons,
                    "ineligibility_reasons": reasons,
                })
    return records


# ---------------------------------------------------------------------------
# Fixture prediction profiles (NOT trained models)
# p1 = unconditional top-1 probability, p3 = top-3 probability, pa = abstain prob,
# bias = mean catalogue-ordinal offset of wrong answers.
# ---------------------------------------------------------------------------

BASE_P1 = {
    ("TS-1", "daylight_neutral"): 0.84, ("TS-1", "warm_indoor"): 0.78, ("TS-1", "cool_fluorescent"): 0.80,
    ("TS-2", "daylight_neutral"): 0.82, ("TS-2", "warm_indoor"): 0.74, ("TS-2", "cool_fluorescent"): 0.79,
    ("TS-3", "daylight_neutral"): 0.80, ("TS-3", "warm_indoor"): 0.67, ("TS-3", "cool_fluorescent"): 0.78,
    ("TS-4", "daylight_neutral"): 0.76, ("TS-4", "warm_indoor"): 0.55, ("TS-4", "cool_fluorescent"): 0.70,
}


def _profile(model: str, cell: tuple[str, str]) -> dict:
    p1 = BASE_P1[cell]
    pa, bias = 0.03, 0.0
    stratum, lighting = cell
    if model == "shade-matcher-v2.4.0-rc1":
        # Global warm-light compensation: big warm gains, over-darkens TS-3 under cool light.
        if lighting == "warm_indoor":
            p1 += {"TS-1": 0.04, "TS-2": 0.06, "TS-3": 0.07, "TS-4": 0.14}[stratum]
        if cell == ("TS-3", "cool_fluorescent"):
            p1 -= 0.08
            bias = 3.0
        if cell == ("TS-4", "cool_fluorescent"):
            p1 += 0.03
        if cell == ("TS-4", "warm_indoor"):
            pa = 0.08  # abstains more on hard images
    elif model == "shade-matcher-v2.4.0-rc2":
        # Compensation gated on lighting-detection confidence and restricted to warm_indoor.
        if lighting == "warm_indoor":
            p1 += {"TS-1": 0.01, "TS-2": 0.03, "TS-3": 0.04, "TS-4": 0.11}[stratum]
        if cell == ("TS-3", "cool_fluorescent"):
            p1 -= 0.01
    p3 = min(0.985, p1 + 0.13)
    return {"p1": round(p1, 4), "p3": round(p3, 4), "pa": pa, "bias": bias}


MODELS = [
    {
        "model_id": "shade-matcher-v2.3.0",
        "role": "baseline",
        "version": "2.3.0",
        "code_revision": "REV-2.3.0",
        "preprocessing": {"white_balance": "grey-world-v1", "warm_light_compensation": "off", "input_size": 384},
        "lighting_profile_map": "lpm-v1",
        "provenance": "Synthetic fixture profile; no training performed. Represents the currently released version.",
    },
    {
        "model_id": "shade-matcher-v2.4.0-rc1",
        "role": "candidate",
        "version": "2.4.0-rc1",
        "code_revision": "REV-2.4.0-rc1",
        "preprocessing": {"white_balance": "grey-world-v1", "warm_light_compensation": "global-curve-v1", "input_size": 384},
        "lighting_profile_map": "lpm-v1",
        "provenance": "Synthetic fixture profile; no training performed. Seeded to show aggregate gain hiding a subgroup regression.",
    },
    {
        "model_id": "shade-matcher-v2.4.0-rc2",
        "role": "corrected_candidate",
        "version": "2.4.0-rc2",
        "code_revision": "REV-2.4.0-rc2",
        "preprocessing": {"white_balance": "grey-world-v1", "warm_light_compensation": "gated-warm-only-v2", "input_size": 384},
        "lighting_profile_map": "lpm-v2",
        "provenance": "Synthetic fixture profile; no training performed. Carries a seeded runtime defect in lpm-v2 for DEV-T3.",
    },
]

LIGHTING_PROFILE_MAPS = {
    "lpm-v1": {
        "DEV-T1": {l: l for l in LIGHTING},
        "DEV-T2": {l: l for l in LIGHTING},
        "DEV-T3": {l: l for l in LIGHTING},
    },
    # Seeded runtime defect: DEV-T3 warm_indoor mapped to the cool fluorescent profile.
    "lpm-v2": {
        "DEV-T1": {l: l for l in LIGHTING},
        "DEV-T2": {l: l for l in LIGHTING},
        "DEV-T3": {"daylight_neutral": "daylight_neutral", "warm_indoor": "cool_fluorescent", "cool_fluorescent": "cool_fluorescent"},
    },
}


def predict(model_id: str, rec: dict) -> dict:
    """Deterministic fixture prediction. Common random numbers per sample make comparisons paired."""
    cell = (rec["tone_stratum"], rec["lighting_category"])
    prof = _profile(model_id, cell)
    sid = rec["sample_id"]
    expected = int(rec["expected_shade_id"][3:])
    if _u(sid, "abstain") < prof["pa"]:
        return {"abstained": True, "top3": []}
    answered = 1 - prof["pa"]
    uc = _u(sid, "correct")
    p1c, p3c = prof["p1"] / answered, prof["p3"] / answered
    r = _rng(sid, "offset", model_id if prof["bias"] else "shared")
    sign = 1 if r.random() < 0.5 else -1
    mag = 1 if r.random() < 0.7 else 2
    off = int(round(prof["bias"])) + sign * mag if prof["bias"] else sign * mag
    if off == 0:
        off = 1
    wrong = min(40, max(1, expected + off))
    if wrong == expected:
        wrong = expected + (1 if expected < 40 else -1)

    def neigh(x: int, exclude: set[int]) -> int:
        for d in (1, -1, 2, -2, 3, -3):
            y = x + d
            if 1 <= y <= 40 and y not in exclude:
                return y
        raise RuntimeError("no neighbour")

    if uc < p1c:
        a = neigh(expected, {expected})
        top = [expected, a, neigh(expected, {expected, a})]
    elif uc < p3c:
        filler = neigh(wrong, {wrong, expected})
        top = [wrong, expected, filler] if _u(sid, "rank") < 0.6 else [wrong, filler, expected]
    else:
        a = neigh(wrong, {wrong, expected})
        top = [wrong, a, neigh(wrong, {wrong, expected, a})]
    return {"abstained": False, "top3": [f"SH-{t:02d}" for t in top]}


REVISIONS = [
    {
        "revision_id": "REV-2.4.0-rc1",
        "author_user_id": "u-cv-eng",
        "summary": "Apply global warm-light compensation curve before shade matching.",
        "requirement_refs": ["AC-1", "AC-2"],
        "test_refs": ["TEST-EVAL-CELLS", "TEST-TARGET-CELL"],
        "diff_file": "REV-2.4.0-rc1.diff",
    },
    {
        "revision_id": "REV-2.4.0-rc2",
        "author_user_id": "u-cv-eng",
        "summary": "Gate warm-light compensation on lighting-detector confidence; restrict to warm_indoor; add per-device lighting profile map lpm-v2.",
        "requirement_refs": ["AC-1", "AC-2", "AC-3"],
        "test_refs": ["TEST-EVAL-CELLS", "TEST-TARGET-CELL", "TEST-NO-REGRESSION"],
        "diff_file": "REV-2.4.0-rc2.diff",
    },
]

RC1_DIFF = """diff --git a/shade_matcher/preprocess.py b/shade_matcher/preprocess.py
--- a/shade_matcher/preprocess.py
+++ b/shade_matcher/preprocess.py
@@ -41,7 +41,9 @@ def normalise(image, meta):
     image = grey_world_white_balance(image)
-    return image
+    # BR-101: compensate warm indoor casts for deeper skin-tone reference patches
+    image = apply_warm_compensation(image, curve=WARM_CURVE_V1)  # applied to every frame
+    return image
diff --git a/config/model.yaml b/config/model.yaml
--- a/config/model.yaml
+++ b/config/model.yaml
@@ -3,3 +3,3 @@
-version: 2.3.0
-warm_light_compensation: off
+version: 2.4.0-rc1
+warm_light_compensation: global-curve-v1
"""

RC2_DIFF = """diff --git a/shade_matcher/preprocess.py b/shade_matcher/preprocess.py
--- a/shade_matcher/preprocess.py
+++ b/shade_matcher/preprocess.py
@@ -41,7 +41,12 @@ def normalise(image, meta):
     image = grey_world_white_balance(image)
-    return image
+    # BR-101: only compensate when the lighting detector is confident the scene is warm indoor
+    profile = LIGHTING_PROFILE_MAP[meta.device_category][meta.lighting_category]
+    if profile == "warm_indoor" and meta.lighting_confidence >= 0.8:
+        image = apply_warm_compensation(image, curve=WARM_CURVE_V2)
+    return image
diff --git a/config/lighting_profile_map.json b/config/lighting_profile_map.json
--- a/config/lighting_profile_map.json  (lpm-v1)
+++ b/config/lighting_profile_map.json  (lpm-v2)
@@ -9,5 +9,5 @@
   "DEV-T3": {
     "daylight_neutral": "daylight_neutral",
-    "warm_indoor": "warm_indoor",
+    "warm_indoor": "cool_fluorescent",
     "cool_fluorescent": "cool_fluorescent"
   }
diff --git a/config/model.yaml b/config/model.yaml
@@ -3,3 +3,3 @@
-version: 2.3.0
-warm_light_compensation: off
+version: 2.4.0-rc2
+warm_light_compensation: gated-warm-only-v2
"""


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=False) + "\n")


def main() -> None:
    recs = dataset()
    _write(OUT / "catalogue.json", {"catalogue_version": CATALOGUE_VERSION, "fictional": True, "shades": catalogue()})
    _write(OUT / "dataset_snapshot.json", {
        "dataset_snapshot_id": DATASET_SNAPSHOT_ID,
        "created": str(date(2026, 9, 17)),
        "seed": SEED,
        "synthetic": True,
        "note": "Synthetic evaluation attributes. Tone strata are fixture labels, not an endorsed classification method.",
        "devices_covered": EVAL_DEVICES,
        "records": recs,
    })
    for m in MODELS:
        preds = {r["sample_id"]: predict(m["model_id"], r) for r in recs}
        _write(OUT / "predictions" / f"{m['model_id']}.json", {"model_id": m["model_id"], "fixture": True, "predictions": preds})
    _write(OUT / "models.json", {"models": MODELS, "lighting_profile_maps": LIGHTING_PROFILE_MAPS,
                                 "fixture_profiles": {m["model_id"]: {f"{s}|{l}": _profile(m["model_id"], (s, l)) for s in STRATA for l in LIGHTING} for m in MODELS}})
    _write(OUT / "revisions" / "revisions.json", {"revisions": REVISIONS})
    (OUT / "revisions" / "REV-2.4.0-rc1.diff").write_text(RC1_DIFF)
    (OUT / "revisions" / "REV-2.4.0-rc2.diff").write_text(RC2_DIFF)
    print(f"wrote {len(recs)} records and {len(MODELS)} prediction files to {OUT}")


if __name__ == "__main__":
    main()
