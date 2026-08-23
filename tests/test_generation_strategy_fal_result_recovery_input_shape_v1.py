from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    'supabase/migrations/'
    '202608200006_generation_strategy_fal_result_recovery_input_shape_v1.sql'
)
PGTAP = ROOT / (
    'supabase/tests/'
    'generation_strategy_fal_result_recovery_input_shape_test.sql'
)
BASE_MIGRATION = ROOT / (
    'supabase/migrations/'
    '202608200005_generation_strategy_fal_result_recovery_v1.sql'
)


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_append_only_patch_and_regression_are_valid_postgresql() -> None:
    migration = _text(MIGRATION)
    pgtap = _text(PGTAP)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert migration.startswith('begin;\n')
    assert migration.rstrip().endswith('commit;')
    assert pgtap.startswith('begin;\n')
    assert pgtap.rstrip().endswith('rollback;')
    assert len(list((ROOT / 'supabase/migrations').glob('202608200006_*.sql'))) == 1


def test_patch_replaces_exactly_the_stale_guard_with_canonical_identity() -> None:
    migration = _text(MIGRATION)
    base = _text(BASE_MIGRATION)
    stale = """     or (job_row.input ->> 'strategy_id') is distinct from
       'viral_product_swap'"""
    canonical = """     or (job_row.input #>> '{strategy_execution,strategy_id}')
       is distinct from receipt_row.strategy_id"""

    assert stale in base
    assert stale in migration
    assert canonical in migration
    assert 'hit_count_value <> 1' in migration
    assert 'patched_value := replace(' in migration
    assert 'definition_value, search_value, replacement_value' in migration
    assert "execute patched_value;" in migration
    assert 'create or replace function\n+  public.' not in migration


def test_exact_production_input_shape_is_the_regression_fixture() -> None:
    pgtap = _text(PGTAP)

    assert "'provider', 'fal'" in pgtap
    assert "'strategy_recipe', 'product_swap'" in pgtap
    assert "'strategy_execution', jsonb_build_object(" in pgtap
    assert "'strategy_id', 'viral_product_swap'" in pgtap
    assert "input_value ->> 'strategy_id' is null" in pgtap
    assert "input_value #>> '{strategy_execution,strategy_id}'" in pgtap
    assert 'exact production input shape satisfies' in pgtap


def test_missing_and_json_null_nested_strategy_identity_fail_closed() -> None:
    migration = _text(MIGRATION)
    pgtap = _text(PGTAP)

    assert (
        "(job_row.input #>> '{strategy_execution,strategy_id}')\n"
        "       is distinct from receipt_row.strategy_id"
    ) in migration
    assert 'missing canonical strategy identity still fails closed' in pgtap
    assert 'JSON null canonical strategy identity still fails closed' in pgtap
    assert "'strategy_id', null" in pgtap


def test_patch_preserves_other_guards_authority_response_and_money_contract() -> None:
    migration = _text(MIGRATION)

    for preserved in (
        "(job_row.input ->> 'provider') is distinct from 'fal'",
        "(job_row.input ->> 'strategy_recipe') is distinct from 'product_swap'",
        "(job_row.input #>> '{strategy_execution,version}') is distinct from",
        'generation-strategy-provider-result-recovery-response-v1',
        'ledger_hash_after_value is distinct from ledger_hash_before_value',
        "has_function_privilege(\n       'authenticated'",
        "has_function_privilege(\n       'service_role'",
    ):
        assert preserved in migration

    lower = migration.casefold()
    for forbidden in (
        'insert into content_factory.generation_spend_ledger',
        'update content_factory.generation_spend_ledger',
        'delete from content_factory.generation_spend_ledger',
        'insert into content_factory.generation_strategy_provider_status_events',
        'update content_factory.generation_jobs',
        'http_post',
        'net.http',
    ):
        assert forbidden not in lower
