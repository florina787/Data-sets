"""Evaluation harness on the real dataset. Writes data/manifests/evaluation_results.json
and docs/evaluation/EVALUATION_RESULTS.md. Every number in those files is produced here.

Usage (from backend/):  uv run python -m scripts.evaluate
"""

from __future__ import annotations

import json
import os
import re
import statistics
import tempfile
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix, precision_recall_fscore_support

# Session memory and telemetry for the evaluation go to a throwaway directory, so
# evaluation runs never appear as real usage in the app's metrics.
_tmp = Path(tempfile.mkdtemp(prefix="cic-eval-"))
os.environ.setdefault("MEMORY_DATABASE_PATH", str(_tmp / "memory.sqlite"))
os.environ.setdefault("CHECKPOINT_DATABASE_PATH", str(_tmp / "checkpoints.sqlite"))

from app.agents.graph import run_chat  # noqa: E402
from app.agents.intent_rules import parse_intent  # noqa: E402
from app.analytics.db import get_db  # noqa: E402
from app.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.governance.human_review import get_review_store, metrics as review_metrics  # noqa: E402
from app.labeling import rules  # noqa: E402
from app.llm.gemini_client import get_llm  # noqa: E402
from app.retrieval.index import get_retriever  # noqa: E402
from app.schemas.analysis import Scope  # noqa: E402

DATASETS = Path(__file__).resolve().parents[1] / "tests" / "evaluation" / "datasets"


def pctl(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * len(v)))], 1)


# ---------------------------------------------------------------------------------------------
# 1. Independent oracle for the Q1 numbers (re-implemented from the raw CSV, no app code)
# ---------------------------------------------------------------------------------------------
ORACLE_TOPICS = [
    ("Duplicate charge", r"^I was charged twice for my"), ("Feature not working", r"^Hello, my .* is not working as expected"),
    ("Paid but service not delivered", r"^UPI shows successful"), ("Coupon not applying", r"^Coupon isn.t applying"),
    ("General help request", r"^(Hi, I need help with my|Mujhe .* ke baare mein help chahiye)"), ("App crash", r"^App crash ho rahi hai"),
    ("Login / account locked", r"^I can.t log in"), ("Item or service not received", r"^The .* hasn.t arrived yet"),
]
ORACLE_SCORES = {"Still not fixed.": -1.0, "It’s urgent.": -0.6, "Thoda jaldi please": -0.6, "Okay, waiting": 0.0, "Got it.": 1.0, "Thanks, that helps.": 0.8}


def oracle_q1(raw_zip: Path, month: str) -> dict:
    with zipfile.ZipFile(raw_zip) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX"))
        df = pd.read_csv(z.open(name))
    df["ts"] = pd.to_datetime(df["timestamp"])
    start = df.groupby("conv_id")["ts"].min()
    convs = start[start.dt.strftime("%Y-%m") == month].index
    out: Counter = Counter()
    totals: Counter = Counter()
    for cid, g in df[df["conv_id"].isin(convs)].sort_values(["conv_id", "turn_index"]).groupby("conv_id"):
        opening = g.iloc[0]["text"]
        topic = next(t for t, p in ORACLE_TOPICS if re.search(p, opening))
        scores = [0.0 if topic == "General help request" else -0.6]
        for t in g[(g["role"] == "customer") & (g["turn_index"] > 0)]["text"]:
            scores.append(next(v for k, v in ORACLE_SCORES.items() if t.startswith(k)))
        totals[topic] += 1
        if sum(scores) / len(scores) <= -0.25:
            out[topic] += 1
    return {"conversations": int(sum(totals.values())), "negative": int(sum(out.values())), "negative_by_topic": dict(out), "by_topic": dict(totals)}


