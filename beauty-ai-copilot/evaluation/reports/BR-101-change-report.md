# Change report — BR-101

> Independent beauty AI prototype — synthetic evaluation data. Fixture predictions, not computer-vision inference. Simulated deployment.

**Title:** BR-101 Foundation shade — deeper tones under warm indoor light  
**Status:** ROLLED_BACK  
**Generated:** 2026-10-11T03:06:10.113544+00:00

## Requirement

- v1 — DRAFT
- v2 — APPROVED (approved by u-po)
  - **AC-1** Target cell TS-4|warm_indoor top-1 accuracy improves by at least 5.0 percentage points vs baseline on matched samples. → `G-TARGET`
  - **AC-2** No required evaluation cell loses more than 2.0 percentage points of top-1 accuracy vs baseline. → `G-NO-REGRESSION`
  - **AC-3** Every required cell has at least 100 eligible paired samples; otherwise the result is INCONCLUSIVE. → `G-SAMPLES`
  - **AC-4** Top-3 accuracy is reported for every cell as a secondary metric (not gated).
  - **AC-5** All privacy and authorization control tests pass. → `G-CONTROLS`
  - **AC-6** Abstentions remain in the denominator and count as incorrect. → `G-ABSTENTION-DENOMINATOR`
  - **AC-7** Unvalidated device cohorts ['DEV-T3'] are watched in post-release monitoring.

## Clarifications

| Key | Answer | By | Cycle |
|---|---|---|---|
| correct_match | Primary metric: top-1 shade accuracy against the reference shade ID. Secondary: top-3 accuracy. Abstentions count as incorrect. | u-po | 1 |
| group_definitions | Use the four synthetic tone strata TS-1..TS-4 from grouping protocol GP-DEMO-1. 'Deeper skin tones' = TS-4. Target cell: TS-4 × warm_indoor. | u-po | 1 |
| lighting_protocol | Use the three declared lighting categories of SPEC-LIGHT-003 §1, captured per §2 with a grey reference card. | u-po | 1 |
| reference_labels | Reference shade IDs from label protocol LP-DEMO-PANEL-01 (synthetic). Label validity still requires expert review. | u-po | 1 |
| acceptable_regression | No required cell may lose more than 2 percentage points of top-1 accuracy against baseline; the target cell must improve by at least 5 percentage points. | u-po | 1 |
| supported_devices | Validated devices: DEV-T1 and DEV-T2. DEV-T3 is not validated and must be watched in monitoring. | u-po | 1 |
| recapture | Request another image when SPEC-IQ-002 §2 triggers fire; count such requests as abstentions. | u-po | 1 |
| release_evidence | Minimum 100 eligible samples per required cell; all privacy and authorization control tests must pass; evaluation must be current and digest-matched. | u-po | 1 |

## Evidence

| Source | Version | Section | Status | Purpose |
|---|---|---|---|---|
| SPEC-SHADE-001 | 1.2 | §2 | VALID | Definition of a correct match |
| PROT-EVAL-008 | 1.0 | §4 | OUTDATED | Definition of a correct match |
| POL-REL-005 | 2.1 | §1 | VALID | Release gates |
| PROT-EVAL-008 | 1.0 | §2 | OUTDATED | Release gates |
| PROT-EVAL-008 | 1.0 | §1 | OUTDATED | Evaluation protocol |
| PROT-EVAL-008 | 2.0 | §1 | VALID | Evaluation protocol |
| SPEC-LIGHT-003 | 1.1 | §2 | VALID | Lighting protocol |
| SPEC-SHADE-001 | 1.2 | §3 | VALID | Lighting protocol |
| SPEC-LIGHT-003 | 1.1 | §3 | VALID | Supported devices |
| DS-CARD-010 | 1.0 | §4 | VALID | Supported devices |
| DS-CARD-010 | 1.0 | §1 | VALID | Dataset composition and limitations |
| DS-CARD-010 | 1.0 | §2 | VALID | Dataset composition and limitations |
| POL-CONSENT-006 | 1.3 | §1 | VALID | Consent for evaluation |
| SPEC-IQ-002 | 2.0 | §3 | VALID | Consent for evaluation |
| SPEC-SHADE-001 | 1.2 | §4 | VALID | Image recapture |
| SPEC-IQ-002 | 2.0 | §2 | VALID | Image recapture |
| NOTE-VENDOR-009 | 0.1 | §1 | NOT_APPROVED | Calibration guidance |
| SPEC-CAT-004 | 3.0 | §1 | VALID | Calibration guidance |
| NOTE-VENDOR-009 | 0.1 | §2 | INJECTION_IGNORED | Third-party calibration notes |

