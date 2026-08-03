from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import models, schemas
from .database import SessionLocal, get_db, init_db
from .domain import due_state, is_overdue, within_days
from .hermes import HermesClient
from .seed import seed_base_data

app = FastAPI(title="Remscheid Ops Platform API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3500", "http://127.0.0.1:3500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as db:
        seed_base_data(db)


def require_write_role(x_user_role: Annotated[str | None, Header()] = None) -> None:
    if x_user_role in {None, "", "read-only"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write role required")


def audit(db: Session, entity_type: str, entity_id: str, action: str, changes: dict, actor: str | None = None) -> None:
    db.add(
        models.AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor,
            changes=changes,
        )
    )


def action_read(action: models.ComplianceAction) -> schemas.ComplianceActionRead:
    state = due_state(action.status, action.due_date)
    return schemas.ComplianceActionRead(
        id=action.id,
        compliance_record_id=action.compliance_record_id,
        title=action.title,
        description=action.description,
        owner_user_id=action.owner_user_id,
        due_date=action.due_date,
        priority=action.priority,
        status=action.status,
        escalation_level=action.escalation_level,
        completed_at=action.completed_at,
        due_state=state,
        overdue=is_overdue(action.status, action.due_date),
    )


def qualification_read(qualification: models.EmployeeQualification) -> schemas.EmployeeQualificationRead:
    state = due_state("open", qualification.valid_until)
    return schemas.EmployeeQualificationRead(
        id=qualification.id,
        employee_id=qualification.employee_id,
        title=qualification.title,
        qualification_type=qualification.qualification_type,
        valid_until=qualification.valid_until,
        document_id=qualification.document_id,
        reminder_days=qualification.reminder_days,
        due_state=state,
        overdue=is_overdue("open", qualification.valid_until),
    )


def record_read(record: models.ComplianceRecord) -> schemas.ComplianceRecordRead:
    return schemas.ComplianceRecordRead(
        id=record.id,
        title=record.title,
        category=record.category,
        branch_id=record.branch_id,
        scope_type=record.scope_type,
        scope_id=record.scope_id,
        status=record.status,
        priority=record.priority,
        owner_user_id=record.owner_user_id,
        legal_basis=record.legal_basis,
        control_type=record.control_type,
        due_date=record.due_date,
        review_date=record.review_date,
        description=record.description,
        risk_if_missing=record.risk_if_missing,
        evidence_summary=record.evidence_summary,
        recurrence=record.recurrence,
        last_completed_at=record.last_completed_at,
        next_due_at=record.next_due_at,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        tags=record.tags,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
        due_state=due_state(record.status, record.due_date),
        overdue=is_overdue(record.status, record.due_date),
        evidence=[schemas.ComplianceEvidenceRead.model_validate(item) for item in record.evidence],
        actions=[action_read(action) for action in record.actions],
    )
def profile_read(profile: models.EmployeeProfile | None) -> schemas.EmployeeProfileRead | None:
    return schemas.EmployeeProfileRead.model_validate(profile) if profile else None


def vehicle_read(vehicle: models.Vehicle) -> schemas.VehicleRead:
    return schemas.VehicleRead.model_validate(vehicle)


def reminder_item(source_type: str, source_id: str, title: str, due: date | None, owner_hint: str | None = None) -> schemas.ReminderRead | None:
    if not due:
        return None
    state = due_state("open", due)
    if state == "green" and not within_days(due, 60):
        return None
    return schemas.ReminderRead(source_type=source_type, source_id=source_id, title=title, due_date=due, state=state, owner_hint=owner_hint)


def build_reminders(db: Session, branch_id: str | None = None) -> list[schemas.ReminderRead]:
    reminders: list[schemas.ReminderRead] = []
    employee_query = select(models.Employee).options(selectinload(models.Employee.profile))
    vehicle_query = select(models.Vehicle)
    if branch_id:
        employee_query = employee_query.where(models.Employee.branch_id == branch_id)
        vehicle_query = vehicle_query.where(models.Vehicle.branch_id == branch_id)
    for employee in db.scalars(employee_query).all():
        profile = employee.profile
        if not profile:
            continue
        candidates = [
            ("Arbeitsvertrag befristet bis", profile.contract_end),
            ("Probezeit endet", profile.probation_until),
            ("Aufenthaltserlaubnis/Arbeitserlaubnis pruefen", profile.residence_permit_valid_until),
            ("Fuehrerscheinkontrolle", profile.driver_license_next_check),
            ("Erste-Hilfe-Kurs auffrischen", profile.first_aid_valid_until),
            ("IPAF-Schulung auffrischen", profile.ipaf_valid_until),
            ("Allgemeine Unterweisung erneuern", profile.general_instruction_next),
            ("Arbeitsmedizinische Vorsorge pruefen", profile.occupational_health_next),
        ]
        for title, due in candidates:
            item = reminder_item("employee", employee.id, f"{employee.full_name}: {title}", due, employee.full_name)
            if item:
                reminders.append(item)
    for vehicle in db.scalars(vehicle_query).all():
        label = vehicle.license_plate
        candidates = [
            ("HU faellig", vehicle.hu_due_date),
            ("UVV/Fahrzeugpruefung faellig", vehicle.uvv_next_check),
            ("Service/Wartung faellig", vehicle.service_due_date),
            ("Reifenwechsel terminieren", vehicle.tire_change_due_date),
            ("Versicherung pruefen", vehicle.insurance_valid_until),
        ]
        for title, due in candidates:
            item = reminder_item("vehicle", vehicle.id, f"{label}: {title}", due, label)
            if item:
                reminders.append(item)
    return sorted(reminders, key=lambda item: item.due_date)

def employee_read(employee: models.Employee) -> schemas.EmployeeRead:
    return schemas.EmployeeRead(
        id=employee.id,
        branch_id=employee.branch_id,
        full_name=employee.full_name,
        role=employee.role,
        team=employee.team,
        start_date=employee.start_date,
        first_aider=employee.first_aider,
        skills=employee.skills,
        notes=employee.notes,
        qualifications=[qualification_read(item) for item in employee.qualifications],
        profile=profile_read(employee.profile),
    )


def assessment_read(assessment: models.BranchAssessment) -> schemas.BranchAssessmentRead:
    return schemas.BranchAssessmentRead.model_validate(assessment)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/bootstrap")
def bootstrap(db: Session = Depends(get_db)) -> dict:
    branches = db.scalars(select(models.Branch).order_by(models.Branch.name.asc())).all()
    users = db.scalars(select(models.User).order_by(models.User.display_name.asc())).all()
    return {
        "branches": [schemas.BranchRead.model_validate(branch).model_dump() for branch in branches],
        "users": [schemas.UserRead.model_validate(user).model_dump() for user in users],
    }


@app.get("/api/cockpit", response_model=schemas.CockpitResponse)
def cockpit(db: Session = Depends(get_db)) -> schemas.CockpitResponse:
    records = db.scalars(
        select(models.ComplianceRecord).options(
            selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions)
        )
    ).all()
    actions = db.scalars(select(models.ComplianceAction)).all()
    qualifications = db.scalars(select(models.EmployeeQualification)).all()
    incidents = db.scalars(select(models.Incident).order_by(models.Incident.occurred_at.desc()).limit(5)).all()
    reminders = build_reminders(db)
    employee_due_count = len([item for item in reminders if item.source_type == "employee"])
    vehicle_due_count = len([item for item in reminders if item.source_type == "vehicle"])
    pipeline_value = db.scalar(select(func.coalesce(func.sum(models.Opportunity.expected_volume), 0))) or 0
    service_due_count = db.scalar(
        select(func.count(models.ServiceContract.id)).where(models.ServiceContract.next_maintenance_at <= date.today())
    )

    overdue_records = [record for record in records if is_overdue(record.status, record.due_date)]
    due_soon = [record for record in records if within_days(record.due_date, 30) and not is_overdue(record.status, record.due_date)]
    open_actions = [action for action in actions if action.status not in {"done", "cancelled"}]
    expiring = [qualification for qualification in qualifications if within_days(qualification.valid_until, 30)]

    return schemas.CockpitResponse(
        metrics=[
            schemas.CockpitMetric(label="Overdue compliance", value=len(overdue_records), state="red" if overdue_records else "green"),
            schemas.CockpitMetric(label="Due in 30 days", value=len(due_soon), state="yellow" if due_soon else "green"),
            schemas.CockpitMetric(label="Open actions", value=len(open_actions), state="red" if open_actions else "green"),
            schemas.CockpitMetric(label="Expiring qualifications", value=len(expiring), state="yellow" if expiring else "green"),
            schemas.CockpitMetric(label="Pipeline EUR", value=float(pipeline_value), state="green"),
            schemas.CockpitMetric(label="Service due", value=int(service_due_count or 0), state="yellow" if service_due_count else "green"),
            schemas.CockpitMetric(label="Employee reminders", value=employee_due_count, state="yellow" if employee_due_count else "green"),
            schemas.CockpitMetric(label="Vehicle reminders", value=vehicle_due_count, state="yellow" if vehicle_due_count else "green"),
        ],
        overdue_compliance=[record_read(record) for record in overdue_records],
        due_soon_compliance=[record_read(record) for record in due_soon],
        open_actions=[action_read(action) for action in open_actions],
        expiring_qualifications=[qualification_read(qualification) for qualification in expiring],
        incidents=incidents,
        reminders=reminders,
        pipeline_value=float(pipeline_value),
        service_due_count=int(service_due_count or 0),
        vehicle_due_count=vehicle_due_count,
        employee_due_count=employee_due_count,
    )

