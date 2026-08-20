from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, branch_filter, ensure_branch_access, ensure_ref, ensure_visible, get_or_404, snapshot

router = APIRouter(tags=["incidents"])

WriteDep = Annotated[Principal, Depends(requires(permissions.INCIDENT_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.INCIDENT_READ))]


def _visible_incident(db: Session, principal: Principal, incident_id: str) -> models.Incident:
    incident = get_or_404(db, models.Incident, incident_id, "Incident")
    ensure_visible(principal, [incident.branch_id], "Incident")
    return incident


@router.get("/api/incidents", response_model=list[schemas.IncidentRead])
def list_incidents(
    principal: ReadDep,
    branch_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[models.Incident]:
    query = select(models.Incident).order_by(models.Incident.occurred_at.desc())
    query = branch_filter(query, models.Incident.branch_id, principal, branch_id)
    return db.scalars(query.limit(limit)).all()


@router.post("/api/incidents", response_model=schemas.IncidentRead)
def create_incident(
    payload: schemas.IncidentCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> models.Incident:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_branch_access(principal, payload.branch_id)
    ensure_ref(db, models.User, payload.owner_user_id, "owner_user_id")
    ensure_ref(db, models.Project, payload.project_id, "project_id")
    ensure_ref(db, models.ProjectSite, payload.site_id, "site_id")
    incident = models.Incident(**payload.model_dump())
    db.add(incident)
    db.flush()
    audit(
        db,
        "incident",
        incident.id,
        "created",
        payload.model_dump(mode="json"),
        principal,
        branch_id=incident.branch_id,
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/api/incidents/{incident_id}", response_model=schemas.IncidentRead)
def get_incident(incident_id: str, principal: ReadDep, db: Session = Depends(get_db)) -> models.Incident:
    return _visible_incident(db, principal, incident_id)


@router.patch("/api/incidents/{incident_id}", response_model=schemas.IncidentRead)
def update_incident(
    incident_id: str,
    payload: schemas.IncidentUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> models.Incident:
    incident = _visible_incident(db, principal, incident_id)
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.User, changes.get("owner_user_id"), "owner_user_id")
    ensure_ref(db, models.Project, changes.get("project_id"), "project_id")
    ensure_ref(db, models.ProjectSite, changes.get("site_id"), "site_id")
    before = {field: getattr(incident, field) for field in changes}
    for field, value in changes.items():
        setattr(incident, field, value)
    audit(
        db,
        "incident",
        incident_id,
        "updated",
        {"before": before, "after": changes},
        principal,
        branch_id=incident.branch_id,
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.delete("/api/incidents/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(incident_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    incident = _visible_incident(db, principal, incident_id)
    audit(db, "incident", incident_id, "deleted", snapshot(incident), principal, branch_id=incident.branch_id)
    db.delete(incident)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
