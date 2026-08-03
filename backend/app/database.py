from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        """SQLite ignores foreign keys unless asked; without this, local runs
        accept references that PostgreSQL would reject."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _alembic_config():
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    config.attributes["configure_logger"] = False
    return config


def init_db() -> None:
    """Brings the database up to the current migration head.

    A database created by the pre-Alembic ``create_all`` bootstrap is missing
    the auth columns, so it is reported instead of being silently stamped.
    """
    from alembic import command

    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        if tables and "alembic_version" not in tables:
            raise RuntimeError(
                "The database was created by the pre-Alembic bootstrap and cannot be migrated "
                "automatically. Recreate it (docker compose down -v, or delete "
                "backend/remscheid_ops.db) and start again; no production data exists yet."
            )
        config = _alembic_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        connection.commit()


def current_revision() -> str | None:
    with engine.connect() as connection:
        if "alembic_version" not in set(inspect(connection).get_table_names()):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
