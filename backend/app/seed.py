import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import catalog, models, permissions, security
from .config import settings

logger = logging.getLogger(__name__)

ROLE_IDS = {
    permissions.ROLE_ADMIN: "role-admin",
    permissions.ROLE_AREA_MANAGER: "role-area-manager",
    permissions.ROLE_BRANCH_MANAGER: "role-branch-manager",
    permissions.ROLE_HSE: "role-hse",
    permissions.ROLE_VIEWER: "role-viewer",
}


ROLE_DESCRIPTIONS = {
    permissions.ROLE_ADMIN: "Verwaltung des Werkzeugs: Konten, Rollen, Notfallzugang.",
    permissions.ROLE_AREA_MANAGER: "Verantwortet mehrere Niederlassungen, setzt Gruppenvorgaben.",
    permissions.ROLE_BRANCH_MANAGER: "Fuehrt eine Niederlassung; volle Fachrechte vor Ort.",
    permissions.ROLE_HSE: "Arbeitssicherheit und Compliance ueber die Standorte hinweg.",
    permissions.ROLE_VIEWER: "Liest mit, aendert nichts.",
}


def seed_roles(db: Session) -> dict[str, models.Role]:
    """Creates the role presets and keeps their permissions in sync.

    The presets are system defined and authoritative: a deployment that
    upgrades to a new permission catalogue picks the change up on restart.
    Roles created in the user administration are not touched here.
    """
    roles: dict[str, models.Role] = {}
    for name, preset in permissions.ROLE_PRESETS.items():
        role = db.scalar(select(models.Role).where(models.Role.name == name))
        if role is None:
            role = models.Role(id=ROLE_IDS[name], name=name, permissions=list(preset))
            db.add(role)
        elif sorted(role.permissions or []) != sorted(preset):
            role.permissions = list(preset)
        role.system = True
        role.description = role.description or ROLE_DESCRIPTIONS.get(name)
        roles[name] = role
    db.flush()
    return roles


def seed_admin_account(db: Session, roles: dict[str, models.Role]) -> None:
    """Creates the emergency administrator on an installation that has none.

    Not a convenience: without it, an installation whose Entra ID registration
    is wrong has nobody who can fix it. The start password comes from
    ADMIN_INITIAL_PASSWORD and has to be replaced at the first login - until
    then the API answers nothing but the change itself.

    Runs once. An existing account is never given a password back, so removing
    the local login stays removed.
    """
    email = settings.admin_email.strip().lower()
    existing = db.scalar(select(models.User).where(func.lower(models.User.email) == email))
    if existing is not None:
        return
    # Somebody may have renamed the account; a second administrator is not
    # created behind their back.
    if db.scalar(
        select(func.count(models.User.id)).where(models.User.role_id == ROLE_IDS[permissions.ROLE_ADMIN])
    ):
        return

    db.add(
        models.User(
            id="user-admin",
            display_name=settings.admin_display_name,
            email=email,
            role=roles[permissions.ROLE_ADMIN],
            all_branches=True,
            password_hash=security.hash_password(settings.admin_initial_password),
            password_changed_at=datetime.now(timezone.utc),
            must_change_password=True,
        )
    )
    db.flush()
    logger.warning(
        "Notfall-Administrator '%s' angelegt. Das Startpasswort muss bei der ersten "
        "Anmeldung geaendert werden.",
        email,
    )


def seed_qualification_types(db: Session) -> None:
    """Adds catalogue entries that do not exist yet.

    Existing rows are left alone on purpose: once a branch has adjusted a
    validity period or a reminder window, the seed must not overwrite it.
    """
    for entry in catalog.QUALIFICATION_TYPES:
        if db.get(models.QualificationType, entry.id) is not None:
            continue
        if db.scalar(select(models.QualificationType).where(models.QualificationType.code == entry.code)):
            continue
        db.add(
            models.QualificationType(
                id=entry.id,
                code=entry.code,
                name=entry.name,
                category=entry.category,
                validity_months=entry.validity_months,
                reminder_days=entry.reminder_days,
                evidence_required=entry.evidence_required,
                legal_basis=entry.legal_basis,
                description=entry.description,
            )
        )
    db.flush()


