from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, permissions

ROLE_IDS = {
    permissions.ROLE_BRANCH_MANAGER: "role-branch-manager",
    permissions.ROLE_HSE: "role-hse",
    permissions.ROLE_VIEWER: "role-viewer",
}


def seed_roles(db: Session) -> dict[str, models.Role]:
    """Creates the role presets and keeps their permissions in sync.

    Roles are system defined, so the preset is authoritative: a deployment that
    upgrades to a new permission catalogue picks the change up on restart.
    """
    roles: dict[str, models.Role] = {}
    for name, preset in permissions.ROLE_PRESETS.items():
        role = db.scalar(select(models.Role).where(models.Role.name == name))
        if role is None:
            role = models.Role(id=ROLE_IDS[name], name=name, permissions=list(preset))
            db.add(role)
        elif sorted(role.permissions or []) != sorted(preset):
            role.permissions = list(preset)
        roles[name] = role
    db.flush()
    return roles


def seed_base_data(db: Session) -> None:
    roles = seed_roles(db)

    if db.scalar(select(models.Branch).limit(1)) is None:
        db.add(models.Branch(id="branch-remscheid", name="Remscheid", location="Remscheid"))

    accounts = [
        (
            "user-branch-manager",
            "Niederlassungsleitung Remscheid",
            "leitung.remscheid@example.local",
            permissions.ROLE_BRANCH_MANAGER,
        ),
        ("user-hse", "HSE Verantwortliche", "hse.remscheid@example.local", permissions.ROLE_HSE),
        ("user-viewer", "Betrachter Remscheid", "betrachter.remscheid@example.local", permissions.ROLE_VIEWER),
    ]
    for user_id, display_name, email, role_name in accounts:
        if db.get(models.User, user_id) is None:
            db.add(models.User(id=user_id, display_name=display_name, email=email, role=roles[role_name]))

    db.commit()
