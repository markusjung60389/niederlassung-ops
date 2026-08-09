from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires
from ..database import get_db
from ..deps import audit, branch_filter, ensure_branch_access, ensure_ref, get_or_404, snapshot
from ..serializers import VEHICLE_LOAD_OPTIONS, vehicle_read

router = APIRouter(tags=["fleet"])

WriteDep = Annotated[Principal, Depends(requires(permissions.FLEET_WRITE))]
ReadDep = Annotated[Principal, Depends(requires(permissions.FLEET_READ))]
read_dependency = Depends(requires(permissions.FLEET_READ))

# Where the vehicle actually is: on loan that is not its home branch.
LOCATION_BRANCH = func.coalesce(models.Vehicle.current_branch_id, models.Vehicle.branch_id)


@router.get("/api/vehicles", response_model=list[schemas.VehicleRead])
def list_vehicles(
    principal: ReadDep,
    branch_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    db: Session = Depends(get_db),
) -> list[schemas.VehicleRead]:
    """Vehicles standing in the selected branch.

    A vehicle on loan is due where it stands, so the list follows the current
    location rather than the home branch.
    """
    query = (
        select(models.Vehicle)
        .options(*VEHICLE_LOAD_OPTIONS)
        .order_by(models.Vehicle.license_plate.asc())
    )
    query = branch_filter(query, LOCATION_BRANCH, principal, branch_id)
    return [vehicle_read(vehicle) for vehicle in db.scalars(query.limit(limit)).all()]


@router.post("/api/vehicles", response_model=schemas.VehicleRead)
def create_vehicle(
    payload: schemas.VehicleCreate, principal: WriteDep, db: Session = Depends(get_db)
) -> schemas.VehicleRead:
    ensure_ref(db, models.Branch, payload.branch_id, "branch_id")
    ensure_ref(db, models.Branch, payload.current_branch_id, "current_branch_id")
    ensure_branch_access(principal, payload.branch_id)
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
    ensure_branch_access(principal, vehicle.location_branch_id)
    changes = payload.model_dump(exclude_unset=True)
    ensure_ref(db, models.Employee, changes.get("assigned_employee_id"), "assigned_employee_id")
    if "current_branch_id" in changes:
        ensure_ref(db, models.Branch, changes["current_branch_id"], "current_branch_id")
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