@app.get("/api/branch-assessments", response_model=list[schemas.BranchAssessmentRead])
def list_branch_assessments(branch_id: str | None = None, db: Session = Depends(get_db)) -> list[schemas.BranchAssessmentRead]:
    query = select(models.BranchAssessment).order_by(models.BranchAssessment.assessment_date.desc())
    if branch_id:
        query = query.where(models.BranchAssessment.branch_id == branch_id)
    return [assessment_read(item) for item in db.scalars(query).all()]


@app.post(
    "/api/branch-assessments",
    response_model=schemas.BranchAssessmentRead,
    dependencies=[Depends(require_write_role)],
)
def create_branch_assessment(
    payload: schemas.BranchAssessmentCreate, db: Session = Depends(get_db)
) -> schemas.BranchAssessmentRead:
    if not db.get(models.Branch, payload.branch_id):
        raise HTTPException(status_code=404, detail="Branch not found")
    assessment = models.BranchAssessment(**payload.model_dump())
    db.add(assessment)
    db.flush()
    audit(db, "branch_assessment", assessment.id, "created", payload.model_dump(mode="json"), payload.created_by)
    db.commit()
    db.refresh(assessment)
    return assessment_read(assessment)


@app.get("/api/hermes/context/branches/{branch_id}", response_model=schemas.HermesBranchContext)
def hermes_branch_context(branch_id: str, db: Session = Depends(get_db)) -> schemas.HermesBranchContext:
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    latest_assessment = db.scalar(
        select(models.BranchAssessment)
        .where(models.BranchAssessment.branch_id == branch_id)
        .order_by(models.BranchAssessment.assessment_date.desc())
        .limit(1)
    )
    records = db.scalars(
        select(models.ComplianceRecord)
        .where(models.ComplianceRecord.branch_id == branch_id)
        .options(selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions))
        .order_by(models.ComplianceRecord.due_date.asc())
    ).all()
    employees = db.scalars(
        select(models.Employee)
        .where(models.Employee.branch_id == branch_id)
        .options(selectinload(models.Employee.qualifications), selectinload(models.Employee.profile))
    ).all()
    open_actions = db.scalars(
        select(models.ComplianceAction)
        .join(models.ComplianceRecord)
        .where(models.ComplianceRecord.branch_id == branch_id)
        .where(models.ComplianceAction.status.notin_(["done", "cancelled"]))
        .order_by(models.ComplianceAction.due_date.asc())
    ).all()
    incidents = db.scalars(
        select(models.Incident)
        .where(models.Incident.branch_id == branch_id)
        .order_by(models.Incident.occurred_at.desc())
        .limit(20)
    ).all()
    vehicles = db.scalars(select(models.Vehicle).where(models.Vehicle.branch_id == branch_id).order_by(models.Vehicle.license_plate.asc())).all()
    return schemas.HermesBranchContext(
        branch=schemas.BranchRead.model_validate(branch),
        latest_assessment=assessment_read(latest_assessment) if latest_assessment else None,
        compliance_records=[record_read(record) for record in records],
        employees=[employee_read(employee) for employee in employees],
        vehicles=[vehicle_read(vehicle) for vehicle in vehicles],
        reminders=build_reminders(db, branch_id),
        open_actions=[action_read(action) for action in open_actions],
        incidents=incidents,
    )

