"""Derives deployability from function requirements and recorded qualifications.

The question a branch manager asks before every assignment is "may this person
work on that job tomorrow". It is answerable from data the system already
holds: the function says what is required, the qualifications say what is
there. This module is the single place that comparison happens, so the list,
the matrix and the cockpit cannot disagree.

Nothing here writes; every value is computed per request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import catalog, models
from .domain import today_local

# Per-requirement outcome, worst first. The order is the comparison order used
# to pick the state that drives an employee's traffic light.
STATE_MISSING = "missing"
STATE_EXPIRED = "expired"
STATE_UNDATED = "undated"
STATE_EXPIRING = "expiring"
STATE_EVIDENCE_MISSING = "evidence_missing"
STATE_OK = "ok"

STATE_ORDER = (
    STATE_MISSING,
    STATE_EXPIRED,
    STATE_UNDATED,
    STATE_EXPIRING,
    STATE_EVIDENCE_MISSING,
    STATE_OK,
)

# Overall deployability.
READY = "ready"
LIMITED = "limited"
BLOCKED = "blocked"

# A mandatory requirement in one of these states stops the assignment.
BLOCKING_STATES = frozenset({STATE_MISSING, STATE_EXPIRED, STATE_UNDATED})
# ... in one of these it still needs attention, but does not stop it.
LIMITING_STATES = frozenset({STATE_EXPIRING, STATE_EVIDENCE_MISSING})

TONE_BY_READINESS = {BLOCKED: "red", LIMITED: "yellow", READY: "green"}


@dataclass(frozen=True)
class RequirementState:
    qualification_type_id: str
    code: str
    name: str
    category: str
    mandatory: bool
    state: str
    valid_until: date | None
    issued_on: date | None
    qualification_id: str | None
    has_evidence: bool

    @property
    def open(self) -> bool:
        return self.state != STATE_OK


def _worst(states: list[str]) -> str:
    for candidate in STATE_ORDER:
        if candidate in states:
            return candidate
    return STATE_OK


def _newest(qualifications: list[models.EmployeeQualification]) -> models.EmployeeQualification:
    """The entry that counts: the one that stays valid longest.

    Refresher courses are added as new rows rather than overwriting the old
    one, so an employee accumulates several entries per type and only the
    latest says whether they are covered today.
    """
    return max(
        qualifications,
        key=lambda item: (
            item.valid_until or date.min,
            item.issued_on or date.min,
            item.created_at,
        ),
    )


def requirement_state(
    requirement: models.JobRoleRequirement,
    qualifications: list[models.EmployeeQualification],
    *,
    today: date | None = None,
) -> RequirementState:
    current = today or today_local()
    kind = requirement.qualification_type
    matching = [item for item in qualifications if item.qualification_type_id == kind.id]

    if not matching:
        return RequirementState(
            qualification_type_id=kind.id,
            code=kind.code,
            name=kind.name,
            category=kind.category,
            mandatory=requirement.mandatory,
            state=STATE_MISSING,
            valid_until=None,
            issued_on=None,
            qualification_id=None,
            has_evidence=False,
        )

    entry = _newest(matching)
    has_evidence = entry.document_id is not None
    window = kind.reminder_days or entry.reminder_days

    if kind.validity_months is not None and entry.valid_until is None:
        state = STATE_UNDATED
    elif entry.valid_until is not None and entry.valid_until < current:
        state = STATE_EXPIRED
    elif entry.valid_until is not None and entry.valid_until <= current + timedelta(days=window):
        state = STATE_EXPIRING
    elif kind.evidence_required and not has_evidence:
        # A valid date nobody can prove is not defensible in an inspection.
        state = STATE_EVIDENCE_MISSING
    else:
        state = STATE_OK

    return RequirementState(
        qualification_type_id=kind.id,
        code=kind.code,
        name=kind.name,
        category=kind.category,
        mandatory=requirement.mandatory,
        state=state,
        valid_until=entry.valid_until,
        issued_on=entry.issued_on,
        qualification_id=entry.id,
        has_evidence=has_evidence,
    )


def requirement_states(
    employee: models.Employee, *, today: date | None = None
) -> list[RequirementState]:
    if employee.job_role is None:
        return []
    qualifications = list(employee.qualifications)
    states = [
        requirement_state(requirement, qualifications, today=today)
        for requirement in employee.job_role.requirements
    ]
    # Mandatory first, then by severity, then alphabetically - the order a
    # manager reads them in.
    return sorted(
        states,
        key=lambda item: (not item.mandatory, STATE_ORDER.index(item.state), item.name),
    )


def readiness_of(states: list[RequirementState]) -> str:
    mandatory = [item.state for item in states if item.mandatory]
    if any(state in BLOCKING_STATES for state in mandatory):
        return BLOCKED
    if any(state in LIMITING_STATES for state in mandatory):
        return LIMITED
    return READY


@dataclass(frozen=True)
class DueItem:
    title: str
    due_date: date | None
    tone: str


def _tone(due: date | None, window: int, current: date) -> str:
    if due is None:
        return "yellow"
    if due < current:
        return "red"
    if due <= current + timedelta(days=window):
        return "yellow"
    return "green"


def employee_due_items(
    employee: models.Employee, states: list[RequirementState], *, today: date | None = None
) -> list[DueItem]:
    """Everything with a date that the manager has to act on, worst first.

    Requirement dates come from the qualifications; contract, probation and
    residence permit stay in the profile because they describe the person, not
    a qualification derived from the function.
    """
    current = today or today_local()
    items: list[DueItem] = []

    for state in states:
        if state.state == STATE_OK:
            continue
        if state.state == STATE_MISSING:
            # An optional qualification nobody has is not a gap, it is simply
            # not applicable. Flagging it would leave every employee amber
            # forever and make the traffic light meaningless.
            if not state.mandatory:
                continue
            items.append(DueItem(f"{state.name} fehlt", None, "red"))
        elif state.state == STATE_UNDATED:
            items.append(DueItem(f"{state.name} ohne Gueltigkeitsdatum", None, "yellow"))
        elif state.state == STATE_EVIDENCE_MISSING:
            items.append(DueItem(f"{state.name}: Nachweis fehlt", state.valid_until, "yellow"))
        else:
            items.append(
                DueItem(
                    state.name,
                    state.valid_until,
                    "red" if state.state == STATE_EXPIRED else "yellow",
                )
            )

    profile = employee.profile
    if profile:
        for title, due in (
            ("Arbeitsvertrag befristet bis", profile.contract_end),
            ("Probezeit endet", profile.probation_until),
            ("Aufenthalts-/Arbeitserlaubnis", profile.residence_permit_valid_until),
        ):
            if due is None:
                continue
            tone = _tone(due, 60, current)
            if tone != "green":
                items.append(DueItem(title, due, tone))

    order = {"red": 0, "yellow": 1, "green": 2}
    return sorted(items, key=lambda item: (order[item.tone], item.due_date or date.max))


VEHICLE_CHECKS: tuple[tuple[str, str], ...] = (
    ("hu_due_date", "Hauptuntersuchung"),
    ("uvv_next_check", "UVV-Pruefung"),
    ("service_due_date", "Service/Wartung"),
    ("tire_change_due_date", "Reifenwechsel"),
    ("insurance_valid_until", "Versicherung"),
)


def vehicle_due_items(vehicle: models.Vehicle, *, today: date | None = None) -> list[DueItem]:
    current = today or today_local()
    items = []
    for attribute, title in VEHICLE_CHECKS:
        due = getattr(vehicle, attribute)
        if due is None:
            continue
        tone = _tone(due, 30, current)
        if tone != "green":
            items.append(DueItem(title, due, tone))
    order = {"red": 0, "yellow": 1, "green": 2}
    return sorted(items, key=lambda item: (order[item.tone], item.due_date or date.max))


def driver_licence_alert(vehicle: models.Vehicle, *, today: date | None = None) -> str | None:
    """Warns when the assigned driver's licence check has lapsed.

    Both facts are already on screen but nobody joins them by hand, and an
    overdue check on an assigned vehicle is exactly the case that turns into
    keeper liability.
    """
    employee = vehicle.assigned_employee
    if employee is None:
        return None
    current = today or today_local()
    checks = [
        item
        for item in employee.qualifications
        if item.type_ref is not None and item.type_ref.code == catalog.CODE_DRIVER_LICENCE_CHECK
    ]
    if not checks:
        return f"{employee.full_name}: keine Fuehrerscheinkontrolle erfasst"
    newest = _newest(checks)
    if newest.valid_until is None:
        return f"{employee.full_name}: Fuehrerscheinkontrolle ohne Datum"
    if newest.valid_until < current:
        overdue = (current - newest.valid_until).days
        return f"{employee.full_name}: Fuehrerscheinkontrolle seit {overdue} Tagen ueberfaellig"
    return None


def first_aider_target(headcount: int) -> int:
    """Minimum number of trained first aiders per DGUV Vorschrift 1 Paragraf 26.

    Up to two employees none is prescribed; beyond that ten percent, rounded
    up, and never fewer than one.
    """
    if headcount <= 2:
        return 0
    return max(1, -(-headcount // 10))