def seed_job_roles(db: Session) -> None:
    """Creates the branch functions and their requirement matrix.

    Requirements are only added for functions this seed created; a function the
    branch has since edited keeps its own matrix.
    """
    for entry in catalog.JOB_ROLES:
        role = db.get(models.JobRole, entry.id)
        if role is not None:
            continue
        if db.scalar(select(models.JobRole).where(models.JobRole.name == entry.name)):
            continue
        db.add(models.JobRole(id=entry.id, name=entry.name, description=entry.description))
        db.flush()
        for type_id, mandatory in entry.requirements:
            if db.get(models.QualificationType, type_id) is None:
                continue
            db.add(
                models.JobRoleRequirement(
                    job_role_id=entry.id, qualification_type_id=type_id, mandatory=mandatory
                )
            )
    db.flush()


def link_employees_to_job_roles(db: Session) -> None:
    """Connects employees whose free-text role matches a function by name.

    Runs on every start so entries created through the old text field keep
    finding their function. Never clears an assignment that already exists.
    """
    roles = {role.name.casefold(): role.id for role in db.scalars(select(models.JobRole)).all()}
    if not roles:
        return
    unlinked = db.scalars(select(models.Employee).where(models.Employee.job_role_id.is_(None))).all()
    for employee in unlinked:
        match = roles.get((employee.role or "").strip().casefold())
        if match:
            employee.job_role_id = match
    db.flush()


def link_users_to_branches(db: Session) -> None:
    """Gives an account without any branch its home branch.

    An account with no link and without `all_branches` sees nothing at all, so
    an installation that predates the branch scoping would lock its users out
    on the first start after the upgrade.
    """
    branch = db.scalar(select(models.Branch).order_by(models.Branch.created_at.asc()))
    if branch is None:
        return
    linked = set(db.scalars(select(models.UserBranch.user_id)).all())
    for user in db.scalars(select(models.User)).all():
        if user.all_branches or user.id in linked:
            continue
        db.add(models.UserBranch(user_id=user.id, branch_id=branch.id))
    db.flush()


def seed_base_data(db: Session) -> None:
    roles = seed_roles(db)
    seed_qualification_types(db)
    seed_job_roles(db)

    if db.scalar(select(models.Branch).limit(1)) is None:
        db.add(
            models.Branch(id="branch-remscheid", name="Remscheid", location="Remscheid", code="RS")
        )

    # Further branches are not seeded: their names, codes and managers are the
    # organisation's, not this file's. The area manager creates them under
    # Niederlassungen, and every group-wide rule reaches them from that moment.
    accounts = [
        (
            "user-area-manager",
            "Bereichsleitung",
            "bereichsleitung@example.local",
            permissions.ROLE_AREA_MANAGER,
            True,
        ),
        (
            "user-branch-manager",
            "Niederlassungsleitung Remscheid",
            "leitung.remscheid@example.local",
            permissions.ROLE_BRANCH_MANAGER,
            False,
        ),
        ("user-hse", "HSE Verantwortliche", "hse.remscheid@example.local", permissions.ROLE_HSE, False),
        (
            "user-viewer",
            "Betrachter Remscheid",
            "betrachter.remscheid@example.local",
            permissions.ROLE_VIEWER,
            False,
        ),
    ]
    for user_id, display_name, email, role_name, all_branches in accounts:
        if db.get(models.User, user_id) is None:
            db.add(
                models.User(
                    id=user_id,
                    display_name=display_name,
                    email=email,
                    role=roles[role_name],
                    all_branches=all_branches,
                )
            )

    db.flush()
    seed_admin_account(db, roles)
    link_users_to_branches(db)
    link_employees_to_job_roles(db)
    db.commit()