def eval_q1_oracle() -> dict:
    s = get_settings()
    r = run_chat("What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?")
    month = r["dataset_scope"]["window"]["start"][:7]
    oracle = oracle_q1(s.raw_dataset_path, month)
    system = {row["name"]: int(row["negative"]) for row in r["rankings"]}
    mism = {k: (system.get(k), oracle["negative_by_topic"].get(k)) for k in system if system.get(k) != oracle["negative_by_topic"].get(k)}
    total_neg = next(m["value"] for m in r["metrics"] if m["id"] == "negative_conversations")
    total = next(m["value"] for m in r["metrics"] if m["id"] == "conversations_in_scope")
    return {"month": month, "system_top5": system, "oracle_negative_by_topic": oracle["negative_by_topic"],
            "totals_match": total == oracle["conversations"] and total_neg == oracle["negative"],
            "top5_counts_match": not mism, "mismatches": mism, "system_totals": [total, total_neg], "oracle_totals": [oracle["conversations"], oracle["negative"]]}


# ---------------------------------------------------------------------------------------------
# 2. Intent classification
# ---------------------------------------------------------------------------------------------
def eval_intent() -> dict:
    items = [json.loads(line) for line in (DATASETS / "intent_questions.jsonl").read_text().splitlines()]
    y_true = [i["expected"] for i in items]
    y_pred = [parse_intent(i["question"]).category for i in items]
    labels = sorted(set(y_true))
    p, r, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    errors = [{"question": i["question"], "expected": t, "predicted": pr} for i, t, pr in zip(items, y_true, y_pred) if t != pr]
    out = {"classifier": "rules", "n": len(items), "accuracy": round(sum(a == b for a, b in zip(y_true, y_pred)) / len(items), 4),
           "macro_f1": round(float(f1.mean()), 4),
           "per_class": [{"label": lab, "precision": round(float(a), 3), "recall": round(float(b), 3), "f1": round(float(c), 3), "support": int(d)}
                         for lab, a, b, c, d in zip(labels, p, r, f1, sup)], "errors": errors}
    held = [json.loads(line) for line in (DATASETS / "intent_questions_heldout.jsonl").read_text().splitlines()]
    h_pred = [parse_intent(i["question"]).category for i in held]
    misses = [(i, p) for i, p in zip(held, h_pred) if p != i["expected"]]
    out["heldout"] = {
        "n": len(held), "accuracy": round(1 - len(misses) / len(held), 4),
        "safe_failures": sum(p == "unsupported" for _, p in misses), "misrouted": sum(p != "unsupported" for _, p in misses),
        "errors": [{"question": i["question"], "expected": i["expected"], "predicted": p} for i, p in misses],
        "note": "Written after the parser was tuned on the main set and scored once without further changes.",
    }
    llm = get_llm()
    if llm.available():
        from app.agents.intent_agent import resolve_intent

        g_pred, valid, lat = [], 0, []
        for i in items:
            t0 = time.perf_counter()
            intent, source, _ = resolve_intent(i["question"], None, [], "eval")
            lat.append((time.perf_counter() - t0) * 1000)
            valid += source == "gemini"
            g_pred.append(intent.category)
        out["gemini"] = {"accuracy": round(sum(a == b for a, b in zip(y_true, g_pred)) / len(items), 4), "schema_valid_rate": round(valid / len(items), 4),
                         "p50_ms": pctl(lat, 0.5)}
    else:
        out["gemini"] = {"status": "not_run", "reason": llm.status().get("reason")}
    return out


# ---------------------------------------------------------------------------------------------
# 3. Labeller robustness: lexicon fallback vs template labels on all real messages
# ---------------------------------------------------------------------------------------------
def eval_labels() -> dict:
    db = get_db()
    df = db.frame("""SELECT m.message_id, m.speaker_role, m.turn_index, m.clean_text, l.sentiment, l.method
                     FROM messages m JOIN message_labels l USING (message_id) WHERE m.dataset_source='original' AND m.speaker_role='customer'""")
    coverage = df["method"].value_counts(normalize=True).round(4).to_dict()
    lex = [rules._lexicon_label(t, "customer", int(i)).sentiment for t, i in zip(df["clean_text"], df["turn_index"])]
    labels = ["positive", "neutral", "negative", "mixed"]
    p, r, f1, sup = precision_recall_fscore_support(df["sentiment"], lex, labels=labels, zero_division=0)
    out = {
        "template_coverage": coverage,
        "unique_customer_texts": int(df["clean_text"].nunique()),
        "lexicon_fallback_vs_templates": {
            "n_messages": len(df), "accuracy": round(float((df["sentiment"] == pd.Series(lex)).mean()), 4),
            "cohen_kappa": round(float(cohen_kappa_score(df["sentiment"], lex)), 4),
            "per_class": [{"label": lab, "precision": round(float(a), 3), "recall": round(float(b), 3), "f1": round(float(c), 3), "support": int(d)}
                          for lab, a, b, c, d in zip(labels, p, r, f1, sup)],
            "confusion_matrix": {"labels": labels, "rows_template_cols_lexicon": confusion_matrix(df["sentiment"], lex, labels=labels).tolist()},
            "note": "Measures how the low-confidence fallback would label unseen phrasing, using the template labels as reference.",
        },
        "human_review": review_metrics(db, get_review_store()),
        "gemini_labels": {"status": "not_run", "reason": get_llm().status().get("reason")} if not get_llm().available() else {"status": "available: run scripts.label_dataset"},
    }
    return out


