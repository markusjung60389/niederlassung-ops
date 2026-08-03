"""Recurrence scheduling and the worker jobs.

`recurrence`, `last_completed_at` and `next_due_at` were stored but never
evaluated, and `escalation_level` never moved.
"""

from datetime import date, timedelta

import pytest

from app import jobs, models
from app.database import SessionLocal
from app.recurrence import add_months, escalation_for, next_due_date
from tests.conftest import MANAGER, auth, make_record


# --- pure scheduling -------------------------------------------------------


@pytest.mark.parametrize(
    "start,months,expected",
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),  # leap year
        (date(2026, 3, 15), 3, date(2026, 6, 15)),
        (date(2026, 12, 1), 12, date(2027, 12, 1)),
        (date(2026, 10, 31), 4, date(2027, 2, 28)),
    ],
)
def test_add_months_clamps_to_valid_days(start, months, expected):
    assert add_months(start, months) == expected


@pytest.mark.parametrize(
    "recurrence,expected",
    [
        ("monthly", date(2026, 7, 1)),
        ("quarterly", date(2026, 9, 1)),
        ("yearly", date(2027, 6, 1)),
        ("one_time", None),
        ("event_based", None),
    ],
)
def test_next_due_date(recurrence, expected):
    assert next_due_date(date(2026, 6, 1), recurrence) == expected


@pytest.mark.parametrize(
    "days_overdue,expected", [(-5, 0), (0, 0), (1, 1), (6, 1), (7, 2), (34, 5), (900, 5)]
)
def test_escalation_is_derived_not_incremented(days_overdue, expected):
    assert escalation_for(days_overdue) == expected


# --- through the API -------------------------------------------------------


def test_completing_a_recurring_record_schedules_the_next_cycle(client):
    record = make_record(client, due_date="2026-06-01", review_date="2026-06-15", recurrence="yearly")
    assert record["next_due_at"] is None

    updated = client.patch(
        f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"status": "compliant"}
    ).json()

    assert updated["last_completed_at"] is not None
    assert updated["next_due_at"].startswith("2027-06-01")


def test_one_time_records_do_not_reschedule(client):
    record = make_record(client, recurrence="one_time")
    updated = client.patch(
        f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"status": "compliant"}
    ).json()
    assert updated["next_due_at"] is None


def test_worker_reopens_the_record_once_the_next_cycle_is_due(client):
    record = make_record(client, due_date="2026-06-01", review_date="2026-06-15", recurrence="yearly")
    client.patch(
        f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"status": "compliant"}
    )

    with SessionLocal() as db:
        # Nothing happens before the date arrives.
        assert jobs.roll_over_recurring_records(db, today=date(2027, 5, 31)) == 0
        assert jobs.roll_over_recurring_records(db, today=date(2027, 6, 1)) == 1

    rolled = client.get(f"/api/compliance-records/{record['id']}", headers=auth(MANAGER)).json()
    assert rolled["status"] == "open"
    assert rolled["due_date"] == "2027-06-01"
    assert rolled["review_date"] == "2027-06-15"  # offset preserved
    assert rolled["next_due_at"] is None
    assert rolled["last_completed_at"] is not None


def test_roll_over_is_idempotent(client):
    record = make_record(client, due_date="2026-06-01", review_date="2026-06-01", recurrence="quarterly")
    client.patch(
        f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"status": "compliant"}
    )
    with SessionLocal() as db:
        assert jobs.roll_over_recurring_records(db, today=date(2027, 1, 1)) == 1
        assert jobs.roll_over_recurring_records(db, today=date(2027, 1, 1)) == 0


def test_roll_over_is_recorded_in_the_audit_log(client):
    record = make_record(client, due_date="2026-06-01", review_date="2026-06-01", recurrence="yearly")
    client.patch(
        f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"status": "compliant"}
    )
    with SessionLocal() as db:
        jobs.roll_over_recurring_records(db, today=date(2027, 6, 2))

    entries = client.get(
        "/api/audit-log",
        headers=auth(MANAGER),
        params={"entity_type": "compliance_record", "action": "recurrence_rolled_over"},
    ).json()
    assert len(entries) == 1
    assert entries[0]["changes"]["due_date"] == "2027-06-01"
    assert entries[0]["actor_user_id"] is None  # system action


def test_overdue_actions_are_escalated(client):
    record = make_record(client)
    overdue_by = 20
    due = date.today() - timedelta(days=overdue_by)
    action = client.post(
        f"/api/compliance-records/{record['id']}/actions",
        headers=auth(MANAGER),
        json={"title": "Ueberfaellige Massnahme", "owner_user_id": MANAGER, "due_date": due.isoformat()},
    ).json()
    assert action["escalation_level"] == 0

    with SessionLocal() as db:
        assert jobs.escalate_overdue_actions(db) == 1
        # Running again changes nothing.
        assert jobs.escalate_overdue_actions(db) == 0

    with SessionLocal() as db:
        stored = db.get(models.ComplianceAction, action["id"])
        assert stored.escalation_level == escalation_for(overdue_by)


def test_completed_actions_are_not_escalated(client):
    record = make_record(client)
    due = date.today() - timedelta(days=90)
    created = client.post(
        f"/api/compliance-records/{record['id']}/actions",
        headers=auth(MANAGER),
        json={"title": "Erledigt", "owner_user_id": MANAGER, "due_date": due.isoformat()},
    ).json()
    client.patch(f"/api/actions/{created['id']}", headers=auth(MANAGER), json={"status": "done"})

    with SessionLocal() as db:
        assert jobs.escalate_overdue_actions(db) == 0


def test_run_all_reports_what_it_did(client):
    record = make_record(client, due_date="2026-06-01", review_date="2026-06-01", recurrence="monthly")
    client.patch(
        f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"status": "compliant"}
    )
    with SessionLocal() as db:
        result = jobs.run_all(db, today=date(2026, 8, 1))
    assert result.rolled_over == 1
    assert "rolled_over=1" in str(result)
