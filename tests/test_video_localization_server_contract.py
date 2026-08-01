from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
STORAGE = (
    MIGRATIONS / "202608010001_video_localization_storage.sql"
).read_text(encoding="utf-8")
CREATOR = (
    MIGRATIONS / "202608010002_video_localization_creator_rpcs.sql"
).read_text(encoding="utf-8")
PROVIDER = (
    MIGRATIONS / "202608010003_video_localization_provider_receipts.sql"
).read_text(encoding="utf-8")
ALL_SQL = "\n".join((STORAGE, CREATOR, PROVIDER))


def test_localization_storage_is_private_and_durable() -> None:
    for marker in (
        "content_factory.video_source_approvals",
        "content_factory.video_localization_batches",
        "content_factory.video_localization_assignments",
        "content_factory.video_localization_qa_decisions",
        "content_factory_private.video_localization_provider_operations",
        "enable row level security",
        "from public, anon, authenticated",
        "to service_role",
        "plan_hash text not null",
        "assignment_hash text not null",
        "request_hash text not null",
        "provider_task_ref_hash text",
    ):
        assert marker in STORAGE


def test_harly_batch_is_exactly_five_sources_times_two_modes() -> None:
    for marker in (
        "harly_five_sources_required",
        "harly_subtitles_and_dub_modes_required",
        "harly_ten_output_contract_required",
        "duplicate_localization_source_asset",
        'normalized_modes jsonb := \'["subtitles", "dub_audio"]\'::jsonb',
        "jsonb_array_length(source_ids) <> 5",
        "jsonb_array_length(assignments_value) <> 10",
        "case when selected.sequence <= 2 then 1 else 2 end",
        "estimated_savings_ratio",
    ):
        assert marker in CREATOR


def test_source_approval_requires_exact_product_rights_and_qa() -> None:
    for marker in (
        "localization_source_rights_or_qa_required",
        "localization_source_media_invalid",
        "media_row.product_id is distinct from product_id_value",
        "media_row.mime_type not like 'video/%'",
        "media_row.sha256",
        "source_relationship in ('owned', 'licensed')",
        "array['owner', 'admin', 'producer']",
    ):
        assert marker in CREATOR or marker in STORAGE


def test_wave_two_is_server_gated_by_two_outputs_and_human_qa() -> None:
    for marker in (
        "localization_batch_not_waiting_for_qa",
        "localization_wave1_outputs_incomplete",
        "localization_qa_checklist_incomplete",
        "product_fidelity",
        "language_quality",
        "no_common_defect",
        "rights_ok",
        "wave2_ready",
        "wave1_qa_rejected",
    ):
        assert marker in CREATOR or marker in STORAGE


def test_provider_operation_is_one_at_a_time_and_fail_closed() -> None:
    for marker in (
        "localization_operation_request_mismatch",
        "localization_batch_has_inflight_assignment",
        "localization_operation_terminal",
        "localization_operation_transition_invalid",
        "localization_provider_task_receipt_required",
        "localization_output_media_invalid",
        "batch_paused_for_reconciliation",
        "provider_outcome_replay_forbidden",
        "when 'unknown' then 'frozen'",
        "status = 'paused'",
        "status = 'qa_required'",
        "status = 'completed'",
    ):
        assert marker in PROVIDER


def test_unknown_provider_outcome_cannot_be_automatically_retried() -> None:
    assert "operation_row.status in ('settled', 'frozen', 'failed')" in PROVIDER
    assert "operation_row.status = 'released'" in PROVIDER
    assert "requested_status <> 'reserved'" in PROVIDER
    assert "requested_status = 'unknown'" in PROVIDER
    assert "provider_outcome_replay_forbidden', requested_status = 'unknown'" in PROVIDER


def test_creator_and_service_privilege_boundaries_are_separate() -> None:
    for function_name in (
        "creator_approve_video_localization_source",
        "creator_create_video_localization_batch",
        "creator_video_localization_batch",
        "creator_decide_video_localization_wave",
        "creator_cancel_video_localization_batch",
    ):
        assert f"grant execute on function public.{function_name}(jsonb)" in CREATOR
        assert "to authenticated" in CREATOR
    assert (
        "revoke all on function "
        "public.system_update_video_localization_assignment(jsonb)\n"
        "  from public, anon, authenticated"
    ) in PROVIDER
    assert (
        "grant execute on function "
        "public.system_update_video_localization_assignment(jsonb)\n"
        "  to service_role"
    ) in PROVIDER


def test_localization_contract_never_stores_raw_competitor_or_prompt_text() -> None:
    forbidden_column = re.compile(
        r"\b(?:url|source_url|caption|prompt|transcript|raw_text|provider_prompt)\s+text\b",
        re.IGNORECASE,
    )
    assert not forbidden_column.search(ALL_SQL)
    assert "http://" not in ALL_SQL
    assert "https://" not in ALL_SQL


def test_all_security_definer_functions_pin_an_empty_search_path() -> None:
    functions = re.findall(
        r"create or replace function\s+[^;]+?\$\$;",
        CREATOR + "\n" + PROVIDER,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert functions
    for function in functions:
        if "security definer" in function.lower():
            assert "set search_path = ''" in function.lower()


def test_migrations_are_transactional_and_ordered() -> None:
    for source in (STORAGE, CREATOR, PROVIDER):
        assert source.startswith("begin;\n")
        assert source.rstrip().endswith("commit;")
    assert "video_source_approvals" in STORAGE
    assert "creator_create_video_localization_batch" in CREATOR
    assert "system_update_video_localization_assignment" in PROVIDER
