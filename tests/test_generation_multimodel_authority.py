"""Static contracts for the authoritative multi-model paid-start seam."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130002_generation_multimodel_authority.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "generation_multimodel_authority_test.sql"


def _read() -> str:
    assert MIGRATION.is_file(), f"Missing migration: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _function(source: str, qualified_name: str, *, last: bool = True) -> str:
    # SQL style intentionally allows a line break before `.function_name`.
    pattern = re.compile(
        r"create\s+or\s+replace\s+function\s+"
        + re.escape(qualified_name).replace(r"\.", r"\s*\.\s*")
        + r"\s*\(",
        flags=re.IGNORECASE,
    )
    matches = list(pattern.finditer(source))
    assert matches, f"Missing SQL function {qualified_name}"
    match = matches[-1] if last else matches[0]
    terminator = re.search(r"\n\$\$;", source[match.end() :])
    assert terminator is not None, f"Unterminated SQL function {qualified_name}"
    end = match.end() + terminator.end()
    return source[match.start() : end]


def test_migration_and_pgtap_exist_and_parse() -> None:
    sql = _read()
    assert MIGRATION.name == "202608130002_generation_multimodel_authority.sql"
    assert parse_sql(sql)
    assert PGTAP.is_file()
    assert parse_sql(PGTAP.read_text(encoding="utf-8"))


def test_catalog_enables_exact_new4_but_keeps_unfinished_providers_closed() -> None:
    sql = _normalized(_read())
    for identity in (
        "runway:gen4.5",
        "runway:seedance2_mini",
        "runway:veo3.1_fast",
        "runway:gemini_omni_flash",
    ):
        assert f"when '{identity}' then true" in sql
    for model in (
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ):
        entry_at = sql.index(f"when 'runway:{model}' then jsonb_build_object")
        entry_end = sql.index("pricing_version", entry_at)
        entry = sql[entry_at:entry_end]
        assert "'enabled_by_default',true" in entry
        assert "disabled_reason" not in entry
    assert "generation_google_lro_sql_ready()" in sql
    google_ready = _normalized(
        _function(
            _read(), "content_factory_private.generation_google_lro_sql_ready"
        )
    )
    assert "select false" in google_ready
    assert "when 'runway:veo3.1' then true" not in sql
    assert "when 'runway:seedance2' then true" not in sql


def test_server_owned_sku_has_frozen_capabilities_and_costs() -> None:
    sku = _normalized(
        _function(
            _read(), "content_factory_private.real_generation_multimodel_sku"
        )
    )
    assert "model_value = 'gen4.5'" in sku
    assert "p_duration between 2 and 10" in sku
    assert "credits_value := p_duration * 12" in sku
    assert "model_value = 'seedance2_mini'" in sku
    assert "p_duration between 4 and 15" in sku
    assert "credits_value := greatest(64, p_duration * 16)" in sku
    assert "model_value = 'veo3.1_fast'" in sku
    assert "p_duration in (4,6,8)" in sku
    assert "case when p_audio then 15 else 10 end" in sku
    assert "model_value = 'gemini_omni_flash'" in sku
    assert "credits_value := p_duration * 10 + 1" in sku
    assert "estimated_cost_minor" in sku
    assert "spend_confirmation" in sku
    assert "p_payload" not in sku


def test_spec_v2_is_the_exact_frozen_seventeen_field_scope() -> None:
    scope = _normalized(
        _function(_read(), "content_factory_private.generation_spec_scope_v2")
    )
    exact_keys = (
        "primary_media_id",
        "media_ids",
        "platform",
        "provider",
        "model",
        "input_mode",
        "duration_seconds",
        "product_category",
        "format",
        "ratio",
        "resolution",
        "audio",
        "spoken_dialogue",
        "reference_count",
        "reference_video",
        "first_frame",
        "last_frame",
    )
    for key in exact_keys:
        assert f"'{key}'" in scope
    assert "ratio_value is distinct from format_value" in scope
    assert "media_count_value between 1 and 5" in scope
    assert "media_count_value=case when last_frame_value then 2 else 1 end" in scope
    assert "reference_count_value=media_count_value" in scope


def test_plpgsql_if_case_expressions_are_parenthesized_for_runtime_compile() -> None:
    """PL/pgSQL otherwise mistakes the first CASE ``THEN`` for IF ``THEN``."""
    scope = _normalized(
        _function(_read(), "content_factory_private.generation_spec_scope_v2")
    )
    batch_guard = _normalized(
        _function(
            _read(), "content_factory_private.guard_generation_batch_contract"
        )
    )
    starter = _normalized(
        _function(
            _read(),
            "content_factory_private.creator_start_real_generation_multimodel_v48",
        )
    )

    assert "spoken_dialogue_value is distinct from (case model_value" in scope
    assert "or (case model_value" in scope
    assert "else true end) then" in scope
    assert "new.total_created<>(case when new.status='succeeded'" in batch_guard
    assert "between 1 and (case model_value" in starter
    assert (
        "if ((p_payload -> 'generation_spec_context') "
        "-array['spec_id','spec_version','spec_hash']::text[])<>'{}'::jsonb"
        in starter
    )

    assert "distinct from case model_value" not in scope
    assert "or case model_value" not in scope
    assert "new.total_created<>case" not in batch_guard
    assert "between 1 and case model_value" not in starter


def test_legacy_constraints_are_old3_only_and_new_models_require_exact_input() -> None:
    sql = _normalized(_read())

    batch_legacy_at = sql.index(
        "rows written under the original three-sku contract"
    )
    batch_exact_at = sql.index(
        "content_factory_private.real_generation_sku_from_input(",
        batch_legacy_at,
    )
    batch_legacy = sql[batch_legacy_at:batch_exact_at]

    job_legacy_at = sql.index("preserve the installed old3 job contract")
    job_exact_at = sql.index(
        "content_factory_private.real_generation_sku_from_input(",
        job_legacy_at,
    )
    job_legacy = sql[job_legacy_at:job_exact_at]

    for legacy_model in (
        "gen4_turbo",
        "seedance2_fast",
        "seedream5_lite",
    ):
        assert f"'{legacy_model}'" in batch_legacy
        assert f"'{legacy_model}'" in job_legacy
    for exact_model in (
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ):
        assert f"'{exact_model}'" not in batch_legacy
        assert f"'{exact_model}'" not in job_legacy

    # CHECK compatibility is only for historical/replica restoration. Every
    # ordinary service-role insert/update still crosses the installed trigger
    # functions, which deliberately have no legacy-envelope bypass.
    for guard_name in (
        "content_factory_private.guard_generation_batch_contract",
        "content_factory_private.guard_generation_job_contract",
    ):
        guard = _normalized(_function(_read(), guard_name))
        assert "real_generation_sku_from_input(" in guard
        assert "sku_config is null" in guard
        assert "original three-sku contract" not in guard
        assert "installed old3 job contract" not in guard


def test_legacy_seedance_helper_remains_vertical_only() -> None:
    legacy = _normalized(
        _function(
            _read(), "content_factory_private.real_generation_sku_config"
        )
    )
    assert "model_value='seedance2_fast'" in legacy
    assert "p_format is distinct from '9:16'" in legacy
    assert legacy.index("p_format is distinct from '9:16'") < legacy.index(
        "real_generation_multimodel_sku("
    )


def test_snapshot_uses_shared_exact_seventeen_fields_only() -> None:
    validator = _normalized(
        _function(
            _read(),
            "content_factory_private.generation_selection_snapshot_valid",
        )
    )
    exact_keys = (
        "provider",
        "model",
        "model_public_label",
        "selection_source",
        "recommendation_reason_codes",
        "recommendation_warning_codes",
        "recommendation_catalog_version",
        "pricing_version",
        "estimated_cost_minor",
        "requested_duration_seconds",
        "requested_ratio",
        "requested_resolution",
        "requested_audio",
        "input_mode",
        "reference_count",
        "acceptance_status_at_launch",
        "provider_readiness_receipt_id",
    )
    for key in exact_keys:
        assert f"'{key}'" in validator
    assert "receipt_hash" not in validator
    assert "snapshot_version" not in validator
    assert "group by item.value having count(*)>1" in validator
    assert validator.count("group by item.value having count(*)>1") == 2


def test_one_recorder_preserves_old3_v3_and_requires_scope_for_new4_v4() -> None:
    recorder = _normalized(
        _function(_read(), "public.system_record_generation_provider_readiness")
    )
    for literal in (
        "v4_required boolean",
        "'generation-provider-readiness-receipt-v3'",
        "'generation-provider-readiness-receipt-v4'",
        "'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'",
        "'project_id','spec_id','spec_version','spec_hash'",
        "generation_multimodel_baseline_claim_v2",
        "membership.status='active'",
    ):
        assert literal in recorder

    # The exact legacy payload remains valid without the v4-only tuple. New4
    # requires every tuple field, and every non-new4 request rejects even a
    # partial/smuggled tuple. This is one endpoint, not a second receipt owner.
    base_required_at = recorder.index("or not p_payload ?& array[")
    base_required_end = recorder.index("]::text[]", base_required_at)
    base_required = recorder[base_required_at:base_required_end]
    for field in ("project_id", "spec_id", "spec_version", "spec_hash"):
        assert f"'{field}'" not in base_required
    assert "and ( not p_payload ?& array[ 'project_id','spec_id','spec_version','spec_hash' ]::text[]" in recorder
    assert "and p_payload ?| array[ 'project_id','spec_id','spec_version','spec_hash' ]::text[]" in recorder
    assert "if v4_required then receipt_body:=receipt_body || jsonb_build_object(" in recorder
    assert "else 'generation-provider-readiness-receipt-v3' end" in recorder
    assert "baseline_claim_value ->> 'scope_hash' else null end" in recorder


def test_v4_binder_recomputes_receipt_and_cross_checks_every_authority() -> None:
    binder = _normalized(
        _function(_read(), "content_factory_private.bind_generation_v4_launch")
    )
    for literal in (
        "generation-provider-readiness-receipt-v4",
        "generation_selection_snapshot_valid",
        "assert_generation_spec_current",
        "generation_spec_scope_v2",
        "real_generation_multimodel_sku",
        "generation_provider_launch_enabled",
        "checked_by is distinct from p_actor_id",
        "spend_confirmation",
        "generation_job_selection_snapshots",
        "generation_multimodel_baseline_claim_v2",
        "generation_multimodel_live_claim_v2",
        "provider_readiness_receipt_consumed",
    ):
        assert literal in binder
    assert binder.index("from content_factory.generation_job_selection_snapshots") < binder.index(
        "receipt_row.receipt_version"
    )
    assert "receipt_row.expires_at<=clock_timestamp()" in binder
    assert "job.project_id=p_project_id" in binder
    assert "job_row.requested_by<>p_actor_id" in binder


def test_live_claim_recomputes_actor_project_signal_and_consent_at_worker_claim() -> None:
    claim = _normalized(
        _function(
            _read(), "content_factory_private.generation_multimodel_live_claim_v2"
        )
    )
    assert "generation_multimodel_baseline_claim_v2" in claim
    assert "generation_spec_provider_start_stale" in claim
    assert "'role_not_allowed','generation_spec_project_scope_mismatch'" in claim
    assert "'content_review_product_category_unverified'" in claim
    assert "content_factory_private.json_hash(to_jsonb(spec_row.compiled_prompt))" in claim
    assert "signal_row.source<>'baseline'" in claim
    assert "generation_review_autostart_consents" in claim
    assert "generation_job_video_reference_bindings" in claim
    assert "generation_quality_guard_lineage" in claim
    assert "quality_lineage_row.source<>'baseline'" in claim
    assert "quality_lineage_hash" in claim

    baseline = _normalized(
        _function(
            _read(), "content_factory_private.generation_multimodel_baseline_claim_v2"
        )
    )
    assert "generation_spec_video_reference_bindings" in baseline

    binder = _normalized(
        _function(_read(), "content_factory_private.bind_generation_v4_launch")
    )
    replay_at = binder.index("if launch_row.id is not null then")
    fresh_at = binder.index("if jsonb_typeof(context_value)<>'object'", replay_at)
    replay = binder[replay_at:fresh_at]
    assert "generation_multimodel_live_claim_v2" in replay
    assert "launch_row.live_claim_snapshot is distinct from live_claim_value" in replay


def test_public_start_preserves_legacy_and_routes_only_new4() -> None:
    sql = _read()
    public_start = _normalized(_function(sql, "public.creator_start_real_generation"))
    private_start = _normalized(
        _function(
            sql,
            "content_factory_private.creator_start_real_generation_multimodel_v48",
        )
    )
    assert "creator_start_real_generation_pre_multimodel_v48" in public_start
    assert "creator_start_real_generation_multimodel_v48" in public_start
    for model in (
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ):
        assert f"'{model}'" in public_start
    assert "seedream5_lite" not in public_start
    assert "gen4_turbo" not in public_start
    assert "seedance2_fast" not in public_start

    policy_at = private_start.index("generation_provider_launch_enabled")
    command_at = private_start.index("begin_command")
    batch_at = private_start.index("insert into content_factory.generation_batches")
    assert policy_at < command_at < batch_at

    assert "require_workspace_project_access" in private_start
    assert "workspace_project_access_allowed" in private_start
    assert "generated_media_reviewer_access_allowed" in private_start
    assert "require_generation_spec_project_v49" in private_start
    assert "assert_generation_spec_current" in private_start
    assert "generation_multimodel_prompt_contract_valid" in private_start
    assert "bind_generation_v4_launch" in private_start
    insert_at = private_start.index("insert into content_factory.generation_jobs")
    assert private_start.index("bind_generation_v4_launch", insert_at) > insert_at
    assert "generation_video_reference_decided" in private_start
    assert "provider_task_id" not in private_start
    assert "http" not in private_start


def test_idempotency_is_actor_scoped_and_exact_replay_rebinds_snapshot() -> None:
    start = _normalized(
        _function(
            _read(),
            "content_factory_private.creator_start_real_generation_multimodel_v48",
        )
    )
    assert "replace(actor_id_value::text,'-','')" in start
    assert "raw_text_sha256(idempotency_key_value)" in start
    assert "creator_start_real_generation_multimodel_v48" in start
    assert "replay_value:=content_factory_private.begin_command" in start
    replay_at = start.index("if replay_value is not null then")
    bind_at = start.index("bind_generation_v4_launch", replay_at)
    return_at = start.index("return replay_value", replay_at)
    assert replay_at < bind_at < return_at
    assert "finish_command" in start


def test_no_client_cost_or_automatic_generation_can_cross_start() -> None:
    start = _normalized(
        _function(
            _read(),
            "content_factory_private.creator_start_real_generation_multimodel_v48",
        )
    )
    allowed_payload = start[: start.index("then raise exception", start.index("p_payload-array["))]
    assert "estimated_cost_minor" not in allowed_payload
    assert "estimated_credits" not in allowed_payload
    assert "automatic_generation" not in allowed_payload
    assert "automatic_spend" not in allowed_payload
    assert "(sku_value ->> 'estimated_cost_minor')::bigint" in start
    assert "(sku_value ->> 'estimated_credits')::bigint" in start
    assert "'automatic_generation',false" in start
    assert "'automatic_spend',false" in start


def test_existing_worker_state_machine_reads_the_exact_persisted_new4_sku() -> None:
    sql = _normalized(_read())
    patch_at = sql.index("do $patch_multimodel_worker_sku$")
    patch_end = sql.index("$patch_multimodel_worker_sku$;", patch_at)
    worker_patch = sql[patch_at:patch_end]
    assert "system_update_real_generation_v1(jsonb)" in worker_patch
    assert "real_generation_sku_from_input( job_row.provider, job_row.input )" in worker_patch
    assert "generation_multimodel_worker_sku_patch_target_invalid" in worker_patch
    assert "execute patched_definition" in worker_patch
    # The migration changes only SKU reconstruction; it does not add a second
    # transition, storage, completion or provider-transport owner.
    assert "update content_factory.generation_jobs" not in worker_patch
    assert "insert into content_factory.media_objects" not in worker_patch
    assert "provider_task_id" not in worker_patch


def test_new4_reuses_the_mature_append_only_quality_lineage() -> None:
    sql = _normalized(_read())
    assert "generation_quality_guard_lineage_model_v48_check" in sql
    start = _normalized(
        _function(
            _read(),
            "content_factory_private.creator_start_real_generation_multimodel_v48",
        )
    )
    assert "insert into content_factory.generation_quality_guard_lineage" in start
    assert "model_value,'baseline',null,'[]'::jsonb" in start
    assert "generation_quality_guard_lineage_conflict" in start


def test_new4_policy_is_launchable_only_through_the_exact_v4_authority_path() -> None:
    start = _normalized(
        _function(
            _read(),
            "content_factory_private.creator_start_real_generation_multimodel_v48",
        )
    )
    policy = _normalized(
        _function(
            _read(), "content_factory_private.generation_provider_launch_enabled"
        )
    )
    for model in (
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ):
        assert f"when 'runway:{model}' then true" in policy
    assert "from content_factory.organizations organization" in policy
    assert "organization.status='active'" in policy
    policy_check = start.index("generation_provider_launch_enabled")
    assert policy_check < start.index("current_profile_id")
    assert policy_check < start.index("begin_command")
    assert policy_check < start.index("insert into content_factory.generation_batches")
    assert "generation_multimodel_baseline_claim_v2" in _normalized(_read())
    assert "generation_multimodel_baseline_required" in _normalized(_read())


def test_status_read_after_start_preserves_exact_new4_selection() -> None:
    status = _normalized(_function(_read(), "public.creator_real_generation_status"))
    assert "creator_real_generation_status_pre_multimodel_v48" in status
    for model in (
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ):
        assert f"'{model}'" in status
    assert "{job,input_mode}" in status
    assert "{job,resolution}" in status
    assert "{job,last_frame}" in status
    assert "generation_review_autostart_consents" in status


def test_new4_video_and_spoken_audio_reuse_the_existing_review_owners() -> None:
    sql = _normalized(_read())
    helper = _normalized(
        _function(
            _read(),
            "content_factory_private.generation_runway_video_review_model_allowed",
        )
    )
    for model in (
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ):
        assert f"'{model}'" in helper
    assert "do $patch_generated_video_review_new4$" in sql
    for owner in (
        "enforce_generated_video_autopilot_input()",
        "creator_start_generated_video_review_pre_project_v47(jsonb)",
        "creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)",
    ):
        assert owner in sql
    assert "do $patch_generated_video_sound_new4$" in sql
    assert "record_content_review_sound_assessment" in sql
    assert "generation_video_sound_multimodel_patch_target_invalid" in sql
    assert "real_generation_sku_from_input(" in sql
    assert (
        "generation_job_row.provider, generation_job_row.input" in sql
    )

    speech = _normalized(
        _function(
            _read(), "content_factory_private.bind_generated_video_spoken_script"
        )
    )
    assert "generation_runway_video_review_model_allowed" in speech
    assert "job.input -> 'audio'='true'::jsonb" in speech
    assert "generated_video_spoken_script" in speech


def test_model_feature_flags_are_bounded_server_projections() -> None:
    creator = _normalized(
        _function(_read(), "public.creator_generation_model_feature_flags")
    )
    system = _normalized(
        _function(_read(), "public.system_generation_model_feature_flags")
    )
    owner = _normalized(
        _function(
            _read(), "content_factory_private.generation_model_feature_flags"
        )
    )
    assert "membership_role" in creator
    assert "membership_role" not in system
    assert "generation_google_veo_lite_v1" in owner
    assert "generation_runway_premium_v1" in owner
    assert "organization.settings" not in creator
    assert "organization.settings" not in system
    sql = _normalized(_read())
    assert (
        "revoke all on function public.system_generation_model_feature_flags(jsonb) "
        "from public, anon, authenticated"
    ) in sql
    assert (
        "grant execute on function public.system_generation_model_feature_flags(jsonb) "
        "to service_role"
    ) in sql


def test_migration_does_not_touch_ui_edge_or_external_providers() -> None:
    sql = _normalized(_read())
    assert "supabase/functions" not in sql
    assert "workspace-os" not in sql
    assert "fetch(" not in sql
    assert "net.http" not in sql
    assert "provider_call_started',true" not in sql
    assert "paid_call_started',true" not in sql
