import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import models, permissions, schemas
from .auth import CurrentPrincipal, Principal, requires
from .config import settings
from .database import SessionLocal, get_db, init_db
from .domain import DEFAULT_REMINDER_WINDOW_DAYS, DUE_SOON_DAYS, due_state, is_overdue, needs_attention, within_days
from .hermes import HermesClient
from .seed import seed_base_data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_base_data(db)
    logger.info(
        "Remscheid Ops API started (env=%s, auth_mode=%s, cors_origins=%s)",
        settings.app_env,
        settings.auth_mode,
        settings.cors_origins,
    )
    if settings.auth_mode == "dev":
        logger.warning(
            "AUTH_MODE=dev: callers authenticate with the X-User-Id header. "
            "Do not expose this deployment outside a trusted network."
        )
    yield


app = FastAPI(title="Remscheid Ops Platform API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    changes: dict,
    principal: Principal | None = None,
) -> None:
    db.add(
        models.AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=principal.user_id if principal else None,
            changes=changes,
        )
    )


def ensure_ref(db: Session, model: type, value: str | None, label: str) -> None:
    """Rejects references to rows that do not exist.

    Without this, SQLite silently stores dangling ids while PostgreSQL raises an
    IntegrityError, so the same request behaves differently per environment.
    """
    if value is None:
        return
    if db.get(model, value) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label} '{value}' does not exist"
        )


def action_read(action: models.ComplianceAction) -> schemas.ComplianceActionRead:
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
        due_state=due_state(action.status, action.due_date),
        overdue=is_overdue(action.status, action.due_date),
    )


def qualification_read(qualification: models.EmployeeQualification) -> schemas.EmployeeQualificationRead:
    return schemas.EmployeeQualificationRead(
        id=qualification.id,
        employee_id=qualification.employee_id,
        title=qualification.title,
        qualification_type=qualification.qualification_type,
        valid_until=qualification.valid_until,
        document_id=qualification.document_id,
        reminder_days=qualification.reminder_days,
        due_state=due_state("open", qualification.valid_until),
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


def load_record(db: Session, record_id: str) -> models.ComplianceRecord:
    record = db.scalar(
        select(models.ComplianceRecord)
        .where(models.ComplianceRecord.id == record_id)
        .options(selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions))
    )
    if not record:
        raise HTTPException(status_code=404, detail="Compliance record not found")
    return record


def reminder_item(
    source_type: str,
    source_id: str,
    title: str,
    due: date | None,
    owner_hint: str | None = None,
    window_days: int = DEFAULT_REMINDER_WINDOW_DAYS,
) -> schemas.ReminderRead | None:
    if not needs_attention(due, window_days):
        return None
    return schemas.ReminderRead(
        source_type=source_type,
        source_id=source_id,
        title=title,
        due_date=due,
        state=due_state("open", due),
        owner_hint=owner_hint,
    )


def build_reminders(
    db: Session,
    branch_id: str | None = None,
    *,
    include_personnel: bool = True,
    include_fleet: bool = True,
) -> list[schemas.ReminderRead]:
    """Collects upcoming and overdue dates.

    Personnel and fleet reminders are gated separately because the personnel
    entries carry names, permit and occupational-health dates.
    """
    reminders: list[schemas.ReminderRead] = []

    if include_personnel:
        employee_query = select(models.Employee).options(
            selectinload(models.Employee.profile), selectinload(models.Employee.qualifications)
        )
        if branch_id:
            employee_query = employee_query.where(models.Employee.branch_id == branch_id)
        for employee in db.scalars(employee_query).all():
            profile = employee.profile
            if profile:
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
                    item = reminder_item(
                        "employee", employee.id, f"{employee.full_name}: {title}", due, employee.full_name
                    )
                    if item:
                        reminders.append(item)
            for qualification in employee.qualifications:
                item = reminder_item(
                    "employee_qualification",
                    qualification.id,
                    f"{employee.full_name}: {qualification.title} laeuft ab",
                    qualification.valid_until,
                    employee.full_name,
                    window_days=qualification.reminder_days,
                )
                if item:
                    reminders.append(item)

    if include_fleet:
        vehicle_query = select(models.Vehicle)
        if branch_id:
            vehicle_query = vehicle_query.where(models.Vehicle.branch_id == branch_id)
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


