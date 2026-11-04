from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent
from ..security.sanitize import redact_obj


def audit(db: Session, user_id: uuid.UUID | None, actor: str, action: str, target: str | None = None,
          detail: dict[str, Any] | None = None, severity: str = "info", commit: bool = True) -> None:
    db.add(AuditEvent(user_id=user_id, actor=actor[:60], action=action[:80], target=(target or None) and target[:200],
                      detail=redact_obj(detail or {}), severity=severity))
    if commit:
        db.commit()
