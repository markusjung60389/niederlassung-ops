from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    location: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    # Microsoft Entra ID object id ("oid" claim). Empty until the account signs in via Azure AD.
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    role_id: Mapped[str | None] = mapped_column(ForeignKey("roles.id"))
    role: Mapped[Role | None] = relationship(lazy="joined")


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    team: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    first_aider: Mapped[bool] = mapped_column(default=False, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    branch: Mapped[Branch] = relationship()
    qualifications: Mapped[list["EmployeeQualification"]] = relationship(back_populates="employee")
    profile: Mapped["EmployeeProfile | None"] = relationship(back_populates="employee", uselist=False)


class EmployeeQualification(Base, TimestampMixin):
    __tablename__ = "employee_qualifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    qualification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    reminder_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    employee: Mapped[Employee] = relationship(back_populates="qualifications")

class EmployeeProfile(Base, TimestampMixin):
    __tablename__ = "employee_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, unique=True)
    contract_type: Mapped[str] = mapped_column(String(40), default="unbefristet", nullable=False)
    contract_start: Mapped[date | None] = mapped_column(Date)
    contract_end: Mapped[date | None] = mapped_column(Date)
    probation_until: Mapped[date | None] = mapped_column(Date)
    residence_permit_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    residence_permit_type: Mapped[str | None] = mapped_column(String(120))
    residence_permit_valid_until: Mapped[date | None] = mapped_column(Date)
    work_permit_note: Mapped[str | None] = mapped_column(Text)
    driver_license_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    driver_license_classes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    driver_license_last_check: Mapped[date | None] = mapped_column(Date)
    driver_license_next_check: Mapped[date | None] = mapped_column(Date)
    first_aid_last_course: Mapped[date | None] = mapped_column(Date)
    first_aid_valid_until: Mapped[date | None] = mapped_column(Date)
    ipaf_last_training: Mapped[date | None] = mapped_column(Date)
    ipaf_valid_until: Mapped[date | None] = mapped_column(Date)
    general_instruction_last: Mapped[date | None] = mapped_column(Date)
    general_instruction_next: Mapped[date | None] = mapped_column(Date)
    occupational_health_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    occupational_health_last: Mapped[date | None] = mapped_column(Date)
    occupational_health_next: Mapped[date | None] = mapped_column(Date)
    ppe_issued_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    employee: Mapped[Employee] = relationship(back_populates="profile")


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    license_plate: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    vehicle_type: Mapped[str | None] = mapped_column(String(80))
    vin: Mapped[str | None] = mapped_column(String(80))
    first_registration: Mapped[date | None] = mapped_column(Date)
    ownership_type: Mapped[str | None] = mapped_column(String(80))
    assigned_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"))
    mileage: Mapped[int | None] = mapped_column(Integer)
    hu_due_date: Mapped[date | None] = mapped_column(Date)
    uvv_last_check: Mapped[date | None] = mapped_column(Date)
    uvv_next_check: Mapped[date | None] = mapped_column(Date)
    service_due_date: Mapped[date | None] = mapped_column(Date)
    tire_type: Mapped[str | None] = mapped_column(String(40))
    tire_change_due_date: Mapped[date | None] = mapped_column(Date)
    insurance_valid_until: Mapped[date | None] = mapped_column(Date)
    fuel_card_number: Mapped[str | None] = mapped_column(String(120))
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    branch: Mapped[Branch] = relationship()
    assigned_employee: Mapped[Employee | None] = relationship()

class EmployeeReview(Base, TimestampMixin):
    __tablename__ = "employee_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False)
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    development_goals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    account_type: Mapped[str] = mapped_column(String(80), default="existing", nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    offer_status: Mapped[str] = mapped_column(String(80), default="lead", nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    expected_volume: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    next_step: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    strategic_relevance: Mapped[str] = mapped_column(String(80), default="medium", nullable=False)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(80), default="active", nullable=False)
    risk_state: Mapped[str] = mapped_column(String(20), default="green", nullable=False)


class ProjectSite(Base, TimestampMixin):
    __tablename__ = "project_sites"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    address: Mapped[str | None] = mapped_column(String(240))
    safety_notes: Mapped[str | None] = mapped_column(Text)


class ServiceContract(Base, TimestampMixin):
    __tablename__ = "service_contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    sla_response_hours: Mapped[int | None] = mapped_column(Integer)
    next_maintenance_at: Mapped[date | None] = mapped_column(Date, index=True)
    upsell_hint: Mapped[str | None] = mapped_column(Text)


class ServiceEvent(Base, TimestampMixin):
    __tablename__ = "service_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    service_contract_id: Mapped[str] = mapped_column(ForeignKey("service_contracts.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scheduled_at: Mapped[date | None] = mapped_column(Date)
    resolved_at: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    repeat_issue: Mapped[bool] = mapped_column(default=False, nullable=False)


class ComplianceRecord(Base, TimestampMixin):
    __tablename__ = "compliance_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(40), default="branch", nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    legal_basis: Mapped[str] = mapped_column(String(200), nullable=False)
    control_type: Mapped[str] = mapped_column(String(40), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    risk_if_missing: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    recurrence: Mapped[str] = mapped_column(String(40), default="yearly", nullable=False)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    branch: Mapped[Branch] = relationship()
    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id])
    evidence: Mapped[list["ComplianceEvidence"]] = relationship(back_populates="record")
    actions: Mapped[list["ComplianceAction"]] = relationship(back_populates="record")


class ComplianceEvidence(Base, TimestampMixin):
    __tablename__ = "compliance_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    compliance_record_id: Mapped[str] = mapped_column(ForeignKey("compliance_records.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(240), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    evidence_type: Mapped[str] = mapped_column(String(80), default="other", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    linked_employee_id: Mapped[str | None] = mapped_column(ForeignKey("employees.id"))
    linked_project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    linked_equipment_id: Mapped[str | None] = mapped_column(String)
    record: Mapped[ComplianceRecord] = relationship(back_populates="evidence")


class ComplianceAction(Base, TimestampMixin):
    __tablename__ = "compliance_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    compliance_record_id: Mapped[str] = mapped_column(ForeignKey("compliance_records.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False, index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record: Mapped[ComplianceRecord] = relationship(back_populates="actions")


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    site_id: Mapped[str | None] = mapped_column(ForeignKey("project_sites.id"))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    immediate_action: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    preventive_action: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    file_name: Mapped[str] = mapped_column(String(240), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[str | None] = mapped_column(String(80))
    source_id: Mapped[str | None] = mapped_column(String)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    changes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

class BranchAssessment(Base, TimestampMixin):
    __tablename__ = "branch_assessments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    team_structure: Mapped[str | None] = mapped_column(Text)
    customer_clusters: Mapped[str | None] = mapped_column(Text)
    service_portfolio: Mapped[str | None] = mapped_column(Text)
    project_types: Mapped[str | None] = mapped_column(Text)
    service_share: Mapped[str | None] = mapped_column(String(120))
    main_problems: Mapped[str | None] = mapped_column(Text)
    management_ratings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    next_actions: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    branch: Mapped[Branch] = relationship()

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    use_case: Mapped[str] = mapped_column(String(80), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
