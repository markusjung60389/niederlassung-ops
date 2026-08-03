"""Background jobs, run by the worker container and reachable from the tests.

Both jobs are idempotent: running them repeatedly produces the same state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .domain import now_utc, today_local
from .recurrence import COMPLETED_STATUSES, escalation_for, next_due_date

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    rolled_over: int = 0
    escalated: int = 0

    def __str__(self) -> str:
        return f"rolled_over={self.rolled_over} escalated={self.escalated}"


def _audit(db: Session, entity_type: str, entity_id: str, action: str, changes: dict) -> None:
    db.add(
        models.AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=None,  # system action
            changes=changes,
        )
    )


def roll_over_recurring_records(db: Session, *, today: date | None = None) -> int:
    """Reopens completed recurring records once their next cycle is due."""
    current = today or today_local()
    records = db.scalars(
        select(models.ComplianceRecord)
        .where(models.ComplianceRecord.status.in_(sorted(COMPLETED_STATUSES)))
        .where(models.ComplianceRecord.next_due_at.is_not(None))
    ).all()

    rolled = 0
    for record in records:
        next_due = record.next_due_at.date() if record.next_due_at else None
        if next_due is None or next_due > current:
            continue

        previous_due = record.due_date
        interval_days = (next_due - previous_due).days
        record.due_date = next_due
        # Keep the review offset the record was configured with.
        if record.review_date and interval_days > 0:
            record.review_date = record.review_date + (next_due - previous_due)
        record.status = "open"
        record.next_due_at = None
        _audit(
            db,
            "compliance_record",
            record.id,
            "recurrence_rolled_over",
            {"previous_due_date": previous_due.isoformat(), "due_date": next_due.isoformat()},
        )
        rolled += 1

    if rolled:
        db.commit()
    return rolled


def escalate_overdue_actions(db: Session, *, today: date | None = None) -> int:
    """Raises the escalation level of overdue actions, one step per week overdue."""
    current = today or today_local()
    actions = db.scalars(
        select(models.ComplianceAction).where(
            models.ComplianceAction.status.notin_(["done", "cancelled"])
        )
    ).all()

    changed = 0
    for action in actions:
        target = escalation_for((current - action.due_date).days)
        if target != action.escalation_level:
            previous = action.escalation_level
            action.escalation_level = target
            _audit(
                db,
                "compliance_action",
                action.id,
                "escalation_changed",
                {"before": previous, "after": target, "due_date": action.due_date.isoformat()},
            )
            changed += 1

    if changed:
        db.commit()
    return changed


def run_all(db: Session, *, today: date | None = None) -> JobResult:
    result = JobResult(
        rolled_over=roll_over_recurring_records(db, today=today),
        escalated=escalate_overdue_actions(db, today=today),
    )
    logger.info("worker cycle finished at %s: %s", now_utc().isoformat(), result)
    return result


def schedule_next_cycle(record: models.ComplianceRecord) -> None:
    """Called when a record is marked completed: stores the next occurrence."""
    from datetime import datetime, time, timezone

    if record.status not in COMPLETED_STATUSES:
        return
    record.last_completed_at = record.last_completed_at or now_utc()
    upcoming = next_due_date(record.due_date, record.recurrence)
    record.next_due_at = (
        datetime.combine(upcoming, time.min, tzinfo=timezone.utc) if upcoming else None
    )
