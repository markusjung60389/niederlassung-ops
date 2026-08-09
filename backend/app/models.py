from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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
    # Short marker used in tight table cells and in the branch switcher.
    code: Mapped[str | None] = mapped_column(String(10), unique=True)
    location: Mapped[str | None] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    manager_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class Role(Base):
    """A named set of permissions.

    The presets are `system` roles: they are kept in sync with
    `permissions.ROLE_PRESETS` on every start, so a new permission reaches
    existing installations. Roles created in the user administration are not,
    and can be edited freely.
    """

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system: Mapped[bool] = mapped_column(default=False, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    # Microsoft Entra ID object id ("oid" claim). Empty until the account signs in via Azure AD.
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Set for the area manager: reads and writes reach every branch without an
    # entry in user_branches having to be maintained per branch.
    all_branches: Mapped[bool] = mapped_column(default=False, nullable=False)
    # --- Local password login (the emergency door beside Entra ID) --------
    # NULL for every account that signs in through Entra ID, which is the
    # normal case: no password, no password to leak.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(default=False, nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Raised on a password change or a deactivation: every session token issued
    # before then stops being accepted, without a session table to keep clean.
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    role_id: Mapped[str | None] = mapped_column(ForeignKey("roles.id"))
    role: Mapped[Role | None] = relationship(lazy="joined")
    branch_links: Mapped[list["UserBranch"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class UserBranch(Base, TimestampMixin):
    """Which branches an account may see and work in."""

    __tablename__ = "user_branches"
    __table_args__ = (UniqueConstraint("user_id", "branch_id", name="uq_user_branches_user_branch"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    user: Mapped[User] = relationship(back_populates="branch_links")
    branch: Mapped[Branch] = relationship(lazy="joined")


class QualificationType(Base, TimestampMixin):
    """Catalogue of the qualifications a branch tracks.

    The catalogue carries the rule (how long a certificate stays valid, how
    early to warn, whether a document has to back it up), so an individual
    qualification only has to carry the dates.
    """

    __tablename__ = "qualification_types"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    # NULL means the entry applies group-wide. A branch id restricts it to that
    # branch, which is the exception rather than the rule: figures are only
    # comparable across branches while the definitions are shared.
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    category: Mapped[str] = mapped_column(String(60), default="qualification", nullable=False)
    # None means the qualification does not expire (driving licence classes).
    validity_months: Mapped[int | None] = mapped_column(Integer)
    reminder_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    evidence_required: Mapped[bool] = mapped_column(default=True, nullable=False)
    legal_basis: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)


class JobRole(Base, TimestampMixin):
    """A function inside the branch: Projektleiter, Service-Techniker, Monteur.

    Deliberately not called `Role` - that name is taken by the permission role
    attached to `User`. Keeping them apart matters: one decides what somebody
    may click, the other what they are allowed to do on site.
    """

    __tablename__ = "job_roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    # NULL means group-wide, see QualificationType.branch_id.
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    requirements: Mapped[list["JobRoleRequirement"]] = relationship(
        back_populates="job_role", cascade="all, delete-orphan"
    )


class JobRoleRequirement(Base, TimestampMixin):
    """Which qualification a function requires, and whether it is mandatory."""

    __tablename__ = "job_role_requirements"
    __table_args__ = (
        UniqueConstraint(
            "job_role_id", "qualification_type_id", name="uq_job_role_requirements_role_type"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    job_role_id: Mapped[str] = mapped_column(ForeignKey("job_roles.id"), nullable=False, index=True)
    qualification_type_id: Mapped[str] = mapped_column(
        ForeignKey("qualification_types.id"), nullable=False, index=True
    )
    mandatory: Mapped[bool] = mapped_column(default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    job_role: Mapped[JobRole] = relationship(back_populates="requirements")
    qualification_type: Mapped[QualificationType] = relationship(lazy="joined")


class RequirementOverride(Base, TimestampMixin):
    """A branch deviating from a group requirement.

    Deliberately a row of its own rather than the silent absence of one: the
    reason, who set it and until when are exactly what an inspection asks
    about, and the area manager can only revoke what he can see.
    """

    __tablename__ = "requirement_overrides"
    __table_args__ = (
        UniqueConstraint("branch_id", "requirement_id", name="uq_requirement_overrides_branch_req"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("job_role_requirements.id"), nullable=False, index=True
    )
    # excluded: does not apply here. mandatory/optional: applies differently.
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # Seen by the area manager; drives the "new since" marker.
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A revocation that bites immediately would turn a branch red overnight, so
    # it names the date from which it applies.
    revoked_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(Text)
    revoked_effective_from: Mapped[date | None] = mapped_column(Date)
    requirement: Mapped[JobRoleRequirement] = relationship(lazy="joined")
    branch: Mapped[Branch] = relationship(lazy="joined")


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Free text kept from before the function catalogue existed. `job_role_id`
    # is the structured successor; `role` stays as the fallback label so no
    # existing entry loses its job title.
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    job_role_id: Mapped[str | None] = mapped_column(ForeignKey("job_roles.id"), index=True)
    team: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    # Departed staff must stay on record for the retention period, so they are
    # deactivated rather than deleted.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    exit_date: Mapped[date | None] = mapped_column(Date)
    first_aider: Mapped[bool] = mapped_column(default=False, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    branch: Mapped[Branch] = relationship()
    job_role: Mapped[JobRole | None] = relationship(lazy="joined")
    qualifications: Mapped[list["EmployeeQualification"]] = relationship(back_populates="employee")
    salary: Mapped["EmployeeSalary | None"] = relationship(
        back_populates="employee", uselist=False
    )
    profile: Mapped["EmployeeProfile | None"] = relationship(back_populates="employee", uselist=False)
    branch_links: Mapped[list["EmployeeBranch"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )

    @property
    def assigned_branch_ids(self) -> set[str]:
        """Home branch plus every branch the person is deployed to.

        The home branch counts implicitly, so a record that predates the
        deployment table behaves exactly as before.
        """
        return {self.branch_id} | {link.branch_id for link in self.branch_links}


class EmployeeBranch(Base, TimestampMixin):
    """A branch the employee is deployed to besides their home branch.

    Requirements add up across these: someone working in two branches has to
    satisfy both rule sets, otherwise an exception granted in one would become
    a loophole for working in the other.
    """

    __tablename__ = "employee_branches"
    __table_args__ = (
        UniqueConstraint("employee_id", "branch_id", name="uq_employee_branches_employee_branch"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    employee: Mapped["Employee"] = relationship(back_populates="branch_links")
    branch: Mapped[Branch] = relationship(lazy="joined")


class EmployeeSalary(Base, TimestampMixin):
    """Pay, deliberately in a table of its own.

    Not a column on `employee_profiles`: the profile is serialised into every
    employee response, and a field that must never travel by accident has no
    business in a payload that is built for something else. Its own table means
    its own endpoint, its own permission and its own audit trail.

    One row per employee - the current arrangement, not a history. What was
    paid last year belongs in the payroll system, which is also the system of
    record for everything here.
    """

    __tablename__ = "employee_salaries"
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_salaries_employee_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    # Numeric, not float: money that is off by a cent because of binary
    # rounding is money somebody has to explain.
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # "monthly" is the gross monthly salary, "hourly" the gross hourly rate.
    period: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    hours_per_week: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    employee: Mapped["Employee"] = relationship(back_populates="salary")


class EmployeeQualification(Base, TimestampMixin):
    __tablename__ = "employee_qualifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    # Free-text kind, kept for rows created before the catalogue.
    qualification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    qualification_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("qualification_types.id"), index=True
    )
    issued_on: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    reminder_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    employee: Mapped[Employee] = relationship(back_populates="qualifications")
    type_ref: Mapped[QualificationType | None] = relationship(lazy="joined")

class EmployeeProfile(Base, TimestampMixin):
    __tablename__ = "employee_profiles"
    # Named explicitly so migrations can address the constraint on PostgreSQL.
    __table_args__ = (UniqueConstraint("employee_id", name="uq_employee_profiles_employee_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False)
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
    # Home branch: who owns the vehicle and pays for its inspections.
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    # Where it currently stands, when that is not home. A vehicle is in one
    # place at a time, so this is a move rather than a second assignment.
    current_branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
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
    branch: Mapped[Branch] = relationship(foreign_keys=[branch_id])
    current_branch: Mapped[Branch | None] = relationship(foreign_keys=[current_branch_id], lazy="joined")
    assigned_employee: Mapped[Employee | None] = relationship()

    @property
    def location_branch_id(self) -> str:
        """The branch that has to act on this vehicle's dates today."""
        return self.current_branch_id or self.branch_id

class EmployeeReview(Base, TimestampMixin):
    __tablename__ = "employee_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    development_goals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    account_type: Mapped[str] = mapped_column(String(80), default="existing", nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    # Nullable so the column can be added to existing rows; required by the API.
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
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
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(80), default="active", nullable=False)
    risk_state: Mapped[str] = mapped_column(String(20), default="green", nullable=False)


class ProjectSite(Base, TimestampMixin):
    __tablename__ = "project_sites"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    address: Mapped[str | None] = mapped_column(String(240))
    safety_notes: Mapped[str | None] = mapped_column(Text)


class ServiceContract(Base, TimestampMixin):
    __tablename__ = "service_contracts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    sla_response_hours: Mapped[int | None] = mapped_column(Integer)
    next_maintenance_at: Mapped[date | None] = mapped_column(Date, index=True)
    upsell_hint: Mapped[str | None] = mapped_column(Text)


class ServiceEvent(Base, TimestampMixin):
    __tablename__ = "service_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    service_contract_id: Mapped[str] = mapped_column(ForeignKey("service_contracts.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scheduled_at: Mapped[date | None] = mapped_column(Date)
    resolved_at: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    repeat_issue: Mapped[bool] = mapped_column(default=False, nullable=False)


class ComplianceRule(Base, TimestampMixin):
    """The obligation itself, separate from the branch's work on it.

    "We instruct annually" holds for whoever it is declared for; the evidence
    for it belongs to one branch. Keeping both in one row worked while there
    was one branch and stops working the moment a rule is meant to apply to
    all of them.
    """

    __tablename__ = "compliance_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    # NULL means group-wide; a branch id restricts the rule to that branch.
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)
    control_type: Mapped[str] = mapped_column(String(40), nullable=False)
    recurrence: Mapped[str] = mapped_column(String(40), default="yearly", nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[str] = mapped_column(String(40), default="medium", nullable=False)
    risk_if_missing: Mapped[str | None] = mapped_column(Text)
    # Switching a rule on must not make four branches overdue overnight.
    valid_from: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    branch: Mapped[Branch | None] = relationship(lazy="joined")
    records: Mapped[list["ComplianceRecord"]] = relationship(back_populates="rule")


class ComplianceRecord(Base, TimestampMixin):
    __tablename__ = "compliance_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    # The rule this is the branch's instance of. Nullable so a record can exist
    # on its own, which is what every record looked like before rules existed.
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("compliance_rules.id"), index=True)
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
    rule: Mapped[ComplianceRule | None] = relationship(back_populates="records", lazy="joined")
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
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
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
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
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
