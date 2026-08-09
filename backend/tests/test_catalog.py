"""Catalogue, functions, requirement matrix and compliance templates."""

from datetime import date, timedelta

from tests.conftest import AREA_MANAGER, BRANCH, MANAGER, VIEWER, auth
from tests.test_readiness import (
    HEALTH,
    IPAF,
    INSTRUCTION,
    MONTEUR,
    add_evidence_backed,
    make_employee_with_role,
)


def test_the_seeded_catalogue_covers_the_remscheid_functions(client):
    roles = client.get("/api/job-roles", headers=auth(MANAGER)).json()
    by_name = {role["name"]: role for role in roles}

    assert set(by_name) == {"Projektleiter", "Service-Techniker", "Monteur"}

    service = by_name["Service-Techniker"]
    mandatory = {item["qualification_code"] for item in service["requirements"] if item["mandatory"]}
    assert {"ipaf", "psa_absturz", "fuehrerschein_kontrolle", "unterweisung_allgemein"} <= mandatory

    monteur = by_name["Monteur"]
    optional = {item["qualification_code"] for item in monteur["requirements"] if not item["mandatory"]}
    # A fitter does not have to drive, but may.
    assert "fuehrerschein" in optional


def test_driver_licence_check_is_a_recurring_qualification(client):
    """Explicitly confirmed as a six-month cycle with a document."""
    types = client.get("/api/qualification-types", headers=auth(MANAGER)).json()
    check = next(item for item in types if item["code"] == "fuehrerschein_kontrolle")

    assert check["validity_months"] == 6
    assert check["evidence_required"] is True
    assert "StVG" in check["legal_basis"]


def test_a_branch_can_add_its_own_qualification_and_require_it(client):
    created = client.post(
        "/api/qualification-types",
        headers=auth(MANAGER),
        json={
            "code": "gabelstapler",
            "name": "Flurfoerderzeug-Schein",
            "category": "training",
            "validity_months": 12,
            "reminder_days": 30,
            # The branch's own entry. Without a branch it would be a group-wide
            # obligation, which the branch manager may not declare.
            "branch_id": BRANCH,
        },
    )
    assert created.status_code == 201, created.text
    type_id = created.json()["id"]

    linked = client.post(
        "/api/job-role-requirements",
        headers=auth(MANAGER),
        json={"job_role_id": MONTEUR, "qualification_type_id": type_id, "mandatory": True},
    )
    assert linked.status_code == 201, linked.text
    assert linked.json()["qualification_name"] == "Flurfoerderzeug-Schein"

    employee = make_employee_with_role(client)
    codes = {item["code"] for item in employee["requirements"]}
    assert "gabelstapler" in codes

    # Cleanup keeps the shared catalogue usable for the next test.
    client.delete(f"/api/job-role-requirements/{linked.json()['id']}", headers=auth(MANAGER))
    client.delete(f"/api/qualification-types/{type_id}", headers=auth(MANAGER))


def test_the_same_requirement_cannot_be_added_twice(client):
    duplicate = client.post(
        "/api/job-role-requirements",
        headers=auth(AREA_MANAGER),
        json={"job_role_id": MONTEUR, "qualification_type_id": IPAF},
    )
    assert duplicate.status_code == 409


def test_a_branch_manager_cannot_change_the_group_matrix(client):
    """The group requirements are the area manager's; the branch takes an
    exception instead, which is visible and revocable."""
    response = client.post(
        "/api/job-role-requirements",
        headers=auth(MANAGER),
        json={"job_role_id": MONTEUR, "qualification_type_id": HEALTH},
    )
    assert response.status_code == 403
    assert "rule:write" in response.json()["detail"]


def test_a_qualification_type_in_use_cannot_be_deleted(client):
    response = client.delete(f"/api/qualification-types/{IPAF}", headers=auth(MANAGER))
    assert response.status_code == 409
    assert "requirement" in response.json()["detail"]


def test_matrix_shows_only_the_types_some_function_requires(client):
    employee = make_employee_with_role(client)
    add_evidence_backed(
        client,
        employee["id"],
        INSTRUCTION,
        valid_until=(date.today() + timedelta(days=900)).isoformat(),
    )

    matrix = client.get("/api/qualification-matrix", headers=auth(MANAGER)).json()
    codes = {item["code"] for item in matrix["qualification_types"]}
    # Monteur requires seven; nothing requires "befaehigte_person" here.
    assert "befaehigte_person" not in codes
    assert "ipaf" in codes

    row = next(item for item in matrix["rows"] if item["employee_id"] == employee["id"])
    assert row["job_role_name"] == "Monteur"
    assert row["readiness"] == "blocked"

    cells = {cell["qualification_type_id"]: cell for cell in row["cells"]}
    assert cells[INSTRUCTION]["state"] == "ok"
    assert cells[IPAF]["state"] == "missing"
    assert cells[IPAF]["mandatory"] is True


def test_compliance_templates_are_offered_for_the_standard_obligations(client):
    templates = client.get("/api/compliance-templates", headers=auth(MANAGER)).json()
    keys = {item["key"] for item in templates}

    assert {"gefaehrdungsbeurteilung", "unterweisung_jaehrlich", "dguv_v3_ortsveraenderlich"} <= keys
    risk = next(item for item in templates if item["key"] == "gefaehrdungsbeurteilung")
    assert risk["legal_basis"].startswith("ArbSchG")
    assert risk["recurrence"] == "yearly"


def test_readers_cannot_change_the_catalogue(client):
    response = client.post(
        "/api/qualification-types",
        headers=auth(VIEWER),
        json={"code": "x_test", "name": "Unerlaubt"},
    )
    assert response.status_code == 403


def test_a_function_with_employees_cannot_be_deleted(client):
    make_employee_with_role(client)
    response = client.delete(f"/api/job-roles/{MONTEUR}", headers=auth(MANAGER))
    assert response.status_code == 409
    assert "employee" in response.json()["detail"]
