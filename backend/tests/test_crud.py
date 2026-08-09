"""Editing and deleting, and the resources that previously had no API at all."""

import pytest

from tests.conftest import BRANCH, MANAGER, VIEWER, auth, make_account, make_employee, make_record


# --- corrections and deletions --------------------------------------------


def test_vehicle_can_be_corrected_and_removed(client):
    created = client.post(
        "/api/vehicles", headers=auth(MANAGER), json={"branch_id": BRANCH, "license_plate": "RS-XX-999"}
    ).json()

    patched = client.patch(
        f"/api/vehicles/{created['id']}", headers=auth(MANAGER), json={"license_plate": "RS-AB-123"}
    )
    assert patched.status_code == 200
    assert patched.json()["license_plate"] == "RS-AB-123"

    assert client.delete(f"/api/vehicles/{created['id']}", headers=auth(MANAGER)).status_code == 204
    assert client.get(f"/api/vehicles/{created['id']}", headers=auth(MANAGER)).status_code == 404


def test_employee_can_be_corrected_and_removed(client):
    employee_id = make_employee(client, "Falsch Geschrieben")
    patched = client.patch(
        f"/api/employees/{employee_id}", headers=auth(MANAGER), json={"full_name": "Richtig Geschrieben"}
    )
    assert patched.json()["full_name"] == "Richtig Geschrieben"
    assert client.delete(f"/api/employees/{employee_id}", headers=auth(MANAGER)).status_code == 204


def test_incident_and_assessment_can_be_corrected(client):
    incident = client.post(
        "/api/incidents",
        headers=auth(MANAGER),
        json={
            "type": "near_miss",
            "severity": "medium",
            "occurred_at": "2026-05-01T10:00:00Z",
            "branch_id": BRANCH,
            "summary": "Beinaheunfall an der Hebebuehne",
            "owner_user_id": MANAGER,
        },
    ).json()
    assert client.patch(
        f"/api/incidents/{incident['id']}", headers=auth(MANAGER), json={"root_cause": "Sicherung fehlte"}
    ).json()["root_cause"] == "Sicherung fehlte"

    assessment = client.post(
        "/api/branch-assessments",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH, "title": "Q1 Bestandsaufnahme", "assessment_date": "2026-03-01"},
    ).json()
    assert client.patch(
        f"/api/branch-assessments/{assessment['id']}", headers=auth(MANAGER), json={"title": "Q1 Bestandsaufnahme korrigiert"}
    ).json()["title"] == "Q1 Bestandsaufnahme korrigiert"
    assert client.delete(f"/api/branch-assessments/{assessment['id']}", headers=auth(MANAGER)).status_code == 204


def test_delete_writes_the_full_row_into_the_audit_log(client):
    created = client.post(
        "/api/vehicles",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH, "license_plate": "RS-ZZ-1", "brand": "Ford"},
    ).json()
    client.delete(f"/api/vehicles/{created['id']}", headers=auth(MANAGER))

    entries = client.get(
        "/api/audit-log", headers=auth(MANAGER), params={"entity_type": "vehicle", "entity_id": created["id"]}
    ).json()
    deleted = next(entry for entry in entries if entry["action"] == "deleted")
    assert deleted["changes"]["license_plate"] == "RS-ZZ-1"
    assert deleted["changes"]["brand"] == "Ford"
    assert deleted["actor_user_id"] == MANAGER


def test_delete_is_blocked_while_dependants_exist(client):
    employee_id = make_employee(client)
    client.post(
        "/api/vehicles",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH, "license_plate": "RS-DD-1", "assigned_employee_id": employee_id},
    )
    response = client.delete(f"/api/employees/{employee_id}", headers=auth(MANAGER))
    assert response.status_code == 409
    assert "assigned vehicle" in response.json()["detail"]


def test_deleting_a_record_removes_its_children(client):
    record = make_record(client)
    client.post(
        f"/api/compliance-records/{record['id']}/actions",
        headers=auth(MANAGER),
        json={"title": "Massnahme", "owner_user_id": MANAGER, "due_date": "2026-11-01"},
    )
    assert client.delete(f"/api/compliance-records/{record['id']}", headers=auth(MANAGER)).status_code == 204
    assert client.get("/api/actions", headers=auth(MANAGER)).json() == []


