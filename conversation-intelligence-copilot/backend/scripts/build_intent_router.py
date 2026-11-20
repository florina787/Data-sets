"""Build the semantic intent-example set (train split) and calibrate its thresholds (validation split).

  uv run python scripts/build_intent_router.py

Writes app/agents/data/intent_examples.json and app/agents/data/intent_router_config.json.
Thresholds: the (min_similarity, min_margin) pair with the highest validation coverage whose
accepted predictions are at least TARGET_PRECISION correct (ties -> stricter). The test split is
never read here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents import semantic_intent as si  # noqa: E402

DATASETS = ROOT / "tests" / "evaluation" / "datasets"
TARGET_PRECISION = 0.95
MIN_ACCEPTED = 10


def rows(split: str) -> list[dict]:
    return [json.loads(line) for line in (DATASETS / f"intent_v2_{split}.jsonl").read_text().splitlines()]


def main() -> None:
    # Refusals come from the policy rules and clarification from the absence of a confident match, so the
    # example set holds analytical intents only (short "clarify" examples like "app crashes" otherwise attract
    # every question that names a topic).
    train = [r for r in rows("train") if r["expected"] not in ("clarify", "unsupported")]
    si.DATA.mkdir(parents=True, exist_ok=True)
    si.EXAMPLES.write_text(json.dumps([{"intent": r["expected"], "question": r["question"], "family": r["family"]} for r in train],
                                      indent=1, ensure_ascii=False) + "\n")
    si.get_semantic_index.cache_clear()
    idx = si.get_semantic_index()
    if idx is None:
        sys.exit("sentence-transformers model unavailable")
    val = rows("validation")
    scored = []
    for r in val:
        m = idx.match(r["question"], {"min_similarity": 0, "min_margin": 0})
        scored.append((m.similarity, m.margin, m.top in r["acceptable"]))
    best = None
    for t100 in range(30, 96, 1):
        for m100 in range(0, 31, 1):
            tau, mu = t100 / 100, m100 / 100
            acc = [ok for s, mg, ok in scored if s >= tau and mg >= mu]
            if len(acc) < MIN_ACCEPTED:
                continue
            prec = sum(acc) / len(acc)
            if prec >= TARGET_PRECISION:
                key = (len(acc), tau, mu)
                if best is None or key[0] > best[0][0] or (key[0] == best[0][0] and (tau, mu) > (best[0][1], best[0][2])):
                    best = (key, prec)
    if best is None:
        cfg = {"min_similarity": 1.1, "min_margin": 1.1, "note": f"No threshold reached {TARGET_PRECISION:.0%} precision on validation; semantic stage disabled."}
    else:
        (n_acc, tau, mu), prec = best
        cfg = {"min_similarity": tau, "min_margin": mu, "target_precision": TARGET_PRECISION,
               "validation": {"n": len(val), "accepted": n_acc, "coverage": round(n_acc / len(val), 4), "precision": round(prec, 4),
                              "top1_accuracy_unthresholded": round(sum(ok for *_, ok in scored) / len(val), 4)},
               "examples": len(train), "example_source": "intent benchmark v2, train split",
               "note": "Cosine similarities are ranking scores, not probabilities."}
    si.CONFIG.write_text(json.dumps(cfg, indent=1) + "\n")
    print(json.dumps(cfg, indent=1))


if __name__ == "__main__":
    main()
