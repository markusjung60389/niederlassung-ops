"""Generic CRUD registration.

Nine tables had no API at all. Registering them through one factory keeps the
behaviour identical everywhere - referential checks on write, an audit entry per
change, a child guard and a full snapshot on delete - instead of forty-odd
hand-written handlers that would drift apart.

Resources with real behaviour (compliance records, employees, evidence) keep
their own handlers.
"""

# NOTE: no `from __future__ import annotations` here. The handlers below take
# their request model from the Crud instance, and FastAPI has to see the real
# class at decoration time; stringified annotations would be read as query
# parameters instead.
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import Principal, requires
from .database import get_db
from .deps import audit, ensure_refs, ensure_visible, get_or_404, guard_children, snapshot


@dataclass
class Crud:
    model: type
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    read_schema: type[BaseModel]
    entity_type: str
    label: str
    read_permission: str
    write_permission: str
    # field name -> referenced model, checked on create and update
    references: dict[str, type] = field(default_factory=dict)
    # query parameter -> column name
    filters: dict[str, str] = field(default_factory=dict)
    order_by: str = "created_at"
    order_desc: bool = False
    # (model, foreign key attribute, label) that block a delete
    children: list[tuple[type, str, str]] = field(default_factory=list)
    # Resolves an instance to the branch id(s) it belongs to, for entities
    # that carry branch-scoped data. Absent entirely (None) or returning None
    # for a given instance both mean group-wide: visible to everyone with the
    # permission, same as before this existed.
    branch_of: Callable[[Any], list[str] | None] | None = None


def register(router: APIRouter, path: str, crud: Crud) -> None:
    model = crud.model
    read_dependency = requires(crud.read_permission)
    write_dependency = requires(crud.write_permission)

    def _visible(principal: Principal, instance: Any) -> Any:
        ids = crud.branch_of(instance) if crud.branch_of is not None else None
        if ids is not None:
            ensure_visible(principal, ids, crud.label)
        return instance

    def _ensure_creatable(principal: Principal, instance: Any) -> None:
        # A 403 here, not the 404 `_visible` uses for reads: there is nothing
        # to hide the existence of, the caller is choosing the branch itself.
        ids = crud.branch_of(instance) if crud.branch_of is not None else None
        if ids is not None and not any(principal.may_see(bid) for bid in ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No access to branch '{ids[0] if len(ids) == 1 else ids}'",
            )

    def _branch_id(instance: Any) -> str | None:
        ids = crud.branch_of(instance) if crud.branch_of is not None else None
        return ids[0] if ids and len(ids) == 1 else None

    @router.get(path, response_model=list[crud.read_schema])
    def list_items(
        principal: Annotated[Principal, Depends(read_dependency)],
        request: Request,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
        offset: Annotated[int, Query(ge=0)] = 0,
        db: Session = Depends(get_db),
    ) -> Sequence[Any]:
        query = select(model)
        for parameter, column in crud.filters.items():
            value = request.query_params.get(parameter)
            if value is not None:
                query = query.where(getattr(model, column) == value)
        order_column = getattr(model, crud.order_by)
        query = query.order_by(order_column.desc() if crud.order_desc else order_column.asc())
        items = db.scalars(query.limit(limit).offset(offset)).all()
        if crud.branch_of is None:
            return items
        visible = []
        for item in items:
            ids = crud.branch_of(item)
            if ids is None or any(principal.may_see(bid) for bid in ids):
                visible.append(item)
        return visible

    @router.post(path, response_model=crud.read_schema, status_code=status.HTTP_201_CREATED)
    def create_item(
        payload: crud.create_schema,  # type: ignore[valid-type]
        principal: Annotated[Principal, Depends(write_dependency)],
        db: Session = Depends(get_db),
    ) -> Any:
        values = payload.model_dump()
        ensure_refs(db, values, crud.references)
        instance = model(**values)
        db.add(instance)
        db.flush()
        # After the flush, not before: `branch_of` may need to follow a
        # relationship (e.g. to the employee a review belongs to), which is
        # not loadable on a transient, not-yet-flushed instance.
        _ensure_creatable(principal, instance)
        audit(db, crud.entity_type, instance.id, "created", values, principal, branch_id=_branch_id(instance))
        db.commit()
        db.refresh(instance)
        return instance

    @router.get(f"{path}/{{item_id}}", response_model=crud.read_schema)
    def get_item(
        item_id: str, principal: Annotated[Principal, Depends(read_dependency)], db: Session = Depends(get_db)
    ) -> Any:
        return _visible(principal, get_or_404(db, model, item_id, crud.label))

    @router.patch(f"{path}/{{item_id}}", response_model=crud.read_schema)
    def update_item(
        item_id: str,
        payload: crud.update_schema,  # type: ignore[valid-type]
        principal: Annotated[Principal, Depends(write_dependency)],
        db: Session = Depends(get_db),
    ) -> Any:
        instance = _visible(principal, get_or_404(db, model, item_id, crud.label))
        changes = payload.model_dump(exclude_unset=True)
        ensure_refs(db, changes, crud.references)
        before = {key: getattr(instance, key) for key in changes}
        for key, value in changes.items():
            setattr(instance, key, value)
        # Re-checked after the change, not just before: a payload that moves
        # the row's own branch column would otherwise let it be reassigned
        # into a branch the caller has no access to.
        _ensure_creatable(principal, instance)
        audit(
            db, crud.entity_type, item_id, "updated", {"before": before, "after": changes}, principal,
            branch_id=_branch_id(instance),
        )
        db.commit()
        db.refresh(instance)
        return instance

    @router.delete(f"{path}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(
        item_id: str,
        principal: Annotated[Principal, Depends(write_dependency)],
        db: Session = Depends(get_db),
    ) -> Response:
        instance = _visible(principal, get_or_404(db, model, item_id, crud.label))
        guard_children(db, crud.children, item_id)
        branch_id = _branch_id(instance)
        # The full row goes into the audit log so a delete stays traceable.
        audit(db, crud.entity_type, item_id, "deleted", snapshot(instance), principal, branch_id=branch_id)
        db.delete(instance)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