# ---------------------------------------------------------------------------------------------
# 4. Retrieval: paraphrased queries (no template wording) with known relevant sets
# ---------------------------------------------------------------------------------------------
PARAPHRASES = {
    "duplicate_charge": "the customer was billed two times for {p}",
    "payment_not_reflected": "payment went through but {p} was never activated",
    "coupon_not_applied": "discount code rejected when paying for {p}",
    "not_received": "still waiting for {p}, it never showed up",
    "app_crash": "application keeps closing when I open {p}",
    "account_locked": "cannot sign in, my profile is blocked",
    "service_malfunction": "{p} is broken and does not work properly",
    "general_help": "I have a question about {p}",
}
PRODUCTS = ["Wallet", "Order", "Insurance", "Broadband", "Flight"]


def _eval_mode(ret, conv, mode: str) -> dict:
    rows, lat = [], []
    for topic, tmpl in PARAPHRASES.items():
        for prod in (PRODUCTS if "{p}" in tmpl else [None]):
            q = tmpl.format(p=prod or "")
            t0 = time.perf_counter()
            res = ret.search(q, Scope(), k=5, mode=mode)["results"]
            lat.append((time.perf_counter() - t0) * 1000)
            ids = [r["conversation_id"] for r in res]
            topic_hits = [conv.loc[i, "topic"] == topic for i in ids]
            exact = [conv.loc[i, "topic"] == topic and (prod is None or conv.loc[i, "product"] == prod) for i in ids]
            first = next((k for k, h in enumerate(exact) if h), None)
            rows.append({"query": q, "topic": topic, "product": prod, "topic_p@5": sum(topic_hits) / 5, "exact_p@5": sum(exact) / 5,
                         "hit@5": any(exact), "rr": 0 if first is None else 1 / (first + 1), "duplicates": len(ids) - len(set(ids))})
    df = pd.DataFrame(rows)
    return {
        "mode": mode, "queries": len(df),
        "topic_precision@5": round(df["topic_p@5"].mean(), 4), "exact_precision@5": round(df["exact_p@5"].mean(), 4),
        "hit_rate@5": round(df["hit@5"].mean(), 4), "mrr@5": round(df["rr"].mean(), 4), "duplicate_rate": round(df["duplicates"].sum() / (5 * len(df)), 4),
        "latency_p50_ms": pctl(lat, 0.5), "latency_p95_ms": pctl(lat, 0.95),
        "by_topic": df.groupby("topic")[["topic_p@5", "exact_p@5"]].mean().round(3).reset_index().to_dict("records"),
    }


def eval_retrieval() -> dict:
    """Score every available method (LSA, dense MiniLM, hybrid RRF) on the same queries; the headline is the app's default mode."""
    db = get_db()
    conv = db.frame("SELECT conversation_id, topic, product FROM conversations WHERE dataset_source='original'").set_index("conversation_id")
    ret = get_retriever()
    modes = ["lsa"] + (["dense", "hybrid"] if "dense" in ret.methods else [])
    by_mode = {m: _eval_mode(ret, conv, m) for m in modes}
    default = ret.default_mode if ret.default_mode in by_mode else "lsa"
    base_topic = conv["topic"].value_counts(normalize=True).mean()
    return {
        **by_mode[default], "default_mode": default, "embedding_backend": ret.manifest["embedding_backend"],
        "backends": {m: b["name"] for m, b in ret.manifest["backends"].items()}, "fusion": ret.manifest.get("fusion"),
        "by_mode": by_mode, "random_baseline_topic_precision": round(float(base_topic), 4),
        "note": "Queries are paraphrases that avoid the template wording; relevance = same issue topic (and product where named).",
    }


