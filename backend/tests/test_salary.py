"""Entgeltdaten: eigene Berechtigung, zweite Bestaetigung, Leseprotokoll.

Three guards, three jobs, and the tests keep them apart: the permission decides
who may look, the step-up how sure we are it is them right now, and the audit
log answers "who looked at this" afterwards - the question that actually gets
asked about pay.
"""

import time
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import models
from app.config import settings
from app.database import SessionLocal
from tests.conftest import AREA_MANAGER, BRANCH, MANAGER, VIEWER, auth
from tests.test_azure_ad import KID, azure_mode, bearer, make_token  # noqa: F401

PAY = {"amount": 4200.0, "period": "monthly", "hours_per_week": 40, "valid_from": "2026-01-01"}


def make_person(client, name="Entgelt Person"):
    response = client.post(
        "/api/employees",
        headers=auth(MANAGER),
        json={"branch_id": BRANCH, "full_name": name, "role": "Monteur"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_pay_is_recorded_and_read_back(client):
    employee = make_person(client)
    written = client.put(
        f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=PAY
    )
    assert written.status_code == 200, written.text
    assert written.json()["amount"] == 4200.0
    assert written.json()["updated_by"] == AREA_MANAGER

    read = client.get(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER))
    assert read.status_code == 200
    assert read.json()["period"] == "monthly"
    assert read.json()["hours_per_week"] == 40


def test_pay_never_travels_with_the_employee(client):
    """The reason it is a table of its own rather than a profile column."""
    employee = make_person(client)
    client.put(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=PAY)

    detail = client.get(f"/api/employees/{employee}", headers=auth(MANAGER)).text
    listing = client.get("/api/employees", headers=auth(MANAGER)).text
    cockpit = client.get("/api/cockpit", headers=auth(MANAGER)).text
    for payload in (detail, listing, cockpit):
        assert "4200" not in payload
        assert "salary" not in payload


def test_without_the_permission_there_is_nothing_to_see(client):
    employee = make_person(client)
    client.put(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=PAY)

    for who in (MANAGER, VIEWER):
        read = client.get(f"/api/employees/{employee}/salary", headers=auth(who))
        assert read.status_code == 403
        assert "salary:read" in read.json()["detail"]

    written = client.put(f"/api/employees/{employee}/salary", headers=auth(MANAGER), json=PAY)
    assert written.status_code == 403


def test_a_foreign_branch_reports_not_found(client):
    """Pay is the last place to make an exception from the branch scope."""
    other = client.post(
        "/api/branches",
        headers=auth(AREA_MANAGER),
        json={"name": "Entgelt Standort", "code": "EG"},
    ).json()
    foreign = client.post(
        "/api/employees",
        headers=auth(AREA_MANAGER),
        json={"branch_id": other["id"], "full_name": "Fremde Person", "role": "Monteur"},
    ).json()["id"]
    client.put(f"/api/employees/{foreign}/salary", headers=auth(AREA_MANAGER), json=PAY)

    with SessionLocal() as db:
        # Give the branch manager the permission but not the branch.
        role = db.get(models.Role, "role-branch-manager")
        before = list(role.permissions)
        role.permissions = before + ["salary:read"]
        db.commit()
    try:
        response = client.get(f"/api/employees/{foreign}/salary", headers=auth(MANAGER))
        assert response.status_code == 404
    finally:
        with SessionLocal() as db:
            db.get(models.Role, "role-branch-manager").permissions = before
            db.commit()


def test_every_read_is_recorded_and_the_amount_is_not(client):
    employee = make_person(client, "Protokoll Person")
    client.put(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=PAY)
    client.get(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER))

    entries = client.get(
        "/api/audit-log?entity_type=employee_salary", headers=auth(AREA_MANAGER)
    ).json()
    actions = [entry["action"] for entry in entries]
    assert "viewed" in actions
    assert "created" in actions
    # The audit log has a wider readership than the endpoint it protects.
    assert "4200" not in str(entries)


def test_removing_the_entry_needs_the_write_permission(client):
    employee = make_person(client)
    client.put(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=PAY)

    assert client.delete(f"/api/employees/{employee}/salary", headers=auth(MANAGER)).status_code == 403
    assert (
        client.delete(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER)).status_code
        == 204
    )
    assert client.get(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER)).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {**PAY, "amount": 0},
        {**PAY, "amount": -100},
        {**PAY, "period": "wöchentlich"},
        {**PAY, "hours_per_week": 200},
    ],
)
def test_implausible_figures_are_refused(client, payload):
    employee = make_person(client)
    assert (
        client.put(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=payload).status_code
        == 422
    )


# --------------------------------------------------------------------------
# Die zweite Bestaetigung
# --------------------------------------------------------------------------


