from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202608130004_generation_multimodel_acceptance_v4.sql"
)
PGTAP_PATH = ROOT / "supabase/tests/generation_multimodel_acceptance_v4_test.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", _read(path).lower()).strip()


def _function(sql: str, name: str) -> str:
    pattern = re.compile(
        rf"create or replace function\s+{re.escape(name.lower())}\s*\(.*?\)"
        rf".*?\$\$.*?\$\$;",
        re.DOTALL,
    )
    match = pattern.search(sql)
    assert match, name
    return match.group(0)


def test_acceptance_v4_sql_and_pgtap_parse() -> None:
    assert len(parse_sql(_read(MIGRATION_PATH))) == 21
    assert len(parse_sql(_read(PGTAP_PATH))) >= 45


def test_one_public_owner_preserves_the_old_rich_resolver_privately() -> None:
    sql = _normalized(MIGRATION_PATH)
    assert sql.count(
        "create or replace function public.creator_generation_model_acceptance"
    ) == 1
    assert (
        "alter function public.creator_generation_model_acceptance(jsonb) "
        "set schema content_factory_private"
    ) in sql
    assert (
        "rename to creator_generation_model_acceptance_pre_multimodel_v49"
    ) in sql
    assert (
        "revoke all on function content_factory_private "
        ".creator_generation_model_acceptance_pre_multimodel_v49(jsonb) "
        "from public, anon, authenticated, service_role"
    ) in sql
    public_owner = _function(
        sql, "public.creator_generation_model_acceptance"
    )
    assert (
        "creator_generation_model_acceptance_pre_multimodel_v49(p_payload)"
        in public_owner
    )
    assert "generation_model_acceptance_catalog_v49(" in public_owner
    assert "membership_role(" in public_owner


def test_catalog_is_the_exact_ten_provider_model_identities() -> None:
    sql = _normalized(MIGRATION_PATH)
    catalog = _function(
        sql, "content_factory_private.generation_acceptance_catalog_v49"
    )
    identities = re.findall(
        r"\(\d+,\s*'([^']+)'::text,\s*'([^']+)'::text\)", catalog
    )
    assert identities == [
        ("runway", "seedream5_lite"),
        ("runway", "gen4_turbo"),
        ("runway", "seedance2_fast"),
        ("runway", "gen4.5"),
        ("runway", "seedance2_mini"),
        ("runway", "veo3.1_fast"),
        ("runway", "gemini_omni_flash"),
        ("runway", "veo3.1"),
        ("runway", "seedance2"),
        ("google", "veo-3.1-lite-generate-preview"),
    ]
    projection = _function(
        sql,
        "content_factory_private.generation_model_acceptance_catalog_v49",
    )
    for token in (
        "generation_catalog_entry(",
        "generation_provider_launch_enabled(",
        "generation_provider_disabled_reason(",
        "'public_label'",
        "'content_kind'",
        "'lifecycle'",
        "'enabled_by_default'",
        "'launch_enabled'",
        "'disabled_reason_code'",
        "'catalog_version'",
        "'pricing_version'",
    ):
        assert token in projection


def test_exact_output_requires_real_paid_succeeded_provider_model_and_sha() -> None:
    sql = _normalized(MIGRATION_PATH)
    exact = _function(
        sql,
        "content_factory_private.generation_acceptance_exact_outputs_v49",
    )
    for token in (
        "job.mode = 'real'",
        "job.provider = p_provider",
        "job.allow_real_spend",
        "job.status = 'succeeded'",
        "job.actual_cost_minor > 0",
        "job.actual_cost_minor = job.estimated_cost_minor",
        "media.id::text = job.output ->> 'output_media_id'",
        "media.sha256 = job.output ->> 'sha256'",
        "media.metadata ->> 'provider' = p_provider",
        "media.metadata ->> 'model' = p_model",
        "media.metadata ->> 'generation_job_id' = job.id::text",
        "job.input ->> 'model' = p_model",
    ):
        assert token in exact
    for forbidden in (
        "generation_provider_readiness_receipts",
        "provider_task_id is not null",
        "output_media_id is not null",
    ):
        assert forbidden not in exact


def test_acceptance_needs_completed_ai_qa_and_independent_watched_human() -> None:
    sql = _normalized(MIGRATION_PATH)
    evidence = _function(
        sql,
        "content_factory_private.generation_acceptance_decisions_v49",
    )
    for token in (
        "review.status = 'completed'",
        "review.completion_hash is not null",
        "review.media_sha256_snapshot = output.media_sha256",
        "review.model_provider is not null",
        "review.model_version is not null",
        "review.input -> 'ai_generated' = 'true'::jsonb",
        "review.input -> 'external_ai_processing_confirmed' = 'true'::jsonb",
        "human_decision.review_completion_hash = review.completion_hash",
        "human_decision.media_sha256_snapshot = output.media_sha256",
        "human_decision.media_watched_confirmed",
        "human_decision.decided_by <> output.requested_by",
        "human_decision.decided_by <> output.assigned_to",
        "human_decision.decided_by <> output.owner_id",
        "content_review_context_amendments",
        "amendment.created_by = human_decision.decided_by",
        "provider_analysis_reused}' = 'true'",
        "external_ai_invoked}' = 'false'",
    ):
        assert token in evidence


