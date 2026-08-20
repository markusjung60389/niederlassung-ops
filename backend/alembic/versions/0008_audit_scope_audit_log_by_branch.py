"""scope the audit log by branch

Revision ID: 0008_audit
Revises: 0007_salary
Create Date: 2026-08-20

Additive only, existing rows are kept as-is.

`branch_id` is nullable on purpose: group-wide events (a role edited, a
qualification type or job role changed, a user created) have no single
branch and stay visible to everyone with `audit:read`, same as before. Events
tied to a branch (an employee, a compliance record, an incident, ...) get one
from this point on, and the audit log endpoint filters on it - a reader
scoped to one branch stops seeing the residence-permit and health data that
another branch's employees carried in their delete snapshots.

Existing rows predate the column and stay NULL: backfilling them would mean
parsing free-form JSON `changes` payloads to guess a branch, which is more
likely to mislabel a row than to help. NULL rows keep behaving exactly as
before the app was upgraded (visible to every reader with `audit:read`) so no
history disappears; only new events get the tighter scoping.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_audit"
down_revision: Union[str, None] = "0007_salary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_audit_log_branch_id", "branches", ["branch_id"], ["id"]
        )
    op.create_index("ix_audit_log_branch_id", "audit_log", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_branch_id", table_name="audit_log")
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_constraint("fk_audit_log_branch_id", type_="foreignkey")
        batch_op.drop_column("branch_id")
