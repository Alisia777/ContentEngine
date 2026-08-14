from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
STRATEGY_SQL_PATH = (
    ROOT
    / "supabase/migrations/202608130007_generation_strategy_execution_v1.sql"
)
MULTIMODEL_SQL_PATH = (
    ROOT
    / "supabase/migrations/202608130002_generation_multimodel_authority.sql"
)
SPEND_SQL_PATH = (
    ROOT / "supabase/migrations/202607170002_generation_spend_budgets.sql"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start + len(start_marker))
    return source[start:end]


def test_strategy_catalog_browser_payload_is_exact() -> None:
    edge = _text(EDGE_PATH)
    parser = _slice(
        edge,
        "function readStrategyCatalogPayload(",
        "\nfunction readGenerationStrategyId(",
    )

    assert 'new Set(["action", "organization_id"])' in parser
    assert 'value.action !== "strategy_catalog"' in parser
    assert "Object.keys(value).length !== keys.size" in parser
    assert "!isUuid(value.organization_id)" in parser
    for forbidden in ("feature", "provider", "model", "project", "spend"):
        assert forbidden not in parser.lower()


def test_strategy_catalog_action_is_lightweight_authenticated_and_fail_closed() -> None:
    edge = _text(EDGE_PATH)
    handler = _slice(
        edge,
        "  const strategyCatalogPayload = readStrategyCatalogPayload(body);",
        "\n  const modelCatalogPayload = readModelCatalogPayload(body);",
    )
    policy_loader = _slice(
        edge,
        "  const loadGenerationStrategyCatalogPolicy = async (",
        "\n  const strategyCatalogPayload = readStrategyCatalogPayload(body);",
    )

    # This exact authenticated RPC enforces active organization plus the
    # established generation roles. Its returned flags are intentionally never
    # read; the service-only strategy policy is the sole catalog authority.
    assert 'context.supabase.rpc(\n        "creator_generation_model_feature_flags"' in handler
    membership_proof = handler.split(
        "const strategyCatalogPolicy = await", 1
    )[0]
    assert "const { error } = await context.supabase.rpc(" in membership_proof
    assert "const { data, error }" not in membership_proof
    assert "strategyCatalogPayload.organization_id" in membership_proof

    assert 'supabaseAdmin.rpc(\n        "system_generation_strategy_catalog_policy"' in policy_loader
    assert 'version: "generation-strategy-catalog-policy-request-v1"' in policy_loader
    assert "readGenerationStrategyCatalogPolicy(data)" in policy_loader
    assert "strategyCatalogPolicy === null" in handler
    assert handler.count('code: "generation_unavailable"') == 2
    assert 'code: "generation_rejected"' in handler

    for forbidden in (
        "creator_generation_spend_overview",
        "creator_generation_provider_policy",
        "loadProviderPolicy(",
        "publicGenerationModelCatalog(",
        "spend_confirmation",
        "provider_readiness",
        "fetch(",
        "Deno.env",
    ):
        assert forbidden not in handler


