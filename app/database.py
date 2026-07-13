from collections.abc import Generator
from pathlib import Path
import sys

from sqlalchemy import create_engine, event
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings
from app.postgres_integrity import install_postgresql_integrity_guards


class Base(DeclarativeBase):
    pass


settings = get_settings()


def _refuse_workspace_database_under_pytest(database_url: str) -> None:
    """A test process must never bind the global engine to production-like data."""

    if "pytest" not in sys.modules:
        return
    parsed = make_url(database_url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database:
        return
    if Path(parsed.database).name.casefold() == "qharisma.db":
        raise RuntimeError(
            "Refusing to open qharisma.db from pytest; configure an isolated test database."
        )


_refuse_workspace_database_under_pytest(settings.database_url)
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_options = {"connect_args": connect_args}
if not settings.database_url.startswith("sqlite"):
    # Supabase/managed poolers can recycle server connections independently of
    # the web process; validate a checkout before handing it to a request.
    engine_options.update({"pool_pre_ping": True, "pool_recycle": 300})
engine = create_engine(settings.database_url, **engine_options)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema()
    if engine.dialect.name != "sqlite":
        _ensure_product_ugc_generation_queue_schema(engine)
    _ensure_customer_billing_schema(engine)
    _ensure_visual_evidence_schema(engine)
    _ensure_wildberries_seller_analytics_schema(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            install_postgresql_integrity_guards(connection)


def _ensure_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    _ensure_generation_cost_ledger_schema(engine)
    _ensure_product_ugc_generation_queue_schema(engine)
    inspector = inspect(engine)
    if "script_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("script_jobs")}
    migrations = {
        "llm_provider": "ALTER TABLE script_jobs ADD COLUMN llm_provider VARCHAR(120)",
        "llm_model": "ALTER TABLE script_jobs ADD COLUMN llm_model VARCHAR(160)",
        "llm_request_json": "ALTER TABLE script_jobs ADD COLUMN llm_request_json TEXT DEFAULT '{}'",
        "llm_response_json": "ALTER TABLE script_jobs ADD COLUMN llm_response_json TEXT DEFAULT '{}'",
    }
    with engine.begin() as connection:
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(text(statement))
    if "video_generation_variants" in inspector.get_table_names():
        variant_columns = {column["name"] for column in inspector.get_columns("video_generation_variants")}
        with engine.begin() as connection:
            if "creative_variant_id" not in variant_columns:
                connection.execute(text("ALTER TABLE video_generation_variants ADD COLUMN creative_variant_id INTEGER"))
    _add_missing_sqlite_columns(
        inspector,
        "product_asset_kits",
        {
            "primary_reference_asset_id": "ALTER TABLE product_asset_kits ADD COLUMN primary_reference_asset_id INTEGER",
            "provider_reference_bundle_json": "ALTER TABLE product_asset_kits ADD COLUMN provider_reference_bundle_json TEXT DEFAULT '{}'",
            "real_generation_blockers_json": "ALTER TABLE product_asset_kits ADD COLUMN real_generation_blockers_json TEXT DEFAULT '[]'",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "product_assets",
        {
            "asset_role": "ALTER TABLE product_assets ADD COLUMN asset_role VARCHAR(80)",
            "is_primary_reference": "ALTER TABLE product_assets ADD COLUMN is_primary_reference BOOLEAN DEFAULT 0",
            "is_safe_for_real_generation": "ALTER TABLE product_assets ADD COLUMN is_safe_for_real_generation BOOLEAN DEFAULT 0",
            "manual_label": "ALTER TABLE product_assets ADD COLUMN manual_label VARCHAR(255)",
            "review_status": "ALTER TABLE product_assets ADD COLUMN review_status VARCHAR(80) DEFAULT 'pending'",
            "review_notes": "ALTER TABLE product_assets ADD COLUMN review_notes TEXT",
            "checksum": "ALTER TABLE product_assets ADD COLUMN checksum VARCHAR(128)",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "publishing_packages",
        {
            "creative_variant_id": "ALTER TABLE publishing_packages ADD COLUMN creative_variant_id INTEGER",
            "review_status": "ALTER TABLE publishing_packages ADD COLUMN review_status VARCHAR(80) DEFAULT 'needs_review'",
            "organization_id": "ALTER TABLE publishing_packages ADD COLUMN organization_id INTEGER",
            "media_artifact_id": "ALTER TABLE publishing_packages ADD COLUMN media_artifact_id INTEGER",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "creative_quality_scores",
        {
            "product_strategy_spec_id": "ALTER TABLE creative_quality_scores ADD COLUMN product_strategy_spec_id INTEGER",
            "offer_alignment_score": "ALTER TABLE creative_quality_scores ADD COLUMN offer_alignment_score FLOAT DEFAULT 0",
            "platform_fit_score": "ALTER TABLE creative_quality_scores ADD COLUMN platform_fit_score FLOAT DEFAULT 0",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "product_ugc_recipe_drafts",
        {
            "created_by_user_profile_id": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN created_by_user_profile_id INTEGER",
            "assigned_to_user_profile_id": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN assigned_to_user_profile_id INTEGER",
            "local_output_paths_json": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN local_output_paths_json TEXT DEFAULT '[]'",
            "generation_report_path": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN generation_report_path VARCHAR(1000)",
            "human_review_status": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN human_review_status VARCHAR(80) DEFAULT 'not_generated'",
            "publishing_readiness": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN publishing_readiness VARCHAR(80) DEFAULT 'blocked'",
            "human_review_notes": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN human_review_notes TEXT",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "campaigns",
        {
            "organization_id": "ALTER TABLE campaigns ADD COLUMN organization_id INTEGER",
            "created_by_user_profile_id": "ALTER TABLE campaigns ADD COLUMN created_by_user_profile_id INTEGER",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "video_jobs",
        {
            "organization_id": "ALTER TABLE video_jobs ADD COLUMN organization_id INTEGER",
            "created_by_user_profile_id": "ALTER TABLE video_jobs ADD COLUMN created_by_user_profile_id INTEGER",
            "product_id": "ALTER TABLE video_jobs ADD COLUMN product_id INTEGER",
            "source_product_ugc_draft_id": "ALTER TABLE video_jobs ADD COLUMN source_product_ugc_draft_id INTEGER",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "frame_extraction_results",
        {
            "extraction_key": "ALTER TABLE frame_extraction_results ADD COLUMN extraction_key VARCHAR(80)",
            "source_video_sha256": "ALTER TABLE frame_extraction_results ADD COLUMN source_video_sha256 VARCHAR(64)",
            "source_video_size_bytes": "ALTER TABLE frame_extraction_results ADD COLUMN source_video_size_bytes INTEGER",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "video_output_acceptances",
        {
            "visual_evidence_snapshot_id": "ALTER TABLE video_output_acceptances ADD COLUMN visual_evidence_snapshot_id INTEGER",
        },
    )
    _add_missing_sqlite_columns(
        inspector,
        "publishing_destinations",
        {
            "organization_id": "ALTER TABLE publishing_destinations ADD COLUMN organization_id INTEGER",
        },
    )
    if "video_jobs" in inspector.get_table_names():
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_video_job_product_ugc_source "
                    "ON video_jobs (source_product_ugc_draft_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_video_jobs_organization_id "
                    "ON video_jobs (organization_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_video_jobs_product_id "
                    "ON video_jobs (product_id)"
                )
            )
    if "publishing_destinations" in inspector.get_table_names():
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_publishing_destinations_organization_id "
                    "ON publishing_destinations (organization_id)"
                )
            )
    if "products" in inspector.get_table_names():
        product_columns = {column["name"] for column in inspector.get_columns("products")}
        if "organization_id" not in product_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE products ADD COLUMN organization_id INTEGER"))
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_products_organization_id "
                    "ON products (organization_id, id)"
                )
            )


def _ensure_generation_cost_ledger_schema(bind) -> None:
    """Create the append-only generation-cost ledger on legacy SQLite DBs."""

    from app import models

    models.GenerationCostLedgerEntry.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "sqlite":
        with bind.begin() as connection:
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS generation_cost_ledger_no_update "
                    "BEFORE UPDATE ON generation_cost_ledger_entries "
                    "BEGIN SELECT RAISE(ABORT, 'generation cost ledger is append-only'); END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS generation_cost_ledger_no_delete "
                    "BEFORE DELETE ON generation_cost_ledger_entries "
                    "BEGIN SELECT RAISE(ABORT, 'generation cost ledger is append-only'); END"
                )
            )


def _ensure_product_ugc_generation_queue_schema(bind) -> None:
    """Install durable queue operations and immutable reconciliation audit."""

    from app import models

    for table in (
        models.ProductUGCGenerationJob.__table__,
        models.ProductUGCQueueWorkerHeartbeat.__table__,
        models.ProductUGCQueueReconciliation.__table__,
    ):
        table.create(bind=bind, checkfirst=True)
    heartbeat_columns = {
        column["name"]
        for column in inspect(bind).get_columns("product_ugc_queue_worker_heartbeats")
    }
    if "is_supervised" not in heartbeat_columns:
        with bind.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE product_ugc_queue_worker_heartbeats "
                    "ADD COLUMN is_supervised BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
    reconciliation_columns = {
        column["name"]
        for column in inspect(bind).get_columns("product_ugc_queue_reconciliations")
    }
    if "quarantine_incident_key" not in reconciliation_columns:
        with bind.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE product_ugc_queue_reconciliations "
                    "ADD COLUMN quarantine_incident_key VARCHAR(64)"
                )
            )
    if bind.dialect.name == "sqlite":
        with bind.begin() as connection:
            # Explicit indexes keep upgrades deterministic even when the table
            # originated from an early development build without ORM indexes.
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_ugc_generation_job_draft "
                    "ON product_ugc_generation_jobs (draft_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_ugc_generation_job_idempotency "
                    "ON product_ugc_generation_jobs (idempotency_key)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_ugc_generation_job_provider_task "
                    "ON product_ugc_generation_jobs (provider, provider_task_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS product_ugc_queue_reconciliation_no_update "
                    "BEFORE UPDATE ON product_ugc_queue_reconciliations "
                    "BEGIN SELECT RAISE(ABORT, 'product ugc queue reconciliation is append-only'); END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS product_ugc_queue_reconciliation_no_delete "
                    "BEFORE DELETE ON product_ugc_queue_reconciliations "
                    "BEGIN SELECT RAISE(ABORT, 'product ugc queue reconciliation is append-only'); END"
                )
            )
        return


