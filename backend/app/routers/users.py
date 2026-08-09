"""Accounts, roles and the permission catalogue.

Two questions are answered per account and they are deliberately separate:
*what* somebody may do (the role) and *where* they may do it (the branch
assignment). Mixing them would mean a role per branch and, four branches later,
sixteen roles nobody dares to touch.

The screen behind this is the one place where somebody can widen their own
access, so every change lands in the audit log and the last administrator
cannot take away their own last permission.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import models, permissions, schemas, security
from ..auth import Principal, requires
from ..config import settings
from ..database import get_db
from ..deps import audit, ensure_ref, get_or_404, snapshot

router = APIRouter(tags=["users"])

WriteDep = Annotated[Principal, Depends(requires(permissions.USER_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.USER_READ))]

# German label and one sentence per permission, so the role editor is readable
# by whoever actually hands out access rather than only by its author.
PERMISSION_CATALOGUE: list[tuple[str, str, str, str]] = [
    (permissions.COMPLIANCE_READ, "Compliance", "Compliance lesen", "Pflichten, Nachweise und Massnahmen einsehen."),
    (permissions.COMPLIANCE_WRITE, "Compliance", "Compliance pflegen", "Eintraege anlegen, bearbeiten, Nachweise hochladen."),
    (permissions.PERSONNEL_READ, "Personal", "Personal lesen", "Mitarbeiter, Qualifikationen und Fristen einsehen."),
    (permissions.PERSONNEL_WRITE, "Personal", "Personal pflegen", "Mitarbeiter anlegen, Qualifikationen erfassen, Ausnahmen setzen."),
    (permissions.FLEET_READ, "Fuhrpark", "Fahrzeuge lesen", "Fahrzeuge, Fristen und Zuordnungen einsehen."),
    (permissions.FLEET_WRITE, "Fuhrpark", "Fahrzeuge pflegen", "Fahrzeuge anlegen, bearbeiten und verlegen."),
    (permissions.ASSESSMENT_READ, "Bestandsaufnahme", "Bestandsaufnahme lesen", "Stichtagsaufnahmen einsehen."),
    (permissions.ASSESSMENT_WRITE, "Bestandsaufnahme", "Bestandsaufnahme pflegen", "Aufnahmen anlegen und fortschreiben."),
    (permissions.INCIDENT_READ, "Ereignisse", "Ereignisse lesen", "Unfaelle und Beinaheunfaelle einsehen."),
    (permissions.INCIDENT_WRITE, "Ereignisse", "Ereignisse erfassen", "Ereignisse melden und nachbearbeiten."),
    (permissions.RULE_READ, "Vorgaben", "Vorgaben lesen", "Gruppenregeln, Katalog und Ausnahmen einsehen."),
    (permissions.RULE_WRITE, "Vorgaben", "Vorgaben aendern", "Gruppenweite Regeln setzen und Ausnahmen widerrufen."),
    (permissions.BRANCH_READ, "Niederlassungen", "Niederlassungen lesen", "Standortliste und Portfolio einsehen."),
    (permissions.BRANCH_WRITE, "Niederlassungen", "Niederlassungen verwalten", "Standorte anlegen, umbenennen, stilllegen."),
    (permissions.USER_READ, "Verwaltung", "Benutzer lesen", "Konten, Rollen und Zuordnungen einsehen."),
    (permissions.USER_WRITE, "Verwaltung", "Benutzer verwalten", "Konten anlegen, Rollen vergeben, Passwoerter setzen."),
    (permissions.SALARY_READ, "Entgelt", "Entgelt lesen", "Gehaelter einsehen. Verlangt zusaetzlich eine Bestaetigung per Microsoft-Anmeldung."),
    (permissions.SALARY_WRITE, "Entgelt", "Entgelt pflegen", "Gehaelter erfassen und aendern. Jeder Zugriff wird protokolliert."),
    (permissions.AUDIT_READ, "Verwaltung", "Protokoll lesen", "Das Aenderungsprotokoll einsehen."),
    (permissions.AGENT_RUN, "Verwaltung", "Assistent nutzen", "Auswertungen ueber den Hermes-Assistenten anstossen."),
    (permissions.SALES_READ, "Vertrieb", "Vertrieb lesen", "Kunden und Chancen ueber die API einsehen."),
    (permissions.SALES_WRITE, "Vertrieb", "Vertrieb pflegen", "Kunden und Chancen ueber die API pflegen."),
]


def _user_read(user: models.User) -> schemas.UserAdminRead:
    return schemas.UserAdminRead(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        is_active=user.is_active,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        all_branches=bool(user.all_branches),
        branch_ids=sorted(link.branch_id for link in user.branch_links),
        has_password=bool(user.password_hash),
        external_id=user.external_id,
        must_change_password=bool(user.must_change_password),
        last_login_at=user.last_login_at,
        locked_until=user.locked_until,
        created_at=user.created_at,
    )


def _load(db: Session, user_id: str) -> models.User:
    user = db.scalar(
        select(models.User)
        .where(models.User.id == user_id)
        .options(selectinload(models.User.branch_links))
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden")
    return user


def _set_branches(db: Session, user: models.User, branch_ids: list[str]) -> None:
    wanted = {item for item in branch_ids if item}
    for branch_id in wanted:
        ensure_ref(db, models.Branch, branch_id, "branch_ids")
    current = {link.branch_id: link for link in user.branch_links}
    for branch_id, link in current.items():
        if branch_id not in wanted:
            db.delete(link)
    for branch_id in wanted - set(current):
        db.add(models.UserBranch(user_id=user.id, branch_id=branch_id))
    db.flush()


def _guard_self_lockout(db: Session, principal: Principal, user: models.User, changes: dict) -> None:
    """Stops the last administrator from removing their own way back in.

    Deactivating yourself or moving yourself to a role without `user:write`
    locks the tool for everyone the moment nobody else holds it - and the only
    fix would be a database console.
    """
    if user.id != principal.user_id:
        return
    losing_access = (
        changes.get("is_active") is False
        or ("role_id" in changes and changes["role_id"] != user.role_id)
    )
    if not losing_access:
        return
    others = db.scalar(
        select(func.count(models.User.id))
        .join(models.Role, models.User.role_id == models.Role.id)
        .where(models.User.id != user.id, models.User.is_active.is_(True))
    ) or 0
    remaining = [
        other
        for other in db.scalars(
            select(models.User).where(models.User.id != user.id, models.User.is_active.is_(True))
        ).all()
        if other.role and permissions.grants(other.role.permissions, permissions.USER_WRITE)
    ]
    if others == 0 or not remaining:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Das ist das letzte Konto mit Benutzerverwaltung. "
                "Zuerst ein weiteres Konto mit dieser Berechtigung anlegen."
            ),
        )


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------


@router.get("/api/users", response_model=list[schemas.UserAdminRead])
def list_users(
    principal: ReadDep, include_inactive: bool = True, db: Session = Depends(get_db)
) -> list[schemas.UserAdminRead]:
    query = select(models.User).options(selectinload(models.User.branch_links))
    if not include_inactive:
        query = query.where(models.User.is_active.is_(True))
    users = db.scalars(query.order_by(models.User.display_name.asc())).all()
    return [_user_read(user) for user in users]


@router.post("/api/users", response_model=schemas.UserAdminRead, status_code=201)
def create_user(
    payload: schemas.UserCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.UserAdminRead:
    email = payload.email.strip().lower()
    if db.scalar(select(models.User).where(func.lower(models.User.email) == email)):
        raise HTTPException(status_code=409, detail=f"Ein Konto mit '{email}' existiert bereits.")
    ensure_ref(db, models.Role, payload.role_id, "role_id")

    user = models.User(
        display_name=payload.display_name.strip(),
        email=email,
        role_id=payload.role_id,
        all_branches=payload.all_branches,
    )
    if payload.password:
        problem = security.password_problem(
            payload.password, display_name=user.display_name, email=user.email
        )
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        user.password_hash = security.hash_password(payload.password)
        user.password_changed_at = datetime.now(timezone.utc)
        # Somebody else chose it, so it is a start password like any other.
        user.must_change_password = True
    db.add(user)
    db.flush()
    _set_branches(db, user, payload.branch_ids)

    audit(
        db,
        "user",
        user.id,
        "created",
        {
            "display_name": user.display_name,
            "email": user.email,
            "role_id": user.role_id,
            "all_branches": user.all_branches,
            "branch_ids": sorted(payload.branch_ids),
            "with_password": bool(payload.password),
        },
        principal,
    )
    db.commit()
    return _user_read(_load(db, user.id))


@router.patch("/api/users/{user_id}", response_model=schemas.UserAdminRead)
def update_user(
    user_id: str, payload: schemas.UserUpdate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.UserAdminRead:
    user = _load(db, user_id)
    changes = payload.model_dump(exclude_unset=True)
    _guard_self_lockout(db, principal, user, changes)

    if "email" in changes and changes["email"]:
        email = changes["email"].strip().lower()
        clash = db.scalar(
            select(models.User).where(func.lower(models.User.email) == email, models.User.id != user_id)
        )
        if clash:
            raise HTTPException(status_code=409, detail=f"Ein Konto mit '{email}' existiert bereits.")
        changes["email"] = email
    if "role_id" in changes:
        ensure_ref(db, models.Role, changes["role_id"], "role_id")

    branch_ids = changes.pop("branch_ids", None)
    before = {field: getattr(user, field) for field in changes}
    for field, value in changes.items():
        setattr(user, field, value)
    if branch_ids is not None:
        before["branch_ids"] = sorted(link.branch_id for link in user.branch_links)
        _set_branches(db, user, branch_ids)
        changes["branch_ids"] = sorted(branch_ids)
    if changes.get("is_active") is False:
        # A deactivated account keeps its rows but loses its running sessions.
        user.token_version = (user.token_version or 1) + 1

    audit(db, "user", user_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    return _user_read(_load(db, user_id))


@router.post("/api/users/{user_id}/password", response_model=schemas.UserAdminRead)
def set_password(
    user_id: str, payload: schemas.PasswordSet, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.UserAdminRead:
    """Sets a password for somebody else - the way back in after a lockout.

    The new password is never stored in the audit log, only the fact that it
    was set and by whom.
    """
    if not settings.auth_password_login_enabled:
        raise HTTPException(status_code=404, detail="Die Passwort-Anmeldung ist deaktiviert.")
    user = _load(db, user_id)
    problem = security.password_problem(
        payload.new_password, display_name=user.display_name, email=user.email
    )
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    user.password_hash = security.hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = payload.must_change
    user.failed_login_count = 0
    user.locked_until = None
    user.token_version = (user.token_version or 1) + 1
    audit(db, "user", user_id, "password_set", {"must_change": payload.must_change}, principal)
    db.commit()
    return _user_read(_load(db, user_id))


@router.delete("/api/users/{user_id}/password", response_model=schemas.UserAdminRead)
def clear_password(user_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> schemas.UserAdminRead:
    """Removes the password login from an account, leaving Entra ID.

    The normal state for everybody except the emergency administrator: no
    password, no password to lose.
    """
    user = _load(db, user_id)
    user.password_hash = None
    user.must_change_password = False
    user.token_version = (user.token_version or 1) + 1
    audit(db, "user", user_id, "password_cleared", {}, principal)
    db.commit()
    return _user_read(_load(db, user_id))


@router.post("/api/users/{user_id}/unlock", response_model=schemas.UserAdminRead)
def unlock_user(user_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> schemas.UserAdminRead:
    user = _load(db, user_id)
    user.failed_login_count = 0
    user.locked_until = None
    audit(db, "user", user_id, "unlocked", {}, principal)
    db.commit()
    return _user_read(_load(db, user_id))


@router.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    """Removes an account that never did anything.

    An account referenced by a record, a measure or the audit log is not
    deleted: the trail of who did what would break. Deactivating is the answer
    there, and the error says so.
    """
    user = _load(db, user_id)
    if user.id == principal.user_id:
        raise HTTPException(status_code=409, detail="Das eigene Konto kann nicht geloescht werden.")

    references = [
        (models.ComplianceRecord, "owner_user_id", "Compliance-Eintrag/-Eintraege"),
        (models.ComplianceAction, "owner_user_id", "Massnahme(n)"),
        (models.AuditLog, "actor_user_id", "Protokolleintrag/-eintraege"),
        (models.Branch, "manager_user_id", "Niederlassung(en)"),
    ]
    blocking = []
    for model, attribute, label in references:
        count = db.scalar(
            select(func.count()).select_from(model).where(getattr(model, attribute) == user_id)
        )
        if count:
            blocking.append(f"{count} {label}")
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Das Konto ist verknuepft mit: "
                + ", ".join(blocking)
                + ". Stattdessen deaktivieren - dann bleibt nachvollziehbar, wer was getan hat."
            ),
        )

    audit(db, "user", user_id, "deleted", snapshot(user) | {"password_hash": None}, principal)
    for link in list(user.branch_links):
        db.delete(link)
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Roles and permissions
# --------------------------------------------------------------------------


@router.get("/api/permissions", response_model=list[schemas.PermissionRead])
def list_permissions(principal: ReadDep) -> list[schemas.PermissionRead]:
    return [
        schemas.PermissionRead(key=key, area=area, label=label, description=description)
        for key, area, label, description in PERMISSION_CATALOGUE
    ]


@router.get("/api/roles", response_model=list[schemas.RoleRead])
def list_roles(principal: ReadDep, db: Session = Depends(get_db)) -> list[schemas.RoleRead]:
    counts = dict(
        db.execute(
            select(models.User.role_id, func.count(models.User.id)).group_by(models.User.role_id)
        ).all()
    )
    roles = db.scalars(select(models.Role).order_by(models.Role.name.asc())).all()
    return [
        schemas.RoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=sorted(role.permissions or []),
            system=bool(role.system),
            user_count=int(counts.get(role.id, 0)),
        )
        for role in roles
    ]


def _validate_permissions(values: list[str]) -> list[str]:
    known = set(permissions.ALL_PERMISSIONS) | {permissions.WILDCARD}
    unknown = [item for item in values if item not in known]
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unbekannte Berechtigung(en): {', '.join(sorted(unknown))}"
        )
    return sorted(set(values))


@router.post("/api/roles", response_model=schemas.RoleRead, status_code=201)
def create_role(
    payload: schemas.RoleCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.RoleRead:
    if db.scalar(select(models.Role).where(models.Role.name == payload.name.strip())):
        raise HTTPException(status_code=409, detail=f"Die Rolle '{payload.name}' existiert bereits.")
    role = models.Role(
        name=payload.name.strip(),
        description=payload.description,
        permissions=_validate_permissions(payload.permissions),
        system=False,
    )
    db.add(role)
    db.flush()
    audit(db, "role", role.id, "created", {"name": role.name, "permissions": role.permissions}, principal)
    db.commit()
    db.refresh(role)
    return schemas.RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=sorted(role.permissions or []),
        system=False,
        user_count=0,
    )


@router.patch("/api/roles/{role_id}", response_model=schemas.RoleRead)
def update_role(
    role_id: str, payload: schemas.RoleUpdate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.RoleRead:
    role = get_or_404(db, models.Role, role_id, "Rolle")
    if role.system:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Die Standardrollen werden bei jedem Start aus dem Programm abgeglichen "
                "und lassen sich nicht aendern. Fuer eine Abweichung eine eigene Rolle anlegen."
            ),
        )
    changes = payload.model_dump(exclude_unset=True)
    if "permissions" in changes and changes["permissions"] is not None:
        changes["permissions"] = _validate_permissions(changes["permissions"])
    before = {field: getattr(role, field) for field in changes}
    for field, value in changes.items():
        setattr(role, field, value)
    audit(db, "role", role_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    db.refresh(role)
    return schemas.RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=sorted(role.permissions or []),
        system=False,
        user_count=int(
            db.scalar(select(func.count(models.User.id)).where(models.User.role_id == role.id)) or 0
        ),
    )


@router.delete("/api/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    role = get_or_404(db, models.Role, role_id, "Rolle")
    if role.system:
        raise HTTPException(status_code=409, detail="Standardrollen lassen sich nicht loeschen.")
    in_use = db.scalar(select(func.count(models.User.id)).where(models.User.role_id == role_id)) or 0
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Die Rolle ist {in_use} Konto/Konten zugeordnet. Zuerst umhaengen.",
        )
    audit(db, "role", role_id, "deleted", snapshot(role), principal)
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
