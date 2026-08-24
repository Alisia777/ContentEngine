from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
AUTOPILOT = (ROOT / "web/app/generation-autopilot.js").read_text(
    encoding="utf-8"
)
HANDOFF = (ROOT / "web/app/content-generation-handoff.js").read_text(
    encoding="utf-8"
)
VIEW = (ROOT / "web/app/product-research-view.js").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-product-research/index.ts"
).read_text(encoding="utf-8")


def _run_contract(body: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable mode contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "autopilot.mjs").write_text(
            AUTOPILOT,
            encoding="utf-8",
        )
        (directory / "handoff.mjs").write_text(
            HANDOFF,
            encoding="utf-8",
        )
        (directory / "view.mjs").write_text(
            VIEW,
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as autopilot from './autopilot.mjs';\n"
            "import * as handoffSubject from './handoff.mjs';\n"
            "import * as view from './view.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_research_mode_recommendation_survives_to_generation_handoff() -> None:
    result = _run_contract(
        """
        const raw = {
          run: { id: "run-mode", status: "completed" },
          latest_draft: {
            id: "draft-mode",
            brief: {
              creative_potential: {
                score: 78,
                confidence_label: "medium",
                recommended_scenario_position: 1,
                recommended_scenario_reason:
                  "Точный товар виден целиком, а статичный тест проще проверить",
              },
              scenarios: [0, 1, 2].map((index) => ({
                title: `Сценарий ${index + 1}`,
                platform: index === 0 ? "Wildberries" : "YouTube Shorts",
                recommended_generation_mode:
                  index === 0
                    ? "real_photo"
                    : index === 1
                      ? "real_gen4"
                      : "real_seedance",
                generation_mode_reason:
                  index === 0
                    ? "Замысел раскрывается одним статичным товарным кадром"
                    : index === 1
                      ? "Товарный ролик строится без обязательной речи"
                      : "В кадре нужен человек и короткая слышимая реплика",
                hook: index === 0
                  ? "Товар сразу выделяется на светлом фоне"
                  : "Товар сразу в кадре",
                spoken_script:
                  index < 2
                    ? ""
                    : "Показываю точный товар и упаковку крупным планом.",
                shot_list: index === 0
                  ? [
                    {
                      seconds: "один кадр",
                      visual: "Товар целиком по центру",
                      voiceover: "без голоса",
                      on_screen_text: "без текста",
                    },
                    {
                      seconds: "один кадр",
                      visual: "Мягкий боковой свет подчёркивает упаковку",
                      voiceover: "без голоса",
                      on_screen_text: "без текста",
                    },
                    {
                      seconds: "один кадр",
                      visual: "Светлый минималистичный фон",
                      voiceover: "без голоса",
                      on_screen_text: "без текста",
                    },
                  ]
                  : [{ visual: "Товар крупно" }],
              })),
            },
          },
        };
        const normalized = view.normalizeProductResearch(raw);
        const record = {
          ...normalized,
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          productName: "Точный товар",
          sku: "SKU-MODE-1",
          sourceIds: ["source-1"],
          stageCorrections: {
            ...normalized.stageCorrections,
            strategy: "Начать с ограниченного теста статичного сценария",
          },
          brief: {
            ...normalized.brief,
            proofPoints: ["Факт подтверждён упаковкой"],
            avoidClaims: ["Не обещать результат"],
          },
        };
        const handoff = handoffSubject.createContentGenerationHandoff(
          record,
          0,
          1000,
        );
        const compiled = handoffSubject.compileContentGenerationPrompt(
          handoff,
          "real_photo",
        );
        return {
          normalizedMode: normalized.scenarios[0].generationMode,
          normalizedReason: normalized.scenarios[0].generationModeReason,
          handoffMode: handoff.scenario.recommendedGenerationMode,
          handoffReason: handoff.scenario.generationModeReason,
          promptReady: compiled.ready,
          promptWarnings: compiled.warnings.map((item) => item.code),
          photoPrompt: compiled.prompt.includes(
            "Создай одно квадратное товарное фото 2048 × 2048",
          ),
          scenarioComposition: compiled.prompt.includes(
            "Мягкий боковой свет подчёркивает упаковку",
          ),
          strippedMetadata: !compiled.prompt.includes("Голос:")
            && !compiled.prompt.includes("Текст:"),
          normalizedPlatform: normalized.scenarios[0].platform,
          recommendedPosition: normalized.recommendedScenarioPosition,
          recommendedIndex: normalized.recommendedScenarioIndex,
          recommendationVisible:
            view.productResearchResultMarkup(record).includes(
              "Лучший первый эксперимент — сценарий 1",
            ),
          serializedReady: Boolean(
            handoffSubject.parseContentGenerationHandoff(
              JSON.stringify(handoff),
              1001,
            ),
          ),
        };
        """
    )
    assert result == {
        "normalizedMode": "real_photo",
        "normalizedReason": (
            "Замысел раскрывается одним статичным товарным кадром"
        ),
        "handoffMode": "real_photo",
        "handoffReason": (
            "Замысел раскрывается одним статичным товарным кадром"
        ),
        "promptReady": True,
        "promptWarnings": [],
        "photoPrompt": True,
        "scenarioComposition": True,
        "strippedMetadata": True,
        "normalizedPlatform": "wildberries",
        "recommendedPosition": 1,
        "recommendedIndex": 0,
        "recommendationVisible": True,
        "serializedReady": True,
    }


def test_mode_autopilot_honors_research_and_provider_duration_constraints() -> None:
    result = _run_contract(
        """
        const available = {
          real_photo: true,
          real_gen4: true,
          real_seedance: true,
        };
        const resolve = (recommendedGenerationMode, spokenScript) =>
          autopilot.resolveHandoffGenerationMode({
            handoff: {
              scenario: {
                recommendedGenerationMode,
                generationModeReason: "Проверенная причина выбора режима",
                spokenScript,
              },
            },
            availability: available,
            mockEnabled: true,
          });
        return {
          explicitPhoto: resolve(
            "real_photo",
            "",
          ),
          explicitSilent: resolve(
            "real_gen4",
            "Короткая реплика существует, но для замысла не обязательна.",
          ),
          explicitUgc: resolve(
            "real_seedance",
            "Показываю точный товар крупно и спокойно возвращаю его в центр.",
          ),
          legacyShort: resolve(
            "",
            "Показываю точный товар крупно.",
          ),
          overlong: resolve(
            "real_seedance",
            Array.from(
              { length: 30 },
              (_, index) => `слово${index + 1}`,
            ).join(" "),
          ),
        };
        """
    )
    assert result["explicitPhoto"]["value"] == "real_photo"
    assert result["explicitPhoto"]["source"] == "research_recommendation"
    assert result["explicitSilent"]["value"] == "real_gen4"
    assert result["explicitSilent"]["source"] == "research_recommendation"
    assert result["explicitUgc"]["value"] == "real_seedance"
    assert result["explicitUgc"]["spokenWords"] == 10
    assert result["legacyShort"]["value"] == "real_seedance"
    assert result["legacyShort"]["source"] == "provider_constraint"
    assert result["overlong"]["value"] == "real_gen4"
    assert result["overlong"]["source"] == "duration_constraint"
    assert "30 слов" in result["overlong"]["reason"]
    assert all(
        item["automatic"] is True and item["blocked"] is False
        for item in result.values()
    )


def test_research_view_exposes_duration_fallback_before_handoff() -> None:
    result = _run_contract(
        """
        const normalized = view.normalizeProductResearch({
          latest_draft: {
            brief: {
              scenarios: [0, 1, 2].map((index) => ({
                title: `Сценарий ${index + 1}`,
                platform: "VK Клипы",
                recommended_generation_mode: "real_seedance",
                generation_mode_reason: "В кадре запланирован человек",
                hook: "Проверяем товар",
                spoken_script: Array.from(
                  { length: index === 0 ? 30 : 10 },
                  (_, word) => `слово${word + 1}`,
                ).join(" "),
                shot_list: [{ visual: "Товар" }],
              })),
            },
          },
        });
        return {
          firstMode: normalized.scenarios[0].generationMode,
          firstReason: normalized.scenarios[0].generationModeReason,
          secondMode: normalized.scenarios[1].generationMode,
        };
        """
    )
    assert result["firstMode"] == "real_gen4"
    assert "30 слов" in result["firstReason"]
    assert result["secondMode"] == "real_seedance"


def test_unavailable_recommended_sku_falls_back_to_dry_run_not_paid_guess() -> None:
    result = _run_contract(
        """
        const resolve = (recommendedGenerationMode, spokenScript) =>
          autopilot.resolveHandoffGenerationMode({
            handoff: {
              scenario: {
                recommendedGenerationMode,
                spokenScript,
              },
            },
            availability: {
              real_photo: false,
              real_gen4: true,
              real_seedance: false,
            },
            mockEnabled: true,
          });
        return {
          photo: resolve("real_photo", ""),
          seedance: resolve(
            "real_seedance",
            "Показываю товар рядом с лицом.",
          ),
        };
        """
    )
    assert result["photo"]["value"] == "mock"
    assert result["photo"]["recommendedMode"] == "real_photo"
    assert result["seedance"]["value"] == "mock"
    assert result["seedance"]["recommendedMode"] == "real_seedance"
    assert all(
        item["automatic"] is False and item["blocked"] is True
        for item in result.values()
    )


def test_research_edge_returns_only_server_validated_generation_modes() -> None:
    for token in (
        "recommended_generation_mode: {",
        'enum: ["real_photo", "real_gen4", "real_seedance"]',
        "generation_mode_reason: {",
        '"recommended_generation_mode",',
        '"generation_mode_reason",',
        'new Set(["real_photo", "real_gen4", "real_seedance"]).has(',
        "Для каждого сценария выбери recommended_generation_mode",
        "real_photo — одно квадратное статичное товарное фото",
        'enum: ["instagram", "youtube", "vk", "wildberries", "ozon"]',
        "const normalizedPlatforms = new Set(",
        "!normalizedPlatforms.has(",
        "claim.run.platforms,",
        "Для real_seedance spoken_script должен содержать 1–22 слова",
        "Для real_photo и real_gen4 верни spoken_script как пустую строку",
        'scenario.recommended_generation_mode === "real_seedance"',
        'scenario.recommended_generation_mode === "real_photo"',
        "countWords(scenario.spoken_script) > 22",
        'shot.seconds !== "один кадр"',
        'shot.seconds !== "0–5 секунд"',
        'shot.on_screen_text !== "без текста"',
        "hasSameWordSequence(",
        '"recommended_scenario_position",',
        '"recommended_scenario_reason",',
        "recommended_scenario_position: {",
        "лучший первый безопасный эксперимент",
        "scenarioIndex + 1 === recommendedScenarioPosition ? 4 : 3",
        "`Режим генерации: ${",
    ):
        assert token in EDGE


def test_portal_uses_recommendation_without_confirming_spend_for_user() -> None:
    for token in (
        "resolveHandoffGenerationMode({",
        "[REAL_PHOTO_MODE]: photoSpendAllowed",
        "[REAL_GEN4_MODE]: gen4SpendAllowed",
        "[REAL_SEEDANCE_MODE]: seedanceSpendAllowed",
            "const defaultMode = repairReady",
            ": handoff",
        "? handoffModeResolution.value",
        "Режим выбран автоматически",
        "квадратное товарное фото · Seedream",
        "Стоимость и права всё равно подтверждаются отдельно",
        'name="real_spend_confirmation"',
        "scenario.generation_mode === REAL_SEEDANCE_MODE",
        "|| !scenario.shot_list",
        "Композиция одного статичного квадратного фото:",
        "Без речи, дикторского текста и сгенерированных надписей.",
        "prepareRecommendedResearchHandoff(research.record)",
        'setValue("format", realGenerationSku(handoffMode)?.format || "9:16")',
    ):
        assert token in APP
    assert "Оплата и рендер не запускались" in VIEW
    confirmation = APP[
        APP.index('name="real_spend_confirmation"') :
        APP.index('name="real_spend_confirmation"') + 320
    ]
    assert "checked" not in confirmation
    assert "required" in confirmation
    assert 'from "./product-research-view.js?v=20260823.copy-engines.58"' in APP
    assert (
        'from "./content-generation-handoff.js?v=20260823.copy-engines.58"'
        in APP
    )
    assert 'from "./generation-autopilot.js?v=20260814.os4.41"' in APP
    assert './app.js?v=20260823.copy-engines.58' in INDEX