def _ensure_customer_billing_schema(bind) -> None:
    """Install isolated append-only customer billing tables and SQLite guards."""

    from app import models

    billing_tables = (
        models.CustomerBillingAccount.__table__,
        models.CustomerBillingSubscriptionState.__table__,
        models.CustomerInvoice.__table__,
        models.CustomerBillingLedgerEntry.__table__,
    )
    for table in billing_tables:
        table.create(bind=bind, checkfirst=True)

    if bind.dialect.name == "sqlite":
        trigger_tables = {
            "customer_billing_accounts": "customer_billing_account",
            "customer_billing_subscription_states": "customer_billing_subscription",
            "customer_invoices": "customer_invoice",
            "customer_billing_ledger_entries": "customer_billing_ledger",
        }
        with bind.begin() as connection:
            for table_name, trigger_prefix in trigger_tables.items():
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_no_update "
                        f"BEFORE UPDATE ON {table_name} "
                        "BEGIN SELECT RAISE(ABORT, 'customer billing records are append-only'); END"
                    )
                )
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_no_delete "
                        f"BEFORE DELETE ON {table_name} "
                        "BEGIN SELECT RAISE(ABORT, 'customer billing records are append-only'); END"
                    )
                )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS customer_billing_ledger_no_overapply "
                    "BEFORE INSERT ON customer_billing_ledger_entries "
                    "WHEN NEW.entry_kind IN ('credit', 'payment') AND NEW.amount_minor > ("
                    "SELECT COALESCE(SUM(CASE WHEN entry_kind = 'charge' THEN amount_minor "
                    "ELSE -amount_minor END), 0) FROM customer_billing_ledger_entries "
                    "WHERE invoice_id = NEW.invoice_id AND organization_id = NEW.organization_id"
                    ") BEGIN SELECT RAISE(ABORT, 'customer billing entry exceeds outstanding balance'); END"
                )
            )