@app.get("/api/compliance-records", response_model=list[schemas.ComplianceRecordRead])
def list_compliance_records(
    branch_id: str | None = None,
    owner_user_id: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    priority: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[schemas.ComplianceRecordRead]:
    query = select(models.ComplianceRecord).options(
        selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions)
    )
    if branch_id:
        query = query.where(models.ComplianceRecord.branch_id == branch_id)
    if owner_user_id:
        query = query.where(models.ComplianceRecord.owner_user_id == owner_user_id)
    if status_filter:
        query = query.where(models.ComplianceRecord.status == status_filter)
    if priority:
        query = query.where(models.ComplianceRecord.priority == priority)
    if category:
        query = query.where(models.ComplianceRecord.category == category)
    records = db.scalars(query.order_by(models.ComplianceRecord.due_date.asc())).all()
    return [record_read(record) for record in records]


@app.post(
    "/api/compliance-records",
    response_model=schemas.ComplianceRecordRead,
    dependencies=[Depends(require_write_role)],
)
def create_compliance_record(payload: schemas.ComplianceRecordCreate, db: Session = Depends(get_db)) -> schemas.ComplianceRecordRead:
    record = models.ComplianceRecord(**payload.model_dump())
    db.add(record)
    db.flush()
    audit(db, "compliance_record", record.id, "created", payload.model_dump(mode="json"), payload.owner_user_id)
    db.commit()
    db.refresh(record)
    return record_read(record)


