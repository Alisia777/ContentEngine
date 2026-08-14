import hashlib
import re
from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130008_generation_strategy_spec_mechanics_v1.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "generation_strategy_spec_mechanics_v1_test.sql"
)
FROZEN = {
    ROOT
    / "supabase"
    / "migrations"
    / "202608130006_generation_strategy_authority_v1.sql": (
        "f8184163e9270a7d26220550f01effe5127f9dcba061af862b03f774b030f600"
    ),
    ROOT
    / "supabase"
    / "migrations"
    / "202608130007_generation_strategy_execution_v1.sql": (
        "cb2b1039f30eec07cc6e8e1d2b7f1e2b005210eccd47c29f23d7ca4ed572fed7"
    ),
}
SPEC_BASE = ROOT / "supabase" / "migrations" / "202608030017_generation_spec_control.sql"
MULTIMODEL = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130002_generation_multimodel_authority.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def _function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create or replace function\s+{re.escape(qualified_name)}\(",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise AssertionError(f"missing function: {qualified_name}")
    next_match = re.search(
        r"\ncreate or replace function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end_at = len(source) if next_match is None else match.end() + next_match.start()
    return source[match.start() : end_at]


def test_migration_and_pgtap_parse_and_frozen_contracts_are_untouched() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert len(parse_sql(migration)) >= 25
    assert len(parse_sql(pgtap)) >= 12
    for path, expected in FROZEN.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_plpgsql_strategy_scope_case_expression_is_parser_safe() -> None:
    sql = _read(MIGRATION)
    scope = _function(
        sql,
        "content_factory_private.generation_strategy_spec_scope_v1",
    )

    assert "or input_mode_value <> (case strategy_id_value" in scope
    assert "or input_mode_value <> case strategy_id_value" not in scope


def test_strategy_scope_is_explicit_recipe_authority_not_model_proxy() -> None:
    sql = _read(MIGRATION)
    scope = _function(
        sql,
        "content_factory_private.generation_strategy_spec_scope_v1",
    )

    for key in (
        "authority_kind",
        "strategy_id",
        "recipe",
        "input_mode",
        "duration_seconds",
        "ratio",
        "resolution",
        "audio",
        "selection",
        "selection_hash",
        "asset_snapshot",
        "asset_snapshot_hash",
        "source",
        "source_hash",
        "mechanics",
        "mechanics_hash",
    ):
        assert f"'{key}'" in scope
    assert "'authority_kind' <> 'strategy_recipe'" in scope
    assert "generation_strategy_recipe_price(" in scope
    assert "generation_strategy_selection_snapshot_valid_v1(" in scope
    assert "json_hash(p_scope -> 'selection')" in scope
    assert "json_hash(p_scope -> 'asset_snapshot')" in scope
    assert "pinned.value ->> 'sha256' !~ '^[0-9a-f]{64}$'" in scope
    assert "target_media_ids_value[" in scope
    assert "least(5, cardinality(target_media_ids_value))" in scope
    assert "product_ugc" not in scope
    rpc = _function(sql, "public.creator_prepare_generation_strategy_spec")
    assert "seedance" not in rpc.lower()
    assert "gen4" not in rpc.lower()
    assert "veo" not in rpc.lower()


def test_dynamic_compiler_patch_is_crlf_normalized_exact_and_fail_closed() -> None:
    sql = _read(MIGRATION)
    patch = _section(
        sql,
        "do $patch_generation_strategy_spec_v1$",
        "alter table content_factory.generation_spec_versions\n  drop constraint",
    )

    assert "replace(\n    pg_catalog.pg_get_functiondef(" in patch
    assert "E'\\r\\n', E'\\n'" in patch
    # Four replacements each assert old=1/new=0 before mutation and
    # old=0/new=1 afterwards; three final authority markers are exact-once.
    assert patch.count("length(patched_definition) - length(replace(") == 19
    assert patch.count("/ length(old_fragment) <> 1") == 4
    assert patch.count("/ length(new_fragment) <> 0") == 4
    assert patch.count("/ length(old_fragment) <> 0") == 4
    assert patch.count("/ length(new_fragment) <> 1") == 4
    for marker in (
        "generation_strategy_spec_patch_owner_invalid",
        "generation_strategy_spec_patch_scope_target_invalid",
        "generation_strategy_spec_patch_recipe_target_invalid",
        "generation_strategy_spec_patch_identity_target_invalid",
        "generation_strategy_spec_patch_hash_target_invalid",
        "generation_strategy_spec_patch_marker_invalid",
    ):
        assert marker in patch
    assert "generation_strategy_spec_scope_v1" in patch
    assert "exact_scope_value ->> 'recipe'" in patch
    assert "generation-strategy-spec-v1" in patch
    assert "execute patched_definition" in patch


def test_dynamic_patch_targets_exact_post_130002_compiler_shape_once() -> None:
    base = _read(SPEC_BASE)
    start = base.index(
        "create or replace function "
        "content_factory_private.create_generation_spec_version("
    )
    end = base.index(
        "revoke all on function "
        "content_factory_private.create_generation_spec_version(",
        start,
    )
    installed_shape = base[start:end].replace("\r\n", "\n")

    multimodel = _read(MULTIMODEL)
    v2_start = multimodel.index("do $patch_generation_spec_v2$")
    v2_end = multimodel.index("$patch_generation_spec_v2$;", v2_start)
    v2_pairs = re.findall(
        r"old_fragment := \$old\$(.*?)\$old\$;\s*"
        r"new_fragment := \$new\$(.*?)\$new\$;",
        multimodel[v2_start:v2_end],
        re.DOTALL,
    )
    assert len(v2_pairs) == 5
    for old, new in v2_pairs:
        assert installed_shape.count(old) == 1
        installed_shape = installed_shape.replace(old, new)

    migration = _read(MIGRATION)
    v3_start = migration.index("do $patch_generation_strategy_spec_v1$")
    v3_end = migration.index(
        "$patch_generation_strategy_spec_v1$;", v3_start
    )
    v3_pairs = re.findall(
        r"old_fragment := \$old\$(.*?)\$old\$;\s*"
        r"new_fragment := \$new\$(.*?)\$new\$;",
        migration[v3_start:v3_end],
        re.DOTALL,
    )
    assert len(v3_pairs) == 4
    for old, new in v3_pairs:
        assert installed_shape.count(old) == 1
        assert installed_shape.count(new) == 0
        installed_shape = installed_shape.replace(old, new)
        assert installed_shape.count(old) == 0
        assert installed_shape.count(new) == 1
    assert "generation_strategy_spec_scope_v1" in installed_shape
    assert "exact_scope_value ->> 'recipe'" in installed_shape
    assert "generation-strategy-spec-v1" in installed_shape


def test_table_scope_branch_and_trigger_bind_actual_recipe_identity() -> None:
    sql = _read(MIGRATION)
    trigger = _function(
        sql,
        "content_factory_private.bind_generation_strategy_spec_scope_v1",
    )

    assert "generation_spec_versions_v1_v2_or_strategy_scope_check" in sql
    assert "spec_contract_version = 'generation-strategy-scope-v1'" in sql
    assert "model = exact_scope ->> 'recipe'" in sql
    assert "exact_scope = content_factory_private" in sql
    assert ".generation_strategy_spec_scope_v1(exact_scope)" in sql
    assert "new.model := scope_value ->> 'recipe'" in trigger
    assert "new.provider := 'runway'" in trigger
    assert "b_generation_strategy_spec_scope_v1_bind" in sql


def test_creator_rpc_accepts_only_proposals_and_server_resolves_authority() -> None:
    sql = _read(MIGRATION)
    rpc = _function(sql, "public.creator_prepare_generation_strategy_spec")

    exact_request_keys = (
        "version",
        "organization_id",
        "project_id",
        "platform",
        "product_category",
        "selection",
        "editable_intent",
        "proposed_prompt",
        "mechanics_summary",
        "confirmation",
        "reason",
        "idempotency_key",
    )
    for key in exact_request_keys:
        assert f"'{key}'" in rpc
    request_allowlist = _section(
        rpc,
        "p_payload - array[",
        "]::text[] <> '{}'::jsonb",
    )
    for forbidden in (
        "model",
        "provider",
        "recipe",
        "selection_hash",
        "source_binding_id",
        "source_binding_hash",
        "source_snapshot_hash",
        "mechanics_hash",
    ):
        assert f"'{forbidden}'" not in request_allowlist
    assert "generation-strategy-spec-prepare-request-v1" in rpc
    assert "research_exact_youtube_media_attachments" in rpc
    assert "attachment.media_sha256_snapshot = source_media_row.sha256" in rpc
    assert "generation_strategy_media_durations" in rpc
    assert "content_factory_private.json_hash(selection_value)" in rpc
    assert "asset_snapshot_value := asset_snapshot_value ||" in rpc
    assert "json_hash(\n    asset_snapshot_value\n  )" in rpc
    assert "'asset_snapshot', asset_snapshot_value" in rpc
    assert "'asset_snapshot_hash', asset_snapshot_hash_value" in rpc
    assert "json_hash(\n    source_snapshot_value\n  )" in rpc
    assert "json_hash(\n      mechanics_snapshot_value\n    )" in rpc
    assert "public.creator_prepare_generation_spec(" in rpc
    delegated_payload = _section(
        rpc,
        "result_value := public.creator_prepare_generation_spec(",
        "  );\n  result_spec :=",
    )
    assert "'project_id'" not in delegated_payload
    assert "'source', 'baseline'" in rpc
    assert "'automatic_approval', false" in rpc
    assert "'provider_call_started', false" in rpc
    assert "'paid_start_integrated', false" in rpc
    assert "'browser_hashes_accepted', false" in rpc
    assert "'browser_source_binding_accepted', false" in rpc
    assert "provider_path" not in rpc
    assert "signed_url" not in rpc
    assert "fetch(" not in rpc.lower()


def test_mechanics_are_nontrivial_human_reviewed_and_source_pinned() -> None:
    sql = _read(MIGRATION)
    normalizer = _function(
        sql,
        "content_factory_private.generation_strategy_mechanics_summary_v1",
    )
    rpc = _function(sql, "public.creator_prepare_generation_strategy_spec")

    assert "jsonb_array_length(p_value -> 'beat_sequence') not between 2 and 6" in normalizer
    assert "length(hook_value) not between 20 and 160" in normalizer
    assert "length(beat_text) not between 12 and 120" in normalizer
    for field in (
        "hook",
        "beat_sequence",
        "pacing",
        "camera_language",
        "composition",
        "audio_pattern",
        "cta_pattern",
    ):
        assert f"'{field}'" in normalizer
    assert "'source_attachment_id', attachment_row.id" in rpc
    assert "'source_attachment_hash', attachment_row.attachment_hash" in rpc
    assert "'source_media_id', source_media_row.id" in rpc
    assert "'source_media_sha256', source_media_row.sha256" in rpc
    assert "'reviewed_by', actor_id_value" in rpc
    assert "'review_confirmation', true" in rpc
    assert "generation_strategy_spec_mechanics_required" in rpc


def test_swap_requires_null_mechanics_and_ugc_rebuild_fail_closed() -> None:
    sql = _read(MIGRATION)
    scope = _function(
        sql,
        "content_factory_private.generation_strategy_spec_scope_v1",
    )
    rpc = _function(sql, "public.creator_prepare_generation_strategy_spec")
    guard = _function(
        sql,
        "content_factory_private.enforce_generation_strategy_spec_authority",
    )

    assert "generation_strategy_spec_mechanics_must_be_null" in rpc
    assert "generation_strategy_spec_source_duration_required" in rpc
    assert "strategy_id_value = 'viral_product_swap'" in scope
    assert "mechanics_value <> 'null'::jsonb" in scope
    assert "'viral_avatar_ugc', 'viral_rebuild'" in guard
    assert "jsonb_typeof(scope_value -> 'mechanics') <> 'object'" in guard
    assert "new.strategy_id = 'viral_product_swap'" in guard
    assert "scope_value -> 'mechanics' <> 'null'::jsonb" in guard


def test_frozen_bind_request_is_guarded_without_dto_or_hash_changes() -> None:
    sql = _read(MIGRATION)
    guard = _function(
        sql,
        "content_factory_private.enforce_generation_strategy_spec_authority",
    )

    assert "alter table content_factory.generation_spec_strategy_bindings" not in sql
    assert "generation-strategy-binding-request-v1" in sql
    assert "scope_value ->> 'selection_hash' <> new.selection_hash" in guard
    assert "new.source_basis <> 'exact_source_video'" in guard
    assert "scope_value #>> '{source,attachment_id}'" in guard
    assert "new.source_binding_id::text" in guard
    assert "scope_value #>> '{source,attachment_hash}'" in guard
    assert "new.source_binding_hash" in guard
    assert "scope_value #> '{selection,assets}'" in guard
    assert "jsonb_array_elements(new.role_asset_snapshot)" in guard
    assert "scope_value -> 'asset_snapshot'" in guard
    assert "ledger.value ->> 'sha256'" in guard
    assert "pinned.value ->> 'sha256'" in guard
    assert "ledger.value ->> 'mime_type'" in guard
    assert "pinned.value ->> 'mime_type'" in guard
    assert "(ledger.value -> 'product_id') is not distinct from" in guard
    assert "selected.value ->> 'media_id'" in guard
    assert "scope_value ->> 'primary_media_id'" in guard
    assert "then 'product_primary'" in guard
    assert "then 'product_reference'" in guard
    assert "with ordinality selected(value, ordinality)" in guard
    assert "prior.ordinality <= selected.ordinality" in guard
    assert "(ledger.value ->> 'ordinal')::integer" in guard
    assert "head.state = 'approved'" in guard
    assert "later.event_sequence > head.event_sequence" in guard
    assert "a_generation_strategy_spec_authority_guard" in sql


def test_prompt_uses_real_mechanics_hash_and_never_forwards_mechanics_as_source_video() -> None:
    sql = _read(MIGRATION)
    prompt = _function(
        sql,
        "content_factory_private.generation_strategy_prompt_snapshot",
    )

    assert "generation_strategy_mechanics_summary_v1(" in prompt
    assert "Human-approved high-level source mechanics:" in prompt
    assert "mechanics_hash_value <>" in prompt
    assert "content_factory_private.json_hash(mechanics_value)" in prompt
    assert "'source_mechanics_snapshot_hash', to_jsonb(mechanics_hash_value)" in prompt
    assert "Never copy source footage" in prompt
    assert "when 'viral_product_swap'" not in prompt
    assert "mechanics_value <> 'null'::jsonb" in prompt
    assert "source_snapshot_hash" not in prompt


def test_ten_sources_create_independent_specs_and_cannot_cross_bind() -> None:
    sql = _read(MIGRATION)
    rpc = _function(sql, "public.creator_prepare_generation_strategy_spec")
    guard = _function(
        sql,
        "content_factory_private.enforce_generation_strategy_spec_authority",
    )

    # The wrapper never accepts/reuses a spec identity. Each distinct
    # idempotency key reaches creator_prepare_generation_spec, whose contract
    # allocates a new spec_id, while exact source and selection remain in that
    # one immutable scope.
    assert "'spec_id'" not in _section(
        rpc,
        "p_payload - array[",
        "]::text[] <> '{}'::jsonb",
    )
    assert "'strategy-spec:' || idempotency_key_value" in rpc
    assert "'selection', selection_value" in rpc
    assert "'asset_snapshot', asset_snapshot_value" in rpc
    assert "'source', source_snapshot_value" in rpc
    assert "'mechanics', to_jsonb(mechanics_snapshot_value)" in rpc
    assert "version.spec_id = new.spec_id" in guard
    assert "version.spec_version = new.spec_version" in guard
    assert "version.spec_hash = new.spec_hash" in guard
    assert "scope_value #>> '{source,media_object_id}'" in guard
    assert "new.source_snapshot ->> 'media_object_id'" in guard


def test_new_rpc_acl_is_authenticated_only_and_no_provider_spend_verb_exists() -> None:
    sql = _read(MIGRATION)

    assert (
        "revoke all on function\n"
        "  public.creator_prepare_generation_strategy_spec(jsonb)\n"
        "  from public, anon, authenticated, service_role"
    ) in sql
    assert (
        "grant execute on function\n"
        "  public.creator_prepare_generation_strategy_spec(jsonb)\n"
        "  to authenticated"
    ) in sql
    lowered = sql.lower()
    for forbidden in (
        "net.http",
        "http_post",
        "provider task",
        "allow_real_spend",
        "generation_strategy_start_claims",
        "generation_strategy_dispatch_attempts",
    ):
        assert forbidden not in lowered
