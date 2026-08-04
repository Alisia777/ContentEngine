from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040014_research_trend_velocity_and_readiness_truth.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "research_market_intelligence_identity_test.sql"
VIEW = ROOT / "web" / "app" / "product-research-view.js"
APP = ROOT / "web" / "app" / "app.js"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_velocity_migration_and_pgtap_are_postgresql_syntax() -> None:
    assert parse_sql(_text(MIGRATION))
    assert parse_sql(_text(PGTAP))


def test_velocity_is_approved_support_not_platform_performance() -> None:
    sql = _text(MIGRATION)

    assert "approved-structural-support-velocity-v1" in sql
    assert "research_watchlist_trend_velocity_events" in sql
    assert "research_watchlist_snapshot_trend_signal_sources" in sql
    assert "research_watchlist_snapshot_sources" in sql
    assert "10000.0 * current_count_value / current_total_value" in sql
    assert "delta_value::numeric * 2592000::numeric / elapsed_value::numeric" in sql
    assert "elapsed_value < 259200" in sql
    assert "elapsed_seconds bigint check (elapsed_seconds >= 0)" in sql
    assert "if elapsed_value < 0 then" in sql
    assert "'category_reset'" in sql
    assert "'signal_new'" in sql
    assert "'signal_removed'" in sql
    assert "'interval_too_short'" in sql
    assert "current_snapshot.previous_snapshot_id" in sql
    assert "research_watchlist_trend_velocity_events_append_only" not in sql
    assert "reject_research_watchlist_memory_mutation" in sql
    assert "grant all on content_factory.research_watchlist_trend_velocity_events" not in sql
    assert "event.snapshot_version desc" in sql

    capture = sql.split(
        "create or replace function content_factory_private.capture_research_snapshot_trend_velocity(",
        1,
    )[1].split("-- Snapshot rows fire", 1)[0]
    assert capture.index("elsif snapshot_category_reset then") < capture.index(
        "elsif current_signal.snapshot_id is null then"
    )
    for marker in (
        "current_binding_value is null",
        "current_category_value is null",
        "previous_binding_value is null",
        "previous_category_value is null",
    ):
        assert marker in capture

    velocity_section = sql.split(
        "create table content_factory.research_watchlist_trend_velocity_events",
        1,
    )[1].split("-- Readiness v2", 1)[0].lower()
    for forbidden in (
        "view_count",
        "like_count",
        "comment_count",
        "video_id",
        "channel_id",
        "raw_caption",
        "transcript",
    ):
        assert forbidden not in velocity_section


def test_velocity_capture_runs_after_completed_snapshot_source_junction() -> None:
    sql = _text(MIGRATION)
    wrapper = sql.split(
        "create or replace function content_factory_private.capture_research_watchlist_snapshot(",
        1,
    )[1].split("do $backfill$", 1)[0]

    base_call = wrapper.index(
        "capture_research_watchlist_snapshot_pre_velocity_v1"
    )
    velocity_call = wrapper.index("capture_research_snapshot_trend_velocity")
    assert base_call < velocity_call
    assert "if snapshot_id_value is not null" in wrapper
    assert "on conflict (organization_id, snapshot_id, signal_key) do nothing" in sql


def test_readiness_v2_removes_raw_youtube_semantic_credit() -> None:
    sql = _text(MIGRATION)
    readiness = sql.split(
        "create or replace function content_factory_private.research_category_evidence_readiness(",
        1,
    )[1].split(
        "alter table content_factory.research_category_readiness_snapshots",
        1,
    )[0]

    assert "category-evidence-readiness-v2" in readiness
    assert "youtube_confirmed_channel_count_value integer := 0" in readiness
    assert (
        "competitor_count_value + youtube_confirmed_channel_count_value"
        in readiness
    )
    assert "analysis_count_value := analysis_count_value +" not in readiness
    assert "where evidence.decision = 'confirm_candidate'" in readiness
    assert "original_source.created_at desc" in readiness
    assert "research_category_evidence_readiness_v1_base" in sql
    assert "category-evidence-readiness-v1" in sql
    assert "category-evidence-readiness-snapshot-v2" in sql
    assert "Competitor observations / confirmed YouTube channels" in readiness


def test_ui_names_the_metric_and_routes_to_human_trend_correction() -> None:
    view = _text(VIEW)
    app = _text(APP)

    assert "Скорость доказательной поддержки" in view
    assert "не просмотры, не продажи" in view
    assert 'data-action="focus-research-trends-stage"' in view
    assert 'action === "focus-research-trends-stage"' in app
    assert 'document.querySelector(\'[data-research-stage="trends"]\')' in app
    assert 'textarea[name="trend_correction"]' in app
    assert "Гипотеза не становится конкурентом или трендом без решения человека" in view
    assert "Сырые YouTube-метаданные" in view
    assert "analysis coverage появляется лишь после точного локального parser head" in view
    assert "Формула изменена" in view
    assert "velocityContractValid" in view
    assert "supportState !== expectedSupportState" in view
    assert "supportDeltaBps !== expectedDelta" in view
    assert "elapsedSeconds: 0" not in view


def test_pgtap_covers_reset_zero_interval_unbound_and_rpc_boundaries() -> None:
    pgtap = _text(PGTAP)

    for marker in (
        "a signal introduced across a category boundary is a reset",
        "equal approved timestamps stay fail-closed",
        "a zero-second interval never becomes a numeric velocity claim",
        "two unbound snapshots never manufacture a comparable velocity claim",
        "service role cannot bypass the tenant-scoped registry and capture RPCs",
    ):
        assert marker in pgtap
