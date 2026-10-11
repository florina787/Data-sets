---
doc_id: SPEC-SHADE-001
version: 1.2
title: Foundation Shade Matching Specification
status: approved
effective_date: 2026-03-01
owner_role: domain_reviewer
access: all
---
DEMO DOCUMENT — fictional specification for an independent prototype. Not a policy of any real company.

## §1 Purpose
The shade matcher returns up to three ranked foundation shade IDs from the active catalogue for a single consented face image captured under a declared lighting category.

## §2 Definition of a correct match
A top-1 match is correct when the first-ranked shade ID equals the reference shade ID assigned under the active label protocol. A top-3 match is correct when the reference shade ID appears anywhere in the three ranked results. An abstention (no shade returned) is never a correct match and remains in the denominator.

## §3 Reference labels
Reference shade IDs are assigned by the label protocol named in the dataset card. Shade IDs are catalogue identifiers, not colour measurements; colour-difference metrics must not be computed from shade IDs.

## §4 Requesting another image
When image quality checks fail (see SPEC-IQ-002 §2) the matcher must request another image instead of returning a shade. Such requests are recorded as abstentions for evaluation purposes.
