"""Regression checks for v4.7 mutation-wrapper preservation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_MIGRATION = (ROOT / "supabase/migrations/202608030006_project_scoped_workflow.sql").read_text(encoding="utf-8")
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
