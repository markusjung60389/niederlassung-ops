from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import crud, models, permissions, schemas, storage
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, ensure_branch_access, ensure_ref, get_or_404, guard_children, snapshot
from ..domain import add_months
from ..readiness import load_overrides
from ..serializers import employee_query, employee_read, profile_read, qualification_read

router = APIRouter(tags=["personnel"])

WriteDep = Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.PERSONNEL_READ))]
read_dependency = Depends(requires(permissions.PERSONNEL_READ))


# --------------------------------------------------------------------------
# Employees
# --------------------------------------------------------------------------


@router.get("/api/employees", response_model=list[schemas.EmployeeRead])
def list_employees(
    principal: ReadDep,
    branch_id: str | None = None,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[schemas.EmployeeRead]:
    """Employees of the selected branch, home branch or deployment.

    Deployability is reported for that branch: an exception granted elsewhere
    does not travel with the person.
    """
    query = employee_query(principal.scope(branch_id), include_inactive=include_inactive)
    employees = db.scalars(query.limit(limit)).all()
    overrides = load_overrides(db)
    return [employee_read(employee, branch_id, overrides) for employee in employees]


@router.post("/api/employees", response_model=schemas.EmployeeRead)
def create_employee(
    payload: schemas.EmployeeCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.EmployeeRead:
    # Existence first: a branch id that does not exist is a bad request in any
    # scope, and reporting it as "no access" would send the caller looking for
    # a permission problem they do not have.
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_branch_access(principal, payload.branch_id)
    ensure_ref(db, models.JobRole, payload.job_role_id, "job_role_id")
    employee = models.Employee(**payload.model_dump())
    db.add(employee)
    db.flush()
    audit(db, "employee", employee.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(employee)
    return employee_read(employee)


@router.get("/api/employees/{employee_id}", response_model=schemas.EmployeeRead)
def get_employee(
    employee_id: str,
    principal: ReadDep,
    branch_id: str | None = None,
    db: Session = Depends(get_db),
) -> schemas.EmployeeRead:
    employee = get_or_404(db, models.Employee, employee_id, "Employee")
    if not any(principal.may_see(item) for item in employee.assigned_branch_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee_read(employee, branch_id, load_overrides(db))


@router.patch("/api/employees/{employee_id}", response_model=schemas.EmployeeRead)
def update_employee(
    employee_id: str,
    payload: schemas.EmployeeUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.EmployeeRead:
    employee = get_or_404(db, models.Employee, employee_id, "Employee")
    changes = payload.model_dump(exclude_unset=True)
    if "job_role_id" in changes:
        ensure_ref(db, models.JobRole, changes["job_role_id"], "job_role_id")
    before = {field: getattr(employee, field) for field in changes}
    for field, value in changes.items():
        setattr(employee, field, value)
    audit(db, "employee", employee_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    db.refresh(employee)
    return employee_read(employee)


@router.post("/api/employees/{employee_id}/branches", response_model=schemas.EmployeeRead)
def assign_to_branch(
    employee_id: str,
    payload: schemas.EmployeeBranchCreate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.EmployeeRead:
    """Deploys somebody to a second branch besides their home branch.

    Requirements add up rather than being replaced: whoever works in two
    branches has to satisfy both sets, otherwise an exception granted in one
    would quietly become a licence to work in the other.
    """
    employee = get_or_404(db, models.Employee, employee_id, "Employee")
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    # Both ends: the branch giving the person away and the one receiving them.
    ensure_branch_access(principal, employee.branch_id)
    ensure_branch_access(principal, payload.branch_id)
    if payload.branch_id == employee.branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is already the employee's home branch",
        )
    if any(link.branch_id == payload.branch_id for link in employee.branch_links):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already deployed to this branch"
        )

    link = models.EmployeeBranch(employee_id=employee_id, branch_id=payload.branch_id, note=payload.note)
    db.add(link)
    db.flush()
    audit(db, "employee", employee_id, "branch_assigned", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(employee)
    return employee_read(employee, None, load_overrides(db))


@router.delete("/api/employees/{employee_id}/branches/{branch_id}", response_model=schemas.EmployeeRead)
def remove_from_branch(
    employee_id: str, branch_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.EmployeeRead:
    employee = get_or_404(db, models.Employee, employee_id, "Employee")
    ensure_branch_access(principal, employee.branch_id)
    ensure_branch_access(principal, branch_id)
    link = next((item for item in employee.branch_links if item.branch_id == branch_id), None)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    audit(db, "employee", employee_id, "branch_removed", snapshot(link), principal)
    db.delete(link)
    db.commit()
    db.refresh(employee)
    return employee_read(employee, None, load_overrides(db))


@router.delete("/api/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    employee = get_or_404(db, models.Employee, employee_id, "Employee")
    guard_children(
        db,
        [
            (models.Vehicle, "assigned_employee_id", "assigned vehicle(s)"),
            (models.ComplianceEvidence, "linked_employee_id", "linked evidence item(s)"),
            (models.EmployeeReview, "employee_id", "review(s)"),
        ],
        employee_id,
    )
    payload = snapshot(employee)
    payload["qualifications"] = [snapshot(item) for item in employee.qualifications]
    if employee.profile:
        payload["profile"] = snapshot(employee.profile)
    audit(db, "employee", employee_id, "deleted", payload, principal)

    for qualification in employee.qualifications:
        db.delete(qualification)
    if employee.profile:
        db.delete(employee.profile)
    db.delete(employee)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Qualifications
# --------------------------------------------------------------------------


def apply_catalogue_defaults(db: Session, values: dict) -> dict:
    """Fills in what the catalogue already knows.

    A course entered on 12.09. with a two-year validity should not require the
    user to work out the expiry date; getting that arithmetic wrong is exactly
    how a certificate silently lapses. The label and the reminder window come
    from the catalogue for the same reason.
    """
    type_id = values.get("qualification_type_id")
    if not type_id:
        return values
    kind = db.get(models.QualificationType, type_id)
    if kind is None:
        return values

    if not values.get("title"):
        values["title"] = kind.name
    if not values.get("qualification_type"):
        values["qualification_type"] = kind.code
    values["reminder_days"] = kind.reminder_days

    issued = values.get("issued_on")
    if values.get("valid_until") is None and issued and kind.validity_months:
        values["valid_until"] = add_months(issued, kind.validity_months)
    return values


@router.get(
    "/api/employee-qualifications",
    response_model=list[schemas.EmployeeQualificationRead],
    dependencies=[read_dependency],
)
def list_qualifications(
    employee_id: str | None = None, db: Session = Depends(get_db)
) -> list[schemas.EmployeeQualificationRead]:
    query = select(models.EmployeeQualification)
    if employee_id:
        query = query.where(models.EmployeeQualification.employee_id == employee_id)
    return [
        qualification_read(item)
        for item in db.scalars(query.order_by(models.EmployeeQualification.valid_until.asc())).all()
    ]


@router.post("/api/employee-qualifications", response_model=schemas.EmployeeQualificationRead)
def create_qualification(
    payload: schemas.EmployeeQualificationCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.EmployeeQualificationRead:
    ensure_ref(db, models.Employee, payload.employee_id, "employee_id")
    ensure_ref(db, models.Document, payload.document_id, "document_id")
    ensure_ref(db, models.QualificationType, payload.qualification_type_id, "qualification_type_id")
    values = apply_catalogue_defaults(db, payload.model_dump())
    qualification = models.EmployeeQualification(**values)
    db.add(qualification)
    db.flush()
    audit(
        db, "employee_qualification", qualification.id, "created", payload.model_dump(mode="json"), principal
    )
    db.commit()
    db.refresh(qualification)
    return qualification_read(qualification)


@router.patch(
    "/api/employee-qualifications/{qualification_id}", response_model=schemas.EmployeeQualificationRead
)
def update_qualification(
    qualification_id: str,
    payload: schemas.EmployeeQualificationUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.EmployeeQualificationRead:
    qualification = get_or_404(db, models.EmployeeQualification, qualification_id, "Qualification")
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.Document, changes.get("document_id"), "document_id")
    ensure_ref(db, models.QualificationType, changes.get("qualification_type_id"), "qualification_type_id")
    # Recompute the expiry from the catalogue when a new course date arrives
    # without an explicit one.
    if "issued_on" in changes and "valid_until" not in changes:
        merged = {
            "qualification_type_id": changes.get(
                "qualification_type_id", qualification.qualification_type_id
            ),
            "issued_on": changes["issued_on"],
            "title": qualification.title,
            "qualification_type": qualification.qualification_type,
        }
        derived = apply_catalogue_defaults(db, merged)
        if derived.get("valid_until"):
            changes["valid_until"] = derived["valid_until"]
    before = {field: getattr(qualification, field) for field in changes}
    for field, value in changes.items():
        setattr(qualification, field, value)
    audit(
        db,
        "employee_qualification",
        qualification_id,
        "updated",
        {"before": before, "after": changes},
        principal,
    )
    db.commit()
    db.refresh(qualification)
    return qualification_read(qualification)


@router.delete(
    "/api/employee-qualifications/{qualification_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_qualification(
    qualification_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    qualification = get_or_404(db, models.EmployeeQualification, qualification_id, "Qualification")
    audit(db, "employee_qualification", qualification_id, "deleted", snapshot(qualification), principal)
    db.delete(qualification)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------


@router.post("/api/employee-profiles", response_model=schemas.EmployeeProfileRead)
def upsert_employee_profile(
    payload: schemas.EmployeeProfileCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.EmployeeProfileRead:
    ensure_ref(db, models.Employee, payload.employee_id, "employee_id")
    profile = db.scalar(
        select(models.EmployeeProfile).where(models.EmployeeProfile.employee_id == payload.employee_id)
    )
    changes = payload.model_dump()
    if profile:
        for field, value in changes.items():
            setattr(profile, field, value)
        action = "updated"
    else:
        profile = models.EmployeeProfile(**changes)
        db.add(profile)
        action = "created"
    db.flush()
    audit(db, "employee_profile", profile.id, action, payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(profile)
    return profile_read(profile)


@router.delete("/api/employee-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee_profile(
    profile_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    profile = get_or_404(db, models.EmployeeProfile, profile_id, "Profile")
    audit(db, "employee_profile", profile_id, "deleted", snapshot(profile), principal)
    db.delete(profile)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Reviews and documents
# --------------------------------------------------------------------------

crud.register(
    router,
    "/api/employee-reviews",
    crud.Crud(
        model=models.EmployeeReview,
        create_schema=schemas.EmployeeReviewCreate,
        update_schema=schemas.EmployeeReviewUpdate,
        read_schema=schemas.EmployeeReviewRead,
        entity_type="employee_review",
        label="Employee review",
        read_permission=permissions.PERSONNEL_READ,
        write_permission=permissions.PERSONNEL_WRITE,
        references={"employee_id": models.Employee},
        filters={"employee_id": "employee_id"},
        order_by="review_date",
        order_desc=True,
    ),
)


@router.get("/api/documents", response_model=list[schemas.DocumentRead], dependencies=[read_dependency])
def list_documents(
    limit: Annotated[int, Query(ge=1, le=500)] = 200, db: Session = Depends(get_db)
) -> list[models.Document]:
    return db.scalars(select(models.Document).order_by(models.Document.created_at.desc()).limit(limit)).all()


@router.post(
    "/api/documents", response_model=schemas.DocumentRead, status_code=status.HTTP_201_CREATED
)
def upload_document(
    principal: WriteDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> models.Document:
    stored = storage.store_upload(file, category="documents")
    document = models.Document(
        title=(title or stored.file_name)[:180],
        file_name=stored.file_name,
        storage_path=stored.storage_path,
        mime_type=stored.mime_type,
        file_size_bytes=stored.size_bytes,
        uploaded_by=principal.user_id,
    )
    db.add(document)
    db.flush()
    audit(
        db,
        "document",
        document.id,
        "created",
        {"file_name": stored.file_name, "size_bytes": stored.size_bytes},
        principal,
    )
    db.commit()
    db.refresh(document)
    return document


@router.get("/api/documents/{document_id}/download", dependencies=[read_dependency])
def download_document(document_id: str, db: Session = Depends(get_db)) -> FileResponse:
    document = get_or_404(db, models.Document, document_id, "Document")
    return FileResponse(
        storage.resolve(document.storage_path),
        media_type=document.mime_type or "application/octet-stream",
        filename=document.file_name,
    )


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    document = get_or_404(db, models.Document, document_id, "Document")
    guard_children(
        db, [(models.EmployeeQualification, "document_id", "qualification(s)")], document_id
    )
    audit(db, "document", document_id, "deleted", snapshot(document), principal)
    storage.delete(document.storage_path)
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
