"""Benutzerverwaltung: Anmeldung mit Passwort, Konten, Rollen, Berechtigungen.

The password login is the emergency door beside Entra ID, so the tests care
about the two things that make it safe rather than merely convenient: the start
password cannot stay in use, and a caller cannot lock the tool for everyone by
editing their own account.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app import models, security
from app.config import settings
from app.database import SessionLocal
from tests.conftest import AREA_MANAGER, BRANCH, MANAGER, VIEWER, auth

ADMIN = "user-admin"
START_PASSWORD = settings.admin_initial_password
NEW_PASSWORD = "Werkzeug-Kiste-2026!"


@pytest.fixture(autouse=True)
def reset_admin():
    """Puts the emergency account back to its freshly seeded state.

    The suite shares one database, and the tests below deliberately change the
    admin password - without this, the second one would fail on the first.
    """
    with SessionLocal() as db:
        admin = db.get(models.User, ADMIN)
        admin.password_hash = security.hash_password(START_PASSWORD)
        admin.must_change_password = True
        admin.failed_login_count = 0
        admin.locked_until = None
        admin.token_version = 1
        admin.is_active = True
        db.commit()
    yield


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client, email: str = settings.admin_email, password: str = START_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def signed_in(client) -> str:
    """Logs in and gets the start password out of the way; returns the token."""
    token = login(client).json()["token"]
    response = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={"current_password": START_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


# --------------------------------------------------------------------------
# Anmeldung
# --------------------------------------------------------------------------


def test_the_emergency_account_exists_and_signs_in(client):
    response = login(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["must_change_password"] is True
    assert body["token"]

    me = client.get("/api/auth/me", headers=bearer(body["token"])).json()
    assert me["source"] == "password"
    assert me["role_name"] == "Administrator"
    assert me["must_change_password"] is True


def test_the_start_password_blocks_everything_until_it_is_changed(client):
    """The whole point of handing one out: it cannot quietly stay in use."""
    token = login(client).json()["token"]

    blocked = client.get("/api/employees", headers=bearer(token))
    assert blocked.status_code == 403
    assert "Startpasswort" in blocked.json()["detail"]

    changed = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={"current_password": START_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False

    allowed = client.get("/api/employees", headers=bearer(changed.json()["token"]))
    assert allowed.status_code == 200


def test_changing_the_password_ends_the_previous_sessions(client):
    token = login(client).json()["token"]
    client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={"current_password": START_PASSWORD, "new_password": NEW_PASSWORD},
    )
    # The token that performed the change is retired with all the others; the
    # response carried a fresh one.
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_a_wrong_password_is_indistinguishable_from_an_unknown_account(client):
    wrong = login(client, password="falsch")
    unknown = login(client, email="gibtesnicht@example.local", password="falsch")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_five_wrong_attempts_lock_the_account_for_a_while(client):
    for _ in range(security.MAX_FAILED_LOGINS):
        assert login(client, password="falsch").status_code == 401

    locked = login(client, password="falsch")
    assert locked.status_code == 429
    # Even the correct password waits now.
    assert login(client).status_code == 429

    with SessionLocal() as db:
        admin = db.get(models.User, ADMIN)
        assert admin.locked_until is not None


def test_a_lockout_expires(client):
    with SessionLocal() as db:
        admin = db.get(models.User, ADMIN)
        admin.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert login(client).status_code == 200


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("kurz1!A", "mindestens 12"),
        ("alleskleinbuchstaben", "drei der vier"),
        (START_PASSWORD, "Startpasswort"),
    ],
)
def test_the_new_password_has_to_be_a_password(client, candidate, expected):
    token = login(client).json()["token"]
    response = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={"current_password": START_PASSWORD, "new_password": candidate},
    )
    assert response.status_code == 400
    assert expected in response.json()["detail"]


def test_the_current_password_has_to_be_right(client):
    token = login(client).json()["token"]
    response = client.post(
        "/api/auth/change-password",
        headers=bearer(token),
        json={"current_password": "falsch", "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400


def test_logging_out_ends_every_session(client):
    token = signed_in(client)
    assert client.post("/api/auth/logout", headers=bearer(token)).status_code == 204
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_the_emergency_account_is_not_offered_as_a_dev_identity(client):
    """It is reached through the password login, not by picking a role."""
    users = client.get("/api/auth/dev-users", headers=auth(MANAGER)).json()
    assert ADMIN not in [user["id"] for user in users]


def test_logins_are_recorded(client):
    login(client, password="falsch")
    login(client)
    entries = client.get("/api/audit-log?entity_type=user", headers=auth(AREA_MANAGER)).json()
    actions = [entry["action"] for entry in entries if entry["entity_id"] == ADMIN]
    assert "login" in actions
    assert "login_failed" in actions


# --------------------------------------------------------------------------
# Konten
# --------------------------------------------------------------------------


def test_only_the_administration_sees_the_accounts(client):
    assert client.get("/api/users", headers=auth(MANAGER)).status_code == 403
    assert client.get("/api/users", headers=auth(VIEWER)).status_code == 403
    assert client.get("/api/users", headers=auth(AREA_MANAGER)).status_code == 200


def test_a_new_account_gets_a_role_and_its_branches(client):
    created = client.post(
        "/api/users",
        headers=auth(AREA_MANAGER),
        json={
            "display_name": "Neue Leitung",
            "email": "Neue.Leitung@Example.local",
            "role_id": "role-branch-manager",
            "branch_ids": [BRANCH],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    # The e-mail is the login, so it is stored the way it is compared.
    assert body["email"] == "neue.leitung@example.local"
    assert body["branch_ids"] == [BRANCH]
    assert body["has_password"] is False
    assert body["role_name"] == "Niederlassungsleiter"

    # And it works as an identity right away.
    me = client.get("/api/auth/me", headers=auth(body["id"])).json()
    assert me["role_name"] == "Niederlassungsleiter"

    client.delete(f"/api/users/{body['id']}", headers=auth(AREA_MANAGER))


def test_the_same_e_mail_cannot_be_used_twice(client):
    payload = {"display_name": "Doppelt", "email": "doppelt@example.local"}
    first = client.post("/api/users", headers=auth(AREA_MANAGER), json=payload)
    assert first.status_code == 201
    second = client.post("/api/users", headers=auth(AREA_MANAGER), json=payload)
    assert second.status_code == 409
    client.delete(f"/api/users/{first.json()['id']}", headers=auth(AREA_MANAGER))


def test_an_account_with_a_password_has_to_change_it_at_the_first_login(client):
    created = client.post(
        "/api/users",
        headers=auth(AREA_MANAGER),
        json={
            "display_name": "Mit Passwort",
            "email": "mit.passwort@example.local",
            "role_id": "role-viewer",
            "password": "Start-Passwort-2026!",
        },
    ).json()
    assert created["has_password"] is True
    assert created["must_change_password"] is True

    response = client.post(
        "/api/auth/login",
        json={"email": "mit.passwort@example.local", "password": "Start-Passwort-2026!"},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True

    client.delete(f"/api/users/{created['id']}", headers=auth(AREA_MANAGER))


def test_an_administrator_can_hand_out_and_remove_a_password(client):
    created = client.post(
        "/api/users",
        headers=auth(AREA_MANAGER),
        json={"display_name": "Gesperrt", "email": "gesperrt@example.local", "role_id": "role-viewer"},
    ).json()

    given = client.post(
        f"/api/users/{created['id']}/password",
        headers=auth(AREA_MANAGER),
        json={"new_password": "Zugang-Wieder-2026!"},
    )
    assert given.status_code == 200
    assert given.json()["has_password"] is True
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "gesperrt@example.local", "password": "Zugang-Wieder-2026!"},
        ).status_code
        == 200
    )

    cleared = client.delete(f"/api/users/{created['id']}/password", headers=auth(AREA_MANAGER))
    assert cleared.json()["has_password"] is False
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "gesperrt@example.local", "password": "Zugang-Wieder-2026!"},
        ).status_code
        == 401
    )

    client.delete(f"/api/users/{created['id']}", headers=auth(AREA_MANAGER))


def test_the_password_never_reaches_the_audit_log(client):
    created = client.post(
        "/api/users",
        headers=auth(AREA_MANAGER),
        json={
            "display_name": "Geheim",
            "email": "geheim@example.local",
            "password": "Nicht-Im-Protokoll-1!",
        },
    ).json()
    entries = client.get("/api/audit-log?entity_type=user", headers=auth(AREA_MANAGER)).json()
    assert entries
    assert "Nicht-Im-Protokoll-1!" not in str(entries)
    client.delete(f"/api/users/{created['id']}", headers=auth(AREA_MANAGER))


def test_deactivating_an_account_ends_its_sessions(client):
    token = signed_in(client)
    # Somebody else deactivates the account while it is signed in.
    response = client.patch(f"/api/users/{ADMIN}", headers=auth(AREA_MANAGER), json={"is_active": False})
    assert response.status_code == 200, response.text

    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401
    client.patch(f"/api/users/{ADMIN}", headers=auth(AREA_MANAGER), json={"is_active": True})


def test_the_last_administrator_cannot_lock_themselves_out(client):
    """Two accounts hold user:write here, so one of them has to go first."""
    client.patch(f"/api/users/{ADMIN}", headers=auth(AREA_MANAGER), json={"is_active": False})
    try:
        response = client.patch(
            f"/api/users/{AREA_MANAGER}", headers=auth(AREA_MANAGER), json={"role_id": "role-viewer"}
        )
        assert response.status_code == 409
        assert "letzte Konto" in response.json()["detail"]

        deactivate = client.patch(
            f"/api/users/{AREA_MANAGER}", headers=auth(AREA_MANAGER), json={"is_active": False}
        )
        assert deactivate.status_code == 409
    finally:
        client.patch(f"/api/users/{ADMIN}", headers=auth(AREA_MANAGER), json={"is_active": True})


def test_an_account_in_use_is_deactivated_rather_than_deleted(client):
    client.post(
        "/api/compliance-records",
        headers=auth(MANAGER),
        json={
            "title": "Haengt am Konto",
            "category": "documentation",
            "branch_id": BRANCH,
            "owner_user_id": MANAGER,
            "legal_basis": "ArbSchG",
            "control_type": "document",
            "due_date": "2026-12-01",
            "review_date": "2026-11-01",
        },
    )
    response = client.delete(f"/api/users/{MANAGER}", headers=auth(AREA_MANAGER))
    assert response.status_code == 409
    assert "deaktivieren" in response.json()["detail"]


def test_branch_assignments_are_edited_here(client):
    created = client.post(
        "/api/users",
        headers=auth(AREA_MANAGER),
        json={
            "display_name": "Ohne Standort",
            "email": "ohne.standort@example.local",
            "role_id": "role-branch-manager",
        },
    ).json()
    # No branch means no data at all - the scope is empty, not unrestricted.
    assert client.get("/api/employees", headers=auth(created["id"])).json() == []

    updated = client.patch(
        f"/api/users/{created['id']}", headers=auth(AREA_MANAGER), json={"branch_ids": [BRANCH]}
    )
    assert updated.json()["branch_ids"] == [BRANCH]
    assert client.get("/api/employees", headers=auth(created["id"])).status_code == 200

    client.delete(f"/api/users/{created['id']}", headers=auth(AREA_MANAGER))


# --------------------------------------------------------------------------
# Rollen und Berechtigungen
# --------------------------------------------------------------------------


def test_the_permission_catalogue_is_explained_in_german(client):
    catalogue = client.get("/api/permissions", headers=auth(AREA_MANAGER)).json()
    keys = {item["key"] for item in catalogue}
    assert "compliance:write" in keys
    assert all(item["label"] and item["description"] and item["area"] for item in catalogue)


def test_the_preset_roles_are_read_only(client):
    roles = {role["name"]: role for role in client.get("/api/roles", headers=auth(AREA_MANAGER)).json()}
    assert roles["Niederlassungsleiter"]["system"] is True
    assert roles["Niederlassungsleiter"]["user_count"] >= 1

    response = client.patch(
        f"/api/roles/{roles['Niederlassungsleiter']['id']}",
        headers=auth(AREA_MANAGER),
        json={"permissions": ["*"]},
    )
    assert response.status_code == 409
    assert "eigene Rolle" in response.json()["detail"]


def test_an_own_role_can_be_created_and_used(client):
    created = client.post(
        "/api/roles",
        headers=auth(AREA_MANAGER),
        json={
            "name": "Fuhrparkbetreuung",
            "description": "Nur Fahrzeuge, sonst nichts.",
            "permissions": ["fleet:read", "fleet:write"],
        },
    )
    assert created.status_code == 201, created.text
    role = created.json()
    assert role["system"] is False

    user = client.post(
        "/api/users",
        headers=auth(AREA_MANAGER),
        json={
            "display_name": "Fuhrpark Person",
            "email": "fuhrpark@example.local",
            "role_id": role["id"],
            "branch_ids": [BRANCH],
        },
    ).json()

    assert client.get("/api/vehicles", headers=auth(user["id"])).status_code == 200
    assert client.get("/api/compliance-records", headers=auth(user["id"])).status_code == 403

    # A role still in use is not deleted away under the account.
    assert client.delete(f"/api/roles/{role['id']}", headers=auth(AREA_MANAGER)).status_code == 409

    client.delete(f"/api/users/{user['id']}", headers=auth(AREA_MANAGER))
    assert client.delete(f"/api/roles/{role['id']}", headers=auth(AREA_MANAGER)).status_code == 204


def test_an_unknown_permission_is_refused(client):
    response = client.post(
        "/api/roles",
        headers=auth(AREA_MANAGER),
        json={"name": "Erfunden", "permissions": ["gibtes:nicht"]},
    )
    assert response.status_code == 400
    assert "gibtes:nicht" in response.json()["detail"]
