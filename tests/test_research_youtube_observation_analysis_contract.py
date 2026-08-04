from __future__ import annotations

from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608040002_research_youtube_observation_analysis.sql"
)
PGTAP = ROOT / "supabase/tests/research_youtube_automatic_integration_test.sql"
API = ROOT / "web/app/supabase-api.js"
VIEW = ROOT / "web/app/product-research-view.js"
APP = ROOT / "web/app/app.js"
WORKER = ROOT / "supabase/functions/creator-background-worker/index.ts"
WORKER_TEST = ROOT / "supabase/functions/creator-background-worker/index_test.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"\bcreate\s+(?:or\s+replace\s+)?function\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        source,
        re.IGNORECASE,
    )
    assert match is not None, f"SQL function {qualified_name} is missing"
    next_match = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_match is None else match.end() + next_match.start()
    return source[match.start() : end]


def _table(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?"
        rf"{re.escape(qualified_name)}\s*\(",
        source,
        re.IGNORECASE,
    )
    assert match is not None, f"SQL table {qualified_name} is missing"
    next_match = re.search(
        r"\bcreate\s+table\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_match is None else match.end() + next_match.start()
    return source[match.start() : end]


def test_migration_and_extended_integration_fixture_parse_as_postgresql() -> None:
    pglast = pytest.importorskip("pglast")

    assert len(pglast.parse_sql(_read(MIGRATION))) >= 35
    assert len(pglast.parse_sql(_read(PGTAP))) >= 70


def test_job_and_events_are_bound_to_the_exact_retained_observation_version() -> None:
    sql = _read(MIGRATION)
    compact = _compact(sql)
    jobs = _compact(
        _table(
            sql,
            "content_factory.research_youtube_observation_analysis_jobs",
        )
    )
    events = _compact(
        _table(
            sql,
            "content_factory.research_youtube_observation_analysis_events",
        )
    )
    enqueue = _compact(
        _function(
            sql,
            "content_factory_private.enqueue_research_youtube_observation_analysis",
        )
    )
    processor = _compact(
        _function(
            sql,
            "public.system_process_due_research_youtube_observation_analysis",
        )
    )

    assert (
        "unique (organization_id, id, observation_hash, retention_expires_at)"
        in compact
    )
    assert (
        "foreign key ( organization_id, observation_id, observation_hash, "
        "retention_expires_at ) references "
        "content_factory.research_youtube_video_observations( "
        "organization_id, id, observation_hash, retention_expires_at ) "
        "on delete cascade"
    ) in events
    assert (
        "unique (organization_id, observation_id, observation_hash, "
        "analysis_version)"
    ) in events
    assert "check (retention_expires_at > created_at)" in events
    assert "max(observation.retention_expires_at)" in enqueue
    assert "'retention_expires_at', retention_expires_at_value" in enqueue
    assert "observation.retention_expires_at > clock_timestamp()" in processor
    assert "observation_row.observation_hash" in processor
    assert "observation_row.retention_expires_at" in processor
    assert "foreign key (organization_id, ingestion_id)" in jobs

    mutation_guard = _compact(
        _function(
            sql,
            "content_factory_private.reject_research_youtube_analysis_event_mutation",
        )
    )
    assert "youtube_retention_purge" in mutation_guard
    assert "research_youtube_observation_analysis_events_append_only" in mutation_guard
    assert "before update or delete" in compact


def test_local_parser_is_single_attempt_no_retry_and_zero_spend() -> None:
    sql = _read(MIGRATION)
    jobs = _compact(
        _table(
            sql,
            "content_factory.research_youtube_observation_analysis_jobs",
        )
    )
    processor = _compact(
        _function(
            sql,
            "public.system_process_due_research_youtube_observation_analysis",
        )
    )

    assert "attempt_count integer not null default 0 check (attempt_count between 0 and 1)" in jobs
    assert "no_retry boolean not null default true check (no_retry)" in jobs
    assert (
        "external_call_started boolean not null default false check "
        "( not external_call_started )"
    ) in jobs
    assert (
        "'approval_required', 'queued', 'processing', 'completed', 'failed'"
        in jobs
    )
    assert "status = 'processing', attempt_count = 1" in processor
    assert "set status = 'failed'" in processor
    assert "set status = 'queued'" not in processor
    assert "'external_call_started', false" in processor
    assert "'provider_attempt_count', 0" in processor
    assert "'cost_minor', 0" in processor
    assert "'automatic_retry_started', false" in processor
    assert "research_youtube_transport_attempts" not in processor
    assert "generation_jobs" not in processor
    assert "net.http" not in processor


def test_derived_analysis_is_fail_closed_until_audited_approval() -> None:
    sql = _read(MIGRATION)
    compact = _compact(sql)
    decision = _compact(
        _function(
            sql,
            "public.system_decide_research_youtube_derived_analysis",
        )
    )
    processor = _compact(
        _function(
            sql,
            "public.system_process_due_research_youtube_observation_analysis",
        )
    )

    assert "begin;" == compact[:6]
    assert compact.endswith("commit;")
    assert "research_youtube_derived_analysis_decisions" in compact
    assert "youtube-derived-metrics-policy-2026-06-01-v1" in decision
    assert "analytics_amendment_ack" in decision
    assert "approval_reference" in decision
    assert "research_youtube_derived_analysis_approval_required" in decision
    assert "pg_advisory_xact_lock" in decision
    assert "set status = 'queued'" in decision
    assert "set status = 'approval_required'" in decision
    assert "research_youtube_derived_analysis_approved" in processor
    assert "set status = 'approval_required'" in processor
    assert "'selected', 0" in processor
    assert "external_call_started', false" in processor


def test_processor_claims_bounded_work_and_fails_closed_on_changed_input() -> None:
    processor = _compact(
        _function(
            _read(MIGRATION),
            "public.system_process_due_research_youtube_observation_analysis",
        )
    )

    assert "limit_value not between 1 and 6" in processor
    assert "where job.status = 'queued'" in processor
    assert "for update skip locked" in processor
    assert "analysis_evidence_expired" in processor
    assert "research_youtube_analysis_input_hash" in processor
    assert "analysis_input_changed" in processor
    assert "research_youtube_observation_analysis_payload" in processor
    assert "research_youtube_observation_analysis_is_valid" in processor
    assert "origin, actor_id, parser_key" in processor
    assert "'system_parser'" in processor
    assert "on conflict (organization_id, idempotency_key) do nothing" in processor
    assert "set status = 'completed'" in processor
    assert "parsed_count = parsed_count_value" in processor
    assert "exception when others" in processor


def test_human_correction_is_append_only_exact_head_cas() -> None:
    correction = _compact(
        _function(
            _read(MIGRATION),
            "public.creator_correct_research_youtube_observation_analysis",
        )
    )

    for required_input in (
        "observation_id",
        "observation_hash",
        "expected_head_event_id",
        "expected_head_hash",
        "analysis",
        "correction_reason",
        "idempotency_key",
    ):
        assert f"'{required_input}'" in correction
    assert "array['owner', 'admin', 'producer', 'reviewer']" in correction
    assert "membership.status = 'active'" in correction
    assert "research_youtube_derived_analysis_approved" in correction
    assert "research_youtube_derived_analysis_approval_required" in correction
    assert "observation.observation_hash = observation_hash_value" in correction
    assert "observation.retention_expires_at > clock_timestamp()" in correction
    assert "begin_command" in correction and "finish_command" in correction
    assert "pg_advisory_xact_lock" in correction
    assert "order by event.analysis_version desc, event.id desc" in correction
    assert "current_head.id <> expected_head_event_id_value" in correction
    assert "current_head.event_hash <> expected_head_hash_value" in correction
    assert "errcode = '40001'" in correction
    assert "research_youtube_observation_analysis_head_stale" in correction
    assert "current_head.analysis_version + 1" in correction
    assert "current_head.id, current_head.event_hash" in correction
    assert "'human_correction'" in correction
    assert "'candidate_decision_changed', false" in correction
    assert "research_youtube_candidate_decisions" not in correction
    assert "research_youtube_transport_attempts" not in correction


def test_readiness_v3_credits_parser_heads_without_promoting_semantic_truth() -> None:
    sql = _read(MIGRATION)
    readiness = _compact(
        _function(
            sql,
            "content_factory_private.research_category_evidence_readiness",
        )
    )

    assert "rename to research_category_evidence_readiness_v2_base" in _compact(sql)
    assert "research_category_evidence_readiness_v2_base" in readiness
    assert "head.event_hash as analysis_event_hash" in readiness
    assert "event.observation_hash = observation.observation_hash" in readiness
    assert "event.retention_expires_at > as_of_value" in readiness
    assert "observed.analysis_event_hash is not null" in readiness
    assert "observed.decision is distinct from 'exclude_candidate'" in readiness
    assert "observed.analysis_origin = 'human_correction'" in readiness
    assert "observed.decision is null" in readiness
    assert "when 'analysis_coverage'" in readiness
    assert "when 'human_validation'" in readiness
    assert "'definition_version', 'category-evidence-readiness-v3'" in readiness
    assert "current_retained_youtube_analysis_event_hashes" in readiness
    assert "parser heads add analysis coverage" in readiness
    assert "only human decisions add semantic credit" in readiness


def test_status_v2_exposes_current_history_job_and_provider_policy() -> None:
    status = _compact(
        _function(
            _read(MIGRATION),
            "public.creator_research_category_learning_status",
        )
    )

    assert "research-category-learning-readiness-v2" in status
    assert "'current_analysis'" in status
    assert "'analysis_history'" in status
    assert "limit 10" in status
    assert "'analysis_job'" in status
    assert "'can_correct_analysis'" in status
    assert "'research-youtube-observation-analysis-v1'" in status
    assert "'analysis_history_limit_per_observation', 10" in status
    assert "'analysis_external_call_started', false" in status
    assert "'analysis_automatic_retry_allowed', false" in status
    assert "'youtube_data_api_v3', 'instagram_meta_graph'" in status
    assert "oauth_app_review_permissions_and_legal_approval_required" in status
    assert "youtube-derived-metrics-policy-2026-06-01-v1" in status
    assert "youtube_derived_analysis_state" in status
    assert "instagram_arbitrary_account_discovery" in status
    assert "unsupported_coverage_gap" in status
    assert "apify_scraper" in status and "bright_data_scraper" in status


def test_expired_analysis_is_purged_with_observation_and_retention_health() -> None:
    sql = _read(MIGRATION)
    purge = _compact(
        _function(sql, "public.system_purge_expired_youtube_api_data")
    )
    retention = _compact(
        _function(
            sql,
            "content_factory_private.research_youtube_retention_ready",
        )
    )

    assert "set_config('content_factory.youtube_retention_purge', 'on', true)" in purge
    assert "delete from content_factory.research_youtube_observation_analysis_jobs" in purge
    assert "system_purge_expired_youtube_api_data_pre_analysis_v1" in purge
    assert "analysis_event_deleted_count" in purge
    assert "analysis_job_deleted_count" in purge
    assert "analysis_overdue_remaining_count" in purge
    assert "analysis_accounted" in purge
    assert "research-youtube-retention-receipt-v2" in purge
    assert "combined_receipt_hash_value" in purge
    assert "research_youtube_observation_analysis_jobs" in retention
    assert "research_youtube_observation_analysis_events" in retention
    assert "receipt.analysis_accounted" in retention
    assert retention.count("retention_expires_at <= clock_timestamp()") == 2


def test_rpc_grants_keep_processor_and_purge_service_only() -> None:
    compact = _compact(_read(MIGRATION))

    expected = (
        (
            "public.system_decide_research_youtube_derived_analysis(jsonb)",
            "service_role",
        ),
        (
            "public.system_process_due_research_youtube_observation_analysis(jsonb)",
            "service_role",
        ),
        (
            "public.creator_correct_research_youtube_observation_analysis(jsonb)",
            "authenticated",
        ),
        ("public.creator_research_category_learning_status(jsonb)", "authenticated"),
        ("public.system_purge_expired_youtube_api_data(jsonb)", "service_role"),
    )
    for signature, role in expected:
        assert f"grant execute on function {signature} to {role}" in compact
        assert (
            f"revoke all on function {signature} "
            "from public, anon, authenticated, service_role"
        ) in compact
    assert not re.search(
        r"grant execute on function "
        r"public\.system_process_due_research_youtube_observation_analysis"
        r"\(jsonb\) to (?:public|anon|authenticated)",
        compact,
    )
    assert not re.search(
        r"grant (?:all|insert|update|delete) on table "
        r"content_factory\.research_youtube_(?:derived_analysis_decisions|"
        r"observation_analysis_(?:jobs|events))[^;]*service_role",
        compact,
    )
    assert not re.search(
        r"grant execute on function public\.system_purge_expired_youtube_api_data"
        r"\(jsonb\) to (?:public|anon|authenticated)",
        compact,
    )


def test_ui_and_api_require_exact_analysis_history_and_cas_payload() -> None:
    api = _read(API)
    view = _read(VIEW)
    app = _read(APP)

    assert '"creator_correct_research_youtube_observation_analysis"' in api
    assert "async correctResearchYoutubeObservationAnalysis(options = {})" in api
    for marker in (
        "expected_head_event_id: expectedHeadEventId",
        "expected_head_hash: expectedHeadHash",
        "researchYoutubeObservationAnalysisIsValid(analysis)",
        "source.external_call_started !== false",
        "source.provider_attempt_count !== 0",
        "source.automatic_retry_started !== false",
    ):
        assert marker in api

    assert '"research-category-learning-readiness-v2"' in view
    assert '"category-evidence-readiness-v3"' in view
    assert "researchYoutubeObservationAnalysisEvent" in view
    assert "researchYoutubeObservationAnalysisJob" in view
    assert '"current_analysis"' in view
    assert '"analysis_history"' in view
    assert '"analysis_job"' in view
    assert '"can_correct_analysis"' in view
    assert "source.can_correct_analysis !== expectedCanCorrect" in view
    assert "analysisHistory[0].eventHash !== currentAnalysis.eventHash" in view
    assert "currentAnalysis.retentionExpiresAt !== retentionExpiresAt" in view
    assert '"approval_required"' in view
    assert "youtubeDerivedAnalysisState" in view
    assert "Исправить гипотезу без повторного provider call" in view

    assert "submitProductResearchYoutubeAnalysisCorrection" in app
    assert "state.api.correctResearchYoutubeObservationAnalysis" in app
    assert "expected_head_event_id: expectedHeadEventId" in app
    assert "expected_head_hash: expectedHeadHash" in app


def test_worker_runs_one_bounded_database_processor_outside_http_dispatch_cap() -> None:
    worker = _read(WORKER)
    worker_test = _read(WORKER_TEST)
    dispatch = worker.index("const outcomes = await Promise.all")
    poll_record = worker.index("const pollRecords = await")
    heartbeat = worker.index(
        "if (!(await heartbeatBackgroundWorker(supabaseAdmin, workerRun)))",
        poll_record,
    )
    analysis = worker.index("const youtubeAnalysis = await")

    assert dispatch < poll_record < heartbeat < analysis
    assert "YOUTUBE_OBSERVATION_ANALYSIS_LIMIT = 6" in worker
    assert "readYoutubeObservationAnalysisSummary" in worker
    assert "processDueYoutubeObservationAnalysis" in worker
    assert '"system_process_due_research_youtube_observation_analysis"' in worker
    assert "provider_attempt_count: 0" in worker
    assert "cost_minor: 0" in worker
    assert "automatic_retry_started: false" in worker
    assert "youtube_analysis: youtubeAnalysis" in worker
    assert "consumes none of the provider cap" in worker
    assert re.search(r"never requeues an\s+//\s+ingestion", worker)

    assert "exact zero-provider envelope" in worker_test
    assert "creates no HTTP dispatch" in worker_test
    assert "spent.provider_attempt_count = 1" in worker_test
    assert "charged.cost_minor = 1" in worker_test
    assert "retrying.automatic_retry_started = true" in worker_test
    assert "per-item status must agree" in worker_test
    assert "same job twice" in worker_test
