# Limitations

**Data and models**
* All data is synthetic. Tone strata are fixture attributes, not a validated grouping method. Labels come from a
  fictional panel, and their validity is not established.
* Predictions are fixed-seed fixtures from per-cell probability profiles. No computer-vision inference or training
  happened, and fixture behaviour is not evidence of how any real model behaves. Common random numbers make unchanged
  cells identical, which gives zero-width intervals.
* There is no colour science. Shade IDs are catalogue identifiers, and nothing here measures perceptual colour
  difference.

**Statistics**
* Gates use point estimates against illustrative thresholds. Intervals are reported, but there is no power analysis or
  multiplicity correction. Production decisions need a statistical review.
* Monitoring reference values come from offline evaluation. Observations, labels and the device mix are simulated
  with documented parameters.

**Agents and language**
* Agent logic is rule-based and deterministic. Live-LLM mode adds summaries only, and it is covered by an optional
  test that was not run here (no key).
* The copilot answers a fixed set of intents from persisted state; it is not open-ended chat.

**Security and operations**
* Demo identity is a header persona. Production mode refuses it, and SSO is unconfigured.
* The audit trail is append-only at the application level with a hash chain. Tamper resistance needs infrastructure
  controls: WORM/object-lock storage, restricted database roles, and external anchoring of chain heads.
* Background jobs use an in-process thread pool. A production deployment needs a durable queue (see
  PRODUCTION_ARCHITECTURE.md). Restart recovery re-queues interrupted runs.
* Idempotency keys are stored without expiry.
* The image sandbox stores files in a local private directory without encryption at rest. Thumbnails and embeddings
  are never generated, so the inventory lists them as “nothing stored”. Backup expiry is a stated design value, not
  automation.
* Development tooling never executes candidate code. A real isolated build workspace (CI) is unconfigured.

**Scope**
* Only BR-101 is implemented. Lipstick AR, hair colour, recommendations, skincare guardrails and provider migration are
  backlog contracts. Photo deletion is partial (sandbox only).
* Business value is not demonstrated. Faster simulated execution does not show engineering time savings (see
  METRICS.md).

**What a real pilot still needs**
An authorized model and serving endpoint, a consented and licensed evaluation set with approved group and label
protocols, reviewer identities via SSO, read-only integrations with the registry, CI and storage, a statistical
review of the gates, and stakeholder validation of the gap hypotheses.