# ---------------------------------------------------------------------------------------------
# 5. End-to-end: QA, grounding, citations, unsupported handling, latency
# ---------------------------------------------------------------------------------------------
def eval_end_to_end() -> dict:
    items = [json.loads(line) for line in (DATASETS / "intent_questions.jsonl").read_text().splitlines()]
    sessions = json.loads((DATASETS / "followup_sessions.json").read_text())
    runs = []
    for it in items:
        t0 = time.perf_counter()
        r = run_chat(it["question"])
        runs.append((it["question"], it["expected"], r, (time.perf_counter() - t0) * 1000, False))
    for s in sessions:
        sid = None
        for q, exp in s["session"]:
            t0 = time.perf_counter()
            r = run_chat(q, sid)
            sid = r["session_id"]
            runs.append((q, exp, r, (time.perf_counter() - t0) * 1000, True))
    checks = Counter()
    totals = Counter()
    failures = []
    for q, exp, r, ms, follow in runs:
        for c in r["quality_status"]["checks"]:
            totals[c["check"]] += 1
            checks[c["check"]] += c["passed"]
            if not c["passed"]:
                failures.append({"question": q, "check": c["check"], "detail": c["detail"]})
    unsupported = [(q, r) for q, exp, r, _, _ in runs if exp == "unsupported"]
    supported = [(q, exp, r) for q, exp, r, _, f in runs if exp != "unsupported"]
    follow = [(q, exp, r) for q, exp, r, _, f in runs if f]
    return {
        "requests": len(runs), "follow_up_requests": len(follow),
        "qa_pass_rate": round(sum(r["quality_status"]["status"] == "pass" for _, _, r, _, _ in runs) / len(runs), 4),
        "check_pass_rates": {k: round(checks[k] / totals[k], 4) for k in sorted(totals)},
        "unsupported_correctly_refused": f"{sum(r['status'] == 'unsupported' for _, r in unsupported)}/{len(unsupported)}",
        "supported_answered": f"{sum(r['status'] in ('completed', 'insufficient_data') for _, _, r in supported)}/{len(supported)}",
        "follow_up_routing_accuracy": round(sum(r["plan"]["category"] == exp for _, exp, r in follow) / len(follow), 4),
        "follow_up_errors": [{"question": q, "expected": exp, "got": r["plan"]["category"]} for q, exp, r in follow if r["plan"]["category"] != exp],
        "evidence_items_total": sum(len(r["evidence"]) for _, _, r, _, _ in runs),
        "latency_p50_ms": pctl([m for *_, m, _ in runs], 0.5), "latency_p95_ms": pctl([m for *_, m, _ in runs], 0.95),
        "llm_mode": Counter(r["model_metadata"]["mode"] for _, _, r, _, _ in runs),
        "qa_failures": failures[:20],
    }


