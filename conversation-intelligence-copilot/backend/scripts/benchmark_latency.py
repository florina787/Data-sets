"""End-to-end latency and correctness benchmark over the real HTTP API, per question category.

Each request is a fresh POST /api/chat with no session, so nothing is resolved from memory, and there is no
analytics result cache: every deterministic request routes, queries DuckDB, runs QA and governance from scratch.
The server is expected to be warm (started, indexes and model preloaded), which is what "warm deterministic
request" means. Model categories are run with the server's LLM response cache pointed at an empty file
(LLM_CACHE_PATH, passed here as --llm-cache-path and emptied before every run), so no model answer is replayed.

Correctness is checked against ground truth computed here with independent SQL on a read-only DuckDB connection,
not by trusting the app's own numbers.

Usage:
  uv run python -m scripts.benchmark_latency --base-url http://127.0.0.1:8000 --label after --runs 20
  uv run python -m scripts.benchmark_latency --label before --base-url http://127.0.0.1:8001 --slow-cap-s 300
Writes data/manifests/latency_benchmark_<label>.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import time
from pathlib import Path

import duckdb
import httpx

ROOT = Path(__file__).resolve().parents[2]

# Phrasings per category; runs cycle through them, so every category sees several wordings.
CATEGORIES: dict[str, dict] = {
    "greeting": {"mode": "auto", "questions": ["Hi", "Hello", "hey there", "How are you?", "Good morning", "thanks!", "What can you do?"]},
    "positive_statements": {"mode": "auto", "questions": ["What are the top 5 positive statements from users?",
                                                          "Show the top 5 positive statements customers made",
                                                          "What are the most common positive comments from customers?",
                                                          "List the top 3 positive customer statements"]},
    "negative_statements": {"mode": "auto", "questions": ["What are the top 5 negative statements from users?",
                                                          "Show the top 3 negative statements customers made",
                                                          "What are the most common negative comments from customers?",
                                                          "List the top 10 negative customer statements"]},
    "complaints": {"mode": "auto", "questions": ["What are the top complaints?", "What were the top 5 topics most associated with negative sentiment?",
                                                 "Which topics have the most negative conversations?", "What do customers complain about most?"]},
    "sentiment_percentages": {"mode": "auto", "questions": ["What is the overall sentiment mix?", "What percentage of conversations are negative?",
                                                            "Show the sentiment distribution across conversations",
                                                            "How many conversations are positive, neutral and negative?"]},
    "sentiment_trend": {"mode": "auto", "questions": ["Show the sentiment trend over time.", "Compare sentiment this month vs last month",
                                                      "How has negative sentiment changed month over month?", "What is the monthly sentiment trend?"]},
    "rankings": {"mode": "auto", "questions": ["Which recurring customer concerns should leadership review first?",
                                               "Which support agents may benefit from coaching on empathy?",
                                               "Rank the customer concerns leadership should prioritise",
                                               "Which agents need coaching on empathy?"]},
    "llm_explanation": {"mode": "hybrid_ai", "questions": ["Why is duplicate charge so negative?", "Why are coupon conversations so negative?",
                                                          "What is behind negative sentiment in refund conversations?",
                                                          "Why are customers unhappy about items not received?"]},
}
DETERMINISTIC = [c for c in CATEGORIES if c != "llm_explanation"]


def ground_truth(db_path: Path) -> dict:
    c = duckdb.connect(str(db_path), read_only=True)
    q = lambda sql, *a: c.execute(sql, list(a)).fetchall()  # noqa: E731
    base = "FROM messages m JOIN message_labels l USING (message_id) JOIN conversations c ON c.conversation_id = m.conversation_id " \
           "WHERE c.dataset_source = 'original' AND m.speaker_role = 'customer' AND l.sentiment = ?"
    statements = {pol: [r[0] for r in q(f"SELECT m.masked_text, COUNT(*) n {base} GROUP BY 1 ORDER BY n DESC, ROUND(AVG(l.sentiment_score), 3) "
                                         f"{'DESC' if pol == 'positive' else 'ASC'}, 1", pol)] for pol in ("positive", "negative")}
    counts = {pol: dict(q(f"SELECT m.masked_text, COUNT(*) {base} GROUP BY 1", pol)) for pol in ("positive", "negative")}
    conv = "FROM conversations WHERE dataset_source = 'original'"
    total, neg = q(f"SELECT COUNT(*), COUNT(*) FILTER (sentiment = 'negative') {conv}")[0]
    by_topic = {t: (n, ng) for t, n, ng in q(f"SELECT topic, COUNT(*), COUNT(*) FILTER (sentiment = 'negative') {conv} GROUP BY 1")}
    months = q(f"SELECT month, COUNT(*), COUNT(*) FILTER (sentiment = 'negative') {conv} GROUP BY 1 ORDER BY 1")
    emp = q(f"SELECT SUM(empathic_replies), SUM(negative_turns_with_reply) {conv}")[0]
    return {"statements": statements, "statement_counts": counts, "total": total, "negative": neg, "by_topic": by_topic,
            "months": [(str(m), n, ng) for m, n, ng in months], "empathy": (int(emp[0]), int(emp[1]))}


def _metric(r: dict, mid: str):
    return next((m for m in r.get("metrics", []) if m["id"] == mid), None)


def check(category: str, question: str, r: dict, gt: dict) -> list[str]:
    """Problems with the answer (empty when correct)."""
    p: list[str] = []
    if r.get("status") == "failed" or "request_id" not in r:
        return [f"request failed: {str(r)[:160]}"]
    cat = (r.get("resolved_intent") or {}).get("category")
    ops = [s["op"] for s in (r.get("plan") or {}).get("steps", [])]
    if (r.get("quality_status") or {}).get("status") == "fail":
        p.append("QA failed")
    if category == "greeting":
        if (r.get("routing") or {}).get("route") != "fast_path":
            p.append(f"not answered by the fast path (route {(r.get('routing') or {}).get('route')}, category {cat})")
        if r.get("token_usage", {}).get("model_calls"):
            p.append("model was called for small talk")
    elif category in ("positive_statements", "negative_statements"):
        pol = category.split("_")[0]
        if cat != "top_statements" or ops != ["top_statements"]:
            return p + [f"wrong analysis: category {cat}, operations {ops}"]
        want = int(next((w for w in question.split() if w.isdigit()), 5))
        truth = gt["statements"][pol][:want]
        got = [row["statement"] for row in r["rankings"]]
        if got != truth:
            p.append(f"statements differ from SQL ground truth: {got[:3]} vs {truth[:3]}")
        if any(int(row["mentions"]) != gt["statement_counts"][pol][row["statement"]] for row in r["rankings"]):
            p.append("mention counts differ from SQL")
        if len(truth) < want and f"Only {len(truth)}" not in r["headline"]:
            p.append("shortfall not stated in the headline")
        if any(s not in r["answer"] for s in got):
            p.append("a statement is missing from the answer text")
    elif category == "complaints":
        if not ops or ops[0] != "rank_negative_topics":
            return p + [f"wrong analysis: category {cat}, operations {ops}"]
        rows = r["rankings"]
        for row in rows:
            n, ng = gt["by_topic"][row["key"]]
            if int(row["conversations"]) != n or int(row["negative"]) != ng:
                p.append(f"{row['key']}: {row['conversations']}/{row['negative']} vs SQL {n}/{ng}")
        if [row["negative"] for row in rows] != sorted((row["negative"] for row in rows), reverse=True):
            p.append("ranking not ordered by negative conversations")
    elif category == "sentiment_percentages":
        m = _metric(r, "negative_rate_overall")
        if not ops or ops[0] != "sentiment_distribution" or m is None:
            return p + [f"wrong analysis: category {cat}, operations {ops}"]
        if (m["numerator"], m["denominator"]) != (gt["negative"], gt["total"]):
            p.append(f"negative {m['numerator']}/{m['denominator']} vs SQL {gt['negative']}/{gt['total']}")
        if f"{gt['negative'] / gt['total']:.1%}" not in r["headline"] + r["answer"]:
            p.append("negative percentage not stated")
    elif category == "sentiment_trend":
        if not ops or ops[0] != "sentiment_trend":
            return p + [f"wrong analysis: category {cat}, operations {ops}"]
        month, n, ng = gt["months"][-1]
        m = _metric(r, "latest_negative_rate")
        if m is None or (m["numerator"], m["denominator"]) != (ng, n):
            p.append(f"latest month {month}: {m and (m['numerator'], m['denominator'])} vs SQL {(ng, n)}")
        if month not in r["headline"]:
            p.append("latest month not in the headline")
    elif category == "rankings":
        if "leadership" in question.lower() or "concern" in question.lower():
            if not ops or ops[0] != "leadership_priorities":
                return p + [f"wrong analysis: category {cat}, operations {ops}"]
            rows = r["rankings"]
            if [x["priority_score"] for x in rows] != sorted((x["priority_score"] for x in rows), reverse=True):
                p.append("priorities not ordered by score")
            if any(int(x["conversations"]) != gt["by_topic"][x["key"]][0] for x in rows):
                p.append("concern volumes differ from SQL")
        else:
            m = _metric(r, "empathy_response_rate")
            if not ops or ops[0] != "agent_coaching_review" or m is None:
                return p + [f"wrong analysis: category {cat}, operations {ops}"]
            if (m["numerator"], m["denominator"]) != gt["empathy"]:
                p.append(f"empathy {m['numerator']}/{m['denominator']} vs SQL {gt['empathy']}")
    elif category == "llm_explanation":
        if not ops or ops[0] != "root_cause_investigation":
            p.append(f"wrong analysis: category {cat}, operations {ops}")
        if not r.get("evidence"):
            p.append("no evidence attached")
    return p


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--label", required=True)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--categories", default=",".join(CATEGORIES))
    ap.add_argument("--llm-cache-path", type=Path, help="the server's LLM_CACHE_PATH; emptied before every run so no model answer is replayed")
    ap.add_argument("--slow-cap-s", type=float, default=0, help="stop a category early once its runs have taken this long (reported)")
    args = ap.parse_args()

    gt = ground_truth(ROOT / "data" / "processed" / "analytics.duckdb")
    client = httpx.Client(base_url=args.base_url, timeout=600)
    health = client.get("/health").json()
    out: dict = {"label": args.label, "base_url": args.base_url, "runs_per_category": args.runs, "health": health, "categories": {},
                 "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for name in args.categories.split(","):
        spec = CATEGORIES[name]
        runs, started = [], time.perf_counter()
        for i in range(args.runs):
            q = spec["questions"][i % len(spec["questions"])]
            if args.llm_cache_path and args.llm_cache_path.exists():
                with sqlite3.connect(args.llm_cache_path) as con:
                    con.execute("DELETE FROM responses")
            t0 = time.perf_counter()
            r = client.post("/api/chat", json={"question": q, "analysis_mode": spec["mode"]}).json()
            wall = (time.perf_counter() - t0) * 1000
            problems = check(name, q, r, gt)
            runs.append({"question": q, "wall_ms": round(wall, 1), "server_ms": r.get("latency_ms"), "correct": not problems, "problems": problems,
                         "route": (r.get("routing") or {}).get("route"), "category": (r.get("resolved_intent") or {}).get("category"),
                         "model_calls": (r.get("token_usage") or {}).get("model_calls"),
                         "explanation_source": (r.get("model_metadata") or {}).get("explanation_source"),
                         "qa": (r.get("quality_status") or {}).get("status"), "headline": r.get("headline", "")[:200]})
            print(f"{name:22s} {i + 1:2d} {wall:9.1f} ms {'ok ' if not problems else 'BAD'} {q[:60]}" + (f"  {problems[:2]}" if problems else ""), flush=True)
            if args.slow_cap_s and time.perf_counter() - started > args.slow_cap_s:
                print(f"{name}: stopped after {len(runs)} runs (cap {args.slow_cap_s:g}s)")
                break
        walls = [x["wall_ms"] for x in runs]
        out["categories"][name] = {
            "n": len(runs), "p50_ms": pct(walls, 0.5), "p95_ms": pct(walls, 0.95), "max_ms": max(walls), "mean_ms": round(statistics.mean(walls), 1),
            "correct": sum(x["correct"] for x in runs), "failures": len(runs) - sum(x["correct"] for x in runs),
            "model_calls": sum(x["model_calls"] or 0 for x in runs), "runs": runs}
    det = [x["wall_ms"] for n in out["categories"] if n in DETERMINISTIC for x in out["categories"][n]["runs"]]
    if det:
        out["deterministic_overall"] = {"n": len(det), "p50_ms": pct(det, 0.5), "p95_ms": pct(det, 0.95), "max_ms": max(det)}
    path = ROOT / "data" / "manifests" / f"latency_benchmark_{args.label}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print("\n" + f"{'category':22s} {'n':>3s} {'p50 ms':>9s} {'p95 ms':>9s} {'correct':>8s}")
    for n, c in out["categories"].items():
        print(f"{n:22s} {c['n']:3d} {c['p50_ms']:9.1f} {c['p95_ms']:9.1f} {c['correct']:4d}/{c['n']}")
    if det:
        print(f"deterministic overall: n={len(det)} p50 {out['deterministic_overall']['p50_ms']} ms, p95 {out['deterministic_overall']['p95_ms']} ms")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
