from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import requires
from ..database import get_db

router = APIRouter(tags=["audit"])


@router.get(
    "/api/audit-log",
    response_model=list[schemas.AuditLogRead],
    dependencies=[Depends(requires(permissions.AUDIT_READ))],
)
def list_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    actor_user_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> list[models.AuditLog]:
    query = select(models.AuditLog).order_by(models.AuditLog.created_at.desc())
    if entity_type:
        query = query.where(models.AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(models.AuditLog.entity_id == entity_id)
    if action:
        query = query.where(models.AuditLog.action == action)
    if actor_user_id:
        query = query.where(models.AuditLog.actor_user_id == actor_user_id)
    return db.scalars(query.limit(limit).offset(offset)).all()
