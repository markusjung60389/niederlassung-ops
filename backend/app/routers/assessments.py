from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, branch_filter, ensure_ref, get_or_404, snapshot
from ..serializers import assessment_read

router = APIRouter(tags=["assessments"])

WriteDep = Annotated[Principal, Depends(requires(permissions.ASSESSMENT_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.ASSESSMENT_READ))]
read_dependency = Depends(requires(permissions.ASSESSMENT_READ))


@router.get(
    "/api/branch-assessments",
    response_model=list[schemas.BranchAssessmentRead],
)
def list_branch_assessments(
    principal: ReadDep,
    branch_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[schemas.BranchAssessmentRead]:
    query = select(models.BranchAssessment).order_by(models.BranchAssessment.assessment_date.desc())
    query = branch_filter(query, models.BranchAssessment.branch_id, principal, branch_id)
    return [assessment_read(item) for item in db.scalars(query.limit(limit)).all()]


@router.post("/api/branch-assessments", response_model=schemas.BranchAssessmentRead)
def create_branch_assessment(
    payload: schemas.BranchAssessmentCreate, principal: WriteDep, db: Session = Depends(get_db)
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


@router.get(
    "/api/branch-assessments/{assessment_id}",
    response_model=schemas.BranchAssessmentRead,
    dependencies=[read_dependency],
)
def get_branch_assessment(assessment_id: str, db: Session = Depends(get_db)) -> schemas.BranchAssessmentRead:
    return assessment_read(get_or_404(db, models.BranchAssessment, assessment_id, "Assessment"))


@router.patch("/api/branch-assessments/{assessment_id}", response_model=schemas.BranchAssessmentRead)
def update_branch_assessment(
    assessment_id: str,
    payload: schemas.BranchAssessmentUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.BranchAssessmentRead:
    assessment = get_or_404(db, models.BranchAssessment, assessment_id, "Assessment")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(assessment, field) for field in changes}
    for field, value in changes.items():
        setattr(assessment, field, value)
    audit(
        db, "branch_assessment", assessment_id, "updated", {"before": before, "after": changes}, principal
    )
    db.commit()
    db.refresh(assessment)
    return assessment_read(assessment)


@router.delete("/api/branch-assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch_assessment(
    assessment_id: str, principal: WriteDep, db: Session = Depends(get_db)
) -> Response:
    assessment = get_or_404(db, models.BranchAssessment, assessment_id, "Assessment")
    audit(db, "branch_assessment", assessment_id, "deleted", snapshot(assessment), principal)
    db.delete(assessment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
