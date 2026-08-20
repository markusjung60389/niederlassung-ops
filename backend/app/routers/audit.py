from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import CurrentPrincipal, requires
from ..database import get_db

router = APIRouter(tags=["audit"])


@router.get(
    "/api/audit-log",
    response_model=list[schemas.AuditLogRead],
    dependencies=[Depends(requires(permissions.AUDIT_READ))],
)
def list_audit_log(
    principal: CurrentPrincipal,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    actor_user_id: str | None = None,
    branch_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> list[models.AuditLog]:
    query = select(models.AuditLog).order_by(models.AuditLog.created_at.desc())
    # Group-wide events (branch_id is NULL - a role, a catalogue entry, a user
    # account) stay visible to everyone with audit:read. Events tied to a
    # branch are scoped the same way the entity itself is: without this, a
    # reader with legitimate audit:read for their own branch could read the
    # delete snapshot of an employee - permit and health dates included - from
    # a branch they have no other access to.
    allowed = principal.scope(branch_id)
    if allowed is not None:
        query = query.where(
            or_(models.AuditLog.branch_id.is_(None), models.AuditLog.branch_id.in_(allowed or ["-"]))
        )
    if entity_type:
        query = query.where(models.AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(models.AuditLog.entity_id == entity_id)
    if action:
        query = query.where(models.AuditLog.action == action)
    if actor_user_id:
        query = query.where(models.AuditLog.actor_user_id == actor_user_id)
    return db.scalars(query.limit(limit).offset(offset)).all()