## Evaluation EVR-c6e8a7b7b294 — shade-matcher-v2.4.0-rc1 vs shade-matcher-v2.3.0

Status **SUCCEEDED**, outcome **FAIL**, policy 2.1-demo, config EVC-SHADE-2026.2, dataset DS-2026.09-SHADE.  
Candidate digest `sha256:94cfcdfb4b30a23b3794ddbdb33ffa6d6dfd3d7c32cb5447ecdea12d2b67f64c`

Eligible held-out samples: 1352 of 1440 (exclusions: {'image_quality_below_protocol': 25, 'retention_expired': 17, 'evaluation_not_permitted': 18, 'consent_withdrawn': 28}).

| Scope | n | Baseline top-1 | Candidate top-1 | Δ pp (95% CI) | Rel. change | Baseline top-3 | Candidate top-3 | Coverage b→c |
|---|---|---|---|---|---|---|---|---|
| **Overall** | 1352 | 1023 (75.67%) | 1057 (78.18%) | +2.51 (+1.55 to +3.48) | +3.32% | 87.87% | 90.16% | 98.08% → 97.78% |
| TS-1|daylight_neutral | 114 | 96 (84.21%) | 96 (84.21%) | +0.00 (+0.00 to +0.00) | +0.00% | 96.49% | 96.49% | 96.49% → 96.49% |
| TS-1|warm_indoor | 114 | 94 (82.46%) | 97 (85.09%) | +2.63 (+0.00 to +6.14) | +3.19% | 93.86% | 97.37% | 98.25% → 98.25% |
| TS-1|cool_fluorescent | 116 | 95 (81.9%) | 95 (81.9%) | +0.00 (+0.00 to +0.00) | +0.00% | 93.97% | 93.97% | 95.69% → 95.69% |
| TS-2|daylight_neutral | 111 | 93 (83.78%) | 93 (83.78%) | +0.00 (+0.00 to +0.00) | +0.00% | 95.5% | 95.5% | 100.0% → 100.0% |
| TS-2|warm_indoor | 110 | 90 (81.82%) | 94 (85.45%) | +3.63 (+0.91 to +7.27) | +4.44% | 90.91% | 94.55% | 97.27% → 97.27% |
| TS-2|cool_fluorescent | 113 | 89 (78.76%) | 89 (78.76%) | +0.00 (+0.00 to +0.00) | +0.00% | 91.15% | 91.15% | 99.12% → 99.12% |
| TS-3|daylight_neutral | 112 | 97 (86.61%) | 97 (86.61%) | +0.00 (+0.00 to +0.00) | +0.00% | 95.54% | 95.54% | 100.0% → 100.0% |
| TS-3|warm_indoor | 112 | 66 (58.93%) | 73 (65.18%) | +6.25 (+1.79 to +11.61) | +10.61% | 70.54% | 77.68% | 96.43% → 96.43% |
| TS-3|cool_fluorescent | 116 | 89 (76.72%) | 84 (72.41%) | -4.31 (-8.62 to -0.86) | -5.62% | 90.52% | 81.03% | 100.0% → 100.0% |
| TS-4|daylight_neutral | 111 | 83 (74.77%) | 83 (74.77%) | +0.00 (+0.00 to +0.00) | +0.00% | 92.79% | 92.79% | 99.1% → 99.1% |
| TS-4|warm_indoor (target) | 115 | 55 (47.83%) | 74 (64.35%) | +16.52 (+9.57 to +24.35) | +34.54% | 60.87% | 80.0% | 98.26% → 94.78% |
| TS-4|cool_fluorescent | 108 | 76 (70.37%) | 82 (75.93%) | +5.56 (+1.85 to +10.19) | +7.90% | 82.41% | 86.11% | 96.3% → 96.3% |

