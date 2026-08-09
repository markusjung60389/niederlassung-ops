from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, ensure_ref, get_or_404, snapshot
from ..serializers import VEHICLE_LOAD_OPTIONS, vehicle_read

router = APIRouter(tags=["fleet"])

WriteDep = Annotated[Principal, Depends(requires(permissions.FLEET_WRITE))]
read_dependency = Depends(requires(permissions.FLEET_READ))


@router.get("/api/vehicles", response_model=list[schemas.VehicleRead], dependencies=[read_dependency])
def list_vehicles(
    branch_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[schemas.VehicleRead]:
    query = (
        select(models.Vehicle)
        .options(*VEHICLE_LOAD_OPTIONS)
        .order_by(models.Vehicle.license_plate.asc())
    )
    if branch_id:
        query = query.where(models.Vehicle.branch_id == branch_id)
    return [vehicle_read(vehicle) for vehicle in db.scalars(query.limit(limit)).all()]


@router.post("/api/vehicles", response_model=schemas.VehicleRead)
def create_vehicle(
    payload: schemas.VehicleCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.VehicleRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.Employee, payload.assigned_employee_id, "assigned_employee_id")
    vehicle = models.Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.flush()
    audit(db, "vehicle", vehicle.id, "created", payload.model_dump(mode="json"), principal)
    db.commit()
    db.refresh(vehicle)
    return vehicle_read(vehicle)


@router.get(
    "/api/vehicles/{vehicle_id}", response_model=schemas.VehicleRead, dependencies=[read_dependency]
)
def get_vehicle(vehicle_id: str, db: Session = Depends(get_db)) -> schemas.VehicleRead:
    return vehicle_read(get_or_404(db, models.Vehicle, vehicle_id, "Vehicle"))


@router.patch("/api/vehicles/{vehicle_id}", response_model=schemas.VehicleRead)
def update_vehicle(
    vehicle_id: str,
    payload: schemas.VehicleUpdate,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.VehicleRead:
    vehicle = get_or_404(db, models.Vehicle, vehicle_id, "Vehicle")
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.Employee, changes.get("assigned_employee_id"), "assigned_employee_id")
    before = {field: getattr(vehicle, field) for field in changes}
    for field, value in changes.items():
        setattr(vehicle, field, value)
    audit(db, "vehicle", vehicle_id, "updated", {"before": before, "after": changes}, principal)
    db.commit()
    db.refresh(vehicle)
    return vehicle_read(vehicle)


@router.delete("/api/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    vehicle = get_or_404(db, models.Vehicle, vehicle_id, "Vehicle")
    audit(db, "vehicle", vehicle_id, "deleted", snapshot(vehicle), principal)
    db.delete(vehicle)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
