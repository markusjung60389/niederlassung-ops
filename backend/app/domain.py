from datetime import date, datetime, timedelta, timezone


RISK_RED_STATUSES = {"expired", "non_compliant"}
RISK_GREEN_STATUSES = {"compliant", "waived"}


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
    if due_date is None:
        return False
    current = today or today_utc()
    return current <= due_date <= current + timedelta(days=days)
