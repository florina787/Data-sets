---
doc_id: PROT-EVAL-008
version: 2.0
title: Shade Matching Evaluation Protocol
status: approved
effective_date: 2026-06-01
supersedes: 1.0
owner_role: qa_engineer
access: all
---
DEMO DOCUMENT — fictional evaluation protocol for a prototype.

## §1 Evaluation cells
Required cells are the cross product of the four synthetic tone strata (TS-1 to TS-4) and the three declared lighting categories: twelve cells.

## §2 Paired comparison
Baseline and candidate are scored on the same eligible sample IDs from the held-out test split. Deltas are reported in percentage points (pp), distinct from relative percentage change.

## §3 Uncertainty
Report 95% paired bootstrap intervals (2,000 resamples, fixed seed) for each cell delta, and Wilson intervals for each accuracy. With twelve cells, some intervals will exclude zero by chance; deterministic gates are illustrative and do not replace a statistical review.

## §4 Abstention
Abstentions count as incorrect for top-1 and top-3 accuracy. Coverage and conditional accuracy on answered samples are reported separately.

## §5 Test-set protection
The held-out test split must not be used for tuning. Each evaluation on the test split is counted per change and reported.
