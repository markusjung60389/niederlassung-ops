from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, ensure_ref, get_or_404, snapshot

router = APIRouter(tags=["incidents"])

WriteDep = Annotated[Principal, Depends(requires(permissions.INCIDENT_WRITE))]
read_dependency = Depends(requires(permissions.INCIDENT_READ))


@router.get("/api/incidents", response_model=list[schemas.IncidentRead], dependencies=[read_dependency])
def list_incidents(
    branch_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[models.Incident]:
    query = select(models.Incident).order_by(models.Incident.occurred_at.desc())
    if branch_id:
        query = query.where(models.Incident.branch_id == branch_id)
    return db.scalars(query.limit(limit)).all()


@router.post("/api/incidents", response_model=schemas.IncidentRead)
def create_incident(
    payload: schemas.IncidentCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> models.Incident:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.User, payload.owner_user_id, "owner_user_id")
    ensure_ref(db, models.Project, payload.project_id, "project_id")
    ensure_ref(db, models.ProjectSite, payload.site_id, "site_id")
    incident = models.Incident(**payload.model_dump())
    db.add(incident)
    db.flush()
    audit(db, "incident", incident.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(incident)
    return incident


@router.get(
    "/api/incidents/{incident_id}", response_model=schemas.IncidentRead, dependencies=[read_dependency]
)
def get_incident(incident_id: str, db: Session = Depends(get_db)) -> models.Incident:
    return get_or_404(db, models.Incident, incident_id, "Incident")


@router.patch("/api/incidents/{incident_id}", response_model=schemas.IncidentRead)
def update_incident(
    incident_id: str,
    payload: schemas.IncidentUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> models.Incident:
    incident = get_or_404(db, models.Incident, incident_id, "Incident")
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.User, changes.get("owner_user_id"), "owner_user_id")
    ensure_ref(db, models.Project, changes.get("project_id"), "project_id")
    ensure_ref(db, models.ProjectSite, changes.get("site_id"), "site_id")
    before = {field: getattr(incident, field) for field in changes}
    for field, value in changes.items():
        setattr(incident, field, value)
    audit(db, "incident", incident_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    db.refresh(incident)
    return incident


@router.delete("/api/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(incident_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    incident = get_or_404(db, models.Incident, incident_id, "Incident")
    audit(db, "incident", incident_id, "deleted", snapshot(incident), principal)
    db.delete(incident)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
