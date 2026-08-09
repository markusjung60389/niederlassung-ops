"""Qualification catalogue, branch functions and the requirement matrix.

Everything here is reference data the branch maintains itself. It is seeded on
first start (see `app/catalog.py`) and editable afterwards - a branch that adds
a qualification does not need a release.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import catalog, models, permissions, schemas, serializers
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, ensure_ref, get_or_404, guard_children, snapshot

router = APIRouter(tags=["catalog"])

WriteDep = Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))]
read_dependency = Depends(requires(permissions.PERSONNEL_READ))


# --------------------------------------------------------------------------
# Qualification types
# --------------------------------------------------------------------------


@router.get(
    "/api/qualification-types",
    response_model=list[schemas.QualificationTypeRead],
    dependencies=[read_dependency],
)
def list_qualification_types(
    include_inactive: bool = False, db: Session = Depends(get_db)
) -> list[schemas.QualificationTypeRead]:
    query = select(models.QualificationType)
    if not include_inactive:
        query = query.where(models.QualificationType.active.is_(True))
    types = db.scalars(query.order_by(models.QualificationType.name.asc())).all()
    return [serializers.qualification_type_read(item) for item in types]


@router.post("/api/qualification-types", response_model=schemas.QualificationTypeRead, status_code=201)
def create_qualification_type(
    payload: schemas.QualificationTypeCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.QualificationTypeRead:
    existing = db.scalar(
        select(models.QualificationType).where(models.QualificationType.code == payload.code)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Qualification type '{payload.code}' already exists",
        )
    kind = models.QualificationType(**payload.model_dump())
    db.add(kind)
    db.flush()
    audit(db, "qualification_type", kind.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(kind)
    return serializers.qualification_type_read(kind)


@router.patch(
    "/api/qualification-types/{type_id}", response_model=schemas.QualificationTypeRead
)
def update_qualification_type(
    type_id: str,
    payload: schemas.QualificationTypeUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.QualificationTypeRead:
    kind = get_or_404(db, models.QualificationType, type_id, "Qualification type")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(kind, field) for field in changes}
    for field, value in changes.items():
        setattr(kind, field, value)
    audit(db, "qualification_type", type_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    db.refresh(kind)
    return serializers.qualification_type_read(kind)


@router.delete("/api/qualification-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_qualification_type(
    type_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    kind = get_or_404(db, models.QualificationType, type_id, "Qualification type")
    guard_children(
        db,
        [
            (models.JobRoleRequirement, "qualification_type_id", "requirement(s)"),
            (models.EmployeeQualification, "qualification_type_id", "recorded qualification(s)"),
        ],
        type_id,
    )
    audit(db, "qualification_type", type_id, "deleted", snapshot(kind), principal)
    db.delete(kind)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Job roles (functions) and their requirements
# --------------------------------------------------------------------------


def _load_role(db: Session, role_id: str) -> models.JobRole:
    role = db.scalar(
        select(models.JobRole)
        .where(models.JobRole.id == role_id)
        .options(selectinload(models.JobRole.requirements))
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job role not found")
    return role


def _employee_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(models.Employee.job_role_id, func.count())
        .where(models.Employee.status == "active")
        .group_by(models.Employee.job_role_id)
    ).all()
    return {role_id: count for role_id, count in rows if role_id}


@router.get("/api/job-roles", response_model=list[schemas.JobRoleRead], dependencies=[read_dependency])
def list_job_roles(
    include_inactive: bool = False, db: Session = Depends(get_db)
) -> list[schemas.JobRoleRead]:
    query = select(models.JobRole).options(selectinload(models.JobRole.requirements))
    if not include_inactive:
        query = query.where(models.JobRole.active.is_(True))
    roles = db.scalars(query.order_by(models.JobRole.name.asc())).all()
    counts = _employee_counts(db)
    return [serializers.job_role_read(role, counts.get(role.id, 0)) for role in roles]


@router.post("/api/job-roles", response_model=schemas.JobRoleRead, status_code=201)
def create_job_role(
    payload: schemas.JobRoleCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.JobRoleRead:
    if db.scalar(select(models.JobRole).where(models.JobRole.name == payload.name)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Function '{payload.name}' already exists"
        )
    role = models.JobRole(**payload.model_dump())
    db.add(role)
    db.flush()
    audit(db, "job_role", role.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    return serializers.job_role_read(_load_role(db, role.id))


@router.patch("/api/job-roles/{role_id}", response_model=schemas.JobRoleRead)
def update_job_role(
    role_id: str, payload: schemas.JobRoleUpdate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.JobRoleRead:
    role = _load_role(db, role_id)
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(role, field) for field in changes}
    for field, value in changes.items():
        setattr(role, field, value)
    audit(db, "job_role", role_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    counts = _employee_counts(db)
    return serializers.job_role_read(_load_role(db, role_id), counts.get(role_id, 0))


@router.delete("/api/job-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_role(role_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    role = _load_role(db, role_id)
    guard_children(db, [(models.Employee, "job_role_id", "employee(s)")], role_id)
    payload = snapshot(role)
    payload["requirements"] = [snapshot(item) for item in role.requirements]
    audit(db, "job_role", role_id, "deleted", payload, principal)
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/api/job-role-requirements", response_model=schemas.JobRoleRequirementRead, status_code=201
)
def create_requirement(
    payload: schemas.JobRoleRequirementCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.JobRoleRequirementRead:
    ensure_ref(db, models.JobRole, payload.job_role_id, "job_role_id")
    ensure_ref(db, models.QualificationType, payload.qualification_type_id, "qualification_type_id")
    duplicate = db.scalar(
        select(models.JobRoleRequirement).where(
            models.JobRoleRequirement.job_role_id == payload.job_role_id,
            models.JobRoleRequirement.qualification_type_id == payload.qualification_type_id,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This qualification is already required by the function",
        )
    requirement = models.JobRoleRequirement(**payload.model_dump())
    db.add(requirement)
    db.flush()
    audit(
        db, "job_role_requirement", requirement.id, "created", payload.model_dump(mode="json"), principal
    )
    db.commit()
    db.refresh(requirement)
    return serializers.requirement_read(requirement)


@router.patch(
    "/api/job-role-requirements/{requirement_id}", response_model=schemas.JobRoleRequirementRead
)
def update_requirement(
    requirement_id: str,
    payload: schemas.JobRoleRequirementUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.JobRoleRequirementRead:
    requirement = get_or_404(db, models.JobRoleRequirement, requirement_id, "Requirement")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(requirement, field) for field in changes}
    for field, value in changes.items():
        setattr(requirement, field, value)
    audit(
        db,
        "job_role_requirement",
        requirement_id,
        "updated",
        {"before": before, "after": changes},
        principal,
    )
    db.commit()
    db.refresh(requirement)
    return serializers.requirement_read(requirement)


@router.delete("/api/job-role-requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(
    requirement_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    requirement = get_or_404(db, models.JobRoleRequirement, requirement_id, "Requirement")
    audit(db, "job_role_requirement", requirement_id, "deleted", snapshot(requirement), principal)
    db.delete(requirement)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Derived views
# --------------------------------------------------------------------------


@router.get(
    "/api/qualification-matrix",
    response_model=schemas.QualificationMatrix,
    dependencies=[read_dependency],
)
def get_matrix(
    branch_id: str | None = None, db: Session = Depends(get_db)
) -> schemas.QualificationMatrix:
    return serializers.qualification_matrix(db, branch_id)


@router.get(
    "/api/compliance-templates",
    response_model=list[schemas.ComplianceTemplateRead],
    dependencies=[Depends(requires(permissions.COMPLIANCE_READ))],
)
def list_compliance_templates(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[schemas.ComplianceTemplateRead]:
    """Standard branch obligations offered when creating a compliance record.

    Reference data in code rather than a table - the manager picks one and
    receives an editable record, so nothing here has to be maintained by hand.
    """
    return [
        schemas.ComplianceTemplateRead(**vars(template))
        for template in catalog.COMPLIANCE_TEMPLATES[:limit]
    ]