| Gate | Rule | Observed | Status | Owner |
|---|---|---|---|---|
| G-CONFIG | Evaluation configuration and versioned policy are present | config present=True; policy 2.1-demo | **PASS** | ml_engineer |
| G-ARTIFACT | Registered digests equal digests recomputed from artifact and dataset files | all digests match | **PASS** | ml_engineer |
| G-AMBIGUITY | No unresolved required ambiguity; requirement version approved | unresolved required=0; requirement approved=True | **PASS** | product_owner |
| G-EVIDENCE | Required evidence cited from current approved documents and every citation resolves | 14 citations resolve to current approved sources | **PASS** | domain_reviewer |
| G-SAMPLES | Every required cell has ≥ 100 eligible paired samples | min n = 108 | **PASS** | qa_engineer |
| G-TARGET | Target cell TS-4|warm_indoor top-1 improves by ≥ 5.0 pp | +16.52 pp (95% paired bootstrap CI +9.57 to +24.35) | **PASS** | product_owner |
| G-NO-REGRESSION | No required cell loses more than 2.0 pp top-1 vs baseline | worst cell TS-3|cool_fluorescent -4.31 pp; VIOLATIONS: TS-3|cool_fluorescent -4.31 pp | **FAIL** | domain_reviewer |
| G-COVERAGE | No required cell's coverage (answered/eligible) drops more than 3.0 pp | TS-4|warm_indoor -3.48 pp | **FAIL** | qa_engineer |
| G-ABSTENTION-DENOMINATOR | Abstentions remain in the denominator; every eligible sample has a prediction record | 1352 eligible samples × 2 models = 2704 prediction records; abstentions in denominator: baseline 26, candidate 30 | **PASS** | qa_engineer |
| G-CONTROLS | All required privacy and authorization control tests pass | 7/7 passed | **PASS** | privacy_reviewer |

Uncertainty: Wilson 95% for proportions; paired percentile bootstrap (2000 resamples, seed 7) for cell deltas. Δ is in percentage points; relative change is reported separately.

## Evaluation EVR-9ada8a256fe1 — shade-matcher-v2.4.0-rc2 vs shade-matcher-v2.3.0

Status **SUCCEEDED**, outcome **PASS**, policy 2.1-demo, config EVC-SHADE-2026.2, dataset DS-2026.09-SHADE.  
Candidate digest `sha256:af2b85697545ed1fb49519297452d373a64d0257880dc46851f12ca73de4d2cb`

Eligible held-out samples: 1352 of 1440 (exclusions: {'image_quality_below_protocol': 25, 'retention_expired': 17, 'evaluation_not_permitted': 18, 'consent_withdrawn': 28}).

| Scope | n | Baseline top-1 | Candidate top-1 | Δ pp (95% CI) | Rel. change | Baseline top-3 | Candidate top-3 | Coverage b→c |
|---|---|---|---|---|---|---|---|---|
| **Overall** | 1352 | 1023 (75.67%) | 1047 (77.44%) | +1.77 (+1.11 to +2.51) | +2.34% | 87.87% | 89.57% | 98.08% → 98.08% |
| TS-1|daylight_neutral | 114 | 96 (84.21%) | 96 (84.21%) | +0.00 (+0.00 to +0.00) | +0.00% | 96.49% | 96.49% | 96.49% → 96.49% |
| TS-1|warm_indoor | 114 | 94 (82.46%) | 95 (83.33%) | +0.87 (+0.00 to +2.63) | +1.06% | 93.86% | 94.74% | 98.25% → 98.25% |
| TS-1|cool_fluorescent | 116 | 95 (81.9%) | 95 (81.9%) | +0.00 (+0.00 to +0.00) | +0.00% | 93.97% | 93.97% | 95.69% → 95.69% |
| TS-2|daylight_neutral | 111 | 93 (83.78%) | 93 (83.78%) | +0.00 (+0.00 to +0.00) | +0.00% | 95.5% | 95.5% | 100.0% → 100.0% |
| TS-2|warm_indoor | 110 | 90 (81.82%) | 93 (84.55%) | +2.73 (+0.00 to +6.36) | +3.34% | 90.91% | 94.55% | 97.27% → 97.27% |
| TS-2|cool_fluorescent | 113 | 89 (78.76%) | 89 (78.76%) | +0.00 (+0.00 to +0.00) | +0.00% | 91.15% | 91.15% | 99.12% → 99.12% |
| TS-3|daylight_neutral | 112 | 97 (86.61%) | 97 (86.61%) | +0.00 (+0.00 to +0.00) | +0.00% | 95.54% | 95.54% | 100.0% → 100.0% |
| TS-3|warm_indoor | 112 | 66 (58.93%) | 72 (64.29%) | +5.36 (+1.79 to +9.82) | +9.10% | 70.54% | 72.32% | 96.43% → 96.43% |
| TS-3|cool_fluorescent | 116 | 89 (76.72%) | 89 (76.72%) | +0.00 (+0.00 to +0.00) | +0.00% | 90.52% | 89.66% | 100.0% → 100.0% |
| TS-4|daylight_neutral | 111 | 83 (74.77%) | 83 (74.77%) | +0.00 (+0.00 to +0.00) | +0.00% | 92.79% | 92.79% | 99.1% → 99.1% |
| TS-4|warm_indoor (target) | 115 | 55 (47.83%) | 69 (60.0%) | +12.17 (+6.09 to +18.26) | +25.44% | 60.87% | 75.65% | 98.26% → 98.26% |
| TS-4|cool_fluorescent | 108 | 76 (70.37%) | 76 (70.37%) | +0.00 (+0.00 to +0.00) | +0.00% | 82.41% | 82.41% | 96.3% → 96.3% |

