---
doc_id: DS-CARD-010
version: 1.0
title: Dataset Card — DS-2026.09-SHADE (synthetic)
status: approved
effective_date: 2026-09-17
owner_role: ml_engineer
access: all
---
DEMO DOCUMENT — describes a fixed-seed synthetic dataset. No images or people are represented.

## §1 Composition
1,560 synthetic records: 4 synthetic tone strata × 3 lighting categories × 130 records (10 validation, 120 held-out test). Devices covered: DEV-T1 and DEV-T2 only.

## §2 Grouping protocol
GP-DEMO-1: tone strata are synthetic attributes assigned at fixture creation. They are not an endorsed real-world classification method and were never inferred from faces.

## §3 Label provenance
LP-DEMO-PANEL-01: fictional three-reviewer panel, majority label. Label validity is not established; real labels require an approved protocol (expert assessment, measured colour references or both).

## §4 Known limitations
No DEV-T3 samples. No measured colour references. Predictions are fixtures from deterministic profiles, not computer-vision inference.
