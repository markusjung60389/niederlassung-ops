"""Exercises the Microsoft Entra ID path end to end with a locally signed token.

The tenant JWKS is replaced by a test key; everything else (signature check,
issuer, audience, expiry, role mapping, user provisioning, the dependency wiring)
runs the real production code path. AUTH_MODE stays "dev" outside these tests.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth as auth_module
from app import models
from app.database import SessionLocal
from tests.conftest import MANAGER

KID = "test-signing-key"
TENANT = "test-tenant"
CLIENT = "test-client"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(**overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": f"api://{CLIENT}",
        "oid": "11111111-2222-3333-4444-555555555555",
        "name": "Entra Testnutzer",
        "preferred_username": "entra.test@example.local",
        "roles": ["OpsManager"],
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=30),
    }
    claims.update(overrides)
    return jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def azure_mode(monkeypatch):
    settings = auth_module.settings
    monkeypatch.setattr(settings, "auth_mode", "azure_ad")
    monkeypatch.setattr(settings, "azure_tenant_id", TENANT)
    monkeypatch.setattr(settings, "azure_client_id", CLIENT)
    monkeypatch.setattr(settings, "azure_api_audience", None)
    monkeypatch.setattr(settings, "azure_role_map", "OpsManager=Niederlassungsleiter")
    monkeypatch.setattr(settings, "azure_auto_provision_users", True)
    monkeypatch.setattr(settings, "azure_default_role_name", None)

    # Serve the local public key instead of calling the tenant JWKS endpoint.
    monkeypatch.setattr(auth_module.jwks_cache, "_keys", {KID: _private_key.public_key()})
    monkeypatch.setattr(auth_module.jwks_cache, "_fetched_at", time.monotonic())
    yield
    _delete_provisioned_users()


def _delete_provisioned_users():
    with SessionLocal() as db:
        for user in db.query(models.User).filter(models.User.external_id.isnot(None)).all():
            if user.id != MANAGER:
                db.delete(user)
            else:
                user.external_id = None
        db.commit()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- token validation ------------------------------------------------------


def test_valid_token_is_accepted(azure_mode):
    claims = asyncio.run(auth_module.verify_azure_token(make_token()))
    assert claims["oid"] == "11111111-2222-3333-4444-555555555555"


def test_expired_token_is_rejected(azure_mode):
    now = datetime.now(timezone.utc)
    token = make_token(exp=now - timedelta(minutes=5), nbf=now - timedelta(minutes=10))
    with pytest.raises(Exception) as excinfo:
        asyncio.run(auth_module.verify_azure_token(token))
    assert excinfo.value.status_code == 401


def test_wrong_audience_is_rejected(azure_mode):
    with pytest.raises(Exception) as excinfo:
        asyncio.run(auth_module.verify_azure_token(make_token(aud="api://someone-else")))
    assert excinfo.value.status_code == 401


def test_wrong_issuer_is_rejected(azure_mode):
    with pytest.raises(Exception) as excinfo:
        asyncio.run(auth_module.verify_azure_token(make_token(iss="https://evil.example.com/v2.0")))
    assert excinfo.value.status_code == 401


def test_token_signed_by_another_key_is_rejected(azure_mode):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "iss": ISSUER,
            "aud": f"api://{CLIENT}",
            "oid": "abc",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        other_key,
        algorithm="RS256",
        headers={"kid": KID},
    )
    with pytest.raises(Exception) as excinfo:
        asyncio.run(auth_module.verify_azure_token(token))
    assert excinfo.value.status_code == 401


def test_unsigned_token_is_rejected(azure_mode):
    """Guards against the 'alg: none' downgrade."""
    token = jwt.encode({"iss": ISSUER, "aud": f"api://{CLIENT}", "oid": "abc"}, key="", algorithm="none")
    with pytest.raises(Exception) as excinfo:
        asyncio.run(auth_module.verify_azure_token(token))
    assert excinfo.value.status_code == 401


# --- request flow ----------------------------------------------------------


def test_request_without_bearer_is_rejected(client, azure_mode):
    response = client.get("/api/cockpit")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_dev_header_does_not_work_in_azure_mode(client, azure_mode):
    assert client.get("/api/cockpit", headers={"X-User-Id": MANAGER}).status_code == 401


def test_user_is_provisioned_and_role_is_mapped(client, azure_mode):
    response = client.get("/api/auth/me", headers=bearer(make_token()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "azure-ad"
    assert body["display_name"] == "Entra Testnutzer"
    assert body["role_name"] == "Niederlassungsleiter"
    assert body["permissions"] == ["*"]

    with SessionLocal() as db:
        user = db.query(models.User).filter_by(external_id="11111111-2222-3333-4444-555555555555").one()
        assert user.email == "entra.test@example.local"


def test_second_login_reuses_the_same_local_user(client, azure_mode):
    first = client.get("/api/auth/me", headers=bearer(make_token())).json()
    second = client.get("/api/auth/me", headers=bearer(make_token())).json()
    assert first["user_id"] == second["user_id"]


def test_existing_local_account_is_linked_by_email(client, azure_mode):
    with SessionLocal() as db:
        manager = db.get(models.User, MANAGER)
        email = manager.email
        assert manager.external_id is None

    body = client.get("/api/auth/me", headers=bearer(make_token(preferred_username=email))).json()
    assert body["user_id"] == MANAGER

    with SessionLocal() as db:
        assert db.get(models.User, MANAGER).external_id == "11111111-2222-3333-4444-555555555555"


def test_unmapped_role_yields_no_permissions(client, azure_mode):
    response = client.get("/api/auth/me", headers=bearer(make_token(roles=["SomethingElse"])))
    assert response.json()["permissions"] == []
    assert client.get("/api/cockpit", headers=bearer(make_token(roles=["SomethingElse"]))).status_code == 403


def test_group_claim_can_be_mapped(client, azure_mode, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "azure_role_map", "group-uuid-1=HSE / Compliance")
    body = client.get(
        "/api/auth/me", headers=bearer(make_token(roles=[], groups=["group-uuid-1"]))
    ).json()
    assert body["role_name"] == "HSE / Compliance"
    assert "compliance:write" in body["permissions"]


def test_auto_provisioning_can_be_disabled(client, azure_mode, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "azure_auto_provision_users", False)
    response = client.get("/api/auth/me", headers=bearer(make_token()))
    assert response.status_code == 403
    assert "auto provisioning is disabled" in response.json()["detail"]
