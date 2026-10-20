"""Evaluation runner.

    python -m app.evaluation.run --suite all --system rules            # demonstration (rules) system, synthetic fixtures
    python -m app.evaluation.run --suite all --system llm --dataset <imported dataset id> [--langsmith]

Judgment types are kept separate: ``deterministic`` (exact checks against reference labels or recomputed values),
``human`` (reviewer confirmations/corrections), ``llm_judge`` (model-graded, never presented as ground truth).
Results are reported per language with sample sizes; languages without reference examples are listed as unevaluated.
"""
from __future__ import annotations

import argparse
import csv
import json
import secrets
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select

from app.analytics.rules import Msg, analyze
from app.config import get_settings
from app.db import init_db, session_scope
from app.ingestion.bootstrap import ensure_demo_datasets
from app.models.orm import Action, Analysis, Conversation, Correction, Dataset, EvalRun, Message
from app.multilingual.language import detect_language
from app.security.redaction import redact

HERE = Path(__file__).resolve().parent / "datasets"
SUITES = ["topic_classification", "resolution_extraction", "language_id", "retrieval_relevance", "numerical_correctness",
          "citation_validity", "unsupported_handling", "tool_selection", "prompt_injection", "reviewer_agreement"]


def _jsonl(name: str) -> list[dict]:
    return [json.loads(l) for l in (HERE / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def _record(suite: str, judgment: str, mode: str, system: str, language: str, results: list[bool], details: dict,
            experiment: str | None = None) -> dict:
    n, passed = len(results), sum(results)
    with session_scope() as db:
        db.add(EvalRun(suite=suite, judgment=judgment, mode=mode, system=system, language=language, n=n, passed=passed,
                       score=round(passed / n, 4) if n else None, details=details, langsmith_experiment=experiment))
    return {"suite": suite, "language": language, "n": n, "passed": passed, "score": round(passed / n, 4) if n else None}


def _multilingual_examples() -> list[dict]:
    s = get_settings()
    ref = json.loads((s.demo_data_dir / "multilingual_reference.json").read_text(encoding="utf-8"))
    rows = {r["tweet_id"]: r for r in csv.DictReader(open(s.demo_data_dir / "multilingual_scenarios.csv", encoding="utf-8"))}
    out = []
    for c in ref["conversations"]:
        if c["replica"] != 0:
            continue  # replicas share text; evaluate each scenario once
        msgs = []
        for mid in c["message_ids"]:
            text, _ = redact(rows[mid]["text"])
            msgs.append({"id": mid, "role": ref["messages"][mid]["role"], "text": text, "gold_language": ref["messages"][mid]["language"]})
        out.append({"id": c["root_id"], "language": c["scenario_language"], "messages": msgs,
                    "gold": {"primary_topic": c["primary_topic"], "resolution_status": c["resolution_status"]}})
    return out


def _predict(ex: dict, system: str, model) -> dict:
    if system.startswith("rules"):
        msgs = [Msg(m["id"], m["role"], m["text"], detect_language(m["text"])["language"]) for m in ex["messages"]]
        return analyze(msgs)
    from app.analytics.extractor import extract_messages
    return extract_messages(ex["messages"], model)


def label_suites(system: str, mode: str, model, langsmith: bool) -> list[dict]:
    examples = [dict(e, source="english_reference") for e in _jsonl("labelled_conversations.jsonl")] + \
               [dict(e, source="synthetic_multilingual_reference") for e in _multilingual_examples()]
    per = {"topic_classification": defaultdict(list), "resolution_extraction": defaultdict(list)}
    detail = {"topic_classification": [], "resolution_extraction": []}
    for ex in examples:
        try:
            pred = _predict(ex, system, model)
            err = None
        except Exception as exc:
            pred, err = {}, f"{type(exc).__name__}: {exc}"[:300]
        for suite, field in (("topic_classification", "primary_topic"), ("resolution_extraction", "resolution_status")):
            ok = pred.get(field) == ex["gold"][field]
            per[suite][ex["language"]].append(ok)
            detail[suite].append({"id": ex["id"], "language": ex["language"], "gold": ex["gold"][field], "pred": pred.get(field), "error": err})
    out = []
    experiment = None
    if langsmith:
        experiment = _langsmith_label_experiment(examples, system, model)
    for suite, by_lang in per.items():
        for lang, res in sorted(by_lang.items()):
            out.append(_record(suite, "deterministic", mode, system, lang, res,
                               {"examples": [d for d in detail[suite] if d["language"] == lang]}, experiment))
    return out


def _langsmith_label_experiment(examples: list[dict], system: str, model) -> str | None:
    from app.observability.tracing import client
    c = client()
    if c is None:
        print("LangSmith not configured; skipping experiment upload.")
        return None
    from langsmith import evaluate
    name = "convolens-labelled-conversations-v1"
    if not c.has_dataset(dataset_name=name):
        ds = c.create_dataset(name, description="Reference-labelled conversations (synthetic fixtures; redacted).")
        c.create_examples(dataset_id=ds.id, inputs=[{"messages": e["messages"], "language": e["language"]} for e in examples],
                          outputs=[e["gold"] for e in examples])

    def target(inputs: dict) -> dict:
        p = _predict({"messages": inputs["messages"]}, system, model)
        return {"primary_topic": p.get("primary_topic"), "resolution_status": p.get("resolution_status")}

    def topic_exact(outputs: dict, reference_outputs: dict) -> bool:
        return outputs.get("primary_topic") == reference_outputs.get("primary_topic")

    def resolution_exact(outputs: dict, reference_outputs: dict) -> bool:
        return outputs.get("resolution_status") == reference_outputs.get("resolution_status")

    res = evaluate(target, data=name, evaluators=[topic_exact, resolution_exact], experiment_prefix=f"convolens-{system}", client=c)
    return getattr(res, "experiment_name", None)


def language_suite(mode: str) -> list[dict]:
    by = defaultdict(list)
    details = defaultdict(list)
    for ex in _multilingual_examples():
        for m in ex["messages"]:
            pred = detect_language(m["text"])["language"]
            by[m["gold_language"]].append(pred == m["gold_language"])
            details[m["gold_language"]].append({"id": m["id"], "gold": m["gold_language"], "pred": pred})
    return [_record("language_id", "deterministic", mode, "lingua+rules", lang, res, {"examples": details[lang]})
            for lang, res in sorted(by.items())]


def retrieval_suite(mode: str, dataset_id: str, ml_dataset_id: str | None) -> list[dict]:
    from app.models.schemas import Filters
    from app.retrieval.index import search, semantic_status
    out = []
    with session_scope() as db:
        for ds_id, items, src in ((dataset_id, _jsonl("retrieval.jsonl"), "english"),
                                  (ml_dataset_id, None, "multilingual")):
            if not ds_id:
                continue
            if items is None:
                ref = json.loads((get_settings().demo_data_dir / "multilingual_reference.json").read_text(encoding="utf-8"))
                items = [dict(q, language="multi") for q in ref["retrieval_questions"]]
                gold = {c["root_id"]: c for c in ref["conversations"]}
            by_lang = defaultdict(list)
            det = []
            for q in items:
                r = search(db, ds_id, q["query"], Filters(), k=5)
                for h in r["hits"]:
                    conv = db.scalar(select(Conversation).where(Conversation.dataset_id == ds_id, Conversation.key == h["conversation_key"]))
                    if src == "multilingual":
                        g = gold.get(conv.root_source_id)
                        rel = bool(g and g["primary_topic"] == q["relevant_topic"])
                        lang = g["scenario_language"] if g else "unknown"
                    else:
                        rel = conv.primary_topic == q["relevant_topic"]
                        lang = h["language"]
                    by_lang[lang].append(rel)
                    det.append({"query": q["id"], "hit": h["evidence_id"], "language": lang, "relevant": rel})
            sem = semantic_status()
            system = "hybrid(bm25+" + ("faiss:" + str(sem.get("model")) if sem.get("available") else "no-semantic") + ")"
            for lang, res in sorted(by_lang.items()):
                out.append(_record("retrieval_relevance", "deterministic", mode, system, lang, res,
                                   {"metric": "precision@5 (relevance = hit conversation's reference/effective topic)",
                                    "source": src, "hits": [d for d in det if d["language"] == lang]}))
    return out


def flo_suites(mode: str, dataset_id: str) -> list[dict]:
    from app.graph.runner import get_runner
    from app.tools.catalog import resolve_evidence
    runner = get_runner()
    session = "ses_eval_" + secrets.token_hex(4)
    res = defaultdict(list)
    det = defaultdict(list)
    cite_lang = defaultdict(list)
    for q in _jsonl("flo_questions.jsonl"):
        evs = list(runner.start(session_id=session, question=q["question"], dataset_id=dataset_id, mode=mode, page="evaluation", filters=q["filters"]))
        ans = evs[-1]
        resp = ans.get("response") or {}
        tools = [e["tool"] for e in evs if e.get("type") == "tool" and e.get("status") == "ok"]
        if q["expect"].get("unsupported"):
            ok = resp.get("kind") == "unsupported" and not tools
            res["unsupported_handling"].append(ok)
            det["unsupported_handling"].append({"id": q["id"], "kind": resp.get("kind"), "tools": tools, "passed": ok})
            continue
        ok = set(q["expect"]["tools_all"]) <= set(tools)
        if q["expect"].get("scope_topics"):
            ok = ok and (resp.get("scope", {}).get("filters", {}).get("topics") == q["expect"]["scope_topics"])
        res["tool_selection"].append(ok)
        det["tool_selection"].append({"id": q["id"], "expected": q["expect"]["tools_all"], "executed": tools, "passed": ok})
        # Numerical correctness: every metric numerator must equal a fresh SQL recount for its tool/scope,
        # and the composed text must only use validated numbers.
        from app.graph.nodes import check_numbers
        bad = check_numbers(resp.get("text", ""), resp.get("metrics", []), q["question"],
                            [e.get("quote", "") for e in resp.get("evidence", [])] + resp.get("limitations", []) + resp.get("scope", {}).get("notes", []))
        res["numerical_correctness"].append(not bad and resp.get("validation", {}).get("status") in ("passed", "not_applicable"))
        det["numerical_correctness"].append({"id": q["id"], "unverified_numbers": bad, "validation": resp.get("validation")})
        with session_scope() as db:
            ev = resp.get("evidence", [])
            if ev:
                r = resolve_evidence(db, dataset_id, [e["id"] for e in ev])
                for item, e in zip(r["items"], ev):
                    ok_c = item["valid"] and item["quote"] == e["quote"]
                    cite_lang[e.get("language", "unknown")].append(ok_c)
    out = [_record(s, "deterministic", mode, "rules:flo-demo" if mode == "demo" else "llm:flo", "all", r, {"cases": det[s]})
           for s, r in res.items()]
    out += [_record("citation_validity", "deterministic", mode, "rules:flo-demo" if mode == "demo" else "llm:flo", lang, r,
                    {"check": "evidence id resolves and quote equals stored redacted span"}) for lang, r in sorted(cite_lang.items())]
    # Prompt injection
    inj = []
    inj_det = []
    with session_scope() as db:
        before = db.scalar(select(func.count(Action.id))) or 0
    for case in _jsonl("injection.jsonl"):
        evs = list(runner.start(session_id=session, question=case["question"], dataset_id=dataset_id, mode=mode, page="evaluation", filters=case["filters"]))
        resp = evs[-1].get("response") or {}
        text = (resp.get("text") or "").lower()
        proposed = any(e.get("type") == "approval_required" for e in evs)
        leaked = [t for t in case["forbidden_text"] if t.lower() in text and t.lower() not in "".join(e.get("quote", "").lower() for e in resp.get("evidence", []))]
        ok = not proposed and not leaked
        inj.append(ok)
        inj_det.append({"id": case["id"], "proposed_action": proposed, "forbidden_text_outside_quotes": leaked, "passed": ok})
    with session_scope() as db:
        after = db.scalar(select(func.count(Action.id))) or 0
    inj.append(after == before)
    inj_det.append({"id": "no_actions_persisted", "passed": after == before})
    out.append(_record("prompt_injection", "deterministic", mode, "rules:flo-demo" if mode == "demo" else "llm:flo", "all", inj, {"cases": inj_det}))
    return out


def reviewer_agreement(mode: str, dataset_id: str) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(Correction).where(Correction.dataset_id == dataset_id, Correction.target_type == "conversation")).all()
        if not rows:
            return []
        res = [c.original_value == c.corrected_value for c in rows]
        return [_record("reviewer_agreement", "human", mode, db.get(Dataset, dataset_id).active_analysis, "all", res,
                        {"definition": "share of reviewed labels the reviewer confirmed unchanged", "reviews": len(res)})]


def unevaluated_languages(dataset_id: str, evaluated: set[str]) -> list[str]:
    with session_scope() as db:
        langs = db.scalars(select(Message.language).where(Message.dataset_id == dataset_id).distinct()).all()
    return sorted(set(langs) - evaluated - {"unknown"})


def run(suites: list[str], system: str, dataset_id: str | None, langsmith: bool) -> dict:
    init_db()
    demo = ensure_demo_datasets()
    mode = "demo" if system == "rules" else "connected"
    model = None
    if system == "llm":
        from app.llm.provider import get_chat_model
        model = get_chat_model()
    target = dataset_id or demo.get("demo")
    with session_scope() as db:
        ds = db.get(Dataset, target)
        if ds is None:
            raise SystemExit(f"Dataset {target} not found")
        if mode == "demo" and not ds.synthetic:
            raise SystemExit("--system rules runs against synthetic demonstration data; use --system llm for imported data")
    sys_name = "rules:rules-v1" if system == "rules" else "llm"
    results = []
    if {"topic_classification", "resolution_extraction"} & set(suites):
        results += label_suites(sys_name, mode, model, langsmith)
    if "language_id" in suites:
        results += language_suite(mode)
    if "retrieval_relevance" in suites:
        results += retrieval_suite(mode, target, demo.get("multilingual") if mode == "demo" else None)
    if {"numerical_correctness", "citation_validity", "unsupported_handling", "tool_selection", "prompt_injection"} & set(suites):
        results += flo_suites(mode, target)
    if "reviewer_agreement" in suites:
        results += reviewer_agreement(mode, target)
    evaluated = {r["language"] for r in results}
    return {"system": sys_name, "dataset": target, "results": results,
            "unevaluated_languages": unevaluated_languages(target, evaluated)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suite", default="all", help="all or comma-separated: " + ", ".join(SUITES))
    p.add_argument("--system", choices=["rules", "llm"], default="rules")
    p.add_argument("--dataset", default=None, help="dataset id (default: demonstration fixtures)")
    p.add_argument("--langsmith", action="store_true", help="also upload the labelled dataset and run a LangSmith experiment")
    a = p.parse_args()
    suites = SUITES if a.suite == "all" else a.suite.split(",")
    out = run(suites, a.system, a.dataset, a.langsmith)
    print(f"System: {out['system']}  dataset: {out['dataset']}")
    print(f"{'suite':26} {'language':10} {'n':>4} {'passed':>6} {'score':>6}")
    for r in out["results"]:
        print(f"{r['suite']:26} {r['language']:10} {r['n']:>4} {r['passed']:>6} {r['score'] if r['score'] is not None else '-':>6}")
    print("Unevaluated languages present in dataset:", ", ".join(out["unevaluated_languages"]) or "none")


if __name__ == "__main__":
    main()
