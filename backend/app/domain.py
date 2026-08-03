from datetime import date, datetime, timedelta, timezone


RISK_RED_STATUSES = {"expired", "non_compliant"}
RISK_GREEN_STATUSES = {"compliant", "waived"}

# Window used for reminders that carry no explicit per-record window.
DEFAULT_REMINDER_WINDOW_DAYS = 60
# Window for the "due soon" cockpit bucket.
DUE_SOON_DAYS = 30


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def due_state(status: str, due_date: date | None, *, today: date | None = None) -> str:
    current = today or today_utc()
    if status in RISK_RED_STATUSES:
        return "red"
    if due_date is not None and due_date < current:
        return "red"
    if status in RISK_GREEN_STATUSES:
        return "green"
    if due_date is not None and due_date <= current + timedelta(days=30):
        return "yellow"
    return "green"


def is_overdue(status: str, due_date: date | None, *, today: date | None = None) -> bool:
    current = today or today_utc()
    return status in RISK_RED_STATUSES or (due_date is not None and due_date < current)


def within_days(due_date: date | None, days: int, *, today: date | None = None) -> bool:
    """True when `due_date` falls inside the next `days` days. Past dates are excluded."""
    if due_date is None:
        return False
    current = today or today_utc()
    return current <= due_date <= current + timedelta(days=days)


def needs_attention(
    due_date: date | None, days: int, *, status: str = "open", today: date | None = None
) -> bool:
    """True when a date is already overdue or comes due inside the window.

    `within_days` alone silently drops everything in the past, which is exactly
    the set that matters most for expiring qualifications and permits.
    """
    if due_date is None:
        return False
    return is_overdue(status, due_date, today=today) or within_days(due_date, days, today=today)
