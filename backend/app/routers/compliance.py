from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, permissions, schemas, storage
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, branch_filter, ensure_branch_access, ensure_ref, get_or_404, snapshot
from ..jobs import schedule_next_cycle
from ..serializers import action_read, load_record, record_read

router = APIRouter(tags=["compliance"])

WriteDep = Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.COMPLIANCE_READ))]
read_dependency = Depends(requires(permissions.COMPLIANCE_READ))


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@router.get("/api/compliance-records", response_model=list[schemas.ComplianceRecordRead])
def list_compliance_records(
    principal: ReadDep,
    branch_id: str | None = None,
    owner_user_id: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    priority: str | None = None,
    category: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> list[schemas.ComplianceRecordRead]:
    query = select(models.ComplianceRecord).options(
        selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions)
    )
    query = branch_filter(query, models.ComplianceRecord.branch_id, principal, branch_id)
    if owner_user_id:
        query = query.where(models.ComplianceRecord.owner_user_id == owner_user_id)
    if status_filter:
        query = query.where(models.ComplianceRecord.status == status_filter)
    if priority:
        query = query.where(models.ComplianceRecord.priority == priority)
    if category:
        query = query.where(models.ComplianceRecord.category == category)
    records = db.scalars(
        query.order_by(models.ComplianceRecord.due_date.asc()).limit(limit).offset(offset)
    ).all()
    return [record_read(record) for record in records]


