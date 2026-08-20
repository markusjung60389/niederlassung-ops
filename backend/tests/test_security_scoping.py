"""Item-level access across branches.

The list endpoints were already filtered by branch (see test_branches.py);
these tests cover the gap next to them - GET/PATCH/DELETE by id, which used
to skip the check entirely as long as the caller held the permission at all.
A branch manager who knew or guessed another branch's id could read, edit or
delete its compliance records, evidence, incidents, assessments, employees,
qualifications, profiles and documents, and read every branch's audit log.
"""

from datetime import date, timedelta

from tests.conftest import AREA_MANAGER, BRANCH, MANAGER, auth, make_account, make_record
from tests.test_branches import employee_in, make_branch
from tests.test_uploads import PDF, upload_evidence


def foreign_record(client, branch_id, **overrides):
    payload = {
        "title": "Fremde Pflicht",
        "category": "training_instruction",
        "branch_id": branch_id,
        "owner_user_id": AREA_MANAGER,
        "legal_basis": "ArbSchG",
        "control_type": "training",
        "due_date": date.today().isoformat(),
        "review_date": date.today().isoformat(),
    }
    payload.update(overrides)
    response = client.post("/api/compliance-records", headers=auth(AREA_MANAGER), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Compliance records, evidence, actions
# --------------------------------------------------------------------------


def test_a_foreign_compliance_record_is_not_found_by_id(client):
    other = make_branch(client)
    record = foreign_record(client, other)

    assert client.get(f"/api/compliance-records/{record['id']}", headers=auth(MANAGER)).status_code == 404
    assert (
        client.patch(
            f"/api/compliance-records/{record['id']}", headers=auth(MANAGER), json={"priority": "high"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/compliance-records/{record['id']}", headers=auth(MANAGER)).status_code == 404


def test_a_foreign_evidence_item_is_not_reachable(client):
    other = make_branch(client)
    record = foreign_record(client, other)
    evidence = upload_evidence(client, record["id"], user=AREA_MANAGER).json()

    assert (
        client.get(f"/api/evidence/{evidence['id']}/download", headers=auth(MANAGER)).status_code == 404
    )
    assert client.delete(f"/api/evidence/{evidence['id']}", headers=auth(MANAGER)).status_code == 404
    # The area manager who owns the branch is unaffected.
    assert (
        client.get(f"/api/evidence/{evidence['id']}/download", headers=auth(AREA_MANAGER)).status_code
        == 200
    )


def test_a_foreign_action_cannot_be_added_updated_or_deleted(client):
    other = make_branch(client)
    record = foreign_record(client, other)

    added = client.post(
        f"/api/compliance-records/{record['id']}/actions",
        headers=auth(MANAGER),
        json={"title": "Einschleusen", "owner_user_id": MANAGER, "due_date": date.today().isoformat()},
    )
    assert added.status_code == 404

    action = client.post(
        f"/api/compliance-records/{record['id']}/actions",
        headers=auth(AREA_MANAGER),
        json={"title": "Massnahme", "owner_user_id": AREA_MANAGER, "due_date": date.today().isoformat()},
    ).json()

    assert (
        client.patch(
            f"/api/actions/{action['id']}", headers=auth(MANAGER), json={"status": "done"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/actions/{action['id']}", headers=auth(MANAGER)).status_code == 404


# --------------------------------------------------------------------------
# Incidents and branch assessments
# --------------------------------------------------------------------------


def test_a_foreign_incident_is_refused_on_write_and_read(client):
    other = make_branch(client)
    created = client.post(
        "/api/incidents",
        headers=auth(MANAGER),
        json={
            "type": "incident",
            "severity": "high",
            "occurred_at": "2026-01-01T08:00:00Z",
            "branch_id": other,
            "summary": "Einschleusen",
            "owner_user_id": MANAGER,
        },
    )
    assert created.status_code == 403

    incident = client.post(
        "/api/incidents",
        headers=auth(AREA_MANAGER),
        json={
            "type": "incident",
            "severity": "high",
            "occurred_at": "2026-01-01T08:00:00Z",
            "branch_id": other,
            "summary": "Fremder Vorfall",
            "owner_user_id": AREA_MANAGER,
        },
    ).json()

    assert client.get(f"/api/incidents/{incident['id']}", headers=auth(MANAGER)).status_code == 404
    assert (
        client.patch(
            f"/api/incidents/{incident['id']}", headers=auth(MANAGER), json={"severity": "low"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/incidents/{incident['id']}", headers=auth(MANAGER)).status_code == 404


def test_a_foreign_branch_assessment_is_refused_on_write_and_read(client):
    other = make_branch(client)
    created = client.post(
        "/api/branch-assessments",
        headers=auth(MANAGER),
        json={"branch_id": other, "title": "Einschleusen", "assessment_date": date.today().isoformat()},
    )
    assert created.status_code == 403

    assessment = client.post(
        "/api/branch-assessments",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other, "title": "Fremde Bewertung", "assessment_date": date.today().isoformat()},
    ).json()

    assert (
        client.get(f"/api/branch-assessments/{assessment['id']}", headers=auth(MANAGER)).status_code == 404
    )
    assert (
        client.patch(
            f"/api/branch-assessments/{assessment['id']}", headers=auth(MANAGER), json={"notes": "x"}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/branch-assessments/{assessment['id']}", headers=auth(MANAGER)).status_code
        == 404
    )


# --------------------------------------------------------------------------
# Employees, qualifications, profiles
# --------------------------------------------------------------------------


def test_a_foreign_employee_cannot_be_updated_or_deleted(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")

    assert (
        client.patch(
            f"/api/employees/{foreign['id']}", headers=auth(MANAGER), json={"full_name": "Umbenannt"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/employees/{foreign['id']}", headers=auth(MANAGER)).status_code == 404


def test_a_qualification_cannot_be_recorded_for_a_foreign_employee(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")

    response = client.post(
        "/api/employee-qualifications",
        headers=auth(MANAGER),
        json={"employee_id": foreign["id"], "title": "Schein", "qualification_type": "training"},
    )
    assert response.status_code == 404


def test_a_foreign_employees_qualification_cannot_be_changed_or_deleted(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")
    qualification = client.post(
        "/api/employee-qualifications",
        headers=auth(AREA_MANAGER),
        json={"employee_id": foreign["id"], "title": "Schein", "qualification_type": "training"},
    ).json()

    assert (
        client.patch(
            f"/api/employee-qualifications/{qualification['id']}",
            headers=auth(MANAGER),
            json={"title": "Manipuliert"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/employee-qualifications/{qualification['id']}", headers=auth(MANAGER)
        ).status_code
        == 404
    )
    # And it stays out of the plain list too, not only the by-id routes.
    titles = [
        item["title"]
        for item in client.get("/api/employee-qualifications", headers=auth(MANAGER)).json()
    ]
    assert "Schein" not in titles


def test_a_foreign_employee_profile_cannot_be_created_or_deleted(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")

    created = client.post(
        "/api/employee-profiles",
        headers=auth(MANAGER),
        json={"employee_id": foreign["id"], "contract_type": "unbefristet"},
    )
    assert created.status_code == 404

    profile = client.post(
        "/api/employee-profiles",
        headers=auth(AREA_MANAGER),
        json={"employee_id": foreign["id"], "contract_type": "unbefristet"},
    ).json()
    assert (
        client.delete(f"/api/employee-profiles/{profile['id']}", headers=auth(MANAGER)).status_code == 404
    )


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


def test_an_unlinked_document_stays_with_its_uploader(client):
    document = client.post(
        "/api/documents",
        headers=auth(AREA_MANAGER),
        files={"file": ("attest.pdf", PDF, "application/pdf")},
        data={"title": "Aerztliches Attest"},
    ).json()

    titles = [item["title"] for item in client.get("/api/documents", headers=auth(MANAGER)).json()]
    assert "Aerztliches Attest" not in titles
    assert (
        client.get(f"/api/documents/{document['id']}/download", headers=auth(MANAGER)).status_code == 404
    )


def test_a_document_linked_to_a_foreign_employee_stays_invisible(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")
    document = client.post(
        "/api/documents",
        headers=auth(AREA_MANAGER),
        files={"file": ("attest.pdf", PDF, "application/pdf")},
        data={"title": "Aerztliches Attest"},
    ).json()
    client.post(
        "/api/employee-qualifications",
        headers=auth(AREA_MANAGER),
        json={
            "employee_id": foreign["id"],
            "title": "Schein",
            "qualification_type": "training",
            "document_id": document["id"],
        },
    )

    assert (
        client.get(f"/api/documents/{document['id']}/download", headers=auth(MANAGER)).status_code == 404
    )


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------


def test_audit_log_hides_entries_from_a_branch_the_reader_cannot_see(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")
    client.delete(f"/api/employees/{foreign['id']}", headers=auth(AREA_MANAGER))

    entries = client.get("/api/audit-log?entity_type=employee", headers=auth(MANAGER)).json()
    assert foreign["id"] not in [item["entity_id"] for item in entries]

    theirs = client.get("/api/audit-log?entity_type=employee", headers=auth(AREA_MANAGER)).json()
    assert foreign["id"] in [item["entity_id"] for item in theirs]


def test_audit_log_still_shows_group_wide_events_to_a_branch_reader(client):
    """NULL branch_id (a role, a catalogue entry) stays visible to everyone
    with audit:read - only branch-scoped rows are filtered."""
    client.patch(
        "/api/qualification-types/qt-erste-hilfe",
        headers=auth(AREA_MANAGER),
        json={"validity_months": 30},
    )
    entries = client.get(
        "/api/audit-log?entity_type=qualification_type&entity_id=qt-erste-hilfe", headers=auth(MANAGER)
    ).json()
    assert any(item["action"] == "updated" for item in entries)


# --------------------------------------------------------------------------
# Hermes context
# --------------------------------------------------------------------------


def test_hermes_context_is_refused_for_a_foreign_branch(client):
    other = make_branch(client)
    response = client.get(f"/api/hermes/context/branches/{other}", headers=auth(MANAGER))
    assert response.status_code == 403

    own = client.get(f"/api/hermes/context/branches/{BRANCH}", headers=auth(MANAGER))
    assert own.status_code == 200
    assert own.json()["reminders"] is not None


# --------------------------------------------------------------------------
# Generic CRUD (accounts, employee reviews)
# --------------------------------------------------------------------------


def test_a_foreign_account_is_not_reachable_by_id(client):
    other = make_branch(client)
    account = client.post(
        "/api/accounts", headers=auth(AREA_MANAGER), json={"name": "Fremdkunde", "branch_id": other}
    ).json()

    assert client.get(f"/api/accounts/{account['id']}", headers=auth(MANAGER)).status_code == 404
    names = [item["name"] for item in client.get("/api/accounts", headers=auth(MANAGER)).json()]
    assert "Fremdkunde" not in names


def test_an_account_cannot_be_moved_into_a_branch_the_caller_lacks(client):
    other = make_branch(client)
    mine = make_account(client, name="Meiner")
    response = client.patch(
        f"/api/accounts/{mine['id']}", headers=auth(MANAGER), json={"branch_id": other}
    )
    assert response.status_code == 403


def test_a_review_of_a_foreign_employee_is_not_reachable(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")
    review = client.post(
        "/api/employee-reviews",
        headers=auth(AREA_MANAGER),
        json={"employee_id": foreign["id"], "review_date": date.today().isoformat(), "summary": "Gut"},
    ).json()

    assert client.get(f"/api/employee-reviews/{review['id']}", headers=auth(MANAGER)).status_code == 404
