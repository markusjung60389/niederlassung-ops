"""Authorisation behaviour.

Before this change every GET was reachable without any credentials and any
non-empty X-User-Role header granted write access.
"""

import pytest

from app.auth import Principal
from app.config import Settings
from tests.conftest import BRANCH, HSE, MANAGER, VIEWER, auth

READ_ENDPOINTS = [
    "/api/bootstrap",
    "/api/cockpit",
    "/api/compliance-records",
    "/api/actions",
    "/api/employees",
    "/api/vehicles",
    "/api/reminders",
    "/api/incidents",
    "/api/branch-assessments",
    "/api/audit-log",
    f"/api/hermes/context/branches/{BRANCH}",
]


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_reads_require_authentication(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_reads_reject_unknown_user(client, path):
    assert client.get(path, headers=auth("does-not-exist")).status_code == 401


def test_health_stays_public(client):
    assert client.get("/health").status_code == 200


def test_arbitrary_role_header_is_not_accepted(client):
    """The old X-User-Role header must no longer grant anything."""
    response = client.post(
        "/api/vehicles",
        headers={"X-User-Role": "branch-manager"},
        json={"branch_id": BRANCH, "license_plate": "RS-XX-1"},
    )
    assert response.status_code == 401


def test_viewer_may_read_but_not_write(client):
    assert client.get("/api/vehicles", headers=auth(VIEWER)).status_code == 200
    response = client.post(
        "/api/vehicles", headers=auth(VIEWER), json={"branch_id": BRANCH, "license_plate": "RS-XX-2"}
    )
    assert response.status_code == 403
    assert "fleet:write" in response.json()["detail"]


def test_hse_may_write_compliance_but_not_personnel(client):
    assert client.get("/api/compliance-records", headers=auth(HSE)).status_code == 200
    response = client.post(
        "/api/employees",
        headers=auth(HSE),
        json={"branch_id": BRANCH, "full_name": "Neu Person", "role": "Techniker"},
    )
    assert response.status_code == 403


def test_agent_endpoint_requires_permission(client):
    """This endpoint previously had no authorisation at all."""
    response = client.post(
        "/api/agent/compliance-review", headers=auth(VIEWER), json={"compliance_record_id": "x"}
    )
    assert response.status_code == 403


def test_whoami_reports_resolved_permissions(client):
    body = client.get("/api/auth/me", headers=auth(HSE)).json()
    assert body["user_id"] == HSE
    assert body["source"] == "dev"
    assert "compliance:write" in body["permissions"]
    assert "personnel:write" not in body["permissions"]


def test_deactivated_account_is_refused(client):
    from app import models
    from app.database import SessionLocal

    with SessionLocal() as db:
        user = db.get(models.User, VIEWER)
        user.is_active = False
        db.commit()
    try:
        assert client.get("/api/vehicles", headers=auth(VIEWER)).status_code == 403
    finally:
        with SessionLocal() as db:
            db.get(models.User, VIEWER).is_active = True
            db.commit()


def test_wildcard_permission_covers_everything(client):
    assert client.get("/api/audit-log", headers=auth(MANAGER)).status_code == 200


def test_area_wildcard_is_honoured():
    principal = Principal(
        user_id="u", display_name="U", email=None, permissions=frozenset({"compliance:*"}), source="test"
    )
    assert principal.has("compliance:write")
    assert not principal.has("personnel:read")


# --- configuration guards -------------------------------------------------


def test_dev_auth_is_refused_in_production():
    with pytest.raises(ValueError, match="AUTH_MODE=dev is refused"):
        Settings(app_env="production", auth_mode="dev", _env_file=None)


def test_azure_mode_requires_tenant_and_client():
    with pytest.raises(ValueError, match="requires AZURE_TENANT_ID"):
        Settings(auth_mode="azure_ad", _env_file=None)


def test_wildcard_cors_origin_is_refused():
    with pytest.raises(ValueError, match="must not contain"):
        Settings(cors_allow_origins="*", _env_file=None)


def test_azure_settings_derive_endpoints():
    settings = Settings(
        auth_mode="azure_ad",
        azure_tenant_id="tenant-1",
        azure_client_id="client-1",
        azure_role_map="OpsManager=Niederlassungsleiter, GroupX = HSE / Compliance",
        _env_file=None,
    )
    assert settings.azure_jwks_url == "https://login.microsoftonline.com/tenant-1/discovery/v2.0/keys"
    assert "https://login.microsoftonline.com/tenant-1/v2.0" in settings.azure_issuers
    assert "https://sts.windows.net/tenant-1/" in settings.azure_issuers
    assert settings.azure_audiences == ["api://client-1", "client-1"]
    assert settings.azure_role_mapping == {
        "OpsManager": "Niederlassungsleiter",
        "GroupX": "HSE / Compliance",
    }


def test_dev_users_offer_the_widest_role_first(client):
    """The frontend selects the first entry when no identity is stored yet.

    Alphabetically that was the read-only viewer, which opened the application
    with every action hidden.
    """
    users = client.get("/api/auth/dev-users", headers=auth(MANAGER)).json()
    assert users[0]["id"] == "user-branch-manager"
    assert [item["role_name"] for item in users] == [
        "Niederlassungsleiter",
        "HSE / Compliance",
        "Betrachter",
    ]
