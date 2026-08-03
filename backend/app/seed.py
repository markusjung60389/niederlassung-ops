from sqlalchemy.orm import Session

from . import models


def seed_base_data(db: Session) -> None:
    if db.query(models.Branch).first():
        return

    branch = models.Branch(id="branch-remscheid", name="Remscheid", location="Remscheid")
    manager_role = models.Role(id="role-branch-manager", name="Niederlassungsleiter", permissions=["*"])
    hse_role = models.Role(id="role-hse", name="HSE / Compliance", permissions=["compliance:write"])
    manager = models.User(
        id="user-branch-manager",
        display_name="Niederlassungsleitung Remscheid",
        email="leitung.remscheid@example.local",
        role=manager_role,
    )
    hse = models.User(
        id="user-hse",
        display_name="HSE Verantwortliche",
        email="hse.remscheid@example.local",
        role=hse_role,
    )
    db.add_all([branch, manager_role, hse_role, manager, hse])
    db.commit()
