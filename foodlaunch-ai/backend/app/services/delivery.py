"""Delivery domain services: briefs, clarifications, requirements, change sets,
release gates, manifests, approvals, deployment and rollback.

All permission checks happen here (server-side), never in the UI.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from app import auth
from app.auth import User
from app.config import FIXTURES
from app.db import canonical_json, kv_get, kv_set, loads, new_id, now_iso, row, rows, session, sha256_text
from app.errors import Conflict, GateFailed, NotFound, PlatformError
from app.records import audit, evidence
from app.states import transition_release, transition_run
from app.tools import deploy as deployer
from app.tools import testing
from app.tools.retrieval import get_index

LKG_KEY = "release.last_known_good"
CURRENT_KEY = "release.current"


@lru_cache(maxsize=1)
def scenario() -> dict:
    return json.loads((FIXTURES / "seed" / "flagship.json").read_text())


# --- runs and briefs -----------------------------------------------------------------

def get_run(run_id: str) -> dict:
    found = row("SELECT * FROM runs WHERE id = ?", (run_id,))
    if found is None:
        raise NotFound("Run not found", run_id=run_id)
    return found


def create_run(user: User, title: str, brief_text: str, mode: str) -> str:
    auth.require(user, "brief.submit")
    if mode not in ("demo", "live"):
        raise PlatformError("Mode must be 'demo' or 'live'")
    if not brief_text.strip() or len(brief_text) > 4000:
        raise PlatformError("Brief text must be 1-4000 characters")
    run_id = new_id("RUN")
    ts = now_iso()
    with session() as conn:
        conn.execute(
            "INSERT INTO runs (id, scenario_id, title, mode, status, stage, created_by, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'draft', 'brief', ?, ?, ?)",
            (run_id, scenario()["scenario_id"], title, mode, user.username, ts, ts),
        )
        conn.execute(
            "INSERT INTO briefs (id, run_id, version, title, text, submitted_by, created_at)"
            " VALUES (?, ?, 1, ?, ?, ?, ?)",
            (new_id("BRF"), run_id, title, brief_text.strip(), user.username, ts),
        )
    audit(user.username, "brief.submit", entity_type="run", entity_id=run_id, mode=mode)
    evidence("brief", f"submitted by {user.username}", f"Brief v1: {brief_text[:120]}", "human",
             run_id=run_id, ref_table="briefs")
    return run_id


def current_brief(run_id: str) -> dict:
    found = row("SELECT * FROM briefs WHERE run_id = ? ORDER BY version DESC LIMIT 1", (run_id,))
    if found is None:
        raise NotFound("Brief not found", run_id=run_id)
    found["analysis"] = loads(found.pop("analysis_json"), None)
    return found


def set_stage(run_id: str, stage: str, waiting_for: str | None = None) -> None:
    with session() as conn:
        conn.execute("UPDATE runs SET stage = ?, waiting_for = ?, updated_at = ? WHERE id = ?",
                     (stage, waiting_for, now_iso(), run_id))


# --- clarifications ------------------------------------------------------------------

def detect_ambiguities(brief_text: str) -> list[dict]:
    """Deterministic Brief Analyst checklist. A dimension is ambiguous when the
    brief invokes it (trigger phrase) but contains none of its resolving terms."""
    text = brief_text.lower()
    found = []
    for item in scenario()["clarifications"]:
        triggered = item["trigger"].lower() in text
        resolved = any(term.lower() in text for term in item["resolved_by_terms"])
        if triggered and not resolved:
            found.append({
                "id": item["id"], "topic": item["topic"], "question": item["question"],
                "required": item["required"], "blocks": item["blocks"], "options": item["options"],
                "evidence": get_index().search(item["doc_query"], k=2),
                "policy_gap": item.get("policy_gap", False), "gap_note": item.get("gap_note"),
                "trigger": item["trigger"],
            })
    return found


def store_clarifications(run_id: str, brief_version: int, items: list[dict], detected_by: str) -> None:
    with session() as conn:
        for item in items:
            conn.execute(
                "INSERT OR IGNORE INTO clarifications (run_id, id, brief_version, topic, question, required,"
                " blocks, options_json, evidence_json, status, detected_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (run_id, item["id"], brief_version, item["topic"], item["question"], int(item["required"]),
                 item["blocks"], json.dumps(item["options"]),
                 json.dumps({"retrieved": item.get("evidence", []), "policy_gap": item.get("policy_gap"),
                             "gap_note": item.get("gap_note"), "trigger": item.get("trigger")}),
                 detected_by),
            )


def list_clarifications(run_id: str) -> list[dict]:
    items = rows("SELECT * FROM clarifications WHERE run_id = ? ORDER BY rowid", (run_id,))
    for item in items:
        item["options"] = json.loads(item.pop("options_json"))
        item["evidence"] = json.loads(item.pop("evidence_json"))
    return items


def open_required_clarifications(run_id: str) -> list[dict]:
    return [c for c in list_clarifications(run_id) if c["required"] and c["status"] != "resolved"]


def decide_clarification(run_id: str, q_id: str, user: User, decision: str, rationale: str,
                         source: str = "user") -> None:
    auth.require(user, "clarification.decide", "clarification", f"{run_id}/{q_id}")
    found = row("SELECT * FROM clarifications WHERE run_id = ? AND id = ?", (run_id, q_id))
    if found is None:
        raise NotFound("Clarification not found", id=q_id)
    if found["status"] == "resolved":
        audit(user.username, "clarification.decide", outcome="rejected", entity_type="clarification",
              entity_id=f"{run_id}/{q_id}", reason="already resolved")
        raise Conflict("Clarification already has a recorded decision", id=q_id)
    if not decision.strip():
        raise PlatformError("Decision text is required")
    run = get_run(run_id)
    if run["status"] not in ("draft", "clarification-needed", "blocked"):
        raise Conflict("Clarifications are closed for this run", status=run["status"])
    with session() as conn:
        conn.execute(
            "UPDATE clarifications SET status = 'resolved', decision = ?, rationale = ?, decision_source = ?,"
            " decided_by = ?, decided_at = ? WHERE run_id = ? AND id = ?",
            (decision.strip(), rationale.strip(), source, user.username, now_iso(), run_id, q_id),
        )
    audit(user.username, "clarification.decide", entity_type="clarification", entity_id=f"{run_id}/{q_id}",
          decision=decision, source=source)
    evidence("clarification_decision", user.username, f"{q_id}: {decision}",
             "seeded_decision" if source == "seeded_demo" else "human", run_id=run_id,
             ref_table="clarifications", ref_id=q_id)


def apply_seeded_decisions(run_id: str, user: User) -> int:
    seeds = {c["id"]: c for c in scenario()["clarifications"]}
    count = 0
    for item in open_required_clarifications(run_id):
        seed = seeds.get(item["id"])
        if seed:
            decide_clarification(run_id, item["id"], user, seed["seeded_decision"],
                                 seed["seeded_rationale"], source="seeded_demo")
            count += 1
    return count


# --- requirements ---------------------------------------------------------------------

def create_requirement_set(run_id: str, version: int, brief_version: int, source: str, origin: str,
                           requirements: list[dict], test_files: list[str], incident_id: str | None = None) -> None:
    with session() as conn:
        if conn.execute("SELECT 1 FROM requirement_sets WHERE run_id = ? AND version = ?",
                        (run_id, version)).fetchone():
            return  # idempotent on resume
        conn.execute(
            "INSERT INTO requirement_sets (run_id, version, brief_version, source, status, origin, test_plan_json,"
            " created_at, incident_id) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?)",
            (run_id, version, brief_version, source, origin, json.dumps({"files": test_files}), now_iso(),
             incident_id),
        )
        for req in requirements:
            conn.execute(
                "INSERT INTO requirements (run_id, set_version, req_id, title, decisions_json) VALUES (?, ?, ?, ?, ?)",
                (run_id, version, req["id"], req["title"], json.dumps(req.get("decisions", []))),
            )
            for ac in req["criteria"]:
                conn.execute(
                    "INSERT INTO acceptance_criteria (run_id, set_version, ac_id, req_id, text, critical)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, version, ac["id"], req["id"], ac["text"], int(ac.get("critical", True))),
                )


def requirement_set(run_id: str, version: int | None = None) -> dict | None:
    if version is None:
        found = row("SELECT * FROM requirement_sets WHERE run_id = ? ORDER BY version DESC LIMIT 1", (run_id,))
    else:
        found = row("SELECT * FROM requirement_sets WHERE run_id = ? AND version = ?", (run_id, version))
    if found is None:
        return None
    found["test_plan"] = json.loads(found.pop("test_plan_json"))
    reqs = rows("SELECT * FROM requirements WHERE run_id = ? AND set_version = ? ORDER BY req_id",
                (run_id, found["version"]))
    acs = rows("SELECT * FROM acceptance_criteria WHERE run_id = ? AND set_version = ? ORDER BY ac_id",
               (run_id, found["version"]))
    for req in reqs:
        req["decisions"] = json.loads(req.pop("decisions_json"))
        req["criteria"] = [a for a in acs if a["req_id"] == req["req_id"]]
    found["requirements"] = reqs
    return found


def approved_set(run_id: str) -> dict | None:
    run = get_run(run_id)
    return requirement_set(run_id, run["requirement_set_version"]) if run["requirement_set_version"] else None


def approve_requirement_set(run_id: str, version: int, user: User) -> dict:
    auth.require(user, "requirements.approve", "requirement_set", f"{run_id}/v{version}")
    found = requirement_set(run_id, version)
    if found is None:
        raise NotFound("Requirement set not found")
    if found["status"] == "approved":
        audit(user.username, "requirements.approve", outcome="rejected", entity_type="requirement_set",
              entity_id=f"{run_id}/v{version}", reason="duplicate approval")
        raise Conflict("Requirement set already approved")
    if open_required_clarifications(run_id):
        raise Conflict("Required clarifications are still open")
    plan = testing.plan_hashes(found["test_plan"]["files"])  # frozen here
    with session() as conn:
        conn.execute(
            "UPDATE requirement_sets SET status = 'approved', approved_by = ?, approved_at = ?, test_plan_json = ?"
            " WHERE run_id = ? AND version = ?",
            (user.username, now_iso(), json.dumps(plan), run_id, version),
        )
        conn.execute("UPDATE runs SET requirement_set_version = ? WHERE id = ?", (version, run_id))
    audit(user.username, "requirements.approve", entity_type="requirement_set", entity_id=f"{run_id}/v{version}",
          tests_hash=plan["tests_hash"])
    evidence("requirements_approval", user.username,
             f"Requirement set v{version} approved; test plan frozen ({plan['tests_hash'][:12]})", "human",
             run_id=run_id, ref_table="requirement_sets", ref_id=f"{run_id}/v{version}")
    return plan


# --- change sets ----------------------------------------------------------------------

def record_change_set(run_id: str, kind: str, patch_name: str, applied, meta: dict,
                      incident_id: str | None = None) -> str:
    existing = row("SELECT id FROM change_sets WHERE run_id = ? AND patch_name = ? AND base_revision = ?",
                   (run_id, patch_name, applied.base_revision))
    if existing:
        return existing["id"]
    cs_id = new_id("CS")
    with session() as conn:
        conn.execute(
            "INSERT INTO change_sets (id, run_id, kind, patch_name, patch_hash, base_revision, revision, files_json,"
            " diff_text, label, agent, title, addresses_json, incident_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cs_id, run_id, kind, patch_name, applied.patch_hash, applied.base_revision, applied.revision,
             json.dumps(applied.files), applied.diff, meta["label"], meta["agent"], meta["title"],
             json.dumps(meta["addresses"]), incident_id, now_iso()),
        )
    evidence("change_set", meta["agent"], f"{meta['title']} -> {applied.revision[:10]}", "fixture",
             revision=applied.revision, run_id=run_id, ref_table="change_sets", ref_id=cs_id)
    return cs_id


def change_sets(run_id: str) -> list[dict]:
    items = rows("SELECT * FROM change_sets WHERE run_id = ? ORDER BY created_at", (run_id,))
    for item in items:
        item["files"] = json.loads(item.pop("files_json"))
        item["addresses"] = json.loads(item.pop("addresses_json"))
    return items


def head_revision(run_id: str) -> str | None:
    found = row("SELECT revision FROM change_sets WHERE run_id = ? ORDER BY created_at DESC LIMIT 1", (run_id,))
    return found["revision"] if found else None


# --- gates ----------------------------------------------------------------------------

def latest_test_run(run_id: str, revision: str, suite_version: int, purpose_prefix: str = "") -> dict | None:
    return row(
        "SELECT * FROM test_runs WHERE run_id = ? AND revision = ? AND suite_version = ? AND status != 'running'"
        " AND purpose LIKE ? ORDER BY started_at DESC LIMIT 1",
        (run_id, revision, suite_version, purpose_prefix + "%"),
    )


def test_results(test_run_id: str) -> list[dict]:
    items = rows("SELECT * FROM test_results WHERE test_run_id = ? ORDER BY nodeid", (test_run_id,))
    for item in items:
        item["ac_ids"] = json.loads(item.pop("ac_ids_json"))
        item["regression_ids"] = json.loads(item.pop("regression_ids_json"))
    return items


def evaluate_gates(run_id: str, revision: str | None) -> dict:
    """Deterministic release gates. Evidence must be for the exact revision."""
    gates: list[dict] = []

    def gate(gate_id: str, name: str, passed: bool, detail: str, refs: list[str] | None = None) -> None:
        gates.append({"id": gate_id, "name": name, "passed": bool(passed), "detail": detail, "refs": refs or []})

    open_q = open_required_clarifications(run_id)
    gate("G1", "Required clarifications resolved", not open_q,
         "all resolved" if not open_q else "open: " + ", ".join(q["id"] for q in open_q))
    req_set = approved_set(run_id)
    gate("G2", "Requirement set approved", req_set is not None and req_set["status"] == "approved",
         f"v{req_set['version']} approved by {req_set['approved_by']}" if req_set else "no approved set")
    test_run = None
    if req_set and revision:
        test_run = latest_test_run(run_id, revision, req_set["version"])
    plan_hash = req_set["test_plan"].get("tests_hash") if req_set else None
    tests_ok = bool(test_run and test_run["status"] == "passed" and test_run["tests_hash"] == plan_hash)
    gate("G3", "Critical tests pass on this exact revision", tests_ok,
         (f"{test_run['id']} {test_run['status']} on {revision[:10]}" if test_run
          else f"no test run for revision {revision[:10] if revision else '-'}"),
         [test_run["id"]] if test_run else [])
    results = test_results(test_run["id"]) if test_run else []
    passed_acs = {ac for r in results if r["outcome"] == "passed" for ac in r["ac_ids"]}
    failed_acs = {ac for r in results if r["outcome"] != "passed" for ac in r["ac_ids"]}
    required = [a for req in (req_set["requirements"] if req_set else []) for a in req["criteria"] if a["critical"]]
    uncovered = [a["ac_id"] for a in required if a["ac_id"] not in passed_acs or a["ac_id"] in failed_acs]
    gate("G4", "Every critical acceptance criterion covered by a passing test", bool(required) and not uncovered,
         "all covered" if required and not uncovered else "gaps: " + ", ".join(uncovered or ["no criteria"]))
    checks = rows("SELECT * FROM static_checks WHERE revision = ? AND run_id = ? ORDER BY created_at DESC",
                  (revision or "", run_id))
    latest = {}
    for check in checks:
        latest.setdefault(check["tool"], check)
    static_ok = {"ruff", "forbidden-call-scan"} <= set(latest) and all(c["status"] == "passed" for c in latest.values())
    gate("G5", "Static-check policy satisfied", static_ok,
         ", ".join(f"{t}: {c['status']}" for t, c in latest.items()) or "not run for this revision",
         [c["id"] for c in latest.values()])
    blocking = rows("SELECT * FROM findings WHERE run_id = ? AND blocking = 1 AND status = 'open'", (run_id,))
    gate("G6", "No unresolved blocking findings", not blocking,
         "none" if not blocking else ", ".join(f["title"] for f in blocking), [f["id"] for f in blocking])
    seen_regressions = set()
    for tr in rows("SELECT id FROM test_runs WHERE run_id = ?", (run_id,)):
        for r in test_results(tr["id"]):
            seen_regressions.update(r["regression_ids"])
    present = {rid for r in results if r["outcome"] == "passed" for rid in r["regression_ids"]}
    missing = sorted(seen_regressions - present)
    gate("G7", "Preserved regression tests present and passing", not missing,
         ("preserved: " + ", ".join(sorted(present))) if not missing else "missing/failing: " + ", ".join(missing))
    return {"revision": revision, "evidence_ready": all(g["passed"] for g in gates), "gates": gates,
            "evaluated_at": now_iso()}


def add_finding(run_id: str, revision: str, severity: str, blocking: bool, title: str, detail: str, source: str) -> str:
    finding_id = new_id("FND")
    with session() as conn:
        conn.execute(
            "INSERT INTO findings (id, run_id, revision, severity, blocking, title, detail, source, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (finding_id, run_id, revision, severity, int(blocking), title, detail, source, now_iso()),
        )
    return finding_id


# --- releases -------------------------------------------------------------------------

def get_release(release_id: str) -> dict:
    found = row("SELECT * FROM releases WHERE id = ?", (release_id,))
    if found is None:
        raise NotFound("Release not found", release_id=release_id)
    found["manifest"] = json.loads(found.pop("manifest_json"))
    found["approval"] = row("SELECT * FROM approvals WHERE release_id = ?", (release_id,))
    return found


def current_release() -> dict | None:
    release_id = kv_get(CURRENT_KEY)
    return get_release(release_id) if release_id else None


def create_release(run_id: str, revision: str, actor: str, kind: str, incident_id: str | None = None) -> dict:
    gates = evaluate_gates(run_id, revision)
    req_set = approved_set(run_id)
    test_run = latest_test_run(run_id, revision, req_set["version"]) if req_set else None
    statics = rows("SELECT id, tool, status FROM static_checks WHERE run_id = ? AND revision = ? ORDER BY created_at",
                   (run_id, revision))
    live = current_release()
    css = change_sets(run_id)
    with session() as conn:
        conn.execute(
            "UPDATE releases SET status = 'invalidated' WHERE run_id = ? AND status IN"
            " ('awaiting-approval', 'approved', 'blocked')", (run_id,))
    release_id = new_id("REL")
    manifest = {
        "release_id": release_id, "kind": kind, "run_id": run_id, "revision": revision,
        "replaces_revision": live["revision"] if live else None,
        "brief_version": current_brief(run_id)["version"],
        "requirement_set_version": req_set["version"] if req_set else None,
        "change_sets": [{"id": c["id"], "patch": c["patch_name"], "patch_hash": c["patch_hash"],
                         "revision": c["revision"]} for c in css],
        "test_run": {"id": test_run["id"], "status": test_run["status"], "tests_hash": test_run["tests_hash"],
                     "exit_code": test_run["exit_code"]} if test_run else None,
        "static_checks": [{"id": s["id"], "tool": s["tool"], "status": s["status"]} for s in statics[-2:]],
        "gates": [{"id": g["id"], "passed": g["passed"]} for g in gates["gates"]],
        "incident_id": incident_id,
        "generated_at": now_iso(),
    }
    manifest_hash = sha256_text(canonical_json(manifest))
    status = "awaiting-approval" if gates["evidence_ready"] else "blocked"
    with session() as conn:
        conn.execute(
            "INSERT INTO releases (id, run_id, revision, kind, status, manifest_json, manifest_hash, incident_id,"
            " created_at, label) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (release_id, run_id, revision, kind, status, canonical_json(manifest), manifest_hash, incident_id,
             now_iso(), f"{kind} release {revision[:10]}"),
        )
    audit(actor, "release.create", entity_type="release", entity_id=release_id, revision=revision,
          manifest_hash=manifest_hash, status=status)
    evidence("release_manifest", actor, f"Manifest {manifest_hash[:12]} for {revision[:10]} ({status})",
             "deterministic", revision=revision, run_id=run_id, ref_table="releases", ref_id=release_id)
    return get_release(release_id)


def approve_release(release_id: str, user: User, manifest_hash: str) -> dict:
    auth.require(user, "release.approve", "release", release_id)
    release = get_release(release_id)
    if release["approval"]:
        audit(user.username, "release.approve", outcome="rejected", entity_type="release", entity_id=release_id,
              reason="duplicate approval")
        raise Conflict("This release already has a recorded approval")
    if release["status"] != "awaiting-approval":
        audit(user.username, "release.approve", outcome="rejected", entity_type="release", entity_id=release_id,
              reason=f"status {release['status']}")
        raise Conflict(f"Release is '{release['status']}', not awaiting approval")
    if manifest_hash != release["manifest_hash"]:
        audit(user.username, "release.approve", outcome="rejected", entity_type="release", entity_id=release_id,
              reason="manifest hash mismatch")
        raise Conflict("Approval must reference the current manifest hash", expected=release["manifest_hash"])
    run_id = release["run_id"]
    if head_revision(run_id) != release["revision"]:
        transition_release(release_id, "invalidated", user.username, "candidate changed")
        raise Conflict("Candidate revision changed after the manifest was generated; approval invalidated")
    gates = evaluate_gates(run_id, release["revision"])
    if not gates["evidence_ready"]:
        raise GateFailed("Release evidence is no longer complete", gates=gates["gates"])
    with session() as conn:
        conn.execute(
            "INSERT INTO approvals (id, release_id, approver, revision, manifest_hash, created_at, status)"
            " VALUES (?, ?, ?, ?, ?, ?, 'valid')",
            (new_id("APR"), release_id, user.username, release["revision"], manifest_hash, now_iso()),
        )
    transition_release(release_id, "approved", user.username)
    transition_run(run_id, "approved", user.username, f"release {release_id} approved")
    audit(user.username, "release.approve", entity_type="release", entity_id=release_id,
          manifest_hash=manifest_hash, revision=release["revision"])
    evidence("approval", user.username, f"Approved {release_id} @ {release['revision'][:10]} "
             f"manifest {manifest_hash[:12]}", "human", revision=release["revision"], run_id=run_id,
             ref_table="approvals", ref_id=release_id)
    return get_release(release_id)


def _activate(release: dict, deployment: dict, actor: str) -> None:
    previous = kv_get(CURRENT_KEY)
    if previous and previous != release["id"]:
        prev = get_release(previous)
        if prev["status"] == "deployed":
            transition_release(previous, "superseded", actor, f"replaced by {release['id']}")
        kv_set(LKG_KEY, previous)
    kv_set(CURRENT_KEY, release["id"])


def deploy_release(release_id: str, user: User) -> dict:
    auth.require(user, "release.deploy", "release", release_id)
    release = get_release(release_id)
    approval = release["approval"]
    if release["status"] != "approved" or not approval:
        audit(user.username, "release.deploy", outcome="rejected", entity_type="release", entity_id=release_id,
              reason="not approved")
        raise Conflict("Only an approved release can be deployed")
    if approval["manifest_hash"] != release["manifest_hash"] or approval["revision"] != release["revision"]:
        raise Conflict("Approval is not bound to this manifest and revision")
    gates = evaluate_gates(release["run_id"], release["revision"])
    if not gates["evidence_ready"]:
        raise GateFailed("Release evidence changed since approval", gates=gates["gates"])
    run_id = release["run_id"]
    transition_run(run_id, "deploying", user.username)
    transition_release(release_id, "deploying", user.username)
    deployment = deployer.deploy(release_id, release["revision"], user.username, "deploy")
    if deployment["status"] == "healthy":
        with session() as conn:
            conn.execute("UPDATE releases SET deployed_at = ? WHERE id = ?", (now_iso(), release_id))
        transition_release(release_id, "deployed", user.username)
        _activate(release, deployment, user.username)
        transition_run(run_id, "deployed", user.username)
    else:
        transition_release(release_id, "failed", user.username)
        transition_run(run_id, "failed", user.username, "deployment health check failed")
    return deployment


def rollback(user: User, reason: str) -> dict:
    auth.require(user, "release.rollback", "release", kv_get(CURRENT_KEY))
    current_id, target_id = kv_get(CURRENT_KEY), kv_get(LKG_KEY)
    if not target_id or target_id == current_id:
        raise Conflict("No different last-known-good release is recorded")
    current = get_release(current_id)
    target = get_release(target_id)
    deployment = deployer.deploy(target_id, target["revision"], user.username, "rollback")
    if deployment["status"] != "healthy":
        raise PlatformError("Rollback deployment failed its health check", deployment=deployment["id"])
    transition_release(current_id, "rolled-back", user.username, reason)
    transition_release(target_id, "deploying", user.username, "rollback target")
    transition_release(target_id, "deployed", user.username, "rollback target")
    kv_set(CURRENT_KEY, target_id)
    if current["run_id"] and get_run(current["run_id"])["status"] == "deployed":
        transition_run(current["run_id"], "rolled-back", user.username, reason)
    audit(user.username, "release.rollback", entity_type="release", entity_id=current_id, to=target_id, reason=reason)
    return deployment


def seed_baseline_release(revision: str) -> str:
    """The pre-campaign baseline, recorded as the initial known-good release."""
    release_id = "REL-BASELINE"
    manifest = {"release_id": release_id, "kind": "baseline", "revision": revision, "seeded": True,
                "note": "Seeded v1.0 storefront, deployed by Reset Demo (no delivery run)."}
    with session() as conn:
        conn.execute(
            "INSERT INTO releases (id, run_id, revision, kind, status, manifest_json, manifest_hash, created_at,"
            " deployed_at, label) VALUES (?, NULL, ?, 'baseline', 'deployed', ?, ?, ?, ?, ?)",
            (release_id, revision, canonical_json(manifest), sha256_text(canonical_json(manifest)), now_iso(),
             now_iso(), "Seeded baseline v1.0"),
        )
    kv_set(CURRENT_KEY, release_id)
    kv_set(LKG_KEY, release_id)
    return release_id


def short(text: str, n: int = 80) -> str:
    return re.sub(r"\s+", " ", text)[:n]
