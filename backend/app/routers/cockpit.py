from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import models, permissions, schemas
from ..auth import CurrentPrincipal, Principal, requires
from ..database import get_db
from ..domain import DUE_SOON_DAYS, is_overdue, needs_attention, today_local, within_days
from ..serializers import (
    action_read,
    build_reminders,
    qualification_read,
    record_read,
    reminders_for,
)

router = APIRouter(tags=["cockpit"])


@router.get("/api/cockpit", response_model=schemas.CockpitResponse)
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
    reminders = reminders_for(db, principal)
    qualifications = db.scalars(select(models.EmployeeQualification)).all() if may_read_personnel else []

    employee_due_count = len([item for item in reminders if item.source_type.startswith("employee")])
    vehicle_due_count = len([item for item in reminders if item.source_type == "vehicle"])

    # Only opportunities that are still live count towards the pipeline.
    pipeline_value = db.scalar(
        select(func.coalesce(func.sum(models.Opportunity.expected_volume), 0)).where(
            models.Opportunity.offer_status.notin_(["won", "lost"])
        )
    ) or 0
    service_due_count = db.scalar(
        select(func.count(models.ServiceContract.id)).where(
            models.ServiceContract.next_maintenance_at <= today_local()
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


@router.get("/api/reminders", response_model=list[schemas.ReminderRead])
def list_reminders(
    principal: CurrentPrincipal, branch_id: str | None = None, db: Session = Depends(get_db)
) -> list[schemas.ReminderRead]:
    if not (principal.has(permissions.PERSONNEL_READ) or principal.has(permissions.FLEET_READ)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission(s): {permissions.PERSONNEL_READ} or {permissions.FLEET_READ}",
        )
    return reminders_for(db, principal, branch_id)


@router.get(
    "/api/hermes/context/branches/{branch_id}",
    response_model=schemas.HermesBranchContext,
    dependencies=[Depends(requires(permissions.COMPLIANCE_READ, permissions.PERSONNEL_READ))],
    tags=["hermes"],
)
def hermes_branch_context(branch_id: str, db: Session = Depends(get_db)) -> schemas.HermesBranchContext:
    from ..serializers import assessment_read, employee_read, vehicle_read

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
