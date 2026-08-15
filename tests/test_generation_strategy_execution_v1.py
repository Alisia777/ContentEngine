import hashlib
import re
from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130007_generation_strategy_execution_v1.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "generation_strategy_execution_v1_test.sql"
AUTHORITY_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130006_generation_strategy_authority_v1.sql"
)
AUTHORITY_PGTAP = (
    ROOT / "supabase" / "tests" / "generation_strategy_authority_v1_test.sql"
)
AUTHORITY_STATIC = ROOT / "tests" / "test_generation_strategy_authority_v1.py"
LEGACY_RECONCILIATION_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607160004_real_generation_reconciliation.sql"
)

FROZEN_AUTHORITY_HASHES = {
    AUTHORITY_MIGRATION: (
        "f8184163e9270a7d26220550f01effe5127f9dcba061af862b03f774b030f600"
    ),
    AUTHORITY_PGTAP: (
        "4cde089e87d97716a2560cdfaab94834555926c34d57475f10dcefafb57b8c17"
    ),
    AUTHORITY_STATIC: (
        "17e5132f42c89e7c73990e794c104aa10fcf6c061c54683ea7765c098e92652f"
    ),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def _function_section(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create or replace function\s+{re.escape(qualified_name)}\(",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise AssertionError(f"function definition missing: {qualified_name}")
    next_match = re.search(
        r"create or replace function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end_at = len(source) if next_match is None else match.end() + next_match.start()
    return source[match.start() : end_at]


def test_sql_and_pgtap_parse_and_frozen_authority_is_untouched() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    assert len(parse_sql(migration)) >= 130
    assert len(parse_sql(pgtap)) >= 25
    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    for path, expected_hash in FROZEN_AUTHORITY_HASHES.items():
        canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(canonical_bytes).hexdigest() == expected_hash


def test_execution_ledgers_are_additive_private_rls_append_only_authority() -> None:
    sql = _read(MIGRATION)
    tables = (
        "generation_strategy_binding_selections",
        "generation_strategy_media_durations",
        "generation_strategy_readiness_receipts",
        "generation_strategy_start_claims",
        "generation_strategy_dispatch_attempts",
        "generation_strategy_dispatch_results",
        "generation_strategy_provider_status_events",
        "generation_strategy_dispatch_reconciliations",
        "generation_strategy_worker_requests",
        "generation_strategy_worker_leases",
    )

    assert "alter table content_factory.generation_spec_strategy_bindings" not in sql
    for table in tables:
        assert f"create table content_factory.{table}" in sql
        assert f"alter table content_factory.{table}\n  enable row level security" in sql
        assert f"revoke all on content_factory.{table}" in sql
        assert f"grant all on content_factory.{table}" in sql
        assert f"generation_strategy_{table.removeprefix('generation_strategy_')}" in sql
    assert sql.count("reject_generation_strategy_mutation();") >= len(tables)


def test_exact_three_strategy_version_and_recipe_tuple_is_single_authority() -> None:
    sql = _read(MIGRATION)

    for strategy_id, recipe in (
        ("viral_avatar_ugc", "product_ugc"),
        ("viral_product_swap", "product_swap"),
        ("viral_rebuild", "product_ad"),
    ):
        assert strategy_id in sql
        assert recipe in sql
        assert f"'/v1/recipes/{recipe}'" in sql
    assert "'2026-08-14.v1'" in sql
    assert "'2026-06'" in sql
    assert "'runway-recipe-credits-2026-08-14.v1'" in sql
    assert "runway-recipes-2026-08-14" not in sql
    assert "generation-strategy-catalog-2026-08-14" not in sql


def test_bind_wrapper_persists_full_selection_and_price_before_readiness() -> None:
    sql = _read(MIGRATION)
    bind = _section(
        sql,
        "create or replace function public.system_resolve_and_bind_generation_strategy(",
        "create or replace function\n  public.system_generation_strategy_media_probe_context(",
    )

    assert "system_resolve_and_bind_generation_strategy_pre_execution_v1" in bind
    assert "selection_value := p_payload -> 'selection'" in bind
    assert "price_value := result_value -> 'price'" in bind
    assert "generation_strategy_selection_current(" in bind
    assert "insert into content_factory.generation_strategy_binding_selections" in bind
    assert "selection_snapshot, selection_hash, price_snapshot" in bind
    assert "existing bindings without" in sql.lower()
    assert "generation_strategy_binding_selection_conflict" in bind
    assert "to service_role" in bind


def test_server_mp4_probe_is_full_download_byte_pinned_and_browser_untrusted() -> None:
    sql = _read(MIGRATION)
    context = _section(
        sql,
        "public.system_generation_strategy_media_probe_context(",
        "public.system_record_generation_strategy_media_duration(",
    )
    record = _section(
        sql,
        "public.system_record_generation_strategy_media_duration(",
        "create or replace function public.creator_generation_strategy_asset_candidates(",
    )

    for marker in (
        "'parser_version', 'iso-bmff-mvhd-v1'",
        "'max_bytes', 33554432",
        "'full_object_sha256_required', true",
        "'single_mvhd_required', true",
        "'fragmented_mp4_allowed', false",
        "'browser_measurement_accepted', false",
    ):
        assert marker in context
    for marker in (
        "p_payload -> 'http_status' is distinct from '200'::jsonb",
        "p_payload ->> 'content_type' <> 'video/mp4'",
        "p_payload -> 'download_complete' is distinct from 'true'::jsonb",
        "p_payload -> 'mvhd_count' is distinct from '1'::jsonb",
        "p_payload -> 'fragmented' is distinct from 'false'::jsonb",
        "media.sha256 = media_sha256_value",
        "media.size_bytes = size_bytes_value",
        "attachment.attachment_hash = attachment_hash_value",
        "attachment.media_sha256_snapshot = media_sha256_value",
        "round(duration_units_value::numeric * 1000 / timescale_value)",
    ):
        assert marker in record
    assert "duration_ms_value not between 1 and 3600000" in record
    assert "insert into content_factory.generation_strategy_media_durations" in record
    assert "to service_role" in record


def test_candidates_are_paginated_safe_and_strategy_specific() -> None:
    sql = _read(MIGRATION)
    candidates = _section(
        sql,
        "create or replace function public.creator_generation_strategy_asset_candidates(",
        "create or replace function public.system_generation_strategy_catalog_policy(",
    )

    for key in (
        "'id'",
        "'kind'",
        "'mime_type'",
        "'duration_seconds'",
        "'status'",
        "'rights_confirmed'",
        "'product_id'",
        "'product_identity'",
        "'filename'",
        "'exact_youtube_attached'",
        "'eligible_roles'",
        "'eligible_strategy_roles'",
        "'eligible'",
        "'blocking_codes'",
        "'blocking_codes_by_strategy'",
        "'created_at'",
        "'_cursor'",
    ):
        assert key in candidates
    assert "generation_strategy_media_durations duration" in candidates
    assert "media.metadata ->> 'duration_seconds'" not in candidates
    assert "'server_duration_probe_required'" in candidates
    assert (
        "jsonb_build_object('strategy_id', 'viral_avatar_ugc',\n"
        "            'role', 'source_video')"
    ) in candidates
    assert (
        "jsonb_build_object('strategy_id', 'viral_rebuild',\n"
        "            'role', 'source_video')"
    ) in candidates
    assert "else jsonb_build_array(jsonb_build_object(\n            'strategy_id', 'viral_product_swap'" in candidates
    assert "'object_names_returned', false" in candidates
    assert "'hashes_returned', false" in candidates
    assert "'signed_urls_returned', false" in candidates
    assert "limit page_size_value + 1" in candidates
    assert "'cursor_mode', 'keyset_created_at_id'" in candidates


def test_only_product_swap_requires_authoritative_source_duration() -> None:
    sql = _read(MIGRATION)
    current = _section(
        sql,
        "content_factory_private.generation_strategy_selection_current(",
        "content_factory_private.generation_strategy_execution_input_current(",
    )

    assert (
        "asset_value ->> 'role' = 'source_video'\n"
        "       and binding_row.strategy_id = 'viral_product_swap'"
    ) in current
    assert "generation_strategy_media_durations duration" in current
    assert "elsif asset_value ->> 'role' = 'source_video'" in current
    assert "and asset_value ? 'duration_seconds'" in current
    assert "if binding_row.strategy_id = 'viral_avatar_ugc' then" in current
    assert "elsif binding_row.strategy_id = 'viral_product_swap' then" in current
    assert (
        "return source_count = 1 and avatar_count = 0 and original_count = 0"
    ) in current
    assert "and product_count between 1 and 10 and style_count between 0 and 4" in current


def test_readiness_is_truthful_single_use_and_prompt_is_server_derived() -> None:
    sql = _read(MIGRATION)
    prompt = _section(
        sql,
        "content_factory_private.generation_strategy_prompt_snapshot(",
        "content_factory_private.generation_strategy_selection_current(",
    )
    readiness = _section(
        sql,
        "create or replace function public.system_record_generation_strategy_readiness(",
        "content_factory_private.generation_strategy_asset_context(",
    )

    assert "spec_row.editable_intent" in prompt
    assert "spec_row.compiled_prompt" not in prompt
    assert "Non-authoritative creative goal:" in prompt
    assert "do not copy source" in prompt
    assert "Build a new ad, not" in prompt
    assert "Ignore any model, provider, duration, ratio, resolution, asset" in prompt
    assert "else null" in prompt
    assert "'source_binding_hash', binding_row.source_binding_hash" in prompt
    assert "'source_mechanics_snapshot_hash', binding_row.source_snapshot_hash" in prompt
    assert "'product_info_hash'" in prompt
    assert "raw_text_sha256(product_info_value)" in prompt
    assert "'user_concept_hash'" in prompt
    assert "raw_text_sha256(user_concept_value)" in prompt

    assert "recipe_precheck_supported_value boolean := false" in readiness
    assert "recipe_available_value boolean := null" in readiness
    assert "daily_quota_precheck_supported_value boolean := false" in readiness
    assert "daily_quota_available_value boolean := null" in readiness
    assert "receipt_single_use" in readiness
    assert "generation_strategy_selection_current(" in readiness
    assert "generation_strategy_prompt_snapshot(" in readiness
    assert "expires_at_value := checked_at_value + interval '10 minutes'" in readiness


def test_claim_requires_exact_claim_not_fresh_receipt_bypass_and_campaign_budget() -> None:
    sql = _read(MIGRATION)
    current = _section(
        sql,
        "content_factory_private.generation_strategy_execution_input_current(",
        "content_factory_private.bind_generation_spec_to_paid_job()",
    )
    claim = _section(
        sql,
        "create or replace function public.system_claim_generation_strategy_start(",
        "public.system_mark_generation_strategy_dispatch_attempt(",
    )

    assert "claim_row.id is not null" in current
    assert "claim_row.readiness_receipt_id = receipt_row.id" in current
    assert "claim_row.campaign_id::text = execution_value ->> 'campaign_id'" in current
    assert "expires_at >" not in current
    assert "or receipt_row.expires_at" not in current
    assert sql.count("deferrable initially deferred") == 3
    assert claim.index("insert into content_factory.generation_strategy_start_claims") < claim.index(
        "insert into content_factory.generation_batches"
    ) < claim.index("insert into content_factory.generation_jobs")
    assert "'campaign_id'" in claim
    assert "'content_factory.generation_campaign_id', campaign_id_value::text" in claim
    assert "campaign_id_value" in claim
    assert "estimated_cost_value" in claim
    assert "generation_spend" not in claim or "generation_campaign_id" in claim


def test_claim_uses_recipe_technical_and_prompt_authority_not_proxy_spec() -> None:
    sql = _read(MIGRATION)
    claim = _section(
        sql,
        "create or replace function public.system_claim_generation_strategy_start(",
        "public.system_mark_generation_strategy_dispatch_attempt(",
    )
    spec_guard = _section(
        sql,
        "content_factory_private.bind_generation_spec_to_paid_job()",
        "-- Extend the batch/job table checks",
    )

    assert "'model', receipt_row.recipe" in claim
    assert "'strategy_recipe', receipt_row.recipe" in claim
    assert "'duration_seconds', strategy_duration_value" in claim
    assert "'audio', strategy_audio_value" in claim
    assert "'ratio', ratio_value" in claim
    assert "'resolution', resolution_value" in claim
    assert "'prompt_text', strategy_prompt_text_value" in claim
    assert "spec_row.compiled_prompt" not in claim
    assert "spec_row.model" not in claim
    assert "spec_row.duration_seconds" not in claim
    assert "spec_row.audio" not in claim
    assert "receipt_row.strategy_prompt_snapshot" in spec_guard
    assert "generation_strategy_execution_input_current(" in spec_guard
    assert claim.count("'productInfoHash'") == 2
    assert claim.count("'userConceptHash'") == 2


def test_one_dispatch_slot_and_result_mapping_fail_closed() -> None:
    sql = _read(MIGRATION)
    attempt = _function_section(
        sql, "public.system_mark_generation_strategy_dispatch_attempt"
    )
    result = _function_section(
        sql, "public.system_record_generation_strategy_dispatch_result"
    )

    assert "unique (organization_id, start_claim_id)" in sql
    assert "dispatch_allowed_value boolean := false" in attempt
    assert "dispatch_allowed_value := true" in attempt
    assert "'replay_post_allowed', false" in attempt
    assert "generation_spend_ledger ledger" in attempt
    assert "event_type = 'reserved'" in attempt
    assert "generation_strategy_asset_context(" in attempt
    assert "'signed_urls_persisted', false" in attempt
    assert "'size_bytes', media.size_bytes" in sql
    assert "'productInfoHash'" in attempt
    assert "'userConceptHash'" in attempt

    assert "400, 401, 402, 403, 404, 405, 422, 429" in result
    assert "provider_http_status_value between 100 and 599" in result
    assert "provider_http_status_value not in (" in result
    assert "provider_submission_ambiguous" in result
    deterministic_rejections = {400, 401, 402, 403, 404, 405, 422, 429}
    for status in (206, 302, 408, 425, 500, 501, 502, 503, 504, 505, 599):
        assert 100 <= status <= 599 and status not in deterministic_rejections
    for code in (
        "input_signing_failed",
        "input_asset_not_current",
        "signed_url_invalid",
    ):
        assert code in result
    assert "provider_post_started_value is false" not in result
    assert "not provider_post_started_value" in result
    assert "set status = 'failed', actual_cost_minor = 0" in result
    assert "'second_post_allowed', false" in result
    assert "'ambiguous_status_only', result_row.outcome = 'ambiguous'" in result
    assert "provider_http_status_value is null" in result
    assert "failure_code_value is distinct from" in result
    assert "generation_strategy_dispatch_result_access_required" not in result


def test_ambiguous_reconciliation_never_reopens_post_and_is_owner_admin_only() -> None:
    sql = _read(MIGRATION)
    reconcile = _function_section(
        sql, "public.system_reconcile_generation_strategy_dispatch"
    )

    assert "membership.role in ('owner', 'admin')" in reconcile
    assert "result.outcome = 'ambiguous'" in reconcile
    assert "result.provider_post_started" in reconcile
    assert "RUNWAY_TASK_ID_VERIFIED" in reconcile
    assert "RUNWAY_NO_TASK_VERIFIED" in reconcile
    assert "provider_task_created_at_value <" in reconcile
    assert "clock_timestamp() - interval '2 minutes'" in reconcile
    assert "set status = 'submitted', actual_cost_minor = job.estimated_cost_minor" in reconcile
    assert "set status = 'failed', actual_cost_minor = 0" in reconcile
    assert "'second_post_allowed', false" in reconcile
    assert "provider_post_allowed" not in reconcile


def test_post_claim_acl_drift_terminalizes_or_continues_without_stranding() -> None:
    sql = _read(MIGRATION)
    attempt = _section(
        sql,
        "create or replace function\n  public.system_mark_generation_strategy_dispatch_attempt(",
        "-- Preserve the installed legacy/multimodel provider-start guard",
    )
    result = _section(
        sql,
        "create or replace function\n  public.system_record_generation_strategy_dispatch_result(",
        "create or replace function\n  public.system_reconcile_generation_strategy_dispatch(",
    )
    provider_status = _section(
        sql,
        "create or replace function\n  public.system_record_generation_strategy_provider_status(",
        "-- E2. Recipe-aware status",
    )

    assert "actor_access_current_value" in attempt
    assert "claim_actor_access_revoked" in attempt
    assert "insert into content_factory.generation_strategy_dispatch_results" in attempt
    assert "set status = 'failed', actual_cost_minor = 0" in attempt
    assert "'terminalized_before_provider_post'" in attempt
    assert "generation_strategy_dispatch_attempt_access_required" not in attempt
    assert "generation_strategy_dispatch_result_access_required" not in result
    assert "generation_strategy_provider_status_access_required" not in provider_status
    assert "attempt.actor_id = actor_id_value" in result
    assert "claim.actor_id = actor_id_value" in provider_status


def test_recipe_status_is_monotonic_storage_verified_and_browser_safe() -> None:
    sql = _read(MIGRATION)
    record = _function_section(
        sql, "public.system_record_generation_strategy_provider_status"
    )
    status = _section(
        sql,
        "create or replace function public.system_generation_strategy_status(",
        "create or replace function public.system_generation_strategy_provider_policy(",
    )

    assert "previous_status_value not in ('submitted', 'processing')" in record
    assert "event.provider_status = provider_status_value" in record
    assert "storage.objects storage_object" in record
    assert "storage_size_value <> size_bytes_value" in record
    assert "storage_mime_value <> mime_type_value" in record
    assert "storage_sha_value <> sha256_value" in record
    assert "insert into content_factory.media_objects" in record
    assert "'review_mode', 'manual_human_review'" in record
    assert "set status = 'review'" in record
    assert "provider_billing_outcome', 'unknown'" in record
    assert "elsif previous_status_value = provider_status_value then" in record
    assert "current_status_reused_value := true" in record
    assert "'current_status_reused', current_status_reused_value" in record
    assert "'same_status_returns_current', true" in record

    assert "legacy_model_catalog_used', false" in status
    assert "'price', receipt_row.price_snapshot - 'spend_confirmation'" in status
    assert "'object_names_returned', false" in status
    assert "'media_hashes_returned', false" in status
    assert "'signed_urls_returned', false" in status
    assert "strategy_prompt_snapshot" not in status
    assert "output_object_name" not in status
    assert "sha256" not in status


def test_worker_candidates_are_exact_bounded_leased_and_never_post_authority() -> None:
    sql = _read(MIGRATION)
    worker = _function_section(
        sql, "public.system_claim_generation_strategy_worker_candidates"
    )

    assert "generation_strategy_start_claims claim" in worker
    assert "join content_factory.generation_jobs job" in worker
    assert "job.status = 'queued'" in worker
    assert "attempt.id is null" in worker
    assert "job.status = 'starting'" in worker
    assert "attempt.id is not null" in worker
    assert "result.id is null" in worker
    assert "attempt.reserved_at <=" in worker
    assert "requested_at_value - interval '90 seconds'" in worker
    assert "'dispatch_unknown'" in worker
    assert "'dispatch_attempt_id'" in worker
    assert "'attempt_hash'" in worker
    assert "'dispatch_token'" in worker
    assert "job.status in ('submitted', 'processing')" in worker
    assert "provider_task_id" in worker
    assert "claim.claimed_at <= requested_at_value - interval '10 seconds'" in worker
    assert "lease_seconds_value not between 30 and 300" in worker
    assert "page_size_value not between 1 and 25" in worker
    assert "for update of job skip locked" in worker
    assert "active_lease.leased_until > requested_at_value" in worker
    assert "insert into content_factory.generation_strategy_worker_requests" in worker
    assert "insert into content_factory.generation_strategy_worker_leases" in worker
    assert "'exact_strategy_claims_only', true" in worker
    assert "'generic_generation_jobs_returned', false" in worker
    assert "'lease_authorizes_provider_post', false" in worker
    assert "'unique_dispatch_attempt_still_required', true" in worker
    assert "'dispatch_unknown_never_reposts', true" in worker
    assert "'dispatch_unknown', 'record_ambiguous_without_post'" in worker
    assert "organization_id_value is null" in worker
    assert "fetch(" not in worker.lower()


def test_legacy_starting_watchdog_cannot_mutate_strategy_claim_jobs() -> None:
    sql = _read(MIGRATION)
    legacy = _read(LEGACY_RECONCILIATION_MIGRATION)
    patch = _section(
        sql,
        "do $patch_legacy_strategy_starting_watchdog$",
        "$patch_legacy_strategy_starting_watchdog$;",
    )

    assert "generation_strategy_start_claims claim" in patch
    assert "claim.generation_job_id = job_id_value" in patch
    assert "'marked', false" in patch
    assert "'strategy_worker_owned', true" in patch
    marker = (
        "  if organization_id_value is null then\n"
        "    raise exception using\n"
        "      errcode = 'P0002',\n"
        "      message = 'real_generation_not_found';\n"
        "  end if;\n"
    )
    legacy_target = _function_section(
        legacy, "public.system_mark_real_generation_reconciliation_required"
    )
    assert legacy_target.count(marker) == 1
    assert "strategy_worker_owned" in _function_section(
        sql, "content_factory_private.generation_strategy_execution_chain_installed"
    )


def test_catalog_and_context_policy_split_selection_from_paid_authority() -> None:
    sql = _read(MIGRATION)
    catalog = _section(
        sql,
        "create or replace function public.system_generation_strategy_catalog_policy(",
        "create or replace function public.system_record_generation_strategy_readiness(",
    )
    policy = _section(
        sql,
        "create or replace function public.system_generation_strategy_provider_policy(",
        "create or replace function public.creator_generation_strategy_repeat_data(",
    )
    chain = _section(
        sql,
        "content_factory_private.generation_strategy_execution_chain_installed()",
        "content_factory_private.generation_strategy_prompt_snapshot(",
    )

    assert "'select_enabled', enabled_value" in catalog
    assert "'preflight_enabled', enabled_value" in catalog
    assert "'paid_start_authorized', false" in catalog
    assert "'catalog_policy_is_not_paid_authority', true" in catalog
    assert "to service_role" in catalog

    for rpc in (
        "system_record_generation_strategy_readiness",
        "system_claim_generation_strategy_start",
        "system_mark_generation_strategy_dispatch_attempt",
        "system_record_generation_strategy_dispatch_result",
        "system_reconcile_generation_strategy_dispatch",
        "system_record_generation_strategy_provider_status",
        "system_generation_strategy_status",
    ):
        assert rpc in chain
    assert "receipt.expires_at > statement_timestamp()" in policy
    assert "receipt_unconsumed_value" in policy
    assert "generation_strategy_start_path_not_integrated" in policy
    assert "launch_enabled_value := binding_current_value" in policy
    assert "provider_call_started', false" in policy


def test_repeat_and_archive_return_safe_full_selection_with_confirmations_reset() -> None:
    sql = _read(MIGRATION)
    repeat = _section(
        sql,
        "create or replace function public.creator_generation_strategy_repeat_data(",
        "-- Make the preserved archive filters",
    )
    archive = _section(
        sql,
        "create or replace function public.creator_generation_archive(",
        "comment on table content_factory.generation_strategy_binding_selections",
    )

    for section in (repeat, archive):
        assert "generation_job_id" in section
        assert "selection" in section
        assert "price" in section
        assert "strategy_prompt_hash" in section
        assert "spend_confirmation', null" in section
        assert "requires_fresh_binding', true" in section
        assert "requires_fresh_human_confirmation', true" in section
        assert "requires_fresh_provider_readiness_receipt', true" in section
        assert "requires_fresh_price_confirmation', true" in section
    assert "jsonb_object_agg(key_value, false)" in repeat
    assert "selection_authority_reused', false" in repeat
    assert "media_hash_authority_reused', false" in repeat
    assert "generation_strategy_execution_selection" in archive
    assert "generation_strategy_price_reference" in archive
    assert "'generation_strategy_snapshot'," not in archive
    assert "'generation_strategy_snapshot_hash'," not in archive
    assert "creator_generation_archive_pre_execution_v1(p_payload)" in archive
    assert "'generation_strategy_snapshot'" in _read(AUTHORITY_MIGRATION)
    assert "'generation_strategy_snapshot_hash'" in _read(AUTHORITY_MIGRATION)


def test_archive_dynamic_patch_targets_are_unique_and_do_not_corrupt_search() -> None:
    authority = _read(AUTHORITY_MIGRATION)
    sql = _read(MIGRATION)
    patch = _section(
        sql,
        "do $patch_generation_strategy_archive_projection$",
        "alter function public.creator_generation_archive(jsonb)",
    )

    pair = "      launch.provider,\n      launch.model,\n"
    assert authority.count(pair) == 1
    assert "E'      launch.provider,\\n      launch.model,\\n'" in patch
    assert "E'      launch.model,\\n'" not in patch
    assert authority.count("            launch.model,\n") == 1

    exact_targets = (
        "      launch.content_kind,\n",
        "      launch.selection_source,\n",
        "      launch.quality_status,\n",
        "      and (provider_value = 'all' or launch.provider = provider_value)\n",
        "      and (model_value = 'all' or lower(launch.model) = model_value)\n",
        "        or launch.content_kind = content_kind_value\n",
        "        or launch.selection_source = selection_source_value\n",
        "        or launch.quality_status = quality_status_value\n",
    )
    for target in exact_targets:
        assert authority.count(target) == 1
    for marker in (
        "coalesce(launch.provider",
        "coalesce(launch.model",
        "coalesce(launch.content_kind",
        "coalesce(launch.selection_source",
        "coalesce(launch.quality_status",
        "provider_value = ''all'' or coalesce(launch.provider",
        "model_value = ''all'' or lower(coalesce(launch.model",
    ):
        assert marker in patch
    assert _read(MIGRATION).count(
        "function_definition := replace(function_definition, E'\\r\\n', E'\\n');"
    ) == 3


def test_service_only_rpc_surface_and_authenticated_readers_are_explicit() -> None:
    sql = _read(MIGRATION)
    service_rpcs = (
        "system_resolve_and_bind_generation_strategy",
        "system_generation_strategy_media_probe_context",
        "system_record_generation_strategy_media_duration",
        "system_generation_strategy_catalog_policy",
        "system_record_generation_strategy_readiness",
        "system_claim_generation_strategy_start",
        "system_mark_generation_strategy_dispatch_attempt",
        "system_record_generation_strategy_dispatch_result",
        "system_reconcile_generation_strategy_dispatch",
        "system_record_generation_strategy_provider_status",
        "system_generation_strategy_status",
        "system_claim_generation_strategy_worker_candidates",
        "system_generation_strategy_provider_policy",
    )
    for rpc in service_rpcs:
        assert f"public.{rpc}(jsonb)" in sql
        function_match = re.search(
            rf"create or replace function\s+public\.{re.escape(rpc)}\(",
            sql,
            re.IGNORECASE,
        )
        assert function_match is not None
        function_at = function_match.start()
        grant_at = sql.index("to service_role", function_at)
        next_function_at = sql.find("create or replace function", function_match.end())
        assert next_function_at == -1 or grant_at < next_function_at
    assert (
        "grant execute on function\n"
        "  public.creator_generation_strategy_asset_candidates(jsonb)\n"
        "  to authenticated"
    ) in sql
    assert (
        "grant execute on function public.creator_generation_strategy_repeat_data(jsonb)\n"
        "  to authenticated"
    ) in sql


def test_plpgsql_case_guards_and_boolean_authority_have_no_known_compile_bypass() -> None:
    sql = _read(MIGRATION)

    forbidden = (
        r"<>\s+case\b",
        r"is\s+distinct\s+from\s+case\b",
        r"\bor\s+case\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, sql, re.IGNORECASE) is None
    assert "<> (case receipt_row.strategy_id" in sql
    assert sql.count("total_created <>\n         (case when") == 1
    assert "jsonb_array_length(asset_context_value) <> (case" in sql
    assert "provider_http_status_value is null" in sql
    assert "failure_code_value is distinct from" in sql
    assert "provider_task_id_value is null\n     or length" in sql
