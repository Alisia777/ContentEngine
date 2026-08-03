from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608030011_research_category_learning_readiness.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "research_category_learning_readiness_test.sql"
)


def _migration() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _function(sql: str, qualified_name: str, next_marker: str) -> str:
    marker = f"create or replace function {qualified_name}"
    if marker not in sql:
        marker = f"create or replace function\n{qualified_name}"
    start = sql.index(marker)
    end = sql.index(next_marker, start)
    return sql[start:end]


def test_sql_and_pgtap_are_postgresql_syntax() -> None:
    assert parse_sql(_migration())
    assert parse_sql(PGTAP.read_text(encoding="utf-8"))


def test_analysis_schema_is_exact_and_rejects_raw_provider_text() -> None:
    sql = _migration()
    validator = _function(
        sql,
        "content_factory_private.research_source_analysis_is_valid",
        "create or replace function content_factory_private.research_source_identity_key",
    )

    required = {
        "schema_version",
        "classification",
        "relevance_score",
        "confidence",
        "summary",
        "structural_signal_keys",
        "limitations",
    }
    for key in required:
        assert f"'{key}'" in validator
    assert "research-source-interpretation-v1" in validator
    assert "value - array[" in validator
    assert "value ?& array[" in validator
    assert "research_analysis_has_forbidden_keys(value)" in validator
    assert "jsonb_array_length(value -> 'structural_signal_keys') > 20" in validator
    assert "signal_value = any(seen_signals)" in validator

    forbidden = _function(
        sql,
        "content_factory_private.research_analysis_has_forbidden_keys",
        "create or replace function content_factory_private.research_source_analysis_is_valid",
    )
    for key in (
        "raw_caption",
        "raw_captions",
        "transcript",
        "raw_transcript",
        "raw_text",
        "source_text",
        "full_text",
    ):
        assert f"'{key}'" in forbidden
    assert "object_entry.key" in forbidden
    assert "object_entry.value" in forbidden


def test_readiness_is_evidence_coverage_not_model_iq() -> None:
    sql = _migration()
    readiness = _function(
        sql,
        "content_factory_private.research_category_evidence_readiness",
        "create or replace function public.creator_research_category_learning_status",
    )

    expected_dimensions = {
        "source_volume": 20,
        "platform_diversity": 15,
        "competitor_observations": 20,
        "trend_recency": 15,
        "analysis_coverage": 15,
        "human_validation": 15,
    }
    for key, weight in expected_dimensions.items():
        assert f"'{key}'" in readiness
        assert f", {weight}," in readiness
    assert sum(expected_dimensions.values()) == 100
    assert "category_evidence_readiness_not_model_iq" in readiness
    assert "'is_model_iq', false" in readiness
    assert "'is_quality_guarantee', false" in readiness
    assert "count(distinct evidence.channel_id)" in readiness
    assert "observed.decision is distinct from 'exclude_candidate'" in readiness
    assert "observation.retention_expires_at > as_of_value" in readiness
    assert "observation.observed_at <= as_of_value" in readiness
    assert "analysis.classification is distinct from 'irrelevant'" in readiness
    assert "source.classification = 'competitor'" in readiness
    assert "source.source_type in ('competitor', 'social_video')" not in readiness


def test_persisted_parser_is_bounded_allowlisted_and_anti_copy() -> None:
    sql = _migration()
    parser = _function(
        sql,
        "content_factory_private.bootstrap_persisted_research_source_analyses",
        "create or replace function public.system_register_research_category_sources",
    )

    assert "draft.origin = 'ai'" in parser
    assert "coalesce(evidence_value, run_row.summary, '{}'::jsonb)" in parser
    assert "metadata ->> 'model_source_id'" in parser
    assert "metadata ->> 'original_source_type'" in parser
    assert "limit 24" in parser
    assert "research_structural_trend_signal_types" in parser
    assert "catalog.status = 'active'" in parser
    assert "when competitor_cited_value then 'competitor'" in parser
    assert "when trend_cited_value then 'trend_signal'" in parser
    assert parser.index("when competitor_cited_value then 'competitor'") < parser.index(
        "when trend_cited_value then 'trend_signal'"
    )
    assert "'input_photo', 'official', 'marketplace', 'product_page'" in parser
    assert "'review', 'editorial', 'social'" in parser
    assert "source_row.metadata ->> 'classification'" not in parser
    assert "source_row.title" not in parser
    assert "extracted_facts" not in parser
    assert "source.type." not in parser
    assert "source.platform." not in parser
    assert "source.trust." not in parser
    assert "No provider-authored prose, title, extracted fact" in parser
    assert "research_source_analysis_events event" in parser
    assert "continue;" in parser
    assert "system_record_research_source_analysis" in parser
    assert "'external_call_started', false" in parser


