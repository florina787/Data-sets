"""Intent-routing evaluation (benchmark v2).

Usage:
  uv run python scripts/evaluate_intent_routing.py --split train validation --methods rules_v1 rules_first_v1
  uv run python scripts/evaluate_intent_routing.py --split test --methods ... --final     (once, after freezing)

Scoring
  * correct      prediction is in the item's `acceptable` list
  * macro F1     over `expected` labels (strict), sklearn
  * outcomes     correct / clarified (prediction "clarify" when not expected) / refused (prediction
                 "unsupported" when not expected) / misrouted (any other wrong analytical intent)
  * a rules NO_MATCH, or a router asking the user to rephrase, is scored as "clarify";
    a policy refusal is "unsupported"
  * latency      wall-clock per question; LLM calls counted per question (cache disabled)

The test split is only read with --final; the script refuses otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_CACHE_PATH", str(Path(tempfile.mkdtemp()) / "intent_eval_cache.sqlite"))  # no cache hits: honest latency

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support  # noqa: E402

DATASETS = ROOT / "tests" / "evaluation" / "datasets"
OUT_DIR = ROOT.parent / "data" / "manifests" / "intent_routing"


def load(split: str) -> list[dict]:
    return [json.loads(line) for line in (DATASETS / f"intent_v2_{split}.jsonl").read_text().splitlines()]


# --- routers under test: each returns (label, info) with info = {"method", "llm_calls"} -------------

def _label_from_rules(intent) -> str:
    from app.agents.intent_rules import NO_MATCH

    return "clarify" if intent.reasoning == NO_MATCH else intent.category


def rules_v1(q: str) -> tuple[str, dict]:
    from scripts.intent_baselines.rules_v1 import parse_intent

    return _label_from_rules(parse_intent(q)), {"method": "rules", "llm_calls": 0}


def rules_v2(q: str) -> tuple[str, dict]:
    from app.agents.intent_rules import match_rules

    intent, rule = match_rules(q)
    return _label_from_rules(intent), {"method": "rules", "llm_calls": 0, "reason": rule}


def _qwen_v1(q: str) -> tuple[str, int]:
    from app.agents.intent_agent import compact_context
    from app.labeling.taxonomy import TOPICS
    from app.llm.gemini_client import LLMUnavailable, get_llm
    from app.llm.structured_output import IntentOutput
    from app.prompts.registry import get_prompt

    p = get_prompt("intent_understanding", "1.0")
    try:
        res = get_llm().generate_json(p, p.render(taxonomy=", ".join(f"{k} ({v.label})" for k, v in TOPICS.items()),
                                                  context=json.dumps(compact_context(None, [])), question=q), IntentOutput, purpose="intent_eval")
        return res.parsed.category, 1  # type: ignore[union-attr]
    except LLMUnavailable:
        return "clarify", 1


def qwen_only_v1(q: str) -> tuple[str, dict]:
    label, n = _qwen_v1(q)
    return label, {"method": "llm", "llm_calls": n}


def rules_first_v1(q: str) -> tuple[str, dict]:
    """The router as it stood before this work: rules, model only on NO_MATCH, policy refusals stand."""
    from scripts.intent_baselines.rules_v1 import NO_MATCH, parse_intent

    r = parse_intent(q)
    if r.reasoning != NO_MATCH:
        return r.category, {"method": "rules", "llm_calls": 0}
    from app.llm.gemini_client import get_llm

    if not get_llm().available():
        return "clarify", {"method": "rules", "llm_calls": 0}
    label, n = _qwen_v1(q)
    return label, {"method": "llm", "llm_calls": n}


def _qwen_v2(q: str, version: str) -> tuple[str, dict]:
    from app.llm.gemini_client import LLMUnavailable, get_llm
    from app.llm.structured_output import IntentClassification
    from app.prompts.registry import get_prompt

    p = get_prompt("intent_classification", version)
    try:
        res = get_llm().generate_json(p, p.render(question=q), IntentClassification, purpose="intent_eval")
        return res.parsed.category, {"method": "llm", "llm_calls": 1}  # type: ignore[union-attr]
    except LLMUnavailable as e:
        return "clarify", {"method": "llm_error", "llm_calls": 1, "reason": str(e)[:100]}


def router_v2(q: str, use_llm: bool = True) -> tuple[str, dict]:
    from app.agents.intent_router import route_intent

    d = route_intent(q, previous=None, allow_llm=use_llm)
    return d.label, {"method": d.method, "llm_calls": d.llm_calls, "reason": d.reason}


METHODS = {
    "rules_v1": rules_v1, "rules_v2": rules_v2, "qwen_only_v1": qwen_only_v1, "rules_first_v1": rules_first_v1,
    "qwen_only_v2_0": lambda q: _qwen_v2(q, "2.0"), "qwen_only_v2_1": lambda q: _qwen_v2(q, "2.1"),
    "router_v2": router_v2, "router_v2_no_llm": lambda q: router_v2(q, use_llm=False),
}


# --- scoring -------------------------------------------------------------------------------------------

def score(rows: list[dict], preds: list[str], infos: list[dict], lat: list[float]) -> dict:
    y_true = [r["expected"] for r in rows]
    correct = [p in r["acceptable"] for r, p in zip(rows, preds)]
    labels = sorted(set(y_true) | set(preds))
    pr, rc, f1, sup = precision_recall_fscore_support(y_true, preds, labels=labels, zero_division=0)
    present = [i for i, lab in enumerate(labels) if lab in set(y_true)]
    outcomes = Counter()
    for r, p, ok in zip(rows, preds, correct):
        outcomes["correct" if ok else "clarified" if p == "clarify" else "refused" if p == "unsupported" else "misrouted"] += 1
    unsup = [p for r, p in zip(rows, preds) if r["expected"] == "unsupported"]
    supported = [p for r, p in zip(rows, preds) if r["expected"] not in ("unsupported", "clarify")]
    errors = [{"question": r["question"], "expected": r["expected"], "predicted": p, "kind": r["kind"], "family": r["family"],
               "method": i.get("method"), "reason": i.get("reason")} for r, p, i, ok in zip(rows, preds, infos, correct) if not ok]
    n = len(rows)
    answered = [ok for ok, p in zip(correct, preds) if p != "clarify"]
    return {
        "n": n, "accuracy": round(sum(correct) / n, 4),
        "macro_f1": round(float(sum(f1[i] for i in present) / len(present)), 4),
        "per_intent": [{"intent": labels[i], "precision": round(float(pr[i]), 3), "recall": round(float(rc[i]), 3),
                        "f1": round(float(f1[i]), 3), "support": int(sup[i])} for i in present],
        "outcomes": dict(outcomes),
        "clarification_rate": round(sum(p == "clarify" for p in preds) / n, 4),
        "misrouting_rate": round(outcomes["misrouted"] / n, 4),
        "coverage": round(len(answered) / n, 4), "accuracy_when_answered": round(sum(answered) / len(answered), 4) if answered else None,
        "unsupported_rejection_rate": round(sum(p == "unsupported" for p in unsup) / len(unsup), 4) if unsup else None,
        "false_refusal_rate": round(sum(p == "unsupported" for p in supported) / len(supported), 4) if supported else None,
        "latency_ms": {"mean": round(statistics.mean(lat), 1), "p50": round(statistics.median(lat), 1),
                       "p95": round(sorted(lat)[min(len(lat) - 1, int(0.95 * len(lat)))], 1)},
        "llm_calls": sum(i.get("llm_calls", 0) for i in infos),
        "llm_invocation_rate": round(sum(i.get("llm_calls", 0) > 0 for i in infos) / n, 4),
        "by_method": dict(Counter(i.get("method") for i in infos)),
        "by_kind": {k: round(sum(c for c, r in zip(correct, rows) if r["kind"] == k) / sum(r["kind"] == k for r in rows), 3)
                    for k in sorted({r["kind"] for r in rows})},
        "confusion": {"labels": labels, "matrix": confusion_matrix(y_true, preds, labels=labels).tolist()},
        "errors": errors,
    }


def run(method: str, rows: list[dict]) -> dict:
    fn = METHODS[method]
    preds, infos, lat = [], [], []
    for r in rows:
        t0 = time.perf_counter()
        label, info = fn(r["question"])
        lat.append((time.perf_counter() - t0) * 1000)
        preds.append(label)
        infos.append(info)
    return score(rows, preds, infos, lat)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", nargs="+", default=["validation"])
    ap.add_argument("--methods", nargs="+", default=["rules_v1"])
    ap.add_argument("--final", action="store_true", help="required to read the frozen test split")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    if "test" in args.split and not args.final:
        sys.exit("The test split is frozen: pass --final only once routing, thresholds and prompts are fixed.")
    from app.llm.gemini_client import get_llm

    llm = get_llm()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for split in args.split:
        rows = load(split)
        for m in args.methods:
            if m.startswith("qwen") and not llm.available():
                print(f"{m}: skipped ({llm.status().get('reason')})")
                continue
            res = run(m, rows)
            res.update({"method": m, "split": split, "provider": llm.status().get("provider"), "model": llm.status().get("model")})
            name = f"{split}_{m}{('_' + args.tag) if args.tag else ''}.json"
            (OUT_DIR / name).write_text(json.dumps(res, indent=1) + "\n")
            print(f"{split:10} {m:18} acc={res['accuracy']:.1%} macroF1={res['macro_f1']:.3f} misrouted={res['misrouting_rate']:.1%} "
                  f"clarify={res['clarification_rate']:.1%} unsup_rej={res['unsupported_rejection_rate']} false_ref={res['false_refusal_rate']} "
                  f"llm_rate={res['llm_invocation_rate']:.1%} p95={res['latency_ms']['p95']}ms")


if __name__ == "__main__":
    main()
