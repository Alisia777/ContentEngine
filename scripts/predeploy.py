from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.config import get_settings, validate_runtime_settings
from app.database import engine
from app.migration_state import (
    require_database_at_migration_head,
    serialized_database_migration,
)


def main() -> None:
    """Create/upgrade the schema once before web and worker are released."""

    # Validate TLS, cloud auth, and storage before opening a production
    # database connection or executing any DDL.
    validate_runtime_settings(get_settings())
    with serialized_database_migration(engine):
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            require_database_at_migration_head(connection)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("ContentEngine pre-deploy schema check: ready")


if __name__ == "__main__":
    main()
