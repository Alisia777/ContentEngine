from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
SOURCE = MODULE.read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(SOURCE, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _selection(strategy_id: str) -> dict[str, object]:
    common = {
        "version": "2026-08-14.v1",
        "strategy_id": strategy_id,
        "recipe_version": "2026-06",
        "duration_seconds": 10,
        "audio": True,
    }
    attestations = {
        "source_media_rights_confirmed": True,
        "transformative_use_confirmed": True,
        "product_assets_rights_confirmed": True,
        "depicted_people_consent_confirmed": True,
    }
    if strategy_id == "viral_avatar_ugc":
        return {
            **common,
            "ratio": "720:1280",
            "assets": [
                {
                    "role": "source_video",
                    "media_id": "11111111-1111-4111-8111-111111111111",
                    "duration_seconds": 22.5,
                },
                {
                    "role": "avatar_image",
                    "media_id": "22222222-2222-4222-8222-222222222222",
                },
                {
                    "role": "product_image",
                    "media_id": "33333333-3333-4333-8333-333333333333",
                },
            ],
            "attestations": {
                **attestations,
                "avatar_likeness_consent_confirmed": True,
            },
        }
    if strategy_id == "viral_product_swap":
        return {
            **common,
            "resolution": "1080p",
            "assets": [
                {
                    "role": "source_video",
                    "media_id": "11111111-1111-4111-8111-111111111111",
                    "duration_seconds": 10,
                },
                {
                    "role": "original_product_image",
                    "media_id": "22222222-2222-4222-8222-222222222222",
                },
                {
                    "role": "new_product_image",
                    "media_id": "33333333-3333-4333-8333-333333333333",
                    "view": "front",
                },
                {
                    "role": "new_product_image",
                    "media_id": "44444444-4444-4444-8444-444444444444",
                    "view": "side",
                },
            ],
            "attestations": attestations,
        }
    if strategy_id == "viral_rebuild":
        return {
            **common,
            "ratio": "1920:1080",
            "audio": False,
            "assets": [
                {
                    "role": "source_video",
                    "media_id": "11111111-1111-4111-8111-111111111111",
                    "duration_seconds": 45,
                },
                {
                    "role": "product_image",
                    "media_id": "22222222-2222-4222-8222-222222222222",
                },
                {
                    "role": "style_image",
                    "media_id": "33333333-3333-4333-8333-333333333333",
                },
            ],
            "attestations": attestations,
        }
    raise AssertionError(f"unsupported fixture strategy: {strategy_id}")


def _runtime_expression(function: str, value: object) -> str:
    return f"subject.{function}({json.dumps(value, ensure_ascii=False)})"


def test_catalog_is_pure_deep_frozen_and_has_only_three_canonical_ids() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "fetch(",
        "XMLHttpRequest",
    ):
        assert forbidden not in SOURCE

    result = _evaluate(
        """
        (() => {
          const deepFrozen = (value) => !value || typeof value !== "object" || (
            Object.isFrozen(value) && Object.values(value).every(deepFrozen)
          );
          return {
            version: subject.GENERATION_STRATEGY_CATALOG_VERSION,
            recipeVersion: subject.RUNWAY_RECIPE_VERSION,
            pricingVersion: subject.RUNWAY_RECIPE_PRICING_VERSION,
            ids: subject.GENERATION_STRATEGY_CATALOG.map((entry) => entry.strategy_id),
            idObject: subject.GENERATION_STRATEGY_IDS,
            deepFrozen: deepFrozen(subject.GENERATION_STRATEGY_CATALOG),
            staleIdsResolve: [
              "viral_avatar_insert",
              "viral_product_replace",
              "reference_recreate_from_scratch",
            ].map((id) => subject.generationStrategyCatalogEntry(id)),
          };
        })()
        """
    )
    assert result == {
        "version": "2026-08-14.v1",
        "recipeVersion": "2026-06",
        "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
        "ids": ["viral_avatar_ugc", "viral_product_swap", "viral_rebuild"],
        "idObject": {
            "avatarUgc": "viral_avatar_ugc",
            "productSwap": "viral_product_swap",
            "rebuild": "viral_rebuild",
        },
        "deepFrozen": True,
        "staleIdsResolve": [None, None, None],
    }


