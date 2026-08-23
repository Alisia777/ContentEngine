from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608160004_writable_authenticated_read_rpcs.sql"
)
PGTAP = ROOT / "supabase/tests/writable_authenticated_read_rpcs_test.sql"
NOTIFICATION_PGTAP = (
    ROOT / "supabase/tests/notification_action_validation_v491_test.sql"
)

EXPOSED_RPCS = (
    "creator_generation_strategy_asset_candidates",
    "creator_generation_strategy_repeat_data",
    "creator_project_media",
    "creator_project_members",
    "creator_project_placement",
    "contentengine_generation_video_reference_lineage",
    "creator_validate_notification_action",
    "workspace_trash_browser",
)


def test_writable_read_rpc_migration_is_explicit_and_transactional() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    lower = source.casefold()

    assert source.lstrip().casefold().startswith("begin;")
    assert source.rstrip().casefold().endswith("commit;")
    assert "notify pgrst, 'reload schema';" in lower
    assert "create or replace function" not in lower
    assert "grant execute" not in lower
    assert "revoke all" not in lower

    for function_name in EXPOSED_RPCS:
        assert f"alter function public.{function_name}(jsonb) volatile;" in lower


def test_writable_read_rpc_migration_fails_loudly_without_acl_drift() -> None:
    source = MIGRATION.read_text(encoding="utf-8").casefold()

    assert "to_regprocedure(" in source
    assert "procedure_oid is null" in source
    assert "must_be_volatile" in source
    assert "has_function_privilege('authenticated'" in source
    assert "has_function_privilege('anon'" in source
    assert "has_function_privilege(" in source and "'service_role'" in source
    assert "execute_acl_changed" in source


def test_pgtap_covers_volatility_acl_authenticated_execution_and_no_spend() -> None:
    source = PGTAP.read_text(encoding="utf-8").casefold()

    assert "set local role authenticated;" in source
    assert "creator_generation_strategy_asset_candidates" in source
    assert "creator_project_media" in source
    assert source.count("lives_ok(") >= 2
    assert "sqlstate 25006" in source
    assert "generation_spend_ledger" in source
    assert "generation_batches" in source
    assert "generation_jobs" in source


def test_existing_notification_validator_contract_requires_writable_rpc() -> None:
    source = NOTIFICATION_PGTAP.read_text(encoding="utf-8").casefold()

    assert "'v'" in source
    assert "writable transaction for authenticated profile sync" in source
    assert "stable and read-only by contract" not in source