@router.post("/api/compliance-records", response_model=schemas.ComplianceRecordRead)
def create_compliance_record(
    payload: schemas.ComplianceRecordCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.ComplianceRecordRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.User, payload.owner_user_id, "owner_user_id")
    ensure_ref(db, models.User, payload.approved_by, "approved_by")
    record = models.ComplianceRecord(**payload.model_dump())
    schedule_next_cycle(record)
    db.add(record)
    db.flush()
    audit(db, "compliance_record", record.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(record)
    return record_read(record)


@router.get(
    "/api/compliance-records/{record_id}",
    response_model=schemas.ComplianceRecordRead,
    dependencies=[read_dependency],
)
def get_compliance_record(record_id: str, db: Session = Depends(get_db)) -> schemas.ComplianceRecordRead:
    return record_read(load_record(db, record_id))


@router.patch("/api/compliance-records/{record_id}", response_model=schemas.ComplianceRecordRead)
def update_compliance_record(
    record_id: str,
    payload: schemas.ComplianceRecordUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.ComplianceRecordRead:
    record = load_record(db, record_id)
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.User, changes.get("owner_user_id"), "owner_user_id")
    ensure_ref(db, models.User, changes.get("approved_by"), "approved_by")

    before = {field: getattr(record, field) for field in changes}
    previous_status = record.status
    for field, value in changes.items():
        setattr(record, field, value)

    # Completing a recurring control schedules the next cycle; the worker
    # reopens the record once that date arrives.
    if record.status != previous_status and "next_due_at" not in changes:
        schedule_next_cycle(record)

    audit(
        db,
        "compliance_record",
        record.id,
        "updated",
        {"before": before, "after": payload.model_dump(mode="json", exclude_unset=True)},
        principal,
    )
    db.commit()
    return record_read(load_record(db, record_id))


@router.delete("/api/compliance-records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compliance_record(
    record_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    record = load_record(db, record_id)
    payload = snapshot(record)
    payload["evidence"] = [snapshot(item) for item in record.evidence]
    payload["actions"] = [snapshot(item) for item in record.actions]
    audit(db, "compliance_record", record_id, "deleted", payload, principal)

    # Evidence and actions belong to the record and go with it; the audit entry
    # above keeps the full contents.
    for item in record.evidence:
        storage.delete(item.storage_path)
        db.delete(item)
    for action in record.actions:
        db.delete(action)
    db.delete(record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------


@router.post(
    "/api/compliance-records/{record_id}/evidence",
    response_model=schemas.ComplianceEvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def add_evidence(
    record_id: str,
    principal: WriteDep,
    file: Annotated[UploadFile, File(description="The evidence document")],
    evidence_type: Annotated[str, Form()] = "other",
    description: Annotated[str | None, Form()] = None,
    valid_from: Annotated[str | None, Form()] = None,
    valid_until: Annotated[str | None, Form()] = None,
    linked_employee_id: Annotated[str | None, Form()] = None,
    linked_project_id: Annotated[str | None, Form()] = None,
    linked_equipment_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> models.ComplianceEvidence:
    """Stores an uploaded document as evidence.

    The storage path is generated server-side; it was previously supplied by the
    client and pointed at files that never existed.
    """
    if not db.get(models.ComplianceRecord, record_id):
        raise HTTPException(status_code=404, detail="Compliance record not found")

    metadata = schemas.ComplianceEvidenceCreate(
        evidence_type=evidence_type,
        description=description,
        valid_from=valid_from or None,
        valid_until=valid_until or None,
        linked_employee_id=linked_employee_id or None,
        linked_project_id=linked_project_id or None,
        linked_equipment_id=linked_equipment_id or None,
    )
    ensure_ref(db, models.Employee, metadata.linked_employee_id, "linked_employee_id")
    ensure_ref(db, models.Project, metadata.linked_project_id, "linked_project_id")

    stored = storage.store_upload(file, category="evidence")
    evidence = models.ComplianceEvidence(
        compliance_record_id=record_id,
        file_name=stored.file_name,
        storage_path=stored.storage_path,
        mime_type=stored.mime_type,
        file_size_bytes=stored.size_bytes,
        uploaded_by=principal.user_id,
        **metadata.model_dump(),
    )
    db.add(evidence)
    db.flush()
    audit(
        db,
        "compliance_record",
        record_id,
        "evidence_added",
        {"evidence_id": evidence.id, "file_name": stored.file_name, "size_bytes": stored.size_bytes},
        principal,
    )
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/api/evidence/{evidence_id}/download", dependencies=[read_dependency])
def download_evidence(evidence_id: str, db: Session = Depends(get_db)) -> FileResponse:
    evidence = get_or_404(db, models.ComplianceEvidence, evidence_id, "Evidence")
    path = storage.resolve(evidence.storage_path)
    return FileResponse(
        path,
        media_type=evidence.mime_type or "application/octet-stream",
        filename=evidence.file_name,
    )


@router.delete("/api/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(evidence_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    evidence = get_or_404(db, models.ComplianceEvidence, evidence_id, "Evidence")
    audit(db, "compliance_record", evidence.compliance_record_id, "evidence_deleted", snapshot(evidence), principal)
    storage.delete(evidence.storage_path)
    db.delete(evidence)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------


@router.post(
    "/api/compliance-records/{record_id}/actions", response_model=schemas.ComplianceActionRead
)
def add_action(
    record_id: str,
    payload: schemas.ComplianceActionCreate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.ComplianceActionRead:
    if not db.get(models.ComplianceRecord, record_id):
        raise HTTPException(status_code=404, detail="Compliance record not found")
    ensure_ref(db, models.User, payload.owner_user_id, "owner_user_id")
    action = models.ComplianceAction(compliance_record_id=record_id, **payload.model_dump())
    db.add(action)
    db.flush()
    audit(db, "compliance_record", record_id, "action_added", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(action)
    return action_read(action)


@router.get(
    "/api/actions", response_model=list[schemas.ComplianceActionRead], dependencies=[read_dependency]
)
def list_actions(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    owner_user_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[schemas.ComplianceActionRead]:
    query = select(models.ComplianceAction)
    if status_filter:
        query = query.where(models.ComplianceAction.status == status_filter)
    if owner_user_id:
        query = query.where(models.ComplianceAction.owner_user_id == owner_user_id)
    actions = db.scalars(query.order_by(models.ComplianceAction.due_date.asc()).limit(limit)).all()
    return [action_read(action) for action in actions]


@router.patch("/api/actions/{action_id}", response_model=schemas.ComplianceActionRead)
def update_action(
    action_id: str,
    payload: schemas.ComplianceActionUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.ComplianceActionRead:
    action = get_or_404(db, models.ComplianceAction, action_id, "Action")
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.User, changes.get("owner_user_id"), "owner_user_id")
    for field, value in changes.items():
        setattr(action, field, value)
    if changes.get("status") == "done" and action.completed_at is None:
        action.completed_at = datetime.now(timezone.utc)
    audit(
        db,
        "compliance_action",
        action.id,
        "updated",
        payload.model_dump(mode="json", exclude_unset=True),
        principal,
    )
    db.commit()
    db.refresh(action)
    return action_read(action)


@router.delete("/api/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action(action_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    action = get_or_404(db, models.ComplianceAction, action_id, "Action")
    audit(db, "compliance_action", action_id, "deleted", snapshot(action), principal)
    db.delete(action)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
