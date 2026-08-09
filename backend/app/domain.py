from datetime import date, datetime, timedelta, timezone

from .config import settings


RISK_RED_STATUSES = {"expired", "non_compliant"}
RISK_GREEN_STATUSES = {"compliant", "waived"}

# Window used for reminders that carry no explicit per-record window.
DEFAULT_REMINDER_WINDOW_DAYS = 60
# Window for the "due soon" cockpit bucket.
DUE_SOON_DAYS = 30


def today_local() -> date:
    """Today in the configured branch timezone.

    Due dates are calendar dates for a German branch; deriving them from UTC
    flips the traffic light up to two hours early during CEST.
    """
    return datetime.now(settings.timezone).date()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def add_months(start: date, months: int) -> date:
    """`start` shifted by whole months, clamped to the end of the target month.

    A course taken on 31.08. with a six-month validity expires on 28.02., not
    on an invalid 31.02. Written out rather than pulling in dateutil for one
    calculation.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    if month == 12:
        last_day = 31
    else:
        last_day = (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(start.day, last_day))


def due_state(status: str, due_date: date | None, *, today: date | None = None) -> str:
    current = today or today_local()
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
    current = today or today_local()
    return status in RISK_RED_STATUSES or (due_date is not None and due_date < current)


def within_days(due_date: date | None, days: int, *, today: date | None = None) -> bool:
    """True when `due_date` falls inside the next `days` days. Past dates are excluded."""
    if due_date is None:
        return False
    current = today or today_local()
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
