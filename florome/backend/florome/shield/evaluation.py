"""Reproducible evaluation on the labelled LedgerLite corpus.

This is the ONLY module that reads ground truth (``ledgerlite_labels.json``). It runs the full research workflow
fresh, then scores three pipelines on the same (function, vulnerability class) sites:

  scanner_only       a site is positive if Opengrep or Bandit reported that class inside the function
  graph_unverified   positive if a hypothesis has a data flow and no guard (no execution)
  hybrid_verified    positive only if the hypothesis was confirmed by reproducible isolated verification
  llm_only           not run: no authorised model endpoint is configured (recorded explicitly, not omitted)

Predictions on sites absent from the labels count as false positives (the corpus labels every intended weakness).
The corpus is small (9 labelled sites) and was written by the same team as the engine; treat the numbers as a
regression benchmark, not as evidence of real-world recall. Novel-vulnerability discovery is not measured.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.config import PACKAGE_DIR, Settings
from florome.security import audit
from florome.security.rbac import Principal
from florome.shield import research
from florome.shield.control import authorize
from florome.shield.models import BenchmarkRun, CodeSymbol, FindingEvidence, SecurityHypothesis, SecurityPolicyDecision

TARGETS = PACKAGE_DIR / "shield" / "range" / "targets"
LABELS = TARGETS / "ledgerlite_labels.json"


def _score(predicted: set[tuple[str, str]], labels: list[dict[str, Any]]) -> dict[str, Any]:
    truth = {(s["function"], s["class"]) for s in labels if s["vulnerable"]}
    negatives = {(s["function"], s["class"]) for s in labels if not s["vulnerable"]}
    tp, fp, fn = len(predicted & truth), len(predicted - truth), len(truth - predicted)
    tn = len(negatives - predicted)
    return {"tp": tp, "fp": fp, "fn": fn, "tn_labelled": tn,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "false_positives": sorted(f"{f}:{c}" for f, c in predicted - truth), "missed": sorted(f"{f}:{c}" for f, c in truth - predicted)}


def run(db: Session, settings: Settings, p: Principal) -> list[BenchmarkRun]:
    authorize(db, settings, p, "evaluation.run", {"id": "ledgerlite"})
    labels = json.loads(LABELS.read_text())["sites"]
    denied_before = db.query(SecurityPolicyDecision).filter_by(tenant_id=p.tenant_id, allowed=False).count()
    t0 = time.perf_counter()
    repo = research.register_repository(db, settings, p, "ledgerlite", str(TARGETS / "ledgerlite"))
    snap = research.ingest(db, settings, p, repo)
    scan = research.scan(db, settings, p, repo, snap)
    t_scan = time.perf_counter() - t0
    hyps = db.scalars(select(SecurityHypothesis).where(SecurityHypothesis.scan_id == scan.id)).all()
    verified_attempts = verified_ok = 0
    for h in hyps:
        research.verify(db, settings, p, h)
        if h.verification_method:
            verified_attempts += 1
            verified_ok += int(h.status in ("confirmed", "disproven"))
    t_verify = time.perf_counter() - t0 - t_scan
    symbols = db.scalars(select(CodeSymbol).where(CodeSymbol.snapshot_id == snap.id, CodeSymbol.kind.in_(["function", "route"]))).all()

    def fn_at(file: str, line: int) -> str:
        s = next((s for s in symbols if s.file == file and s.start_line <= line <= s.end_line), None)
        return s.name if s else "<module>"

    ev = db.scalars(select(FindingEvidence).where(FindingEvidence.scan_id == scan.id, FindingEvidence.tool.in_(["opengrep", "bandit"]))).all()
    scanner = {(fn_at(e.file, e.line), e.vuln_class) for e in ev if e.vuln_class != "other" and e.file == "app.py"}
    graph = {(h.function, h.vuln_class) for h in hyps if h.file == "app.py" and any(s["type"] in ("data_flow", "route") for s in h.supporting)
             and not h.contradicting}
    confirmed = [h for h in hyps if h.status == "confirmed"]
    hybrid = {(h.function, h.vuln_class) for h in confirmed if h.file == "app.py"}

    patches = []
    t_patch0 = time.perf_counter()
    for h in confirmed:
        try:
            patches.append(research.generate_patch(db, settings, p, h))
        except research.ResearchError:
            patches.append(None)
    t_patch = time.perf_counter() - t_patch0
    made = [x for x in patches if x is not None]
    patch_metrics = {"confirmed_findings": len(confirmed), "patches_generated": len(made),
                     "patches_verified": sum(x.status == "verified" for x in made),
                     "regression_pass_rate": round(sum(x.regression.get("functional_ok", False) for x in made) / len(made), 3) if made else None,
                     "exploit_blocked_rate": round(sum(x.regression.get("exploit_blocked_runs") == 2 for x in made) / len(made), 3) if made else None}
    denied = db.query(SecurityPolicyDecision).filter_by(tenant_id=p.tenant_id, allowed=False).count() - denied_before
    common = {"sample_size_sites": len(labels), "vulnerable_sites": sum(s["vulnerable"] for s in labels),
              "snapshot": snap.id, "commit": snap.commit, "tree_hash": snap.tree_hash, "tools": scan.tools,
              "model_tokens": 0, "compute_cost_usd": 0.0, "policy_denials_during_run": denied}
    out = []
    for name, pred, extra in [
        ("scanner_only", scanner, {"seconds": round(t_scan, 2)}),
        ("graph_unverified", graph, {"seconds": round(t_scan, 2)}),
        ("hybrid_verified", hybrid, {"seconds": round(t_scan + t_verify, 2), "verification_attempted": verified_attempts,
                                     "verification_decisive": verified_ok,
                                     "verification_success_rate": round(verified_ok / verified_attempts, 3) if verified_attempts else None,
                                     "seconds_per_confirmed_finding": round((t_scan + t_verify) / len(confirmed), 2) if confirmed else None,
                                     "patching": {**patch_metrics, "seconds": round(t_patch, 2)}}),
    ]:
        br = BenchmarkRun(tenant_id=p.tenant_id, corpus="ledgerlite@labels-v1", pipeline=name, status="completed", sample_size=len(labels),
                          metrics={**_score(pred, labels), **common, **extra}, per_site=sorted(f"{f}:{c}" for f, c in pred),
                          note="Known-vulnerability detection on a training target. Not a measure of novel discovery.")
        db.add(br)
        out.append(br)
    db.add(BenchmarkRun(tenant_id=p.tenant_id, corpus="ledgerlite@labels-v1", pipeline="llm_only", status="not_run", sample_size=len(labels),
                        metrics={}, note="Not run: no authorised model endpoint is configured. Florome does not call paid model APIs implicitly."))
    db.flush()
    audit.record(db, p.tenant_id, p.user_id, "shield.evaluation", "ledgerlite", "success",
                 {r.pipeline: {"precision": r.metrics.get("precision"), "recall": r.metrics.get("recall")} for r in out})
    return out