@app.get("/api/compliance-records/{record_id}", response_model=schemas.ComplianceRecordRead)
def get_compliance_record(record_id: str, db: Session = Depends(get_db)) -> schemas.ComplianceRecordRead:
    record = db.scalar(
        select(models.ComplianceRecord)
        .where(models.ComplianceRecord.id == record_id)
        .options(selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions))
    )
    if not record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
    return record_read(record)


@app.patch(
    "/api/compliance-records/{record_id}",
    response_model=schemas.ComplianceRecordRead,
    dependencies=[Depends(require_write_role)],
)
def update_compliance_record(
    record_id: str, payload: schemas.ComplianceRecordUpdate, db: Session = Depends(get_db)
) -> schemas.ComplianceRecordRead:
    record = db.scalar(select(models.ComplianceRecord).where(models.ComplianceRecord.id == record_id))
    if not record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(record, field) for field in changes}
    for field, value in changes.items():
        setattr(record, field, value)
    audit(db, "compliance_record", record.id, "updated", {"before": before, "after": changes}, record.owner_user_id)
    db.commit()
    db.refresh(record)
    return get_compliance_record(record.id, db)


@app.post(
    "/api/compliance-records/{record_id}/evidence",
    response_model=schemas.ComplianceEvidenceRead,
    dependencies=[Depends(require_write_role)],
)
def add_evidence(
    record_id: str, payload: schemas.ComplianceEvidenceCreate, db: Session = Depends(get_db)
) -> schemas.ComplianceEvidenceRead:
    if not db.get(models.ComplianceRecord, record_id):
        raise HTTPException(status_code=404, detail="Compliance record not found")
    evidence = models.ComplianceEvidence(compliance_record_id=record_id, **payload.model_dump())
    db.add(evidence)
    db.flush()
    audit(db, "compliance_record", record_id, "evidence_added", payload.model_dump(mode="json"), payload.uploaded_by)
    db.commit()
    db.refresh(evidence)
    return evidence


