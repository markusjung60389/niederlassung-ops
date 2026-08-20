from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas, security
from ..auth import CurrentPrincipal
from ..config import settings
from ..database import get_db
from ..deps import audit

router = APIRouter(tags=["auth"])


@router.get("/api/auth/me", response_model=schemas.PrincipalRead)
def whoami(principal: CurrentPrincipal) -> schemas.PrincipalRead:
    return schemas.PrincipalRead(
        user_id=principal.user_id,
        display_name=principal.display_name,
        email=principal.email,
        role_name=principal.role_name,
        permissions=sorted(principal.permissions),
        source=principal.source,
        must_change_password=principal.must_change_password,
    )


# --------------------------------------------------------------------------
# Local password login
# --------------------------------------------------------------------------


def _password_login_enabled() -> None:
    if not settings.auth_password_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Die Passwort-Anmeldung ist deaktiviert."
        )


@router.post("/api/auth/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)) -> schemas.LoginResponse:
    """Signs in with e-mail and password and returns a session token.

    The emergency door beside Entra ID. Wrong credentials always answer the
    same way, whether the account exists or not - a login form that
    distinguishes the two is a directory of valid e-mail addresses.
    """
    _password_login_enabled()
    now = datetime.now(timezone.utc)
    user = db.scalar(
        select(models.User).where(func.lower(models.User.email) == payload.email.strip().lower())
    )

    locked_until = security.as_utc(user.locked_until) if user is not None else None
    if locked_until and locked_until > now:
        minutes = max(1, int((locked_until - now).total_seconds() // 60) + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Zu viele Fehlversuche. Bitte in {minutes} Minuten erneut versuchen.",
        )

    # Runs the same scrypt cost whether or not the account exists, so response
    # time cannot be used to enumerate addresses.
    password_ok = security.verify_password(
        payload.password, user.password_hash if user is not None else security.DUMMY_HASH
    )
    if user is None or not user.is_active or not password_ok:
        if user is not None:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= security.MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=security.LOCKOUT_MINUTES)
                user.failed_login_count = 0
            audit(db, "user", user.id, "login_failed", {"email": payload.email})
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-Mail oder Passwort ist falsch.",
        )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    token, expires_at = security.issue_session(user.id, user.token_version)
    audit(db, "user", user.id, "login", {"source": "password"})
    db.commit()
    db.refresh(user)
    return schemas.LoginResponse(
        token=token,
        expires_at=expires_at,
        must_change_password=bool(user.must_change_password),
        display_name=user.display_name,
    )


@router.post("/api/auth/change-password", response_model=schemas.LoginResponse)
def change_password(
    payload: schemas.PasswordChange, principal: CurrentPrincipal, db: Session = Depends(get_db)
) -> schemas.LoginResponse:
    """Replaces the caller's own password and hands back a fresh session.

    Reachable while `must_change_password` is set - it is the one thing that
    still works then. The new session is returned because the change retires
    every token issued before it, including the one used for this request.
    """
    _password_login_enabled()
    user = db.get(models.User, principal.user_id)
    if user is None or not security.verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Das aktuelle Passwort ist falsch."
        )
    problem = security.password_problem(
        payload.new_password, display_name=user.display_name, email=user.email
    )
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)
    if security.verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das neue Passwort muss sich vom bisherigen unterscheiden.",
        )

    user.password_hash = security.hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    user.token_version = (user.token_version or 1) + 1
    token, expires_at = security.issue_session(user.id, user.token_version)
    audit(db, "user", user.id, "password_changed", {"by": "self"}, principal)
    db.commit()
    return schemas.LoginResponse(
        token=token, expires_at=expires_at, must_change_password=False, display_name=user.display_name
    )


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(principal: CurrentPrincipal, db: Session = Depends(get_db)) -> Response:
    """Ends every session of the caller, not just the one in this browser.

    A shared or lost device is the reason somebody clicks this; ending only the
    current token would leave the others alive.
    """
    user = db.get(models.User, principal.user_id)
    if user is not None:
        user.token_version = (user.token_version or 1) + 1
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/auth/dev-users", response_model=list[schemas.DevUserRead])
def dev_users(db: Session = Depends(get_db)) -> list[schemas.DevUserRead]:
    """Identities selectable while AUTH_MODE=dev.

    Returns 404 under azure_ad so no user directory is exposed in production.
    """
    if settings.auth_mode != "dev":
        raise HTTPException(status_code=404, detail="Not available")
    users = [
        user
        for user in db.scalars(
            select(models.User)
            .where(models.User.is_active.is_(True))
            .order_by(models.User.display_name.asc())
        ).all()
        # The emergency administrator is not a role to try out: it exists for
        # the password login and is reached through it.
        if not (user.role and user.role.name == permissions.ROLE_ADMIN)
    ]
    # The frontend picks the first entry when no identity has been chosen yet.
    # Alphabetically that is the read-only viewer, so the application opened
    # with every action hidden and looked like a broken build. Widest
    # permissions first; the name still orders within a role.
    def breadth(user: models.User) -> int:
        held = user.role.permissions if user.role else []
        return -1000 if held and held[0] == "*" else -len(held)

    users.sort(key=breadth)
    return [
        schemas.DevUserRead(
            id=user.id, display_name=user.display_name, role_name=user.role.name if user.role else None
        )
        for user in users
    ]


@router.get("/api/bootstrap")
def bootstrap(principal: CurrentPrincipal, db: Session = Depends(get_db)) -> dict:
    # Only the branches the caller belongs to: this drives the branch switcher,
    # and the names of the others are none of their business either.
    branches = [
        branch
        for branch in db.scalars(
            select(models.Branch)
            .where(models.Branch.active.is_(True))
            .order_by(models.Branch.name.asc())
        ).all()
        if principal.may_see(branch.id)
    ]
    users = db.scalars(
        select(models.User).where(models.User.is_active.is_(True)).order_by(models.User.display_name.asc())
    ).all()
    return {
        "branches": [schemas.BranchRead.model_validate(branch).model_dump() for branch in branches],
        "users": [schemas.UserRead.model_validate(user).model_dump() for user in users],
        "auth_mode": settings.auth_mode,
        "permissions": sorted(principal.permissions),
        "password_login_enabled": settings.auth_password_login_enabled,
    }
