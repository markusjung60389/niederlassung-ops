"""Branches, the portfolio across them, and the exception register.

The first two screens the area manager needs and the branch manager never
opens: which branch is drifting, and which exceptions have been taken since
he last looked.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import models, permissions, readiness, schemas, serializers
from ..auth import CurrentPrincipal, Principal, requires
from ..database import get_db
from ..deps import audit, ensure_branch_access, ensure_ref, get_or_404, guard_children, snapshot
from ..domain import today_local

router = APIRouter(tags=["branches"])

WriteDep = Annotated[Principal, Depends(requires(permissions.BRANCH_WRITE))]
RuleWriteDep = Annotated[Principal, Depends(requires(permissions.RULE_WRITE))]

# How long a newly taken exception counts as new to the area manager.
NEW_EXCEPTION_DAYS = 21
# Default grace period between revoking an exception and it taking effect.
REVOCATION_GRACE_DAYS = 30


# --------------------------------------------------------------------------
# Branches
# --------------------------------------------------------------------------


@router.get("/api/branches", response_model=list[schemas.BranchRead])
def list_branches(
    principal: CurrentPrincipal, include_inactive: bool = False, db: Session = Depends(get_db)
) -> list[schemas.BranchRead]:
    """Only the branches the caller belongs to.

    This drives the branch switcher, so a manager cannot even select a branch
    they have no business in.
    """
    query = select(models.Branch).order_by(models.Branch.name.asc())
    if not include_inactive:
        query = query.where(models.Branch.active.is_(True))
    branches = db.scalars(query).all()
    return [
        schemas.BranchRead.model_validate(branch)
        for branch in branches
        if principal.may_see(branch.id)
    ]


@router.post("/api/branches", response_model=schemas.BranchRead, status_code=201)
def create_branch(
    payload: schemas.BranchCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.BranchRead:
    if db.scalar(select(models.Branch).where(models.Branch.name == payload.name)):
        raise HTTPException(status_code=409, detail=f"Branch '{payload.name}' already exists")
    ensure_ref(db, models.User, payload.manager_user_id, "manager_user_id")
    branch = models.Branch(**payload.model_dump())
    db.add(branch)
    db.flush()
    audit(db, "branch", branch.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(branch)
    return schemas.BranchRead.model_validate(branch)


@router.patch("/api/branches/{branch_id}", response_model=schemas.BranchRead)
def update_branch(
    branch_id: str, payload: schemas.BranchUpdate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.BranchRead:
    branch = get_or_404(db, models.Branch, branch_id, "Branch")
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.User, changes.get("manager_user_id"), "manager_user_id")
    before = {field: getattr(branch, field) for field in changes}
    for field, value in changes.items():
        setattr(branch, field, value)
    audit(db, "branch", branch_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    db.refresh(branch)
    return schemas.BranchRead.model_validate(branch)


@router.delete("/api/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(branch_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    branch = get_or_404(db, models.Branch, branch_id, "Branch")
    guard_children(
        db,
        [
            (models.Employee, "branch_id", "employee(s)"),
            (models.Vehicle, "branch_id", "vehicle(s)"),
            (models.ComplianceRecord, "branch_id", "compliance record(s)"),
        ],
        branch_id,
    )
    audit(db, "branch", branch_id, "deleted", snapshot(branch), principal)
    db.delete(branch)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Portfolio
# --------------------------------------------------------------------------


@router.get("/api/portfolio", response_model=list[schemas.BranchPortfolioRow])
def portfolio(principal: CurrentPrincipal, db: Session = Depends(get_db)) -> list[schemas.BranchPortfolioRow]:
    """One row per branch, the same figures computed the same way.

    That comparability is the reason the catalogue stays group-wide: if every
    branch defined "instruction" for itself, the column next door would mean
    nothing.
    """
    if not principal.has(permissions.PERSONNEL_READ) and not principal.has(permissions.COMPLIANCE_READ):
        raise HTTPException(status_code=403, detail="Missing permission(s): personnel:read or compliance:read")

    today = today_local()
    fresh_since = today - timedelta(days=NEW_EXCEPTION_DAYS)
    overrides = readiness.load_overrides(db)
    branches = [
        branch
        for branch in db.scalars(
            select(models.Branch).where(models.Branch.active.is_(True)).order_by(models.Branch.name.asc())
        ).all()
        if principal.may_see(branch.id)
    ]

    rows: list[schemas.BranchPortfolioRow] = []
    for branch in branches:
        employees = db.scalars(serializers.employee_query([branch.id])).all()
        blocked = limited = 0
        for employee in employees:
            level = readiness.readiness_of(readiness.requirement_states(employee, branch.id, overrides))
            blocked += level == readiness.BLOCKED
            limited += level == readiness.LIMITED

        # Headcount and the first-aider quota count the home branch only:
        # a person deployed in three branches must not count three times.
        home = [item for item in employees if item.branch_id == branch.id]
        trained = sum(1 for item in home if item.first_aider)
        required = readiness.first_aider_target(len(home))

        overdue = db.scalar(
            select(func.count(models.ComplianceRecord.id)).where(
                models.ComplianceRecord.branch_id == branch.id,
                models.ComplianceRecord.due_date < today,
                models.ComplianceRecord.status.notin_(["compliant", "waived"]),
            )
        ) or 0

        vehicles = db.scalars(
            select(models.Vehicle).where(
                func.coalesce(models.Vehicle.current_branch_id, models.Vehicle.branch_id) == branch.id
            )
        ).all()
        due_vehicles = sum(1 for vehicle in vehicles if readiness.vehicle_due_items(vehicle))

        branch_overrides = [
            item
            for (override_branch, _), item in overrides.items()
            if override_branch == branch.id and readiness.override_is_active(item, today)
        ]
        new_exceptions = sum(
            1
            for item in branch_overrides
            if item.acknowledged_at is None and item.created_at.date() >= fresh_since
        )

        state = "red" if blocked or overdue else ("yellow" if limited or due_vehicles or trained < required else "green")
        rows.append(
            schemas.BranchPortfolioRow(
                branch_id=branch.id,
                branch_name=branch.name,
                code=branch.code,
                headcount=len(home),
                blocked=blocked,
                limited=limited,
                overdue_compliance=int(overdue),
                due_vehicles=due_vehicles,
                first_aiders_trained=trained,
                first_aiders_required=required,
                open_exceptions=len(branch_overrides),
                new_exceptions=new_exceptions,
                state=state,
            )
        )
    return rows


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------


def _override_read(override: models.RequirementOverride, today) -> schemas.RequirementOverrideRead:
    requirement = override.requirement
    return schemas.RequirementOverrideRead(
        id=override.id,
        branch_id=override.branch_id,
        branch_name=override.branch.name,
        requirement_id=override.requirement_id,
        job_role_id=requirement.job_role_id,
        job_role_name=requirement.job_role.name,
        qualification_name=requirement.qualification_type.name,
        mode=override.mode,
        reason=override.reason,
        valid_until=override.valid_until,
        created_by=override.created_by,
        created_at=override.created_at,
        acknowledged_at=override.acknowledged_at,
        revoked_at=override.revoked_at,
        revoked_reason=override.revoked_reason,
        revoked_effective_from=override.revoked_effective_from,
        active=readiness.override_is_active(override, today),
    )


@router.get(
    "/api/requirement-overrides",
    response_model=list[schemas.RequirementOverrideRead],
    dependencies=[Depends(requires(permissions.RULE_READ))],
)
def list_overrides(
    principal: CurrentPrincipal,
    branch_id: str | None = None,
    include_revoked: bool = False,
    db: Session = Depends(get_db),
) -> list[schemas.RequirementOverrideRead]:
    today = today_local()
    query = select(models.RequirementOverride).options(
        selectinload(models.RequirementOverride.requirement).selectinload(
            models.JobRoleRequirement.job_role
        )
    )
    allowed = principal.scope(branch_id)
    if allowed is not None:
        query = query.where(models.RequirementOverride.branch_id.in_(allowed or ["-"]))
    items = db.scalars(query.order_by(models.RequirementOverride.created_at.desc())).all()
    return [
        _override_read(item, today)
        for item in items
        if include_revoked or readiness.override_is_active(item, today)
    ]


@router.post(
    "/api/requirement-overrides", response_model=schemas.RequirementOverrideRead, status_code=201
)
def create_override(
    payload: schemas.RequirementOverrideCreate,
    principal: Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.RequirementOverrideRead:
    """A branch manager sets this for their own branch, without approval.

    It becomes visible to the area manager immediately, who can revoke it -
    which is why the reason is mandatory and the entry is a row rather than a
    silent absence.
    """
    ensure_branch_access(principal, payload.branch_id)
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.JobRoleRequirement, payload.requirement_id, "requirement_id")
    existing = db.scalar(
        select(models.RequirementOverride).where(
            models.RequirementOverride.branch_id == payload.branch_id,
            models.RequirementOverride.requirement_id == payload.requirement_id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="An exception for this requirement already exists")

    override = models.RequirementOverride(**payload.model_dump(), created_by=principal.user_id)
    db.add(override)
    db.flush()
    audit(
        db,
        "requirement_override",
        override.id,
        "created",
        payload.model_dump(mode="json"),
        principal,
    )
    db.commit()
    db.refresh(override)
    return _override_read(override, today_local())


@router.post(
    "/api/requirement-overrides/{override_id}/revoke",
    response_model=schemas.RequirementOverrideRead,
)
def revoke_override(
    override_id: str,
    payload: schemas.RequirementOverrideRevoke,
    principal: RuleWriteDep,
    db: Session = Depends(get_db),
) -> schemas.RequirementOverrideRead:
    override = get_or_404(db, models.RequirementOverride, override_id, "Exception")
    override.revoked_by = principal.user_id
    override.revoked_at = models.utcnow()
    override.revoked_reason = payload.reason
    override.revoked_effective_from = payload.effective_from or (
        today_local() + timedelta(days=REVOCATION_GRACE_DAYS)
    )
    audit(
        db,
        "requirement_override",
        override_id,
        "revoked",
        {"reason": payload.reason, "effective_from": override.revoked_effective_from.isoformat()},
        principal,
    )
    db.commit()
    db.refresh(override)
    return _override_read(override, today_local())


@router.post(
    "/api/requirement-overrides/{override_id}/acknowledge",
    response_model=schemas.RequirementOverrideRead,
)
def acknowledge_override(
    override_id: str, principal: RuleWriteDep, db: Session = Depends(get_db)
) -> schemas.RequirementOverrideRead:
    """Marks an exception as seen, so "new" keeps meaning new."""
    override = get_or_404(db, models.RequirementOverride, override_id, "Exception")
    override.acknowledged_by = principal.user_id
    override.acknowledged_at = models.utcnow()
    db.commit()
    db.refresh(override)
    return _override_read(override, today_local())


@router.delete(
    "/api/requirement-overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_override(
    override_id: str,
    principal: Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))],
    db: Session = Depends(get_db),
) -> Response:
    override = get_or_404(db, models.RequirementOverride, override_id, "Exception")
    ensure_branch_access(principal, override.branch_id)
    audit(db, "requirement_override", override_id, "deleted", snapshot(override), principal)
    db.delete(override)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
