# Evaluation

- `labels.json` — human-authored expected outcomes for the 13 synthetic cases. Kept outside `data/synthetic/`
  so no agent or connector reads it.
- `results/` — reports written by `python -m app.evaluation.run` (JSON + `latest.md`).

Two kinds of evaluation are kept separate:

1. **Deterministic safety and workflow evaluation** (this runner, DEMO provider, free, runs in CI): permission and
   approval probes, unauthorized writes, citation resolution, abstention, refusals, terminal states, audit replay.
2. **Live-model quality evaluation** (not run yet): must be opt-in, budget-limited, and record dataset version,
   provider, model id, prompts, configuration and date. An LLM judge may supplement it but never decides
   authorization or policy compliance.

Release gates (prototype): all permission/approval tests pass; zero unauthorized writes; all references resolve;
every seeded case reaches its expected state. Model-quality thresholds are intentionally not set until a baseline
exists.
