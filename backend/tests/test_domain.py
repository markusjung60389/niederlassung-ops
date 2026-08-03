from datetime import date, timedelta

from app.domain import due_state, is_overdue, within_days


def test_expired_or_non_compliant_records_are_red():
    today = date(2026, 6, 30)
    assert due_state("non_compliant", today + timedelta(days=30), today=today) == "red"
    assert due_state("open", today - timedelta(days=1), today=today) == "red"
    assert is_overdue("open", today - timedelta(days=1), today=today) is True


def test_due_soon_records_are_yellow():
    today = date(2026, 6, 30)
    due = today + timedelta(days=14)
    assert due_state("in_progress", due, today=today) == "yellow"
    assert within_days(due, 30, today=today) is True


def test_compliant_future_records_are_green():
    today = date(2026, 6, 30)
    assert due_state("compliant", today + timedelta(days=1), today=today) == "green"
    assert is_overdue("compliant", today + timedelta(days=1), today=today) is False
