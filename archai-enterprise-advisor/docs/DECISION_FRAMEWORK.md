# ArchAI Decision Framework

All logic lives in `app/decision_engine/` and `app/governance/autonomy.py`. All numbers live in `app/decision_engine/weights.py`. Ratings are on a 0–5 scale and are normalized to 0..1 (`u = rating / 5`).

## Scores

| Score | Formula (points out of 100) | Gates / adjustments |
|---|---|---|
| ML Suitability | prediction 55 · structured share 20 · data quality 15 · ML-task match 10 | capped at 30 if prediction ≤ 1 |
| GenAI Suitability | generation 50 · unstructured share 15 · GenAI-task match 15 · hallucination tolerance 10 · (1 − deterministic) 10 | capped at 30 if generation ≤ 1 |
| RAG Suitability | proprietary knowledge 30 · citations 15 · change frequency 10 · unstructured 15 · fragmentation 15 · document quality 15 | capped at 25 if proprietary ≤ 1 and citations ≤ 1; an existing vector DB adds **0** |
| Agentic Readiness | multi-step 25 · variability 20 · cross-system 20 · tools 20 · autonomy benefit 15; × (0.75 + 0.25 · infra/100) | × 0.4 if deterministic ≥ 4; capped at 45 if need gate unmet; capped at 20 for deterministic-only actions |
| AI Suitability | strongest of {prediction, generation, 0.85·knowledge, reasoning} × 65 + second strongest × 35; × (1 − 0.45 · deterministic) | capped at 20 for deterministic workloads |
| Infrastructure Readiness | container 20 · service architecture 15 · identity 15 · gateway 10 · secrets 10 · CI/CD 10 · observability 10 · private networking 5 · integration 5 | — |
| Data Readiness | availability 20 · quality 20 · permissions 15 · freshness 10 · ownership 10 · document quality 10 · lineage 7.5 · metadata 7.5 | — |
| Security Risk | industry baseline (banking 30 … general 10) + PII 10, financial 8, confidential 6, privileged 10, residency 5, regulation 2/pt, customer-facing 5, high-risk writes 8, deterministic-only actions 10 | minus mitigations: RBAC/ABAC 4, secrets 3, private networking 3, gateway 2 |
| Operational Risk | transaction criticality 25 · availability 15 · latency 10 · integration 10 · legacy 5 · platform gap 15 · AI-maturity gap 10 · volume 5 · variability 5 | — |
| Overall Risk | 0.45 · security + 0.35 · operational + 0.20 · (100 − data readiness) | — |
| ROI / Business Value | 100 · r / (r + 1.5), where r = benefit / (AI operating + implementation / 3) | — |

## Decision rules (in order)

1. **R-DET-01.** Deterministic workload (deterministic ≥ 4 with low AI signals) → no AI.
2. **R-AI-01.** AI suitability < 40 → no AI.
3. **Pattern qualification.** ML ≥ 60, GenAI ≥ 55, RAG ≥ 60 (plus a generation/search need **and** data prerequisites; otherwise **R-RAG-DATA**), Agentic ≥ 60 (plus the need gate, and the workload is not deterministic).
4. **R-AI-02.** No pattern qualifies → no AI.
5. **R-SIMPLE-01.** Agentic if it qualifies, adding RAG if RAG also qualifies. Otherwise RAG, then GenAI. ML is added when it qualifies.
6. **R-HYB-01.** HYBRID if any of the following applies: a deterministic core (deterministic ≥ 3 with authoritative systems), deterministic-only actions, cross-system lookups without agents, or ML combined with GenAI.
7. **R-FORBID-01 / R-REPL-01.** Deterministic-only actions stay with existing systems. A request to replace a deterministic component is rejected.
8. **No AI.** The result is KEEP EXISTING when an existing solution exists, and TRADITIONAL SOFTWARE otherwise.
9. **Agentic verdict.** CONSTRAINED if the industry is regulated, there are high-risk writes, security risk ≥ 45 or overall risk ≥ 50. Otherwise RECOMMENDED (bounded).
10. **Autonomy caps** (see README → Governance).
11. **Challenger (R-CHAL-01).** A FAIL excludes the offending pattern and the engine decides again, up to 3 revisions. If ROI fails and the benefit cannot even recover a third of the implementation cost, all AI patterns are excluded.
