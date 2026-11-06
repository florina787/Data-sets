---
id: KB-DSP-004
title: Technician dispatch prerequisites
version: "1.2"
doc_type: policy
authority: policy
product: home_internet
tenant_scope: "*"
allowed_roles: [specialist, network_analyst, field_coordinator, supervisor, auditor]
effective_date: "2026-09-10"
---
SYNTHETIC POLICY for an independent prototype. Not an operator's real policy.

## Evidence prerequisites
A technician dispatch may be proposed when fresh diagnostics (collected within the last 24 hours) show a line impairment or equipment fault, no active incident exists on the service's mapped path, and applicable customer troubleshooting has already been completed or is not appropriate.

## Line impairment indicators
Line impairment indicators are: SNR margin below 6 dB, more than 200 CRC errors per hour, or more than 1 link retrain per hour, while other services on the same access node show no loss-of-signal pattern (which would instead suggest a shared network problem).

## Approval
Dispatch requires approval by a supervisor who did not propose the dispatch. Appointment availability is not inferred; the coordinator confirms it with the customer.