def test_recipe_routes_assets_and_reference_semantics_are_exact() -> None:
    result = _evaluate(
        """
        subject.GENERATION_STRATEGY_CATALOG.map((entry) => ({
          id: entry.strategy_id,
          recipe: entry.recipe,
          path: entry.server.provider_path,
          referenceMode: entry.source_reference_mode,
          transformation: entry.transformation_kind,
          roles: entry.asset_roles.map((role) => ({
            role: role.role,
            count: [role.min_count, role.max_count],
            kind: role.media_kind,
            forwarded: role.forwarded_to_provider,
            providerField: role.provider_field,
            views: role.allowed_views,
            duration: [
              role.duration_required,
              role.min_duration_seconds,
              role.max_duration_seconds,
            ],
          })),
          attestations: entry.required_attestations.map((item) => item.id),
          notice: entry.preservation_notice,
        }))
        """
    )
    by_id = {item["id"]: item for item in result}

    avatar = by_id["viral_avatar_ugc"]
    assert avatar["recipe"] == "product_ugc"
    assert avatar["path"] == "/v1/recipes/product_ugc"
    assert avatar["referenceMode"] == "mechanics_only_not_provider_input"
    assert avatar["transformation"] == "new_ugc_remake"
    assert [(r["role"], r["forwarded"], r["providerField"]) for r in avatar["roles"]] == [
        ("source_video", False, None),
        ("avatar_image", True, "characterImage"),
        ("product_image", True, "productImage"),
    ]
    assert "avatar_likeness_consent_confirmed" in avatar["attestations"]
    assert "новый ролик" in avatar["notice"].lower()

    swap = by_id["viral_product_swap"]
    assert swap["recipe"] == "product_swap"
    # Runway has no /v1/recipes/product_swap; the real endpoint is
    # video_to_video (Gen-4 Aleph).
    assert swap["path"] == "/v1/video_to_video"
    assert swap["referenceMode"] == "provider_reference_video"
    assert swap["transformation"] == "product_swap_preserve_scene"
    assert [(r["role"], r["count"], r["providerField"]) for r in swap["roles"]] == [
        ("source_video", [1, 1], "referenceVideo"),
        ("original_product_image", [1, 1], "originalProductImage"),
        ("new_product_image", [1, 10], "newProductImages"),
    ]
    assert swap["roles"][0]["duration"] == [True, 1.8, 15]
    assert swap["roles"][2]["views"] == ["front", "side", "back"]
    assert "не гарантирует" in swap["notice"].lower()

    rebuild = by_id["viral_rebuild"]
    assert rebuild["recipe"] == "product_ad"
    assert rebuild["path"] == "/v1/recipes/product_ad"
    assert rebuild["referenceMode"] == "mechanics_and_style_only_not_provider_input"
    assert rebuild["transformation"] == "new_product_ad_remake"
    assert [(r["role"], r["count"], r["forwarded"], r["providerField"]) for r in rebuild["roles"]] == [
        ("source_video", [1, 1], False, None),
        ("product_image", [1, 10], True, "productImages"),
        ("style_image", [0, 4], True, "styleImages"),
    ]
    assert "новый product ad" in rebuild["notice"].lower()

    assert swap["attestations"] == [
        "source_media_rights_confirmed",
        "transformative_use_confirmed",
        "product_assets_rights_confirmed",
        "depicted_people_consent_confirmed",
    ]
    assert rebuild["attestations"] == swap["attestations"]


def test_duration_dimension_audio_rules_match_official_recipe_contracts() -> None:
    result = _evaluate(
        """
        Object.fromEntries(subject.GENERATION_STRATEGY_CATALOG.map((entry) => [
          entry.strategy_id,
          entry.output_rules,
        ]))
        """
    )
    avatar = result["viral_avatar_ugc"]
    assert avatar["duration"] == {"min_seconds": 4, "max_seconds": 15, "default_seconds": 15}
    assert avatar["dimension_field"] == "ratio"
    assert avatar["ratios"] == ["720:1280", "1080:1920"]
    assert avatar["audio"] == {"required_explicit_boolean": True, "provider_default": True}

    swap = result["viral_product_swap"]
    assert swap["duration"] == {"min_seconds": 4, "max_seconds": 15, "default_seconds": 10}
    assert swap["dimension_field"] == "resolution"
    assert swap["ratios"] == []
    assert swap["resolutions"] == ["720p", "1080p"]
    assert swap["audio"] == {"required_explicit_boolean": True, "provider_default": True}

    rebuild = result["viral_rebuild"]
    assert rebuild["duration"] == {"min_seconds": 4, "max_seconds": 15, "default_seconds": 10}
    assert rebuild["dimension_field"] == "ratio"
    assert rebuild["ratios"] == [
        "1280:720",
        "720:1280",
        "960:960",
        "834:1112",
        "1920:1080",
        "1080:1920",
        "1440:1440",
        "1248:1664",
    ]
    assert rebuild["audio"] == {"required_explicit_boolean": True, "provider_default": False}


