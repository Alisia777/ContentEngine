"""Движки «Создания» (viral_rebuild), заведённые 23.08.2026.

До этого у стратегии не было ни одной строки реестра, а единственная
«исполнимая пара» вела на несуществующий адрес Runway. Теперь четыре модели
fal класса «фото → видео»; ролик-референс провайдеру не уходит. Проверяется
согласие всех слоёв и тела запросов против схем fal.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "supabase/functions/_shared/generation-recipe-adapters.js"
CATALOG = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
EDGE_CONTRACT = ROOT / (
    "supabase/functions/_shared/generation-strategy-edge-contract.js"
)
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"
RUNTIME = ROOT / "web/app/generation-strategy-runtime.js"
APP = ROOT / "web/app/app.js"
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"
GUIDED = ROOT / "web/app/workspace-os-v4-generation-guided.js"
ADVISOR = ROOT / "web/app/generation-engine-advisor.js"
MIGRATION = ROOT / (
    "supabase/migrations/202608230021_rebuild_engines_reference_to_video_v1.sql"
)

ADAPTER_SOURCE = ADAPTER.read_text(encoding="utf-8")
CATALOG_SOURCE = CATALOG.read_text(encoding="utf-8")
EDGE_CONTRACT_SOURCE = EDGE_CONTRACT.read_text(encoding="utf-8")
EDGE_SOURCE = EDGE.read_text(encoding="utf-8")
RUNTIME_SOURCE = RUNTIME.read_text(encoding="utf-8")
APP_SOURCE = APP.read_text(encoding="utf-8")
INTAKE_SOURCE = INTAKE.read_text(encoding="utf-8")
GUIDED_SOURCE = GUIDED.read_text(encoding="utf-8")
MIGRATION_SOURCE = MIGRATION.read_text(encoding="utf-8")

ENGINES = {
    "minimax/h3/reference-to-video": {
        "pricing_version": "fal-usd-per-second-minimax-h3-2026-08-23.v1",
        "shape": "minimax_images_regenerate",
        "rate": 6,
        "window": (5, 15),
        "recommended": True,
    },
    "xai/grok-imagine-video/reference-to-video": {
        "pricing_version": "fal-usd-per-second-grok-imagine-2026-08-23.v1",
        "shape": "grok_images_regenerate",
        "rate": 8,
        "window": (4, 10),
        "recommended": False,
    },
    "alibaba/happy-horse/reference-to-video": {
        "pricing_version": "fal-usd-per-second-happy-horse-reference-2026-08-23.v1",
        "shape": "happy_horse_images_regenerate",
        "rate": 14,
        "window": (4, 15),
        "recommended": False,
    },
    "bytedance/seedance-2.5/reference-to-video": {
        "pricing_version": "fal-usd-per-second-bytedance-2-5-2026-08-23.v1",
        "shape": "seedance_images_regenerate",
        "rate": 48,
        "window": (4, 15),
        "recommended": False,
    },
}
NEW_VERSIONS = [
    "fal-usd-per-second-grok-imagine-2026-08-23.v1",
    "fal-usd-per-second-happy-horse-reference-2026-08-23.v1",
]


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for provider body contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        (directory / ADAPTER.name).write_text(ADAPTER_SOURCE, encoding="utf-8")
        (directory / CATALOG.name).write_text(CATALOG_SOURCE, encoding="utf-8")
        (directory / EDGE_CONTRACT.name).write_text(
            EDGE_CONTRACT_SOURCE, encoding="utf-8"
        )
        (directory / "contract.js").write_text(
            "import * as subject from './generation-recipe-adapters.js';\n"
            "import * as catalog from './generation-strategy-catalog.js';\n"
            "import * as edge from './generation-strategy-edge-contract.js';\n"
            f"const result = await ({expression});\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [node, "contract.js"], cwd=directory, capture_output=True,
            text=True, encoding="utf-8", timeout=20, check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def _bodies(duration: int, ratio: str, reference_count: int, styles: int = 0):
    references = ", ".join(
        f'signed("product_reference", "angle-{index}.webp")'
        for index in range(reference_count)
    )
    style_refs = ", ".join(
        f'signed("style_reference", "style-{index}.jpg")' for index in range(styles)
    )
    assets = ", ".join(filter(None, [
        'signed("product_primary", "front.jpg")', references, style_refs,
    ]))
    return _evaluate(
        f"""
        (() => {{
          const signed = (role, name) => ({{
            role,
            uri: `https://project.supabase.co/storage/v1/object/sign/private/${{name}}?token=opaque`,
          }});
          const assets = [{assets}];
          const selection = {{
            strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
            strategyId: "viral_rebuild",
            recipe: "product_ad",
            recipeVersion: subject.RUNWAY_RECIPE_VERSION,
            durationSeconds: {duration},
            audio: false,
            ratio: {json.dumps(ratio)},
            productInfo: "Product: ROASTER grill. SKU: ROASTER-1. Category: household.",
            userConcept: "Hook: the grill opens in one motion. Beats: close-up on the lid, smoke, skewers laid out, family gathers. Camera: slow push-in, then handheld. Keep the mood warm.",
          }};
          const out = {{}};
          for (const modelKey of {json.dumps(list(ENGINES))}) {{
            try {{
              out[modelKey] = subject.buildFalRecipeRequest(selection, assets, modelKey);
            }} catch (error) {{
              out[modelKey] = {{ error: String(error.message) }};
            }}
          }}
          return out;
        }})()
        """
    )


def test_catalog_edge_contract_and_migration_agree_on_every_rebuild_engine():
    result = _evaluate(
        """
        ({
          shapes: catalog.FAL_STRATEGY_MODEL_SHAPES.product_ad,
          versions: catalog.GENERATION_STRATEGY_PRICING_VERSIONS,
          routes: edge.GENERATION_STRATEGY_EDGE_CONTRACT.providerPolicyRoutes.viral_rebuild,
          limits: catalog.FAL_SHAPE_IMAGE_LIMITS,
        })
        """
    )
    for model_key, engine in ENGINES.items():
        assert result["shapes"][model_key] == engine["shape"], model_key
        assert engine["pricing_version"] in result["versions"], model_key
        assert result["routes"][f"fal:{model_key}"] == {
            "providerPath": model_key,
            "pollKind": "fal_request",
            "pricingVersion": engine["pricing_version"],
        }
        assert result["limits"][engine["shape"]] >= 5
        assert model_key not in ADAPTER_SOURCE
        assert f'"fal:{model_key}"' in INTAKE_SOURCE
    for version in NEW_VERSIONS:
        assert version in RUNTIME_SOURCE
        assert APP_SOURCE.count(f'"{version}"') >= 2
    assert '"fal-usd-per-second-grok-imagine-2026-08-23.v1": "Grok Imagine"' in APP_SOURCE
    assert (
        '"fal-usd-per-second-happy-horse-reference-2026-08-23.v1": "Happy Horse"'
        in APP_SOURCE
    )


def test_migration_registers_rows_allowlist_and_launch_gate_for_rebuild():
    checks = re.findall(
        r"pricing_version_check\n  check \(pricing_version = any \(array\[(.*?)\]\)\);",
        MIGRATION_SOURCE, flags=re.DOTALL,
    )
    assert len(checks) == 2
    for check in checks:
        versions = re.findall(r"'([^']+)'", check)
        assert len(versions) == 10
        for version in NEW_VERSIONS:
            assert version in versions
    allowed = MIGRATION_SOURCE.split("route_allowed(", 1)[1].split("-- 3. Рубильник", 1)[0]
    # Несуществующий рецептный адрес Runway из списка исполнимых пар убран.
    assert "/v1/recipes/product_ad" not in allowed
    assert "viral_rebuild" in allowed
    for model_key, engine in ENGINES.items():
        assert f"'{model_key}'" in allowed
        assert f"'{engine['pricing_version']}'" in allowed
    launch = MIGRATION_SOURCE.split("do $launch_gate_rebuild_engines$", 1)[1]
    assert "when 'fal:xai/grok-imagine-video/reference-to-video' then true" in launch
    assert "when 'fal:alibaba/happy-horse/reference-to-video' then true" in launch
    rows = MIGRATION_SOURCE.split("-- 4. Строки реестра", 1)[1].split(
        "on conflict (strategy_id, provider, model_key) do nothing;", 1
    )[0]
    for model_key, engine in ENGINES.items():
        row = rows.split(f"'viral_rebuild', 'fal',\n  '{model_key}',", 1)[1].split("'\n)", 1)[0]
        assert f"'usd_minor_per_second', {engine['rate']}," in row
        assert f"\n  {engine['window'][0]}, {engine['window'][1]}, " in row
        assert "'operator_choice', 'regenerate'," in row
        assert ("true, true, now()," if engine["recommended"] else "false, true, now(),") in row
    assert "generation_strategy_executable_route_exists(\n    'viral_rebuild'\n  )" in MIGRATION_SOURCE
    assert "rebuild_rows <> 4 or enabled_rows <> 4" in MIGRATION_SOURCE


def test_request_bodies_match_the_fal_openapi_schemas() -> None:
    bodies = _bodies(duration=10, ratio="720:1280", reference_count=6, styles=2)
    for model_key, body in bodies.items():
        assert "error" not in body, (model_key, body)
        assert body["provider"] == "fal"
        assert body["endpointPath"] == model_key
        assert body["pollKind"] == "fal_request"

    minimax = bodies["minimax/h3/reference-to-video"]["body"]
    assert sorted(minimax) == [
        "aspect_ratio", "duration", "enable_prompt_expansion", "prompt",
        "reference_image_urls", "resolution",
    ]
    assert len(minimax["reference_image_urls"]) == 5
    assert minimax["duration"] == 10 and minimax["resolution"] == "768P"
    assert minimax["aspect_ratio"] == "9:16"
    assert minimax["enable_prompt_expansion"] is False
    assert "Image 1, Image 2, Image 3, Image 4 and Image 5" in minimax["prompt"]

    grok = bodies["xai/grok-imagine-video/reference-to-video"]["body"]
    assert sorted(grok) == ["aspect_ratio", "duration", "prompt", "reference_image_urls", "resolution"]
    assert grok["duration"] == 10 and grok["resolution"] == "720p"
    assert "@Image1, @Image2, @Image3, @Image4 and @Image5" in grok["prompt"]

    horse = bodies["alibaba/happy-horse/reference-to-video"]["body"]
    assert sorted(horse) == ["aspect_ratio", "duration", "image_urls", "prompt", "resolution"]
    assert horse["duration"] == 10 and horse["resolution"] == "720p"
    assert "character1, character2, character3, character4 and character5" in horse["prompt"]

    seedance = bodies["bytedance/seedance-2.5/reference-to-video"]["body"]
    assert sorted(seedance) == [
        "aspect_ratio", "bitrate_mode", "duration", "generate_audio",
        "image_urls", "prompt", "resolution",
    ]
    assert seedance["duration"] == "10" and seedance["generate_audio"] is False
    assert len(seedance["image_urls"]) == 6
    assert "video_urls" not in seedance

    for model_key in ENGINES:
        body = bodies[model_key]["body"]
        images = body.get("image_urls") or body.get("reference_image_urls")
        # Главное фото первое, стилевые референсы в список не попадают.
        assert images[0].endswith("front.jpg?token=opaque")
        assert not any("style-" in uri for uri in images)
        assert "ROASTER-1" in body["prompt"]
        assert "grill opens in one motion" in body["prompt"]
        assert body["prompt"].startswith("Create a product advertising video")


def test_ratio_maps_to_aspect_and_source_video_is_refused() -> None:
    square = _bodies(duration=8, ratio="960:960", reference_count=1)
    for model_key in ENGINES:
        assert square[model_key]["body"]["aspect_ratio"] == "1:1", model_key
    portrait_3_4 = _bodies(duration=8, ratio="834:1112", reference_count=1)
    assert portrait_3_4["minimax/h3/reference-to-video"]["body"]["aspect_ratio"] == "3:4"
    # Grok не делает длиннее 10 с, MiniMax — короче 5.
    long = _bodies(duration=12, ratio="720:1280", reference_count=1)
    assert long["xai/grok-imagine-video/reference-to-video"] == {
        "error": "generation_recipe_adapter:duration_invalid",
    }
    assert "error" not in long["minimax/h3/reference-to-video"]
    short = _bodies(duration=4, ratio="720:1280", reference_count=1)
    assert short["minimax/h3/reference-to-video"] == {
        "error": "generation_recipe_adapter:duration_invalid",
    }
    assert "error" not in short["xai/grok-imagine-video/reference-to-video"]
    refused = _evaluate(
        """
        (() => {
          const signed = (role, name) => ({ role, uri: `https://p.supabase.co/storage/v1/object/sign/private/${name}?token=x` });
          const selection = {
            strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
            strategyId: "viral_rebuild", recipe: "product_ad",
            recipeVersion: subject.RUNWAY_RECIPE_VERSION, durationSeconds: 8, audio: false,
            ratio: "720:1280", productInfo: "Product: X. SKU: X-1.", userConcept: "Some concept.",
          };
          try {
            subject.buildFalRecipeRequest(selection, [
              signed("source_video", "viral.mp4"), signed("product_primary", "f.jpg"),
            ], "minimax/h3/reference-to-video");
            return { ok: true };
          } catch (error) { return { ok: false, code: String(error.message) }; }
        })()
        """
    )
    assert refused["ok"] is False


def test_edge_builds_fal_product_ad_and_the_form_filters_ratios_by_engine():
    builder = EDGE_SOURCE.split("export function buildGenerationStrategyProviderRequest", 1)[1]
    builder = builder.split("function buildProviderRequest(", 1)[0]
    assert 'routeProvider === "fal" && context.recipe === "product_ad"' in builder
    product_ad = builder.split('context.recipe === "product_ad"', 1)[1].split(
        'if (context.recipe === "product_ugc") return null;', 1
    )[0]
    assert "ratio: context.ratio," in product_ad
    assert "buildFalRecipeRequest(" in product_ad
    assert "function strategyEngineResolutions(form, strategyId)" in GUIDED_SOURCE
    assert "row.output_rules.resolution_by_ratio?.[value]" in GUIDED_SOURCE
    assert 'control?.name === "generation_intake_engine"' in GUIDED_SOURCE
    assert "function rebuildEngineFacts(form, state)" in INTAKE_SOURCE
    assert "strategyId === STRATEGY_AUTHORITY_STRATEGY" in INTAKE_SOURCE


def test_advisor_ranks_rebuild_engines_by_photos_duration_and_price() -> None:
    advisor = ADVISOR.read_text(encoding="utf-8")
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required")
    routes = []
    for model_key, engine in ENGINES.items():
        routes.append({
            "id": f"fal:{model_key}", "label": model_key, "tier": "premium" if engine["rate"] > 40 else "cheap",
            "priceKind": "usd_minor_per_second", "priceRateMinor": engine["rate"],
            "minDurationSeconds": engine["window"][0], "maxDurationSeconds": engine["window"][1],
            "durationSource": "operator_choice", "engineFamily": "regenerate",
            "inputProfile": {"video": {"min_seconds": engine["window"][0], "max_seconds": engine["window"][1], "min_short_side_px": None, "max_long_side_px": None}, "images": {"max": 5, "style": "at_refs"}, "keeps_source_audio": False},
            "recommended": engine["recommended"], "enabled": True,
        })
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        (directory / ADVISOR.name).write_text(advisor, encoding="utf-8")
        (directory / "run.js").write_text(
            "import { adviseGenerationEngine } from './generation-engine-advisor.js';\n"
            f"const routes = {json.dumps(routes)};\n"
            "const out = {\n"
            "  twelve: adviseGenerationEngine({ routes, facts: { requestedDurationSeconds: 12, productImageCount: 3, productCategory: 'household', brief: '' } }),\n"
            "  eight: adviseGenerationEngine({ routes, facts: { requestedDurationSeconds: 8, productImageCount: 1, productCategory: 'cosmetics', brief: '' } }),\n"
            "};\n"
            "process.stdout.write(JSON.stringify(out));\n",
            encoding="utf-8",
        )
        completed = subprocess.run([node, "run.js"], cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert completed.returncode == 0, completed.stderr
    out = json.loads(completed.stdout)
    # 12 с: Grok отсеян (до 10 с), дешевле всех MiniMax.
    assert out["twelve"]["engineId"] == "fal:minimax/h3/reference-to-video"
    assert {item["engineId"] for item in out["twelve"]["excluded"]} == {
        "fal:xai/grok-imagine-video/reference-to-video",
    }
    assert any("с нуля" in reason for reason in out["twelve"]["reasons"])
    assert "$0.72" in " ".join(out["twelve"]["reasons"])
    # 8 с: все подходят, MiniMax дешевле Grok (6¢ против 8¢).
    assert out["eight"]["engineId"] == "fal:minimax/h3/reference-to-video"
    assert out["eight"]["excluded"] == []
    assert out["eight"]["alternatives"][0]["engineId"] == "fal:xai/grok-imagine-video/reference-to-video"


def test_kling_image_to_video_joins_rebuild_with_start_frame_style() -> None:
    """Пятый движок «Создания» (26.08.2026): Kling O3 Standard image-to-video —
    «фото → видео» со стартовым кадром. Одно фото, в указании оно зовётся
    «the start frame» (@-ссылок нет), длительность 3–15 задаёт оператор,
    звук управляется generate_audio и меняет цену провайдера."""
    catalog = (ROOT / "supabase/functions/_shared/generation-strategy-catalog.js").read_text(
        encoding="utf-8"
    )
    assert 'FAL_KLING_O3_STANDARD_I2V_MODEL =\n  "fal-ai/kling-video/o3/standard/image-to-video"' in catalog
    assert '[FAL_KLING_O3_STANDARD_I2V_MODEL]: "kling_image_regenerate"' in catalog
    assert "kling_image_regenerate: 1," in catalog
    assert 'kling_image_regenerate: "start_frame",' in catalog

    adapters = (ROOT / "supabase/functions/_shared/generation-recipe-adapters.js").read_text(
        encoding="utf-8"
    )
    assert 'if (style === "start_frame") return "the start frame";' in adapters
    builder = adapters.split("function buildFalKlingProductAd", 1)[1].split("\nfunction ", 1)[0]
    assert "image_url: images[0]," in builder
    assert "productAdDuration(selection, 3, 15)" in builder
    assert "generate_audio: selection.audio === true," in builder
    assert '"aspect_ratio"' not in builder
    switch = adapters.split("function buildFalProductAdBody", 1)[1].split("\nfunction ", 1)[0]
    assert 'case "kling_image_regenerate":' in switch


def test_engine_advisor_gives_correct_rebuild_recommendations() -> None:
    """Живой контракт советчика ИИ-центра для «Создания» (26.08.2026): на пяти
    боевых маршрутах реестра совет разумен — много фото и длинный ролик ведут
    к дешёвому мульти-фото MiniMax, одно фото — к Kling image-to-video
    («стартовый кадр»), а движки вне окна длительности исключаются с
    названной причиной, не молча."""
    import json
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("Node.js is required")
    advisor = (ROOT / "web/app/generation-engine-advisor.js").read_text(encoding="utf-8")
    harness = """
