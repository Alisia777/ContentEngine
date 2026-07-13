"""Shared Alembic head checks and PostgreSQL migration serialization."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALEMBIC_CONFIG = ROOT / "alembic.ini"
MIGRATION_ADVISORY_LOCK_ID = 18918490631056725


class DatabaseMigrationStateError(RuntimeError):
    """Safe startup failure when the live schema is not at repository head."""


@lru_cache(maxsize=4)
def expected_migration_heads(
    config_path: str = str(DEFAULT_ALEMBIC_CONFIG),
) -> frozenset[str]:
    config = Config(config_path)
    heads = frozenset(ScriptDirectory.from_config(config).get_heads())
    if not heads:
        raise DatabaseMigrationStateError("repository_migration_head_missing")
    return heads


def current_migration_heads(connection: Connection) -> frozenset[str]:
    return frozenset(MigrationContext.configure(connection).get_current_heads())


def database_is_at_migration_head(
    connection: Connection,
    *,
    config_path: Path | str = DEFAULT_ALEMBIC_CONFIG,
) -> bool:
    return current_migration_heads(connection) == expected_migration_heads(
        str(Path(config_path).resolve())
    )


def require_database_at_migration_head(
    connection: Connection,
    *,
    config_path: Path | str = DEFAULT_ALEMBIC_CONFIG,
) -> None:
    if not database_is_at_migration_head(connection, config_path=config_path):
        raise DatabaseMigrationStateError("database_migration_head_mismatch")


@contextmanager
def serialized_database_migration(engine: Engine) -> Iterator[None]:
    """Serialize web/worker Alembic runs with one PostgreSQL session lock."""

    if engine.dialect.name != "postgresql":
        yield
        return

    with engine.connect() as lock_connection:
        # Managed pre-deploy commands have a finite lifetime. Bound lock wait
        # below that window so a wedged reference deploy fails instead of hanging.
        lock_connection.execute(text("SET lock_timeout = '10min'"))
        lock_connection.execute(
            text("SELECT pg_advisory_lock(:lock_id)"),
            {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
        )
        try:
            yield
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            )
