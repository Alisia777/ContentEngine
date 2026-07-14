from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607140004_seedance2_fast_8s_generation.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()


def _function(schema: str, name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{schema}\.{name}"
        rf"\s*\(\s*p_payload\s+jsonb[^)]*\)\s*returns\s+jsonb"
        rf"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing {schema}.{name}(jsonb)"
    return match.group("header").casefold(), match.group("body").casefold()


def test_migration_is_separate_and_ordered_after_paid_gen4() -> None:
    assert MIGRATION.name == "202607140004_seedance2_fast_8s_generation.sql"
    assert (ROOT / "supabase/migrations/202607140003_paid_runway_generation.sql").exists()
    assert LOWER.startswith("begin;")
    assert LOWER.rstrip().endswith("commit;")


def test_batches_store_queryable_sku_and_billing_facts() -> None:
    for column in (
        "add column provider text",
        "add column model text",
        "add column duration_seconds integer",
        "add column audio boolean",
        "add column estimated_cost_minor bigint",
        "add column estimated_credits bigint",
        "add column currency text",
    ):
        assert column in LOWER
    assert "generation_batches_sku_contract_check" in LOWER
    assert "model in ('mock', 'gen4_turbo', 'seedance2_fast')" in LOWER
    assert "generation_batches_estimated_cost_nonnegative_check" in LOWER
    assert "generation_batches_estimated_credits_nonnegative_check" in LOWER
    assert "estimated_cost_minor = 232" in LOWER
    assert "estimated_credits = 232" in LOWER
    assert "currency = 'usd'" in LOWER


def test_backfill_is_null_and_cast_safe_for_existing_gen4_rows() -> None:
    backfill = LOWER[: LOWER.index("alter table content_factory.generation_batches\n  alter column")]
    assert "coalesce(" in backfill
    assert "'gen4_turbo'" in backfill
    assert "~ '^[0-9]+$'" in backfill
    assert "when batch.mode = 'real' then 5" in backfill
    assert "when batch.mode = 'real' then 25" in backfill
    assert "nullif(batch.input #>> '{billing,currency}', '')" in backfill


def test_sku_config_preserves_gen4_and_adds_one_exact_seedance_sku() -> None:
    assert "real_generation_sku_config" in LOWER
    for token in (
        "p_model = 'gen4_turbo'",
        "p_duration = '5'::jsonb",
        "runway_gen4_turbo_5s_usd_0.25",
        "p_model = 'seedance2_fast'",
        "p_duration = '8'::jsonb",
        "p_audio = 'true'::jsonb",
        "p_format = '9:16'",
        "runway_seedance2_fast_8s_audio_usd_2.32",
        "'ratio', '720:1280'",
        "'estimated_cost_minor', 232",
        "'estimated_credits', 232",
    ):
        assert token in LOWER


def test_seedance_start_requires_exact_paid_inputs_and_approved_media() -> None:
    header, body = _function(
        "content_factory_private", "creator_start_seedance2_fast_8s"
    )
    assert "security definer" in header
    assert "set search_path = ''" in header
    for token in (
        "array['owner', 'admin', 'producer', 'operator']",
        "p_payload ->> 'model' is distinct from 'seedance2_fast'",
        "p_payload -> 'duration_seconds' is distinct from '8'::jsonb",
        "p_payload -> 'audio' is distinct from 'true'::jsonb",
        "p_payload ->> 'format' is distinct from '9:16'",
        "runway_seedance2_fast_8s_audio_usd_2.32",
        "real_generation_count_must_be_one",
        "jsonb_array_length(media_ids) <> 1",
        "media_row.status <> 'ready'",
        "media_row.product_id is distinct from product_id_value",
        "media_row.metadata -> 'rights_confirmed' is distinct from 'true'::jsonb",
        "seedance_approved_product_media_required",
    ):
        assert token in body
    assert re.search(r"not\s+in\s*\(\s*'product_photo'\s*,\s*'packshot'", body)
    assert "length(brief_value) < 1" in body
    assert "length(brief_value) > 1200" in body


def test_seedance_start_reuses_shared_idempotency_and_quota_boundaries() -> None:
    _, body = _function(
        "content_factory_private", "creator_start_seedance2_fast_8s"
    )
    assert "'creator_start_real_generation'" in body
    assert "begin_command(" in body
    assert "finish_command(" in body
    assert body.index("begin_command(") < body.index("real_generation_quota:organization")
    assert "real_generation_quota:user" in body
    assert "user_daily_jobs >= 10" in body
    assert "organization_daily_jobs >= 50" in body
    assert "assignee_open_jobs >= 1" in body
    assert "organization_open_jobs >= 3" in body


def test_start_wire_result_contains_exact_seedance_provider_input() -> None:
    _, body = _function(
        "content_factory_private", "creator_start_seedance2_fast_8s"
    )
    for token in (
        "'model', 'seedance2_fast'",
        "'duration_seconds', 8",
        "'audio', true",
        "'ratio', '720:1280'",
        "'prompt_text', prompt_value",
        "'input_object_name', media_row.object_name",
        "'output_object_name', output_object_name_value",
        "'estimated_cost_minor', 232",
        "'estimated_credits', 232",
        "'video_review'",
        "'blocked'",
    ):
        assert token in body


def test_public_start_dispatcher_preserves_gen4_and_strips_only_false_audio() -> None:
    header, body = _function("public", "creator_start_real_generation")
    assert "security definer" in header
    assert "creator_start_seedance2_fast_8s(p_payload)" in body
    assert "creator_start_gen4_turbo_5s(" in body
    assert "p_payload - 'audio'" in body
    assert "p_payload -> 'audio' is distinct from 'false'::jsonb" in body
    assert "{job,audio}" in body
    assert "{job,estimated_credits}" in body
    assert "alter function public.creator_start_real_generation(jsonb)" in LOWER
    assert "rename to creator_start_gen4_turbo_5s" in LOWER


def test_model_neutral_system_updater_writes_persisted_facts_directly() -> None:
    header, body = _function("public", "system_update_real_generation")
    assert "security definer" in header
    assert "for update" in body
    assert "real_generation_sku_config(" in body
    assert "batch_row.model is distinct from model_value" in body
    assert "batch_row.duration_seconds is distinct from duration_seconds_value" in body
    assert "batch_row.audio is distinct from audio_value" in body
    assert "actual_cost_minor = job.estimated_cost_minor" in body
    assert "'model', model_value" in body
    assert "'duration_seconds', duration_seconds_value" in body
    assert "'audio', audio_value" in body
    assert "'estimated_credits', estimated_credits_value" in body
    assert "normalize_seedance_job_cost" not in LOWER
    assert "normalize_seedance_media_metadata" not in LOWER
    assert "normalize_seedance_task_result" not in LOWER


def test_system_state_machine_keeps_atomic_claim_and_storage_validation() -> None:
    _, body = _function("public", "system_update_real_generation")
    assert "if job_row.status = 'queued'" in body
    assert "set status = 'starting'" in body
    assert "claimed := true" in body
    assert "claimed := false" in body
    assert "stored_provider_task_id is distinct from provider_task_id_value" in body
    assert "storage.objects" in body
    assert "storage_object.user_metadata" in body
    assert "storage_sha256 <> sha256_value" in body
    assert "mime_type_value <> 'video/mp4'" in body
    assert "set status = 'review'" in body
    assert "ambiguous provider post outcomes remain `starting`" in body


def test_status_wire_contract_adds_audio_and_credits_without_losing_fields() -> None:
    header, body = _function("public", "creator_real_generation_status")
    assert "security definer" in header
    assert "array['owner', 'admin', 'producer', 'reviewer', 'operator']" in body
    for field in (
        "'provider_task_id'",
        "'model'",
        "'duration_seconds'",
        "'audio'",
        "'ratio'",
        "'estimated_cost_minor'",
        "'estimated_credits'",
        "'actual_cost_minor'",
        "'output_object_name'",
        "'output_media_id'",
        "'failure_code'",
        "'updated_at'",
    ):
        assert field in body
    assert "coalesce((job_row.input ->> 'audio')::boolean, false)" in body


def test_rpc_privileges_keep_users_and_service_role_separate() -> None:
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+public\.creator_start_real_generation\(jsonb\)"
        r"\s+from\s+public\s*,\s*anon",
        LOWER,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+public\.creator_start_real_generation\(jsonb\)"
        r"\s+to\s+authenticated",
        LOWER,
    )
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+public\.system_update_real_generation\(jsonb\)"
        r"\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
        LOWER,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+public\.system_update_real_generation\(jsonb\)"
        r"\s+to\s+service_role",
        LOWER,
    )
