"""Remediation Planning Agent (deterministic).

Builds an ordered recovery plan from an RCA report:

  1. undo the root change (rollback) when the root cause is a confirmed/probable change with a known previous version;
  2. recover each downstream link on the causal chain, upstream first, using the connector's own action catalog;
  3. record the incident (ticket) with the RCA summary.

Steps use only actions a connector publishes, and every parameter set is validated against that action's JSON
schema before the plan is stored. If the RCA conclusion is inconclusive, no state-changing step is planned:
the plan is limited to recording the incident and listing further diagnostics.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from florome.connectors.base import ActionValidationError, Connector
from florome.rca.engine import Topology

# resource kind on the causal chain -> (action, whose resource executes it)
RECOVERY: dict[str, tuple[str, str]] = {
    "s3_bucket": ("replay_ingestion", "parent"),
    "databricks_job": ("rerun_job", "self"),
    "app_service": ("refresh_cache", "self"),
    "ci_pipeline": ("rerun_failed_jobs", "self"),
}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _minutes_since(iso: str, now: datetime) -> int:
    return max(1, min(1440, int((now - datetime.fromisoformat(iso)).total_seconds() // 60) + 15))


def build_plan(report: dict[str, Any], topo: Topology, evidence_by_id: dict[str, dict[str, Any]],
               connector_for: Callable[[str], Connector | None], now: datetime) -> dict[str, Any]:
    concl = report["conclusion"]
    status = report.get("challenge", {}).get("final_status", concl["status"])
    hyps = {h["id"]: h for h in report["hypotheses"]}
    steps: list[dict[str, Any]] = []
    notes: list[str] = []

    def add(action_id: str, target: str, params: dict[str, Any], rationale: str, hypothesis_id: str | None) -> None:
        res = topo.resources[target]
        conn = connector_for(res.get("connection_id") or "")
        if conn is None:
            notes.append(f"No connector instance for {res['name']}; '{action_id}' must be done manually.")
            return
        try:
            spec = conn.validate_action(action_id, res["kind"], params)
        except ActionValidationError as exc:
            notes.append(f"Skipped {action_id} on {res['name']}: {exc}")
            return
        steps.append({"index": len(steps), "action_id": action_id, "title": spec.title, "connection_id": res["connection_id"],
                      "connector_type": conn.connector_type, "simulated": conn.is_simulated,
                      "target_resource_id": target, "target_name": res["name"], "target_kind": res["kind"],
                      "environment": res.get("environment", "prod"), "params": params, "expected_outcome": spec.expected_outcome,
                      "risk": spec.risk, "reversible": spec.reversible, "rollback": spec.rollback,
                      "required_permission": spec.required_permission, "tested": spec.tested, "rationale": rationale,
                      "hypothesis_id": hypothesis_id})

    root = hyps.get(concl.get("root_hypothesis_id") or "")
    actionable = status in ("confirmed", "probable") and root is not None
    if actionable:
        root_res = root["candidate_resource_id"]
        if root["kind"] == "change":
            change = next((evidence_by_id[e] for e in root["supporting_evidence"]
                           if e in evidence_by_id and evidence_by_id[e]["kind"] in ("deployment", "config_change")), None)
            prev = (change or {}).get("payload", {}).get("previous_version")
            if prev:
                add("rollback_deployment", root_res, {"to_version": prev},
                    f"{root['id']} ({root['status']}): {root['title']}", root["id"])
            else:
                notes.append(f"Root change on {topo.name(root_res)} has no recorded previous version; revert must be planned manually.")
        elif root["kind"] == "saturation":
            notes.append(f"Saturation on {topo.name(root_res)}: capacity changes are not in any connector catalog; escalate to the owning team.")
        onset = report["anomaly_onset"]
        for link in concl["causal_chain"][1:]:
            rid = link["resource_id"]
            kind = topo.resources[rid]["kind"]
            if kind not in RECOVERY:
                continue
            action_id, who = RECOVERY[kind]
            target = rid if who == "self" else next(iter(topo.parents(rid)), None)
            if target is None:
                continue
            params: dict[str, Any] = {}
            if action_id == "replay_ingestion":
                params = {"window_minutes": _minutes_since(onset.get(root_res, now.isoformat()), now)}
            if action_id == "rerun_failed_jobs":
                notes.append(f"{topo.name(rid)}: re-run needs a run id; add it manually.")
                continue
            add(action_id, target, params, f"Recover {topo.name(rid)} (chain link {link['link_status']}).", link.get("hypothesis_id"))
    else:
        notes.append(f"RCA status is '{status}': no state-changing action is planned. Run the listed diagnostics first.")

    primary = report["incident"]["primary_resource_id"]
    add("create_ticket", primary, {"summary": f"[{status}] {concl['statement']}"[:500]}, "Record the incident and RCA outcome.", None)

    validation_targets = [c["resource_id"] for c in concl.get("causal_chain", [])] or [primary]
    downstream = [d for d in topo.descendants(primary) if topo.resources[d]["kind"] == "business_process"]
    risk = max((s["risk"] for s in steps), key=lambda r: RISK_ORDER[r], default="low")
    return {"steps": steps, "notes": notes, "risk": risk, "rca_status": status,
            "validation_targets": list(dict.fromkeys([*validation_targets, *downstream])),
            "next_diagnostics": concl.get("next_diagnostics", [])}
