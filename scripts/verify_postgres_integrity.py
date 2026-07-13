from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.database import engine
from app.postgres_integrity import (
    POSTGRES_INTEGRITY_FUNCTION_NAMES,
    POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS,
    POSTGRES_INTEGRITY_TRIGGER_TABLES,
)


def verify_postgresql_integrity_guards() -> None:
    """Fail deployment verification unless every database guard is live."""

    if engine.dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL integrity verification requires PostgreSQL")

    with engine.connect() as connection:
        trigger_rows = connection.execute(
            text(
                """
                SELECT
                    trigger_info.tgname AS trigger_name,
                    table_info.relname AS table_name,
                    function_info.proname AS function_name,
                    trigger_info.tgenabled AS enabled
                FROM pg_catalog.pg_trigger AS trigger_info
                JOIN pg_catalog.pg_class AS table_info
                  ON table_info.oid = trigger_info.tgrelid
                JOIN pg_catalog.pg_namespace AS table_schema
                  ON table_schema.oid = table_info.relnamespace
                JOIN pg_catalog.pg_proc AS function_info
                  ON function_info.oid = trigger_info.tgfoid
                WHERE NOT trigger_info.tgisinternal
                  AND table_schema.nspname = current_schema()
                """
            )
        ).mappings().all()
        function_rows = connection.execute(
            text(
                """
                SELECT function_info.proname AS function_name
                FROM pg_catalog.pg_proc AS function_info
                JOIN pg_catalog.pg_namespace AS function_schema
                  ON function_schema.oid = function_info.pronamespace
                WHERE function_schema.nspname = current_schema()
                  AND function_info.pronargs = 0
                """
            )
        ).scalars().all()

    expected_triggers = {
        trigger_name: (
            POSTGRES_INTEGRITY_TRIGGER_TABLES[trigger_name],
            POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS[trigger_name],
        )
        for trigger_name in POSTGRES_INTEGRITY_TRIGGER_TABLES
    }
    actual_triggers = {
        row["trigger_name"]: (row["table_name"], row["function_name"])
        for row in trigger_rows
        if row["trigger_name"] in expected_triggers and row["enabled"] != "D"
    }
    if actual_triggers != expected_triggers:
        missing = sorted(set(expected_triggers) - set(actual_triggers))
        mismatched = sorted(
            name
            for name in set(expected_triggers) & set(actual_triggers)
            if actual_triggers[name] != expected_triggers[name]
        )
        raise RuntimeError(
            "PostgreSQL integrity trigger verification failed: "
            f"missing_or_disabled={missing}, mismatched={mismatched}"
        )

    actual_functions = set(function_rows)
    missing_functions = sorted(POSTGRES_INTEGRITY_FUNCTION_NAMES - actual_functions)
    if missing_functions:
        raise RuntimeError(
            "PostgreSQL integrity function verification failed: "
            f"missing={missing_functions}"
        )

    print(
        "PostgreSQL integrity guards verified: "
        f"{len(expected_triggers)} triggers, "
        f"{len(POSTGRES_INTEGRITY_FUNCTION_NAMES)} functions"
    )


if __name__ == "__main__":
    verify_postgresql_integrity_guards()