# --------------------------------------------------------------------------
# Health and identity
# --------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    """Unauthenticated on purpose: used by the container healthcheck."""
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=schemas.PrincipalRead)
def whoami(principal: CurrentPrincipal) -> schemas.PrincipalRead:
    return schemas.PrincipalRead(
        user_id=principal.user_id,
        display_name=principal.display_name,
        email=principal.email,
        role_name=principal.role_name,
        permissions=sorted(principal.permissions),
        source=principal.source,
    )


@app.get("/api/auth/dev-users", response_model=list[schemas.DevUserRead])
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


@app.get("/api/bootstrap")
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


# --------------------------------------------------------------------------
# Cockpit
# --------------------------------------------------------------------------


@app.get("/api/cockpit", response_model=schemas.CockpitResponse)
def cockpit(
    principal: Annotated[Principal, Depends(requires(permissions.COMPLIANCE_READ))],
    db: Session = Depends(get_db),
) -> schemas.CockpitResponse:
    records = db.scalars(
        select(models.ComplianceRecord).options(
            selectinload(models.ComplianceRecord.evidence), selectinload(models.ComplianceRecord.actions)
        )
    ).all()
    actions = db.scalars(select(models.ComplianceAction)).all()
    incidents = db.scalars(select(models.Incident).order_by(models.Incident.occurred_at.desc()).limit(5)).all()

    may_read_personnel = principal.has(permissions.PERSONNEL_READ)
    may_read_fleet = principal.has(permissions.FLEET_READ)
    reminders = build_reminders(db, include_personnel=may_read_personnel, include_fleet=may_read_fleet)

    qualifications = (
        db.scalars(select(models.EmployeeQualification)).all() if may_read_personnel else []
    )
    employee_due_count = len([item for item in reminders if item.source_type.startswith("employee")])
    vehicle_due_count = len([item for item in reminders if item.source_type == "vehicle"])

    pipeline_value = db.scalar(select(func.coalesce(func.sum(models.Opportunity.expected_volume), 0))) or 0
    service_due_count = db.scalar(
        select(func.count(models.ServiceContract.id)).where(
            models.ServiceContract.next_maintenance_at <= date.today()
        )
    )

    overdue_records = [record for record in records if is_overdue(record.status, record.due_date)]
    due_soon = [
        record
        for record in records
        if within_days(record.due_date, DUE_SOON_DAYS) and not is_overdue(record.status, record.due_date)
    ]
    open_actions = [action for action in actions if action.status not in {"done", "cancelled"}]
    # Already-expired qualifications matter most, so they stay in this bucket
    # instead of being filtered out by a forward-looking window.
    expiring = [
        qualification
        for qualification in qualifications
        if needs_attention(qualification.valid_until, DUE_SOON_DAYS)
    ]
    overdue_qualifications = [
        qualification for qualification in expiring if is_overdue("open", qualification.valid_until)
    ]

    return schemas.CockpitResponse(
        metrics=[
            schemas.CockpitMetric(
                label="Overdue compliance", value=len(overdue_records), state="red" if overdue_records else "green"
            ),
            schemas.CockpitMetric(
                label="Due in 30 days", value=len(due_soon), state="yellow" if due_soon else "green"
            ),
            schemas.CockpitMetric(
                label="Open actions", value=len(open_actions), state="red" if open_actions else "green"
            ),
            schemas.CockpitMetric(
                label="Expiring qualifications",
                value=len(expiring),
                state="red" if overdue_qualifications else ("yellow" if expiring else "green"),
            ),
            schemas.CockpitMetric(label="Pipeline EUR", value=float(pipeline_value), state="green"),
            schemas.CockpitMetric(
                label="Service due", value=int(service_due_count or 0), state="yellow" if service_due_count else "green"
            ),
            schemas.CockpitMetric(
                label="Employee reminders", value=employee_due_count, state="yellow" if employee_due_count else "green"
            ),
            schemas.CockpitMetric(
                label="Vehicle reminders", value=vehicle_due_count, state="yellow" if vehicle_due_count else "green"
            ),
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


# --------------------------------------------------------------------------
# Branch assessments
# --------------------------------------------------------------------------


@app.get(
    "/api/branch-assessments",
    response_model=list[schemas.BranchAssessmentRead],
    dependencies=[Depends(requires(permissions.ASSESSMENT_READ))],
)
def list_branch_assessments(
    branch_id: str | None = None, db: Session = Depends(get_db)
) -> list[schemas.BranchAssessmentRead]:
    query = select(models.BranchAssessment).order_by(models.BranchAssessment.assessment_date.desc())
    if branch_id:
        query = query.where(models.BranchAssessment.branch_id == branch_id)
    return [assessment_read(item) for item in db.scalars(query).all()]


@app.post("/api/branch-assessments", response_model=schemas.BranchAssessmentRead)
def create_branch_assessment(
    payload: schemas.BranchAssessmentCreate,
    principal: Annotated[Principal, Depends(requires(permissions.ASSESSMENT_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.BranchAssessmentRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.User, payload.created_by, "created_by")
    assessment = models.BranchAssessment(**payload.model_dump())
    db.add(assessment)
    db.flush()
    audit(db, "branch_assessment", assessment.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(assessment)
    return assessment_read(assessment)


# --------------------------------------------------------------------------
# Hermes context
# --------------------------------------------------------------------------


@app.get(
    "/api/hermes/context/branches/{branch_id}",
    response_model=schemas.HermesBranchContext,
    dependencies=[Depends(requires(permissions.COMPLIANCE_READ, permissions.PERSONNEL_READ))],
)
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
    vehicles = db.scalars(
        select(models.Vehicle)
        .where(models.Vehicle.branch_id == branch_id)
        .order_by(models.Vehicle.license_plate.asc())
    ).all()
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


# --------------------------------------------------------------------------
# Compliance records
# --------------------------------------------------------------------------


@app.get(
    "/api/compliance-records",
    response_model=list[schemas.ComplianceRecordRead],
    dependencies=[Depends(requires(permissions.COMPLIANCE_READ))],
)
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


@app.post("/api/compliance-records", response_model=schemas.ComplianceRecordRead)
def create_compliance_record(
    payload: schemas.ComplianceRecordCreate,
    principal: Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.ComplianceRecordRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.User, payload.owner_user_id, "owner_user_id")
    ensure_ref(db, models.User, payload.approved_by, "approved_by")
    record = models.ComplianceRecord(**payload.model_dump())
    db.add(record)
    db.flush()
    audit(db, "compliance_record", record.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(record)
    return record_read(record)


@app.get(
    "/api/compliance-records/{record_id}",
    response_model=schemas.ComplianceRecordRead,
    dependencies=[Depends(requires(permissions.COMPLIANCE_READ))],
)
def get_compliance_record(record_id: str, db: Session = Depends(get_db)) -> schemas.ComplianceRecordRead:
    return record_read(load_record(db, record_id))


@app.patch("/api/compliance-records/{record_id}", response_model=schemas.ComplianceRecordRead)
def update_compliance_record(
    record_id: str,
    payload: schemas.ComplianceRecordUpdate,
    principal: Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.ComplianceRecordRead:
    record = load_record(db, record_id)
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.User, changes.get("owner_user_id"), "owner_user_id")
    ensure_ref(db, models.User, changes.get("approved_by"), "approved_by")
    before = {field: getattr(record, field) for field in changes}
    for field, value in changes.items():
        setattr(record, field, value)
    audit(
        db,
        "compliance_record",
        record.id,
        "updated",
        {"before": _jsonable(before), "after": payload.model_dump(mode="json", exclude_unset=True)},
        principal,
    )
    db.commit()
    return record_read(load_record(db, record_id))


def _jsonable(values: dict) -> dict:
    """Audit payloads are stored as JSON, so dates/datetimes need converting."""
    result: dict[str, Any] = {}
    for key, value in values.items():
        result[key] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return result


@app.post("/api/compliance-records/{record_id}/evidence", response_model=schemas.ComplianceEvidenceRead)
def add_evidence(
    record_id: str,
    payload: schemas.ComplianceEvidenceCreate,
    principal: Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.ComplianceEvidenceRead:
    if not db.get(models.ComplianceRecord, record_id):
        raise HTTPException(status_code=404, detail="Compliance record not found")
    ensure_ref(db, models.User, payload.uploaded_by, "uploaded_by")
    ensure_ref(db, models.Employee, payload.linked_employee_id, "linked_employee_id")
    ensure_ref(db, models.Project, payload.linked_project_id, "linked_project_id")
    evidence = models.ComplianceEvidence(compliance_record_id=record_id, **payload.model_dump())
    db.add(evidence)
    db.flush()
    audit(db, "compliance_record", record_id, "evidence_added", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(evidence)
    return evidence


@app.post("/api/compliance-records/{record_id}/actions", response_model=schemas.ComplianceActionRead)
def add_action(
    record_id: str,
    payload: schemas.ComplianceActionCreate,
    principal: Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))],
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


@app.get(
    "/api/actions",
    response_model=list[schemas.ComplianceActionRead],
    dependencies=[Depends(requires(permissions.COMPLIANCE_READ))],
)
def list_actions(db: Session = Depends(get_db)) -> list[schemas.ComplianceActionRead]:
    actions = db.scalars(select(models.ComplianceAction).order_by(models.ComplianceAction.due_date.asc())).all()
    return [action_read(action) for action in actions]


@app.patch("/api/actions/{action_id}", response_model=schemas.ComplianceActionRead)
def update_action(
    action_id: str,
    payload: schemas.ComplianceActionUpdate,
    principal: Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.ComplianceActionRead:
    action = db.get(models.ComplianceAction, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
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


# --------------------------------------------------------------------------
# Personnel
# --------------------------------------------------------------------------


@app.get(
    "/api/employees",
    response_model=list[schemas.EmployeeRead],
    dependencies=[Depends(requires(permissions.PERSONNEL_READ))],
)
def list_employees(db: Session = Depends(get_db)) -> list[schemas.EmployeeRead]:
    employees = db.scalars(
        select(models.Employee).options(
            selectinload(models.Employee.qualifications), selectinload(models.Employee.profile)
        )
    ).all()
    return [employee_read(employee) for employee in employees]


@app.post("/api/employees", response_model=schemas.EmployeeRead)
def create_employee(
    payload: schemas.EmployeeCreate,
    principal: Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.EmployeeRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    employee = models.Employee(**payload.model_dump())
    db.add(employee)
    db.flush()
    audit(db, "employee", employee.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(employee)
    return employee_read(employee)


@app.post("/api/employee-qualifications", response_model=schemas.EmployeeQualificationRead)
def create_qualification(
    payload: schemas.EmployeeQualificationCreate,
    principal: Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.EmployeeQualificationRead:
    ensure_ref(db, models.Employee, payload.employee_id, "employee_id")
    ensure_ref(db, models.Document, payload.document_id, "document_id")
    qualification = models.EmployeeQualification(**payload.model_dump())
    db.add(qualification)
    db.flush()
    audit(db, "employee_qualification", qualification.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(qualification)
    return qualification_read(qualification)


@app.post("/api/employee-profiles", response_model=schemas.EmployeeProfileRead)
def upsert_employee_profile(
    payload: schemas.EmployeeProfileCreate,
    principal: Annotated[Principal, Depends(requires(permissions.PERSONNEL_WRITE))],
    db: Session = Depends(get_db),
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


# --------------------------------------------------------------------------
# Fleet
# --------------------------------------------------------------------------


@app.get(
    "/api/vehicles",
    response_model=list[schemas.VehicleRead],
    dependencies=[Depends(requires(permissions.FLEET_READ))],
)
def list_vehicles(branch_id: str | None = None, db: Session = Depends(get_db)) -> list[schemas.VehicleRead]:
    query = select(models.Vehicle).order_by(models.Vehicle.license_plate.asc())
    if branch_id:
        query = query.where(models.Vehicle.branch_id == branch_id)
    return [vehicle_read(vehicle) for vehicle in db.scalars(query).all()]


@app.post("/api/vehicles", response_model=schemas.VehicleRead)
def create_vehicle(
    payload: schemas.VehicleCreate,
    principal: Annotated[Principal, Depends(requires(permissions.FLEET_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.VehicleRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.Employee, payload.assigned_employee_id, "assigned_employee_id")
    vehicle = models.Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.flush()
    audit(db, "vehicle", vehicle.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(vehicle)
    return vehicle_read(vehicle)


# --------------------------------------------------------------------------
# Reminders, incidents, audit
# --------------------------------------------------------------------------


@app.get("/api/reminders", response_model=list[schemas.ReminderRead])
def list_reminders(
    principal: CurrentPrincipal, branch_id: str | None = None, db: Session = Depends(get_db)
) -> list[schemas.ReminderRead]:
    may_read_personnel = principal.has(permissions.PERSONNEL_READ)
    may_read_fleet = principal.has(permissions.FLEET_READ)
    if not (may_read_personnel or may_read_fleet):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission(s): {permissions.PERSONNEL_READ} or {permissions.FLEET_READ}",
        )
    return build_reminders(
        db, branch_id, include_personnel=may_read_personnel, include_fleet=may_read_fleet
    )


@app.get(
    "/api/incidents",
    response_model=list[schemas.IncidentRead],
    dependencies=[Depends(requires(permissions.INCIDENT_READ))],
)
def list_incidents(db: Session = Depends(get_db)) -> list[schemas.IncidentRead]:
    return db.scalars(select(models.Incident).order_by(models.Incident.occurred_at.desc())).all()


@app.post("/api/incidents", response_model=schemas.IncidentRead)
def create_incident(
    payload: schemas.IncidentCreate,
    principal: Annotated[Principal, Depends(requires(permissions.INCIDENT_WRITE))],
    db: Session = Depends(get_db),
) -> schemas.IncidentRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.User, payload.owner_user_id, "owner_user_id")
    ensure_ref(db, models.Project, payload.project_id, "project_id")
    ensure_ref(db, models.ProjectSite, payload.site_id, "site_id")
    incident = models.Incident(**payload.model_dump())
    db.add(incident)
    db.flush()
    audit(db, "incident", incident.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(incident)
    return incident


@app.get(
    "/api/audit-log",
    response_model=list[schemas.AuditLogRead],
    dependencies=[Depends(requires(permissions.AUDIT_READ))],
)
def list_audit_log(
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    db: Session = Depends(get_db),
) -> list[schemas.AuditLogRead]:
    query = select(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit)
    if entity_type:
        query = query.where(models.AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(models.AuditLog.entity_id == entity_id)
    return db.scalars(query).all()


# --------------------------------------------------------------------------
# Hermes agent
# --------------------------------------------------------------------------


@app.post("/api/agent/compliance-review", response_model=schemas.AgentReviewResponse)
async def agent_compliance_review(
    payload: schemas.AgentComplianceReviewRequest,
    principal: Annotated[Principal, Depends(requires(permissions.AGENT_RUN))],
    db: Session = Depends(get_db),
) -> schemas.AgentReviewResponse:
    record = load_record(db, payload.compliance_record_id)

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
        created_by=principal.user_id,
    )
    db.add(run)
    db.commit()
    try:
        run.response_payload = await HermesClient().compliance_review(request_payload)
        run.status = "completed"
    except Exception as exc:  # Hermes failures must be visible but not crash the app state.
        logger.warning("Hermes compliance review failed for record %s: %s", record.id, exc)
        run.response_payload = {"error": str(exc)}
        run.status = "failed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    return schemas.AgentReviewResponse(id=run.id, status=run.status, response_payload=run.response_payload)
