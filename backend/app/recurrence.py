"""Scheduling of recurring compliance controls.

``recurrence``, ``last_completed_at`` and ``next_due_at`` were stored but never
evaluated, so a control marked compliant stayed done forever. Completing a
recurring record now schedules the next cycle, and the worker rolls it over
once that date arrives.
"""

from __future__ import annotations

import calendar
from datetime import date

MONTHS_PER_RECURRENCE: dict[str, int] = {
    "monthly": 1,
    "quarterly": 3,
    "yearly": 12,
}

# These never schedule themselves; they are driven by an external trigger.
NON_RECURRING = {"one_time", "event_based"}

COMPLETED_STATUSES = {"compliant", "waived"}


def add_months(start: date, months: int) -> date:
    """Adds months, clamping to the last valid day (31 Jan + 1 month = 28/29 Feb)."""
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_due_date(current: date, recurrence: str) -> date | None:
    """The next occurrence after `current`, or None when it does not repeat."""
    months = MONTHS_PER_RECURRENCE.get(recurrence)
    if months is None or recurrence in NON_RECURRING:
        return None
    return add_months(current, months)


def escalation_for(days_overdue: int, *, step_days: int = 7, maximum: int = 5) -> int:
    """Escalation level derived purely from how long an action is overdue.

    Deriving it instead of incrementing keeps the job idempotent: running it
    twice in a row cannot inflate the level.
    """
    if days_overdue <= 0:
        return 0
    return min(maximum, days_overdue // step_days + 1)
