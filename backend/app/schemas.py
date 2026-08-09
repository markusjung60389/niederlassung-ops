from __future__ import annotations
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    code: str | None = None
    location: str | None = None
    active: bool = True
    manager_user_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = Field(default=None, max_length=10)
    location: str | None = None
    manager_user_id: str | None = None
    notes: str | None = None


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    code: str | None = Field(default=None, max_length=10)
    location: str | None = None
    active: bool | None = None
    manager_user_id: str | None = None
    notes: str | None = None


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
    """Metadata accompanying an upload.

    `file_name` and `storage_path` are deliberately absent: the server derives
    both from the uploaded file. A client-supplied path would let a caller point
    a record at any location on disk.
    """

    evidence_type: str = Field(default="other", max_length=80)
    description: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    linked_employee_id: str | None = None
    linked_project_id: str | None = None
    linked_equipment_id: str | None = None


class ComplianceEvidenceRead(BaseModel):
    id: str
    compliance_record_id: str
    file_name: str
    storage_path: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    evidence_type: str
    description: str | None = None
    uploaded_by: str | None = None
    uploaded_at: datetime
    valid_from: date | None = None
    valid_until: date | None = None
    linked_employee_id: str | None = None
    linked_project_id: str | None = None
    linked_equipment_id: str | None = None

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
    # The rule this is the branch's instance of; None for a record that stands
    # on its own, which is what every record was before rules existed.
    rule_id: str | None = None
    rule_scope: str | None = None
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


class QualificationTypeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=180)
    # None keeps the entry group-wide, which is the default on purpose.
    branch_id: str | None = None
    category: str = Field(default="qualification", max_length=60)
    validity_months: int | None = Field(default=None, ge=1, le=600)
    reminder_days: int = Field(default=60, ge=1, le=365)
    evidence_required: bool = True
    legal_basis: str | None = Field(default=None, max_length=200)
    description: str | None = None
    active: bool = True


class QualificationTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    category: str | None = Field(default=None, max_length=60)
    validity_months: int | None = Field(default=None, ge=1, le=600)
    reminder_days: int | None = Field(default=None, ge=1, le=365)
    evidence_required: bool | None = None
    legal_basis: str | None = Field(default=None, max_length=200)
    description: str | None = None
    active: bool | None = None


class QualificationTypeRead(QualificationTypeCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)


class JobRoleRequirementCreate(BaseModel):
    job_role_id: str
    qualification_type_id: str
    mandatory: bool = True
    note: str | None = None


class JobRoleRequirementUpdate(BaseModel):
    mandatory: bool | None = None
    note: str | None = None


class JobRoleRequirementRead(BaseModel):
    id: str
    job_role_id: str
    qualification_type_id: str
    mandatory: bool
    note: str | None = None
    qualification_name: str
    qualification_code: str

    model_config = ConfigDict(from_attributes=True)


class JobRoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    branch_id: str | None = None
    description: str | None = None
    active: bool = True


class JobRoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    branch_id: str | None = None
    description: str | None = None
    active: bool | None = None


class JobRoleRead(JobRoleCreate):
    id: str
    requirements: list[JobRoleRequirementRead] = []
    employee_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RequirementOverrideCreate(BaseModel):
    """A branch deviating from a group requirement.

    The reason is mandatory: an exception nobody can explain during an
    inspection is worse than an open gap.
    """

    branch_id: str
    requirement_id: str
    mode: Literal["excluded", "mandatory", "optional"]
    reason: str = Field(min_length=5)
    valid_until: date | None = None


class RequirementOverrideRevoke(BaseModel):
    reason: str = Field(min_length=5)
    # A revocation that bites immediately turns a branch red overnight, so it
    # names the day it applies from.
    effective_from: date | None = None


class RequirementOverrideRead(BaseModel):
    id: str
    branch_id: str
    branch_name: str
    requirement_id: str
    job_role_id: str
    job_role_name: str
    qualification_name: str
    mode: str
    reason: str
    valid_until: date | None = None
    created_by: str | None = None
    created_at: datetime
    acknowledged_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    revoked_effective_from: date | None = None
    active: bool


class ComplianceRuleCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    # The same vocabulary the records use: a rule that materialises into a
    # record the compliance view cannot categorise would be a rule nobody sees.
    category: ComplianceCategory
    control_type: ControlType
    recurrence: Recurrence = "yearly"
    legal_basis: str = Field(min_length=2, max_length=200)
    priority: Priority = "medium"
    risk_if_missing: str | None = None
    # None means group-wide.
    branch_id: str | None = None
    valid_from: date | None = None
    # Due date the branch instances start with.
    first_due_date: date


class ComplianceRuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    category: ComplianceCategory | None = None
    control_type: ControlType | None = None
    recurrence: Recurrence | None = None
    legal_basis: str | None = Field(default=None, min_length=2, max_length=200)
    priority: Priority | None = None
    risk_if_missing: str | None = None
    valid_from: date | None = None
    active: bool | None = None


class ComplianceRuleScopeChange(BaseModel):
    """Moves a rule between group-wide and branch-specific.

    `branch_id` None promotes it to group-wide; a branch id restricts it to
    that branch. `first_due_date` applies to the instances that newly come
    into being.
    """

    branch_id: str | None = None
    first_due_date: date | None = None
    # Instances in branches that lose the rule become rules of their own
    # instead of disappearing with their evidence.
    detach_dropped: bool = True


class ComplianceRuleRead(ComplianceRuleCreate):
    id: str
    first_due_date: date | None = None
    active: bool = True
    branch_name: str | None = None
    record_count: int = 0
    branch_ids: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class ScopeChangePreview(BaseModel):
    """What a scope change would do, before it does it."""

    creates_in: list[str] = []
    detaches_in: list[str] = []
    unchanged_in: list[str] = []
    newly_blocked_employees: int = 0


class BranchPortfolioRow(BaseModel):
    branch_id: str
    branch_name: str
    code: str | None = None
    headcount: int
    blocked: int
    limited: int
    overdue_compliance: int
    due_vehicles: int
    first_aiders_trained: int
    first_aiders_required: int
    open_exceptions: int
    new_exceptions: int
    state: str


class EmployeeBranchCreate(BaseModel):
    branch_id: str
    note: str | None = None


class EmployeeQualificationCreate(BaseModel):
    employee_id: str
    # Both are filled from the catalogue when `qualification_type_id` is given,
    # so selecting a catalogue entry is enough. Free-form entries still need a
    # title; that is enforced in the validator below rather than by the field,
    # which would otherwise make catalogue use needlessly wordy.
    title: str | None = Field(default=None, min_length=2, max_length=180)
    qualification_type: str | None = Field(default=None, min_length=2, max_length=80)
    qualification_type_id: str | None = None
    issued_on: date | None = None
    valid_until: date | None = None
    document_id: str | None = None
    reminder_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def require_a_title_or_a_catalogue_entry(self) -> "EmployeeQualificationCreate":
        if not self.qualification_type_id and not (self.title and self.qualification_type):
            raise ValueError(
                "Either qualification_type_id, or both title and qualification_type, must be given"
            )
        return self


class EmployeeQualificationRead(EmployeeQualificationCreate):
    id: str
    # Always set once stored: either given or taken from the catalogue.
    title: str
    qualification_type: str
    due_state: str
    overdue: bool

    model_config = ConfigDict(from_attributes=True)


class RequirementStateRead(BaseModel):
    """One line of the qualification matrix: what the function needs vs. what is on file."""

    override_mode: str | None = None
    override_reason: str | None = None
    qualification_type_id: str
    code: str
    name: str
    category: str
    mandatory: bool
    state: str
    valid_until: date | None = None
    issued_on: date | None = None
    qualification_id: str | None = None
    has_evidence: bool = False


class EmployeeCreate(BaseModel):
    branch_id: str
    full_name: str = Field(min_length=2, max_length=160)
    role: str = Field(min_length=2, max_length=120)
    job_role_id: str | None = None
    team: str | None = None
    start_date: date | None = None
    status: str = Field(default="active", max_length=20)
    exit_date: date | None = None
    first_aider: bool = False
    skills: list[str] = Field(default_factory=list)
    notes: str | None = None


class EmployeeRead(EmployeeCreate):
    id: str
    job_role_name: str | None = None
    qualifications: list[EmployeeQualificationRead] = []
    profile: EmployeeProfileRead | None = None
    # Derived, never stored: deployability and the next date to act on.
    requirements: list[RequirementStateRead] = []
    # Home branch plus deployments, and deployability in each of them.
    branch_ids: list[str] = []
    readiness_by_branch: dict[str, str] = {}
    readiness: str = "ready"
    due_state: str = "green"
    open_requirements: int = 0
    next_due_title: str | None = None
    next_due_date: date | None = None

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
    # Where the vehicle currently stands, when that is not its home branch.
    current_branch_id: str | None = None


