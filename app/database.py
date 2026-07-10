from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
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


def _ensure_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
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
            "local_output_paths_json": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN local_output_paths_json TEXT DEFAULT '[]'",
            "generation_report_path": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN generation_report_path VARCHAR(1000)",
            "human_review_status": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN human_review_status VARCHAR(80) DEFAULT 'not_generated'",
            "publishing_readiness": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN publishing_readiness VARCHAR(80) DEFAULT 'blocked'",
            "human_review_notes": "ALTER TABLE product_ugc_recipe_drafts ADD COLUMN human_review_notes TEXT",
        },
    )


def _add_missing_sqlite_columns(inspector, table_name: str, migrations: dict[str, str]) -> None:
    if table_name not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as connection:
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(text(statement))
