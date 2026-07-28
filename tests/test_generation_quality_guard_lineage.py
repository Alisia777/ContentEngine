from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607280002_generation_quality_guard_lineage.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generation_quality_guard_lineage_test.sql"
).read_text(encoding="utf-8")


def test_quality_guard_lineage_sql_and_pgtap_are_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(PGTAP)


def test_lineage_persists_only_bounded_structural_causal_evidence() -> None:
    for token in (
        "generation_quality_guard_lineage",
        "generation_job_id uuid not null",
        "applied_policy_hash text",
        "guard_codes jsonb not null",
        "prompt_hash text not null",
        "unique (organization_id, generation_job_id)",
        "source = 'performance_learning'",
        "source in ('baseline', 'approved_research')",
        "guard_codes = '[]'::jsonb",
    ):
        assert token in MIGRATION
    table_contract = MIGRATION[
        MIGRATION.index("create table if not exists")
        : MIGRATION.index(
            "create index if not exists "
            "generation_quality_guard_lineage_learning_idx"
        )
    ]
    for forbidden in (
        "prompt_text",
        "review_comment",
        "transcript",
        "finding",
        "recommendation",
        "caption",
        "script",
    ):
        assert forbidden not in table_contract.lower()


def test_guard_code_validator_is_small_allowlisted_and_fail_closed() -> None:
    helper = MIGRATION[
        MIGRATION.index(
            "valid_generation_quality_guard_codes("
        )
        : MIGRATION.index(
            "create table if not exists"
        )
    ]
    for code in (
        "product_fidelity",
        "technical_stability",
        "audio_quality",
        "speech_fidelity",
        "hook_clarity",
        "visual_quality",
        "trust",
        "platform_fit",
    ):
        assert f"'{code}'" in helper
    for token in (
        "jsonb_typeof(p_guard_codes) <> 'array'",
        "jsonb_array_length(p_guard_codes) > 3",
        "guard_code = any(seen_codes)",
        "exception when others then",
        "return false",
    ):
        assert token in helper


def test_server_policy_is_recomputed_before_any_paid_database_command() -> None:
    missing_context_gate = MIGRATION.index(
        "if learning_context is null"
    )
    identity_resolution = MIGRATION.index(
        "organization_id :=\n    content_factory_private.resolve_organization("
    )
    policy_call = MIGRATION.index(
        "server_policy := public.creator_generation_learning_policy("
    )
    paid_command = MIGRATION.index(
        ".creator_start_real_generation_pre_guard_lineage_v8(p_payload)",
        policy_call,
    )
    lineage_insert = MIGRATION.index(
        "insert into content_factory.generation_quality_guard_lineage"
    )
    assert missing_context_gate < identity_resolution
    assert policy_call < paid_command < lineage_insert
    for token in (
        "server_policy -> 'quality_guard_codes'",
        "server_policy -> 'applied'",
        "learning_context ->> 'applied_policy_hash'",
        "generation_quality_guard_policy_stale",
    ):
        assert token in MIGRATION
    assert "provider_tasks" not in MIGRATION
    assert "runway" not in MIGRATION.lower()


def test_lineage_is_bound_to_exact_job_creative_signal_and_prompt_hash() -> None:
    for token in (
        "job_row.requested_by is distinct from user_id",
        "job_row.input ->> 'platform'",
        "job_row.input ->> 'model'",
        "job_row.input ->> 'prompt_text'",
        "p_payload ->> 'brief'",
        "creative_signal.product_id is distinct from job_row.product_id",
        "creative_signal.source is distinct from learning_source_value",
        "creative_signal.applied_policy_hash",
        "creative_signal.prompt_hash is distinct from prompt_hash_value",
        "content_factory_private.json_hash(",
        "generation_quality_guard_lineage_binding_invalid",
        "generation_quality_guard_lineage_conflict",
    ):
        assert token in MIGRATION


def test_legacy_calls_keep_original_validation_and_error_ordering() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation("
        )
        :
    ]
    context_gate = wrapper.index("if learning_context is null")
    direct_return = wrapper.index(
        ".creator_start_real_generation_pre_guard_lineage_v8(p_payload)",
        context_gate,
    )
    organization_resolution = wrapper.index(
        "content_factory_private.resolve_organization(p_payload)"
    )
    current_user = wrapper.index(
        "content_factory_private.current_profile_id()"
    )
    assert context_gate < direct_return < organization_resolution < current_user


def test_lineage_is_private_append_only_and_idempotent() -> None:
    for token in (
        "enable row level security",
        "revoke all on content_factory.generation_quality_guard_lineage",
        "from public, anon, authenticated",
        "generation_quality_guard_lineage_append_only",
        "before update or delete",
        "on conflict (organization_id, generation_job_id) do nothing",
        "existing_lineage.guard_codes is distinct from guard_codes_value",
        "existing_lineage.prompt_hash is distinct from prompt_hash_value",
    ):
        assert token in MIGRATION
    assert "select plan(15);" in PGTAP
    assert PGTAP.rstrip().endswith("rollback;")


def test_final_wrapper_keeps_public_rpc_and_private_complete_predecessor() -> None:
    for token in (
        "rename to creator_start_real_generation_pre_guard_lineage_v8",
        "revoke all on function",
        "from public, anon, authenticated, service_role",
        "create or replace function public.creator_start_real_generation(",
        "security definer",
        "grant execute on function public.creator_start_real_generation(jsonb)",
        "to authenticated",
        "notify pgrst, 'reload schema'",
    ):
        assert token in MIGRATION
