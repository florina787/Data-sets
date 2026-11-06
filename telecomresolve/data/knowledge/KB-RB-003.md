---
id: KB-RB-003
title: Area incident handling runbook
version: "2.1"
doc_type: runbook
authority: runbook
product: home_internet
tenant_scope: "*"
allowed_roles: [specialist, network_analyst, field_coordinator, supervisor, auditor]
effective_date: "2026-08-20"
---
SYNTHETIC DOCUMENT for an independent prototype.

## Linking a case to an incident
A case may be associated with an incident only when the incident's network asset is on the service's mapped path (access node or its parent aggregation node) and the incident's active interval overlaps the time the customer's symptoms were observed. Geographic proximity or a shared postal area alone does not establish that the incident affects the customer.

## Closed incidents
A closed or resolved incident cannot explain symptoms that began after it ended. New complaints after closure must be investigated with fresh evidence.

## Restoration estimates
Only quote a restoration estimate that is published on the incident record. If no estimate is published, say that no estimate is available yet. Never guarantee a restoration time.

## During an active incident
Do not dispatch a technician to an individual service affected by an active incident on its mapped path. Do not ask customers to repeat troubleshooting during an active incident.
