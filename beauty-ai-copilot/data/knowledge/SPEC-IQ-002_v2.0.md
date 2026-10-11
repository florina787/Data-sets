---
doc_id: SPEC-IQ-002
version: 2.0
title: Image Quality Requirements
status: approved
effective_date: 2026-01-15
owner_role: cv_engineer
access: all
---
DEMO DOCUMENT — fictional specification for an independent prototype.

## §1 Scope
Applies to every image submitted to the shade matcher, in evaluation and in production.

## §2 Re-capture triggers
Request another image when: the face region is smaller than 20% of the frame; exposure clipping exceeds 5% of the face region; the lighting detector confidence is below 0.6; or motion blur exceeds the protocol threshold.

## §3 Evaluation eligibility
Samples failing image-quality checks are excluded from evaluation cells and counted separately as ineligible.
