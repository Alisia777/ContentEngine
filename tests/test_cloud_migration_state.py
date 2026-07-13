from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from app.migration_state import (
    MIGRATION_ADVISORY_LOCK_ID,
    database_is_at_migration_head,
    expected_migration_heads,
    serialized_database_migration,
)


ROOT = Path(__file__).resolve().parents[1]


def test_live_alembic_revision_must_equal_repository_head() -> None:
    expected_migration_heads.cache_clear()
    expected = expected_migration_heads()
    assert expected == frozenset({"c8a91f6e2d44"})

    database = create_engine("sqlite:///:memory:")
    with database.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('5b7130c8f42e')")
        )
    with database.connect() as connection:
        assert not database_is_at_migration_head(connection)
        connection.execute(
            text("UPDATE alembic_version SET version_num = '8f2d31c4a9b7'")
        )
        assert not database_is_at_migration_head(connection)
        connection.execute(
            text("UPDATE alembic_version SET version_num = 'c8a91f6e2d44'")
        )
        assert database_is_at_migration_head(connection)


class _RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, dict | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((" ".join(str(statement).split()), parameters))


class _RecordingPostgresEngine:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self) -> None:
        self.connection = _RecordingConnection()

    def connect(self):
        return self.connection


def test_postgresql_migrations_are_serialized_by_bounded_advisory_lock() -> None:
    database = _RecordingPostgresEngine()
    events: list[str] = []

    with serialized_database_migration(database):  # type: ignore[arg-type]
        events.append("migration")

    statements = database.connection.statements
    assert events == ["migration"]
    assert statements[0][0] == "SET lock_timeout = '10min'"
    assert "pg_advisory_lock" in statements[1][0]
    assert statements[1][1] == {"lock_id": MIGRATION_ADVISORY_LOCK_ID}
    assert "pg_advisory_unlock" in statements[-1][0]


def test_reference_alembic_guard_remains_while_production_uses_supabase_migrations() -> None:
    forward = (
        ROOT
        / "migrations/versions/8f2d31c4a9b7_install_postgres_integrity_guards.py"
    ).read_text(encoding="utf-8")
    security = (
        ROOT
        / "migrations/versions/c8a91f6e2d44_harden_supabase_public_schema.py"
    ).read_text(encoding="utf-8")
    production = (ROOT / ".github/workflows/supabase-pages.yml").read_text(
        encoding="utf-8"
    )
    predeploy = (ROOT / "scripts/predeploy.py").read_text(encoding="utf-8")
    worker = (ROOT / "scripts/run_product_ugc_queue_worker.py").read_text(
        encoding="utf-8"
    )
    web = (ROOT / "app/main.py").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert 'down_revision: Union[str, Sequence[str], None] = "5b7130c8f42e"' in forward
    assert "install_postgresql_integrity_guards(bind)" in forward
    assert 'down_revision: Union[str, Sequence[str], None] = "8f2d31c4a9b7"' in security
    assert "install_postgresql_public_schema_security(bind)" in security
    assert not (ROOT / "render.yaml").exists()
    assert "supabase db push --linked" in production
    assert "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e" in production
    assert "migrate" in production
    assert predeploy.index("validate_runtime_settings") < predeploy.index("command.upgrade")
    assert "serialized_database_migration(engine)" in predeploy
    assert "require_database_at_migration_head(connection)" in predeploy
    assert "require_database_at_migration_head(connection)" in worker
    assert web.index("require_database_at_migration_head(connection)") < web.index(
        "reconcile_stale()"
    )
    assert "python -m alembic upgrade 24aaca5b4358" in ci
    assert "drop_postgresql_integrity_guards" in ci
