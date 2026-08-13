from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608120008_operator_project_research_ai.sql"
)
PGTAP_PATH = ROOT / "supabase/tests/operator_project_research_ai_test.sql"
QUEUE_SOURCE_PATH = (
    ROOT
    / "supabase/migrations/202608100001_research_ai_center_generation_presets.sql"
)
EXACT_QUEUE_SOURCE_PATH = (
    ROOT
    / "supabase/migrations/202608110004_exact_youtube_source_research_lifecycle.sql"
)
EDGE_PATH = ROOT / "supabase/functions/creator-product-research/index.ts"
APP_PATH = ROOT / "web/app/app.js"
VIEW_PATH = ROOT / "web/app/product-research-view.js"
SHARED_PGTAP_PATH = (
    ROOT / "supabase/tests/research_ai_generation_shared_project_path_test.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _dollar_body(source: str, tag: str) -> str:
    delimiter = f"${tag}$"
    start = source.index(delimiter) + len(delimiter)
    end = source.index(delimiter, start)
    return source[start:end]


def _replace_anchor(definition: str, migration: str, old_tag: str, new_tag: str) -> str:
    old = _dollar_body(migration, old_tag)
    new = _dollar_body(migration, new_tag)
    assert definition.count(old) == 1
    return definition.replace(old, new)


def test_migration_and_behavioral_pgtap_parse_transactionally() -> None:
    migration = _read(MIGRATION_PATH)
    pgtap = _read(PGTAP_PATH)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert migration.lstrip().casefold().startswith("begin;")
    assert migration.rstrip().casefold().endswith("commit;")
    assert pgtap.lstrip().casefold().startswith("begin;")
    assert pgtap.rstrip().casefold().endswith("rollback;")


def test_operator_qualification_is_role_project_acl_and_training_bound() -> None:
    migration = _read(MIGRATION_PATH)
    helper = migration[
        migration.index("qualified_operator_project_research_allowed(") :
        migration.index("qualified_operator_project_research_context_allowed(")
    ]

    for token in (
        "membership.role = 'operator'",
        "membership.status = 'active'",
        "organization.status = 'active'",
        "profile.status = 'active'",
        "generated_media_reviewer_access_allowed(",
        "workspace_project_access_allowed(",
    ):
        assert token in helper

    context_helper = migration[
        migration.index("qualified_operator_project_research_context_allowed(") :
        migration.index("qualified_operator_own_ai_research_receipt_allowed(")
    ]
    assert "current_setting('contentengine.project_id', true)" in context_helper
    assert "project_setting::uuid" in context_helper
    assert "exception when invalid_text_representation" in context_helper
    assert re.search(
        r"project_setting\s+!~\*\s+'\^\[0-9a-f\]\{8\}-.+\$'",
        context_helper,
        re.DOTALL,
    )


def test_all_four_mature_start_gates_are_fail_closed_patches() -> None:
    migration = _read(MIGRATION_PATH)
    patch = migration[
        migration.index("$patch_project_research_start_layers$") :
        migration.index("$preserve_project_research_before_operator_price$")
    ]

    for signature in (
        "creator_start_project_research_pre_ai_handoff_v1(jsonb)",
        "public.creator_start_product_research(jsonb)",
        "creator_start_product_research_pre_provider_control(jsonb)",
        "public.creator_start_project_research(jsonb)",
    ):
        assert signature in patch
    for topology_error in (
        "project_research_start_base_topology_changed",
        "product_research_provider_outer_topology_changed",
        "product_research_provider_inner_topology_changed",
        "exact_project_research_outer_topology_changed",
    ):
        assert topology_error in patch
    assert patch.count("qualified_operator_project_research_allowed(") >= 2
    assert patch.count("qualified_operator_project_research_context_allowed(") >= 2
    assert patch.count("patched_value := replace(") == 4


def test_operator_idempotency_and_full_metered_authorization_are_actor_scoped() -> None:
    migration = _read(MIGRATION_PATH)
    wrapper = migration[
        migration.index("create or replace function public.creator_start_project_research(") :
        migration.index("$preserve_project_research_status_before_operator_own_v1$")
    ]

    actor_key = wrapper.index("operator_idempotency_key_value :=")
    delegate = wrapper.index("creator_start_project_research_pre_operator_price_v1")
    assert actor_key < delegate
    for token in (
        "'organization_id', organization_id_value",
        "'project_id', project_id_value",
        "'actor_id', actor_id_value",
        "'raw_idempotency_key', raw_idempotency_key_value",
        "paid_authorization_value is distinct from price_contract_value",
        "p_payload - 'paid_analysis_authorization'",
        "run.created_by = actor_id_value",
        "authorization_entry.authorized_by = actor_id_value",
        "authorization_entry.authorization_kind =",
        "'explicit_paid_analysis'",
        "authorization_entry.paid_analysis_ack",
        "authorization_entry.max_provider_attempts = 1",
        "not authorization_entry.automatic_fallback_allowed",
        "binding.bound_by = actor_id_value",
        "source.requested_by = actor_id_value",
        "attachment.attached_by = actor_id_value",
        "media.owner_id = actor_id_value",
    ):
        assert token in wrapper


def test_price_snapshot_is_metered_exact_and_runtime_model_is_pinned() -> None:
    migration = _read(MIGRATION_PATH)
    edge = _read(EDGE_PATH)
    price = migration[
        migration.index("research_price_contract()") :
        migration.index("create table if not exists\n  content_factory.research_operator_price_confirmations")
    ]

    canonical = {
        "'model', 'gpt-5.5'",
        "'billing_mode', 'metered_actual_usage'",
        "'service_tier', 'default'",
        "'input_usd_per_million_tokens', '5.00'",
        "'output_usd_per_million_tokens', '30.00'",
        "'long_context_threshold_input_tokens', 272000",
        "'long_context_input_usd_per_million_tokens', '10.00'",
        "'long_context_output_usd_per_million_tokens', '45.00'",
        "'web_search_usd_per_call', '0.01'",
        "'max_output_tokens', 18000",
        "'max_provider_attempts', 1",
        "'fixed_total', false",
    }
    for token in canonical:
        assert token in price
    assert 'const RESEARCH_BILLING_MODEL = "gpt-5.5";' in edge
    open_ai_model = edge[edge.index("function openAiModel()") : edge.index(
        "function validateSignedStorageUrl"
    )]
    assert "return RESEARCH_BILLING_MODEL;" in open_ai_model
    assert "Deno.env.get" not in open_ai_model
    assert "max_output_tokens: MAX_OUTPUT_TOKENS" in edge
    assert 'const RESEARCH_SERVICE_TIER = "default";' in edge
    assert "service_tier: RESEARCH_SERVICE_TIER" in edge
    assert "const MAX_OUTPUT_TOKENS = 18_000" in edge


def test_price_confirmation_is_append_only_and_required_before_commit() -> None:
    migration = _read(MIGRATION_PATH)
    for token in (
        "research_operator_price_confirmation_immutable",
        "before update or delete on",
        "after insert on content_factory.product_research_runs",
        "deferrable initially deferred",
        "operator_research_price_confirmation_required",
        "unique (organization_id, run_id)",
        "price_snapshot_hash ~ '^[0-9a-f]{64}$'",
    ):
        assert token in migration
    assert migration.index("create constraint trigger enforce_operator_research_price_confirmation") < migration.index(
        "$patch_project_research_start_layers$"
    )
    trigger = migration[
        migration.index("create constraint trigger enforce_operator_research_price_confirmation") :
        migration.index("$patch_project_research_start_layers$")
    ]
    assert "after insert on content_factory.product_research_runs" in trigger
    assert "after insert or update" not in trigger


def test_start_return_is_provider_free_and_committed_replay_is_exactly_pinned() -> None:
    migration = _read(MIGRATION_PATH)
    wrapper = migration[
        migration.index("create or replace function public.creator_start_project_research(") :
        migration.index("$preserve_project_research_status_before_operator_own_v1$")
    ]

    fresh_or_replay_guard = wrapper[
        wrapper.index("from content_factory.research_execution_authorizations") :
        wrapper.index("from content_factory.research_ai_category_bindings")
    ]
    assert "exists (" in fresh_or_replay_guard
    assert "research_run_provider_bindings provider_binding" in fresh_or_replay_guard
    assert "join content_factory.research_operator_price_confirmations confirmation" in fresh_or_replay_guard
    for token in (
        "confirmation.project_id = project_id_value",
        "confirmation.confirmed_by = actor_id_value",
        "provider_binding.provider_key = 'openai_web_search'",
        "'openai-responses-web-search-v1'",
        "provider_binding.model = 'gpt-5.5'",
        "provider_binding.attempt_number = 1",
        "confirmation.pricing_version =",
        "confirmation.confirmation_value =",
    ):
        assert token in fresh_or_replay_guard
    assert wrapper.index("research_run_provider_bindings provider_binding") < wrapper.index(
        "insert into content_factory.research_operator_price_confirmations"
    )


def test_pending_and_learned_operator_filters_execute_before_limit() -> None:
    migration = _read(MIGRATION_PATH)
    source = _read(QUEUE_SOURCE_PATH)
    function_start = source.index(
        "create or replace function public.creator_ai_research_training_queue("
    )
    definition = source[
        function_start : source.index("\ncreate or replace function", function_start + 1)
    ]
    definition = _replace_anchor(
        definition, migration, "old_queue_payload_allowlist", "new_queue_payload_allowlist"
    )
    definition = _replace_anchor(
        definition, migration, "old_queue_receipt_declare", "new_queue_receipt_declare"
    )
    definition = _replace_anchor(
        definition, migration, "old_queue_project_gate", "new_queue_project_gate"
    )
    definition = _replace_anchor(
        definition, migration, "old_queue_receipt_parse", "new_queue_receipt_parse"
    )
    definition = _replace_anchor(
        definition, migration, "old_queue_ownership", "new_queue_ownership"
    )
    definition = _replace_anchor(
        definition, migration, "old_learned_ownership", "new_learned_ownership"
    )
    definition = _replace_anchor(
        definition, migration, "old_queue_filter", "new_queue_filter"
    )
    definition = _replace_anchor(
        definition, migration, "old_learned_filter", "new_learned_filter"
    )
    definition = _replace_anchor(
        definition, migration, "old_queue_caps", "new_queue_caps"
    )

    first_filter = definition.index(
        "qualified_operator_own_ai_research_receipt_allowed("
    )
    first_limit = definition.index("limit limit_value", first_filter)
    learned_start = definition.index("from content_factory.ai_research_learning_selections")
    learned_filter = definition.index(
        "qualified_operator_own_ai_research_receipt_allowed(", learned_start
    )
    learned_limit = definition.index("limit limit_value", learned_filter)
    assert first_filter < first_limit
    assert learned_filter < learned_limit
    assert "selection.selected_by = user_id" in definition[learned_start:learned_limit]
    assert "'operator_own_receipts_only', actor_role_value = 'operator'" in definition
    project_gate = definition.index("if p_payload ? 'project_id' then")
    first_query = definition.index("select coalesce(jsonb_agg", project_gate)
    assert "message = 'project_id_required'" in definition[project_gate:first_query]
    assert "require_workspace_project_access(" in definition[project_gate:first_query]
    assert "qualified_operator_project_research_allowed(" in definition[
        project_gate:first_query
    ]
    assert definition.count("when actor_role_value = 'operator' then 'own'") == 2
    assert "'receipt_id'" in definition.split("]::text[]", 1)[0]
    assert "receipt_id_value := content_factory_private.require_uuid(" in definition
    assert definition.count("receipt_id_value is null") == 2
    assert definition.index("receipt.id = receipt_id_value") < first_limit
    assert definition.index("selection.receipt_id = receipt_id_value") < learned_limit


def test_exact_youtube_operator_source_and_lifecycle_filters_precede_limit() -> None:
    migration = _read(MIGRATION_PATH)
    definition = _read(EXACT_QUEUE_SOURCE_PATH)
    for old_tag, new_tag in (
        ("old_exact_declare", "new_exact_declare"),
        ("old_exact_role", "new_exact_role"),
        ("old_exact_latest", "new_exact_latest"),
        ("old_exact_effective", "new_exact_effective"),
        ("old_exact_source_filter", "new_exact_source_filter"),
    ):
        definition = _replace_anchor(definition, migration, old_tag, new_tag)

    source_filter = definition.index("source.requested_by = actor_id_value")
    outer_limit = definition.index("limit limit_value", source_filter)
    assert source_filter < outer_limit
    latest = definition.index("run.created_by = actor_id_value")
    effective = definition.index("selection.selected_by = actor_id_value", latest)
    assert latest < effective < outer_limit
    assert definition.count(
        "qualified_operator_own_ai_research_receipt_allowed("
    ) >= 2


def test_status_ownership_and_qualification_run_before_mature_delegate() -> None:
    migration = _read(MIGRATION_PATH)
    wrapper = migration[
        migration.index("create or replace function public.creator_project_research_status(") :
        migration.index("$patch_ai_research_queue_for_operator$")
    ]
    delegate = wrapper.index("creator_project_research_status_pre_operator_own_v1")
    for token in (
        "actor_role_value = 'operator'",
        "require_workspace_project_access(",
        "qualified_operator_project_research_allowed(",
        "run.project_id = project_id_value",
        "run.id = run_id_value",
        "run.created_by = actor_id_value",
        "message = 'research_run_not_allowed'",
    ):
        assert token in wrapper[:delegate]
    assert "grant execute on function public.creator_project_research_status(jsonb)\n  to authenticated" in wrapper


def test_both_decision_ownership_gates_precede_begin_and_delegate() -> None:
    migration = _read(MIGRATION_PATH)
    private_patch = migration[
        migration.index("$patch_ai_research_decision_for_operator$") :
        migration.index("$preserve_ai_research_decision_before_operator_own_v1$")
    ]
    assert private_patch.index(
        "qualified_operator_own_ai_research_receipt_allowed("
    ) < private_patch.index("begin_command(")

    outer = migration[
        migration.index(
            "create or replace function public.contentengine_decide_ai_research_training("
        ) :
        migration.index("$preserve_project_flow_before_operator_research$")
    ]
    delegate = outer.index(
        "contentengine_decide_ai_research_training_pre_operator_own_v1"
    )
    helper = outer.index("qualified_operator_own_ai_research_receipt_allowed(")
    exact_receipt = outer.index("receipt.project_id = project_id_value")
    assert helper < exact_receipt < delegate
    assert "receipt.created_by = actor_id_value" in outer[:delegate]


def test_public_and_private_grants_preserve_browser_and_service_boundaries() -> None:
    migration = _read(MIGRATION_PATH)
    for public_grant in (
        "grant execute on function public.creator_start_project_research(jsonb)\n  to authenticated",
        "grant execute on function public.creator_project_research_status(jsonb)\n  to authenticated",
        "grant execute on function\n  public.contentengine_decide_ai_research_training(jsonb)\n  to authenticated, service_role",
    ):
        assert public_grant in migration
    for private_name in (
        "creator_start_project_research_pre_operator_price_v1",
        "creator_project_research_status_pre_operator_own_v1",
        "contentengine_decide_ai_research_training_pre_operator_own_v1",
    ):
        revoke_marker = "revoke all on function content_factory_private"
        revoke_at = migration.index(
            revoke_marker,
            migration.index(f".{private_name}(jsonb)"),
        )
        revoke_block = migration[revoke_at : revoke_at + 320]
        assert f".{private_name}(jsonb)" in revoke_block
        assert "from public, anon, authenticated, service_role" in revoke_block
    assert "system_begin_research_provider_attempt" not in migration
    assert "fetch(" not in migration.casefold()
    assert "http_post" not in migration.casefold()


def test_browser_submits_only_current_whole_tariff_after_manual_checkbox() -> None:
    app = _read(APP_PATH)
    view = _read(VIEW_PATH)
    normalize = app[
        app.index("function normalizeResearchPaidTariff") :
        app.index("function normalizeLatestOwnResearchRun")
    ]
    for field in (
        "version",
        "provider",
        "provider_key",
        "adapter_version",
        "model",
        "currency",
        "billing_mode",
        "service_tier",
        "input_usd_per_million_tokens",
        "output_usd_per_million_tokens",
        "long_context_threshold_input_tokens",
        "long_context_input_usd_per_million_tokens",
        "long_context_output_usd_per_million_tokens",
        "web_search_usd_per_call",
        "max_output_tokens",
        "max_provider_attempts",
        "fixed_total",
        "confirmation_value",
    ):
        assert field in normalize

    # The page may centralize this one canonical property in its API wrapper;
    # exact-video and generic starts must both reach that same clone/validator.
    assert "paid_analysis_authorization: paidTariff" in app
    assert "paidAnalysisConfirmation === paidTariff.confirmation_value" in app
    checkbox_lines = [
        line for line in view.splitlines() if 'name="paid_analysis_confirmation"' in line
    ]
    assert checkbox_lines
    assert all("checked" not in line for line in checkbox_lines)
    persistence_window = re.compile(
        r"(?:localStorage|sessionStorage|persist[A-Za-z0-9_]*)"
        r"[^\n]{0,200}paid_analysis_(?:confirmation|authorization)",
        re.IGNORECASE,
    )
    assert persistence_window.search(app) is None


def test_behavioral_fixture_covers_auth_lineage_replay_and_zero_provider_auto() -> None:
    pgtap = _read(PGTAP_PATH).casefold()
    for marker in (
        "same operator and raw key replay the exact same run",
        "same raw key is actor-scoped and cannot replay the sibling run",
        "operator run carries the exact full metered authorization",
        "future direct operator run insert without exact snapshot is rejected",
        "committed replay after exact claimed binding remains idempotent",
        "forged provider binding without immutable confirmation cannot replay",
        "legacy existing operator run update remains valid without backfilled price",
        "operator own exact run passes the public status boundary",
        "older own run status returns exact project ownership category and receipt",
        "sibling operator is rejected before the mature status delegate",
        "foreign project cannot be substituted at the status boundary",
        "operator without explicit project acl is rejected before status delegation",
        "revoked qualification is rejected before status delegation",
        "operator exact-youtube queue contains only their own registered source",
        "manager exact-youtube queue retains the project-wide view",
        "exact own receipt selector bypasses category queue pagination",
        "operator ai queue requires one explicit project id",
        "operator without project acl is rejected before queue queries",
        "revoked operator qualification is rejected before queue queries",
        "sibling receipt is rejected before decision command replay",
        "own receipt decision creates one actor-owned append-only selection",
        "operator learned queue contains only their own selection",
        "manager ai queue behavior remains project-wide without own markers",
        "research start, queues and decisions create no provider attempt",
        "private mature delegates remain unavailable to authenticated",
    ):
        assert marker in pgtap
    for forbidden in (
        "net.http_",
        "http_post(",
        "creator-product-research",
    ):
        assert forbidden not in pgtap
    assert pgtap.count("system_begin_research_provider_attempt(") == 1
    assert "this is a direct test call, never a side effect" in pgtap


def test_shared_project_second_operator_no_longer_inherits_learned_queue() -> None:
    shared = _read(SHARED_PGTAP_PATH).casefold()
    assert "jsonb_array_length(queue_value -> 'learned') = 0" in shared
    assert (
        "the second operator does not inherit teammate learned queue but retains "
        "project-shared approved advice and binding"
    ) in shared
    assert "the second member sees learned conclusions" not in shared
