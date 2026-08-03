"""Shared request helpers: auditing, referential checks and JSON coercion."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .auth import Principal


def jsonable(value: Any) -> Any:
    """Audit payloads land in a JSON column, so dates and decimals need coercing."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    changes: dict,
    principal: Principal | None = None,
) -> None:
    db.add(
        models.AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=principal.user_id if principal else None,
            changes=jsonable(changes),
        )
    )


def snapshot(instance: Any) -> dict:
    """Full row contents, used so a delete leaves a record of what was removed."""
    return {
        column.name: jsonable(getattr(instance, column.name))
        for column in instance.__table__.columns
    }


def ensure_ref(db: Session, model: type, value: str | None, label: str) -> None:
    """Rejects references to rows that do not exist.

    Without this, SQLite silently stores dangling ids while PostgreSQL raises an
    IntegrityError, so the same request behaves differently per environment.
    """
    if value is None:
        return
    if db.get(model, value) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label} '{value}' does not exist"
        )


def ensure_refs(db: Session, payload: dict, references: dict[str, type]) -> None:
    for field, model in references.items():
        if field in payload:
            ensure_ref(db, model, payload[field], field)


def guard_children(
    db: Session, children: Iterable[tuple[type, str, str]], parent_id: str
) -> None:
    """Blocks a delete that would orphan dependent rows.

    `children` holds (model, foreign key attribute, human readable label).
    """
    blocking: list[str] = []
    for model, attribute, label in children:
        count = db.scalar(
            select(func.count()).select_from(model).where(getattr(model, attribute) == parent_id)
        )
        if count:
            blocking.append(f"{count} {label}")
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete while dependent records exist: "
                + ", ".join(blocking)
                + ". Remove or reassign them first."
            ),
        )


def get_or_404(db: Session, model: type, entity_id: str, label: str) -> Any:
    instance = db.get(model, entity_id)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return instance
