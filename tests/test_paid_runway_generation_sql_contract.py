from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140003_paid_runway_generation.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()


def _function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{name}"
        rf"\s*\(\s*p_payload\s+jsonb[^)]*\)\s*returns\s+jsonb"
        rf"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing {name}(jsonb)"
    return match.group("header").casefold(), match.group("body").casefold()


def test_migration_is_ordered_after_member_and_owner_changes() -> None:
    assert MIGRATION.name == "202607140003_paid_runway_generation.sql"
    assert (ROOT / "supabase/migrations/202607140002_owner_display_name.sql").exists()
    assert LOWER.startswith("begin;")
    assert LOWER.rstrip().endswith("commit;")


def test_table_contract_preserves_mock_and_narrows_real_runway_rows() -> None:
    assert "mode in ('mock', 'real')" in LOWER
    assert "provider in ('mock', 'runway')" in LOWER
    assert "generation_batches_spend_contract_check" in LOWER
    assert "generation_jobs_spend_contract_check" in LOWER
    assert "generation_jobs_estimated_cost_nonnegative_check" in LOWER
    assert "generation_jobs_actual_cost_nonnegative_check" in LOWER
    assert "estimated_cost_minor = 25" in LOWER
    assert "mode = 'mock'" in LOWER
    assert "provider = 'mock'" in LOWER
    assert "not allow_real_spend" in LOWER
    assert "actual_cost_minor = 0" in LOWER
    assert "guard_generation_batch_contract" in LOWER
    assert "guard_generation_job_contract" in LOWER


def test_browser_rpcs_are_hardened_and_system_rpc_is_service_only() -> None:
    for name in ("creator_start_real_generation", "creator_real_generation_status"):
        header, _ = _function(name)
        assert "security definer" in header
        assert "set search_path = ''" in header
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{name}\(jsonb\)"
            rf"\s+from\s+public\s*,\s*anon",
            LOWER,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{name}\(jsonb\)"
            rf"\s+to\s+authenticated",
            LOWER,
        )

    header, _ = _function("system_update_real_generation")
    assert "security definer" in header
    assert "set search_path = ''" in header
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


def test_start_rpc_has_exact_paid_sku_media_and_role_gates() -> None:
    _, body = _function("creator_start_real_generation")
    for token in (
        "array['owner', 'admin', 'producer', 'operator']",
        "real_generation_count_must_be_one",
        "exact_one_product_media_required",
        "p_payload ->> 'mode' is distinct from 'real'",
        "p_payload ->> 'provider' is distinct from 'runway'",
        "p_payload ->> 'model' is distinct from 'gen4_turbo'",
        "p_payload -> 'duration_seconds' is distinct from '5'::jsonb",
        "p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb",
        "runway_gen4_turbo_5s_usd_0.25",
        "estimated_cost_minor', 25",
        "estimated_credits', 25",
        "currency', 'usd'",
    ):
        assert token in body
    assert re.search(r"not\s+in\s*\(\s*'product_photo'\s*,\s*'packshot'", body)
    assert "jsonb_array_length(media_ids) <> 1" in body
    assert "media_row.status <> 'ready'" in body
    assert "media_row.product_id is distinct from product_id_value" in body


def test_start_rpc_serializes_strict_concurrency_and_daily_quotas() -> None:
    _, body = _function("creator_start_real_generation")
    assert "real_generation_quota:organization" in body
    assert "real_generation_quota:user" in body
    assert body.index("real_generation_quota:organization") < body.index(
        "real_generation_user_daily_quota_exceeded"
    )
    for error in (
        "real_generation_user_daily_quota_exceeded",
        "real_generation_organization_daily_quota_exceeded",
        "real_generation_assignee_concurrency_exceeded",
        "real_generation_organization_concurrency_exceeded",
    ):
        assert error in body
    assert "user_daily_jobs >= 10" in body
    assert "organization_daily_jobs >= 50" in body
    assert "assignee_open_jobs >= 1" in body
    assert "organization_open_jobs >= 3" in body


def test_start_result_is_the_safe_edge_provider_contract() -> None:
    _, body = _function("creator_start_real_generation")
    for field in (
        "'batch_id', batch_id_value",
        "'status', 'queued'",
        "'provider', 'runway'",
        "'model', 'gen4_turbo'",
        "'duration_seconds', 5",
        "'ratio', ratio_value",
        "'prompt_text', prompt_value",
        "'input_object_name', media_row.object_name",
        "'output_object_name', output_object_name_value",
        "'estimated_cost_minor', 25",
    ):
        assert field in body
    assert "when '9:16' then '720:1280'" in body
    assert "when '16:9' then '1280:720'" in body
    assert "else '960:960'" in body
    assert "'job_id', job_id_value" in body
    assert "'video_review'" in body
    assert "'blocked'" in body


