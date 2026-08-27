from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608210001_generation_strategy_spec_provider_neutral_v2.sql"
)
CLIENT = ROOT / "web/app/generation-strategy-spec.js"
APP = ROOT / "web/app/app.js"


def _migration() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_v2_scope_is_provider_neutral_and_names_the_real_route_authority() -> None:
    sql = _migration()
    v2 = sql[
        sql.index("generation_strategy_spec_scope_v2(p_scope jsonb)") :
        sql.index("revoke all on function\n  content_factory_private.generation_strategy_spec_scope_v2")
    ]
    assert "generation-strategy-spec-scope-v2" in v2
    assert "generation-strategy-route-policy-v1" in v2
    assert "generation_strategy_provider_routes" in v2
    assert "deferred_until_preflight" in v2
    assert "'route_policy'" in v2
    # The only Runway value in the validator is inside the explicit conversion
    # passed to the immutable legacy-v1 validator; it is never returned as v2.
    assert "legacy_scope := (p_scope - 'route_policy')" in v2
    assert v2.count("'provider', 'runway'") == 1
    assert "'provider', 'runway'" not in v2.split("legacy_scope :=", 1)[0]
    assert "return p_scope;" in v2


def test_migration_dual_reads_v1_without_rewriting_approved_history() -> None:
    sql = _migration()
    assert "generation_strategy_spec_scope_legacy_v1" in sql
    assert "select coalesce(" in sql
    assert "generation-strategy-scope-v1" in sql
    assert "generation-strategy-scope-v2" in sql
    assert "provider is null" in sql
    assert "generation-strategy-spec-v2" in sql
    assert "update content_factory.generation_spec_versions" not in sql.casefold()
    assert "delete from content_factory.generation_spec_versions" not in sql.casefold()


def test_prepare_cannot_accept_a_browser_provider_and_paid_route_stays_deferred() -> None:
    sql = _migration()
    prepare_patch = sql[
        sql.index("$patch_generation_strategy_prepare_scope_v2$") :
        sql.index("$patch_generation_strategy_prepare_scope_v2$;", sql.index(
            "$patch_generation_strategy_prepare_scope_v2$"
        ))
    ]
    assert "creator_prepare_generation_strategy_spec(jsonb)" in prepare_patch
    assert "generation_strategy_provider_routes" in prepare_patch
    assert "deferred_until_preflight" in prepare_patch
    assert "provider_pattern" in prepare_patch
    assert "route_fragment" in prepare_patch
    assert "provider" not in CLIENT.read_text(encoding="utf-8").split(
        "const PREPARE_INPUT_KEYS", 1
    )[1].split("]);", 1)[0]


def test_prepare_replays_legacy_idempotency_receipt_before_using_v2_key() -> None:
    sql = _migration()
    prepare_patch = sql[
        sql.index("$patch_generation_strategy_prepare_scope_v2$") :
        sql.index("$patch_generation_strategy_prepare_scope_v2$;", sql.index(
            "$patch_generation_strategy_prepare_scope_v2$"
        ))
    ]
    # The project boundary has always removed project_id before delegating to
    # the receipt-owning generic RPC, so there is exactly one historical hash
    # shape to reconstruct.
    assert "legacy_request_payload_pre_project" not in prepare_patch
    legacy_payload = prepare_patch[
        prepare_patch.index("legacy_request_payload := jsonb_build_object(") :
        prepare_patch.index("perform pg_catalog.pg_advisory_xact_lock", prepare_patch.index(
            "legacy_request_payload := jsonb_build_object("
        ))
    ]
    assert "'project_id'" not in legacy_payload
    assert "'exact_scope', legacy_scope_value" in legacy_payload
    assert "content_factory.command_receipts" in prepare_patch
    assert "'strategy-spec:' || idempotency_key_value" in prepare_patch
    assert "'strategy-spec-v2:' || idempotency_key_value" in prepare_patch
    assert "content_factory_private.json_hash(legacy_request_payload)" in prepare_patch
    assert "message = 'idempotency_key_conflict'" in prepare_patch
    assert "result_value := legacy_result_value" in prepare_patch
    assert "exact_scope_value := legacy_scope_value" in prepare_patch
    # The sole provider-bearing fragment is explicitly the v1 receipt
    # reconstruction. The emitted scope has already replaced its provider pair
    # with route_policy before this fragment is injected.
    assert "legacy_scope_marker" in prepare_patch
    assert "regexp_count(patched_value, version_pattern) <> 1" in prepare_patch
    assert "regexp_count(patched_value, provider_pattern) <> 0" in prepare_patch
    assert "regexp_count(patched_value, provider_literal_pattern) <> 1" in prepare_patch
    assert "'-- Cross-version idempotency:', 1" in prepare_patch

    final_verify = sql[
        sql.index("$generation_strategy_spec_provider_neutral_v2_verify$") :
        sql.index("$generation_strategy_spec_provider_neutral_v2_verify$;", sql.index(
            "$generation_strategy_spec_provider_neutral_v2_verify$"
        ))
    ]
    assert "emitted_scope_prefix" in final_verify
    assert "regexp_count(\n          emitted_scope_prefix, provider_literal_pattern" in final_verify
    assert "regexp_count(\n          definition_value, provider_literal_pattern" in final_verify


def test_review_card_does_not_present_legacy_runway_hint_as_execution_truth() -> None:
    app = APP.read_text(encoding="utf-8")
    assert (
        'from "./generation-strategy-spec.js?v=20260826.rebuild-clean.28";'
        in app
    )
    start = app.index("function generationStrategySpecMechanicsMarkup")
    end = app.index("function generationStrategySingleSpecReviewMarkup", start)
    review = app[start:end]
    assert "scope.provider" not in review
    assert "generation_strategy_provider_routes" not in review
    assert "Маршрут" in review
    assert "подписанной квитанцией" in review
    assert "scope.recipe" in review
