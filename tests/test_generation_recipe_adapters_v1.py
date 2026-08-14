from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_MODULE = (
    ROOT / "supabase/functions/_shared/generation-recipe-adapters.js"
)
ADAPTER_SOURCE = ADAPTER_MODULE.read_text(encoding="utf-8")
STRATEGY_CATALOG_MODULE = (
    ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
)
STRATEGY_CATALOG_SOURCE = STRATEGY_CATALOG_MODULE.read_text(encoding="utf-8")
EDGE_MODULE = ROOT / "supabase/functions/creator-generate/index.ts"
EDGE_CONTRACT_MODULE = (
    ROOT / "supabase/functions/_shared/generation-strategy-edge-contract.js"
)


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for Runway recipe adapter contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        (directory / "generation-recipe-adapters.js").write_text(
            ADAPTER_SOURCE, encoding="utf-8"
        )
        (directory / "generation-strategy-catalog.js").write_text(
            STRATEGY_CATALOG_SOURCE, encoding="utf-8"
        )
        (directory / "contract.js").write_text(
            "import * as subject from './generation-recipe-adapters.js';\n"
            "const attempt = (callback) => {\n"
            "  try { return {ok:true,value:callback()}; }\n"
            "  catch (error) { return {ok:false,code:error?.code || '',message:error?.message || ''}; }\n"
            "};\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_recipe_adapter_is_pure_inert_and_exports_no_dispatch_capability() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "document.",
        "window.",
        "WebSocket",
        "setTimeout(",
        "Authorization",
        "Bearer ",
    ):
        assert forbidden not in ADAPTER_SOURCE

    result = _evaluate(
        """
        (() => ({
          exports: Object.keys(subject).sort(),
          strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
          recipeVersion: subject.RUNWAY_RECIPE_VERSION,
          mapping: subject.RUNWAY_RECIPE_BY_STRATEGY,
          endpoints: subject.RUNWAY_RECIPE_ENDPOINTS,
        }))()
        """
    )
    assert result == {
        "exports": [
            "GENERATION_STRATEGY_CONTRACT_VERSION",
            "GenerationRecipeAdapterError",
            "RUNWAY_RECIPE_BY_STRATEGY",
            "RUNWAY_RECIPE_ENDPOINTS",
            "RUNWAY_RECIPE_VERSION",
            "buildRunwayRecipeRequest",
        ],
        "strategyVersion": "2026-08-14.v1",
        "recipeVersion": "2026-06",
        "mapping": {
            "viral_avatar_ugc": "product_ugc",
            "viral_product_swap": "product_swap",
            "viral_rebuild": "product_ad",
        },
        "endpoints": {
            "product_ugc": "/v1/recipes/product_ugc",
            "product_swap": "/v1/recipes/product_swap",
            "product_ad": "/v1/recipes/product_ad",
        },
    }


