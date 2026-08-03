from datetime import date, timedelta

from app.domain import due_state, is_overdue, needs_attention, within_days


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


def test_within_days_excludes_the_past():
    today = date(2026, 6, 30)
    assert within_days(today - timedelta(days=1), 30, today=today) is False


def test_needs_attention_covers_overdue_and_upcoming():
    today = date(2026, 6, 30)
    assert needs_attention(today - timedelta(days=900), 30, today=today) is True
    assert needs_attention(today, 30, today=today) is True
    assert needs_attention(today + timedelta(days=30), 30, today=today) is True
    assert needs_attention(today + timedelta(days=31), 30, today=today) is False
    assert needs_attention(None, 30, today=today) is False
