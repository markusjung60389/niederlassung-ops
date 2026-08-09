"""ORM to response-schema conversion, shared across routers."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models, permissions, readiness, schemas
from .auth import Principal
from .domain import DEFAULT_REMINDER_WINDOW_DAYS, due_state, is_overdue, needs_attention


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
        qualification_type_id=qualification.qualification_type_id,
        issued_on=qualification.issued_on,
        valid_until=qualification.valid_until,
        document_id=qualification.document_id,
        reminder_days=qualification.reminder_days,
        due_state=due_state("open", qualification.valid_until),
        overdue=is_overdue("open", qualification.valid_until),
    )


def qualification_type_read(kind: models.QualificationType) -> schemas.QualificationTypeRead:
    return schemas.QualificationTypeRead.model_validate(kind)


def requirement_read(requirement: models.JobRoleRequirement) -> schemas.JobRoleRequirementRead:
    return schemas.JobRoleRequirementRead(
        id=requirement.id,
        job_role_id=requirement.job_role_id,
        qualification_type_id=requirement.qualification_type_id,
        mandatory=requirement.mandatory,
        note=requirement.note,
        qualification_name=requirement.qualification_type.name,
        qualification_code=requirement.qualification_type.code,
    )


def job_role_read(role: models.JobRole, employee_count: int = 0) -> schemas.JobRoleRead:
    requirements = sorted(
        role.requirements, key=lambda item: (not item.mandatory, item.qualification_type.name)
    )
    return schemas.JobRoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        active=role.active,
        requirements=[requirement_read(item) for item in requirements],
        employee_count=employee_count,
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
    due_items = readiness.vehicle_due_items(vehicle)
    first = due_items[0] if due_items else None
    return schemas.VehicleRead(
        **{
            column.name: getattr(vehicle, column.name)
            for column in models.Vehicle.__table__.columns
        },
        assigned_employee_name=(
            vehicle.assigned_employee.full_name if vehicle.assigned_employee else None
        ),
        due_state=first.tone if first else "green",
        next_due_title=first.title if first else None,
        next_due_date=first.due_date if first else None,
        driver_alert=readiness.driver_licence_alert(vehicle),
    )


def employee_read(employee: models.Employee) -> schemas.EmployeeRead:
    states = readiness.requirement_states(employee)
    level = readiness.readiness_of(states)
    due_items = readiness.employee_due_items(employee, states)
    first = due_items[0] if due_items else None

    # An employee who has left keeps their record but stops raising alarms.
    if employee.status != "active":
        level, tone = readiness.READY, "green"
    else:
        tone = readiness.TONE_BY_READINESS[level]
        if first and first.tone == "red":
            tone = "red"
        elif tone == "green" and first:
            tone = "yellow"

    return schemas.EmployeeRead(
        id=employee.id,
        branch_id=employee.branch_id,
        full_name=employee.full_name,
        role=employee.role,
        job_role_id=employee.job_role_id,
        job_role_name=employee.job_role.name if employee.job_role else None,
        team=employee.team,
        start_date=employee.start_date,
        status=employee.status,
        exit_date=employee.exit_date,
        first_aider=employee.first_aider,
        skills=employee.skills,
        notes=employee.notes,
        qualifications=[qualification_read(item) for item in employee.qualifications],
        profile=profile_read(employee.profile),
        requirements=[schemas.RequirementStateRead(**vars(item)) for item in states],
        readiness=level,
        due_state=tone,
        open_requirements=sum(1 for item in states if item.open),
        next_due_title=first.title if first else None,
        next_due_date=first.due_date if first else None,
    )


def assessment_read(assessment: models.BranchAssessment) -> schemas.BranchAssessmentRead:
    return schemas.BranchAssessmentRead.model_validate(assessment)


def load_record(db: Session, record_id: str) -> models.ComplianceRecord:
    from fastapi import HTTPException

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
        employee_query = (
            select(models.Employee)
            .where(models.Employee.status == "active")
            .options(
                selectinload(models.Employee.profile), selectinload(models.Employee.qualifications)
            )
        )
        if branch_id:
            employee_query = employee_query.where(models.Employee.branch_id == branch_id)
        for employee in db.scalars(employee_query).all():
            profile = employee.profile
            if profile:
                # Only the person's own contractual dates live here. The
                # training and licence dates moved into qualifications with
                # migration 0004 and are picked up in the loop below - reading
                # both would produce the same reminder twice.
                candidates = [
                    ("Arbeitsvertrag befristet bis", profile.contract_end),
                    ("Probezeit endet", profile.probation_until),
                    ("Aufenthaltserlaubnis/Arbeitserlaubnis pruefen", profile.residence_permit_valid_until),
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


def reminders_for(db: Session, principal: Principal, branch_id: str | None = None):
    return build_reminders(
        db,
        branch_id,
        include_personnel=principal.has(permissions.PERSONNEL_READ),
        include_fleet=principal.has(permissions.FLEET_READ),
    )


# --------------------------------------------------------------------------
# Loading helpers
# --------------------------------------------------------------------------

EMPLOYEE_LOAD_OPTIONS = (
    selectinload(models.Employee.qualifications),
    selectinload(models.Employee.profile),
    selectinload(models.Employee.job_role).selectinload(models.JobRole.requirements),
)

VEHICLE_LOAD_OPTIONS = (
    selectinload(models.Vehicle.assigned_employee).selectinload(models.Employee.qualifications),
)


def employee_query(branch_id: str | None = None, include_inactive: bool = False):
    query = select(models.Employee).options(*EMPLOYEE_LOAD_OPTIONS)
    if branch_id:
        query = query.where(models.Employee.branch_id == branch_id)
    if not include_inactive:
        query = query.where(models.Employee.status == "active")
    return query.order_by(models.Employee.full_name.asc())


def qualification_matrix(
    db: Session, branch_id: str | None = None
) -> schemas.QualificationMatrix:
    """Employees against qualification types.

    Only the types that at least one function actually requires are shown -
    a matrix listing every catalogue entry would be mostly empty columns.
    """
    employees = db.scalars(employee_query(branch_id)).all()
    required_ids = {
        requirement.qualification_type_id
        for employee in employees
        if employee.job_role
        for requirement in employee.job_role.requirements
    }
    types = db.scalars(
        select(models.QualificationType)
        .where(models.QualificationType.id.in_(required_ids or {"-"}))
        .order_by(models.QualificationType.name.asc())
    ).all()

    rows = []
    for employee in employees:
        states = {item.qualification_type_id: item for item in readiness.requirement_states(employee)}
        rows.append(
            schemas.MatrixRow(
                employee_id=employee.id,
                full_name=employee.full_name,
                job_role_id=employee.job_role_id,
                job_role_name=employee.job_role.name if employee.job_role else None,
                readiness=readiness.readiness_of(list(states.values())),
                cells=[
                    schemas.MatrixCell(
                        qualification_type_id=kind.id,
                        state=states[kind.id].state if kind.id in states else "not_required",
                        mandatory=states[kind.id].mandatory if kind.id in states else False,
                        valid_until=states[kind.id].valid_until if kind.id in states else None,
                        has_evidence=states[kind.id].has_evidence if kind.id in states else False,
                    )
                    for kind in types
                ],
            )
        )

    return schemas.QualificationMatrix(
        qualification_types=[qualification_type_read(kind) for kind in types], rows=rows
    )
