# RCA engine

`florome/rca/engine.py` is pure and deterministic, with no LLM. The scope is the symptomatic resource plus all of its upstream ancestors.

## Anomalies

* ERROR or CRITICAL logs and statuses
* Threshold breaches on non-capacity metrics
* Traces with a 5xx status

A resource's **onset** is its first anomaly.

## Hypotheses and tests

| Kind | Tests | Classification |
|---|---|---|
| change (deployment/config) | temporal_precedence, proximity (≤120 min), signature_match (error text mentions the change's terms), no_earlier_upstream_anomaly, dependency_path | **disproven** if precedence fails, or if the signature fails *and* an earlier upstream anomaly exists. **confirmed** if all pass. **probable** if the signature is untestable but other tests pass. **inconclusive** otherwise. |
| saturation | capacity_breach_near_onset | disproven, probable or inconclusive. Never confirmed: saturation alone is correlational. |
| propagation (edge A→B) | temporal_precedence, dependency_path, signature_match (B's errors name A) | confirmed, probable, inconclusive or disproven |

The conclusion is the strongest non-disproven root candidate. Ties at the top rank make the conclusion **inconclusive**. The causal chain follows non-disproven propagation links.

## Challenger

`rca/challenger.py` runs these checks: correlation_only, competing_explanations, causal_chain_gaps, evidence_gaps, single_source, unexplained_anomalies. It only downgrades.

## Demo result (reproducible)

| H | Hypothesis | Status |
|---|---|---|
| H1 | revenue-api deployment (3h earlier) | disproven |
| H2 | autoscale config change on revenue-api | disproven: errors don't mention it, and upstream failed first |
| H3 | ingest-orders v2.14.0 schema-v3 parser | **confirmed** |
| H4, H5 | CPU saturation | disproven: CPU 35% and 41% |
| H6 | ingest-orders → orders-raw | **probable**: the bucket has no logs to carry a signature |
| H7–H9 | downstream propagation | confirmed |

The challenger warns about the H6 gap and about single-source evidence. It honestly marks the S3 link as weaker than the rest.