| Gate | Rule | Observed | Status | Owner |
|---|---|---|---|---|
| G-CONFIG | Evaluation configuration and versioned policy are present | config present=True; policy 2.1-demo | **PASS** | ml_engineer |
| G-ARTIFACT | Registered digests equal digests recomputed from artifact and dataset files | all digests match | **PASS** | ml_engineer |
| G-AMBIGUITY | No unresolved required ambiguity; requirement version approved | unresolved required=0; requirement approved=True | **PASS** | product_owner |
| G-EVIDENCE | Required evidence cited from current approved documents and every citation resolves | 14 citations resolve to current approved sources | **PASS** | domain_reviewer |
| G-SAMPLES | Every required cell has ≥ 100 eligible paired samples | min n = 108 | **PASS** | qa_engineer |
| G-TARGET | Target cell TS-4|warm_indoor top-1 improves by ≥ 5.0 pp | +12.17 pp (95% paired bootstrap CI +6.09 to +18.26) | **PASS** | product_owner |
| G-NO-REGRESSION | No required cell loses more than 2.0 pp top-1 vs baseline | worst cell TS-1|daylight_neutral +0.00 pp | **PASS** | domain_reviewer |
| G-COVERAGE | No required cell's coverage (answered/eligible) drops more than 3.0 pp | within limit | **PASS** | qa_engineer |
| G-ABSTENTION-DENOMINATOR | Abstentions remain in the denominator; every eligible sample has a prediction record | 1352 eligible samples × 2 models = 2704 prediction records; abstentions in denominator: baseline 26, candidate 26 | **PASS** | qa_engineer |
| G-CONTROLS | All required privacy and authorization control tests pass | 7/7 passed | **PASS** | privacy_reviewer |

Uncertainty: Wilson 95% for proportions; paired percentile bootstrap (2000 resamples, seed 7) for cell deltas. Δ is in percentage points; relative change is reported separately.

## Reviews and approvals

- Review code: APPROVE by u-qa
- Review domain: APPROVE by u-domain
- Review privacy: APPROVE by u-privacy
- Approval requirements: APPROVED by u-po, expires 2027-10-11T03:06:09.321760+00:00
- Approval release: APPROVED by u-release, expires 2026-10-14T03:06:09.954776+00:00, used by REL-c7880fd1771c

## Release REL-c7880fd1771c (simulated)

Model shade-matcher-v2.4.0-rc2, status ROLLED_BACK, stages [5, 25, 100] (prototype settings).
- 2026-10-11T03:06:09.981980+00:00: deploy 5% by u-release
- 2026-10-11T03:06:10.020978+00:00: promote 25% by u-release
- 2026-10-11T03:06:10.081845+00:00: rollback 0% by u-release

### Alert ALT-e12103995120 — DEV-T3|warm_indoor (RESOLVED)

Observed: {'accuracy_pct': 42.11, 'labelled': 57, 'wilson95': [30.19, 55.02], 'reference_pct': 72.95}
- DEV-T3|warm_indoor: observed top-1 42.11% on 57 labelled sessions vs reference 72.95% (Wilson 95% upper 55.02%).
- Other DEV-T3 cells: DEV-T3|daylight_neutral: 86.76% (n=68); DEV-T3|cool_fluorescent: 85.0% (n=40)
- Same lighting on other devices: DEV-T1|warm_indoor: 73.37% (n=184); DEV-T2|warm_indoor: 79.35% (n=155)
- Suspected cause: Released lighting-profile map lpm-v2 maps DEV-T3/warm_indoor to 'cool_fluorescent' (previous lpm-v1: 'warm_indoor').
- Caveat: A statistical alert alone does not prove root cause.
- Caveat: Observations are simulated; reference labels are synthetic and arrive with delay.
- Caveat: Confirm the hypothesis with a targeted device test before closing the incident.

## Limitations

- Synthetic data, fictional brand/policies; tone strata are not an endorsed classification method.
- Gates are illustrative demo rules; label validity and statistical uncertainty require expert review.
- Simulated deployment and monitoring; no customer traffic.