def test_viewer_cannot_delete(client):
    created = client.post(
        "/api/vehicles", headers=auth(MANAGER), json={"branch_id": BRANCH, "license_plate": "RS-RO-1"}
    ).json()
    assert client.delete(f"/api/vehicles/{created['id']}", headers=auth(VIEWER)).status_code == 403


# --- sales and service, previously unreachable ----------------------------


def test_sales_data_stays_reachable_through_the_api(client):
    """The sales screens are gone; the data behind them is not.

    Accounts, opportunities and service contracts keep their tables and their
    endpoints, so nothing recorded so far is lost - the branch simply does not
    work in them here any more.
    """
    account = make_account(client)
    created = client.post(
        "/api/opportunities",
        headers=auth(MANAGER),
        json={"account_id": account["id"], "title": "Chance", "expected_volume": 10000},
    )
    assert created.status_code == 201, created.text

    listed = client.get("/api/opportunities", headers=auth(MANAGER)).json()
    assert "Chance" in [item["title"] for item in listed]


def test_the_cockpit_no_longer_reports_sales_figures(client):
    cockpit = client.get("/api/cockpit", headers=auth(MANAGER)).json()
    labels = [metric["label"] for metric in cockpit["metrics"]]
    assert not any("Pipeline" in label for label in labels)
    assert "Service faellig" not in labels


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/accounts", {"name": "Neuer Kunde", "branch_id": BRANCH}),
        ("/api/projects", {"name": "Neues Projekt"}),
        ("/api/tasks", {"title": "Neue Aufgabe"}),
    ],
)
def test_generic_resources_support_the_full_lifecycle(client, path, payload):
    created = client.post(path, headers=auth(MANAGER), json=payload)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    assert client.get(f"{path}/{item_id}", headers=auth(MANAGER)).status_code == 200
    assert len(client.get(path, headers=auth(MANAGER)).json()) == 1
    assert client.delete(f"{path}/{item_id}", headers=auth(MANAGER)).status_code == 204
    assert client.get(f"{path}/{item_id}", headers=auth(MANAGER)).status_code == 404


def test_generic_resources_validate_references(client):
    response = client.post(
        "/api/opportunities", headers=auth(MANAGER), json={"account_id": "ghost", "title": "Chance"}
    )
    assert response.status_code == 400
    assert "account_id" in response.json()["detail"]


def test_generic_resources_are_audited(client):
    account = make_account(client, name="Auditkunde")
    entries = client.get(
        "/api/audit-log", headers=auth(MANAGER), params={"entity_type": "account", "entity_id": account["id"]}
    ).json()
    assert [entry["action"] for entry in entries] == ["created"]


def test_account_delete_is_blocked_by_opportunities(client):
    account = make_account(client)
    client.post(
        "/api/opportunities",
        headers=auth(MANAGER),
        json={"account_id": account["id"], "title": "Offen", "expected_volume": 1000},
    )
    response = client.delete(f"/api/accounts/{account['id']}", headers=auth(MANAGER))
    assert response.status_code == 409


def test_sales_needs_its_own_permission(client):
    from app import models
    from app.database import SessionLocal

    with SessionLocal() as db:
        role = db.get(models.Role, "role-viewer")
        original = list(role.permissions)
        role.permissions = ["compliance:read"]
        db.commit()
    try:
        assert client.get("/api/accounts", headers=auth(VIEWER)).status_code == 403
    finally:
        with SessionLocal() as db:
            db.get(models.Role, "role-viewer").permissions = original
            db.commit()


def test_list_endpoints_are_paginated(client):
    for index in range(5):
        make_account(client, name=f"Kunde {index:02d}")
    page = client.get("/api/accounts", headers=auth(MANAGER), params={"limit": 2, "offset": 0}).json()
    assert len(page) == 2
    second = client.get("/api/accounts", headers=auth(MANAGER), params={"limit": 2, "offset": 2}).json()
    assert {item["id"] for item in page}.isdisjoint({item["id"] for item in second})
