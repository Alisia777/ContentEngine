from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
EDGE = EDGE_PATH.read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    assert start in EDGE, f"Missing Edge boundary: {start}"
    assert end in EDGE, f"Missing Edge boundary: {end}"
    return EDGE.split(start, 1)[1].split(end, 1)[0]


def _function(name: str, next_name: str) -> str:
    return _between(f"function {name}(", f"function {next_name}(")


def test_strategy_bind_browser_envelope_is_exact_and_has_no_server_authority() -> None:
    payload_type = _between(
        "type GenerationStrategyBindPayload = {",
        "type GenerationStrategyMediaProbePayload = {",
    )
    parser = _function(
        "readGenerationStrategyBindPayload",
        "readGenerationStrategyMediaProbePayload",
    )

    assert 'action: "strategy_bind"' in payload_type
    for required in (
        "organization_id",
        "project_id",
        "spec_id",
        "spec_version",
        "spec_hash",
        "generation_strategy",
        "confirmation",
        "idempotency_key",
    ):
        assert required in payload_type
        assert f'"{required}"' in parser
    for forbidden in (
        "actor_id",
        "provider_path",
        "signed_url",
        "object_name",
        "bucket_id",
        "price_hash",
        "selection_hash",
        "binding_hash",
        "estimated_cost",
        "spend_confirmation",
    ):
        assert forbidden not in payload_type
        assert f'"{forbidden}"' not in parser

    assert "hasExactKeys(value, keys)" in parser
    assert "validateGenerationStrategySelection(" in parser
    assert "generationStrategyCatalogEntry(strategyId)" in parser
    assert 'entry.provider !== "runway"' in parser
    assert "entry.recipe !== recipe" in parser


def test_strategy_bind_injects_jwt_actor_and_calls_only_the_service_binder() -> None:
    handler = _between(
        "  const strategyBindPayload = readGenerationStrategyBindPayload(body);",
        "  const strategyMediaProbePayload = readGenerationStrategyMediaProbePayload(",
    )

    assert "if (!internalWorker && strategyBindPayload !== null)" in handler
    assert "const actorId = context.userClaims?.id;" in handler
    assert "if (!isUuid(actorId))" in handler
    assert '"system_resolve_and_bind_generation_strategy"' in handler
    assert 'version: "generation-strategy-resolve-bind-request-v1"' in handler
    assert "actor_id: actorId" in handler
    assert "selection: strategyBindPayload.generation_strategy as Json" in handler
    assert "confirmation: true" in handler
    assert "readGenerationStrategyBindResult(" in handler

    # Binding is persistence-only. It must never contact Runway, sign objects,
    # accept browser authority, or consume a paid-start claim.
    for forbidden in (
        "fetch(",
        "RUNWAY_API_ORIGIN",
        "createSignedUrl",
        "provider_path",
        "system_claim_generation_strategy_start",
        "system_mark_generation_strategy_dispatch_attempt",
        "system_record_generation_strategy_dispatch_result",
    ):
        assert forbidden not in handler


