from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import models as M

log = logging.getLogger("sherin.audit")


def audit(db: Session, actor: str, role: str, action: str, entity: str, entity_id: str, **detail) -> None:
    db.add(M.AuditLog(actor=actor, role=role, action=action, entity=entity, entity_id=str(entity_id), detail=detail))
    log.info("audit", extra={"actor": actor, "role": role, "action": action, "entity": entity, "entity_id": entity_id})
