from __future__ import annotations
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ComplianceCategory = Literal[
    "work_safety_organization",
    "risk_assessment",
    "training_instruction",
    "construction_site_coordination",
    "tools_and_equipment_inspection",
    "working_time",
    "first_aid",
    "occupational_health",
    "electrical_safety",
    "incident_and_deviation",
    "documentation",
]
ComplianceStatus = Literal["open", "in_progress", "compliant", "non_compliant", "expired", "waived"]
Priority = Literal["low", "medium", "high", "critical"]
ControlType = Literal["document", "training", "inspection", "medical", "process", "incident", "approval"]
ScopeType = Literal["branch", "site", "project", "employee", "equipment", "vehicle"]
Recurrence = Literal["one_time", "monthly", "quarterly", "yearly", "event_based"]
ActionStatus = Literal["open", "in_progress", "blocked", "done", "cancelled"]


class BranchRead(BaseModel):
    id: str
    name: str
    location: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: str
    display_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class PrincipalRead(BaseModel):
    """The caller as resolved by the configured identity provider."""

    user_id: str
    display_name: str
    email: str | None = None
    role_name: str | None = None
    permissions: list[str]
    source: str


class DevUserRead(BaseModel):
    """Selectable identity for AUTH_MODE=dev. Never served in azure_ad mode."""

    id: str
    display_name: str
    role_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogRead(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_user_id: str | None = None
    changes: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceEvidenceCreate(BaseModel):
    file_name: str = Field(min_length=1, max_length=240)
    storage_path: str = Field(min_length=1, max_length=400)
    mime_type: str | None = None
    evidence_type: str = "other"
    description: str | None = None
    uploaded_by: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    linked_employee_id: str | None = None
    linked_project_id: str | None = None
    linked_equipment_id: str | None = None


class ComplianceEvidenceRead(ComplianceEvidenceCreate):
    id: str
    compliance_record_id: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplianceActionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str | None = None
    owner_user_id: str
    due_date: date
    priority: Priority = "medium"
    status: ActionStatus = "open"
    escalation_level: int = Field(default=0, ge=0, le=5)


class ComplianceActionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = None
    owner_user_id: str | None = None
    due_date: date | None = None
    priority: Priority | None = None
    status: ActionStatus | None = None
    escalation_level: int | None = Field(default=None, ge=0, le=5)


class ComplianceActionRead(BaseModel):
    id: str
    compliance_record_id: str
    title: str
    description: str | None = None
    owner_user_id: str
    due_date: date
    priority: str
    status: str
    escalation_level: int
    completed_at: datetime | None = None
    due_state: str
    overdue: bool

    model_config = ConfigDict(from_attributes=True)


class ComplianceRecordCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: ComplianceCategory
    branch_id: str
    scope_type: ScopeType = "branch"
    scope_id: str | None = None
    status: ComplianceStatus = "open"
    priority: Priority = "medium"
    owner_user_id: str
    legal_basis: str = Field(min_length=2, max_length=200)
    control_type: ControlType
    due_date: date
    review_date: date
    description: str | None = None
    risk_if_missing: str | None = None
    evidence_summary: str | None = None
    recurrence: Recurrence = "yearly"
    last_completed_at: datetime | None = None
    next_due_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class ComplianceRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    category: ComplianceCategory | None = None
    scope_type: ScopeType | None = None
    scope_id: str | None = None
    status: ComplianceStatus | None = None
    priority: Priority | None = None
    owner_user_id: str | None = None
    legal_basis: str | None = Field(default=None, min_length=2, max_length=200)
    control_type: ControlType | None = None
    due_date: date | None = None
    review_date: date | None = None
    description: str | None = None
    risk_if_missing: str | None = None
    evidence_summary: str | None = None
    recurrence: Recurrence | None = None
    last_completed_at: datetime | None = None
    next_due_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    tags: list[str] | None = None
    notes: str | None = None


class ComplianceRecordRead(BaseModel):
    id: str
    title: str
    category: str
    branch_id: str
    scope_type: str
    scope_id: str | None = None
    status: str
    priority: str
    owner_user_id: str
    legal_basis: str
    control_type: str
    due_date: date
    review_date: date
    description: str | None = None
    risk_if_missing: str | None = None
    evidence_summary: str | None = None
    recurrence: str
    last_completed_at: datetime | None = None
    next_due_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    tags: list[str]
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    due_state: str
    overdue: bool
    evidence: list[ComplianceEvidenceRead] = []
    actions: list[ComplianceActionRead] = []

    model_config = ConfigDict(from_attributes=True)


class IncidentCreate(BaseModel):
    type: Literal["incident", "near_miss", "deviation"]
    severity: Priority
    occurred_at: datetime
    branch_id: str
    project_id: str | None = None
    site_id: str | None = None
    summary: str = Field(min_length=3)
    immediate_action: str | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    closed_at: datetime | None = None
    owner_user_id: str


class IncidentRead(IncidentCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeQualificationCreate(BaseModel):
    employee_id: str
    title: str = Field(min_length=2, max_length=180)
    qualification_type: str = Field(min_length=2, max_length=80)
    valid_until: date | None = None
    document_id: str | None = None
    reminder_days: int = Field(default=30, ge=1, le=365)


class EmployeeQualificationRead(EmployeeQualificationCreate):
    id: str
    due_state: str
    overdue: bool

    model_config = ConfigDict(from_attributes=True)


class EmployeeCreate(BaseModel):
    branch_id: str
    full_name: str = Field(min_length=2, max_length=160)
    role: str = Field(min_length=2, max_length=120)
    team: str | None = None
    start_date: date | None = None
    first_aider: bool = False
    skills: list[str] = Field(default_factory=list)
    notes: str | None = None


class EmployeeRead(EmployeeCreate):
    id: str
    qualifications: list[EmployeeQualificationRead] = []
    profile: EmployeeProfileRead | None = None

    model_config = ConfigDict(from_attributes=True)
class EmployeeProfileCreate(BaseModel):
    employee_id: str
    contract_type: str = "unbefristet"
    contract_start: date | None = None
    contract_end: date | None = None
    probation_until: date | None = None
    residence_permit_required: bool = False
    residence_permit_type: str | None = None
    residence_permit_valid_until: date | None = None
    work_permit_note: str | None = None
    driver_license_required: bool = False
    driver_license_classes: list[str] = Field(default_factory=list)
    driver_license_last_check: date | None = None
    driver_license_next_check: date | None = None
    first_aid_last_course: date | None = None
    first_aid_valid_until: date | None = None
    ipaf_last_training: date | None = None
    ipaf_valid_until: date | None = None
    general_instruction_last: date | None = None
    general_instruction_next: date | None = None
    occupational_health_required: bool = False
    occupational_health_last: date | None = None
    occupational_health_next: date | None = None
    ppe_issued_at: date | None = None
    notes: str | None = None


class EmployeeProfileRead(EmployeeProfileCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleCreate(BaseModel):
    branch_id: str
    license_plate: str = Field(min_length=2, max_length=40)
    brand: str | None = None
    model: str | None = None
    vehicle_type: str | None = None
    vin: str | None = None
    first_registration: date | None = None
    ownership_type: str | None = None
    assigned_employee_id: str | None = None
    mileage: int | None = Field(default=None, ge=0)
    hu_due_date: date | None = None
    uvv_last_check: date | None = None
    uvv_next_check: date | None = None
    service_due_date: date | None = None
    tire_type: str | None = None
    tire_change_due_date: date | None = None
    insurance_valid_until: date | None = None
    fuel_card_number: str | None = None
    equipment: list[str] = Field(default_factory=list)
    notes: str | None = None


class VehicleRead(VehicleCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReminderRead(BaseModel):
    source_type: str
    source_id: str
    title: str
    due_date: date
    state: str
    owner_hint: str | None = None

class BranchAssessmentCreate(BaseModel):
    branch_id: str
    title: str = Field(min_length=3, max_length=180)
    assessment_date: date
    team_structure: str | None = None
    customer_clusters: str | None = None
    service_portfolio: str | None = None
    project_types: str | None = None
    service_share: str | None = None
    main_problems: str | None = None
    management_ratings: dict[str, str] = Field(default_factory=dict)
    next_actions: list[dict[str, str]] = Field(default_factory=list)
    notes: str | None = None
    created_by: str | None = None


class BranchAssessmentRead(BranchAssessmentCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HermesBranchContext(BaseModel):
    branch: BranchRead
    latest_assessment: BranchAssessmentRead | None
    compliance_records: list[ComplianceRecordRead]
    employees: list[EmployeeRead]
    vehicles: list[VehicleRead]
    reminders: list[ReminderRead]
    open_actions: list[ComplianceActionRead]
    incidents: list[IncidentRead]

class CockpitMetric(BaseModel):
    label: str
    value: int | float
    state: str = "green"


class CockpitResponse(BaseModel):
    metrics: list[CockpitMetric]
    overdue_compliance: list[ComplianceRecordRead]
    due_soon_compliance: list[ComplianceRecordRead]
    open_actions: list[ComplianceActionRead]
    expiring_qualifications: list[EmployeeQualificationRead]
    incidents: list[IncidentRead]
    reminders: list[ReminderRead]
    pipeline_value: float
    service_due_count: int
    vehicle_due_count: int
    employee_due_count: int


class AgentComplianceReviewRequest(BaseModel):
    compliance_record_id: str
    prompt: str | None = None


class AgentReviewResponse(BaseModel):
    id: str
    status: str
    response_payload: dict | None = None



