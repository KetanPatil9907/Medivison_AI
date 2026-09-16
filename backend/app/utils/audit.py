import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.analytics import AuditLog


def write_audit_log(
    db: Session,
    user: User | int | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    before: dict | None = None,
    after: dict | None = None,
    meta: dict | None = None,
    success: bool = True,
) -> None:
    user_id = None
    if user is not None:
        user_id = user.id if isinstance(user, User) else user

    ip = None
    ua = None
    if request is not None:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip,
        user_agent=ua,
        before=json.dumps(before) if before else None,
        after=json.dumps(after) if after else None,
        meta=json.dumps(meta) if meta else None,
        success=success,
    )
    db.add(entry)
    db.commit()