def test_three_official_recipe_payloads_have_exact_body_parity() -> None:
    result = _evaluate(
        r"""
        (() => {
          const signed = (role, name, view) => ({
            role,
            uri: `https://project.supabase.co/storage/v1/object/sign/private/${name}?token=opaque`,
            ...(view ? {view} : {}),
          });
          const common = {
            strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
            recipeVersion: subject.RUNWAY_RECIPE_VERSION,
          };
          const ugc = subject.buildRunwayRecipeRequest({
            ...common,
            strategyId: "viral_avatar_ugc",
            recipe: "product_ugc",
            durationSeconds: 15,
            ratio: "720:1280",
            audio: true,
            productInfo: "Exact product facts",
            userConcept: "Recreate only the approved mechanics with our consenting avatar.",
          }, [signed("avatar", "avatar.jpg"), signed("product_primary", "product.png")]);
          const swap = subject.buildRunwayRecipeRequest({
            ...common,
            strategyId: "viral_product_swap",
            recipe: "product_swap",
            durationSeconds: 10,
            resolution: "1080p",
            audio: true,
          }, [
            signed("source_video", "source.mp4"),
            signed("original_product", "original.png"),
            signed("product_primary", "front.png", "front"),
            signed("product_reference", "side.png", "side"),
          ]);
          const ad = subject.buildRunwayRecipeRequest({
            ...common,
            strategyId: "viral_rebuild",
            recipe: "product_ad",
            durationSeconds: 8,
            ratio: "1080:1920",
            audio: false,
            productInfo: "Exact product facts",
            userConcept: "Build a new ad from the approved mechanics; do not copy source footage.",
          }, [
            signed("product_primary", "front.png"),
            signed("product_reference", "back.png"),
            signed("style_reference", "mood.png"),
          ]);
          return {
            ugc,
            swap,
            ad,
            frozen: [ugc, swap, ad].every((item) =>
              Object.isFrozen(item) && Object.isFrozen(item.body) &&
              Object.values(item.body).filter((value) => value && typeof value === "object")
                .every((value) => Object.isFrozen(value))
            ),
          };
        })()
        """
    )
    common_envelope = {
        "provider": "runway",
        "method": "POST",
        "pollKind": "runway_task",
    }
    assert result["ugc"] == {
        **common_envelope,
        "endpointPath": "/v1/recipes/product_ugc",
        "body": {
            "version": "2026-06",
            "characterImage": {
                "uri": "https://project.supabase.co/storage/v1/object/sign/private/avatar.jpg?token=opaque"
            },
            "productImage": {
                "uri": "https://project.supabase.co/storage/v1/object/sign/private/product.png?token=opaque"
            },
            "productInfo": "Exact product facts",
            "userConcept": (
                "Recreate only the approved mechanics with our consenting avatar."
            ),
            "duration": 15,
            "ratio": "720:1280",
            "audio": True,
        },
    }
    assert result["swap"] == {
        **common_envelope,
        "endpointPath": "/v1/recipes/product_swap",
        "body": {
            "version": "2026-06",
            "referenceVideo": {
                "uri": "https://project.supabase.co/storage/v1/object/sign/private/source.mp4?token=opaque"
            },
            "originalProductImage": {
                "uri": "https://project.supabase.co/storage/v1/object/sign/private/original.png?token=opaque"
            },
            "newProductImages": [
                {
                    "uri": "https://project.supabase.co/storage/v1/object/sign/private/front.png?token=opaque",
                    "view": "front",
                },
                {
                    "uri": "https://project.supabase.co/storage/v1/object/sign/private/side.png?token=opaque",
                    "view": "side",
                },
            ],
            "duration": 10,
            "resolution": "1080p",
            "audio": True,
        },
    }
    assert result["ad"] == {
        **common_envelope,
        "endpointPath": "/v1/recipes/product_ad",
        "body": {
            "version": "2026-06",
            "productImages": [
                {
                    "uri": "https://project.supabase.co/storage/v1/object/sign/private/front.png?token=opaque"
                },
                {
                    "uri": "https://project.supabase.co/storage/v1/object/sign/private/back.png?token=opaque"
                },
            ],
            "styleImages": [
                {
                    "uri": "https://project.supabase.co/storage/v1/object/sign/private/mood.png?token=opaque"
                }
            ],
            "productInfo": "Exact product facts",
            "userConcept": (
                "Build a new ad from the approved mechanics; do not copy source footage."
            ),
            "ratio": "1080:1920",
            "duration": 8,
            "audio": False,
        },
    }
    assert result["frozen"] is True