def test_status_fails_closed_on_quality_context_actor_and_freshness() -> None:
    sql = _normalized(MIGRATION_PATH)
    resolver = _function(
        sql, "content_factory_private.generation_model_acceptance_v49"
    )
    for token in (
        "evidence.overall_score >= 80",
        "evidence.blockers_count = 0",
        "evidence.compliance_status is not null",
        "evidence.compliance_status <> 'block'",
        "order by evidence.decided_at desc, evidence.decision_id desc",
        "make_interval(days => evidence_max_age_days)",
        "expires_at_value > p_evaluated_at",
        "elsif not evidence_row.context_bound",
        "elsif evidence_row.blockers_count > 0",
        "elsif evidence_row.overall_score < 80",
        "elsif not evidence_fresh_value",
        "'acceptance_evidence_stale'",
        "status_value := 'accepted'",
        "status_value := 'needs_revalidation'",
        "status_value := 'unproven'",
    ):
        assert token in resolver


def test_pending_is_exact_per_provider_and_model_without_starting_work() -> None:
    sql = _normalized(MIGRATION_PATH)
    resolver = _function(
        sql, "content_factory_private.generation_model_acceptance_v49"
    )
    for token in (
        "generation_acceptance_exact_outputs_v49(",
        "candidate.media_sha256_snapshot = output.media_sha256",
        "candidate.input ->> 'generation_job_id'",
        "generation_acceptance_decisions_v49(",
        "'pending_review'",
        "'generation_job_id'",
        "'media_id'",
        "'review_id'",
        "'review_status'",
    ):
        assert token in resolver
    for forbidden in (
        "creator_start_real_generation",
        "system_claim_generation",
        "insert into content_factory.generation_jobs",
        "insert into content_factory.generation_batches",
        "http_post",
        "net.http_post",
    ):
        assert forbidden not in resolver


def test_old_rows_are_merged_before_catalog_metadata_only() -> None:
    sql = _normalized(MIGRATION_PATH)
    projection = _function(
        sql,
        "content_factory_private.generation_model_acceptance_catalog_v49",
    )
    assert "select legacy_model.value into model_value" in projection
    assert "where legacy_model.value ->> 'model' = catalog_row.model" in projection
    assert "model_value := model_value || jsonb_build_object(" in projection
    for preserved_key in (
        "'evidence'",
        "'pending_review'",
        "'successful_runs'",
        "'reviewed_runs'",
        "'accepted_runs'",
        "'pending_review_runs'",
    ):
        # These fields are derived by legacy/new resolvers, never overwritten
        # by catalog projection metadata.
        metadata_tail = projection[projection.index(
            "model_value := model_value || jsonb_build_object("
        ):]
        assert preserved_key not in metadata_tail.split(
            "if model_value ->> 'status'", 1
        )[0]


def test_acceptance_is_advisory_and_never_automatic_spend() -> None:
    sql = _normalized(MIGRATION_PATH)
    assert sql.count("'automatic_generation', false") >= 2
    assert sql.count("'automatic_spend', false") >= 2
    assert "'automatic_generation', true" not in sql
    assert "'automatic_spend', true" not in sql
    for forbidden in (
        "insert into content_factory.generation_jobs",
        "insert into content_factory.generation_batches",
        "update content_factory.generation_jobs",
        "delete from content_factory.generation_jobs",
        "creator_start_real_generation",
        "system_record_generation_provider_readiness",
    ):
        assert forbidden not in sql


def test_pgtap_covers_every_required_functional_boundary() -> None:
    pgtap = _normalized(PGTAP_PATH)
    for token in (
        "new runway model accepts only exact paid output",
        "wrong provider and model media identity is excluded",
        "same actor cannot independently accept",
        "approval without context binding fails closed",
        "evidence older than ninety days",
        "leaves the exact output and review pending",
        "legacy model evidence and pending fields remain byte-equivalent",
        "blocked direct google stays visible and unproven",
        "premium catalog models remain honestly unproven",
        "automatic_generation",
        "automatic_spend",
    ):
        assert token in pgtap
    assert "set local session_replication_role = replica" in pgtap
    assert "set local session_replication_role = origin" in pgtap
