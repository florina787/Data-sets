---
doc_id: SPEC-LIGHT-003
version: 1.1
title: Supported Lighting and Device Protocol
status: approved
effective_date: 2026-04-01
owner_role: cv_engineer
access: all
---
DEMO DOCUMENT — fictional specification for an independent prototype.

## §1 Lighting categories
Three declared lighting categories are supported: daylight_neutral (5000–6500K), warm_indoor (2700–3500K) and cool_fluorescent (4000–4500K, fluorescent spectrum).

## §2 Lighting capture protocol
Evaluation images are captured with a grey reference card in frame. Lighting category is declared by the capture operator and verified against the card; it is never inferred from skin appearance.

## §3 Supported devices
Validated device cohorts: DEV-T1 and DEV-T2. Device cohort DEV-T3 is not yet validated; any lighting-profile mapping for DEV-T3 must be verified before it receives production traffic.

## §4 Lighting profile maps
Each device cohort maps declared lighting to a preprocessing profile through a versioned lighting-profile map. A change to the map is a model configuration change and requires evaluation.
