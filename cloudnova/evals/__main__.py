"""Eval harness: `python -m evals [--llm] [--only ID_SUBSTR]`. Exit code 1 on any FAIL or unexpected XPASS."""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app import db  # noqa: E402
from app.agent import supervisor  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.llm.provider import provider_status, set_provider_override  # noqa: E402
from app.pipeline.build import build  # noqa: E402
from evals.oracle import expected as oracle_expected  # noqa: E402


class _DownProvider:
    name, model = "qwen", "offline-test"

    def complete(self, *a, **k):
        raise AppError("llm_unavailable", "simulated: local Qwen is down", 503)

    def ping(self):
        return {"reachable": False, "models": []}


def _resolve(v, ora):
    if isinstance(v, str) and v.startswith("oracle:"):
        return ora[v.split(":", 1)[1]]
    if isinstance(v, dict):
        return {k: _resolve(x, ora) for k, x in v.items()}
    if isinstance(v, list):
        return [_resolve(x, ora) for x in v]
    return v


def _col(res, name):
    cols = res["columns"]
    if "*" in name:
        hits = [i for i, c in enumerate(cols) if fnmatch.fnmatch(c.lower(), name.lower())]
        if not hits:
            raise AssertionError(f"no column matching {name} in {cols}")
        return hits[0]
    if name not in cols:
        raise AssertionError(f"column {name} not in {cols}")
    return cols.index(name)


def _row(res, where=None, any_true=None):
    rows = res["rows"]
    if where:
        idx = {k: _col(res, k) for k in where}
        rows = [r for r in rows if all(str(r[i]) == str(where[k]) for k, i in idx.items())]
    if any_true:
        rows = [r for r in rows if any(v is True or (isinstance(v, str) and any_true in v.lower()) for v in r)]
    if not rows:
        raise AssertionError(f"no row matching {where or any_true}")
    return rows[0]


def check(c: dict, resp: dict | None, err: AppError | None) -> str:
    t, exp = c["type"], c.get("expected")
    if t == "error":
        assert err is not None and err.code == exp, f"expected error {exp}, got {err.code if err else 'success'}"
        return f"error {exp}"
    if err is not None:
        raise AssertionError(f"unexpected error {err.code}: {err.message}")
    res = resp.get("result") or {"columns": [], "rows": []}
    if t == "number":
        r = _row(res, c.get("where"), c.get("where_any_true"))
        got = r[_col(res, c["column"])]
        tol = c.get("tol", 0)
        assert got is not None and abs(float(got) - float(exp)) <= tol, f"{c['column']}: expected {exp}, got {got}"
        return f"{c['column']}={got}"
    if t == "argmax":
        i, j = _col(res, c["column"]), _col(res, c["label"])
        best = max(res["rows"], key=lambda r: r[i] if r[i] is not None else float("-inf"))
        assert best[j] == exp, f"argmax {c['label']}: expected {exp}, got {best[j]}"
        return f"{c['label']}={best[j]}"
    if t in ("top_k", "top_names"):
        got = [r[_col(res, c["column"])] for r in res["rows"]][: len(exp)]
        assert got == exp, f"expected {exp}, got {got}"
        return f"{len(got)} ids match"
    if t == "flags":
        i, f = _col(res, c["id_column"]), _col(res, c["flag_column"])
        got = sorted(r[i] for r in res["rows"] if r[f])
        assert got == sorted(exp), f"flagged expected {exp}, got {got}"
        return f"flagged={got}"
    if t == "intent":
        assert resp["intent"] == exp, f"intent expected {exp}, got {resp['intent']}"
        return f"intent={exp}"
    if t == "planner":
        assert resp["planner"] == exp, f"planner expected {exp}, got {resp['planner']}"
        return f"planner={exp}"
    if t == "chart":
        assert resp.get("chart") and resp["chart"]["type"] == exp, f"chart expected {exp}, got {resp.get('chart')}"
        return f"chart={exp}"
    if t == "contains":
        assert exp in (resp.get(c["field"]) or ""), f"{c['field']} lacks {exp!r}"
        return f"{c['field']} contains {exp!r}"
    if t == "trace":
        assert any(s.get("status") == exp for s in resp["trace"]), f"no trace step with status {exp}"
        return f"trace {exp}"
    if t == "rows_min":
        assert len(res["rows"]) >= exp, f"expected ≥{exp} rows, got {len(res['rows'])}"
        return f"{len(res['rows'])} rows"
    raise AssertionError(f"unknown check type {t}")