def _ensure_visual_evidence_schema(bind) -> None:
    """Upgrade immutable evidence storage and install mutation guards.

    ``create_all`` only creates missing tables. The explicit ALTER statements
    below are therefore required for production databases created before exact
    source/frame evidence and acceptance binding were introduced.
    """

    from app import models

    models.VisualEvidenceSnapshot.__table__.create(bind=bind, checkfirst=True)
    if bind.dialect.name == "sqlite":
        with bind.begin() as connection:
            snapshot_columns = {
                column["name"] for column in inspect(bind).get_columns("visual_evidence_snapshots")
            }
            if "report_sha256" not in snapshot_columns:
                connection.execute(
                    text(
                        "ALTER TABLE visual_evidence_snapshots "
                        "ADD COLUMN report_sha256 VARCHAR(64)"
                    )
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_frame_extraction_key "
                    "ON frame_extraction_results (extraction_key)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_frame_extraction_results_source_video_sha256 "
                    "ON frame_extraction_results (source_video_sha256)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_video_output_acceptances_visual_evidence_snapshot_id "
                    "ON video_output_acceptances (visual_evidence_snapshot_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_visual_evidence_snapshots_report_sha256 "
                    "ON visual_evidence_snapshots (report_sha256)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_visual_evidence_extraction_manifest_policy_report "
                    "ON visual_evidence_snapshots "
                    "(frame_extraction_result_id, frame_manifest_sha256, "
                    "policy_sha256, report_sha256)"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS visual_evidence_snapshot_no_update "
                    "BEFORE UPDATE ON visual_evidence_snapshots "
                    "BEGIN SELECT RAISE(ABORT, 'visual evidence snapshots are append-only'); END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS visual_evidence_snapshot_no_delete "
                    "BEFORE DELETE ON visual_evidence_snapshots "
                    "BEGIN SELECT RAISE(ABORT, 'visual evidence snapshots are append-only'); END"
                )
            )
    elif bind.dialect.name == "postgresql":
        with bind.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE frame_extraction_results "
                    "ADD COLUMN IF NOT EXISTS extraction_key VARCHAR(80), "
                    "ADD COLUMN IF NOT EXISTS source_video_sha256 VARCHAR(64), "
                    "ADD COLUMN IF NOT EXISTS source_video_size_bytes INTEGER"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE visual_evidence_snapshots "
                    "ADD COLUMN IF NOT EXISTS report_sha256 VARCHAR(64)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE video_output_acceptances "
                    "ADD COLUMN IF NOT EXISTS visual_evidence_snapshot_id INTEGER"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_frame_extraction_key "
                    "ON frame_extraction_results (extraction_key)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_frame_extraction_results_source_video_sha256 "
                    "ON frame_extraction_results (source_video_sha256)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_video_output_acceptances_visual_evidence_snapshot_id "
                    "ON video_output_acceptances (visual_evidence_snapshot_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_visual_evidence_snapshots_report_sha256 "
                    "ON visual_evidence_snapshots (report_sha256)"
                )
            )
            # The earlier three-column identity omitted OCR references and
            # expected tokens. Replace it with the full report fingerprint.
            connection.execute(
                text(
                    "ALTER TABLE visual_evidence_snapshots DROP CONSTRAINT IF EXISTS "
                    "uq_visual_evidence_extraction_manifest_policy"
                )
            )
            connection.execute(
                text(
                    "DROP INDEX IF EXISTS uq_visual_evidence_extraction_manifest_policy"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_visual_evidence_extraction_manifest_policy_report "
                    "ON visual_evidence_snapshots "
                    "(frame_extraction_result_id, frame_manifest_sha256, "
                    "policy_sha256, report_sha256)"
                )
            )
            connection.execute(
                text(
                    "DO $$ BEGIN IF NOT EXISTS ("
                    "SELECT 1 FROM pg_constraint WHERE conname = "
                    "'fk_video_output_acceptance_visual_evidence_snapshot'"
                    ") THEN ALTER TABLE video_output_acceptances ADD CONSTRAINT "
                    "fk_video_output_acceptance_visual_evidence_snapshot "
                    "FOREIGN KEY (visual_evidence_snapshot_id) "
                    "REFERENCES visual_evidence_snapshots(id); "
                    "END IF; END; $$;"
                )
            )


