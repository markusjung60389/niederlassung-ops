"""auth fields and integrity

Adds the Entra ID columns, the one-profile-per-employee constraint and the
lookup indexes.

Written to run against a populated database:
  * ``is_active`` gets a server default, otherwise the NOT NULL fails on
    existing rows.
  * the unique constraint is named explicitly, otherwise the downgrade cannot
    address it on PostgreSQL.
  * duplicate employee profiles are archived into ``audit_log`` before the
    constraint is applied, instead of aborting the migration or dropping data
    without a trace.

Revision ID: 0002_auth
Revises: 0001_initial
Create Date: 2026-08-03
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_auth"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNIQUE_PROFILE = "uq_employee_profiles_employee_id"

INDEXES: list[tuple[str, str, list[str], bool]] = [
    ("audit_log", "ix_audit_log_created_at", ["created_at"], False),
    ("audit_log", "ix_audit_log_entity_id", ["entity_id"], False),
    ("audit_log", "ix_audit_log_entity_type", ["entity_type"], False),
    ("branch_assessments", "ix_branch_assessments_assessment_date", ["assessment_date"], False),
    ("branch_assessments", "ix_branch_assessments_branch_id", ["branch_id"], False),
    ("compliance_actions", "ix_compliance_actions_compliance_record_id", ["compliance_record_id"], False),
    ("compliance_actions", "ix_compliance_actions_due_date", ["due_date"], False),
    ("compliance_actions", "ix_compliance_actions_status", ["status"], False),
    ("compliance_evidence", "ix_compliance_evidence_compliance_record_id", ["compliance_record_id"], False),
    ("compliance_records", "ix_compliance_records_branch_id", ["branch_id"], False),
    ("compliance_records", "ix_compliance_records_due_date", ["due_date"], False),
    ("compliance_records", "ix_compliance_records_owner_user_id", ["owner_user_id"], False),
    ("compliance_records", "ix_compliance_records_status", ["status"], False),
    ("employee_qualifications", "ix_employee_qualifications_employee_id", ["employee_id"], False),
    ("employee_qualifications", "ix_employee_qualifications_valid_until", ["valid_until"], False),
    ("employees", "ix_employees_branch_id", ["branch_id"], False),
    ("incidents", "ix_incidents_branch_id", ["branch_id"], False),
    ("incidents", "ix_incidents_occurred_at", ["occurred_at"], False),
    ("service_contracts", "ix_service_contracts_next_maintenance_at", ["next_maintenance_at"], False),
    ("users", "ix_users_external_id", ["external_id"], True),
    ("vehicles", "ix_vehicles_branch_id", ["branch_id"], False),
]


def _archive_duplicate_profiles(connection) -> int:
    """Keeps the newest profile per employee and stores the rest in audit_log."""
    profiles = connection.execute(
        sa.text(
            "SELECT * FROM employee_profiles ORDER BY employee_id, created_at DESC, id DESC"
        )
    ).mappings().all()

    seen: set[str] = set()
    removed = 0
    for row in profiles:
        employee_id = row["employee_id"]
        if employee_id not in seen:
            seen.add(employee_id)
            continue
        payload = {
            key: (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in dict(row).items()
        }
        connection.execute(
            sa.text(
                "INSERT INTO audit_log (id, entity_type, entity_id, action, actor_user_id, changes, created_at) "
                "VALUES (:id, :entity_type, :entity_id, :action, NULL, :changes, :created_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "entity_type": "employee_profile",
                "entity_id": row["id"],
                "action": "deduplicated_by_migration_0002",
                "changes": json.dumps(payload),
                "created_at": datetime.now(timezone.utc),
            },
        )
        connection.execute(
            sa.text("DELETE FROM employee_profiles WHERE id = :id"), {"id": row["id"]}
        )
        removed += 1
    return removed


def upgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("users", schema=None) as batch_op:
        # server_default keeps the NOT NULL valid for rows that already exist.
        batch_op.add_column(sa.Column("external_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    removed = _archive_duplicate_profiles(connection)
    if removed:
        print(f"[0002_auth] archived {removed} duplicate employee profile(s) into audit_log")

    with op.batch_alter_table("employee_profiles", schema=None) as batch_op:
        batch_op.create_unique_constraint(UNIQUE_PROFILE, ["employee_id"])

    for table, name, columns, unique in INDEXES:
        op.create_index(name, table, columns, unique=unique)


def downgrade() -> None:
    for table, name, _columns, _unique in reversed(INDEXES):
        op.drop_index(name, table_name=table)

    with op.batch_alter_table("employee_profiles", schema=None) as batch_op:
        batch_op.drop_constraint(UNIQUE_PROFILE, type_="unique")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("external_id")
