"""Regression checks for v4.7 mutation-wrapper preservation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_MIGRATION = (ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql").read_text(encoding="utf-8")
SOUND_GATE_MIGRATION = (
    ROOT / "supabase/migrations/202608040004_generated_video_sound_release_gate.sql"
).read_text(encoding="utf-8")
COMPLIANCE_MIGRATION = (ROOT / "supabase/migrations/202607140007_placement_compliance_ack.sql").read_text(
    encoding="utf-8"
)


def test_public_mutation_wrapper_is_renamed_before_private_schema_transfer() -> None:
    start = PROJECT_MIGRATION.index("do $preserve_project_mutations$")
    end = PROJECT_MIGRATION.index("$preserve_project_mutations$;", start)
    preservation = PROJECT_MIGRATION[start:end]

    rename_statement = "'alter function public.%I(jsonb) rename to %I',\n        function_name, alias_name"
    transfer_statement = "'alter function public.%I(jsonb) set schema content_factory_private',\n        alias_name"

    assert "'creator_confirm_placement'" in preservation
    assert rename_statement in preservation
    assert transfer_statement in preservation
    assert preservation.index(rename_statement) < preservation.index(transfer_statement)
    assert (
        "'alter function public.%I(jsonb) set schema content_factory_private',\n        function_name"
    ) not in preservation


def test_placement_private_base_is_preserved_behind_the_project_wrapper() -> None:
    assert (
        "alter function public.creator_confirm_placement(jsonb)\n  set schema content_factory_private"
    ) in COMPLIANCE_MIGRATION
    assert "result := content_factory_private.creator_confirm_placement(p_payload)" in COMPLIANCE_MIGRATION
    assert "creator_confirm_placement_pre_project_v47" in PROJECT_MIGRATION


def test_project_media_guard_defers_empty_list_validation_to_inner_rpc() -> None:
    start = PROJECT_MIGRATION.index("create or replace function content_factory_private.call_project_scoped_v47")
    end = PROJECT_MIGRATION.index("create or replace function", start + 1)
    dispatcher = PROJECT_MIGRATION[start:end]

    assert "jsonb_typeof(media_ids_value) = 'array'" in dispatcher
    assert "media.project_id = project_id_value" in dispatcher
    assert "media.status = 'ready'" in dispatcher
    assert "jsonb_array_length(media_ids_value) < 1" not in dispatcher
    assert "jsonb_typeof(media_ids_value) <> 'array'" not in dispatcher


def test_sound_gate_precedes_project_scope_and_repairs_the_preserved_inner_video_command() -> None:
    assert "creator_approve_generated_video_review_pre_sound_gate_v1" in SOUND_GATE_MIGRATION

    repair_start = PROJECT_MIGRATION.index("do $repair_preserved_command_receipts_v47$")
    repair_end = PROJECT_MIGRATION.index("$repair_preserved_command_receipts_v47$;", repair_start)
    repair = PROJECT_MIGRATION[repair_start:repair_end]
    assert "'creator_approve_generated_video_review_pre_sound_gate_v1'" in repair
    assert "'creator_approve_generated_video_review_with_context_pre_project_v47'" not in repair

    assert "'creator_approve_generated_video_review_with_context_pre_project_v47'" in PROJECT_MIGRATION