def test_adapter_rejects_cross_recipe_fields_roles_and_untrusted_shapes() -> None:
    result = _evaluate(
        r"""
        (() => {
          const base = {
            strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
            strategyId: "viral_avatar_ugc",
            recipe: "product_ugc",
            recipeVersion: subject.RUNWAY_RECIPE_VERSION,
            durationSeconds: 8,
            ratio: "720:1280",
            audio: true,
            productInfo: "Product",
            userConcept: "Approved mechanics with a consenting avatar.",
          };
          const avatar = {role:"avatar",uri:"https://media.example/avatar.png?sig=a"};
          const product = {role:"product_primary",uri:"https://media.example/product.png?sig=b"};
          const source = {role:"source_video",uri:"https://media.example/source.mp4?sig=c"};
          return {
            recipeMismatch: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, recipe:"product_ad"}, [avatar, product]
            )),
            strategyVersion: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, strategyVersion:"unsafe-latest"}, [avatar, product]
            )),
            recipeVersion: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, recipeVersion:"unsafe-latest"}, [avatar, product]
            )),
            clientCost: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, estimatedCostMinor:1}, [avatar, product]
            )),
            clientUrl: attempt(() => subject.buildRunwayRecipeRequest(
              base, [avatar, {...product,url:"https://evil.example/product.png"}]
            )),
            ugcSourceVideo: attempt(() => subject.buildRunwayRecipeRequest(
              base, [avatar, product, source]
            )),
            ugcProductReference: attempt(() => subject.buildRunwayRecipeRequest(
              base, [avatar, product, {role:"product_reference",uri:"https://media.example/p2.png"}]
            )),
            duplicateUri: attempt(() => subject.buildRunwayRecipeRequest(
              base, [avatar, {...product,uri:avatar.uri}]
            )),
            ipUrl: attempt(() => subject.buildRunwayRecipeRequest(
              base, [{...avatar,uri:"https://127.0.0.1/a.png"}, product]
            )),
            viewOnUgc: attempt(() => subject.buildRunwayRecipeRequest(
              base, [avatar, {...product,view:"front"}]
            )),
          };
        })()
        """
    )
    assert {key: value["code"] for key, value in result.items()} == {
        "recipeMismatch": "strategy_recipe_binding_invalid",
        "strategyVersion": "strategy_recipe_binding_invalid",
        "recipeVersion": "strategy_recipe_binding_invalid",
        "clientCost": "selection_fields_invalid",
        "clientUrl": "signed_asset_fields_invalid",
        "ugcSourceVideo": "product_ugc_assets_invalid",
        "ugcProductReference": "product_ugc_assets_invalid",
        "duplicateUri": "signed_asset_duplicate",
        "ipUrl": "signed_asset_uri_invalid",
        "viewOnUgc": "signed_asset_view_incompatible",
    }
    assert all(value["ok"] is False for value in result.values())


def test_product_swap_and_product_ad_enforce_official_counts_and_fields() -> None:
    result = _evaluate(
        r"""
        (() => {
          const common = {
            strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
            recipeVersion: subject.RUNWAY_RECIPE_VERSION,
            durationSeconds: 10,
            audio: true,
          };
          const asset = (role, index, view) => ({
            role,
            uri:`https://media.example/${role}-${index}.png?sig=${index}`,
            ...(view ? {view} : {}),
          });
          const swap = {
            ...common, strategyId:"viral_product_swap", recipe:"product_swap",
            resolution:"720p",
          };
          const ad = {
            ...common, strategyId:"viral_rebuild", recipe:"product_ad",
            ratio:"1280:720", productInfo:"Product", userConcept:"New approved ad.",
          };
          const swapBase = [
            {...asset("source_video",1),uri:"https://media.example/source-1.mp4?sig=1"},
            asset("original_product",2), asset("product_primary",3),
          ];
          return {
            swapRatio: attempt(() => subject.buildRunwayRecipeRequest(
              {...swap,ratio:"720:1280"}, swapBase
            )),
            swapMissingOriginal: attempt(() => subject.buildRunwayRecipeRequest(
              swap, swapBase.filter((item) => item.role !== "original_product")
            )),
            swapBadView: attempt(() => subject.buildRunwayRecipeRequest(
              swap, [...swapBase.slice(0,2), asset("product_primary",3,"top")]
            )),
            swapTooManyProducts: attempt(() => subject.buildRunwayRecipeRequest(
              swap, [...swapBase, ...Array.from({length:10}, (_,i) => asset("product_reference",i+10))]
            )),
            adResolution: attempt(() => subject.buildRunwayRecipeRequest(
              {...ad,resolution:"720p"}, [asset("product_primary",1)]
            )),
            adSourceVideo: attempt(() => subject.buildRunwayRecipeRequest(
              ad, [asset("product_primary",1), {...asset("source_video",2),uri:"https://media.example/source.mp4"}]
            )),
            adTooManyStyles: attempt(() => subject.buildRunwayRecipeRequest(
              ad, [asset("product_primary",1), ...Array.from({length:5}, (_,i) => asset("style_reference",i+2))]
            )),
          };
        })()
        """
    )
    assert {key: value["code"] for key, value in result.items()} == {
        "swapRatio": "selection_fields_invalid",
        "swapMissingOriginal": "original_product_count_invalid",
        "swapBadView": "signed_asset_view_invalid",
        "swapTooManyProducts": "product_swap_assets_invalid",
        "adResolution": "selection_fields_invalid",
        "adSourceVideo": "signed_asset_role_incompatible",
        "adTooManyStyles": "product_ad_assets_invalid",
    }


