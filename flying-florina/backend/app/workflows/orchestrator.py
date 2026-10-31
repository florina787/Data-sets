"""Supervisor entry point: classify, create the run, execute the graph, compose the workspace."""

from __future__ import annotations

import threading
import time
from typing import Any

from app.core import audit, db
from app.core.security import Actor
from app.core.util import new_id, now_iso
from app.workflows import compose as composer
from app.workflows.engine import CaseState, _event, checkpoint, run_graph
from app.workflows.graphs import GRAPHS
from app.workflows import conversation, explain
from app.workflows.router import CONVERSATIONAL, route


def ensure_session(actor: Actor, session_id: str | None, title: str) -> str:
    if session_id:
        s = db.query_one("SELECT id, user_id FROM sessions WHERE id = ?", (session_id,))
        if s and s["user_id"] == actor.id:
            with db.session(write=True) as conn:
                conn.execute("UPDATE sessions SET updated = ? WHERE id = ?", (now_iso(), session_id))
            return session_id
    sid = new_id("SES")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (sid, actor.id, title[:120], now_iso(), now_iso()))
    return sid


def start(actor: Actor, query: str, persona: str | None = None, session_id: str | None = None,
          options: dict[str, Any] | None = None, wait: bool = True, replay_of: str | None = None) -> CaseState:
    options = options or {}
    sid = ensure_session(actor, session_id, query)
    r = route(query, conversation.get_context(sid) if session_id else None, use_model=not options.get("rules_only"))
    forced = options.get("force_workflow") if options.get("force_workflow") in GRAPHS else None
    workflow = forced or r.workflow
    intent = {**r.intent, "workflow": workflow, "family": r.family, "route_method": r.method, "confidence": r.intent.get("confidence", 0.0),
              "reason": r.reason}
    run_id = new_id("RUN")
    state = CaseState(session_id=sid, run_id=run_id, query=query, persona=persona or actor.persona, actor=actor.as_dict(),
                      workflow=workflow, intent=intent, status="queued", route=r.as_dict())
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO workflow_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, sid, actor.id, state.persona, query, workflow, "queued", now_iso(), now_iso(),
                      state.model_dump_json(), db.jdump(options), replay_of))
        state.audit_event_ids.append(audit.append(actor.id, "workflow.started", f"{workflow}: {query[:120]}",
                                                  {"run_id": run_id, "intent": {k: intent[k] for k in ("workflow", "confidence")}}, conn))
    fam = f" · family {r.family}" if r.family else ""
    _event(run_id, "intake", "Intake & Intent Agent", "completed", 1, 0.0,
           f"Routed to '{workflow}' by {r.method}{fam}{' (follow-up)' if r.follow_up else ''}. {r.reason}",
           {"scores": intent.get("scores", {}), "family_scores": r.family_scores, "semantic": r.semantic, "entities": intent.get("entities", {}),
            "secondary": r.secondary})
    conversation.save_context(sid, r, query)

    if not forced and r.label in CONVERSATIONAL and r.label != "data_export":
        def talk() -> None:
            conversation.answer(state, r, actor)
            checkpoint(state)

        if wait:
            talk()
        else:
            checkpoint(state)
            threading.Thread(target=talk, name=f"chat-{run_id}", daemon=True).start()
        return state

    def work() -> None:
        final = run_graph(GRAPHS[workflow](), state, actor, options)
        t0 = time.perf_counter()
        try:
            composer.compose(final)
            _event(run_id, "compose_workspace", "Reporting Agent", "completed", 1, (time.perf_counter() - t0) * 1000,
                   f"Composed {len(final.workspace)} workspace blocks from agent outputs.")
        except Exception as err:  # noqa: BLE001
            final.errors.append({"step": "compose_workspace", "error": str(err)})
            final.workspace = [composer.md(f"Workspace could not be composed: {err}")]
            _event(run_id, "compose_workspace", "Reporting Agent", "failed", 1, (time.perf_counter() - t0) * 1000, str(err))
        if r.secondary and r.secondary != r.family:
            final.workspace.append({"type": "actions", "items": [{"label": f"Also answer the {r.secondary} part", "kind": "query",
                                                                  "target": next(q["question"] for q in conversation.FOUR_QUESTIONS if q["family"] == r.secondary)}]})
        # Publish the deterministic, evidence-backed workspace first; the Qwen explanation is added when ready.
        final.pending_explanation = True
        checkpoint(final)
        try:
            explain.run(final, actor.id)
        except Exception as err:  # noqa: BLE001 - an explanation failure must never lose the evidence
            final.errors.append({"step": "qwen_explanation", "error": str(err)})
        final.pending_explanation = False
        checkpoint(final)

    if wait:
        work()
    else:
        threading.Thread(target=work, name=f"wf-{run_id}", daemon=True).start()
    return state


def get_run(run_id: str) -> dict[str, Any] | None:
    r = db.query_one("SELECT * FROM workflow_runs WHERE id = ?", (run_id,))
    if not r:
        return None
    r["state"] = db.jload(r.pop("state_json"), {})
    r["options"] = db.jload(r.pop("options_json"), {})
    return r


def cancel(run_id: str, actor: Actor) -> bool:
    with db.session(write=True) as conn:
        cur = conn.execute("UPDATE workflow_runs SET status = 'cancelled', updated = ? WHERE id = ? AND status IN ('queued', 'running')",
                           (now_iso(), run_id))
        changed = cur.rowcount > 0
        if changed:
            audit.append(actor.id, "workflow.cancelled", f"Run {run_id} cancelled", {"run_id": run_id}, conn)
    return changed
