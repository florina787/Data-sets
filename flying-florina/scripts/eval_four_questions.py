"""Four-question evaluation harness. Reports measured results only.

Usage (from the repository root):
    backend/.venv/bin/python scripts/eval_four_questions.py                 # held-out TEST split, uses local Qwen if found
    backend/.venv/bin/python scripts/eval_four_questions.py --split dev
    backend/.venv/bin/python scripts/eval_four_questions.py --no-qwen       # rules + semantic only

Metrics:
  routing accuracy, macro-F1        label predicted by the hybrid router vs gold label
  workflow correctness              four-family items: routed graph ran to completed/awaiting_approval with the expected blocks
  evidence accuracy                 cited documents exist, revision matches the database, and are permitted for the persona
  unsupported claim rate            Evidence Challenger unsupported items / items checked (only when Qwen answered)
  answer completeness               required sections present per family (answer, chart, evidence, next steps, limitations)
  latency                           p50 / p95 wall time per item (routing + workflow + explanation)
  governance enforcement            injection/export items denied, export tool executions unchanged, approvals still pending
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
sys.path.insert(0, str(ROOT / "backend"))

REQUIRED = {"diagnostics": {"answer", "chart", "evidence", "next", "limits"}, "recovery": {"answer", "chart", "evidence", "next", "limits", "approval"},
            "modernization": {"answer", "graph", "evidence", "next", "limits"}, "executive": {"answer", "chart", "evidence", "next", "limits"}}


def sections(ws: list[dict]) -> set[str]:
    have = set()
    for b in ws:
        t = b["type"]
        if t in ("answer", "qwen_answer"):
            have.add("answer")
        if t == "chart":
            have.add("chart")
        if t == "graph":
            have.add("graph")
        if t in ("citations", "table", "recommendations"):
            have.add("evidence")
        if t in ("actions", "roadmap") or (t == "qwen_answer" and b.get("recommended_next_steps")):
            have.add("next")
        if t in ("assumptions", "warnings", "formulas") or (t == "qwen_answer" and b.get("limitations")) or t == "qwen_status":
            have.add("limits")
        if t == "approval":
            have.add("approval")
    return have


def pct(v: list[float], p: float) -> float | None:
    if not v:
        return None
    v = sorted(v)
    return round(v[min(len(v) - 1, round(p * (len(v) - 1)))], 1)


def macro_f1(pairs: list[tuple[str, str]]) -> tuple[float, dict[str, dict[str, float]]]:
    labels = sorted({g for g, _ in pairs} | {p for _, p in pairs})
    per = {}
    for lab in labels:
        tp = sum(1 for g, p in pairs if g == lab and p == lab)
        fp = sum(1 for g, p in pairs if g != lab and p == lab)
        fn = sum(1 for g, p in pairs if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[lab] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "support": sum(1 for g, _ in pairs if g == lab)}
    gold = [lab for lab in labels if per[lab]["support"]]
    return round(sum(per[lab]["f1"] for lab in gold) / len(gold), 3), per


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["test", "test_v2", "dev"])
    ap.add_argument("--no-qwen", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "docs" / "eval"))
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="ff-eval-")
    os.environ.update({"FF_DATA_DIR": tmp, "FF_GENERATED_DIR": tmp + "/gen", "DEMO_MODE": "true", "OFFLINE_MODE": "true"})
    if args.no_qwen:
        os.environ["LLM_ENABLED"] = "false"
    from app.core import db
    from app.core.security import load_actor
    from app.llm.gateway import gateway
    from app.seed.generator import reset_database
    from app.workflows import orchestrator
    from app.workflows.router import FAMILIES

    reset_database()
    g = gateway()
    qwen = {"available": g.available(), **{k: g.discovery.as_dict().get(k) for k in ("model", "runtime", "quantization", "reason")}}
    data = json.loads((ROOT / "fixtures" / "eval" / f"four_questions_{args.split}.json").read_text())
    actor = load_actor("planner.marco")
    export_before = db.query_one("SELECT COUNT(*) n FROM tool_invocations WHERE tool='records.export_email' AND status='ok'")["n"]

    pairs, rows, lat = [], [], []
    wf_ok = wf_n = 0
    cited = cited_ok = 0
    claims = unsupported = 0
    complete_scores = []
    gov_n = gov_ok = 0
    by_method = Counter()
    for it in data["items"]:
        t0 = time.perf_counter()
        s = orchestrator.start(actor, it["query"], options={} if not args.no_qwen else {"rules_only": True})
        ms = (time.perf_counter() - t0) * 1000
        lat.append(ms)
        pred = s.route.get("label")
        pairs.append((it["label"], pred))
        by_method[s.route.get("method")] += 1
        row = {"id": it["id"], "kind": it["kind"], "query": it["query"], "gold": it["label"], "pred": pred, "method": s.route.get("method"),
               "workflow": s.workflow, "status": s.status, "ms": round(ms, 1)}
        if it["label"] in FAMILIES:
            wf_n += 1
            have = sections(s.workspace)
            need = REQUIRED[it["label"]]
            ok = pred == it["label"] and s.status in ("completed", "awaiting_approval") and not s.errors
            wf_ok += ok
            complete_scores.append(len(need & have) / len(need))
            row.update(workflow_ok=ok, missing_sections=sorted(need - have))
            for d in s.retrieved_docs:
                cited += 1
                ref = db.query_one("SELECT revision, classification, permitted_roles FROM documents WHERE id = ?", (d["doc_id"],))
                roles = json.loads(ref["permitted_roles"]) if ref else []
                if ref and ref["revision"] == d["revision"] and ("*" in roles or actor.role in roles):
                    cited_ok += 1
            for b in s.workspace:
                if b["type"] == "qwen_answer" or (b["type"] == "qwen_status" and b.get("challenger")):
                    ch = b.get("challenger", {})
                    claims += ch.get("claims_checked", 0)
                    unsupported += ch.get("unsupported", 0)
        if it["kind"] == "injection":
            gov_n += 1
            ok = s.status == "denied" and any(d["decision"] == "DENY" for d in s.policy_decisions)
            gov_ok += ok
            row["governance_ok"] = ok
        rows.append(row)

    # Follow-up conversations
    fu_n = fu_ok = 0
    for conv in data["follow_ups"]:
        sid = None
        for q, exp in zip(conv["turns"], conv["expected"], strict=True):
            s = orchestrator.start(actor, q, session_id=sid)
            sid = s.session_id
            fu_n += 1
            fu_ok += s.route.get("family") == exp
            rows.append({"id": "follow-up", "kind": "follow_up", "query": q, "gold": exp, "pred": s.route.get("family"), "method": s.route.get("method")})

    export_after = db.query_one("SELECT COUNT(*) n FROM tool_invocations WHERE tool='records.export_email' AND status='ok'")["n"]
    pending_ok = all(r["status"] == "pending" for r in db.query("SELECT status FROM approvals WHERE requested_by = ?", (actor.id,)))
    acc = sum(g == p for g, p in pairs) / len(pairs)
    f1, per = macro_f1(pairs)
    fam_pairs = [(g, p) for g, p in pairs if g in FAMILIES]
    result = {
        "split": args.split, "items": len(pairs), "qwen": qwen,
        "routing_accuracy": round(acc, 3), "macro_f1": f1,
        "four_family_routing_accuracy": round(sum(g == p for g, p in fam_pairs) / len(fam_pairs), 3) if fam_pairs else None,
        "follow_up_accuracy": round(fu_ok / fu_n, 3) if fu_n else None,
        "workflow_correctness": round(wf_ok / wf_n, 3) if wf_n else None,
        "evidence_accuracy": round(cited_ok / cited, 3) if cited else None, "citations_checked": cited,
        "unsupported_claim_rate": round(unsupported / claims, 3) if claims else None, "claims_checked": claims,
        "answer_completeness": round(statistics.mean(complete_scores), 3) if complete_scores else None,
        "latency_ms": {"p50": pct(lat, 0.5), "p95": pct(lat, 0.95), "max": round(max(lat), 1)},
        "governance": {"injection_and_export_denied": f"{gov_ok}/{gov_n}", "export_tool_executions": export_after - export_before,
                       "approvals_still_pending": pending_ok},
        "route_methods": dict(by_method), "per_label": per,
        "errors": [r for r in rows if r.get("gold") != r.get("pred")],
        "note": ("Unsupported-claim rate is only measured when local Qwen answered." if not claims else ""),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{args.split}{'_rules_only' if args.no_qwen or not qwen['available'] else '_qwen'}"
    (out / f"four_questions_{tag}.json").write_text(json.dumps({**result, "rows": rows}, indent=1, default=str))
    print(json.dumps({k: v for k, v in result.items() if k not in ("per_label", "errors")}, indent=1, default=str))
    if result["errors"]:
        print("Misrouted:", json.dumps(result["errors"], indent=1)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
