"""Pay per employee, behind a permission and a second confirmation.

Three things guard this and they do different jobs:

* `salary:read` / `salary:write` - who may look at all. Held by no preset
  except the two wildcard roles; everybody else needs a role built for it.
* the step-up (`auth.requires_step_up`) - how sure we are it is really them,
  right now. A stolen laptop with an open session does not open this.
* the audit log - **every read is recorded**, not only every change. With pay
  data the question that gets asked afterwards is "who looked at this", and a
  log that only knows about writes cannot answer it.

The amounts themselves never enter the audit log: it is readable by anybody
with `audit:read`, and writing the figure there would hand it to exactly the
people this endpoint keeps it from.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, permissions, schemas
from ..auth import Principal, requires, requires_step_up
from ..database import get_db
from ..deps import audit, get_or_404

router = APIRouter(tags=["salary"])

ReadDep = Annotated[Principal, Depends(requires(permissions.SALARY_READ))]
WriteDep = Annotated[Principal, Depends(requires(permissions.SALARY_WRITE))]
step_up = Depends(requires_step_up)


def _employee(db: Session, employee_id: str, principal: Principal) -> models.Employee:
    employee = get_or_404(db, models.Employee, employee_id, "Employee")
    # Same rule as everywhere else: a branch outside the caller's scope does
    # not exist for them, and pay is the last place to make an exception.
    if not any(principal.may_see(item) for item in employee.assigned_branch_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


def _salary_read(salary: models.EmployeeSalary) -> schemas.EmployeeSalaryRead:
    return schemas.EmployeeSalaryRead(
        employee_id=salary.employee_id,
        amount=float(salary.amount),
        period=salary.period,
        hours_per_week=float(salary.hours_per_week) if salary.hours_per_week is not None else None,
        valid_from=salary.valid_from,
        note=salary.note,
        updated_by=salary.updated_by,
        updated_at=salary.updated_at,
    )


@router.get(
    "/api/employees/{employee_id}/salary",
    response_model=schemas.EmployeeSalaryRead,
    dependencies=[step_up],
)
def get_salary(
    employee_id: str, principal: ReadDep, db: Session = Depends(get_db)
) -> schemas.EmployeeSalaryRead:
    employee = _employee(db, employee_id, principal)
    salary = db.scalar(
        select(models.EmployeeSalary).where(models.EmployeeSalary.employee_id == employee_id)
    )
    if salary is None:
        raise HTTPException(status_code=404, detail="Fuer diese Person ist kein Entgelt hinterlegt.")

    # The read itself is the event worth recording here.
    audit(db, "employee_salary", employee_id, "viewed", {"employee": employee.full_name}, principal)
    db.commit()
    return _salary_read(salary)


@router.put(
    "/api/employees/{employee_id}/salary",
    response_model=schemas.EmployeeSalaryRead,
    dependencies=[step_up],
)
def set_salary(
    employee_id: str,
    payload: schemas.EmployeeSalaryWrite,
    principal: WriteDep,
    db: Session = Depends(get_db),
) -> schemas.EmployeeSalaryRead:
    employee = _employee(db, employee_id, principal)
    salary = db.scalar(
        select(models.EmployeeSalary).where(models.EmployeeSalary.employee_id == employee_id)
    )
    created = salary is None
    if salary is None:
        salary = models.EmployeeSalary(employee_id=employee_id, **payload.model_dump())
        db.add(salary)
    else:
        for field, value in payload.model_dump().items():
            setattr(salary, field, value)
    salary.updated_by = principal.user_id
    db.flush()

    audit(
        db,
        "employee_salary",
        employee_id,
        "created" if created else "updated",
        # No amount: the audit log has a wider readership than this endpoint.
        {"employee": employee.full_name, "period": salary.period, "valid_from": salary.valid_from},
        principal,
    )
    db.commit()
    db.refresh(salary)
    return _salary_read(salary)


@router.delete(
    "/api/employees/{employee_id}/salary",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[step_up],
)
def delete_salary(employee_id: str, principal: WriteDep, db: Session = Depends(get_db)) -> Response:
    employee = _employee(db, employee_id, principal)
    salary = db.scalar(
        select(models.EmployeeSalary).where(models.EmployeeSalary.employee_id == employee_id)
    )
    if salary is None:
        raise HTTPException(status_code=404, detail="Fuer diese Person ist kein Entgelt hinterlegt.")
    audit(db, "employee_salary", employee_id, "deleted", {"employee": employee.full_name}, principal)
    db.delete(salary)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
