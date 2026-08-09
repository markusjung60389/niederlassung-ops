"""Authentication and authorisation.

Two modes, selected via ``AUTH_MODE``:

``dev``
    The caller identifies itself with the ``X-User-Id`` header, which must match
    an active row in ``users``. Refused when ``APP_ENV`` is production.

``azure_ad``
    Every request must carry a Microsoft Entra ID (Azure AD) bearer token. The
    token signature is verified against the tenant JWKS, issuer and audience are
    checked, and the app roles in the token are mapped onto local roles.

The Entra ID path is fully implemented but stays dormant until ``AUTH_MODE`` is
switched to ``azure_ad``; see ``docs/azure-ad-setup.md``.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Annotated, Any, Callable

import httpx
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, permissions
from .config import settings
from .database import get_db

try:  # pragma: no cover - exercised through the azure_ad path only
    import jwt

    JWT_AVAILABLE = True
except Exception:  # pragma: no cover
    jwt = None  # type: ignore[assignment]
    JWT_AVAILABLE = False


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, independent of the identity provider used."""

    user_id: str
    display_name: str
    email: str | None
    permissions: frozenset[str]
    source: str
    role_name: str | None = None
    # Which branches this caller may see and work in. `all_branches` is the
    # area manager: no per-branch row has to be maintained for them, and a
    # branch added later is included without anyone remembering to.
    branch_ids: frozenset[str] = frozenset()
    all_branches: bool = False

    def has(self, permission: str) -> bool:
        return permissions.grants(self.permissions, permission)

    def may_see(self, branch_id: str | None) -> bool:
        """True when the caller may read data of that branch.

        `None` means the row is not tied to a branch - a group-wide rule, for
        instance - and is readable by anyone who may read the area at all.
        """
        return branch_id is None or self.all_branches or branch_id in self.branch_ids

    def scope(self, branch_id: str | None = None) -> list[str] | None:
        """The branch ids a query should be limited to.

        `None` means no restriction, which only ever happens for the area
        manager without a selected branch. A requested branch outside the
        caller's scope yields an empty list rather than a silent widening.
        """
        if branch_id is not None:
            return [branch_id] if self.may_see(branch_id) else []
        if self.all_branches:
            return None
        return sorted(self.branch_ids)


def _unauthorized(detail: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if settings.auth_mode == "azure_ad" else None
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers=headers)


# --------------------------------------------------------------------------
# Microsoft Entra ID
# --------------------------------------------------------------------------


class JwksCache:
    """Caches the tenant signing keys and refetches on unknown key ids.

    Entra ID rotates signing keys, so a cache miss triggers exactly one refresh
    before the token is rejected.
    """

    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def _expired(self) -> bool:
        return (time.monotonic() - self._fetched_at) > settings.azure_jwks_cache_seconds

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.azure_jwks_url)
            response.raise_for_status()
            document = response.json()
        keys: dict[str, Any] = {}
        for entry in document.get("keys", []):
            kid = entry.get("kid")
            if not kid:
                continue
            try:
                keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(entry))
            except Exception:  # pragma: no cover - malformed key material
                continue
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def get_key(self, kid: str) -> Any:
        async with self._lock:
            if self._expired() or kid not in self._keys:
                await self._refresh()
            key = self._keys.get(kid)
        if key is None:
            raise _unauthorized("Token signing key is unknown to the configured tenant.")
        return key

    def clear(self) -> None:
        self._keys = {}
        self._fetched_at = 0.0


jwks_cache = JwksCache()


async def verify_azure_token(token: str) -> dict[str, Any]:
    """Validates an Entra ID access token and returns its claims."""
    if not JWT_AVAILABLE:  # pragma: no cover - dependency guard
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_MODE=azure_ad requires the 'pyjwt[crypto]' dependency.",
        )
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise _unauthorized(f"Malformed bearer token: {exc}") from exc

    kid = header.get("kid")
    if not kid:
        raise _unauthorized("Bearer token has no key id.")
    key = await jwks_cache.get_key(kid)

    last_error: Exception | None = None
    for issuer in settings.azure_issuers:
        try:
            return jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=settings.azure_audiences,
                issuer=issuer,
                leeway=settings.azure_leeway_seconds,
                options={"require": ["exp", "iss", "aud"]},
            )
        except Exception as exc:  # try the next accepted issuer
            last_error = exc
    raise _unauthorized(f"Bearer token rejected: {last_error}")


def _claim_role_names(claims: dict[str, Any]) -> list[str]:
    """Maps Entra app roles and group ids onto local role names."""
    mapping = settings.azure_role_mapping
    raw: list[str] = []
    role_claim = claims.get(settings.azure_role_claim)
    if isinstance(role_claim, list):
        raw.extend(str(value) for value in role_claim)
    elif isinstance(role_claim, str):
        raw.append(role_claim)
    groups = claims.get("groups")
    if isinstance(groups, list):
        raw.extend(str(value) for value in groups)

    names = [mapping[item] for item in raw if item in mapping]
    if not names and settings.azure_default_role_name:
        names = [settings.azure_default_role_name]
    return names


def _resolve_azure_user(db: Session, claims: dict[str, Any]) -> models.User:
    external_id = claims.get("oid") or claims.get("sub")
    if not external_id:
        raise _unauthorized("Bearer token carries no object id claim.")
    email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
    display_name = claims.get("name") or email or str(external_id)

    user = db.scalar(select(models.User).where(models.User.external_id == str(external_id)))
    if user is None and email:
        # Link a pre-created local account on first login.
        user = db.scalar(select(models.User).where(models.User.email == email))
        if user is not None:
            user.external_id = str(external_id)

    role_names = _claim_role_names(claims)
    role = None
    if role_names:
        role = db.scalar(select(models.Role).where(models.Role.name.in_(role_names)))

    if user is None:
        if not settings.azure_auto_provision_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No local account exists for this identity and auto provisioning is disabled.",
            )
        if not email:
            raise _unauthorized("Bearer token carries no email claim, cannot provision a user.")
        user = models.User(
            external_id=str(external_id),
            display_name=str(display_name),
            email=str(email),
            role=role,
        )
        db.add(user)
        db.flush()
    else:
        user.display_name = str(display_name)
        if role is not None:
            user.role = role

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated.")

    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------


def _principal_from_user(user: models.User, source: str) -> Principal:
    role = user.role
    return Principal(
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        permissions=frozenset(role.permissions if role and role.permissions else ()),
        source=source,
        role_name=role.name if role else None,
        branch_ids=frozenset(link.branch_id for link in user.branch_links),
        all_branches=bool(user.all_branches),
    )


async def current_principal(
    db: Annotated[Session, Depends(get_db)],
    x_user_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if settings.auth_mode == "azure_ad":
        if not authorization or not authorization.lower().startswith("bearer "):
            raise _unauthorized("Bearer token required.")
        claims = await verify_azure_token(authorization.split(" ", 1)[1].strip())
        return _principal_from_user(_resolve_azure_user(db, claims), "azure-ad")

    user_id = x_user_id or settings.auth_dev_default_user_id
    if not user_id:
        raise _unauthorized("X-User-Id header required while AUTH_MODE=dev.")
    user = db.get(models.User, user_id)
    if user is None:
        raise _unauthorized("Unknown user id.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated.")
    return _principal_from_user(user, "dev")


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def requires(*required: str) -> Callable[[Principal], Principal]:
    """Dependency factory: the caller must hold every listed permission."""

    def dependency(principal: CurrentPrincipal) -> Principal:
        missing = [item for item in required if not principal.has(item)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission(s): {', '.join(missing)}",
            )
        return principal

    return dependency