class VehicleRelocate(BaseModel):
    """Moving a vehicle to another branch.

    Temporary by default: the home branch keeps it on its books while the
    receiving branch is responsible for HU, UVV and the driver. `permanent`
    hands it over for good, which is the rarer and the more consequential of
    the two - hence a flag rather than two fields the caller has to get right.
    """

    # None sends the vehicle back to its home branch.
    branch_id: str | None = None
    permanent: bool = False
    note: str | None = None


class VehicleRead(VehicleCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    # Derived, never stored.
    assigned_employee_name: str | None = None
    current_branch_name: str | None = None
    location_branch_id: str | None = None
    due_state: str = "green"
    next_due_title: str | None = None
    next_due_date: date | None = None
    driver_alert: str | None = None

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


class FirstAiderStatus(BaseModel):
    """Trained first aiders against the DGUV Vorschrift 1 minimum."""

    headcount: int
    trained: int
    required: int
    state: str


class CockpitResponse(BaseModel):
    metrics: list[CockpitMetric]
    overdue_compliance: list[ComplianceRecordRead]
    due_soon_compliance: list[ComplianceRecordRead]
    open_actions: list[ComplianceActionRead]
    expiring_qualifications: list[EmployeeQualificationRead]
    incidents: list[IncidentRead]
    reminders: list[ReminderRead]
    vehicle_due_count: int
    employee_due_count: int
    blocked_employees: int = 0
    limited_employees: int = 0
    first_aiders: FirstAiderStatus | None = None


class MatrixCell(BaseModel):
    qualification_type_id: str
    state: str
    mandatory: bool
    valid_until: date | None = None
    has_evidence: bool = False


class MatrixRow(BaseModel):
    employee_id: str
    full_name: str
    job_role_id: str | None = None
    job_role_name: str | None = None
    readiness: str
    cells: list[MatrixCell]


class QualificationMatrix(BaseModel):
    """Employees against qualification types - the deployability overview."""

    qualification_types: list[QualificationTypeRead]
    rows: list[MatrixRow]


class MonthOutlook(BaseModel):
    month: str
    label: str
    items: list[ReminderRead]


class ComplianceTemplateRead(BaseModel):
    key: str
    title: str
    category: str
    control_type: str
    recurrence: str
    legal_basis: str
    priority: str
    risk_if_missing: str


class AgentComplianceReviewRequest(BaseModel):
    compliance_record_id: str
    prompt: str | None = None


class AgentReviewResponse(BaseModel):
    id: str
    status: str
    response_payload: dict | None = None





# --------------------------------------------------------------------------
# Update payloads for resources that previously could not be corrected at all
# --------------------------------------------------------------------------


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    role: str | None = Field(default=None, min_length=2, max_length=120)
    job_role_id: str | None = None
    team: str | None = None
    start_date: date | None = None
    status: str | None = Field(default=None, max_length=20)
    exit_date: date | None = None
    first_aider: bool | None = None
    skills: list[str] | None = None
    notes: str | None = None


class EmployeeQualificationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    qualification_type: str | None = Field(default=None, min_length=2, max_length=80)
    qualification_type_id: str | None = None
    issued_on: date | None = None
    valid_until: date | None = None
    document_id: str | None = None
    reminder_days: int | None = Field(default=None, ge=1, le=365)


class VehicleUpdate(BaseModel):
    license_plate: str | None = Field(default=None, min_length=2, max_length=40)
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
    equipment: list[str] | None = None
    notes: str | None = None
    current_branch_id: str | None = None


class IncidentUpdate(BaseModel):
    type: Literal["incident", "near_miss", "deviation"] | None = None
    severity: Priority | None = None
    occurred_at: datetime | None = None
    project_id: str | None = None
    site_id: str | None = None
    summary: str | None = Field(default=None, min_length=3)
    immediate_action: str | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    closed_at: datetime | None = None
    owner_user_id: str | None = None


class BranchAssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    assessment_date: date | None = None
    team_structure: str | None = None
    customer_clusters: str | None = None
    service_portfolio: str | None = None
    project_types: str | None = None
    service_share: str | None = None
    main_problems: str | None = None
    management_ratings: dict[str, str] | None = None
    next_actions: list[dict[str, str]] | None = None
    notes: str | None = None


# --------------------------------------------------------------------------
# Sales and service
# --------------------------------------------------------------------------

AccountType = Literal["existing", "prospect", "target", "inactive"]
OfferStatus = Literal["lead", "qualified", "offer_sent", "negotiation", "won", "lost"]
StrategicRelevance = Literal["low", "medium", "high"]
ProjectStatus = Literal["planned", "active", "on_hold", "done", "cancelled"]
RiskState = Literal["green", "yellow", "red"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    branch_id: str
    account_type: AccountType = "existing"
    owner_user_id: str | None = None
    industry: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    branch_id: str | None = None
    account_type: AccountType | None = None
    owner_user_id: str | None = None
    industry: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class AccountRead(AccountCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityCreate(BaseModel):
    account_id: str
    title: str = Field(min_length=2, max_length=180)
    offer_status: OfferStatus = "lead"
    probability: int = Field(default=25, ge=0, le=100)
    expected_volume: float = Field(default=0, ge=0)
    next_step: str | None = None
    follow_up_date: date | None = None
    owner_user_id: str | None = None
    strategic_relevance: StrategicRelevance = "medium"


class OpportunityUpdate(BaseModel):
    account_id: str | None = None
    title: str | None = Field(default=None, min_length=2, max_length=180)
    offer_status: OfferStatus | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_volume: float | None = Field(default=None, ge=0)
    next_step: str | None = None
    follow_up_date: date | None = None
    owner_user_id: str | None = None
    strategic_relevance: StrategicRelevance | None = None


class OpportunityRead(OpportunityCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    account_id: str | None = None
    status: ProjectStatus = "active"
    risk_state: RiskState = "green"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    account_id: str | None = None
    status: ProjectStatus | None = None
    risk_state: RiskState | None = None


class ProjectRead(ProjectCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectSiteCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=180)
    address: str | None = Field(default=None, max_length=240)
    safety_notes: str | None = None


class ProjectSiteUpdate(BaseModel):
    project_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=180)
    address: str | None = Field(default=None, max_length=240)
    safety_notes: str | None = None


class ProjectSiteRead(ProjectSiteCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceContractCreate(BaseModel):
    account_id: str
    title: str = Field(min_length=2, max_length=180)
    sla_response_hours: int | None = Field(default=None, ge=1, le=8760)
    next_maintenance_at: date | None = None
    upsell_hint: str | None = None


class ServiceContractUpdate(BaseModel):
    account_id: str | None = None
    title: str | None = Field(default=None, min_length=2, max_length=180)
    sla_response_hours: int | None = Field(default=None, ge=1, le=8760)
    next_maintenance_at: date | None = None
    upsell_hint: str | None = None


class ServiceContractRead(ServiceContractCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceEventCreate(BaseModel):
    service_contract_id: str
    event_type: str = Field(min_length=2, max_length=80)
    scheduled_at: date | None = None
    resolved_at: date | None = None
    summary: str = Field(min_length=3)
    repeat_issue: bool = False


class ServiceEventUpdate(BaseModel):
    service_contract_id: str | None = None
    event_type: str | None = Field(default=None, min_length=2, max_length=80)
    scheduled_at: date | None = None
    resolved_at: date | None = None
    summary: str | None = Field(default=None, min_length=3)
    repeat_issue: bool | None = None


class ServiceEventRead(ServiceEventCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Documents, tasks, reviews
# --------------------------------------------------------------------------


class DocumentRead(BaseModel):
    id: str
    title: str
    file_name: str
    storage_path: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    uploaded_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    owner_user_id: str | None = None
    status: Literal["open", "in_progress", "blocked", "done", "cancelled"] = "open"
    due_date: date | None = None
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    owner_user_id: str | None = None
    status: Literal["open", "in_progress", "blocked", "done", "cancelled"] | None = None
    due_date: date | None = None
    source_type: str | None = Field(default=None, max_length=80)
    source_id: str | None = None


class TaskRead(TaskCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeReviewCreate(BaseModel):
    employee_id: str
    review_date: date
    summary: str = Field(min_length=3)
    development_goals: list[str] = Field(default_factory=list)


class EmployeeReviewUpdate(BaseModel):
    review_date: date | None = None
    summary: str | None = Field(default=None, min_length=3)
    development_goals: list[str] | None = None


class EmployeeReviewRead(EmployeeReviewCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Agent runs
# --------------------------------------------------------------------------


class AgentRunRead(BaseModel):
    id: str
    use_case: str
    source_entity_type: str
    source_entity_id: str
    request_payload: dict
    response_payload: dict | None = None
    status: str
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