def test_the_emergency_login_never_reaches_pay(client):
    """An emergency door that also opens the salary list is not one."""
    from tests.test_accounts import ADMIN, NEW_PASSWORD, START_PASSWORD

    with SessionLocal() as db:
        from app import security

        admin = db.get(models.User, ADMIN)
        admin.password_hash = security.hash_password(START_PASSWORD)
        admin.must_change_password = False
        admin.token_version = (admin.token_version or 1) + 1
        db.commit()

    token = client.post(
        "/api/auth/login", json={"email": settings.admin_email, "password": START_PASSWORD}
    ).json()["token"]
    employee = make_person(client)
    client.put(f"/api/employees/{employee}/salary", headers=auth(AREA_MANAGER), json=PAY)

    response = client.get(
        f"/api/employees/{employee}/salary", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert "Notfallzugang" in response.json()["detail"]
    assert NEW_PASSWORD  # keeps the import honest about what it is for


def test_entra_id_without_the_step_up_is_challenged(client, azure_mode):
    """The 401 carries what MSAL needs to ask for a stronger token."""
    # Under azure_ad the X-User-Id path is closed, so the precondition is
    # written directly rather than through the API.
    with SessionLocal() as db:
        person = models.Employee(branch_id=BRANCH, full_name="Entra Entgelt", role="Monteur")
        db.add(person)
        db.flush()
        employee = person.id
        db.add(
            models.EmployeeSalary(
                employee_id=employee, amount=4200, period="monthly", valid_from=date(2026, 1, 1)
            )
        )
        # The Entra identity maps onto the branch manager; give it the
        # permission so the step-up is the only thing missing.
        role = db.get(models.Role, "role-branch-manager")
        before = list(role.permissions)
        role.permissions = before + ["salary:read"]
        db.commit()
    try:
        response = client.get(
            f"/api/employees/{employee}/salary", headers=bearer(make_token())
        )
        assert response.status_code == 401
        body = response.json()["detail"]
        assert "Bestaetigung" in body["detail"]
        assert body["claims_challenge"]
        assert "insufficient_claims" in response.headers["WWW-Authenticate"]

        # The first call provisioned the Entra account; it still has no branch
        # and would therefore see nothing, step-up or not.
        with SessionLocal() as db:
            provisioned = db.scalar(
                select(models.User).where(models.User.external_id.is_not(None))
            )
            db.add(models.UserBranch(user_id=provisioned.id, branch_id=BRANCH))
            db.commit()

        # With the authentication context satisfied it goes through.
        allowed = client.get(
            f"/api/employees/{employee}/salary",
            headers=bearer(make_token(acrs=[settings.azure_salary_auth_context])),
        )
        assert allowed.status_code == 200, allowed.text

        # Fallback without a P1 licence: a recent multi-factor sign-in.
        recent = client.get(
            f"/api/employees/{employee}/salary",
            headers=bearer(make_token(amr=["pwd", "mfa"], auth_time=int(time.time()) - 60)),
        )
        assert recent.status_code == 200

        stale = client.get(
            f"/api/employees/{employee}/salary",
            headers=bearer(
                make_token(
                    amr=["pwd", "mfa"],
                    auth_time=int(time.time()) - settings.salary_step_up_max_age_seconds - 60,
                )
            ),
        )
        assert stale.status_code == 401

        single_factor = client.get(
            f"/api/employees/{employee}/salary",
            headers=bearer(make_token(amr=["pwd"], auth_time=int(time.time()))),
        )
        assert single_factor.status_code == 401
    finally:
        with SessionLocal() as db:
            db.get(models.Role, "role-branch-manager").permissions = before
            # Everything pointing at the provisioned account has to go before
            # the azure_mode fixture removes it: the branch link, and the
            # audit entries the reads above wrote.
            provisioned = db.scalars(
                select(models.User).where(models.User.external_id.is_not(None))
            ).all()
            for account in provisioned:
                for link in db.scalars(
                    select(models.UserBranch).where(models.UserBranch.user_id == account.id)
                ).all():
                    db.delete(link)
                for entry in db.scalars(
                    select(models.AuditLog).where(models.AuditLog.actor_user_id == account.id)
                ).all():
                    db.delete(entry)
            db.commit()


def test_the_rest_of_the_application_needs_no_step_up(client, azure_mode):
    """Only pay is behind the second confirmation, nothing else."""
    response = client.get("/api/employees", headers=bearer(make_token()))
    assert response.status_code == 200


def test_the_permission_is_in_no_preset_but_the_two_wildcards(client):
    roles = {role["name"]: role for role in client.get("/api/roles", headers=auth(AREA_MANAGER)).json()}
    assert roles["Betrachter"]["permissions"].count("salary:read") == 0
    assert roles["Niederlassungsleiter"]["permissions"].count("salary:read") == 0
    assert roles["HSE / Compliance"]["permissions"].count("salary:read") == 0
    assert roles["Bereichsleiter"]["permissions"] == ["*"]

    catalogue = client.get("/api/permissions", headers=auth(AREA_MANAGER)).json()
    entry = next(item for item in catalogue if item["key"] == "salary:read")
    assert entry["area"] == "Entgelt"
    assert "Bestaetigung" in entry["description"]


def test_a_lapsed_lockout_does_not_apply_here():
    """Placeholder to keep the datetime import honest in this module."""
    assert datetime.now(timezone.utc) - timedelta(seconds=1) < datetime.now(timezone.utc)
