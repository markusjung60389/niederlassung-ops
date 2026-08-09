"""qualification catalogue, branch functions and employee status

Revision ID: 0004_qualifications
Revises: 0003_sales
Create Date: 2026-08-09

Structure and data, in that order:

1. Three new tables: the qualification catalogue, the branch functions and the
   requirement matrix between them.
2. `employees` gains a function reference plus an active/departed status;
   `employee_qualifications` gains a catalogue reference and an issue date.
3. The catalogue is filled with the obligations a German branch of this trade
   actually has, and the three Remscheid functions are created with their
   requirements.
4. The training and licence dates that sat in `employee_profiles` are **copied**
   into `employee_qualifications`, where a document can be attached to them.

Point 4 copies, it does not move: the profile columns keep their values and are
simply no longer read. If the mapping turns out to be wrong for a branch, the
originals are still there. Dropping those columns is a later migration, once
this one has proven itself in production.
"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0004_qualifications"
down_revision: Union[str, None] = "0003_sales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Fixed ids, shared with app/catalog.py so the runtime seed recognises these
# rows instead of creating a second copy.
QUALIFICATION_TYPES = [
    # (id, code, name, category, validity_months, reminder_days, legal_basis)
    ("qt-fuehrerschein", "fuehrerschein", "Fahrerlaubnis", "licence", None, 60, "FeV"),
    (
        "qt-fuehrerschein-kontrolle",
        "fuehrerschein_kontrolle",
        "Fuehrerscheinkontrolle",
        "licence",
        6,
        30,
        "DGUV Vorschrift 70 / Halterhaftung StVG",
    ),
    (
        "qt-erste-hilfe",
        "erste_hilfe",
        "Erste-Hilfe-Ausbildung",
        "training",
        24,
        60,
        "DGUV Vorschrift 1 Paragraf 26",
    ),
    ("qt-ipaf", "ipaf", "IPAF-Bedienerschulung", "training", 60, 90, "DGUV Grundsatz 308-008"),
    ("qt-psa-absturz", "psa_absturz", "PSA gegen Absturz", "instruction", 12, 45, "DGUV Regel 112-198"),
    (
        "qt-unterweisung",
        "unterweisung_allgemein",
        "Jaehrliche Unterweisung",
        "instruction",
        12,
        45,
        "ArbSchG Paragraf 12 / DGUV Vorschrift 1 Paragraf 4",
    ),
    (
        "qt-arbeitsmedizin",
        "arbeitsmedizin",
        "Arbeitsmedizinische Vorsorge",
        "medical",
        36,
        60,
        "ArbMedVV",
    ),
    (
        "qt-befaehigte-person",
        "befaehigte_person",
        "Befaehigte Person zur Pruefung",
        "training",
        36,
        90,
        "BetrSichV / TRBS 1203",
    ),
    (
        "qt-brandschutzhelfer",
        "brandschutzhelfer",
        "Brandschutzhelfer",
        "training",
        36,
        60,
        "ASR A2.2 / DGUV Information 205-023",
    ),
]

JOB_ROLES = [
    (
        "jr-projektleiter",
        "Projektleiter",
        "Fuehrt Projekte, koordiniert Montage und Service, ist auf Baustellen unterwegs.",
        [
            ("qt-unterweisung", True),
            ("qt-fuehrerschein", True),
            ("qt-fuehrerschein-kontrolle", True),
            ("qt-arbeitsmedizin", True),
            ("qt-ipaf", False),
            ("qt-erste-hilfe", False),
            ("qt-brandschutzhelfer", False),
        ],
    ),
    (
        "jr-service-techniker",
        "Service-Techniker",
        "Wartung, Pruefung und Instandsetzung beim Kunden, ueberwiegend im Aussendienst.",
        [
            ("qt-unterweisung", True),
            ("qt-fuehrerschein", True),
            ("qt-fuehrerschein-kontrolle", True),
            ("qt-ipaf", True),
            ("qt-psa-absturz", True),
            ("qt-arbeitsmedizin", True),
            ("qt-befaehigte-person", True),
            ("qt-erste-hilfe", False),
        ],
    ),
    (
        "jr-monteur",
        "Monteur",
        "Montage und Demontage vor Ort, Arbeiten in Hoehe mit Hubarbeitsbuehne.",
        [
            ("qt-unterweisung", True),
            ("qt-ipaf", True),
            ("qt-psa-absturz", True),
            ("qt-arbeitsmedizin", True),
            ("qt-fuehrerschein", False),
            ("qt-fuehrerschein-kontrolle", False),
            ("qt-erste-hilfe", False),
        ],
    ),
]

# Spellings seen in the existing free-text role column. Anything else stays
# unlinked and is assigned in the application - guessing further would attach
# people to the wrong requirements.
ROLE_ALIASES = {
    "projektleiter": "jr-projektleiter",
    "projektleiterin": "jr-projektleiter",
    "projektleitung": "jr-projektleiter",
    "service-techniker": "jr-service-techniker",
    "servicetechniker": "jr-service-techniker",
    "service techniker": "jr-service-techniker",
    "servicetechnikerin": "jr-service-techniker",
    "techniker": "jr-service-techniker",
    "monteur": "jr-monteur",
    "monteurin": "jr-monteur",
    "montage": "jr-monteur",
}

# (qualification type id, title, valid_until column, issued_on column)
PROFILE_MIGRATIONS = [
    (
        "qt-fuehrerschein-kontrolle",
        "Fuehrerscheinkontrolle",
        "driver_license_next_check",
        "driver_license_last_check",
    ),
    ("qt-erste-hilfe", "Erste-Hilfe-Ausbildung", "first_aid_valid_until", "first_aid_last_course"),
    ("qt-ipaf", "IPAF-Bedienerschulung", "ipaf_valid_until", "ipaf_last_training"),
    (
        "qt-unterweisung",
        "Jaehrliche Unterweisung",
        "general_instruction_next",
        "general_instruction_last",
    ),
    (
        "qt-arbeitsmedizin",
        "Arbeitsmedizinische Vorsorge",
        "occupational_health_next",
        "occupational_health_last",
    ),
]


def _seed_catalogue(connection, now: datetime) -> None:
    for type_id, code, name, category, validity, reminder, legal_basis in QUALIFICATION_TYPES:
        connection.execute(
            sa.text(
                "INSERT INTO qualification_types "
                "(id, code, name, category, validity_months, reminder_days, evidence_required,"
                " legal_basis, active, created_at, updated_at) "
                "VALUES (:id, :code, :name, :category, :validity, :reminder, :evidence,"
                " :legal_basis, :active, :created, :updated)"
            ),
            {
                "id": type_id,
                "code": code,
                "name": name,
                "category": category,
                "validity": validity,
                "reminder": reminder,
                "evidence": True,
                "legal_basis": legal_basis,
                "active": True,
                "created": now,
                "updated": now,
            },
        )

    for role_id, name, description, requirements in JOB_ROLES:
        connection.execute(
            sa.text(
                "INSERT INTO job_roles (id, name, description, active, created_at, updated_at) "
                "VALUES (:id, :name, :description, :active, :created, :updated)"
            ),
            {
                "id": role_id,
                "name": name,
                "description": description,
                "active": True,
                "created": now,
                "updated": now,
            },
        )
        for type_id, mandatory in requirements:
            connection.execute(
                sa.text(
                    "INSERT INTO job_role_requirements "
                    "(id, job_role_id, qualification_type_id, mandatory, created_at, updated_at) "
                    "VALUES (:id, :role, :type, :mandatory, :created, :updated)"
                ),
                {
                    "id": str(uuid4()),
                    "role": role_id,
                    "type": type_id,
                    "mandatory": mandatory,
                    "created": now,
                    "updated": now,
                },
            )


def _link_employees(connection) -> None:
    rows = connection.execute(sa.text("SELECT id, role FROM employees")).fetchall()
    for employee_id, role in rows:
        match = ROLE_ALIASES.get((role or "").strip().casefold())
        if match:
            connection.execute(
                sa.text("UPDATE employees SET job_role_id = :role WHERE id = :id"),
                {"role": match, "id": employee_id},
            )


def _copy_profile_dates(connection, now: datetime) -> int:
    columns = ", ".join(
        sorted(
            {column for _, _, column, issued in PROFILE_MIGRATIONS for column in (column, issued)}
        )
    )
    profiles = connection.execute(
        sa.text(f"SELECT employee_id, driver_license_classes, {columns} FROM employee_profiles")
    ).mappings().all()

    created = 0
    for profile in profiles:
        employee_id = profile["employee_id"]
        for type_id, title, valid_column, issued_column in PROFILE_MIGRATIONS:
            valid_until = profile[valid_column]
            issued_on = profile[issued_column]
            if valid_until is None and issued_on is None:
                continue
            existing = connection.execute(
                sa.text(
                    "SELECT 1 FROM employee_qualifications "
                    "WHERE employee_id = :employee AND qualification_type_id = :type LIMIT 1"
                ),
                {"employee": employee_id, "type": type_id},
            ).first()
            if existing:
                continue
            connection.execute(
                sa.text(
                    "INSERT INTO employee_qualifications "
                    "(id, employee_id, title, qualification_type, qualification_type_id,"
                    " issued_on, valid_until, reminder_days, created_at, updated_at) "
                    "VALUES (:id, :employee, :title, :kind, :type, :issued, :valid, :reminder,"
                    " :created, :updated)"
                ),
                {
                    "id": str(uuid4()),
                    "employee": employee_id,
                    "title": title,
                    "kind": type_id.removeprefix("qt-"),
                    "type": type_id,
                    "issued": issued_on,
                    "valid": valid_until,
                    "reminder": 30,
                    "created": now,
                    "updated": now,
                },
            )
            created += 1
    return created


def upgrade() -> None:
    op.create_table(
        "job_roles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job_roles"),
        sa.UniqueConstraint("name", name="uq_job_roles_name"),
    )
    op.create_table(
        "qualification_types",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False, server_default="qualification"),
        sa.Column("validity_months", sa.Integer(), nullable=True),
        sa.Column("reminder_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("evidence_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("legal_basis", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_qualification_types"),
        sa.UniqueConstraint("code", name="uq_qualification_types_code"),
    )
    op.create_table(
        "job_role_requirements",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_role_id", sa.String(), nullable=False),
        sa.Column("qualification_type_id", sa.String(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_role_id"], ["job_roles.id"], name="fk_job_role_requirements_job_role_id_job_roles"
        ),
        sa.ForeignKeyConstraint(
            ["qualification_type_id"],
            ["qualification_types.id"],
            name="fk_job_role_requirements_qualification_type_id_qualification_types",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_role_requirements"),
        sa.UniqueConstraint(
            "job_role_id", "qualification_type_id", name="uq_job_role_requirements_role_type"
        ),
    )
    op.create_index(
        "ix_job_role_requirements_job_role_id", "job_role_requirements", ["job_role_id"]
    )
    op.create_index(
        "ix_job_role_requirements_qualification_type_id",
        "job_role_requirements",
        ["qualification_type_id"],
    )

    with op.batch_alter_table("employee_qualifications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("qualification_type_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("issued_on", sa.Date(), nullable=True))
        batch_op.create_index(
            "ix_employee_qualifications_qualification_type_id", ["qualification_type_id"]
        )
        batch_op.create_foreign_key(
            "fk_employee_qualifications_qualification_type_id_qualification_types",
            "qualification_types",
            ["qualification_type_id"],
            ["id"],
        )

    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.add_column(sa.Column("job_role_id", sa.String(), nullable=True))
        # server_default is what makes this safe on a populated table: without
        # it the NOT NULL column has no value for existing rows.
        batch_op.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active")
        )
        batch_op.add_column(sa.Column("exit_date", sa.Date(), nullable=True))
        batch_op.create_index("ix_employees_job_role_id", ["job_role_id"])
        batch_op.create_index("ix_employees_status", ["status"])
        batch_op.create_foreign_key(
            "fk_employees_job_role_id_job_roles", "job_roles", ["job_role_id"], ["id"]
        )

    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    _seed_catalogue(connection, now)
    _link_employees(connection)
    _copy_profile_dates(connection, now)


def downgrade() -> None:
    # The copied qualifications disappear with the column that identifies them,
    # but the profile columns they came from were never touched - no date is
    # lost by going back.
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM employee_qualifications WHERE qualification_type_id IS NOT NULL")
    )

    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.drop_constraint("fk_employees_job_role_id_job_roles", type_="foreignkey")
        batch_op.drop_index("ix_employees_status")
        batch_op.drop_index("ix_employees_job_role_id")
        batch_op.drop_column("exit_date")
        batch_op.drop_column("status")
        batch_op.drop_column("job_role_id")

    with op.batch_alter_table("employee_qualifications", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_employee_qualifications_qualification_type_id_qualification_types",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_employee_qualifications_qualification_type_id")
        batch_op.drop_column("issued_on")
        batch_op.drop_column("qualification_type_id")

    op.drop_index("ix_job_role_requirements_qualification_type_id", table_name="job_role_requirements")
    op.drop_index("ix_job_role_requirements_job_role_id", table_name="job_role_requirements")
    op.drop_table("job_role_requirements")
    op.drop_table("qualification_types")
    op.drop_table("job_roles")
