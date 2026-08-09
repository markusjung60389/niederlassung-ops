"""Compliance rules: the obligation, separate from each branch's work on it.

A rule ("we instruct annually", "the ladder inspection is due yearly") is the
specification. Its instance in a branch is a compliance record with an owner, a
due date and evidence. Keeping the two apart is what makes a rule promotable:
the same wording can be declared for one branch today and for the whole group
tomorrow without anyone re-typing it four times.

The scope change is the part worth reading. Demoting a group-wide rule to a
single branch must not make the other three branches' work disappear - their
instances carry evidence, actions and an audit trail. They are detached into
rules of their own instead, so nothing is lost and each branch keeps working.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, ensure_ref, get_or_404, snapshot
from ..domain import today_local
from ..routers.catalog_routes import guard_rule_scope, scope_condition

router = APIRouter(tags=["compliance-rules"])

WriteDep = Annotated[Principal, Depends(requires(permissions.COMPLIANCE_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.RULE_READ))]

# How far ahead of the due date a branch is expected to have looked at it.
REVIEW_LEAD_DAYS = 14

# Fields that describe the obligation. They live on the rule and are pushed
# down to the instances, so a corrected legal basis reaches every branch.
INHERITED_FIELDS = (
    "title",
    "category",
    "legal_basis",
    "control_type",
    "recurrence",
    "priority",
    "risk_if_missing",
)


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _rule_read(rule: models.ComplianceRule) -> schemas.ComplianceRuleRead:
    records = list(rule.records)
    return schemas.ComplianceRuleRead(
        id=rule.id,
        title=rule.title,
        category=rule.category,
        control_type=rule.control_type,
        recurrence=rule.recurrence,
        legal_basis=rule.legal_basis,
        priority=rule.priority,
        risk_if_missing=rule.risk_if_missing,
        branch_id=rule.branch_id,
        branch_name=rule.branch.name if rule.branch else None,
        valid_from=rule.valid_from,
        # Not stored on the rule: the earliest instance is what the rule
        # actually started the branches off with.
        first_due_date=min((item.due_date for item in records), default=None),
        active=rule.active,
        record_count=len(records),
        branch_ids=sorted({item.branch_id for item in records}),
    )


def _load_rule(db: Session, rule_id: str) -> models.ComplianceRule:
    rule = db.scalar(
        select(models.ComplianceRule)
        .where(models.ComplianceRule.id == rule_id)
        .options(selectinload(models.ComplianceRule.records))
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance rule not found")
    return rule


def _target_branches(db: Session, principal: Principal, branch_id: str | None) -> list[models.Branch]:
    """The branches a rule with this scope applies to.

    Group-wide means every active branch, including the ones the caller cannot
    see - that is precisely why creating one needs rule:write.
    """
    if branch_id is not None:
        return [get_or_404(db, models.Branch, branch_id, "Branch")]
    return list(
        db.scalars(
            select(models.Branch)
            .where(models.Branch.active.is_(True))
            .order_by(models.Branch.name.asc())
        ).all()
    )


@router.get("/api/compliance-rules", response_model=list[schemas.ComplianceRuleRead])
def list_compliance_rules(
    principal: ReadDep,
    branch_id: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
) -> list[schemas.ComplianceRuleRead]:
    """Group-wide rules plus whatever the selected branch declared for itself."""
    query = select(models.ComplianceRule).options(selectinload(models.ComplianceRule.records))
    if not include_inactive:
        query = query.where(models.ComplianceRule.active.is_(True))
    query = query.where(
        or_(
            models.ComplianceRule.branch_id.is_(None),
            scope_condition(models.ComplianceRule.branch_id, principal, branch_id),
        )
    )
    rules = db.scalars(query.order_by(models.ComplianceRule.title.asc())).all()
    return [_rule_read(rule) for rule in rules]


@router.get("/api/compliance-rules/{rule_id}", response_model=schemas.ComplianceRuleRead)
def get_compliance_rule(
    rule_id: str, principal: ReadDep, db: Session = Depends(get_db)
) -> schemas.ComplianceRuleRead:
    rule = _load_rule(db, rule_id)
    if rule.branch_id is not None and not principal.may_see(rule.branch_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance rule not found")
    return _rule_read(rule)


# --------------------------------------------------------------------------
# Materialisation
# --------------------------------------------------------------------------


def _materialise(
    db: Session,
    rule: models.ComplianceRule,
    branches: list[models.Branch],
    *,
    due_date: date,
    principal: Principal,
) -> list[models.ComplianceRecord]:
    """Gives every listed branch its own instance of the rule.

    Idempotent: a branch that already has one keeps it, so re-running a scope
    change never duplicates a record or resets a due date somebody worked to.
    """
    existing = {record.branch_id for record in rule.records}
    created: list[models.ComplianceRecord] = []
    for branch in branches:
        if branch.id in existing:
            continue
        record = models.ComplianceRecord(
            title=rule.title,
            category=rule.category,
            branch_id=branch.id,
            rule_id=rule.id,
            scope_type="branch",
            status="open",
            priority=rule.priority,
            # The branch manager owns their branch's instance; without one the
            # rule's author keeps it rather than the record having no owner.
            owner_user_id=branch.manager_user_id or principal.user_id,
            legal_basis=rule.legal_basis,
            control_type=rule.control_type,
            due_date=due_date,
            review_date=due_date - timedelta(days=REVIEW_LEAD_DAYS),
            risk_if_missing=rule.risk_if_missing,
            recurrence=rule.recurrence,
            tags=[],
        )
        db.add(record)
        created.append(record)
    if created:
        db.flush()
    return created


@router.post("/api/compliance-rules", response_model=schemas.ComplianceRuleRead, status_code=201)
def create_compliance_rule(
    payload: schemas.ComplianceRuleCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.ComplianceRuleRead:
    guard_rule_scope(principal, payload.branch_id)
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    branches = _target_branches(db, principal, payload.branch_id)

    data = payload.model_dump()
    first_due_date = data.pop("first_due_date")
    rule = models.ComplianceRule(**data, created_by=principal.user_id)
    db.add(rule)
    db.flush()

    created = _materialise(db, rule, branches, due_date=first_due_date, principal=principal)
    audit(
        db,
        "compliance_rule",
        rule.id,
        "created",
        {**payload.model_dump(mode="json"), "records_created": len(created)},
        principal,
    )
    db.commit()
    return _rule_read(_load_rule(db, rule.id))


@router.patch("/api/compliance-rules/{rule_id}", response_model=schemas.ComplianceRuleRead)
def update_compliance_rule(
    rule_id: str,
    payload: schemas.ComplianceRuleUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.ComplianceRuleRead:
    """Edits the obligation and pushes the wording down to the instances.

    Due dates, owners and evidence stay where they are - those belong to the
    branch, not to the rule.
    """
    rule = _load_rule(db, rule_id)
    guard_rule_scope(principal, rule.branch_id)
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(rule, field) for field in changes}
    for field, value in changes.items():
        setattr(rule, field, value)

    inherited = {field: value for field, value in changes.items() if field in INHERITED_FIELDS}
    if inherited:
        for record in rule.records:
            for field, value in inherited.items():
                setattr(record, field, value)

    audit(
        db,
        "compliance_rule",
        rule_id,
        "updated",
        {"before": before, "after": changes, "records_updated": len(rule.records) if inherited else 0},
        principal,
    )
    db.commit()
    return _rule_read(_load_rule(db, rule_id))


@router.delete("/api/compliance-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compliance_rule(
    rule_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    """Removes the specification, never the branches' work on it.

    The instances stay behind as standalone records with their evidence and
    actions; only the link to the rule goes.
    """
    rule = _load_rule(db, rule_id)
    guard_rule_scope(principal, rule.branch_id)
    detached = [record.id for record in rule.records]
    for record in rule.records:
        record.rule_id = None
    audit(
        db,
        "compliance_rule",
        rule_id,
        "deleted",
        {**snapshot(rule), "records_detached": detached},
        principal,
    )
    db.flush()
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Scope changes
# --------------------------------------------------------------------------


def _scope_plan(
    db: Session, rule: models.ComplianceRule, principal: Principal, branch_id: str | None
) -> tuple[list[models.Branch], list[models.ComplianceRecord], list[str]]:
    """(branches that get an instance, instances that lose the rule, unchanged)."""
    targets = _target_branches(db, principal, branch_id)
    target_ids = {branch.id for branch in targets}
    held = {record.branch_id for record in rule.records}
    creates = [branch for branch in targets if branch.id not in held]
    detaches = [record for record in rule.records if record.branch_id not in target_ids]
    unchanged = sorted(held & target_ids)
    return creates, detaches, unchanged


def _branch_names(db: Session, branch_ids: list[str]) -> list[str]:
    if not branch_ids:
        return []
    rows = db.scalars(select(models.Branch).where(models.Branch.id.in_(branch_ids))).all()
    names = {branch.id: branch.name for branch in rows}
    return [names.get(branch_id, branch_id) for branch_id in branch_ids]


@router.post("/api/compliance-rules/{rule_id}/scope-preview", response_model=schemas.ScopeChangePreview)
def preview_scope_change(
    rule_id: str,
    payload: schemas.ComplianceRuleScopeChange,
    principal: ReadDep,
    db: Session = Depends(get_db),
) -> schemas.ScopeChangePreview:
    """What the change would do, in branch names, before it does it."""
    rule = _load_rule(db, rule_id)
    creates, detaches, unchanged = _scope_plan(db, rule, principal, payload.branch_id)
    return schemas.ScopeChangePreview(
        creates_in=[branch.name for branch in creates],
        detaches_in=_branch_names(db, [record.branch_id for record in detaches]),
        unchanged_in=_branch_names(db, unchanged),
    )


@router.post("/api/compliance-rules/{rule_id}/scope", response_model=schemas.ComplianceRuleRead)
def change_scope(
    rule_id: str,
    payload: schemas.ComplianceRuleScopeChange,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.ComplianceRuleRead:
    """Promotes a branch rule to the group, or restricts a group rule to one branch.

    Both directions need rule:write on the side that is group-wide: promoting
    hands work to branches the caller does not run, demoting takes a rule away
    from them.
    """
    rule = _load_rule(db, rule_id)
    guard_rule_scope(principal, rule.branch_id)
    guard_rule_scope(principal, payload.branch_id)
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    if payload.branch_id == rule.branch_id:
        raise HTTPException(status_code=400, detail="The rule already has this scope")

    creates, detaches, unchanged = _scope_plan(db, rule, principal, payload.branch_id)
    previous_scope = rule.branch_id
    rule.branch_id = payload.branch_id

    detached: list[str] = []
    for record in detaches:
        if payload.detach_dropped:
            # The branch keeps working on it under a rule of its own; the
            # record, its evidence and its history stay untouched.
            local = models.ComplianceRule(
                title=rule.title,
                category=rule.category,
                branch_id=record.branch_id,
                control_type=rule.control_type,
                recurrence=rule.recurrence,
                legal_basis=rule.legal_basis,
                priority=rule.priority,
                risk_if_missing=rule.risk_if_missing,
                valid_from=rule.valid_from,
                created_by=principal.user_id,
            )
            db.add(local)
            db.flush()
            record.rule_id = local.id
            detached.append(local.id)
        else:
            record.rule_id = None

    due_date = payload.first_due_date or today_local() + timedelta(days=30)
    created = _materialise(db, rule, creates, due_date=due_date, principal=principal)
    audit(
        db,
        "compliance_rule",
        rule_id,
        "scope_changed",
        {
            "before": previous_scope,
            "after": payload.branch_id,
            "records_created": [record.branch_id for record in created],
            "records_detached": [record.branch_id for record in detaches],
            "detached_as_local_rules": detached,
            "unchanged": unchanged,
        },
        principal,
    )
    db.commit()
    return _rule_read(_load_rule(db, rule_id))


@router.post("/api/compliance-rules/{rule_id}/materialise", response_model=schemas.ComplianceRuleRead)
def materialise_missing(
    rule_id: str,
    principal: WriteDep,
    first_due_date: Annotated[date | None, Query()] = None,
    db: Session = Depends(get_db),
) -> schemas.ComplianceRuleRead:
    """Gives branches that have no instance yet one.

    Needed after a branch is opened: a group-wide rule declared last year
    otherwise silently skips it.
    """
    rule = _load_rule(db, rule_id)
    guard_rule_scope(principal, rule.branch_id)
    branches = _target_branches(db, principal, rule.branch_id)
    due_date = first_due_date or today_local() + timedelta(days=30)
    created = _materialise(db, rule, branches, due_date=due_date, principal=principal)
    if created:
        audit(
            db,
            "compliance_rule",
            rule_id,
            "materialised",
            {"records_created": [record.branch_id for record in created]},
            principal,
        )
    db.commit()
    return _rule_read(_load_rule(db, rule_id))
