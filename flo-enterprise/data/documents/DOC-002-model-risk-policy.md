---
id: DOC-002
title: Model and AI Risk Management Policy (synthetic)
owner: Chief Risk Officer
version: "1.4"
classification: internal
tenant: t-flo
access_groups: [all-staff]
effective_date: 2025-06-01
jurisdiction: CA
language: en
doc_type: policy
---
# Scope
Applies to quantitative models and AI agents used by FLO, including large language model workflows.

# Inventory and validation
Every AI agent must be registered with an owner, version, permitted tools, data classification and evaluation requirements. Agents must pass the evaluation gate (financial correctness, groundedness, authorization and privacy leakage tests) before release.

# Human oversight
AI outputs that are client-facing, that change official financial records, or that modify portfolios require documented human approval. AI systems must not make final legal or regulatory determinations.

# Monitoring
Production agents are monitored for latency, cost, failure rates and evaluation scores. Repeated tool failures must open an incident.
