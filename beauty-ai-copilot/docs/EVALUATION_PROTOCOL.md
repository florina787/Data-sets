# Evaluation protocol (demo)

Implements the fictional PROT-EVAL-008 v2.0 through config `evaluation/configs/EVC-SHADE-2026.2.json`.

## Population

* Snapshot `DS-2026.09-SHADE` (synthetic). Held-out **test** split only; the validation split is never scored here.
* Eligibility is recomputed by the dataset permission service at run time. It requires a granted consent record that
  permits `evaluation`, an unexpired retention date, image quality `pass`, and the approved grouping protocol.
  Exclusions are counted by reason and reported. 1,352 of 1,440 test records are eligible.
* Required cells: 4 synthetic strata × 3 declared lighting categories = 12. Target cell: `TS-4|warm_indoor`.

## Metrics (all with raw counts)

| Metric | Definition |
|---|---|
| Top-1 accuracy (primary) | correct first-ranked shade ÷ **all eligible samples** (abstentions count as incorrect) |
| Top-3 accuracy (secondary, not gated) | reference within the three ranked shades ÷ all eligible samples |
| Coverage | answered ÷ eligible |
| Abstention rate | abstained ÷ eligible |
| Conditional top-1 | correct ÷ answered (reported separately; never used for gates) |
| Δ pp | candidate % − baseline % (percentage points) |
| Relative change | (candidate − baseline) ÷ baseline × 100 (reported separately, labelled “not pp”) |
| Confusion | reference shade **family** × predicted family (+ ABSTAIN), per cell and overall |

No perceptual colour distance is computed from shade IDs. That needs measured reference values, a calibrated image
pipeline and an agreed colorimetric protocol.

## Pairing and uncertainty

* Baseline and candidate are scored on the **same eligible sample IDs**. Integrity gate: both models have a
  prediction record for every eligible sample.
* Wilson 95% intervals for each proportion.
* Paired percentile bootstrap for each cell's top-1 Δ: 2,000 resamples of matched sample IDs, seed 7 (+ cell offset),
  95%.
* **Repeated comparisons:** 12 cells are compared at once and no multiplicity correction is applied. Some intervals
  will exclude zero by chance; the deterministic gates use point estimates and are illustrative.
* **Fixture artifact:** the fixtures use common random numbers per sample. Cells whose profile is unchanged therefore
  have identical predictions, giving Δ = 0 with a zero-width interval. Real models would not behave this way.

## Test-set protection

Each run records `test_set_evaluation_index` (the number of successful test-split evaluations for the change), and
the UI shows it. Tuning against the test split is a process violation that a real pilot should enforce with access
controls. The validation split exists for that purpose.

## Results on the seeded fixtures (from `evaluation/reports/BR-101-summary.json`)

| Candidate | Overall top-1 | Target TS-4 × warm | Worst cell | Outcome |
|---|---|---|---|---|
| rc1 | 75.67% → 78.18% (+2.51 pp) | 47.83% → 64.35% (+16.52 pp, CI +9.57 to +24.35); coverage −3.48 pp | TS-3 × cool −4.31 pp (CI −8.62 to −0.86) | **FAIL** (G-NO-REGRESSION, G-COVERAGE) |
| rc2 | 75.67% → 77.44% (+1.77 pp) | 47.83% → 60.00% (+12.17 pp, CI +6.09 to +18.26) | no cell below 0.00 pp | **PASS** |

## What still needs expert review

Label validity (how true shade suitability is established), group definitions, statistical power and multiplicity for
a real decision, device coverage, and whether these demo thresholds are appropriate. Parity on synthetic strata does
not demonstrate fairness.