def main() -> None:
    started = time.perf_counter()
    res = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "dataset": "cs_conversations.csv (Syncora sample, 3,000 conversations)",
           "model": get_llm().status()}
    print("1/5 oracle check…", flush=True)
    res["q1_oracle"] = eval_q1_oracle()
    print("2/5 intent…", flush=True)
    res["intent"] = eval_intent()
    print("3/5 labels…", flush=True)
    res["labels"] = eval_labels()
    print("4/5 retrieval…", flush=True)
    res["retrieval"] = eval_retrieval()
    print("5/5 end to end…", flush=True)
    res["end_to_end"] = eval_end_to_end()
    gem = res["intent"]["gemini"]
    res["prompt_evaluations"] = {
        "intent_understanding": gem if gem.get("status") != "not_run" else {"status": "not_run", "reason": gem.get("reason"),
                                                                             "rules_baseline_accuracy": res["intent"]["accuracy"]},
        "message_classification": res["labels"]["gemini_labels"],
        "grounded_explanation": {"status": "not_run" if not get_llm().available() else "see end_to_end",
                                 "numeric_grounding_check": "enforced on every model explanation (tests/integration/test_graph.py)"},
    }
    e, rt, it, q1 = res["end_to_end"], res["retrieval"], res["intent"], res["q1_oracle"]
    res["summary"] = [
        {"metric": "Q1 numbers vs independent oracle", "display": "match" if q1["top5_counts_match"] and q1["totals_match"] else "MISMATCH", "note": q1["month"]},
        {"metric": "Intent accuracy (rules, tuning set)", "display": f"{it['accuracy']:.0%}", "note": f"{it['n']} questions; parser was tuned on this set"},
        {"metric": "Intent accuracy (rules, held-out)", "display": f"{it['heldout']['accuracy']:.0%}",
         "note": f"{it['heldout']['n']} unseen paraphrases; {it['heldout']['safe_failures']} of {it['heldout']['n'] - round(it['heldout']['accuracy'] * it['heldout']['n'])} misses refused safely"},
        {"metric": "QA pass rate (end to end)", "display": f"{e['qa_pass_rate']:.0%}", "note": f"{e['requests']} requests"},
        {"metric": "Follow-up routing", "display": f"{e['follow_up_routing_accuracy']:.0%}", "note": f"{e['follow_up_requests']} follow-ups"},
        {"metric": "Unsupported refused", "display": e["unsupported_correctly_refused"], "note": "no fabricated answers"},
        {"metric": "Retrieval topic P@5", "display": f"{rt['topic_precision@5']:.0%}", "note": f"random baseline {rt['random_baseline_topic_precision']:.0%}"},
        {"metric": "Retrieval exact P@5", "display": f"{rt['exact_precision@5']:.0%}", "note": "topic + product"},
        {"metric": "Latency p50 / p95", "display": f"{e['latency_p50_ms']:.0f} / {e['latency_p95_ms']:.0f} ms", "note": "deterministic mode, local"},
    ]
    res["duration_seconds"] = round(time.perf_counter() - started, 1)
    s = get_settings()
    s.manifests_dir.mkdir(parents=True, exist_ok=True)
    (s.manifests_dir / "evaluation_results.json").write_text(json.dumps(res, indent=2, default=str))
    md = PROJECT_ROOT / "docs" / "evaluation" / "EVALUATION_RESULTS.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(render_markdown(res))
    print(json.dumps(res["summary"], indent=2))