def run_case(case: dict, ora: dict, sessions: dict) -> tuple[str, str, float]:
    t0 = time.perf_counter()
    if "rejected_sql" in case:
        try:
            db.run_query(case["rejected_sql"])
            return "FAIL", "query was NOT rejected", 0.0
        except AppError as e:
            ok = e.code == "sql_rejected"
            return ("PASS" if ok else "FAIL"), e.message, (time.perf_counter() - t0) * 1000
    details = []
    if case.get("question") is None:  # pure data checks
        for c in case["checks"]:
            got = db.internal_scalar(c["sql"])
            exp = _resolve(c["expected"], ora)
            if got != exp:
                return "FAIL", f"{c['sql']}: expected {exp}, got {got}", (time.perf_counter() - t0) * 1000
            details.append(f"{got}")
        return "PASS", "; ".join(details), (time.perf_counter() - t0) * 1000
    sid = sessions.setdefault(case["session"], supervisor.new_session()) if case.get("session") else supervisor.new_session()
    if case.get("llm_down"):
        set_provider_override(_DownProvider())
    resp, err = None, None
    try:
        resp = supervisor.ask(case["question"], sid)
    except AppError as e:
        err = e
    finally:
        set_provider_override(None)
    try:
        for c in case["checks"]:
            details.append(check(_resolve(c, ora), resp, err))
        return "PASS", "; ".join(details), (time.perf_counter() - t0) * 1000
    except AssertionError as e:
        return "FAIL", str(e), (time.perf_counter() - t0) * 1000


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals")
    ap.add_argument("--llm", action="store_true", help="include cases that need the local Qwen model")
    ap.add_argument("--only", help="run cases whose id contains this text")
    args = ap.parse_args(argv)
    build(quiet=True)
    cases = yaml.safe_load((HERE / "cases.yaml").read_text())
    ora = oracle_expected()
    llm_ok = provider_status()["reachable"]
    sessions: dict = {}
    results = []
    print(f"{'case':42} {'category':16} {'result':7} {'ms':>8}  detail")
    print("-" * 130)
    for case in cases:
        if args.only and args.only not in case["id"]:
            continue
        if case.get("llm") and not args.llm:
            status, detail, ms = "SKIP", "needs --llm", 0.0
        elif case.get("llm") and not llm_ok:
            status, detail, ms = "SKIP", "local Qwen not reachable", 0.0
        else:
            try:
                status, detail, ms = run_case(case, ora, sessions)
            except Exception as exc:  # a crashing case is a FAIL, not a crashed harness
                status, detail, ms = "FAIL", f"crashed: {type(exc).__name__}: {exc}", 0.0
            if case.get("xfail"):
                status = "XFAIL" if status == "FAIL" else "XPASS"
                detail = (detail + " | why: " + " ".join(case["xfail"].split())) if status == "XFAIL" else "unexpectedly passed — revisit the documented limitation"
        results.append({"id": case["id"], "category": case["category"], "status": status, "ms": round(ms, 1), "detail": detail})
        print(f"{case['id']:42} {case['category']:16} {status:7} {ms:8.0f}  {detail[:160]}")
    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "XFAIL", "XPASS", "SKIP")}
    print("-" * 130)
    print("  ".join(f"{k}={v}" for k, v in counts.items()) + f"   (LLM cases {'included' if args.llm else 'skipped'}; Qwen reachable={llm_ok})")
    out = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "llm_included": args.llm, "counts": counts, "results": results}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "latest.json").write_text(json.dumps(out, indent=2))
    return 1 if counts["FAIL"] or counts["XPASS"] else 0


if __name__ == "__main__":
    sys.exit(main())
