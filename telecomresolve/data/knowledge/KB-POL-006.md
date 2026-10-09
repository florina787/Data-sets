---
id: KB-POL-006
title: Action approval policy
version: "2026.10-synthetic.1"
doc_type: policy
authority: policy
product: home_internet
tenant_scope: "*"
allowed_roles: [specialist, network_analyst, field_coordinator, supervisor, auditor]
effective_date: "2026-10-01"
---
SYNTHETIC POLICY mirroring the prototype's action catalog.

## Approval binding
An approval is bound to the case, the action type, the exact action payload, the policy version, the evidence snapshot, and an expiry time. A changed payload, a new evidence snapshot, or an expired approval requires a new review.

## Roles
Specialists may confirm low-risk actions such as incident association and customer troubleshooting suggestions. Technician dispatch requires supervisor approval with separation of duties. Bill credits are disabled.

## Execution
Authorization and policy are re-checked immediately before execution. A successful action response does not prove that service has recovered.