def render_markdown(r: dict) -> str:
    e, rt, it, lb, q1 = r["end_to_end"], r["retrieval"], r["intent"], r["labels"], r["q1_oracle"]
    lines = [f"# Evaluation results (generated {r['generated_at']})", "",
             "Generated by `backend/scripts/evaluate.py` on the real dataset. Do not edit by hand.", "",
             f"Model status during the run: `{r['model'].get('mode')}` — {r['model'].get('reason') or 'available'}", "",
             "## Summary", "", "| Metric | Result | Note |", "|---|---|---|"]
    lines += [f"| {s['metric']} | {s['display']} | {s['note']} |" for s in r["summary"]]
    lines += ["", "## 1. Q1 numbers vs an independent oracle", "",
              f"An independent re-implementation reads the raw CSV, assigns topics with its own regexes and scores sentiment with its own table. Month: {q1['month']}.", "",
              f"* Totals (conversations, negative): system {q1['system_totals']} vs oracle {q1['oracle_totals']}",
              f"* Top-5 negative counts match: **{q1['top5_counts_match']}**", f"* System: `{q1['system_top5']}`", ""]
    lines += ["## 2. Intent classification (rules parser)", "", f"Accuracy **{it['accuracy']:.1%}**, macro-F1 {it['macro_f1']:.3f} on {it['n']} questions.", "",
              "| Intent | P | R | F1 | n |", "|---|---|---|---|---|"]
    lines += [f"| {c['label']} | {c['precision']} | {c['recall']} | {c['f1']} | {c['support']} |" for c in it["per_class"]]
    lines += ["", "Errors (tuning set):", ""] + [f"* “{x['question']}” → expected `{x['expected']}`, got `{x['predicted']}`" for x in it["errors"]] + [""]
    h = it["heldout"]
    lines += [f"### Held-out set: accuracy **{h['accuracy']:.0%}** on {h['n']} unseen paraphrases", "", h["note"],
              f"Misses: {h['safe_failures']} refused as unsupported (safe), {h['misrouted']} routed to a different analysis.", ""]
    lines += [f"* “{x['question']}” → expected `{x['expected']}`, got `{x['predicted']}`" for x in h["errors"]] + [""]
    lines += [f"Gemini intent evaluation: `{it['gemini']}`", ""]
    lf = lb["lexicon_fallback_vs_templates"]
    lines += ["## 3. Labelling", "", f"Template coverage of customer messages: `{lb['template_coverage']}`.", "",
              f"Lexicon fallback vs template labels ({lf['n_messages']} customer messages): accuracy {lf['accuracy']:.1%}, Cohen's κ {lf['cohen_kappa']}.", "",
              "| Class | P | R | F1 | n |", "|---|---|---|---|---|"]
    lines += [f"| {c['label']} | {c['precision']} | {c['recall']} | {c['f1']} | {c['support']} |" for c in lf["per_class"]]
    lines += ["", f"Human review: `{lb['human_review'].get('status')}` — {lb['human_review'].get('note', '')}", "",
              f"Gemini labels: `{lb['gemini_labels']}`", ""]
    lines += ["## 4. Retrieval", "", f"{rt['queries']} paraphrased queries. Default mode `{rt['default_mode']}` ({rt['embedding_backend']}; {rt.get('fusion') or 'single index'}).", "",
              "| Method | topic P@5 | exact P@5 | hit-rate@5 | MRR@5 | p50 ms |", "|---|---|---|---|---|---|"]
    lines += [f"| {m['mode']} | {m['topic_precision@5']:.1%} | {m['exact_precision@5']:.1%} | {m['hit_rate@5']:.1%} | {m['mrr@5']:.3f} | {m['latency_p50_ms']} |"
              for m in rt["by_mode"].values()]
    lines += ["", "Default mode details:", "",
              f"* Topic precision@5 **{rt['topic_precision@5']:.1%}** (random baseline {rt['random_baseline_topic_precision']:.1%})",
              f"* Exact (topic+product) precision@5 {rt['exact_precision@5']:.1%}; hit-rate@5 {rt['hit_rate@5']:.1%}; MRR@5 {rt['mrr@5']:.3f}",
              f"* Duplicate rate {rt['duplicate_rate']:.1%}; latency p50 {rt['latency_p50_ms']} ms, p95 {rt['latency_p95_ms']} ms", "",
              "| Topic | topic P@5 | exact P@5 |", "|---|---|---|"]
    lines += [f"| {x['topic']} | {x['topic_p@5']} | {x['exact_p@5']} |" for x in rt["by_topic"]]
    lines += ["", "## 5. End to end", "", f"* Requests: {e['requests']} ({e['follow_up_requests']} follow-ups)",
              f"* QA pass rate: **{e['qa_pass_rate']:.1%}**", f"* Unsupported questions refused: {e['unsupported_correctly_refused']}",
              f"* Supported questions answered: {e['supported_answered']}", f"* Follow-up routing accuracy: {e['follow_up_routing_accuracy']:.1%}",
              f"* Latency p50 {e['latency_p50_ms']} ms, p95 {e['latency_p95_ms']} ms", f"* Model mode counts: `{dict(e['llm_mode'])}`", "",
              "| QA check | pass rate |", "|---|---|"]
    lines += [f"| {k} | {v:.1%} |" for k, v in e["check_pass_rates"].items()]
    if e["qa_failures"]:
        lines += ["", "QA failures:", ""] + [f"* {f['question']} — {f['check']}: {f['detail']}" for f in e["qa_failures"]]
    if e["follow_up_errors"]:
        lines += ["", "Follow-up routing errors:", ""] + [f"* {f['question']} → expected `{f['expected']}`, got `{f['got']}`" for f in e["follow_up_errors"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