def test_strategy_bind_response_is_allowlisted_against_frozen_130006_contract() -> None:
    parser = _function(
        "readGenerationStrategyBindResult",
        "readGenerationModelFeatureFlags",
    )
    price = _function(
        "generationStrategyPriceValid",
        "readGenerationStrategyBindResult",
    )
    assets = _function(
        "generationStrategyBindingAssetsValid",
        "generationStrategyPriceValid",
    )

    for top_level_key in ("ok", "version", "binding", "selection", "price", "contract"):
        assert f'"{top_level_key}"' in parser
    assert 'value.version !== "generation-strategy-resolve-bind-response-v1"' in parser

    for immutable_key in (
        "catalog_version",
        "recipe_version",
        "pricing_version",
        "strategy_id",
        "recipe",
        "selection_hash",
        "binding_hash",
        "strategy_snapshot_hash",
        "source_binding_hash",
        "price_hash",
        "spend_confirmation",
    ):
        assert immutable_key in parser or immutable_key in price

    for exact_false in (
        "browser_hashes_accepted",
        "browser_source_binding_accepted",
        "provider_call_started",
        "paid_start_integrated",
        "launch_enabled",
    ):
        assert f"value.contract.{exact_false} !== false" in parser
    for exact_true in (
        "server_resolved_source_binding",
        "server_resolved_media_hashes",
    ):
        assert f"value.contract.{exact_true} !== true" in parser

    for role in (
        "product_primary",
        "product_reference",
        "creator_avatar",
        "original_product",
        "source_video",
        "style_reference",
    ):
        assert f'"{role}"' in assets
    assert "rights_confirmed !== true" in assets
    assert "typeof asset.likeness_consent !== \"boolean\"" in assets

    # Версия прайса — свойство маршрута, а не литерал Runway: у fal их две
    # (за ролик и за секунду). Проверяется принадлежность известному набору,
    # иначе снимок цены второго движка отвергался бы формой, а не содержанием.
    assert "isKnownStrategyPricingVersion(value.pricing_version)" in price
    assert "RUNWAY_RECIPE_PRICING_VERSION" not in price
    assert "RUNWAY_RECIPE_VERSION" in price

    # Сверка со ступенями кредитов остаётся обязательной там, где кредиты и
    # есть, — у Runway. Маршрут с ценой за ролик или за секунду сверяется на
    # внутреннюю согласованность снимка.
    assert "estimateGenerationStrategyCredits(" in price
    assert 'const runwayCredits = value.provider === "runway"' in price
    assert "value.estimated_credits === expectedPrice.estimated_credits" in price
    assert "expectedConfirmation" in price
    assert "value.spend_confirmation === expectedConfirmation" in price


def test_strategy_bind_maps_only_known_sql_errors_and_fails_closed_otherwise() -> None:
    error_reader = _function(
        "readGenerationStrategyBindRpcError",
        "readClaimErrorCode",
    )
    handler = _between(
        "  const strategyBindPayload = readGenerationStrategyBindPayload(body);",
        "  const strategyMediaProbePayload = readGenerationStrategyMediaProbePayload(",
    )

    assert "GENERATION_STRATEGY_BIND_VALIDATION_ERROR_CODES.has(code)" in error_reader
    assert "GENERATION_STRATEGY_BIND_ACCESS_ERROR_CODES.has(code)" in error_reader
    assert "GENERATION_STRATEGY_BIND_CONFLICT_ERROR_CODES.has(code)" in error_reader
    assert "return { code, status: 422 }" in error_reader
    assert "return { code, status: 403 }" in error_reader
    assert "return { code, status: 409 }" in error_reader
    assert "return null" in error_reader

    assert "const mapped = readGenerationStrategyBindRpcError(error);" in handler
    assert handler.count('code: "generation_unavailable"') >= 3
    assert "json(request, result)" in handler


def test_paid_strategy_start_uses_frozen_130007_claim_and_one_post_owner() -> None:
    start = _between(
        "  const handleGenerationStrategyStart = async (",
        "  const handleGenerationStrategyReconciliation = async (",
    )
    continuation = _between(
        "  const continueGenerationStrategyClaim = async (",
        "  const generationStrategyOutputObjectName = async (",
    )

    assert '"system_claim_generation_strategy_start"' in start
    assert 'version: "generation-strategy-start-claim-request-v1"' in start
    assert "await readGenerationStrategyStartClaim(data" in start
    assert "continueGenerationStrategyClaim({" in start

    assert '"system_mark_generation_strategy_dispatch_attempt"' in continuation
    assert 'version: "generation-strategy-dispatch-attempt-request-v1"' in continuation
    assert "attempt.dispatch_allowed !== true" in continuation
    assert "attempt.replay !== false" in continuation
    assert "attempt.terminal_result !== null" in continuation
    assert "signAndValidateGenerationStrategyAssets(" in continuation
    assert "await readGenerationStrategyDispatchAttempt(data" in continuation
    assert "buildGenerationStrategyProviderRequest(" in continuation
    assert continuation.count("fetchProviderJsonWithDeadline(") == 1
    assert '"system_record_generation_strategy_dispatch_result"' not in continuation
    assert "recordGenerationStrategyDispatchResult(" in continuation
