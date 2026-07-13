from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.postgres_security import (
    SUPABASE_API_ROLES,
    inspect_postgresql_public_schema_security,
    install_postgresql_public_schema_security,
)


ROOT = Path(__file__).resolve().parents[1]


class _MappingResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self):
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows


class _RecordingConnection:
    def __init__(
        self,
        dialect_name: str = "postgresql",
        *,
        rows: list[dict[str, object]] | None = None,
    ) -> None:
        self.dialect = SimpleNamespace(name=dialect_name)
        self.rows = rows or []
        self.statements: list[tuple[str, dict[str, object] | None]] = []

    def execute(self, statement, parameters=None):
        self.statements.append((" ".join(str(statement).split()), parameters))
        return _MappingResult(self.rows)


def test_installer_enables_rls_and_removes_only_database_api_object_privileges() -> None:
    connection = _RecordingConnection()

    install_postgresql_public_schema_security(connection)  # type: ignore[arg-type]

    ddl = "\n".join(statement for statement, _params in connection.statements)
    assert "ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY" in ddl
    assert "FORCE ROW LEVEL SECURITY" not in ddl
    assert "pg_catalog.pg_depend" in ddl
    assert "object_dependency.deptype = 'e'" in ddl
    assert "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public" in ddl
    assert "REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public" in ddl
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON TABLES"
    ) in ddl
    assert (
        "ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON SEQUENCES"
    ) in ddl
    assert "current_user" in ddl
    for role_name in SUPABASE_API_ROLES:
        assert role_name in ddl

    # Auth and Storage still need schema/extension-function access.  This
    # migration revokes only table and sequence object privileges.
    assert "REVOKE USAGE ON SCHEMA" not in ddl
    assert "ON ALL FUNCTIONS" not in ddl
    assert "ALTER FUNCTION" not in ddl
    assert "FROM current_user" not in ddl


def test_installer_refuses_non_postgresql_connection() -> None:
    with pytest.raises(ValueError, match="requires PostgreSQL"):
        install_postgresql_public_schema_security(  # type: ignore[arg-type]
            _RecordingConnection("sqlite")
        )


def test_security_inspection_requires_every_table_and_effective_role_isolation() -> None:
    connection = _RecordingConnection(
        rows=[
            {
                "table_name": "organizations",
                "rls_enabled": True,
                "api_role_has_privilege": False,
            },
            {
                "table_name": "memberships",
                "rls_enabled": True,
                "api_role_has_privilege": False,
            },
        ]
    )

    result = inspect_postgresql_public_schema_security(  # type: ignore[arg-type]
        connection,
        {"organizations", "memberships"},
    )

    assert result.rls_enabled is True
    assert result.api_roles_restricted is True
    sql, parameters = connection.statements[0]
    assert "FROM pg_catalog.pg_roles AS api_role" in sql
    assert "EXISTS" in sql
    assert "has_table_privilege" in sql
    assert "has_any_column_privilege" in sql
    assert parameters == {"table_names": ("memberships", "organizations")}


def test_security_inspection_treats_missing_supabase_roles_as_secure() -> None:
    # The database computes api_role_has_privilege with a correlated EXISTS.
    # If none of the named roles exists, that expression is false.
    connection = _RecordingConnection(
        rows=[
            {
                "table_name": "organizations",
                "rls_enabled": True,
                "api_role_has_privilege": False,
            }
        ]
    )

    result = inspect_postgresql_public_schema_security(  # type: ignore[arg-type]
        connection,
        {"organizations"},
    )

    assert result.rls_enabled is True
    assert result.api_roles_restricted is True


@pytest.mark.parametrize(
    ("rows", "expected_rls", "expected_restricted"),
    [
        (
            [
                {
                    "table_name": "organizations",
                    "rls_enabled": False,
                    "api_role_has_privilege": False,
                }
            ],
            False,
            True,
        ),
        (
            [
                {
                    "table_name": "organizations",
                    "rls_enabled": True,
                    "api_role_has_privilege": True,
                }
            ],
            True,
            False,
        ),
        ([], False, False),
    ],
)
def test_security_inspection_fails_closed(
    rows: list[dict[str, object]],
    expected_rls: bool,
    expected_restricted: bool,
) -> None:
    result = inspect_postgresql_public_schema_security(  # type: ignore[arg-type]
        _RecordingConnection(rows=rows),
        {"organizations"},
    )

    assert result.rls_enabled is expected_rls
    assert result.api_roles_restricted is expected_restricted


def test_security_revision_is_after_current_head_and_sqlite_is_a_safe_noop(
    monkeypatch,
) -> None:
    migration_path = (
        ROOT
        / "migrations/versions/c8a91f6e2d44_harden_supabase_public_schema.py"
    )
    specification = importlib.util.spec_from_file_location(
        "contentengine_security_migration",
        migration_path,
    )
    assert specification is not None and specification.loader is not None
    migration = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(migration)

    called = False

    def unexpected_install(_connection) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        migration,
        "op",
        SimpleNamespace(
            get_bind=lambda: _RecordingConnection("sqlite"),
        ),
    )
    monkeypatch.setattr(
        migration,
        "install_postgresql_public_schema_security",
        unexpected_install,
    )

    assert migration.down_revision == "8f2d31c4a9b7"
    migration.upgrade()
    migration.downgrade()
    assert called is False


def test_ci_and_cloud_runbook_enforce_public_schema_security_contract() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/CLOUD_DEPLOYMENT.md").read_text(encoding="utf-8")
    readiness = (ROOT / "app/readiness.py").read_text(encoding="utf-8")

    assert "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public" in workflow
    assert "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public" in workflow
    assert "python scripts/verify_postgres_schema_security.py" in workflow
    assert "Disable the **Data API**" in runbook
    assert "database_rls" in readiness
    assert "database_api_roles_restricted" in readiness
