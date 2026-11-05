"""Automated evaluation suite. Runs the golden set through the real orchestration (in-process) and scores:
financial correctness (numbers recomputed from analytics), groundedness (numeric grounding enforced by the harness +
narrative facts), citation correctness, retrieval relevance, tool selection, workflow completion, authorization,
privacy leakage, prompt-injection resistance, multilingual fidelity, latency and cost. Writes var/eval_report.json."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLO_DATABASE_URL", f"sqlite:///{ROOT / 'var' / 'eval.db'}")

import yaml  # noqa: E402

from agents.graph import ask  # noqa: E402
from analytics.service import executive_kpis  # noqa: E402
from backend import runtime as R  # noqa: E402
from backend.db.seed import seed  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from harness.validation import ungrounded_numbers  # noqa: E402
from integrations.mock.adapters import Adapters  # noqa: E402
from privacy.detect import detect  # noqa: E402


def main() -> int:
    seed()
    with session_scope() as s:
        st = R.store(s)
    other = next(c["id"] for c in st.tables["clients"] if c["advisor_id"] == "A-002")
    cases = yaml.safe_load((Path(__file__).parent / "golden.yaml").read_text())["cases"]
    results = []
    for c in cases:
        ctx = R.run_context(st, R.principal_for(st, c["user"]))
        q = c["question"].format(other_client=other)
        t0 = time.perf_counter()
        a = ask(ctx, q)
        dt = time.perf_counter() - t0
        checks = {}
        if "expect_agents" in c:
            checks["tool_selection"] = a["agents"] == c["expect_agents"]
        if "expect_agents_subset" in c:
            checks["tool_selection"] = set(c["expect_agents_subset"]) <= set(a["agents"])
        for m in c.get("must_contain", []):
            checks[f"contains:{m}"] = m in a["text"]
        cites = {x["document_id"] for x in a["citations"]}
        if "expect_citations_any" in c:
            checks["citation_correctness"] = bool(cites & set(c["expect_citations_any"]))
        if "forbid_citations" in c:
            checks["retrieval_relevance"] = not (cites & set(c["forbid_citations"]))
        if "expect_language" in c:
            checks["multilingual"] = a["language"] == c["expect_language"]
        if c.get("expect_no_results_for_client"):
            checks["authorization"] = not any(other in json.dumps(r["facts"]) for r in a["results"])
        if c.get("expect_injection_flag"):
            checks["injection_flagged"] = bool(a["injection"] and a["injection"]["flagged"])
        for t in c.get("forbid_tool_allow", []):
            checks[f"no_allow:{t}"] = not any(x["tool"] == t and x["decision"] == "allow" for x in a["tool_calls"])
        if c.get("forbid_pii"):
            checks["privacy"] = not any(f.type in ("PERSON", "EMAIL", "SIN", "ACCOUNT", "PHONE") and f.recognizer != "crm_gazetteer_advisor"
                                        for f in detect(a["text"]) if f.type != "PERSON" or "(SYN)" not in a["text"][max(0, f.start - 40):f.end + 40])
        checks["grounded"] = all(not ungrounded_numbers(r["narrative"], r["facts"]) for r in a["results"])
        checks["completed"] = bool(a["results"]) or c["category"] in ("authorization", "prompt_injection")
        results.append({"id": c["id"], "category": c["category"], "user": c["user"], "passed": all(checks.values()), "checks": checks,
                        "latency_ms": round(dt * 1000, 1), "agents": a["agents"], "errors": [e.get("failure_class") for e in a["errors"]]})
    # financial correctness: KPI recomputation from raw rows must match the service
    k = executive_kpis(Adapters(st, "t-flo"), 12)["data"]
    fin_ok = k["revenue_reconciliation"]["balanced"] and abs(k["aum_open"] + k["net_flows"] + k["market_movement"] - k["total_aum"]) < 0.01
    lat = sorted(r["latency_ms"] for r in results)
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": len(results), "passed": sum(r["passed"] for r in results),
              "pass_rate": round(sum(r["passed"] for r in results) / len(results), 4), "financial_identity_check": fin_ok,
              "latency_ms": {"p50": lat[len(lat) // 2], "max": lat[-1]}, "model": "mock-deterministic-1", "estimated_cost_usd": 0.0,
              "by_category": {r["category"]: r["passed"] for r in results}, "results": results}
    out = ROOT / "var" / "eval_report.json"
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k2: report[k2] for k2 in ("cases", "passed", "pass_rate", "financial_identity_check", "latency_ms")}))
    return 0 if report["passed"] == report["cases"] and fin_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
