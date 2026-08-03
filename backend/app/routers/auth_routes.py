from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentPrincipal
from ..config import settings
from ..database import get_db

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
    )


@router.get("/api/auth/dev-users", response_model=list[schemas.DevUserRead])
def dev_users(db: Session = Depends(get_db)) -> list[schemas.DevUserRead]:
    """Identities selectable while AUTH_MODE=dev.

    Returns 404 under azure_ad so no user directory is exposed in production.
    """
    if settings.auth_mode != "dev":
        raise HTTPException(status_code=404, detail="Not available")
    users = db.scalars(
        select(models.User).where(models.User.is_active.is_(True)).order_by(models.User.display_name.asc())
    ).all()
    return [
        schemas.DevUserRead(
            id=user.id, display_name=user.display_name, role_name=user.role.name if user.role else None
        )
        for user in users
    ]


@router.get("/api/bootstrap")
def bootstrap(principal: CurrentPrincipal, db: Session = Depends(get_db)) -> dict:
    branches = db.scalars(select(models.Branch).order_by(models.Branch.name.asc())).all()
    users = db.scalars(
        select(models.User).where(models.User.is_active.is_(True)).order_by(models.User.display_name.asc())
    ).all()
    return {
        "branches": [schemas.BranchRead.model_validate(branch).model_dump() for branch in branches],
        "users": [schemas.UserRead.model_validate(user).model_dump() for user in users],
        "auth_mode": settings.auth_mode,
        "permissions": sorted(principal.permissions),
    }
