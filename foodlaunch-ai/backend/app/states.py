"""Explicit state machines for delivery runs and releases."""

from __future__ import annotations

from app.db import now_iso, row, session
from app.errors import InvalidTransition, NotFound
from app.records import audit

RUN_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"clarification-needed", "requirements-review", "failed"},
    "clarification-needed": {"requirements-review", "blocked", "failed"},
    "requirements-review": {"requirements-approved", "clarification-needed", "failed"},
    "requirements-approved": {"implementing", "blocked", "failed"},
    "implementing": {"testing", "blocked", "failed"},
    "testing": {"implementing", "awaiting-release-approval", "blocked", "failed"},
    "blocked": {"implementing", "testing", "clarification-needed", "requirements-review",
                "awaiting-release-approval", "failed"},
    "awaiting-release-approval": {"approved", "blocked", "implementing", "failed"},
    "approved": {"deploying", "awaiting-release-approval", "blocked"},
    "deploying": {"deployed", "failed"},
    "deployed": {"requirements-review", "implementing", "rolled-back"},
    "rolled-back": {"requirements-review", "implementing", "deploying"},
    "failed": {"implementing", "awaiting-release-approval", "deploying"},
}
RUN_STATUSES = set(RUN_TRANSITIONS)

RELEASE_TRANSITIONS: dict[str, set[str]] = {
    "awaiting-approval": {"approved", "invalidated", "blocked"},
    "blocked": {"awaiting-approval", "invalidated"},
    "approved": {"deploying", "invalidated"},
    "deploying": {"deployed", "failed"},
    "deployed": {"superseded", "rolled-back"},
    "rolled-back": {"deploying"},
    "superseded": {"deploying"},
    "failed": {"deploying", "invalidated"},
    "invalidated": set(),
}


def transition_run(run_id: str, to_status: str, actor: str, reason: str = "") -> None:
    with session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if current is None:
                raise NotFound("Run not found", run_id=run_id)
            from_status = current["status"]
            if from_status == to_status:
                conn.execute("COMMIT")
                return
            if to_status not in RUN_TRANSITIONS.get(from_status, set()):
                raise InvalidTransition(
                    f"Run cannot move from '{from_status}' to '{to_status}'",
                    run_id=run_id, from_status=from_status, to_status=to_status,
                )
            ts = now_iso()
            conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE id = ?", (to_status, ts, run_id)
            )
            conn.execute(
                "INSERT INTO status_history (run_id, from_status, to_status, actor, reason, ts)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, from_status, to_status, actor, reason, ts),
            )
            conn.execute("COMMIT")
        except InvalidTransition as exc:
            conn.execute("ROLLBACK")
            audit(actor, "run.transition", outcome="rejected", entity_type="run",
                  entity_id=run_id, error=exc.message)
            raise
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    audit(actor, "run.transition", entity_type="run", entity_id=run_id,
          from_status=from_status, to_status=to_status, reason=reason)


def transition_release(release_id: str, to_status: str, actor: str, reason: str = "") -> None:
    found = row("SELECT status FROM releases WHERE id = ?", (release_id,))
    if found is None:
        raise NotFound("Release not found", release_id=release_id)
    if to_status not in RELEASE_TRANSITIONS[found["status"]]:
        audit(actor, "release.transition", outcome="rejected", entity_type="release",
              entity_id=release_id, from_status=found["status"], to_status=to_status)
        raise InvalidTransition(
            f"Release cannot move from '{found['status']}' to '{to_status}'",
            release_id=release_id,
        )
    with session() as conn:
        updated = conn.execute(
            "UPDATE releases SET status = ? WHERE id = ? AND status = ?",
            (to_status, release_id, found["status"]),
        ).rowcount
    if not updated:
        raise InvalidTransition("Release changed concurrently; retry", release_id=release_id)
    audit(actor, "release.transition", entity_type="release", entity_id=release_id,
          from_status=found["status"], to_status=to_status, reason=reason)