def test_sql_policy_shape_matches_the_existing_strict_edge_reader() -> None:
    edge = _text(EDGE_PATH)
    sql = _text(STRATEGY_SQL_PATH)
    reader = _slice(
        edge,
        "function readGenerationStrategyCatalogPolicy(",
        "\nfunction generationStrategyBindingAssetsValid(",
    )
    sql_policy = _slice(
        sql,
        "create or replace function public.system_generation_strategy_catalog_policy(",
        "\nrevoke all on function\n  public.system_generation_strategy_catalog_policy",
    )

    top_level_fields = (
        "ok",
        "version",
        "execution_capabilities",
        "checks",
        "select_enabled",
        "preflight_enabled",
        "paid_start_authorized",
        "contract",
    )
    check_fields = (
        "organization_active",
        "sql_provider_configuration_enabled",
        "execution_chain_installed",
        "edge_secret_check_required_at_preflight",
    )
    contract_fields = (
        "read_only",
        "server_authoritative",
        "provider_call_started",
        "receipt_required_for_paid_start",
        "catalog_policy_is_not_paid_authority",
    )
    capability_fields = (
        "enabled",
        "catalog_version",
        "strategy_id",
        "provider",
        "recipe",
        "recipe_version",
        "provider_path",
        "pricing_version",
    )
    for field in (
        *top_level_fields,
        *check_fields,
        *contract_fields,
        *capability_fields,
    ):
        assert f'"{field}"' in reader
        assert f"'{field}'" in sql_policy

    expected_rows = {
        "viral_avatar_ugc": ("product_ugc", "/v1/recipes/product_ugc"),
        "viral_product_swap": ("product_swap", "/v1/recipes/product_swap"),
        "viral_rebuild": ("product_ad", "/v1/recipes/product_ad"),
    }
    assert "Object.keys(capabilities).length !== expectedIds.size" in reader
    for strategy_id, (recipe, provider_path) in expected_rows.items():
        assert sql_policy.count(f"'{strategy_id}'") == 2
        assert f"'recipe', '{recipe}'" in sql_policy
        assert f"'provider_path', '{provider_path}'" in sql_policy
    assert sql_policy.count("'catalog_version', '2026-08-14.v1'") == 3
    assert sql_policy.count("'recipe_version', '2026-06'") == 3
    assert (
        sql_policy.count(
            "'pricing_version', 'runway-recipe-credits-2026-08-14.v1'"
        )
        == 3
    )


def test_strategy_catalog_success_envelope_is_exact_and_public_only() -> None:
    edge = _text(EDGE_PATH)
    handler = _slice(
        edge,
        "  const strategyCatalogPayload = readStrategyCatalogPayload(body);",
        "\n  const modelCatalogPayload = readModelCatalogPayload(body);",
    )

    exact_envelope = """catalog: {
        strategyCatalogVersion: publicStrategyCatalog.version,
        strategyRecipeVersion: publicStrategyCatalog.recipe_version,
        strategyPricingVersion: publicStrategyCatalog.pricing_version,
        strategies: publicStrategyCatalog.strategies.map((strategy) => {"""
    assert exact_envelope in handler

    projection = handler.split(
        "strategies: publicStrategyCatalog.strategies.map((strategy) => {", 1
    )[1].split("          };", 1)[0]
    public_fields = (
        "strategy_id",
        "public_label",
        "public_summary",
        "transformation_kind",
        "source_reference_mode",
        "preservation_notice",
        "human_review_required",
        "provider",
        "recipe",
        "recipe_version",
        "asset_roles",
        "required_attestations",
        "output_rules",
        "pricing",
        "enabled",
        "disabled_reason",
    )
    for field in public_fields:
        assert projection.count(f"{field}: strategy.{field}") == 1
    for private_field in (
        "server",
        "provider_path",
        "authorization",
        "executionCapabilities",
        "selectEnabled",
        "preflightEnabled",
        "paid_start_authorized",
    ):
        assert private_field not in projection

    # The response is strategy-only: no legacy model-catalog projection leaks
    # into this independent action.
    for legacy_field in ("models:", "featureFlags:", "inputCapabilities:"):
        assert legacy_field not in handler


def test_model_catalog_membership_cleanup_is_not_authorization_equivalent() -> None:
    """Document why the existing model_catalog spend proof is retained."""
    feature_flags_sql = _text(MULTIMODEL_SQL_PATH)
    spend_sql = _text(SPEND_SQL_PATH)
    feature_roles = "array['owner','admin','producer','reviewer','operator']"
    spend_roles = "array['owner', 'admin', 'producer', 'operator']"

    assert feature_roles in feature_flags_sql
    assert spend_roles in spend_sql
    assert "reviewer" in feature_roles and "reviewer" not in spend_roles
