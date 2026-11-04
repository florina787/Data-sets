from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import Header

from ..billing.metering import usage_summary
from ..db import SessionLocal

IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)]


def usage_for(user_id: uuid.UUID, feature_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        s = usage_summary(db, user_id)
    f = next(x for x in s["features"] if x["id"] == feature_id)
    return {"feature": feature_id, "plan": s["plan"]["id"], "trial_remaining": f["trial_remaining"],
            "plan_remaining": f["plan_remaining"], "trial_limit": f["trial_limit"]}


def with_usage(result: dict[str, Any], user_id: uuid.UUID, feature_id: str) -> dict[str, Any]:
    return {**result, "_usage": usage_for(user_id, feature_id)}