def _ensure_wildberries_seller_analytics_schema(bind) -> None:
    """Install org-scoped WB evidence tables and database mutation guards."""

    from app import models

    for table in (
        models.WildberriesAnalyticsConnection.__table__,
        models.WildberriesAnalyticsSyncAudit.__table__,
        models.WildberriesMetricSnapshot.__table__,
        models.WildberriesMetricQuarantine.__table__,
    ):
        table.create(bind=bind, checkfirst=True)

    immutable_tables = (
        "wildberries_analytics_sync_audits",
        "wildberries_metric_snapshots",
        "wildberries_metric_quarantine",
    )
    if bind.dialect.name == "sqlite":
        with bind.begin() as connection:
            for table_name in immutable_tables:
                trigger_prefix = table_name.removesuffix("s")
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_no_update "
                        f"BEFORE UPDATE ON {table_name} "
                        "BEGIN SELECT RAISE(ABORT, 'Wildberries analytics evidence is append-only'); END"
                    )
                )
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {trigger_prefix}_no_delete "
                        f"BEFORE DELETE ON {table_name} "
                        "BEGIN SELECT RAISE(ABORT, 'Wildberries analytics evidence is append-only'); END"
                    )
                )


def _add_missing_sqlite_columns(inspector, table_name: str, migrations: dict[str, str]) -> None:
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as connection:
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(text(statement))
