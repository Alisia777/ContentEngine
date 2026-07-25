from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240013_repair_conflict_target_inference.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.casefold()


def test_forward_repair_is_transactional_and_ordered() -> None:
    assert MIGRATION.lstrip().casefold().startswith("begin;")
    assert MIGRATION.rstrip().casefold().endswith("commit;")
    assert (
        ROOT
        / "supabase/migrations/202607240012_generation_learning_rpc_writable_transaction.sql"
    ).exists()


def test_platform_and_learning_upserts_bind_named_constraints() -> None:
    for marker in (
        "training_walkthrough_progress_owner_module_walkthrough_uq",
        "generation_creative_signals_org_job_uq",
        "public.creator_submit_platform_simulator(jsonb)",
        "public.creator_start_real_generation(jsonb)",
        "pg_get_functiondef",
        "regexp_replace",
        "execute repaired_definition",
        "platform_simulator_conflict_target_not_found",
        "generation_learning_conflict_target_not_found",
        "conflict_target_repair_contract_failed",
    ):
        assert marker in LOWER


def test_repair_preserves_function_bodies_and_changes_only_conflict_targets() -> None:
    assert "drop function" not in LOWER
    assert "create or replace function public.creator_submit_platform_simulator" not in LOWER
    assert "create or replace function public.creator_start_real_generation" not in LOWER
    assert LOWER.count("repaired_definition = function_definition") == 2
    assert LOWER.count("execute repaired_definition") == 2
