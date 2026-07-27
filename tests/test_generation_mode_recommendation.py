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
              scenarios: [0, 1, 2].map((index) => ({
                title: `Сценарий ${index + 1}`,
                platform: "YouTube Shorts",
                recommended_generation_mode:
                  index === 0 ? "real_gen4" : "real_seedance",
                generation_mode_reason:
                  index === 0
                    ? "Товарный кадр строится без обязательной речи"
                    : "В кадре нужен человек и короткая слышимая реплика",
                hook: "Товар сразу в кадре",
                spoken_script:
                  index === 0
                    ? ""
                    : "Показываю точный товар и упаковку крупным планом.",
                shot_list: [{ visual: "Товар крупно" }],
              })),
            },
          },
        };
        const normalized = view.normalizeProductResearch(raw);
        const record = {
          ...normalized,
          approved: true,
          productName: "Точный товар",
          sku: "SKU-MODE-1",
          sourceIds: ["source-1"],
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
          "real_gen4",
        );
        return {
          normalizedMode: normalized.scenarios[0].generationMode,
          normalizedReason: normalized.scenarios[0].generationModeReason,
          handoffMode: handoff.scenario.recommendedGenerationMode,
          handoffReason: handoff.scenario.generationModeReason,
          promptReady: compiled.ready,
          promptWarnings: compiled.warnings.map((item) => item.code),
          silentPrompt: compiled.prompt.includes(
            "Без речи, дикторского текста и сгенерированных надписей",
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
        "normalizedMode": "real_gen4",
        "normalizedReason": (
            "Товарный кадр строится без обязательной речи"
        ),
        "handoffMode": "real_gen4",
        "handoffReason": (
            "Товарный кадр строится без обязательной речи"
        ),
        "promptReady": True,
        "promptWarnings": [],
        "silentPrompt": True,
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
        return autopilot.resolveHandoffGenerationMode({
          handoff: {
            scenario: {
              recommendedGenerationMode: "real_seedance",
              spokenScript: "Показываю товар рядом с лицом.",
            },
          },
          availability: {
            real_photo: true,
            real_gen4: true,
            real_seedance: false,
          },
          mockEnabled: true,
        });
        """
    )
    assert result["value"] == "mock"
    assert result["recommendedMode"] == "real_seedance"
    assert result["automatic"] is False
    assert result["blocked"] is True


def test_research_edge_returns_only_server_validated_generation_modes() -> None:
    for token in (
        "recommended_generation_mode: {",
        'enum: ["real_gen4", "real_seedance"]',
        "generation_mode_reason: {",
        '"recommended_generation_mode",',
        '"generation_mode_reason",',
        'new Set(["real_gen4", "real_seedance"]).has(',
        "Для каждого сценария выбери recommended_generation_mode",
        "Для real_seedance spoken_script должен содержать не более 22 слов",
        'Для real_gen4 верни spoken_script как пустую строку',
        'scenario.recommended_generation_mode === "real_gen4"',
        "`Режим генерации: ${",
    ):
        assert token in EDGE


def test_portal_uses_recommendation_without_confirming_spend_for_user() -> None:
    for token in (
        "resolveHandoffGenerationMode({",
        "[REAL_GEN4_MODE]: gen4SpendAllowed",
        "[REAL_SEEDANCE_MODE]: seedanceSpendAllowed",
            "const defaultMode = repairReady",
            ": handoff",
        "? handoffModeResolution.value",
        "Режим выбран автоматически",
        "Стоимость и права всё равно подтверждаются отдельно",
        'name="real_spend_confirmation"',
        "scenario.generation_mode !== REAL_GEN4_MODE",
        "Без речи, дикторского текста и сгенерированных надписей.",
    ):
        assert token in APP
    confirmation = APP[
        APP.index('name="real_spend_confirmation"') :
        APP.index('name="real_spend_confirmation"') + 320
    ]
    assert "checked" not in confirmation
    assert "required" in confirmation
    assert (
        'from "./product-research-view.js?v=20260726.2"'
        in APP
    )
    assert (
        'from "./content-generation-handoff.js?v=20260726.7"'
        in APP
    )
    assert 'from "./generation-autopilot.js?v=20260726.3"' in APP
    assert './app.js?v=20260727.16' in INDEX