def test_starting_claim_closes_duplicate_paid_provider_calls() -> None:
    _, body = _function("system_update_real_generation")
    starting = body[body.index("if status_value = 'starting'") :]
    assert "if job_row.status = 'queued'" in starting
    assert "set status = 'starting'" in starting
    assert "claimed := true" in starting
    assert "claimed := false" in starting
    assert "for update" in body
    assert "'claimed', claimed" in starting
    assert "an ambiguous runway" in body
    assert "remains `starting`" in body


def test_active_paid_review_task_cannot_be_unblocked_by_generic_actions() -> None:
    assert "guard_real_generation_review_task" in LOWER
    assert "real_generation_review_task_guard" in LOWER
    assert "real_generation_review_task_locked" in LOWER
    assert "generation_status in ('queued', 'starting', 'submitted', 'processing')" in LOWER
    assert "new.status <> 'blocked'" in LOWER
    assert "generation_status in ('failed', 'cancelled')" in LOWER
    assert "new.status <> 'cancelled'" in LOWER


def test_provider_transitions_require_one_immutable_task_id() -> None:
    _, body = _function("system_update_real_generation")
    assert "generation_jobs_runway_provider_task_uq" in LOWER
    assert "provider_task_id_invalid" in body
    assert "stored_provider_task_id is distinct from provider_task_id_value" in body
    assert "job_row.status <> 'starting'" in body
    assert "job_row.status <> 'submitted'" in body
    assert "job_row.status <> 'processing'" in body
    assert "real_generation_provider_task_mismatch" in body
    assert "job_row.status in ('submitted', 'processing')" in body
    assert "provider_task_id_value is null" in body
    assert "job_row.status in ('queued', 'starting') and provider_task_id_value is not null" in body


def test_success_is_bound_to_exact_storage_mp4_hash_task_and_media() -> None:
    _, body = _function("system_update_real_generation")
    for token in (
        "storage.objects",
        "storage_object.user_metadata",
        "storage_user_metadata ->> 'sha256'",
        "storage_metadata ->> 'sha256'",
        "storage_size <> size_bytes_value",
        "storage_mime_type <> 'video/mp4'",
        "storage_sha256 <> sha256_value",
        "output_object_name_value is distinct from job_row.input ->> 'output_object_name'",
        "split_part(output_object_name_value, '/', 2) <> job_row.assigned_to::text",
        "linked_task_count <> 1",
        "task_row.id::text is distinct from job_row.input ->> 'review_task_id'",
        "'kind', 'generated_video'",
        "set status = 'succeeded'",
        "set status = 'review'",
        "total_created = 1",
    ):
        assert token in body


def test_failed_path_accepts_only_sanitized_codes_and_no_raw_detail() -> None:
    _, body = _function("system_update_real_generation")
    assert "real_generation_update_payload_invalid" in body
    assert "real_generation_failure_code_invalid" in body
    assert "provider_credits_unavailable" in body
    assert "provider_task_failed" in body
    assert "output_upload_failed" in body
    assert "failure_code_value" in body
    assert "provider_message" not in body
    assert "provider_body" not in body
    assert "provider_error" not in body


def test_user_status_is_fail_closed_and_timeout_recoverable() -> None:
    _, body = _function("creator_real_generation_status")
    assert "array['owner', 'admin', 'producer', 'reviewer', 'operator']" in body
    assert "manager_scope or job.requested_by = user_id or job.assigned_to = user_id" in " ".join(
        body.split()
    )
    assert "real_generation_not_found" in body
    for field in (
        "'provider_task_id'",
        "'estimated_cost_minor'",
        "'actual_cost_minor'",
        "'output_object_name'",
        "'output_media_id'",
        "'failure_code'",
        "'updated_at'",
    ):
        assert field in body


def test_bootstrap_capability_matches_the_new_database_gate() -> None:
    _, body = _function("creator_bootstrap")
    assert "content_factory_private.creator_bootstrap(p_payload)" in body
    assert "workspace_open" in body
    assert "('owner', 'admin', 'producer', 'operator')" in body
    assert "{capabilities,real_generation}" in body
    assert "alter function public.creator_bootstrap(jsonb)" in LOWER
    assert "set schema content_factory_private" in LOWER
