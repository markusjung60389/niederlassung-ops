"""multiple branches: scope, deployments, exceptions and compliance rules

Revision ID: 0005_branches
Revises: 0004_qualifications
Create Date: 2026-08-09

Additive throughout - no column is dropped, no row is deleted.

1. New tables: `user_branches` (who may see which branch), `employee_branches`
   (where somebody is deployed besides their home branch),
   `requirement_overrides` (a branch's exception from a group requirement) and
   `compliance_rules` (the obligation, separate from the branch's work on it).
2. New columns: branch code/active/manager, `users.all_branches`, a branch
   reference on the catalogue and the functions (NULL = group-wide),
   `vehicles.current_branch_id` for a vehicle standing at another branch, and
   `compliance_records.rule_id`.
3. Data, and this is the part that matters on a populated database:
   - every existing account is linked to every existing branch. Before this
     migration everyone saw everything; afterwards scope is enforced, so
     without the backfill the first login after the upgrade would show an
     empty application. Narrowing it down is then a deliberate act.
   - the catalogue and the functions become group-wide (`branch_id` NULL),
     which is what they effectively were.
   - existing compliance records keep working unchanged and additionally get a
     branch-local rule describing them, so they show up in the new rule list
     and can be promoted to a group rule later. Records that describe the same
     obligation inside one branch share one rule instead of each getting a
     copy.

`employee_branches` is deliberately *not* backfilled from `employees.branch_id`:
the home branch already counts as an assignment, and a copy of it here would
turn into a stale second assignment the moment somebody moves branch.
"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0005_branches"
down_revision: Union[str, None] = "0004_qualifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _link_users_to_branches(connection, now: datetime) -> None:
    branches = [row[0] for row in connection.execute(sa.text("SELECT id FROM branches")).fetchall()]
    users = [row[0] for row in connection.execute(sa.text("SELECT id FROM users")).fetchall()]
    for user_id in users:
        for branch_id in branches:
            connection.execute(
                sa.text(
                    "INSERT INTO user_branches (id, user_id, branch_id, created_at, updated_at) "
                    "VALUES (:id, :user, :branch, :created, :updated)"
                ),
                {
                    "id": str(uuid4()),
                    "user": user_id,
                    "branch": branch_id,
                    "created": now,
                    "updated": now,
                },
            )


def _rules_from_records(connection, now: datetime) -> int:
    """Gives every existing compliance record a rule that describes it.

    Grouped per branch by what makes an obligation the same one: the title and
    how it is controlled. Two annual instruction records in one branch are one
    rule with two instances, not two rules.
    """
    records = connection.execute(
        sa.text(
            "SELECT id, title, category, branch_id, control_type, recurrence, legal_basis,"
            " priority, risk_if_missing, owner_user_id FROM compliance_records"
        )
    ).mappings().all()

    created: dict[tuple, str] = {}
    for record in records:
        key = (
            record["branch_id"],
            record["title"],
            record["category"],
            record["control_type"],
            record["recurrence"],
            record["legal_basis"],
        )
        rule_id = created.get(key)
        if rule_id is None:
            rule_id = str(uuid4())
            created[key] = rule_id
            connection.execute(
                sa.text(
                    "INSERT INTO compliance_rules (id, title, category, branch_id, control_type,"
                    " recurrence, legal_basis, priority, risk_if_missing, active, created_by,"
                    " created_at, updated_at) "
                    "VALUES (:id, :title, :category, :branch, :control, :recurrence, :legal,"
                    " :priority, :risk, :active, :created_by, :created, :updated)"
                ),
                {
                    "id": rule_id,
                    "title": record["title"],
                    "category": record["category"],
                    "branch": record["branch_id"],
                    "control": record["control_type"],
                    "recurrence": record["recurrence"],
                    "legal": record["legal_basis"],
                    "priority": record["priority"],
                    "risk": record["risk_if_missing"],
                    "active": True,
                    "created_by": record["owner_user_id"],
                    "created": now,
                    "updated": now,
                },
            )
        connection.execute(
            sa.text("UPDATE compliance_records SET rule_id = :rule WHERE id = :id"),
            {"rule": rule_id, "id": record["id"]},
        )
    return len(created)


def upgrade() -> None:
    op.create_table(
        "user_branches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_branches_user_id"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], name="fk_user_branches_branch_id"),
        sa.PrimaryKeyConstraint("id", name="pk_user_branches"),
        sa.UniqueConstraint("user_id", "branch_id", name="uq_user_branches_user_branch"),
    )
    op.create_index("ix_user_branches_user_id", "user_branches", ["user_id"])
    op.create_index("ix_user_branches_branch_id", "user_branches", ["branch_id"])

    op.create_table(
        "employee_branches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("employee_id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], name="fk_employee_branches_employee_id"
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name="fk_employee_branches_branch_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employee_branches"),
        sa.UniqueConstraint("employee_id", "branch_id", name="uq_employee_branches_employee_branch"),
    )
    op.create_index("ix_employee_branches_employee_id", "employee_branches", ["employee_id"])
    op.create_index("ix_employee_branches_branch_id", "employee_branches", ["branch_id"])

    op.create_table(
        "requirement_overrides",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=False),
        sa.Column("requirement_id", sa.String(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("acknowledged_by", sa.String(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("revoked_effective_from", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name="fk_requirement_overrides_branch_id"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["job_role_requirements.id"],
            name="fk_requirement_overrides_requirement",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_requirement_overrides_created_by"
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by"], ["users.id"], name="fk_requirement_overrides_acknowledged_by"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["users.id"], name="fk_requirement_overrides_revoked_by"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requirement_overrides"),
        sa.UniqueConstraint("branch_id", "requirement_id", name="uq_requirement_overrides_branch_req"),
    )
    op.create_index("ix_requirement_overrides_branch_id", "requirement_overrides", ["branch_id"])
    op.create_index(
        "ix_requirement_overrides_requirement_id", "requirement_overrides", ["requirement_id"]
    )

    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("branch_id", sa.String(), nullable=True),
        sa.Column("control_type", sa.String(length=40), nullable=False),
        sa.Column("recurrence", sa.String(length=40), nullable=False, server_default="yearly"),
        sa.Column("legal_basis", sa.String(length=200), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("risk_if_missing", sa.Text(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], name="fk_compliance_rules_branch_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_compliance_rules_created_by"),
        sa.PrimaryKeyConstraint("id", name="pk_compliance_rules"),
    )
    op.create_index("ix_compliance_rules_branch_id", "compliance_rules", ["branch_id"])

    with op.batch_alter_table("branches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=10), nullable=True))
        batch_op.add_column(
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("manager_user_id", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_branches_code", ["code"])
        batch_op.create_foreign_key(
            "fk_branches_manager_user_id", "users", ["manager_user_id"], ["id"]
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("all_branches", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("qualification_types", schema=None) as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.String(), nullable=True))
        batch_op.create_index("ix_qualification_types_branch_id", ["branch_id"])
        batch_op.create_foreign_key(
            "fk_qualification_types_branch_id", "branches", ["branch_id"], ["id"]
        )

    with op.batch_alter_table("job_roles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.String(), nullable=True))
        batch_op.create_index("ix_job_roles_branch_id", ["branch_id"])
        batch_op.create_foreign_key("fk_job_roles_branch_id", "branches", ["branch_id"], ["id"])

    with op.batch_alter_table("vehicles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_branch_id", sa.String(), nullable=True))
        batch_op.create_index("ix_vehicles_current_branch_id", ["current_branch_id"])
        batch_op.create_foreign_key(
            "fk_vehicles_current_branch_id", "branches", ["current_branch_id"], ["id"]
        )

    with op.batch_alter_table("compliance_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("rule_id", sa.String(), nullable=True))
        batch_op.create_index("ix_compliance_records_rule_id", ["rule_id"])
        batch_op.create_foreign_key(
            "fk_compliance_records_rule_id", "compliance_rules", ["rule_id"], ["id"]
        )

    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    _link_users_to_branches(connection, now)
    # The catalogue and the functions were written for one branch and hold for
    # all of them; NULL is what group-wide means. Explicit rather than implied,
    # because the column is new and every row has to state its scope.
    connection.execute(sa.text("UPDATE qualification_types SET branch_id = NULL"))
    connection.execute(sa.text("UPDATE job_roles SET branch_id = NULL"))
    connection.execute(
        sa.text("UPDATE branches SET code = 'RS' WHERE id = 'branch-remscheid' AND code IS NULL")
    )
    _rules_from_records(connection, now)


def downgrade() -> None:
    # The records keep their own copy of everything a rule holds, so dropping
    # the rules loses no compliance data. Exceptions and deployments do
    # disappear with their tables - they have no equivalent before this
    # migration.
    with op.batch_alter_table("compliance_records", schema=None) as batch_op:
        batch_op.drop_constraint("fk_compliance_records_rule_id", type_="foreignkey")
        batch_op.drop_index("ix_compliance_records_rule_id")
        batch_op.drop_column("rule_id")

    with op.batch_alter_table("vehicles", schema=None) as batch_op:
        batch_op.drop_constraint("fk_vehicles_current_branch_id", type_="foreignkey")
        batch_op.drop_index("ix_vehicles_current_branch_id")
        batch_op.drop_column("current_branch_id")

    with op.batch_alter_table("job_roles", schema=None) as batch_op:
        batch_op.drop_constraint("fk_job_roles_branch_id", type_="foreignkey")
        batch_op.drop_index("ix_job_roles_branch_id")
        batch_op.drop_column("branch_id")

    with op.batch_alter_table("qualification_types", schema=None) as batch_op:
        batch_op.drop_constraint("fk_qualification_types_branch_id", type_="foreignkey")
        batch_op.drop_index("ix_qualification_types_branch_id")
        batch_op.drop_column("branch_id")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("all_branches")

    with op.batch_alter_table("branches", schema=None) as batch_op:
        batch_op.drop_constraint("fk_branches_manager_user_id", type_="foreignkey")
        batch_op.drop_constraint("uq_branches_code", type_="unique")
        batch_op.drop_column("manager_user_id")
        batch_op.drop_column("active")
        batch_op.drop_column("code")

    op.drop_index("ix_compliance_rules_branch_id", table_name="compliance_rules")
    op.drop_table("compliance_rules")
    op.drop_index("ix_requirement_overrides_requirement_id", table_name="requirement_overrides")
    op.drop_index("ix_requirement_overrides_branch_id", table_name="requirement_overrides")
    op.drop_table("requirement_overrides")
    op.drop_index("ix_employee_branches_branch_id", table_name="employee_branches")
    op.drop_index("ix_employee_branches_employee_id", table_name="employee_branches")
    op.drop_table("employee_branches")
    op.drop_index("ix_user_branches_branch_id", table_name="user_branches")
    op.drop_index("ix_user_branches_user_id", table_name="user_branches")
    op.drop_table("user_branches")
