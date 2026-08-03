"""Migrations must never destroy data.

A pre-Alembic database is simulated by building revision 0001 (which was
generated from the original models) and removing the version marker, which is
exactly the shape the old ``create_all`` bootstrap left behind. Rows are then
inserted and the real migration path is run against them.
"""

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_ROOT = Path(__file__).resolve().parent.parent
NOW = "2026-01-01 08:00:00"


def head_revision() -> str:
    """Read from Alembic rather than hard-coded, so new migrations do not break these tests."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


HEAD = head_revision()


def _run(module_args: list[str], database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *module_args],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        env={
            "DATABASE_URL": database_url,
            "AUTH_MODE": "dev",
            "APP_ENV": "test",
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(BACKEND_ROOT),
        },
    )


def _alembic(database_url: str, *args: str) -> None:
    result = _run(["-m", "alembic", *args], database_url)
    assert result.returncode == 0, result.stderr


def _init_db(database_url: str) -> str:
    """Runs init_db in a fresh interpreter so settings pick up the URL."""
    result = _run(
        ["-c", "from app.database import init_db, current_revision; init_db(); print(current_revision())"],
        database_url,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def _make_legacy_database(url: str, engine, *, duplicate_profiles: int = 0) -> None:
    _alembic(url, "upgrade", "0001_initial")
    with engine.begin() as connection:
        # A database from before the migration history has no version marker.
        connection.execute(sa.text("DROP TABLE alembic_version"))

        connection.execute(
            sa.text("INSERT INTO branches (id, name, location, created_at, updated_at) "
                    "VALUES ('b1','Remscheid','Remscheid',:t,:t)"),
            {"t": NOW},
        )
        connection.execute(
            sa.text("INSERT INTO roles (id, name, permissions) VALUES ('r1','Niederlassungsleiter','[\"*\"]')")
        )
        connection.execute(
            sa.text("INSERT INTO users (id, display_name, email, role_id, created_at, updated_at) "
                    "VALUES ('u1','Alt Nutzer','alt@example.local','r1',:t,:t)"),
            {"t": NOW},
        )
        connection.execute(
            sa.text("INSERT INTO employees (id, branch_id, full_name, role, team, start_date, "
                    "first_aider, skills, notes, created_at, updated_at) "
                    "VALUES ('e1','b1','Erika Muster','Monteurin','Team A','2020-01-01',0,"
                    "'[\"IPAF\"]','Notiz',:t,:t)"),
            {"t": NOW},
        )
        connection.execute(
            sa.text("INSERT INTO compliance_records (id, title, category, branch_id, scope_type, status, "
                    "priority, owner_user_id, legal_basis, control_type, due_date, review_date, "
                    "recurrence, tags, created_at, updated_at) "
                    "VALUES ('c1','Unterweisung','training_instruction','b1','branch','open','high','u1',"
                    "'DGUV V1','training','2026-06-01','2026-06-01','yearly','[]',:t,:t)"),
            {"t": NOW},
        )
        for index in range(1 + duplicate_profiles):
            connection.execute(
                sa.text(
                    "INSERT INTO employee_profiles (id, employee_id, contract_type, "
                    "residence_permit_required, residence_permit_type, driver_license_required, "
                    "driver_license_classes, occupational_health_required, notes, created_at, updated_at) "
                    "VALUES (:id,'e1','unbefristet',1,:permit,0,'[]',1,:notes,:created,:created)"
                ),
                {
                    "id": f"p{index}",
                    "permit": f"Aufenthaltstitel {index}",
                    "notes": f"profil-{index}",
                    "created": f"2026-01-0{index + 1} 08:00:00",
                },
            )


@pytest.fixture
def legacy_db(tmp_path):
    path = tmp_path / f"legacy-{uuid.uuid4().hex}.db"
    url = f"sqlite:///{path}"
    engine = sa.create_engine(url)
    yield engine, url
    engine.dispose()


def test_legacy_database_is_adopted_and_keeps_its_rows(legacy_db):
    engine, url = legacy_db
    _make_legacy_database(url, engine)

    assert _init_db(url) == HEAD

    with engine.connect() as connection:
        employee = connection.execute(sa.text("SELECT * FROM employees")).mappings().one()
        assert employee["full_name"] == "Erika Muster"
        assert employee["notes"] == "Notiz"

        profile = connection.execute(sa.text("SELECT * FROM employee_profiles")).mappings().one()
        assert profile["residence_permit_type"] == "Aufenthaltstitel 0"

        record = connection.execute(sa.text("SELECT * FROM compliance_records")).mappings().one()
        assert record["title"] == "Unterweisung"

        user = connection.execute(sa.text("SELECT * FROM users")).mappings().one()
        assert user["display_name"] == "Alt Nutzer"
        # New NOT NULL column is backfilled instead of failing on existing rows.
        assert user["is_active"] in (1, True)
        assert user["external_id"] is None


def test_duplicate_profiles_are_archived_not_silently_dropped(legacy_db):
    """The new unique constraint cannot be applied while duplicates exist."""
    engine, url = legacy_db
    _make_legacy_database(url, engine, duplicate_profiles=2)

    _init_db(url)

    with engine.connect() as connection:
        remaining = connection.execute(sa.text("SELECT * FROM employee_profiles")).mappings().all()
        assert len(remaining) == 1
        assert remaining[0]["notes"] == "profil-2"  # newest survives

        archived = connection.execute(
            sa.text("SELECT * FROM audit_log WHERE action = 'deduplicated_by_migration_0002'")
        ).mappings().all()
        assert len(archived) == 2
        assert sorted(json.loads(row["changes"])["notes"] for row in archived) == ["profil-0", "profil-1"]


def test_migrating_twice_is_a_no_op(legacy_db):
    engine, url = legacy_db
    _make_legacy_database(url, engine)

    assert _init_db(url) == HEAD
    assert _init_db(url) == HEAD

    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM employees")).scalar() == 1


def test_unique_constraint_is_enforced_after_migration(legacy_db):
    engine, url = legacy_db
    _make_legacy_database(url, engine)
    _init_db(url)

    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO employee_profiles (id, employee_id, contract_type, "
                    "residence_permit_required, driver_license_required, driver_license_classes, "
                    "occupational_health_required, created_at, updated_at) "
                    "VALUES ('p-dup','e1','unbefristet',0,0,'[]',0,:t,:t)"
                ),
                {"t": NOW},
            )


def test_downgrade_and_upgrade_round_trip_keeps_data(legacy_db):
    """A rollback must not take the pre-existing rows with it."""
    engine, url = legacy_db
    _make_legacy_database(url, engine)
    _init_db(url)

    _alembic(url, "downgrade", "0001_initial")
    _alembic(url, "upgrade", "head")

    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM employees")).scalar() == 1
        assert connection.execute(sa.text("SELECT COUNT(*) FROM employee_profiles")).scalar() == 1
        assert connection.execute(sa.text("SELECT COUNT(*) FROM compliance_records")).scalar() == 1
        assert connection.execute(sa.text("SELECT display_name FROM users")).scalar() == "Alt Nutzer"


def test_fresh_database_reaches_head(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    assert _init_db(url) == HEAD


def test_models_match_migrations(tmp_path):
    """Guards against a model change shipped without a migration."""
    url = f"sqlite:///{tmp_path / 'check.db'}"
    _alembic(url, "upgrade", "head")
    result = _run(["-m", "alembic", "check"], url)
    assert result.returncode == 0, f"models drifted from migrations:\n{result.stdout}\n{result.stderr}"
