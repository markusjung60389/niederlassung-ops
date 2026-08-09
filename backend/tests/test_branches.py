"""Several branches: who sees what, exceptions, moving vehicles, rules.

The scoping tests are deliberately blunt - "A must not see B" for every list
there is. That is the property a branch manager cannot check for himself and
the one a data protection officer asks about first.
"""

from datetime import date, timedelta

from app.database import SessionLocal
from app import models
from tests.conftest import AREA_MANAGER, BRANCH, MANAGER, auth

def make_branch(client, name="Solingen", code="SG"):
    """Creates a second branch as the area manager and returns its id.

    Written through the API rather than the session so the audit entry and the
    permission check are exercised too.
    """
    existing = client.get("/api/branches", headers=auth(AREA_MANAGER)).json()
    match = next((item for item in existing if item["name"] == name), None)
    if match:
        return match["id"]
    response = client.post(
        "/api/branches",
        headers=auth(AREA_MANAGER),
        json={"name": name, "code": code, "location": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def employee_in(client, branch_id, name="Kollege Auswaerts", actor=AREA_MANAGER):
    response = client.post(
        "/api/employees",
        headers=auth(actor),
        json={
            "branch_id": branch_id,
            "full_name": name,
            "role": "Monteur",
            "job_role_id": "jr-monteur",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def vehicle_in(client, branch_id, plate="RS-AB 123", actor=AREA_MANAGER):
    response = client.post(
        "/api/vehicles",
        headers=auth(actor),
        json={"branch_id": branch_id, "license_plate": plate},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


def test_a_branch_manager_does_not_see_another_branch(client):
    other = make_branch(client)
    employee_in(client, other, "Fremde Person")
    vehicle_in(client, other, "SG-XY 999")

    names = [item["full_name"] for item in client.get("/api/employees", headers=auth(MANAGER)).json()]
    assert "Fremde Person" not in names

    plates = [item["license_plate"] for item in client.get("/api/vehicles", headers=auth(MANAGER)).json()]
    assert "SG-XY 999" not in plates

    branches = [item["id"] for item in client.get("/api/branches", headers=auth(MANAGER)).json()]
    assert other not in branches
    assert BRANCH in branches


def test_reading_a_foreign_employee_reports_not_found(client):
    other = make_branch(client)
    foreign = employee_in(client, other, "Nicht Meine")

    response = client.get(f"/api/employees/{foreign['id']}", headers=auth(MANAGER))
    assert response.status_code == 404


def test_the_area_manager_sees_every_branch(client):
    other = make_branch(client)
    employee_in(client, other, "Fremde Person")

    names = [
        item["full_name"] for item in client.get("/api/employees", headers=auth(AREA_MANAGER)).json()
    ]
    assert "Fremde Person" in names


def test_selecting_a_branch_outside_the_scope_returns_nothing_not_everything(client):
    """The dangerous failure mode: an ignored filter showing all branches."""
    other = make_branch(client)
    employee_in(client, other, "Fremde Person")
    employee_in(client, BRANCH, "Eigene Person", actor=MANAGER)

    response = client.get(f"/api/employees?branch_id={other}", headers=auth(MANAGER))
    assert response.status_code == 200
    assert response.json() == []


def test_the_bootstrap_only_lists_the_callers_branches(client):
    """It drives the branch switcher: an entry there is an entry one may open."""
    other = make_branch(client)
    mine = client.get("/api/bootstrap", headers=auth(MANAGER)).json()
    assert [item["id"] for item in mine["branches"]] == [BRANCH]

    theirs = client.get("/api/bootstrap", headers=auth(AREA_MANAGER)).json()
    assert other in [item["id"] for item in theirs["branches"]]


def test_actions_of_another_branch_stay_invisible(client):
    other = make_branch(client)
    record = client.post(
        "/api/compliance-records",
        headers=auth(AREA_MANAGER),
        json={
            "title": "Fremde Pflicht",
            "category": "training_instruction",
            "branch_id": other,
            "owner_user_id": AREA_MANAGER,
            "legal_basis": "ArbSchG",
            "control_type": "training",
            "due_date": date.today().isoformat(),
            "review_date": date.today().isoformat(),
        },
    ).json()
    client.post(
        f"/api/compliance-records/{record['id']}/actions",
        headers=auth(AREA_MANAGER),
        json={
            "title": "Fremde Massnahme",
            "owner_user_id": AREA_MANAGER,
            "due_date": date.today().isoformat(),
        },
    )

    mine = client.get("/api/actions", headers=auth(MANAGER)).json()
    assert "Fremde Massnahme" not in [item["title"] for item in mine]
    theirs = client.get("/api/actions", headers=auth(AREA_MANAGER)).json()
    assert "Fremde Massnahme" in [item["title"] for item in theirs]


def test_creating_in_a_foreign_branch_is_refused(client):
    other = make_branch(client)
    response = client.post(
        "/api/employees",
        headers=auth(MANAGER),
        json={"branch_id": other, "full_name": "Schmuggelware", "role": "Monteur"},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Deployments
# --------------------------------------------------------------------------


def test_a_deployment_makes_the_person_visible_in_the_second_branch(client):
    other = make_branch(client)
    employee = employee_in(client, BRANCH, "Wander Arbeiter", actor=MANAGER)

    assigned = client.post(
        f"/api/employees/{employee['id']}/branches",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other, "note": "Unterstuetzung Montage"},
    )
    assert assigned.status_code == 200, assigned.text
    assert sorted(assigned.json()["branch_ids"]) == sorted([BRANCH, other])

    listed = client.get(f"/api/employees?branch_id={other}", headers=auth(AREA_MANAGER)).json()
    assert "Wander Arbeiter" in [item["full_name"] for item in listed]

    # Readiness is reported per branch, so the receiving manager sees what the
    # person may do *here*.
    row = next(item for item in listed if item["full_name"] == "Wander Arbeiter")
    assert other in row["readiness_by_branch"]

    removed = client.delete(
        f"/api/employees/{employee['id']}/branches/{other}", headers=auth(AREA_MANAGER)
    )
    assert removed.status_code == 200
    assert removed.json()["branch_ids"] == [BRANCH]


def test_the_home_branch_cannot_be_added_as_a_deployment(client):
    employee = employee_in(client, BRANCH, "Doppelt Gemoppelt", actor=MANAGER)
    response = client.post(
        f"/api/employees/{employee['id']}/branches",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH},
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Vehicles on the move
# --------------------------------------------------------------------------


def test_a_vehicle_on_loan_is_listed_where_it_stands(client):
    other = make_branch(client)
    vehicle = vehicle_in(client, BRANCH, "RS-LO 100", actor=MANAGER)

    moved = client.post(
        f"/api/vehicles/{vehicle['id']}/relocate",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other, "note": "Aushilfe Baustelle"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["location_branch_id"] == other
    # The home branch keeps it on its books.
    assert moved.json()["branch_id"] == BRANCH

    here = client.get(f"/api/vehicles?branch_id={BRANCH}", headers=auth(AREA_MANAGER)).json()
    there = client.get(f"/api/vehicles?branch_id={other}", headers=auth(AREA_MANAGER)).json()
    assert "RS-LO 100" not in [item["license_plate"] for item in here]
    assert "RS-LO 100" in [item["license_plate"] for item in there]


def test_a_permanent_move_changes_the_home_branch(client):
    other = make_branch(client)
    vehicle = vehicle_in(client, BRANCH, "RS-PE 200", actor=MANAGER)

    moved = client.post(
        f"/api/vehicles/{vehicle['id']}/relocate",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other, "permanent": True},
    ).json()
    assert moved["branch_id"] == other
    assert moved["current_branch_id"] is None


def test_a_loaned_vehicle_comes_home_again(client):
    other = make_branch(client)
    vehicle = vehicle_in(client, BRANCH, "RS-HO 300", actor=MANAGER)

    client.post(
        f"/api/vehicles/{vehicle['id']}/relocate",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other},
    )
    back = client.post(
        f"/api/vehicles/{vehicle['id']}/relocate", headers=auth(AREA_MANAGER), json={}
    ).json()
    assert back["current_branch_id"] is None
    assert back["location_branch_id"] == BRANCH


def test_a_branch_manager_cannot_hand_a_vehicle_to_a_branch_they_do_not_run(client):
    other = make_branch(client)
    vehicle = vehicle_in(client, BRANCH, "RS-NO 400", actor=MANAGER)

    response = client.post(
        f"/api/vehicles/{vehicle['id']}/relocate",
        headers=auth(MANAGER),
        json={"branch_id": other},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------


def requirement_id(client, job_role_id="jr-monteur", code="ipaf"):
    roles = client.get("/api/job-roles", headers=auth(MANAGER)).json()
    role = next(item for item in roles if item["id"] == job_role_id)
    return next(item["id"] for item in role["requirements"] if item["qualification_code"] == code)


def test_an_exception_lifts_the_requirement_in_that_branch_only(client):
    other = make_branch(client)
    requirement = requirement_id(client)
    employee = employee_in(client, BRANCH, "Ohne IPAF", actor=MANAGER)

    before = client.get(f"/api/employees/{employee['id']}?branch_id={BRANCH}", headers=auth(MANAGER)).json()
    assert any(item["code"] == "ipaf" for item in before["requirements"])

    created = client.post(
        "/api/requirement-overrides",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "requirement_id": requirement,
            "mode": "excluded",
            "reason": "Keine Hubarbeitsbuehnen im Einsatz",
        },
    )
    assert created.status_code == 201, created.text

    after = client.get(f"/api/employees/{employee['id']}?branch_id={BRANCH}", headers=auth(MANAGER)).json()
    assert not any(item["code"] == "ipaf" for item in after["requirements"])

    # Another branch keeps the requirement: an exception does not travel.
    elsewhere = client.get(
        f"/api/employees/{employee['id']}?branch_id={other}", headers=auth(AREA_MANAGER)
    ).json()
    assert any(item["code"] == "ipaf" for item in elsewhere["requirements"])

    client.delete(f"/api/requirement-overrides/{created.json()['id']}", headers=auth(MANAGER))


def test_an_exception_needs_a_reason(client):
    requirement = requirement_id(client)
    response = client.post(
        "/api/requirement-overrides",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH, "requirement_id": requirement, "mode": "excluded", "reason": "x"},
    )
    assert response.status_code == 422


def test_the_area_manager_sees_a_new_exception_and_can_revoke_it(client):
    requirement = requirement_id(client)
    created = client.post(
        "/api/requirement-overrides",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "requirement_id": requirement,
            "mode": "excluded",
            "reason": "Uebergangsweise ausgesetzt",
        },
    ).json()

    register = client.get("/api/requirement-overrides", headers=auth(AREA_MANAGER)).json()
    entry = next(item for item in register if item["id"] == created["id"])
    assert entry["acknowledged_at"] is None
    assert entry["reason"] == "Uebergangsweise ausgesetzt"

    portfolio = client.get("/api/portfolio", headers=auth(AREA_MANAGER)).json()
    row = next(item for item in portfolio if item["branch_id"] == BRANCH)
    assert row["new_exceptions"] == 1

    acknowledged = client.post(
        f"/api/requirement-overrides/{created['id']}/acknowledge", headers=auth(AREA_MANAGER)
    ).json()
    assert acknowledged["acknowledged_at"] is not None

    revoked = client.post(
        f"/api/requirement-overrides/{created['id']}/revoke",
        headers=auth(AREA_MANAGER),
        json={"reason": "Buehnen sind wieder im Einsatz"},
    ).json()
    # A grace period rather than immediately: the branch gets time to comply.
    assert date.fromisoformat(revoked["revoked_effective_from"]) > date.today()
    assert revoked["active"] is True

    client.delete(f"/api/requirement-overrides/{created['id']}", headers=auth(MANAGER))


def test_a_branch_manager_cannot_revoke_an_exception(client):
    requirement = requirement_id(client)
    created = client.post(
        "/api/requirement-overrides",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "requirement_id": requirement,
            "mode": "excluded",
            "reason": "Selbst gesetzt",
        },
    ).json()

    response = client.post(
        f"/api/requirement-overrides/{created['id']}/revoke",
        headers=auth(MANAGER),
        json={"reason": "Doch nicht"},
    )
    assert response.status_code == 403
    client.delete(f"/api/requirement-overrides/{created['id']}", headers=auth(MANAGER))


def test_a_revoked_exception_stops_applying_once_it_takes_effect(client):
    requirement = requirement_id(client)
    employee = employee_in(client, BRANCH, "Nach Widerruf", actor=MANAGER)
    created = client.post(
        "/api/requirement-overrides",
        headers=auth(MANAGER),
        json={
            "branch_id": BRANCH,
            "requirement_id": requirement,
            "mode": "excluded",
            "reason": "Zunaechst ausgesetzt",
        },
    ).json()
    client.post(
        f"/api/requirement-overrides/{created['id']}/revoke",
        headers=auth(AREA_MANAGER),
        json={"reason": "Gilt wieder", "effective_from": (date.today() - timedelta(days=1)).isoformat()},
    )

    after = client.get(f"/api/employees/{employee['id']}?branch_id={BRANCH}", headers=auth(MANAGER)).json()
    assert any(item["code"] == "ipaf" for item in after["requirements"])

    client.delete(f"/api/requirement-overrides/{created['id']}", headers=auth(MANAGER))


# --------------------------------------------------------------------------
# Compliance rules
# --------------------------------------------------------------------------


def make_rule(client, branch_id=None, title="Jaehrliche Unterweisung", actor=AREA_MANAGER):
    response = client.post(
        "/api/compliance-rules",
        headers=auth(actor),
        json={
            "title": title,
            "category": "training_instruction",
            "control_type": "training",
            "recurrence": "yearly",
            "legal_basis": "DGUV Vorschrift 1 Paragraf 4",
            "branch_id": branch_id,
            "first_due_date": (date.today() + timedelta(days=60)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_group_rule_gives_every_branch_its_own_record(client):
    other = make_branch(client)
    rule = make_rule(client)

    assert sorted(rule["branch_ids"]) == sorted([BRANCH, other])
    assert rule["record_count"] == 2

    here = client.get(f"/api/compliance-records?branch_id={BRANCH}", headers=auth(MANAGER)).json()
    mine = [item for item in here if item["title"] == "Jaehrliche Unterweisung"]
    assert len(mine) == 1
    assert mine[0]["owner_user_id"]


def test_a_branch_manager_cannot_declare_a_group_rule(client):
    response = client.post(
        "/api/compliance-rules",
        headers=auth(MANAGER),
        json={
            "title": "Fuer alle",
            "category": "training_instruction",
            "control_type": "training",
            "legal_basis": "ArbSchG",
            "first_due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 403

    own = make_rule(client, branch_id=BRANCH, title="Nur Remscheid", actor=MANAGER)
    assert own["branch_ids"] == [BRANCH]


def test_a_local_rule_is_promoted_to_the_whole_group(client):
    other = make_branch(client)
    rule = make_rule(client, branch_id=BRANCH, title="Erst lokal", actor=MANAGER)

    preview = client.post(
        f"/api/compliance-rules/{rule['id']}/scope-preview",
        headers=auth(AREA_MANAGER),
        json={"branch_id": None},
    ).json()
    assert preview["creates_in"] == ["Solingen"]
    assert preview["detaches_in"] == []

    promoted = client.post(
        f"/api/compliance-rules/{rule['id']}/scope",
        headers=auth(AREA_MANAGER),
        json={"branch_id": None, "first_due_date": (date.today() + timedelta(days=90)).isoformat()},
    ).json()
    assert promoted["branch_id"] is None
    assert sorted(promoted["branch_ids"]) == sorted([BRANCH, other])


def test_demoting_a_group_rule_leaves_the_other_branches_their_work(client):
    """The point of the whole exercise: nothing disappears with the scope."""
    other = make_branch(client)
    rule = make_rule(client, title="Erst fuer alle")
    records = client.get("/api/compliance-records", headers=auth(AREA_MANAGER)).json()
    elsewhere = next(
        item for item in records if item["branch_id"] == other and item["title"] == "Erst fuer alle"
    )

    demoted = client.post(
        f"/api/compliance-rules/{rule['id']}/scope",
        headers=auth(AREA_MANAGER),
        json={"branch_id": BRANCH},
    ).json()
    assert demoted["branch_ids"] == [BRANCH]

    # The other branch's record is still there, with its own rule now.
    kept = client.get(f"/api/compliance-records/{elsewhere['id']}", headers=auth(AREA_MANAGER))
    assert kept.status_code == 200
    assert kept.json()["rule_id"] != rule["id"]

    rules = client.get(f"/api/compliance-rules?branch_id={other}", headers=auth(AREA_MANAGER)).json()
    local = next(item for item in rules if item["title"] == "Erst fuer alle" and item["branch_id"] == other)
    assert local["record_count"] == 1


def test_deleting_a_rule_keeps_the_records(client):
    rule = make_rule(client, branch_id=BRANCH, title="Wird geloescht", actor=MANAGER)
    response = client.delete(f"/api/compliance-rules/{rule['id']}", headers=auth(MANAGER))
    assert response.status_code == 204

    records = client.get("/api/compliance-records", headers=auth(MANAGER)).json()
    kept = next(item for item in records if item["title"] == "Wird geloescht")
    assert kept["rule_id"] is None


def test_correcting_a_rule_reaches_every_branch(client):
    make_branch(client)
    rule = make_rule(client, title="Falsche Grundlage")
    updated = client.patch(
        f"/api/compliance-rules/{rule['id']}",
        headers=auth(AREA_MANAGER),
        json={"legal_basis": "DGUV Vorschrift 1 Paragraf 4 Absatz 1"},
    )
    assert updated.status_code == 200, updated.text

    records = client.get("/api/compliance-records", headers=auth(AREA_MANAGER)).json()
    affected = [item for item in records if item["title"] == "Falsche Grundlage"]
    assert affected
    assert all(item["legal_basis"] == "DGUV Vorschrift 1 Paragraf 4 Absatz 1" for item in affected)


# --------------------------------------------------------------------------
# Portfolio
# --------------------------------------------------------------------------


def test_the_portfolio_reports_one_row_per_branch(client):
    other = make_branch(client)
    employee_in(client, BRANCH, "Ohne Nachweise", actor=MANAGER)

    rows = client.get("/api/portfolio", headers=auth(AREA_MANAGER)).json()
    by_branch = {row["branch_id"]: row for row in rows}
    assert set(by_branch) == {BRANCH, other}

    home = by_branch[BRANCH]
    assert home["headcount"] == 1
    # Nothing on file for a Monteur: not deployable, and the branch is red.
    assert home["blocked"] == 1
    assert home["state"] == "red"

    # The branch manager only ever sees their own row.
    own = client.get("/api/portfolio", headers=auth(MANAGER)).json()
    assert [row["branch_id"] for row in own] == [BRANCH]


def test_a_deployed_employee_counts_once(client):
    other = make_branch(client)
    employee = employee_in(client, BRANCH, "Nur einmal", actor=MANAGER)
    client.post(
        f"/api/employees/{employee['id']}/branches",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other},
    )

    rows = {row["branch_id"]: row for row in client.get("/api/portfolio", headers=auth(AREA_MANAGER)).json()}
    assert rows[BRANCH]["headcount"] == 1
    assert rows[other]["headcount"] == 0


def test_the_second_branch_survives_a_restart_of_the_seed(client):
    """The seed must not touch branches it did not create."""
    other = make_branch(client)
    with SessionLocal() as db:
        from app.seed import seed_base_data

        seed_base_data(db)
        assert db.get(models.Branch, other) is not None


def test_promoting_a_local_rule_does_not_move_the_original_record(client):
    """The record it started with stays in its branch, and only there."""
    other = make_branch(client)
    rule = make_rule(client, branch_id=BRANCH, title="Bleibt in Remscheid", actor=MANAGER)
    client.post(
        f"/api/compliance-rules/{rule['id']}/scope",
        headers=auth(AREA_MANAGER),
        json={"branch_id": None, "first_due_date": (date.today() + timedelta(days=90)).isoformat()},
    )

    here = client.get(f"/api/compliance-records?branch_id={BRANCH}", headers=auth(AREA_MANAGER)).json()
    there = client.get(f"/api/compliance-records?branch_id={other}", headers=auth(AREA_MANAGER)).json()
    assert [item["title"] for item in here].count("Bleibt in Remscheid") == 1
    assert [item["title"] for item in there].count("Bleibt in Remscheid") == 1