def test_completion_and_first_category_resolution_close_the_lifecycle() -> None:
    sql = _migration()
    completion = _function(
        sql,
        "public.system_complete_product_research",
        "-- Category confirmation is the guaranteed local lifecycle edge",
    )
    resolution = _function(
        sql,
        "public.creator_resolve_research_market_category",
        "revoke all on function",
    )
    registration = _function(
        sql,
        "public.system_register_research_category_sources",
        "-- Keep product-research completion",
    )

    assert "complete_product_research_v2_base(p_payload)" in completion
    assert "completion_value ->> 'status' = 'completed'" in completion
    assert "system_register_research_category_sources" in completion
    assert "research_product_market_category_bindings" in completion
    assert "return completion_value" in completion

    assert "resolve_research_market_category_v1_base(p_payload)" in resolution
    assert "system_register_research_category_sources" in resolution
    assert "return resolution_value" in resolution
    assert "bootstrap_persisted_research_source_analyses" in registration
    assert "on conflict do nothing" in registration
    assert "source_content_hash = source.content_hash" in registration
    assert "'item_limit', 100" in registration


def test_status_is_read_only_and_uses_one_as_of_boundary() -> None:
    sql = _migration()
    status = _function(
        sql,
        "public.creator_research_category_learning_status",
        "create or replace function public.creator_capture_research_category_readiness",
    )

    assert "as_of_value timestamptz := clock_timestamp()" in status
    assert "research_category_evidence_readiness(" in status
    assert "'retained_youtube_evidence'" in status
    assert "'retention_days', 29" in status
    assert "'raw_captions_stored', false" in status
    assert "'analysis_history_limit_per_source', 10" in status
    assert "'lineage_history_limit_per_source', 10" in status
    assert "'item_limit', 50" in status
    assert "'ingestion_status'" in status
    assert "'transport_attempt_count'" in status
    assert "current_profile_id" not in status
    for mutation in ("insert into", "update ", "delete from"):
        assert mutation not in status.lower()


def test_capture_checks_pre_hash_then_registers_and_snapshots() -> None:
    sql = _migration()
    capture = _function(
        sql,
        "public.creator_capture_research_category_readiness",
        "create or replace function public.system_record_research_source_analysis",
    )

    check = capture.index("research_category_evidence_changed")
    register = capture.index("insert into content_factory.research_category_source_ledger")
    recompute = capture.index("readiness_value :=", register)
    snapshot = capture.index(
        "insert into content_factory.research_category_readiness_snapshots"
    )
    assert check < register < recompute < snapshot
    assert "as_of_value timestamptz := clock_timestamp()" in capture
    assert "'external_call_started', false" in capture


def test_collection_is_consent_budget_and_policy_gated() -> None:
    sql = _migration()
    policy = _function(
        sql,
        "public.creator_configure_research_source_collection_policy",
        "create or replace function public.system_propose_due_research_source_collection",
    )
    propose = _function(
        sql,
        "public.system_propose_due_research_source_collection",
        "create or replace function content_factory_private.research_automatic_youtube_dispatch_allowed",
    )
    claim = _function(
        sql,
        "public.system_claim_due_research_youtube_collection",
        "create or replace function public.system_read_automatic_research_youtube_ingestion",
    )
    read = _function(
        sql,
        "public.system_read_automatic_research_youtube_ingestion",
        "create or replace function public.system_begin_automatic_research_youtube_transport",
    )
    transport = _function(
        sql,
        "public.system_begin_automatic_research_youtube_transport",
        "create or replace function\ncontent_factory_private.bootstrap_persisted_research_source_analyses",
    )

    assert "array['owner', 'admin']" in policy
    assert "research_instagram_provider_legal_choice_required" in policy
    for acknowledgement in (
        "automatic_collection_ack",
        "terms_ack",
        "quota_ack",
        "no_retry_ack",
    ):
        assert acknowledgement in policy
    assert "monthly_hard_budget_units_value < 2" in policy

    assert "pg_advisory_xact_lock" in propose
    assert "monthly_hard_budget_exhausted" in propose
    assert "scheduled_for_value - interval '90 days'" in propose
    assert "'planned_quota_units', 2" in propose
    assert "'external_call_started', false" in propose
    assert "'automatic_retry_started', false" in propose

    assert "for update of ingestion skip locked" in claim
    assert "ingestion.mode = 'category_refresh'" in claim
    assert "research_automatic_youtube_dispatch_allowed" in claim
    assert "manual_canary" not in claim
    assert "claim_value -> 'ingestion' ->> 'max_http_requests'" in claim
    assert "claim_value -> 'ingestion' ->> 'max_quota_units'" in claim
    assert "research_automatic_youtube_dispatch_allowed" in read
    assert "ingestion_row.status <> 'processing'" in read
    assert "ingestion_row.lease_expires_at <= clock_timestamp()" in read
    assert "research_automatic_youtube_dispatch_allowed" in transport
    assert "system_begin_research_youtube_transport(p_payload)" in transport


def test_pgtap_contains_runtime_regressions_for_the_critical_contracts() -> None:
    pgtap = PGTAP.read_text(encoding="utf-8")
    expected_runtime_contracts = (
        "fallback parsing is deterministically capped at twenty-four sources",
        "competitor citation takes precedence over a simultaneous trend role",
        "uncited market data never manufactures a trend or competitor role",
        "no provider title, fact, prose or invented source signal is copied",
        "lost-response replay re-enters registration safely",
        "fallback replay never overwrites or appends after a human head",
        "same-URL content versions do not inflate current source identity volume",
        "many retained videos from one channel count once",
        "excluding a current candidate lowers the evidence-readiness score",
        "readiness drops after retention expiry",
        "lost-response completion replay returns the exact same legacy response",
    )
    for contract in expected_runtime_contracts:
        assert contract in pgtap
