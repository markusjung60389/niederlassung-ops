"""pay per employee, in a table of its own

Revision ID: 0007_salary
Revises: 0006_accounts
Create Date: 2026-08-09

One new table, nothing else touched.

Deliberately not a column on `employee_profiles`: the profile travels inside
every employee response, and a field that must never be sent by accident does
not belong in a payload built for something else. Its own table gives it its
own endpoint, its own permission and its own audit trail.

`amount` is NUMERIC(10,2), not a float - money that is off by a cent because
of binary rounding is money somebody has to explain. One row per employee: the
current arrangement, not a history. What was paid last year is the payroll
system's business, and so is everything else about it.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_salary"
down_revision: Union[str, None] = "0006_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_salaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("hours_per_week", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name="fk_employee_salaries_employee_id"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_employee_salaries_updated_by"),
        sa.PrimaryKeyConstraint("id", name="pk_employee_salaries"),
        sa.UniqueConstraint("employee_id", name="uq_employee_salaries_employee_id"),
    )
    op.create_index("ix_employee_salaries_employee_id", "employee_salaries", ["employee_id"])


def downgrade() -> None:
    # Going back removes the pay data. There is no earlier place to keep it -
    # it never existed before this migration - and leaving an orphan table
    # behind would be worse than the clean removal.
    op.drop_index("ix_employee_salaries_employee_id", table_name="employee_salaries")
    op.drop_table("employee_salaries")