@app.post(
    "/api/compliance-records/{record_id}/actions",
    response_model=schemas.ComplianceActionRead,
    dependencies=[Depends(require_write_role)],
)
def add_action(record_id: str, payload: schemas.ComplianceActionCreate, db: Session = Depends(get_db)) -> schemas.ComplianceActionRead:
    if not db.get(models.ComplianceRecord, record_id):
        raise HTTPException(status_code=404, detail="Compliance record not found")
    action = models.ComplianceAction(compliance_record_id=record_id, **payload.model_dump())
    db.add(action)
    db.flush()
    audit(db, "compliance_record", record_id, "action_added", payload.model_dump(mode="json"), payload.owner_user_id)
    db.commit()
    db.refresh(action)
    return action_read(action)


@app.get("/api/actions", response_model=list[schemas.ComplianceActionRead])
def list_actions(db: Session = Depends(get_db)) -> list[schemas.ComplianceActionRead]:
    actions = db.scalars(select(models.ComplianceAction).order_by(models.ComplianceAction.due_date.asc())).all()
    return [action_read(action) for action in actions]


@app.patch("/api/actions/{action_id}", response_model=schemas.ComplianceActionRead, dependencies=[Depends(require_write_role)])
def update_action(action_id: str, payload: schemas.ComplianceActionUpdate, db: Session = Depends(get_db)) -> schemas.ComplianceActionRead:
    action = db.get(models.ComplianceAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(action, field, value)
    if changes.get("status") == "done" and action.completed_at is None:
        action.completed_at = datetime.now(timezone.utc)
    audit(db, "compliance_action", action.id, "updated", changes, action.owner_user_id)
    db.commit()
    db.refresh(action)
    return action_read(action)


@app.get("/api/employees", response_model=list[schemas.EmployeeRead])
def list_employees(db: Session = Depends(get_db)) -> list[schemas.EmployeeRead]:
    employees = db.scalars(select(models.Employee).options(selectinload(models.Employee.qualifications), selectinload(models.Employee.profile))).all()
    return [employee_read(employee) for employee in employees]



@app.post("/api/employees", response_model=schemas.EmployeeRead, dependencies=[Depends(require_write_role)])
def create_employee(payload: schemas.EmployeeCreate, db: Session = Depends(get_db)) -> schemas.EmployeeRead:
    employee = models.Employee(**payload.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return schemas.EmployeeRead(
        id=employee.id,
        branch_id=employee.branch_id,
        full_name=employee.full_name,
        role=employee.role,
        team=employee.team,
        start_date=employee.start_date,
        first_aider=employee.first_aider,
        skills=employee.skills,
        notes=employee.notes,
        qualifications=[],
    )


@app.post(
    "/api/employee-qualifications",
    response_model=schemas.EmployeeQualificationRead,
    dependencies=[Depends(require_write_role)],
)
def create_qualification(
    payload: schemas.EmployeeQualificationCreate, db: Session = Depends(get_db)
) -> schemas.EmployeeQualificationRead:
    qualification = models.EmployeeQualification(**payload.model_dump())
    db.add(qualification)
    db.commit()
    db.refresh(qualification)
    return qualification_read(qualification)

@app.post(
    "/api/employee-profiles",
    response_model=schemas.EmployeeProfileRead,
    dependencies=[Depends(require_write_role)],
)
def upsert_employee_profile(
    payload: schemas.EmployeeProfileCreate, db: Session = Depends(get_db)
) -> schemas.EmployeeProfileRead:
    if not db.get(models.Employee, payload.employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
    profile = db.scalar(select(models.EmployeeProfile).where(models.EmployeeProfile.employee_id == payload.employee_id))
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
    audit(db, "employee_profile", profile.id, action, payload.model_dump(mode="json"), None)
    db.commit()
    db.refresh(profile)
    return profile_read(profile)


@app.get("/api/vehicles", response_model=list[schemas.VehicleRead])
def list_vehicles(branch_id: str | None = None, db: Session = Depends(get_db)) -> list[schemas.VehicleRead]:
    query = select(models.Vehicle).order_by(models.Vehicle.license_plate.asc())
    if branch_id:
        query = query.where(models.Vehicle.branch_id == branch_id)
    return [vehicle_read(vehicle) for vehicle in db.scalars(query).all()]


@app.post("/api/vehicles", response_model=schemas.VehicleRead, dependencies=[Depends(require_write_role)])
def create_vehicle(payload: schemas.VehicleCreate, db: Session = Depends(get_db)) -> schemas.VehicleRead:
    if not db.get(models.Branch, payload.branch_id):
        raise HTTPException(status_code=404, detail="Branch not found")
    vehicle = models.Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.flush()
    audit(db, "vehicle", vehicle.id, "created", payload.model_dump(mode="json"), None)
    db.commit()
    db.refresh(vehicle)
    return vehicle_read(vehicle)


@app.get("/api/reminders", response_model=list[schemas.ReminderRead])
def list_reminders(branch_id: str | None = None, db: Session = Depends(get_db)) -> list[schemas.ReminderRead]:
    return build_reminders(db, branch_id)

@app.get("/api/incidents", response_model=list[schemas.IncidentRead])
def list_incidents(db: Session = Depends(get_db)) -> list[schemas.IncidentRead]:
    return db.scalars(select(models.Incident).order_by(models.Incident.occurred_at.desc())).all()


@app.post("/api/incidents", response_model=schemas.IncidentRead, dependencies=[Depends(require_write_role)])
def create_incident(payload: schemas.IncidentCreate, db: Session = Depends(get_db)) -> schemas.IncidentRead:
    incident = models.Incident(**payload.model_dump())
    db.add(incident)
    db.flush()
    audit(db, "incident", incident.id, "created", payload.model_dump(mode="json"), incident.owner_user_id)
    db.commit()
    db.refresh(incident)
    return incident


@app.post("/api/agent/compliance-review", response_model=schemas.AgentReviewResponse)
async def agent_compliance_review(payload: schemas.AgentComplianceReviewRequest, db: Session = Depends(get_db)) -> schemas.AgentReviewResponse:
    record = db.scalar(
        select(models.ComplianceRecord)
        .where(models.ComplianceRecord.id == payload.compliance_record_id)
        .options(selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions))
    )
    if not record:
        raise HTTPException(status_code=404, detail="Compliance record not found")

    request_payload = {
        "branch": record.branch.name if record.branch else record.branch_id,
        "record_type": record.category,
        "title": record.title,
        "status": record.status,
        "priority": record.priority,
        "due_date": record.due_date.isoformat(),
        "legal_basis": record.legal_basis,
        "evidence_count": len(record.evidence),
        "open_actions": len([action for action in record.actions if action.status not in {"done", "cancelled"}]),
        "notes": payload.prompt or record.notes or record.evidence_summary,
    }
    run = models.AgentRun(
        use_case="compliance_review",
        source_entity_type="compliance_record",
        source_entity_id=record.id,
        request_payload=request_payload,
        status="running",
        created_by=record.owner_user_id,
    )
    db.add(run)
    db.commit()
    try:
        response_payload = await HermesClient().compliance_review(request_payload)
        run.response_payload = response_payload
        run.status = "completed"
    except Exception as exc:  # Hermes failures must be visible but not crash the app state.
        run.response_payload = {"error": str(exc)}
        run.status = "failed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    return schemas.AgentReviewResponse(id=run.id, status=run.status, response_payload=run.response_payload)