def test_current_official_credit_formulas_cover_every_recipe_and_resolution() -> None:
    result = _evaluate(
        """
        (() => {
          const inputs = {
            viral_avatar_ugc: {
              "720p": {duration_seconds: 4, ratio: "720:1280", audio: true},
              "1080p": {duration_seconds: 4, ratio: "1080:1920", audio: true},
            },
            viral_product_swap: {
              "720p": {duration_seconds: 4, resolution: "720p", audio: true},
              "1080p": {duration_seconds: 4, resolution: "1080p", audio: true},
            },
            viral_rebuild: {
              "720p": {duration_seconds: 4, ratio: "1280:720", audio: false},
              "1080p": {duration_seconds: 4, ratio: "1920:1080", audio: false},
            },
          };
          return Object.fromEntries(Object.entries(inputs).map(([id, tiers]) => [
            id,
            Object.fromEntries(Object.entries(tiers).map(([tier, input]) => {
              const atFour = subject.estimateGenerationStrategyCredits(id, input);
              const atFifteen = subject.estimateGenerationStrategyCredits(id, {
                ...input, duration_seconds: 15,
              });
              return [tier, {
                atFour: atFour.estimated_credits,
                atFifteen: atFifteen.estimated_credits,
                centsAtFifteen: atFifteen.estimated_pre_tax_usd_minor,
                pricingVersion: atFifteen.pricing_version,
              }];
            })),
          ]));
        })()
        """
    )
    assert result == {
        "viral_avatar_ugc": {
            "720p": {
                "atFour": 192,
                "atFifteen": 588,
                "centsAtFifteen": 588,
                "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
            },
            "1080p": {
                "atFour": 208,
                "atFifteen": 648,
                "centsAtFifteen": 648,
                "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
            },
        },
        "viral_product_swap": {
            "720p": {
                "atFour": 212,
                "atFifteen": 608,
                "centsAtFifteen": 608,
                "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
            },
            "1080p": {
                "atFour": 228,
                "atFifteen": 668,
                "centsAtFifteen": 668,
                "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
            },
        },
        "viral_rebuild": {
            "720p": {
                "atFour": 200,
                "atFifteen": 596,
                "centsAtFifteen": 596,
                "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
            },
            "1080p": {
                "atFour": 216,
                "atFifteen": 656,
                "centsAtFifteen": 656,
                "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
            },
        },
    }


@pytest.mark.parametrize(
    "strategy_id",
    ["viral_avatar_ugc", "viral_product_swap", "viral_rebuild"],
)
def test_exact_wire_selections_validate_without_claiming_execution(strategy_id: str) -> None:
    result = _evaluate(
        _runtime_expression("validateGenerationStrategySelection", _selection(strategy_id))
    )
    assert result["ok"] is True
    assert result["strategy_id"] == strategy_id
    assert result["provider"] == "runway"
    assert result["recipe_version"] == "2026-06"
    assert result["estimated_credits"] > 0
    assert "provider_path" not in result


def test_selection_validation_rejects_unknown_stale_and_client_authoritative_fields() -> None:
    valid = _selection("viral_avatar_ugc")
    result = _evaluate(
        f"""
        (() => {{
          const valid = {json.dumps(valid, ensure_ascii=False)};
          const clone = () => JSON.parse(JSON.stringify(valid));
          const stale = clone(); stale.strategy_id = "viral_avatar_insert";
          const version = clone(); version.version = "2026-08-13.v1";
          const recipe = clone(); recipe.recipe_version = "unsafe-latest";
          const provider = clone(); provider.provider = "runway";
          const providerPath = clone(); providerPath.provider_path = "/v1/recipes/product_ugc";
          const cost = clone(); cost.estimated_credits = 1;
          const uri = clone(); uri.assets[0].uri = "https://attacker.invalid/video.mp4";
          return {{
            stale: subject.validateGenerationStrategySelection(stale),
            version: subject.validateGenerationStrategySelection(version),
            recipe: subject.validateGenerationStrategySelection(recipe),
            provider: subject.validateGenerationStrategySelection(provider),
            providerPath: subject.validateGenerationStrategySelection(providerPath),
            cost: subject.validateGenerationStrategySelection(cost),
            uri: subject.validateGenerationStrategySelection(uri),
          }};
        }})()
        """
    )
    assert result["stale"]["code"] == "strategy_unknown"
    assert result["version"]["code"] == "catalog_version_mismatch"
    assert result["recipe"]["code"] == "recipe_version_mismatch"
    assert result["provider"]["code"] == "selection_field_unknown"
    assert result["providerPath"]["code"] == "selection_field_unknown"
    assert result["cost"]["code"] == "selection_field_unknown"
    assert result["uri"]["code"] == "asset_field_unknown"


