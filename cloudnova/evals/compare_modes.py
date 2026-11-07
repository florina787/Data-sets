"""Hybrid vs Qwen-only (LLM text-to-SQL) on the six stakeholder questions.

    python -m evals.compare_modes

Correctness is judged against the independent oracle by looking for the expected values anywhere in the
returned result rows (Qwen chooses its own column names), so the check is lenient on shape and strict on numbers.
Writes evals/results/mode_comparison.{json,md}. Needs the local Qwen server.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.__main__ import STAKEHOLDER_QUESTIONS  # noqa: E402
from app.agent import supervisor  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.llm.provider import provider_status  # noqa: E402
from app.pipeline.build import build  # noqa: E402
from evals.oracle import expected  # noqa: E402


def _nums(rows):
    out = []
    for r in rows:
        for v in r:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out += [float(v), abs(float(v)), float(v) * 100]
    return out


def _has(rows, x, tol):
    return any(abs(n - x) <= tol for n in _nums(rows))


def judge(i: int, res: dict, o: dict) -> tuple[bool, str]:
    rows = (res or {}).get("rows") or []
    if not rows:
        return False, "no rows"
    flat = [str(v) for r in rows for v in r]
    if i == 1:
        ok = _has(rows, o["q1_paid_2024"], 0.01)
        return ok, "paid 2024 found" if ok else "paid 2024 value not in result"
    if i == 2:
        top = rows[0]
        ok = o["q2_region"] in [str(v) for v in top] and _has([top], o["q2_avg_mrr"], 0.01)
        return ok, "APAC + avg MRR correct" if ok else f"top row {top[:3]}"
    if i == 3:
        ok = _has(rows, abs(o["q3_refunds"]), 0.01)
        return ok, "refund total found" if ok else "refund total not in result"
    if i == 4:
        ok = _has(rows, o["q4_churn_enterprise"], 1e-4) and _has(rows, o["q4_churn_starter"], 1e-4)
        if not ok:  # accept percentages rounded to 2 dp
            ok = _has(rows, round(o["q4_churn_enterprise"] * 100, 2), 0.01) and _has(rows, round(o["q4_churn_starter"] * 100, 2), 0.01)
        return ok, "both churn rates found" if ok else "churn rates not in result"
    if i == 5:
        ids = o["q5_top5_ids"]
        got = [next((v for v in r if isinstance(v, str) and v.startswith("ACC-")), None) for r in rows[:5]]
        ok = got == ids
        return ok, "top-5 ids in order" if ok else f"got {got}"
    if i == 6:
        ok = _has(rows, o["q6_count"], 0) and _has(rows, o["q6_exposure"], 0.01)
        return ok, "count + exposure found" if ok else "count/exposure not in result"
    return False, "?"


def run_mode(mode: str, o: dict) -> list[dict]:
    os.environ["QUERY_MODE"] = mode
    get_settings.cache_clear()
    out = []
    for i, q in enumerate(STAKEHOLDER_QUESTIONS, 1):
        t0 = time.perf_counter()
        try:
            r = supervisor.ask(q, None)
            ok, why = judge(i, r.get("result"), o)
            out.append({"q": i, "mode": mode, "correct": ok, "why": why, "planner": r["planner"], "sql": r["sql"],
                        "ms": round((time.perf_counter() - t0) * 1000), "llm_ms": r["llm"]["latency_ms"]})
        except AppError as e:
            out.append({"q": i, "mode": mode, "correct": False, "why": f"{e.code}: {e.message[:120]}", "planner": "llm_sql",
                        "sql": (e.details.get("attempts") or [{}])[-1].get("sql"), "ms": round((time.perf_counter() - t0) * 1000), "llm_ms": None})
        print(f"  {mode:6} Q{i}: {'✓' if out[-1]['correct'] else '✗'} {out[-1]['ms']:>6} ms  {out[-1]['why']}", flush=True)
    return out


def main() -> int:
    build(quiet=True)
    st = provider_status()
    if not st["reachable"]:
        print("local Qwen is not reachable — start it first (see README).")
        return 2
    o = expected()
    results = run_mode("hybrid", o) + run_mode("llm", o)
    os.environ["QUERY_MODE"] = "hybrid"
    get_settings.cache_clear()
    summary = {}
    for mode in ("hybrid", "llm"):
        rs = [r for r in results if r["mode"] == mode]
        ms = sorted(r["ms"] for r in rs)
        summary[mode] = {"correct": sum(r["correct"] for r in rs), "total": len(rs), "median_ms": ms[len(ms) // 2], "max_ms": ms[-1]}
    meta = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": st["model"], "served": st["served_models"],
            "hardware": f"{platform.machine()} · {os.cpu_count()} CPU threads · CPU-only inference", "temperature": 0.0}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "mode_comparison.json").write_text(json.dumps({"meta": meta, "summary": summary, "results": results}, indent=2))
    lines = [f"# Hybrid vs Qwen-only on the six stakeholder questions", "",
             f"Measured {meta['run_at']} · model `{meta['model']}` · {meta['hardware']} · temperature 0 · "
             f"correctness judged against `evals/oracle.py`.", "",
             "| Mode | Correct | Median latency | Max latency |", "|---|---|---|---|"]
    for mode, s in summary.items():
        lines.append(f"| {mode} | {s['correct']}/{s['total']} | {s['median_ms']:,} ms | {s['max_ms']:,} ms |")
    lines += ["", "| Q | Hybrid | Qwen-only | Qwen-only detail |", "|---|---|---|---|"]
    for i in range(1, 7):
        h = next(r for r in results if r["mode"] == "hybrid" and r["q"] == i)
        l = next(r for r in results if r["mode"] == "llm" and r["q"] == i)
        lines.append(f"| Q{i} | {'✓' if h['correct'] else '✗'} {h['ms']} ms | {'✓' if l['correct'] else '✗'} {l['ms']:,} ms | {l['why']} |")
    lines += ["", "## SQL Qwen generated (Qwen-only mode)", ""]
    for r in results:
        if r["mode"] == "llm":
            lines += [f"**Q{r['q']}** — {'correct' if r['correct'] else 'WRONG: ' + r['why']}", "```sql", (r["sql"] or "(none)").strip(), "```", ""]
    (HERE / "results" / "mode_comparison.md").write_text("\n".join(lines))
    print("\n" + "\n".join(lines[:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
