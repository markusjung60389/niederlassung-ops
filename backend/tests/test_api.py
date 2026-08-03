"""Regression tests for the defects found in the codebase review."""

from datetime import date, timedelta

from tests.conftest import BRANCH, MANAGER, VIEWER, auth, make_employee, make_record


def _add_qualification(client, employee_id, valid_until, reminder_days=30, title="IPAF Schein"):
    response = client.post(
        "/api/employee-qualifications",
        headers=auth(MANAGER),
        json={
            "employee_id": employee_id,
            "title": title,
            "qualification_type": "training",
            "valid_until": valid_until.isoformat(),
            "reminder_days": reminder_days,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- expired qualifications ------------------------------------------------


def test_expired_qualification_appears_in_cockpit(client):
    """Previously filtered out by within_days(), which drops every past date."""
    employee_id = make_employee(client)
    _add_qualification(client, employee_id, date(2020, 1, 1))

    cockpit = client.get("/api/cockpit", headers=auth(MANAGER)).json()
    titles = [item["title"] for item in cockpit["expiring_qualifications"]]
    assert "IPAF Schein" in titles

    metric = next(m for m in cockpit["metrics"] if m["label"] == "Expiring qualifications")
    assert metric["value"] == 1
    assert metric["state"] == "red"


def test_upcoming_qualification_is_yellow_not_red(client):
    employee_id = make_employee(client)
    _add_qualification(client, employee_id, date.today() + timedelta(days=10))

    cockpit = client.get("/api/cockpit", headers=auth(MANAGER)).json()
    metric = next(m for m in cockpit["metrics"] if m["label"] == "Expiring qualifications")
    assert metric["value"] == 1
    assert metric["state"] == "yellow"


def test_distant_qualification_is_not_reported(client):
    employee_id = make_employee(client)
    _add_qualification(client, employee_id, date.today() + timedelta(days=400))

    cockpit = client.get("/api/cockpit", headers=auth(MANAGER)).json()
    assert cockpit["expiring_qualifications"] == []


# --- qualification reminders ----------------------------------------------


def test_qualifications_produce_reminders(client):
    """Reminders previously ignored the employee_qualifications table entirely."""
    employee_id = make_employee(client, "Max Muster")
    _add_qualification(client, employee_id, date(2020, 1, 1))

    reminders = client.get("/api/reminders", headers=auth(MANAGER)).json()
    entries = [item for item in reminders if item["source_type"] == "employee_qualification"]
    assert len(entries) == 1
    assert entries[0]["state"] == "red"
    assert "Max Muster" in entries[0]["title"]


def test_reminder_days_is_honoured_per_qualification(client):
    """reminder_days was stored and validated but never used."""
    employee_id = make_employee(client)
    due = date.today() + timedelta(days=100)
    _add_qualification(client, employee_id, due, reminder_days=7, title="Kurzfrist")
    _add_qualification(client, employee_id, due, reminder_days=365, title="Langfrist")

    reminders = client.get("/api/reminders", headers=auth(MANAGER)).json()
    titles = " ".join(item["title"] for item in reminders)
    assert "Langfrist" in titles
    assert "Kurzfrist" not in titles


# --- referential integrity -------------------------------------------------


def test_compliance_record_rejects_unknown_branch(client):
    response = client.post(
        "/api/compliance-records",
        headers=auth(MANAGER),
        json={
            "title": "Fehlerhafter Datensatz",
            "category": "training_instruction",
            "branch_id": "DOES-NOT-EXIST",
            "owner_user_id": MANAGER,
            "legal_basis": "DGUV Vorschrift 1",
            "control_type": "training",
            "due_date": "2026-12-01",
            "review_date": "2026-12-01",
        },
    )
    assert response.status_code == 400
    assert "branch_id" in response.json()["detail"]


def test_compliance_record_rejects_unknown_owner(client):
    response = client.post(
        "/api/compliance-records",
        headers=auth(MANAGER),
        json={
            "title": "Fehlerhafter Datensatz",
            "category": "training_instruction",
            "branch_id": BRANCH,
            "owner_user_id": "ghost",
            "legal_basis": "DGUV Vorschrift 1",
            "control_type": "training",
            "due_date": "2026-12-01",
            "review_date": "2026-12-01",
        },
    )
    assert response.status_code == 400
    assert "owner_user_id" in response.json()["detail"]


def test_employee_rejects_unknown_branch(client):
    response = client.post(
        "/api/employees",
        headers=auth(MANAGER),
        json={"branch_id": "NOPE", "full_name": "Max Muster", "role": "Techniker"},
    )
    assert response.status_code == 400


def test_vehicle_rejects_unknown_assignee(client):
    response = client.post(
        "/api/vehicles",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH, "license_plate": "RS-AB-1", "assigned_employee_id": "ghost"},
    )
    assert response.status_code == 400


def test_qualification_rejects_unknown_employee(client):
    response = client.post(
        "/api/employee-qualifications",
        headers=auth(MANAGER),
        json={"employee_id": "ghost", "title": "Schein", "qualification_type": "training"},
    )
    assert response.status_code == 400


# --- audit trail -----------------------------------------------------------


def test_employee_creation_is_audited_with_the_real_actor(client):
    employee_id = make_employee(client)
    entries = client.get(
        "/api/audit-log", headers=auth(MANAGER), params={"entity_type": "employee", "entity_id": employee_id}
    ).json()
    assert len(entries) == 1
    assert entries[0]["action"] == "created"
    assert entries[0]["actor_user_id"] == MANAGER


def test_qualification_creation_is_audited(client):
    employee_id = make_employee(client)
    qualification = _add_qualification(client, employee_id, date(2027, 1, 1))
    entries = client.get(
        "/api/audit-log",
        headers=auth(MANAGER),
        params={"entity_type": "employee_qualification", "entity_id": qualification["id"]},
    ).json()
    assert len(entries) == 1


def test_record_update_audit_survives_json_serialisation(client):
    """The 'before' snapshot holds date objects, which are not JSON by default."""
    record = make_record(client)
    response = client.patch(
        f"/api/compliance-records/{record['id']}",
        headers=auth(MANAGER),
        json={"due_date": "2027-03-03", "status": "in_progress"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["due_date"] == "2027-03-03"

    entries = client.get(
        "/api/audit-log",
        headers=auth(MANAGER),
        params={"entity_type": "compliance_record", "entity_id": record["id"]},
    ).json()
    updated = next(item for item in entries if item["action"] == "updated")
    assert updated["changes"]["before"]["due_date"] == "2026-12-01"
    assert updated["changes"]["after"]["due_date"] == "2027-03-03"


# --- data minimisation -----------------------------------------------------


def test_cockpit_hides_personnel_data_without_permission(client):
    """A fleet-only reader must not receive names and permit dates."""
    from app import models
    from app.database import SessionLocal

    employee_id = make_employee(client, "Geheim Person")
    _add_qualification(client, employee_id, date(2020, 1, 1))

    with SessionLocal() as db:
        role = db.get(models.Role, "role-viewer")
        original = list(role.permissions)
        role.permissions = ["compliance:read", "fleet:read"]
        db.commit()
    try:
        cockpit = client.get("/api/cockpit", headers=auth(VIEWER)).json()
        assert cockpit["expiring_qualifications"] == []
        assert all("Geheim Person" not in item["title"] for item in cockpit["reminders"])
        assert client.get("/api/employees", headers=auth(VIEWER)).status_code == 403
    finally:
        with SessionLocal() as db:
            db.get(models.Role, "role-viewer").permissions = original
            db.commit()


def test_dev_user_directory_is_hidden_outside_dev_mode(client, monkeypatch):
    from app import main

    assert client.get("/api/auth/dev-users").status_code == 200
    monkeypatch.setattr(main.settings, "auth_mode", "azure_ad")
    assert client.get("/api/auth/dev-users").status_code == 404