import { adviseGenerationEngine } from "./advisor.mjs";
const routes = [
  { id: "fal:minimax", label: "MiniMax", enabled: true, recommended: true, tier: "cheap", priceKind: "usd_minor_per_second", priceRateMinor: 6, minDurationSeconds: 5, maxDurationSeconds: 15, durationSource: "operator_choice", engineFamily: "regenerate", inputProfile: { video: { max_seconds: 15, min_seconds: 5, max_long_side_px: null, min_short_side_px: null }, images: { max: 5, style: "named_refs" }, keeps_source_audio: false } },
  { id: "fal:grok", label: "Grok", enabled: true, recommended: false, tier: "cheap", priceKind: "usd_minor_per_second", priceRateMinor: 8, minDurationSeconds: 4, maxDurationSeconds: 10, durationSource: "operator_choice", engineFamily: "regenerate", inputProfile: { video: { max_seconds: 10, min_seconds: 1, max_long_side_px: null, min_short_side_px: null }, images: { max: 5, style: "at_refs" }, keeps_source_audio: false } },
  { id: "fal:kling-i2v", label: "Kling i2v", enabled: true, recommended: false, tier: "cheap", priceKind: "usd_minor_per_second", priceRateMinor: 12, minDurationSeconds: 4, maxDurationSeconds: 15, durationSource: "operator_choice", engineFamily: "regenerate", inputProfile: { video: { max_seconds: 15, min_seconds: 3, max_long_side_px: null, min_short_side_px: null }, images: { max: 1, style: "start_frame" }, keeps_source_audio: false } },
  { id: "fal:happy", label: "Happy Horse", enabled: true, recommended: false, tier: "medium", priceKind: "usd_minor_per_second", priceRateMinor: 14, minDurationSeconds: 4, maxDurationSeconds: 15, durationSource: "operator_choice", engineFamily: "regenerate", inputProfile: { video: { max_seconds: 15, min_seconds: 3, max_long_side_px: null, min_short_side_px: null }, images: { max: 5, style: "at_refs" }, keeps_source_audio: false } },
  { id: "fal:seedance", label: "Seedance", enabled: true, recommended: false, tier: "premium", priceKind: "usd_minor_per_second", priceRateMinor: 48, minDurationSeconds: 4, maxDurationSeconds: 15, durationSource: "operator_choice", engineFamily: "regenerate", inputProfile: { video: { max_seconds: 30, min_seconds: 4, max_long_side_px: null, min_short_side_px: null }, images: { max: 6, style: "at_refs" }, keeps_source_audio: false } },
];
const many = adviseGenerationEngine({ routes, facts: { sourceDurationSeconds: null, requestedDurationSeconds: 15, sourceShortSidePx: null, productImageCount: 5, productCategory: "apparel", brief: "Продающий ролик о рюкзаке, показать вместительность.", budgetMinorPerRun: null } });
const single = adviseGenerationEngine({ routes, facts: { sourceDurationSeconds: null, requestedDurationSeconds: 10, sourceShortSidePx: null, productImageCount: 1, productCategory: "apparel", brief: "Короткий ролик о сумке.", budgetMinorPerRun: null } });
process.stdout.write(JSON.stringify({
  many: many?.engineId,
  single: single?.engineId,
  manyExcludedGrok: (many?.excluded || []).find((e) => e.engineId === "fal:grok")?.reason || "",
}));
"""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        (d / "advisor.mjs").write_text(advisor, encoding="utf-8")
        (d / "run.mjs").write_text(harness, encoding="utf-8")
        completed = subprocess.run(
            [node, "run.mjs"], cwd=d, capture_output=True, text=True,
            encoding="utf-8", timeout=15, check=False,
        )
    assert completed.returncode == 0, completed.stderr
    verdict = json.loads(completed.stdout)
    assert verdict["many"] == "fal:minimax"
    assert verdict["single"] == "fal:kling-i2v"
    assert "4–10" in verdict["manyExcludedGrok"]


def test_edge_input_profile_styles_mirror_sql_validator() -> None:
    """Боевой урок 26.08: стиль start_frame попал в SQL-валидатор и в реестр,
    а edge-валидатор каталога о нём не знал — строка Kling i2v валила проверку
    ВСЕЙ политики, strategy_catalog отвечал 503, и все три формы показывали
    «каталог движков не загрузился». Списки стилей обязаны совпадать буквально,
    и связка «start_frame ⇔ ровно одно фото» обязана жить в обоих слоях."""
    edge = EDGE_SOURCE
    block = edge.split("function generationStrategyRouteInputProfileValid", 1)[1]
    block = block.split("\nfunction ", 1)[0]
    assert '"start_frame"' in block
    assert '(images.style === "start_frame" && (images.max as number) !== 1)' in block
    migration = (
        ROOT / "supabase/migrations/202608260001_input_profile_start_frame_v1.sql"
    ).read_text(encoding="utf-8")
    sql_styles = re.search(
        r"in \(([^)]*)\)", migration.split("'style'", 1)[1]
    ).group(1)
    edge_styles = re.search(r"!\[([^\]]*)\]\.includes", block).group(1)
    assert (
        sorted(re.findall(r"'([a-z_]+)'", sql_styles))
        == sorted(re.findall(r'"([a-z_]+)"', edge_styles))
    )
