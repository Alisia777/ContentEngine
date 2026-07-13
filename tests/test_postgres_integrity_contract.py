from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.postgres_integrity import (
    POSTGRES_INTEGRITY_FUNCTION_NAMES,
    POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS,
    POSTGRES_INTEGRITY_TRIGGER_TABLES,
    drop_postgresql_integrity_guards,
    install_postgresql_integrity_guards,
)


ROOT = Path(__file__).resolve().parents[1]


class RecordingConnection:
    def __init__(self, dialect_name: str = "postgresql") -> None:
        self.dialect = SimpleNamespace(name=dialect_name)
        self.statements: list[str] = []

    def execute(self, statement) -> None:
        self.statements.append(" ".join(str(statement).split()))


def test_installer_emits_complete_deterministic_postgresql_guard_set() -> None:
    connection = RecordingConnection()

    install_postgresql_integrity_guards(connection)  # type: ignore[arg-type]

    ddl = "\n".join(connection.statements)
    assert set(POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS) == set(
        POSTGRES_INTEGRITY_TRIGGER_TABLES
    )
    assert set(POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS.values()) == set(
        POSTGRES_INTEGRITY_FUNCTION_NAMES
    )
    for function_name in POSTGRES_INTEGRITY_FUNCTION_NAMES:
        assert f"CREATE OR REPLACE FUNCTION {function_name}()" in ddl
    for trigger_name, table_name in POSTGRES_INTEGRITY_TRIGGER_TABLES.items():
        function_name = POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS[trigger_name]
        assert f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}" in ddl
        assert f"CREATE TRIGGER {trigger_name}" in ddl
        assert f"ON {table_name} FOR EACH ROW EXECUTE FUNCTION {function_name}()" in ddl

    assert (
        "CREATE TRIGGER customer_billing_ledger_no_overapply BEFORE INSERT "
        "ON customer_billing_ledger_entries"
    ) in ddl
    assert "FROM customer_invoices" in ddl
    assert "organization_id = NEW.organization_id FOR UPDATE" in ddl
    assert "customer billing entry exceeds outstanding balance" in ddl
    assert (
        "CREATE TRIGGER generation_cost_ledger_entries_append_only "
        "BEFORE UPDATE OR DELETE"
    ) in ddl


def test_downgrade_removes_triggers_before_functions() -> None:
    connection = RecordingConnection()

    drop_postgresql_integrity_guards(connection)  # type: ignore[arg-type]

    expected_trigger_drops = len(POSTGRES_INTEGRITY_TRIGGER_TABLES)
    assert len(connection.statements) == (
        expected_trigger_drops + len(POSTGRES_INTEGRITY_FUNCTION_NAMES)
    )
    assert all(
        statement.startswith("DROP TRIGGER IF EXISTS")
        for statement in connection.statements[:expected_trigger_drops]
    )
    assert all(
        statement.startswith("DROP FUNCTION IF EXISTS")
        for statement in connection.statements[expected_trigger_drops:]
    )


def test_integrity_installer_refuses_non_postgresql_connection() -> None:
    with pytest.raises(ValueError, match="require a PostgreSQL connection"):
        install_postgresql_integrity_guards(  # type: ignore[arg-type]
            RecordingConnection("sqlite")
        )


def test_forward_migration_and_ci_own_production_integrity_guards() -> None:
    migration = (
        ROOT / "migrations/versions/24aaca5b4358_initial_cloud_schema.py"
    ).read_text(encoding="utf-8")
    forward = (
        ROOT
        / "migrations/versions/8f2d31c4a9b7_install_postgres_integrity_guards.py"
    ).read_text(encoding="utf-8")
    database = (ROOT / "app/database.py").read_text(encoding="utf-8")
    verifier = (ROOT / "scripts/verify_postgres_integrity.py").read_text(
        encoding="utf-8"
    )
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "install_postgresql_integrity_guards(bind)" in migration
    assert "drop_postgresql_integrity_guards(bind)" in migration
    assert "install_postgresql_integrity_guards(bind)" in forward
    assert 'down_revision: Union[str, Sequence[str], None] = "5b7130c8f42e"' in forward
    assert "install_postgresql_integrity_guards(connection)" in database
    assert "pg_catalog.pg_trigger" in verifier
    assert "pg_catalog.pg_proc" in verifier
    assert "python scripts/verify_postgres_integrity.py" in ci
    assert "python -m alembic upgrade 24aaca5b4358" in ci