def test_selection_validation_fails_closed_on_output_assets_and_rights() -> None:
    avatar = _selection("viral_avatar_ugc")
    swap = _selection("viral_product_swap")
    result = _evaluate(
        f"""
        (() => {{
          const avatar = {json.dumps(avatar, ensure_ascii=False)};
          const swap = {json.dumps(swap, ensure_ascii=False)};
          const clone = (value) => JSON.parse(JSON.stringify(value));
          const duration = clone(avatar); duration.duration_seconds = 3;
          const audio = clone(avatar); audio.audio = "true";
          const dimension = clone(avatar); dimension.resolution = "720p";
          const ratio = clone(avatar); ratio.ratio = "9:16";
          const missingAsset = clone(avatar); missingAsset.assets.pop();
          const duplicateAsset = clone(avatar);
          duplicateAsset.assets[2].media_id = duplicateAsset.assets[1].media_id;
          const zeroAsset = clone(avatar);
          zeroAsset.assets[0].media_id = "00000000-0000-0000-0000-000000000000";
          const falseRight = clone(avatar);
          falseRight.attestations.avatar_likeness_consent_confirmed = false;
          const extraRight = clone(avatar);
          extraRight.attestations.spend_confirmed = true;
          const missingRight = clone(avatar);
          delete missingRight.attestations.source_media_rights_confirmed;
          const shortSwap = clone(swap); shortSwap.assets[0].duration_seconds = 1.79;
          const longSwap = clone(swap); longSwap.assets[0].duration_seconds = 15.01;
          const missingSwapDuration = clone(swap);
          delete missingSwapDuration.assets[0].duration_seconds;
          const badView = clone(swap); badView.assets[2].view = "top";
          return {{
            duration: subject.validateGenerationStrategySelection(duration),
            audio: subject.validateGenerationStrategySelection(audio),
            dimension: subject.validateGenerationStrategySelection(dimension),
            ratio: subject.validateGenerationStrategySelection(ratio),
            missingAsset: subject.validateGenerationStrategySelection(missingAsset),
            duplicateAsset: subject.validateGenerationStrategySelection(duplicateAsset),
            zeroAsset: subject.validateGenerationStrategySelection(zeroAsset),
            falseRight: subject.validateGenerationStrategySelection(falseRight),
            extraRight: subject.validateGenerationStrategySelection(extraRight),
            missingRight: subject.validateGenerationStrategySelection(missingRight),
            shortSwap: subject.validateGenerationStrategySelection(shortSwap),
            longSwap: subject.validateGenerationStrategySelection(longSwap),
            missingSwapDuration: subject.validateGenerationStrategySelection(missingSwapDuration),
            badView: subject.validateGenerationStrategySelection(badView),
          }};
        }})()
        """
    )
    assert result["duration"]["code"] == "duration_unsupported"
    assert result["audio"]["code"] == "audio_invalid"
    assert result["dimension"]["code"] == "dimension_field_forbidden"
    assert result["ratio"]["code"] == "ratio_unsupported"
    assert result["missingAsset"]["code"] == "asset_role_count_invalid"
    assert result["duplicateAsset"]["code"] == "asset_media_id_duplicate"
    assert result["zeroAsset"]["code"] == "asset_media_id_invalid"
    assert result["falseRight"]["code"] == "attestation_required"
    assert result["extraRight"]["code"] == "attestation_unknown"
    assert result["missingRight"]["code"] == "attestation_required"
    assert result["shortSwap"]["code"] == "asset_duration_unsupported"
    assert result["longSwap"]["code"] == "asset_duration_unsupported"
    assert result["missingSwapDuration"]["code"] == "asset_duration_required"
    assert result["badView"]["code"] == "asset_view_unsupported"


