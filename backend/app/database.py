import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

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


LEGACY_BASELINE_REVISION = "0001_initial"


def init_db() -> None:
    """Brings the database up to the current migration head, keeping all data.

    A database created by the pre-Alembic ``create_all`` bootstrap carries no
    version marker. Its schema is exactly revision 0001, so it is stamped as
    such and then migrated forward like any other database. Nothing is dropped
    and nothing is recreated.
    """
    from alembic import command
    from sqlalchemy.pool import NullPool

    # Migrations run on their own engine, without the foreign-key pragma the
    # application engine installs. SQLite implements ALTER by rebuilding the
    # table (create, copy, drop, rename), and the intermediate DROP violates
    # foreign keys from other tables while enforcement is on.
    migration_engine = create_engine(
        settings.database_url, poolclass=NullPool, connect_args=connect_args
    )
    try:
        with migration_engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            config = _alembic_config()
            config.attributes["connection"] = connection

            if tables and "alembic_version" not in tables:
                logger.warning(
                    "Database predates the migration history; adopting it at revision %s and "
                    "migrating forward. No data is removed.",
                    LEGACY_BASELINE_REVISION,
                )
                command.stamp(config, LEGACY_BASELINE_REVISION)

            command.upgrade(config, "head")
            connection.commit()
    finally:
        migration_engine.dispose()


def current_revision() -> str | None:
    with engine.connect() as connection:
        if "alembic_version" not in set(inspect(connection).get_table_names()):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
