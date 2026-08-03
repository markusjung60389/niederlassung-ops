import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import get_or_404
from ..domain import now_utc
from ..hermes import HermesClient
from ..serializers import load_record

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])

RunDep = Annotated[Principal, Depends(requires(permissions.AGENT_RUN))]


@router.post("/api/agent/compliance-review", response_model=schemas.AgentReviewResponse)
async def agent_compliance_review(
    payload: schemas.AgentComplianceReviewRequest,
    principal: RunDep,
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
    run.completed_at = now_utc()
    db.commit()
    return schemas.AgentReviewResponse(id=run.id, status=run.status, response_payload=run.response_payload)


@router.get(
    "/api/agent/runs",
    response_model=list[schemas.AgentRunRead],
    dependencies=[Depends(requires(permissions.AGENT_RUN))],
)
def list_agent_runs(
    source_entity_id: str | None = None,
    use_case: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: Session = Depends(get_db),
) -> list[models.AgentRun]:
    """Previously every review result was lost as soon as the response was sent."""
    query = select(models.AgentRun).order_by(models.AgentRun.created_at.desc())
    if source_entity_id:
        query = query.where(models.AgentRun.source_entity_id == source_entity_id)
    if use_case:
        query = query.where(models.AgentRun.use_case == use_case)
    return db.scalars(query.limit(limit)).all()


@router.get(
    "/api/agent/runs/{run_id}",
    response_model=schemas.AgentRunRead,
    dependencies=[Depends(requires(permissions.AGENT_RUN))],
)
def get_agent_run(run_id: str, db: Session = Depends(get_db)) -> models.AgentRun:
    return get_or_404(db, models.AgentRun, run_id, "Agent run")