def test_public_projection_is_allowlisted_immutable_and_disabled_by_default() -> None:
    result = _evaluate(
        """
        (() => {
          const capability = (entry) => ({
            enabled: true,
            catalog_version: subject.GENERATION_STRATEGY_CATALOG_VERSION,
            strategy_id: entry.strategy_id,
            provider: entry.provider,
            recipe: entry.recipe,
            recipe_version: entry.recipe_version,
            provider_path: entry.server.provider_path,
            pricing_version: entry.pricing_version,
          });
          const good = Object.fromEntries(subject.GENERATION_STRATEGY_CATALOG.map(
            (entry) => [entry.strategy_id, capability(entry)],
          ));
          const stale = JSON.parse(JSON.stringify(good));
          stale.viral_avatar_ugc.catalog_version = "stale";
          const extra = JSON.parse(JSON.stringify(good));
          extra.viral_product_swap.unverified = true;
          const base = subject.publicGenerationStrategyCatalog();
          const enabled = subject.publicGenerationStrategyCatalog({executionCapabilities: good});
          const staleProjection = subject.publicGenerationStrategyCatalog({executionCapabilities: stale});
          const extraProjection = subject.publicGenerationStrategyCatalog({executionCapabilities: extra});
          const serialized = JSON.stringify(base);
          return {
            baseEnabled: base.strategies.map((entry) => entry.enabled),
            baseReasons: base.strategies.map((entry) => entry.disabled_reason),
            enabled: enabled.strategies.map((entry) => entry.enabled),
            stale: staleProjection.strategies.map((entry) => entry.enabled),
            extra: extraProjection.strategies.map((entry) => entry.enabled),
            frozen: Object.isFrozen(base) && Object.isFrozen(base.strategies) &&
              base.strategies.every((entry) => Object.isFrozen(entry)),
            leaks: [
              "/v1/recipes/",
              "provider_field",
              "forwarded_to_provider",
              '"server"',
              "secret",
              "authorization",
              "media_id",
            ].filter((token) => serialized.toLowerCase().includes(token.toLowerCase())),
            humanReview: base.strategies.map((entry) => entry.human_review_required),
            sourceUse: base.strategies.map((entry) =>
              entry.asset_roles.find((role) => role.role === "source_video").source_use
            ),
          };
        })()
        """
    )
    assert result["baseEnabled"] == [False, False, False]
    assert result["baseReasons"] == ["strategy_route_not_verified"] * 3
    assert result["enabled"] == [True, True, True]
    assert result["stale"] == [False, True, True]
    assert result["extra"] == [True, False, True]
    assert result["frozen"] is True
    assert result["leaks"] == []
    assert result["humanReview"] == [True, True, True]
    assert result["sourceUse"] == [
        "mechanics_or_style_reference_only",
        "provider_input",
        "mechanics_or_style_reference_only",
    ]


def test_execution_validation_requires_exact_server_owned_capability_handshake() -> None:
    selection = _selection("viral_product_swap")
    result = _evaluate(
        f"""
        (() => {{
          const selection = {json.dumps(selection, ensure_ascii=False)};
          const entry = subject.generationStrategyCatalogEntry(selection.strategy_id);
          const capability = {{
            enabled: true,
            catalog_version: subject.GENERATION_STRATEGY_CATALOG_VERSION,
            strategy_id: entry.strategy_id,
            provider: entry.provider,
            recipe: entry.recipe,
            recipe_version: entry.recipe_version,
            provider_path: entry.server.provider_path,
            pricing_version: entry.pricing_version,
          }};
          const good = {{[entry.strategy_id]: capability}};
          const wrongPath = {{[entry.strategy_id]: {{...capability, provider_path: "/v1/recipes/product_ad"}}}};
          return {{
            defaultResult: subject.validateGenerationStrategyForExecution(selection),
            wrongPath: subject.validateGenerationStrategyForExecution(selection, {{
              executionCapabilities: wrongPath,
            }}),
            enabled: subject.validateGenerationStrategyForExecution(selection, {{
              executionCapabilities: good,
            }}),
          }};
        }})()
        """
    )
    assert result["defaultResult"]["code"] == "strategy_execution_not_enabled"
    assert result["wrongPath"]["code"] == "strategy_execution_not_enabled"
    assert result["enabled"]["ok"] is True
    assert result["enabled"]["provider_path"] == "/v1/video_to_video"
    assert result["enabled"]["estimated_credits"] == 468
