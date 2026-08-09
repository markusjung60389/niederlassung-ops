"""Deployability: what the function requires against what is on file."""

from datetime import date, timedelta

from app.domain import add_months
from app.readiness import first_aider_target
from tests.conftest import BRANCH, MANAGER, auth

MONTEUR = "jr-monteur"
SERVICE = "jr-service-techniker"
IPAF = "qt-ipaf"
INSTRUCTION = "qt-unterweisung"
PSA = "qt-psa-absturz"
HEALTH = "qt-arbeitsmedizin"


def make_employee_with_role(client, name="Erika Muster", job_role_id=MONTEUR):
    response = client.post(
        "/api/employees",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "full_name": name,
            "role": "Monteur",
            "job_role_id": job_role_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def add_qualification(client, employee_id, type_id, **overrides):
    """Selecting a catalogue entry is enough - title and window come from it."""
    payload = {"employee_id": employee_id, "qualification_type_id": type_id}
    payload.update(overrides)
    response = client.post("/api/employee-qualifications", headers=auth(MANAGER), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def add_evidence_backed(client, employee_id, type_id, **overrides):
    """Every seeded catalogue entry requires a document, so tests that want a
    clean `ok` have to attach one."""
    document = client.post(
        "/api/documents",
        headers=auth(MANAGER),
        files={"file": (f"{type_id}.pdf", b"%PDF-1.4 nachweis", "application/pdf")},
        data={"title": f"Nachweis {type_id}"},
    )
    assert document.status_code == 201, document.text
    return add_qualification(
        client, employee_id, type_id, document_id=document.json()["id"], **overrides
    )


def get_employee(client, employee_id):
    response = client.get(f"/api/employees/{employee_id}", headers=auth(MANAGER))
    assert response.status_code == 200, response.text
    return response.json()


def states_of(employee):
    return {item["qualification_type_id"]: item["state"] for item in employee["requirements"]}


# --- the core question -----------------------------------------------------


def test_employee_without_any_qualification_is_blocked(client):
    employee = make_employee_with_role(client)

    assert employee["readiness"] == "blocked"
    assert employee["due_state"] == "red"
    # Monteur has four mandatory requirements plus three optional ones.
    assert states_of(employee)[IPAF] == "missing"
    assert employee["open_requirements"] == 7


def test_all_mandatory_qualifications_valid_and_evidenced_makes_the_employee_ready(client):
    employee = make_employee_with_role(client)
    far = (date.today() + timedelta(days=900)).isoformat()
    for type_id in (IPAF, INSTRUCTION, PSA, HEALTH):
        add_evidence_backed(client, employee["id"], type_id, valid_until=far)

    refreshed = get_employee(client, employee["id"])
    # Optional requirements stay open but must not affect deployability.
    assert refreshed["readiness"] == "ready"
    assert refreshed["due_state"] == "green"


def test_a_valid_date_without_a_document_is_not_defensible(client):
    """The gap that only shows up during an inspection: green date, no proof."""
    employee = make_employee_with_role(client)
    far = (date.today() + timedelta(days=900)).isoformat()
    for type_id in (IPAF, INSTRUCTION, PSA, HEALTH):
        add_qualification(client, employee["id"], type_id, valid_until=far)

    refreshed = get_employee(client, employee["id"])
    assert states_of(refreshed)[IPAF] == "evidence_missing"
    # It needs attention, but it does not stop the assignment.
    assert refreshed["readiness"] == "limited"
    assert refreshed["due_state"] == "yellow"


def test_expired_mandatory_qualification_blocks(client):
    employee = make_employee_with_role(client)
    far = (date.today() + timedelta(days=900)).isoformat()
    for type_id in (INSTRUCTION, PSA, HEALTH):
        add_qualification(client, employee["id"], type_id, valid_until=far)
    add_qualification(
        client, employee["id"], IPAF, valid_until=(date.today() - timedelta(days=1)).isoformat()
    )

    refreshed = get_employee(client, employee["id"])
    assert refreshed["readiness"] == "blocked"
    assert states_of(refreshed)[IPAF] == "expired"
    assert refreshed["next_due_title"] == "IPAF-Bedienerschulung"


def test_qualification_inside_the_reminder_window_only_limits(client):
    employee = make_employee_with_role(client)
    far = (date.today() + timedelta(days=900)).isoformat()
    for type_id in (INSTRUCTION, PSA, HEALTH):
        add_qualification(client, employee["id"], type_id, valid_until=far)
    # IPAF warns 90 days ahead.
    add_qualification(
        client, employee["id"], IPAF, valid_until=(date.today() + timedelta(days=30)).isoformat()
    )

    refreshed = get_employee(client, employee["id"])
    assert refreshed["readiness"] == "limited"
    assert refreshed["due_state"] == "yellow"
    assert states_of(refreshed)[IPAF] == "expiring"


def test_a_refresher_course_supersedes_the_expired_entry(client):
    """Refreshers are added as new rows; only the longest-valid one counts."""
    employee = make_employee_with_role(client)
    add_evidence_backed(
        client, employee["id"], IPAF, valid_until=(date.today() - timedelta(days=10)).isoformat()
    )
    add_evidence_backed(
        client, employee["id"], IPAF, valid_until=(date.today() + timedelta(days=900)).isoformat()
    )

    assert states_of(get_employee(client, employee["id"]))[IPAF] == "ok"


def test_missing_date_is_not_treated_as_valid(client):
    """A type with a validity period but no expiry date cannot be counted as covered."""
    employee = make_employee_with_role(client)
    add_qualification(client, employee["id"], IPAF)

    refreshed = get_employee(client, employee["id"])
    assert states_of(refreshed)[IPAF] == "undated"
    assert refreshed["readiness"] == "blocked"


def test_departed_employees_are_hidden_and_stop_alarming(client):
    employee = make_employee_with_role(client)
    assert get_employee(client, employee["id"])["readiness"] == "blocked"

    response = client.patch(
        f"/api/employees/{employee['id']}",
        headers=auth(MANAGER),
        json={"status": "inactive", "exit_date": date.today().isoformat()},
    )
    assert response.status_code == 200, response.text

    assert response.json()["due_state"] == "green"
    listed = client.get("/api/employees", headers=auth(MANAGER)).json()
    assert employee["id"] not in [item["id"] for item in listed]
    with_inactive = client.get(
        "/api/employees?include_inactive=true", headers=auth(MANAGER)
    ).json()
    assert employee["id"] in [item["id"] for item in with_inactive]


# --- expiry arithmetic -----------------------------------------------------


def test_expiry_is_derived_from_the_catalogue_validity(client):
    employee = make_employee_with_role(client)
    qualification = add_qualification(
        client, employee["id"], INSTRUCTION, issued_on="2026-03-15"
    )

    # Jaehrliche Unterweisung: twelve months.
    assert qualification["valid_until"] == "2027-03-15"
    # Title and reminder window come from the catalogue too.
    assert qualification["title"] == "Jaehrliche Unterweisung"
    assert qualification["reminder_days"] == 45


def test_an_explicit_expiry_date_wins_over_the_catalogue(client):
    employee = make_employee_with_role(client)
    qualification = add_qualification(
        client, employee["id"], INSTRUCTION, issued_on="2026-03-15", valid_until="2026-09-30"
    )
    assert qualification["valid_until"] == "2026-09-30"


def test_add_months_clamps_to_the_end_of_the_month():
    assert add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert add_months(date(2024, 8, 31), 6) == date(2025, 2, 28)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert add_months(date(2026, 11, 30), 1) == date(2026, 12, 30)


# --- cross-checks ----------------------------------------------------------


def test_vehicle_warns_when_the_assigned_driver_has_no_licence_check(client):
    employee = make_employee_with_role(client, job_role_id=SERVICE)
    response = client.post(
        "/api/vehicles",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "license_plate": "RS-OP 123",
            "assigned_employee_id": employee["id"],
        },
    )
    assert response.status_code == 200, response.text

    vehicles = client.get("/api/vehicles", headers=auth(MANAGER)).json()
    vehicle = vehicles[0]
    assert vehicle["assigned_employee_name"] == "Erika Muster"
    assert "keine Fuehrerscheinkontrolle" in vehicle["driver_alert"]

    add_qualification(
        client,
        employee["id"],
        "qt-fuehrerschein-kontrolle",
        valid_until=(date.today() - timedelta(days=40)).isoformat(),
    )
    vehicle = client.get("/api/vehicles", headers=auth(MANAGER)).json()[0]
    assert "40 Tagen ueberfaellig" in vehicle["driver_alert"]

    add_qualification(
        client,
        employee["id"],
        "qt-fuehrerschein-kontrolle",
        valid_until=(date.today() + timedelta(days=100)).isoformat(),
    )
    assert client.get("/api/vehicles", headers=auth(MANAGER)).json()[0]["driver_alert"] is None


def test_vehicle_traffic_light_follows_the_earliest_overdue_check(client):
    response = client.post(
        "/api/vehicles",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "license_plate": "RS-OP 999",
            "hu_due_date": (date.today() - timedelta(days=3)).isoformat(),
            "service_due_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    vehicle = response.json()
    assert vehicle["due_state"] == "red"
    assert vehicle["next_due_title"] == "Hauptuntersuchung"


def test_first_aider_target_follows_dguv_minimum():
    assert first_aider_target(0) == 0
    assert first_aider_target(2) == 0
    assert first_aider_target(3) == 1
    assert first_aider_target(10) == 1
    assert first_aider_target(11) == 2
    assert first_aider_target(30) == 3


def test_cockpit_reports_deployability_and_first_aiders(client):
    make_employee_with_role(client, "Blockierte Person")
    cockpit = client.get("/api/cockpit", headers=auth(MANAGER)).json()

    assert cockpit["blocked_employees"] == 1
    assert cockpit["first_aiders"]["headcount"] == 1
    assert cockpit["first_aiders"]["required"] == 0
    metric = next(m for m in cockpit["metrics"] if m["label"] == "Nicht einsatzfaehig")
    assert metric["value"] == 1 and metric["state"] == "red"
