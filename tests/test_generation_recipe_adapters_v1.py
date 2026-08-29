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
            # Речь ведущего для «Дуэта» — БУКВАЛЬНЫЙ текст, который он
            # произнесёт вслух. Отдельно от компиляторов указаний: те собирают
            # задание модели («замени человека в кадре»), и ведущий зачитал бы
            # техзадание прямо в кадре.
            "buildDuetCommentaryScript",
            # Компиляторы «замены человека в кадре» (buildFalAvatarSelection и
            # buildRunwayAvatarPrompt) убраны 22.08.2026 вместе с самим таким
            # прочтением стратегии. Это было не мёртвым кодом общего вида, а
            # готовым ПЛАТНЫМ телом запроса: одна строка маршрута — и оператор
            # за настоящие деньги получил бы переписанный чужой ролик вместо
            # комментария к нему.
            # Второй маршрут «Копии»: точечная замена объекта через fal.
            # Экспорт такой же чистый — сборка тела запроса без сети.
            "buildFalProductSwapSelection",
            "buildFalRecipeRequest",
            # Создание ведущего — ОТДЕЛЬНЫЙ платный вызов ($1.00), а не часть
            # генерации: ведущий заводится один раз и живёт долго.
            "buildHeygenAvatarRequest",
            # Ведущий для «Дуэта». С 23.08.2026 исходник уходит провайдеру
            # фоном (v2), ведущий встаёт в угол кружком/вырезом.
            "buildHeygenRecipeRequest",
            # «Создание» на Runway Gen-4 Turbo (29.08.2026): настоящий
            # /v1/image_to_video, первое фото товара — стартовый кадр.
            "buildRunwayGen4ProductAdRequest",
            "buildRunwayProductSwapPrompt",
            "buildRunwayRecipeRequest",
            # Раскладка врезки → масштаб и смещение провайдера; чистая
            # арифметика, экспортирована ради проверки и калибровки.
            "heygenOverlayPlacement",
        ],
        "strategyVersion": "2026-08-14.v1",
        "recipeVersion": "2026-06",
        "mapping": {
            "viral_avatar_ugc": "product_ugc",
            "viral_product_swap": "product_swap",
            "viral_rebuild": "product_ad",
        },
        "endpoints": {
            # Runway has no /v1/recipes/* endpoints at all. Product Swap moved
            # to the real video_to_video (Gen-4 Aleph) on 17.08.2026, and Avatar
            # followed on 21.08.2026 when it became a video edit rather than a
            # new UGC shoot.
            "product_ugc": "/v1/video_to_video",
            "product_swap": "/v1/video_to_video",
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
          // «Дуэт» через Runway не собирается вовсе: этот движок умеет только
          // переписать исходник, а дуэту нужен отдельно снятый ведущий поверх
          // нетронутого ролика.
          let ugcRefusal = null;
          try {
            subject.buildRunwayRecipeRequest({
              ...common,
              strategyId: "viral_avatar_ugc",
              recipe: "product_ugc",
              durationSeconds: 15,
              resolution: "720p",
              audio: true,
              promptText: "Replace the person on camera with our consenting avatar; keep the scene.",
            }, [signed("source_video", "source.mp4"), signed("avatar", "avatar.jpg")]);
          } catch (error) {
            ugcRefusal = error?.code || String(error);
          }
          const swap = subject.buildRunwayRecipeRequest({
            ...common,
            strategyId: "viral_product_swap",
            recipe: "product_swap",
            durationSeconds: 10,
            resolution: "1080p",
            audio: true,
            promptText: "Replace the product with the referenced exact product.",
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
            ugcRefusal,
            swap,
            ad,
            frozen: [swap, ad].every((item) =>
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
    # «Дуэт» Runway не собирает. До 22.08.2026 собирал — тогда стратегия
    # считалась заменой человека в кадре, и тело было тем же aleph2, что у
    # «Копии». Владелец это отменил: исходник не трогается вовсе.
    #
    # Отказ живёт в адаптере, а не только в реестре маршрутов, потому что цена
    # ошибки здесь денежная: одна строка в базе — и оператор получил бы
    # переписанный чужой ролик вместо комментария к нему.
    assert result["ugcRefusal"] == "runway_recipe_unsupported"
    # Real aleph2 video_to_video body (2024-11-06): model/videoUri/promptText/
    # targetAspectRatio only — the route is prompt-only because timed keyframes
    # with product photos pull the scene toward the photos' interiors instead
    # of the source footage (verified on paid runs 17.08.2026). The exact dict
    # equality below also pins the ABSENCE of keyframes, of foreign recipe
    # fields (duration/audio/resolution/version) and of originalProductImage —
    # the frame is already inside the source video, while the asset set
    # validation still requires the photos server-side.
    assert result["swap"] == {
        **common_envelope,
        "endpointPath": "/v1/video_to_video",
        "body": {
            "model": "aleph2",
            "videoUri": "https://project.supabase.co/storage/v1/object/sign/private/source.mp4?token=opaque",
            "promptText": "Replace the product with the referenced exact product.",
            "targetAspectRatio": "9:16",
        },
    }
    for foreign_field in (
        "duration",
        "audio",
        "resolution",
        "version",
        "originalProductImage",
        "referenceVideo",
        "newProductImages",
    ):
        assert foreign_field not in result["swap"]["body"]
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
            resolution: "720p",
            audio: true,
            promptText: "Replace the person on camera with a consenting avatar.",
          };
          const avatar = {role:"avatar",uri:"https://media.example/avatar.png?sig=a"};
          const product = {role:"product_primary",uri:"https://media.example/product.png?sig=b"};
          const source = {role:"source_video",uri:"https://media.example/source.mp4?sig=c"};
          const original = {role:"original_product",uri:"https://media.example/orig.png?sig=d"};
          const swapBase = {
            ...base,
            strategyId: "viral_product_swap",
            recipe: "product_swap",
            promptText: "Replace the product with the referenced exact product.",
          };
          return {
            recipeMismatch: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, recipe:"product_ad"}, [source, avatar]
            )),
            strategyVersion: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, strategyVersion:"unsafe-latest"}, [source, avatar]
            )),
            recipeVersion: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, recipeVersion:"unsafe-latest"}, [source, avatar]
            )),
            clientCost: attempt(() => subject.buildRunwayRecipeRequest(
              {...base, estimatedCostMinor:1}, [source, avatar]
            )),
            clientUrl: attempt(() => subject.buildRunwayRecipeRequest(
              base, [source, {...avatar,url:"https://evil.example/avatar.png"}]
            )),
            duplicateUri: attempt(() => subject.buildRunwayRecipeRequest(
              base, [source, {...avatar,uri:source.uri}]
            )),
            ipUrl: attempt(() => subject.buildRunwayRecipeRequest(
              base, [{...avatar,uri:"https://127.0.0.1/a.png"}, product]
            )),
            // «Дуэт» этим движком не собирается вовсе: он умеет только
            // переписать исходник. Отказ наступает до разбора ролей — сам
            // рецепт сюда не относится.
            duetRecipe: attempt(() => subject.buildRunwayRecipeRequest(
              base, [source, avatar]
            )),
            // Чужие роли и вид ракурса проверяются на «Копии»: это её тело
            // собирается из ассетов, и именно там подмена набора имеет цену.
            swapAvatar: attempt(() => subject.buildRunwayRecipeRequest(
              swapBase, [source, original, product, avatar]
            )),
            swapStyleReference: attempt(() => subject.buildRunwayRecipeRequest(
              swapBase,
              [source, original, product,
               {role:"style_reference",uri:"https://media.example/mood.png"}]
            )),
            viewOnSwapSource: attempt(() => subject.buildRunwayRecipeRequest(
              swapBase, [{...source,view:"front"}, original, product]
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
        "duplicateUri": "signed_asset_duplicate",
        "ipUrl": "signed_asset_uri_invalid",
        "duetRecipe": "runway_recipe_unsupported",
        "swapAvatar": "signed_asset_role_incompatible",
        "swapStyleReference": "signed_asset_role_incompatible",
        "viewOnSwapSource": "signed_asset_view_incompatible",
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
            promptText:"Swap the product; preserve the original scene.",
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
            swapMissingPrompt: attempt(() => subject.buildRunwayRecipeRequest(
              (() => { const {promptText, ...rest} = swap; return rest; })(),
              swapBase
            )),
            swapAtPromptLimit: attempt(() => subject.buildRunwayRecipeRequest(
              {...swap, promptText:"p".repeat(1000)}, swapBase
            )),
            swapOverlongPrompt: attempt(() => subject.buildRunwayRecipeRequest(
              {...swap, promptText:"p".repeat(1001)}, swapBase
            )),
            swapReferenceCap: attempt(() => subject.buildRunwayRecipeRequest(
              swap,
              [...swapBase, ...Array.from({length:5}, (_,i) => asset("product_reference",i+10))]
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
    successes = {"swapAtPromptLimit", "swapReferenceCap"}
    failures = {key: value for key, value in result.items() if key not in successes}
    assert {key: value["code"] for key, value in failures.items()} == {
        "swapRatio": "selection_fields_invalid",
        "swapMissingOriginal": "original_product_count_invalid",
        "swapBadView": "signed_asset_view_invalid",
        "swapTooManyProducts": "product_swap_assets_invalid",
        "swapMissingPrompt": "selection_fields_invalid",
        "swapOverlongPrompt": "prompt_text_invalid",
        "adResolution": "selection_fields_invalid",
        "adSourceVideo": "signed_asset_role_incompatible",
        "adTooManyStyles": "product_ad_assets_invalid",
    }
    # Prompt-only body even when many photos pass the server-side asset
    # validation: the photos stay spend-contour selection assets and never
    # leak into the provider body as keyframes.
    cap = result["swapReferenceCap"]
    assert cap["ok"] is True
    assert "keyframes" not in cap["value"]["body"]
    boundary = result["swapAtPromptLimit"]
    assert boundary["ok"] is True
    assert len(boundary["value"]["body"]["promptText"]) == 1_000


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
    )[1].split("export async function readGenerationStrategyStartClaim(", 1)[0]
    for exact_policy_guard in (
        "capability.provider !== expected.provider",
        "!record(route)",
        "capability.provider_path !== route.providerPath",
        "capability.poll_kind !== route.pollKind",
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
    # Правки готового видео исходник провайдеру ОТДАЮТ: «Копия» с самого начала,
    # «Аватар» — с 21.08.2026, когда он перестал быть съёмкой нового UGC про
    # товар. Отсюда два отображения роли вместо одного.
    assert mapping.count('role: "source_video", uri: String(asset.uri)') == 2
    assert 'context.recipe === "product_ugc"' in mapping
    assert 'context.recipe === "product_swap"' in mapping

    # А вот инвариант «Создания» остаётся и стережётся здесь же: product_ad
    # собирает ролик с нуля и исходник видеть не должен никогда — он доходит до
    # модели только серверным разбором механики внутри userConcept.
    assert "Product Ad consumes the source only through server-compiled mechanics" in mapping
    assert "buildRunwayRecipeRequest(selection, mappedAssets)" in mapping

    # Товар ушёл из «Аватара»: роль product_image в его ветке обязана отвергаться,
    # а не молча превращаться в product_primary, иначе провайдеру уйдёт набор,
    # которого нет в подписанной привязке.
    ugc_branch = mapping.split('if (context.recipe === "product_ugc") {', 1)[1].split(
        'else if (context.recipe === "product_swap")', 1
    )[0]
    assert 'role: "avatar"' in ugc_branch
    assert "product_primary" not in ugc_branch
