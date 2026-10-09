---
doc_id: ENG-STD
title: Digital Delivery Engineering Standard (synthetic)
version: "2.1"
owner: Digital Engineering
effective: 2026-04-01
---
# Digital Delivery Engineering Standard

## 1. Requirements
Every requirement needs measurable acceptance criteria. Ambiguities in a brief are recorded as decisions with an owner before implementation starts.

## 2. Testing
Every acceptance criterion is covered by at least one automated test. A test that exposed a defect is kept as a regression test and must not be weakened or deleted.

## 3. Release gates
A release needs passing critical tests on the exact revision being released, a clean static analysis policy, no unresolved blocking findings, and a recorded approval from a release approver.

## 4. Separation of duties
Engineers cannot approve their own releases. Release approval is limited to the release-approver role.

## 5. Incident response
Mitigate first, either by rolling back to the last known good release or by shipping a reviewed repair. Every incident links to the release and the telemetry that support it.