def test_creator_generate_wires_only_allowlisted_recipe_envelopes() -> None:
    edge = EDGE_MODULE.read_text(encoding="utf-8")
    for token in (
        'from "../_shared/generation-recipe-adapters.js"',
        '"/v1/recipes/product_ugc"',
        '"/v1/recipes/product_swap"',
        '"/v1/recipes/product_ad"',
        "buildRunwayRecipeRequest(",
        "readGenerationStrategyPayload(",
        'code: "generation_strategy_start_not_ready"',
    ):
        assert token in edge
    assert edge.index("readGenerationStrategyPayload(") < edge.index(
        "const startPayload = readStartPayload(body);"
    )
    assert edge.index('code: "generation_strategy_start_not_ready"') < edge.index(
        '"creator_generation_spec_effective_policy"'
    )


def test_creator_generate_strategy_catalog_is_explicit_and_sql_fail_closed() -> None:
    edge = EDGE_MODULE.read_text(encoding="utf-8")
    edge_contract = EDGE_CONTRACT_MODULE.read_text(encoding="utf-8")
    assert (
        'from "../_shared/generation-strategy-catalog.js"' in edge
        and "publicGenerationStrategyCatalog" in edge
    )
    assert '"system_generation_strategy_catalog_policy"' in edge
    assert '"system_generation_strategy_provider_policy"' in edge
    policy_reader = edge_contract.split(
        "export function readGenerationStrategyProviderPolicy(", 1
    )[1].split("export function readGenerationStrategyStartClaim(", 1)[0]
    for exact_policy_guard in (
        'capability.provider !== "runway"',
        "capability.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION",
        "value.contract.server_authoritative !== true",
        "value.contract.provider_call_started !== false",
        "value.contract.receipt_single_use !== true",
    ):
        assert exact_policy_guard in policy_reader

    projection = edge.split(
        "strategies: publicStrategyCatalog.strategies.map((entry) => {", 1
    )[1].split("version: GENERATION_MODEL_CATALOG_VERSION", 1)[0]
    for version_field, authoritative_source in (
        ("strategyCatalogVersion", "publicStrategyCatalog.version"),
        ("strategyRecipeVersion", "publicStrategyCatalog.recipe_version"),
        ("strategyPricingVersion", "publicStrategyCatalog.pricing_version"),
    ):
        assert f"{version_field}: {authoritative_source}" in edge
    for public_field in (
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
    ):
        assert f"{public_field}:" in projection or f"{public_field}," in projection
    for private_or_optimistic_field in (
        "...entry",
        "server:",
        "provider_path",
        "signed",
        "secret",
        "token",
        "executionSupported:",
        "launchEnabled:",
        "disabledReasonCode:",
    ):
        assert private_or_optimistic_field not in projection
    assert "enabled: entry.enabled" in projection
    assert "disabled_reason: entry.disabled_reason" in projection


def test_edge_role_mapping_never_forwards_mechanics_only_source_video() -> None:
    edge = EDGE_MODULE.read_text(encoding="utf-8")
    mapping = edge.split(
        "export function buildGenerationStrategyProviderRequest(", 1
    )[1].split("function buildProviderRequest(", 1)[0]
    assert mapping.count('role: "source_video", uri: String(asset.uri)') == 1
    assert 'context.recipe === "product_ugc"' in mapping
    assert 'context.recipe === "product_swap"' in mapping
    assert "source video is mechanics-only for Product UGC" in mapping
    assert "Product Ad consumes the source only through server-compiled mechanics" in mapping
    assert "buildRunwayRecipeRequest(selection, mappedAssets)" in mapping
