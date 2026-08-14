import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "web" / "app" / "supabase-api.js"
STRATEGY_CATALOG = (
    ROOT / "supabase" / "functions" / "_shared" / "generation-strategy-catalog.js"
)


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable for the browser API contract test")
    completed = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_strategy_catalog_client_is_exact_and_independent_from_model_catalog() -> None:
    script = f"""
      const {{ CreatorApi }} = await import({json.dumps(CLIENT.as_uri())});
      const strategyContract = await import({json.dumps(STRATEGY_CATALOG.as_uri())});

      const executionCapabilities = Object.fromEntries(
        strategyContract.GENERATION_STRATEGY_CATALOG.map((entry) => [entry.strategy_id, {{
          enabled: true,
          catalog_version: strategyContract.GENERATION_STRATEGY_CATALOG_VERSION,
          strategy_id: entry.strategy_id,
          provider: entry.provider,
          recipe: entry.recipe,
          recipe_version: entry.recipe_version,
          provider_path: entry.server.provider_path,
          pricing_version: entry.pricing_version,
        }}]),
      );
      const projected = strategyContract.publicGenerationStrategyCatalog({{ executionCapabilities }});
      const valid = {{
        ok: true,
        catalog: {{
          strategyCatalogVersion: projected.version,
          strategyRecipeVersion: projected.recipe_version,
          strategyPricingVersion: projected.pricing_version,
          strategies: projected.strategies,
        }},
      }};
      const calls = [];
      const api = Object.create(CreatorApi.prototype);
      api.organizationId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
      let response = valid;
      api.invokeRealGeneration = async (...args) => {{
        calls.push(args);
        return response;
      }};

      const accepted = await api.generationStrategyCatalog();
      const invalidResponses = [
        {{ ...valid, unexpected: true }},
        {{ ...valid, catalog: {{ ...valid.catalog, models: [] }} }},
        {{ ...valid, catalog: {{ ...valid.catalog, strategyCatalogVersion: "" }} }},
        {{ ...valid, catalog: {{ ...valid.catalog, strategies: valid.catalog.strategies.slice(0, 2) }} }},
        {{
          ...valid,
          catalog: {{
            ...valid.catalog,
            strategies: valid.catalog.strategies.map((entry, index) => (
              index === 0 ? {{ ...entry, public_label: "" }} : entry
            )),
          }},
        }},
      ];
      const rejectionCodes = [];
      for (const invalid of invalidResponses) {{
        response = invalid;
        try {{
          await api.generationStrategyCatalog();
          rejectionCodes.push("accepted_invalid_response");
        }} catch (error) {{
          rejectionCodes.push(error.code || "missing_error_code");
        }}
      }}

      process.stdout.write(JSON.stringify({{
        callActions: calls.map((args) => args[0]),
        callArgumentCounts: calls.map((args) => args.length),
        callPayloads: calls.map((args) => args[1]),
        acceptedKeys: Object.keys(accepted.catalog),
        acceptedIds: accepted.catalog.strategies.map((entry) => entry.strategy_id),
        acceptedLabels: accepted.catalog.strategies.map((entry) => entry.public_label),
        rejectionCodes,
      }}));
    """
    result = _run_node(script)

    assert result["callActions"] == ["strategy_catalog"] * 6
    assert result["callArgumentCounts"] == [2] * 6
    assert result["callPayloads"] == [
        {
            "action": "strategy_catalog",
            "organization_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        }
    ] * 6
    assert result["acceptedKeys"] == [
        "strategyCatalogVersion",
        "strategyRecipeVersion",
        "strategyPricingVersion",
        "strategies",
    ]
    assert result["acceptedIds"] == [
        "viral_avatar_ugc",
        "viral_product_swap",
        "viral_rebuild",
    ]
    assert result["acceptedLabels"] == [
        "Новый UGC с аватаром и товаром",
        "Заменить товар в исходном ролике",
        "Создать новый ролик по механике референса",
    ]
    assert result["rejectionCodes"] == [
        "generation_strategy_catalog_invalid",
    ] * 5


def test_strategy_catalog_transport_has_an_exact_read_only_contract() -> None:
    source = CLIENT.read_text(encoding="utf-8")
    request_keys = source[
        source.index("  strategy_catalog: Object.freeze([") :
        source.index("  strategy_media_probe: Object.freeze([")
    ]
    assert '"action"' in request_keys
    assert '"organization_id"' in request_keys
    assert '"confirmation"' not in request_keys
    assert '"project_id"' not in request_keys

    method = source[
        source.index("  async generationStrategyCatalog()") :
        source.index("\n  probeGenerationStrategyMedia(", source.index("  async generationStrategyCatalog()"))
    ]
    assert 'this.invokeRealGeneration("strategy_catalog", {' in method
    assert 'hasExactObjectKeys(data, ["ok", "catalog"])' in method
    for field in (
        "strategyCatalogVersion",
        "strategyRecipeVersion",
        "strategyPricingVersion",
        "strategies",
    ):
        assert field in method
    assert "models" not in method
    assert "fetch(" not in method
    assert "startGenerationStrategy" not in method
