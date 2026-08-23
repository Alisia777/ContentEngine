from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/content-generation-handoff.js"
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/product-research-view.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _run_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable handoff contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            MODULE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
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


def test_approved_research_scenario_compiles_to_generation_ready_seedance_prompt() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-1",
          draftId: "draft-1",
          productName: "Bombbar Протеиновый батончик Фисташка",
          sku: "BB-PISTACHIO-60",
          sourceIds: ["source-1"],
          brief: {
            keyMessage: "Удобный перекус в дороге",
            proofPoints: "20 г белка\\nТочная масса указана на упаковке",
            avoidClaims: "лечит\\nгарантирует похудение",
            visualDirection: "Домашний свет, естественная подача",
            cta: "Проверьте карточку товара",
          },
          scenarios: [{
            title: "Перекус после тренировки",
            platform: "Instagram Reels",
            hook: "Что взять с собой после тренировки?",
            script: "После тренировки беру этот батончик с собой — удобно открыть и съесть по дороге.",
            shotList: "Блогер показывает упаковку крупно\\nОткрывает батончик и показывает продукт\\nВозвращает упаковку в центр кадра",
            taskTitle: "Снять UGC после тренировки",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const compiled = subject.compileContentGenerationPrompt(handoff, "real_seedance");
        return {
          ready: compiled.ready,
          duration: compiled.durationSeconds,
          spokenWords: compiled.spokenWords,
          bounded: compiled.prompt.length <= subject.CONTENT_GENERATION_PROMPT_LIMIT,
          exactProduct: compiled.prompt.includes(record.productName),
          exactSpeech: compiled.prompt.includes(`Реплика героя дословно: «${record.scenarios[0].script}»`),
          productLock: compiled.prompt.includes("Сохрани форму, цвет, упаковку, этикетку и пропорции"),
          noUnboundCategoryRule: !compiled.prompt.includes("ResearchCategoryRule/"),
          platform: handoff.scenario.platform,
          position: handoff.scenario.position,
        };
        """
    )
    assert result == {
        "ready": True,
        "duration": 8,
        "spokenWords": 13,
        "bounded": True,
        "exactProduct": True,
        "exactSpeech": True,
        "productLock": True,
        "noUnboundCategoryRule": True,
        "platform": "instagram",
        "position": 1,
    }


def test_compiler_respects_each_provider_prompt_limit_without_limiting_human_idea() -> None:
    result = _run_module(
        """
        const common = {
          productName: "Точный товар",
          sku: "SKU-1",
          scenarioIntent: "Показать товар естественно. ".repeat(80),
          visualDirection: "Мягкий свет. ".repeat(80),
          avoidClaims: ["неподтверждённое обещание"],
          productCategory: "household",
        };
        const gen4 = subject.compileSafeGenerationBrief({ ...common, mode: "real_gen4", durationSeconds: 10 });
        const seedance = subject.compileSafeGenerationBrief({ ...common, mode: "real_seedance", durationSeconds: 15 });
        return {
          gen4Ready: gen4.ready,
          gen4Length: gen4.prompt.length,
          gen4Limit: subject.contentGenerationPromptLimit("real_gen4"),
          seedanceReady: seedance.ready,
          seedanceLength: seedance.prompt.length,
          seedanceLimit: subject.contentGenerationPromptLimit("real_seedance"),
        };
        """
    )
    assert result["gen4Ready"] is True
    assert result["gen4Length"] <= result["gen4Limit"] == 1_000
    assert result["seedanceReady"] is True
    assert result["seedanceLength"] <= result["seedanceLimit"] == 1_200


def test_new_models_compile_exact_duration_and_public_ratio_without_legacy_rounding() -> None:
    result = _run_module(
        r'''
        const common = {
          productName: "Точный товар",
          sku: "SKU-EXACT",
          scenarioIntent: "Герой показывает товар. Реплика: «Показываю точный товар без лишних обещаний». ",
          productCategory: "other",
        };
        const fixtures = [
          ["runway", "gen4.5", "real_gen4", 3, "16:9", false],
          ["runway", "seedance2_mini", "real_seedance", 6, "21:9", true],
          ["runway", "veo3.1_fast", "real_gen4", 4, "16:9", false],
          ["runway", "veo3.1_fast", "real_seedance", 8, "9:16", true],
          ["runway", "gemini_omni_flash", "real_seedance", 3, "16:9", true],
          ["google", "veo-3.1-lite-generate-preview", "real_seedance", 6, "9:16", true],
        ];
        const rows = fixtures.map(([provider, model, mode, durationSeconds, format, audio]) => {
          const generationSelection = {
            provider, model, format, durationSeconds, audio, promptLimit: 4000,
          };
          const compiled = subject.compileSafeGenerationBrief({
            ...common, mode, durationSeconds, generationSelection,
          });
          const expected = audio
            ? `Создай один непрерывный UGC-ролик длительностью ${durationSeconds} секунд с соотношением сторон ${format}.`
            : `Создай один непрерывный ролик длительностью ${durationSeconds} секунд с соотношением сторон ${format}.`;
          const verticalTamper = compiled.prompt.replace(expected,
            audio
              ? `Создай один непрерывный вертикальный UGC-ролик длительностью ${durationSeconds} секунд.`
              : `Создай один непрерывный вертикальный ролик длительностью ${durationSeconds} секунд.`,
          );
          return {
            provider, model, ready: compiled.ready,
            duration: compiled.durationSeconds,
            firstLine: compiled.prompt.split("\n")[0],
            expected,
            tamperCodes: subject.inspectContentGenerationPrompt(verticalTamper, mode, {
              productName: common.productName,
              productCategory: common.productCategory,
              durationSeconds,
              generationSelection,
            }).blockers.map((entry) => entry.code),
          };
        });
        const legacy = subject.compileSafeGenerationBrief({
          ...common,
          mode: "real_gen4",
          durationSeconds: 5,
          generationSelection: {
            provider: "runway", model: "gen4_turbo", format: "16:9",
            durationSeconds: 5, audio: false, promptLimit: 1000,
          },
        });
        return { rows, legacyFirstLine: legacy.prompt.split("\n")[0] };
        '''
    )
    assert all(row["ready"] for row in result["rows"])
    assert all(row["duration"] in {3, 4, 6, 8} for row in result["rows"])
    assert all(row["firstLine"] == row["expected"] for row in result["rows"])
    assert all(
        {"seedance_output_guard_missing", "gen4_output_guard_missing"}
        & set(row["tamperCodes"])
        for row in result["rows"]
    )
    assert result["legacyFirstLine"] == (
        "Создай один непрерывный вертикальный ролик длительностью 5 секунд."
    )


def test_handoff_carries_human_research_decision_into_required_prompt_guard() -> None:
    result = _run_module(
        """
        const base = {
          approved: true,
          projectId: "11111111-1111-4111-8111-111111111111",
          id: "research-managed",
          draftId: "draft-managed",
          productName: "Точный товар",
          sku: "SKU-MANAGED",
          sourceIds: ["source-1"],
          guidance: { status: "needs_user_decision" },
          stageCorrections: {
            competitors: "Не использовать сравнение с ложным конкурентом https://example.com/raw",
            strategy: "Сначала проверить демонстрацию без сравнения",
          },
          brief: {
            proofPoints: "Факт с упаковки",
            avoidClaims: "Не обещать результат",
          },
          scenarios: [{
            title: "Демонстрация",
            platform: "youtube",
            hook: "Покажем применение",
            script: "Показываю товар в использовании без лишних обещаний.",
            shotList: "Товар крупно\\nДемонстрация применения",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(base, 0, 1000);
        const restored = subject.parseContentGenerationHandoff(
          JSON.stringify(handoff),
          1000,
        );
        const compiled = subject.compileContentGenerationPrompt(
          restored,
          "real_seedance",
        );
        let missingDecisionBlocked = false;
        try {
          subject.createContentGenerationHandoff({
            ...base,
            stageCorrections: {},
          }, 0, 1000);
        } catch (error) {
          missingDecisionBlocked = String(error.message).includes(
            "решение по пробелам",
          );
        }
        return {
          ready: compiled.ready,
          decisionStored: handoff.researchDecision.includes(
            "Сначала проверить демонстрацию без сравнения",
          ),
          decisionRequired: compiled.prompt.includes(
            "Решение пользователя после исследования — имеет приоритет",
          ),
          noRawUrl: !handoff.researchDecision.includes("https://")
            && !compiled.prompt.includes("https://"),
          missingDecisionBlocked,
        };
        """
    )
    assert result == {
        "ready": True,
        "decisionStored": True,
        "decisionRequired": True,
        "noRawUrl": True,
        "missingDecisionBlocked": True,
    }


def test_ozon_research_is_not_silently_relabelled_for_generation() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert 'normalized.includes("ozon")' in source
    assert "платная автогенерация для Ozon пока не подключена" in source
    assert "platform: scenarioPlatform" in source


def test_every_filled_stage_correction_survives_the_bounded_handoff() -> None:
    result = _run_module(
        """
        const long = (prefix) => `${prefix} ${"важная правка ".repeat(80)}`;
        const record = {
          approved: true,
          projectId: "11111111-1111-4111-8111-111111111111",
          id: "research-all-corrections",
          draftId: "draft-all-corrections",
          productName: "Точный товар",
          sku: "SKU-CORRECTIONS",
          sourceIds: ["source-1"],
          guidance: { status: "needs_user_decision" },
          stageCorrections: {
            sources: long("SOURCE-SENTINEL"),
            category: long("CATEGORY-SENTINEL"),
            competitors: long("COMPETITOR-SENTINEL"),
            trends: long("TREND-SENTINEL"),
            strategy: long("STRATEGY-SENTINEL"),
          },
          brief: { proofPoints: "Факт", avoidClaims: "Не обещать" },
          scenarios: [{
            title: "Тест",
            platform: "instagram",
            hook: "Показать товар",
            script: "Показываю точный товар без лишних обещаний.",
            shotList: "Товар крупно\\nПрименение",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        return {
          bounded: handoff.researchDecision.length <= 420
            && handoff.researchDecision.length >= 300,
          hasEveryStage: [
            "SOURCE-SENTINEL",
            "CATEGORY-SENTINEL",
            "COMPETITOR-SENTINEL",
            "TREND-SENTINEL",
            "STRATEGY-SENTINEL",
          ].every((sentinel) => handoff.researchDecision.includes(sentinel)),
          marked: handoff.researchDecision.includes("…"),
        };
        """
    )
    assert result == {"bounded": True, "hasEveryStage": True, "marked": True}


def test_long_seedance_speech_is_blocked_until_operator_shortens_exact_line() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-2",
          draftId: "draft-2",
          productName: "Точный товар",
          sku: "SKU-2",
          sourceIds: ["source-1"],
          brief: { proofPoints: "Подтверждённый факт", avoidClaims: "Не обещать результат" },
          scenarios: [{
            title: "Длинный сценарий",
            platform: "youtube",
            hook: "Проверяем товар",
            script: Array.from({ length: 30 }, (_, index) => `слово${index + 1}`).join(" "),
            shotList: "Показать товар крупно",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 2000);
        const compiled = subject.compileContentGenerationPrompt(handoff, "real_seedance");
        const repaired = compiled.prompt.replace(
          /Реплика героя дословно: «[^»]+»/u,
          "Реплика героя дословно: «Показываю точный товар без лишних обещаний»",
        );
        const inspected = subject.inspectContentGenerationPrompt(repaired, "real_seedance", {
          productName: record.productName,
        });
        return {
          initialReady: compiled.ready,
          initialBlockers: compiled.blockers.map((item) => item.code),
          placeholder: compiled.prompt.includes("[СОКРАТИТЕ РЕПЛИКУ"),
          repairedReady: inspected.ready,
        };
        """
    )
    assert result["initialReady"] is False
    assert "spoken_script_too_long" in result["initialBlockers"]
    assert result["placeholder"] is True
    assert result["repairedReady"] is True


def test_gen4_compiler_keeps_visual_action_and_explicitly_removes_audio() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-3",
          draftId: "draft-3",
          productName: "Точный крем",
          sku: "CREAM-1",
          sourceIds: ["source-1"],
          brief: { proofPoints: "Объём указан на упаковке", avoidClaims: "Не обещать лечение" },
          scenarios: [{
            title: "Текстура",
            platform: "vk",
            hook: "Посмотрите на текстуру",
            script: "Показываю крем крупным планом.",
            shotList: "Медленно приблизить камеру к закрытой упаковке\\nПовернуть банку",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 3000);
        const compiled = subject.compileContentGenerationPrompt(handoff, "real_gen4");
        return {
          ready: compiled.ready,
          duration: compiled.durationSeconds,
          silent: compiled.prompt.includes("Без речи, дикторского текста и сгенерированных надписей"),
          oneAction: compiled.prompt.includes("Медленно приблизить камеру к закрытой упаковке")
            && !compiled.prompt.includes("Повернуть банку"),
          warningCodes: compiled.warnings.map((item) => item.code),
        };
        """
    )
    assert result["ready"] is True
    assert result["duration"] == 5
    assert result["silent"] is True
    assert result["oneAction"] is True
    assert "audio_ignored" in result["warningCodes"]


def test_photo_handoff_compiles_to_square_packshot_without_video_instructions() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-photo",
          draftId: "draft-photo",
          productName: "BOMBBAR PRO",
          sku: "BB-PRO-001",
          sourceIds: ["source-photo"],
          brief: {
            visualDirection: "Светлый минималистичный фон",
            avoidClaims: "лечит\\nгарантирует результат",
          },
          scenarios: [{
            title: "Статичное фото из исследования",
            platform: "wildberries",
            recommendedGenerationMode: "real_photo",
            hook: "Товар сразу выделяется на светлом фоне",
            script: "",
            shotList: "один кадр: Товар целиком по центру. Голос: без голоса. Текст: без текста.\\nодин кадр: Мягкий боковой свет подчёркивает упаковку. Голос: без голоса. Текст: без текста.\\nодин кадр: Светлый минималистичный фон. Голос: без голоса. Текст: без текста.",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 4000);
        const compiled = subject.compileContentGenerationPrompt(handoff, "real_photo");
        return {
          ready: compiled.ready,
          duration: compiled.durationSeconds,
          exactProduct: compiled.prompt.includes("BOMBBAR PRO"),
          square2k: compiled.prompt.includes("квадратное товарное фото 2048 × 2048"),
          exactReference: compiled.prompt.includes("@ProductReference как главный точный референс"),
          tamperedBlockers: subject.inspectContentGenerationPrompt(
            compiled.prompt.replace("@ProductReference", "Figure 1"),
            "real_photo",
            { productName: record.productName },
          ).blockers.map((item) => item.code),
          hasVideoDuration: compiled.prompt.includes("8 секунд"),
          hasSpokenLine: compiled.prompt.includes("Реплика героя дословно"),
          scenarioComposition: compiled.prompt.includes(
            "Мягкий боковой свет подчёркивает упаковку",
          ),
          strippedMetadata: !compiled.prompt.includes("Голос:")
            && !compiled.prompt.includes("Текст:"),
          recommendedMode: handoff.scenario.recommendedGenerationMode,
          blockers: compiled.blockers.map((item) => item.code),
        };
        """
    )
    assert result == {
        "ready": True,
        "duration": 0,
        "exactProduct": True,
        "square2k": True,
        "exactReference": True,
        "tamperedBlockers": ["photo_reference_guard_missing"],
        "hasVideoDuration": False,
        "hasSpokenLine": False,
        "scenarioComposition": True,
        "strippedMetadata": True,
        "recommendedMode": "real_photo",
        "blockers": [],
    }


def test_steamer_prompt_preserves_real_scale_and_replaces_face_interaction() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-steamer",
          draftId: "draft-steamer",
          productName: "Пароварка большая",
          sku: "STEAM-01",
          sourceIds: ["source-steamer"],
          brief: {
            proofPoints: ["Три корзины видны на исходнике"],
            avoidClaims: ["готовит полезнее"],
          },
          scenarios: [{
            title: "Небезопасный общий шаблон",
            platform: "tiktok",
            hook: "Показываю товар",
            script: "Показываю товар в работе и одну проверяемую деталь крупно.",
            shotList: "Герой держит пароварку у лица и приближает к камере",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 5000);
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_seedance",
          null,
          null,
          8,
          "household",
        );
        return {
          ready: compiled.ready,
          countertop: compiled.prompt.includes(
            "товар показан целиком в естественном размере на устойчивой столешнице",
          ),
          safeAction: compiled.prompt.includes(
            "Герой открывает крышку или рабочую часть",
          ),
          irrelevantFaceRule: compiled.prompt.includes("подносить к лицу"),
          copiedUnsafeAction: compiled.prompt.includes(
            "держит пароварку у лица",
          ),
          interactionKind: subject.inferProductInteractionProfile({
            productName: record.productName,
            productCategory: "household",
          }).kind,
        };
        """
    )
    assert result == {
        "ready": True,
        "countertop": True,
        "safeAction": True,
        "irrelevantFaceRule": False,
        "copiedUnsafeAction": False,
        "interactionKind": "countertop_appliance",
    }


def test_steamer_auto_brief_uses_natural_product_specific_spoken_line() -> None:
    result = _run_module(
        """
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "Пароварка большая",
          sku: "STEAM-01",
          durationSeconds: 12,
          productCategory: "household",
        });
        return {
          ready: compiled.ready,
          duration: compiled.durationSeconds,
          spokenLine: compiled.prompt.includes(
            "Реплика героя дословно: «Показываю, как работает пароварка: управление, процесс и готовый результат.»",
          ),
          irrelevantFaceRule: compiled.prompt.includes("подносить к лицу"),
        };
        """
    )
    assert result == {
        "ready": True,
        "duration": 12,
        "spokenLine": True,
        "irrelevantFaceRule": False,
    }


def test_steamer_auto_brief_preserves_human_scenario_under_product_guards() -> None:
    result = _run_module(
        """
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "Пароварка",
          sku: "WWW123",
          durationSeconds: 15,
          productCategory: "household",
          scenarioIntent: [
            "Блогер готовит лосось с брокколи и овощами в пароварке.",
            "Затем не спеша достаёт еду на тарелку и показывает результат.",
            "Пароварка стоит на столе; к камере приближается только тарелка.",
            "Рассказать о готовке без жарки и лишнего масла.",
          ].join(" "),
        });
        return {
          ready: compiled.ready,
          bounded: compiled.prompt.length <= subject.CONTENT_GENERATION_PROMPT_LIMIT,
          keepsDish: compiled.prompt.includes("лосось с брокколи и овощами"),
          keepsPacing: compiled.prompt.includes("не спеша достаёт еду"),
          keepsScaleGuard: compiled.prompt.includes(
            "товар показан целиком в естественном размере на устойчивой столешнице"
          ),
          hasRelevantLine: compiled.prompt.includes(
            "Реплика героя дословно: «Готовлю лосось с овощами на пару: без жарки и лишнего масла, равномерно и удобно.»"
          ),
          noDoublePunctuation: !compiled.prompt.includes("столе.."),
          productLock: compiled.prompt.includes(
            "Сохрани форму, цвет, упаковку, этикетку и пропорции"
          ),
        };
        """
    )
    assert result == {
        "ready": True,
        "bounded": True,
        "keepsDish": True,
        "keepsPacing": True,
        "keepsScaleGuard": True,
        "hasRelevantLine": True,
        "noDoublePunctuation": True,
        "productLock": True,
    }


def test_air_fryer_auto_brief_preserves_exact_quote_before_bounded_intent() -> None:
    result = _run_module(
        """
        const scenarioIntent = [
          "Светлая домашняя кухня.",
          "Блогер кладёт в корзину аэрогриля куриные бёдра и картофель, выбирает режим и показывает приготовление.",
          "Затем спокойно выдвигает корзину, перекладывает готовую курицу с картофелем на тарелку и подносит к камере только тарелку.",
          "Корпус аэрогриля всё время стоит на столе.",
          "Герой говорит: «Курица с картофелем получается румяной, а готовить в аэрогриле удобно — без сковороды и лишнего масла.»",
        ].join(" ");
        const exactSpeech =
          "Курица с картофелем получается румяной, а готовить в аэрогриле удобно — без сковороды и лишнего масла.";
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "Аэрогриль MILIO",
          sku: "WWW123",
          durationSeconds: 15,
          productCategory: "household",
          scenarioIntent,
        });
        return {
          ready: compiled.ready,
          bounded: compiled.prompt.length <= subject.CONTENT_GENERATION_PROMPT_LIMIT,
          exactSpeech: compiled.prompt.includes(
            `Реплика героя дословно: «${exactSpeech}»`,
          ),
          speechOccursOnce: compiled.prompt.split(exactSpeech).length - 1 === 1,
          keepsCompleteAction: compiled.prompt.includes(
            "Корпус аэрогриля всё время стоит на столе.",
          ),
          noMidWordCut: !compiled.prompt.includes("без сковороды и ли."),
          dynamicSpeechLimit:
            compiled.spokenWords <= subject.seedanceSpokenWordLimit(15),
        };
        """
    )
    assert result == {
        "ready": True,
        "bounded": True,
        "exactSpeech": True,
        "speechOccursOnce": True,
        "keepsCompleteAction": True,
        "noMidWordCut": True,
        "dynamicSpeechLimit": True,
    }


def test_categories_have_separate_cold_start_interactions() -> None:
    result = _run_module(
        """
        const categories = [
          "cosmetics",
          "baa",
          "sports_food",
          "food",
          "household",
          "apparel",
          "electronics",
          "other",
        ];
        const profiles = categories.map((productCategory) =>
          subject.inferProductInteractionProfile({
            productName: "Новый товар",
            productCategory,
          })
        );
        return {
          kinds: profiles.map((item) => item.kind),
          uniqueRequirements: new Set(
            profiles.map((item) => item.requirement),
          ).size,
          otherColdStart: profiles.at(-1).kind === "other_cold_start",
          faceTemplateRemoved: profiles.every(
            (item) => !item.videoAction.includes("у лица"),
          ),
        };
        """
    )
    assert result["uniqueRequirements"] == 8
    assert result["otherColdStart"] is True
    assert result["faceTemplateRemoved"] is True
    assert result["kinds"] == [
        "cosmetics",
        "supplement",
        "sports_food",
        "food",
        "household_cold_start",
        "wearable",
        "electronics",
        "other_cold_start",
    ]


def test_safe_autobrief_is_generation_ready_for_each_paid_mode() -> None:
    result = _run_module(
        """
        const modes = ["real_photo", "real_gen4", "real_seedance"];
        return Object.fromEntries(modes.map((mode) => {
          const compiled = subject.compileSafeGenerationBrief({
            mode,
            productName: "Точный тестовый товар",
            sku: "SKU-SAFE-1",
          });
          const inspected = subject.inspectContentGenerationPrompt(compiled.prompt, mode, {
            productName: "Точный тестовый товар",
          });
          return [mode, {
            ready: compiled.ready && inspected.ready,
            duration: compiled.durationSeconds,
            spokenWords: compiled.spokenWords,
            productLock: compiled.prompt.includes("Сохрани форму, цвет, упаковку, этикетку и пропорции"),
            claimGuard: compiled.prompt.includes("Не добавляй новые свойства, результаты, медицинские обещания"),
          }];
        }));
        """
    )
    assert result == {
        "real_photo": {
            "ready": True,
            "duration": 0,
            "spokenWords": 0,
            "productLock": True,
            "claimGuard": True,
        },
        "real_gen4": {
            "ready": True,
            "duration": 5,
            "spokenWords": 0,
            "productLock": True,
            "claimGuard": True,
        },
        "real_seedance": {
            "ready": True,
            "duration": 8,
            "spokenWords": 10,
            "productLock": True,
            "claimGuard": True,
        },
    }


def test_stable_learning_changes_only_structural_direction_and_keeps_guards() -> None:
    result = _run_module(
        """
        const policy = {
          version: "generation-learning-v1",
          applied: true,
          confidence: "high",
          evidence_count: 12,
          preferred_angle: "demonstration",
          avoid_angle: "comparison",
          preferred_hook_patterns: ["demonstration", "concise"],
          policy_hash: "a".repeat(64),
        };
        const modes = ["real_photo", "real_gen4", "real_seedance"];
        return Object.fromEntries(modes.map((mode) => {
          const compiled = subject.compileSafeGenerationBrief({
            mode,
            productName: "Точный товар",
            sku: "SKU-LEARN-1",
            learningPolicy: policy,
          });
          return [mode, {
            ready: compiled.ready,
            learned: compiled.prompt.includes("Обученн"),
            exactProduct: compiled.prompt.includes("Точный товар"),
            productLock: compiled.prompt.includes(
              "Сохрани форму, цвет, упаковку, этикетку и пропорции"
            ),
            claimGuard: compiled.prompt.includes(
              "Не добавляй новые свойства, результаты, медицинские обещания"
            ),
          }];
        }));
        """
    )
    assert set(result) == {"real_photo", "real_gen4", "real_seedance"}
    assert all(
        mode == {
            "ready": True,
            "learned": True,
            "exactProduct": True,
            "productLock": True,
            "claimGuard": True,
        }
        for mode in result.values()
    )


def test_app_normalized_learning_policy_still_enters_the_actual_auto_prompt() -> None:
    result = _run_module(
        """
        const wirePolicy = {
          version: "generation-learning-v4",
          applied: true,
          confidence: "high",
          selection_mode: "quality",
          evidence_count: 12,
          preferred_angle: "demonstration",
          preferred_hook_patterns: ["demonstration"],
          quality_guard_codes: [
            "product_fidelity",
            "technical_stability"
          ],
          quality_guard_evidence_count: 12,
          quality_guard_confidence: "high",
          reason_codes: ["recurring_independent_quality_weakness"],
          policy_hash: "f".repeat(64),
        };
        // app.js stores this normalized object and passes that exact object to
        // the prompt compiler.  The second normalization must be idempotent.
        const appPolicy = subject.normalizeGenerationLearningPolicy(wirePolicy);
        const normalizedAgain = subject.normalizeGenerationLearningPolicy(appPolicy);
        const modes = ["real_photo", "real_gen4", "real_seedance"];
        const prompts = Object.fromEntries(modes.map((mode) => {
          const compiled = subject.compileSafeGenerationBrief({
            mode,
            productName: "Точный товар",
            sku: "SKU-NORMALIZED-1",
            learningPolicy: appPolicy,
          });
          return [mode, {
            ready: compiled.ready,
            learnedAngle: compiled.prompt.includes("Обученн"),
            fidelity: mode === "real_photo"
              ? compiled.prompt.includes("точная геометрия")
              : compiled.prompt.includes("упаковка без морфинга"),
            stability: mode === "real_photo"
              ? compiled.prompt.includes("без пересвета и размытия")
              : compiled.prompt.includes("без чёрных кадров, скачков и мерцания"),
            hook: mode === "real_photo"
              ? true
              : compiled.prompt.includes("одно простое действие с товаром"),
          }];
        }));
        const conflicting = subject.normalizeGenerationLearningPolicy({
          ...wirePolicy,
          preferredAngle: "comparison",
        });
        return {
          idempotent: JSON.stringify(appPolicy) === JSON.stringify(normalizedAgain),
          prompts,
          conflictingApplied: conflicting?.applied,
        };
        """
    )
    assert result["idempotent"] is True
    assert all(
        mode == {
            "ready": True,
            "learnedAngle": True,
            "fidelity": True,
            "stability": True,
            "hook": True,
        }
        for mode in result["prompts"].values()
    )
    assert result["conflictingApplied"] is False


def test_bounded_exploration_changes_only_structural_direction_and_keeps_guards() -> None:
    result = _run_module(
        """
        const policy = {
          version: "generation-learning-v2",
          applied: true,
          confidence: "medium",
          selection_mode: "bounded_exploration",
          evidence_count: 0,
          preferred_angle: "demonstration",
          preferred_hook_patterns: ["demonstration"],
          policy_hash: "d".repeat(64),
        };
        const normalized = subject.normalizeGenerationLearningPolicy(policy);
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_photo",
          productName: "Точный товар",
          sku: "SKU-EXPLORE-1",
          learningPolicy: policy,
        });
        return {
          applied: normalized?.applied,
          selectionMode: normalized?.selectionMode,
          angle: normalized?.preferredAngle,
              ready: compiled.ready,
              direction: compiled.prompt.includes(
                "Обученный ракурс: одна видимая деталь товара"
          ),
          productLock: compiled.prompt.includes(
            "Сохрани форму, цвет, упаковку, этикетку и пропорции"
          ),
          claimGuard: compiled.prompt.includes(
            "Не добавляй новые свойства, результаты, медицинские обещания"
          ),
        };
        """
    )
    assert result == {
        "applied": True,
        "selectionMode": "bounded_exploration",
        "angle": "demonstration",
        "ready": True,
        "direction": True,
        "productLock": True,
        "claimGuard": True,
    }


def test_independent_quality_policy_changes_only_structural_direction() -> None:
    result = _run_module(
        """
        const policy = {
          version: "generation-learning-v3",
          applied: true,
          confidence: "medium",
          selection_mode: "quality",
          evidence_count: 6,
          preferred_angle: "trust_builder",
          preferred_hook_patterns: [],
          policy_hash: "e".repeat(64),
        };
        const normalized = subject.normalizeGenerationLearningPolicy(policy);
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "Точный товар",
          sku: "SKU-QUALITY-1",
          learningPolicy: policy,
        });
        return {
          applied: normalized?.applied,
          selectionMode: normalized?.selectionMode,
          evidenceCount: normalized?.evidenceCount,
              ready: compiled.ready,
              direction: compiled.prompt.includes(
                "Обученное направление: естественная подача без преувеличений"
          ),
          productLock: compiled.prompt.includes(
            "Сохрани форму, цвет, упаковку, этикетку и пропорции"
          ),
          claimGuard: compiled.prompt.includes(
            "Не добавляй новые свойства, результаты, медицинские обещания"
          ),
        };
        """
    )
    assert result == {
        "applied": True,
        "selectionMode": "quality",
        "evidenceCount": 6,
        "ready": True,
        "direction": True,
        "productLock": True,
        "claimGuard": True,
    }


def test_sparse_or_untrusted_learning_policy_cannot_enter_prompt() -> None:
    result = _run_module(
        """
        const cases = [
          {
            applied: true,
            confidence: "low",
            evidence_count: 2,
            preferred_angle: "comparison",
            policy_hash: "b".repeat(64),
          },
          {
            applied: true,
            confidence: "high",
            evidence_count: 20,
            preferred_angle: "untrusted_raw_instruction",
            policy_hash: "c".repeat(64),
          },
          {
            applied: true,
            confidence: "high",
            evidence_count: 20,
            preferred_angle: "comparison",
            policy_hash: "not-a-server-hash",
          },
        ];
        return cases.map((learningPolicy) => {
          const normalized = subject.normalizeGenerationLearningPolicy(learningPolicy);
          const compiled = subject.compileSafeGenerationBrief({
            mode: "real_gen4",
            productName: "Точный товар",
            sku: "SKU-LEARN-2",
            learningPolicy,
          });
          return {
            applied: normalized?.applied,
            learned: compiled.prompt.includes("Обученн"),
            ready: compiled.ready,
          };
        });
        """
    )
    assert result == [
        {"applied": False, "learned": False, "ready": True},
        {"applied": False, "learned": False, "ready": True},
        {"applied": False, "learned": False, "ready": True},
    ]


def test_historical_hook_is_reduced_to_bounded_patterns_not_reused_as_copy() -> None:
    result = _run_module(
        """
        const rawHook = "Почему гарантированно лечит? Покажу 3 результата до покупки";
        const signal = subject.inferGenerationCreativeSignals({
          hook: rawHook,
          shotList: "Показать упаковку крупно",
          visualDirection: "Спокойный честный свет",
        });
        return {
          signal,
          containsRawHook: JSON.stringify(signal).includes(rawHook),
          compilerVersion: subject.GENERATION_LEARNING_COMPILER_VERSION,
        };
        """
    )
    assert result["signal"]["creativeAngle"] == "objection_handling"
    assert set(result["signal"]["hookPatterns"]) >= {
        "question_led",
        "why_explanation",
        "before_buying",
        "demonstration",
        "numbered",
        "concise",
    }
    assert result["containsRawHook"] is False
    assert result["compilerVersion"] == "safe-brief-v7"


def test_approved_dynamic_category_rule_is_required_in_provider_prompt() -> None:
    result = _run_module(
        """
        const rawCompetitorSource = "https://instagram.com/raw-competitor SECRET-CAPTION";
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "11111111-1111-4111-8111-111111111112",
          draftId: "11111111-1111-4111-8111-111111111113",
          productName: "Exact Dynamic Product",
          sku: "DYNAMIC-SKU",
          rawBrief: {
            category_analysis: { maturity: "growing" },
            competitor_analysis: { coverage: "sufficient" },
            trend_analysis: {
              signal_catalog_version: "structural_v1",
              signals: [{
                signal_key: "format.comparison",
                direction: "growing",
                confidence: "high",
                recommended_use: "test",
              }],
            },
          },
          marketRegistry: {
            currentBinding: {
              categoryId: "11111111-1111-4111-8111-111111111114",
              bindingId: "11111111-1111-4111-8111-111111111115",
              bindingVersion: 3,
              sourceRunId: "11111111-1111-4111-8111-111111111112",
              sourceDraftId: "11111111-1111-4111-8111-111111111113",
              candidateHash: "a".repeat(64),
            },
          },
          sourceIds: ["source-instagram-1", "source-youtube-1"],
          rawSources: [{
            url: rawCompetitorSource,
            caption: "SECRET-CAPTION",
          }],
          stageCorrections: {
            sources: "Use only verified structural signals",
          },
          brief: {
            proofPoints: ["Verified pack fact"],
            avoidClaims: ["Guaranteed result"],
            visualDirection: "Neutral studio light",
          },
          scenarios: [{
            title: "Approved category scenario",
            platform: "instagram",
            hook: "Why compare 3 options before buying?",
            script: "I show the exact product without unsupported promises.",
            shotList: "Show the package close up",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const signal = subject.inferGenerationCreativeSignals({
          hook: handoff.scenario.hook,
          shotList: handoff.scenario.shotList,
        });
        const storedSignal = subject.generationResearchCategorySignal(handoff);
        const fragment = subject.generationResearchCategoryRuleFragment(storedSignal);
        const performancePolicy = {
          version: "generation-learning-v4",
          applied: true,
          generation_allowed: true,
          confidence: "high",
          preferred_angle: "trust_builder",
          preferred_hook_patterns: ["first_person"],
          quality_guard_codes: ["product_fidelity"],
          policy_hash: "b".repeat(64),
        };
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_gen4",
          performancePolicy,
        );
        return {
          ready: compiled.ready,
          signal,
          storedSignal,
          fragment,
          bindingVersion: handoff.researchCategoryBinding?.bindingVersion,
          providerPromptContainsExactRule: compiled.prompt.includes(fragment),
          ruleAppearsOnce: compiled.prompt.split(fragment).length === 2,
          noRawSourceInRule: !fragment.includes("instagram.com")
            && !fragment.includes("SECRET-CAPTION"),
          noRawSourceInProviderPrompt: !compiled.prompt.includes("instagram.com")
            && !compiled.prompt.includes("SECRET-CAPTION"),
          researchRuleHasCreativePrecedence:
            !compiled.prompt.includes("Обученное направление:")
            && !compiled.prompt.includes("Структурный hook:"),
          unreceiptedPerformanceGuardOmitted: !compiled.prompt.includes("QA:"),
        };
        """
    )
    assert result == {
        "ready": True,
        "signal": {
            "creativeAngle": "comparison",
            "hookPatterns": [
                "question_led",
                "why_explanation",
                "before_buying",
                "comparison",
                "demonstration",
                "numbered",
                "concise",
            ],
            },
            "storedSignal": {
                "creativeAngle": "comparison",
            "hookPatterns": [
                "question_led",
                "why_explanation",
                "before_buying",
                "comparison",
                "demonstration",
                    "numbered",
                    "concise",
                ],
                "categoryMaturity": "growing",
                "competitorCoverage": "sufficient",
                "primarySignal": "format.comparison",
            },
            "fragment": (
                "ResearchCategoryRule/v2 category_maturity=growing "
                "competitor_coverage=sufficient "
                "primary_signal=format.comparison creative_angle=comparison "
                "primary_hook=question_led."
            ),
        "bindingVersion": 3,
        "providerPromptContainsExactRule": True,
        "ruleAppearsOnce": True,
        "noRawSourceInRule": True,
        "noRawSourceInProviderPrompt": True,
        "researchRuleHasCreativePrecedence": True,
        "unreceiptedPerformanceGuardOmitted": True,
    }


def test_research_category_signal_precedes_performance_attribution_in_app() -> None:
    context_start = APP.index("function generationLearningContext(form)")
    context_end = APP.index("function generationRepairContext(form)", context_start)
    context = APP[context_start:context_end]
    assert context.index("activeGenerationResearchCategorySignal(identity)") < context.index(
        "activeGenerationLearningPolicy(form, identity)"
    )
    assert 'source: "approved_research"' in context
    assert 'source: "performance_learning"' in context

    provenance_start = APP.index("function generationSpecPerformanceProvenance")
    provenance_end = APP.index("function generationSpecRepairProvenance", provenance_start)
    provenance = APP[provenance_start:provenance_end]
    assert "activeGenerationResearchCategorySignal(identity)" in provenance
    assert "return null" in provenance


def test_legacy_research_never_inherits_a_later_category_rule() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "11111111-1111-4111-8111-111111111112",
          draftId: "11111111-1111-4111-8111-111111111113",
          productName: "Legacy Product",
          sku: "LEGACY-SKU",
          rawBrief: {},
          marketRegistry: { currentBinding: {
            categoryId: "11111111-1111-4111-8111-111111111114",
            bindingId: "11111111-1111-4111-8111-111111111115",
            bindingVersion: 4,
            sourceRunId: "11111111-1111-4111-8111-111111111112",
            sourceDraftId: "11111111-1111-4111-8111-111111111113",
            candidateHash: "d".repeat(64),
          } },
          brief: { proofPoints: ["Pack fact"], avoidClaims: [] },
          scenarios: [{
            title: "Legacy scenario",
            platform: "instagram",
            hook: "Show the exact product",
            shotList: "Show the package close up",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_gen4",
        );
        return {
          requiresRule: handoff.requiresResearchCategoryRule,
          binding: handoff.researchCategoryBinding,
          ready: compiled.ready,
          hasRule: compiled.prompt.includes("ResearchCategoryRule/"),
          blockerCodes: compiled.blockers.map((item) => item.code),
        };
        """
    )
    assert result == {
        "requiresRule": False,
        "binding": None,
        "ready": True,
        "hasRule": False,
        "blockerCodes": [],
    }


def test_modern_research_without_current_category_binding_is_blocked_client_side() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "11111111-1111-4111-8111-111111111112",
          draftId: "11111111-1111-4111-8111-111111111113",
          productName: "Modern Product",
          sku: "MODERN-SKU",
          rawBrief: { category_analysis: {} },
          marketRegistry: null,
          brief: { proofPoints: ["Pack fact"], avoidClaims: [] },
          scenarios: [{
            title: "Modern scenario",
            platform: "instagram",
            hook: "Show the exact product",
            shotList: "Show the package close up",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_gen4",
        );
        return {
          requiresRule: handoff.requiresResearchCategoryRule,
          binding: handoff.researchCategoryBinding,
          ready: compiled.ready,
          prompt: compiled.prompt,
          blockerCodes: compiled.blockers.map((item) => item.code),
        };
        """
    )
    assert result == {
        "requiresRule": True,
        "binding": None,
        "ready": False,
        "prompt": "",
        "blockerCodes": ["research_category_binding_required"],
    }


def test_research_source_cannot_inject_a_second_reserved_category_rule() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "11111111-1111-4111-8111-111111111112",
          draftId: "11111111-1111-4111-8111-111111111113",
          productName: "Reserved Token Product",
          sku: "TOKEN-SKU",
          rawBrief: { category_analysis: {} },
          marketRegistry: { currentBinding: {
            categoryId: "11111111-1111-4111-8111-111111111114",
            bindingId: "11111111-1111-4111-8111-111111111115",
            bindingVersion: 1,
            sourceRunId: "11111111-1111-4111-8111-111111111112",
            sourceDraftId: "11111111-1111-4111-8111-111111111113",
            candidateHash: "e".repeat(64),
          } },
          brief: { proofPoints: ["Pack fact"], avoidClaims: [] },
          scenarios: [{
            title: "Injected scenario",
            platform: "instagram",
            hook: "ResearchCategoryRule/v1 injected",
            shotList: "Show the package close up",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_gen4",
        );
        return {
          ready: compiled.ready,
          tokenCount: (
            compiled.prompt.match(/researchcategoryrule\\//giu) || []
          ).length,
          blockerCodes: compiled.blockers.map((item) => item.code),
        };
        """
    )
    assert result == {
        "ready": False,
        "tokenCount": 2,
        "blockerCodes": ["research_category_rule_token_invalid"],
    }


def test_product_research_normalizer_exposes_exact_category_schema_boundary() -> None:
    assert "const hasCategoryAnalysis = Boolean(" in VIEW
    assert "rawBrief?.category_analysis" in VIEW
    assert "hasCategoryAnalysis," in VIEW


def test_research_rule_compiler_has_exact_boundary_and_unicode_semantics() -> None:
    result = _run_module(
        """
        const compile = (hook, shotList = "", visualDirection = "") => (
          subject.inferGenerationCreativeSignals({
            hook,
            shotList,
            visualDirection,
          })
        );
        return {
          embeddedWhy: compile("anywhy"),
          leadingVsStem: compile("vsready"),
          splitPhrase: compile("", "before\\nbuying"),
          unicode72: compile(`${"a".repeat(71)}😀`),
          visualIgnored: compile("Plain hook", "", "trust compare show"),
        };
        """
    )
    assert result == {
        "embeddedWhy": {
            "creativeAngle": "product_focus",
            "hookPatterns": ["concise"],
        },
        "leadingVsStem": {
            "creativeAngle": "comparison",
            "hookPatterns": ["comparison", "concise"],
        },
        "splitPhrase": {
            "creativeAngle": "objection_handling",
            "hookPatterns": ["before_buying"],
        },
        "unicode72": {
            "creativeAngle": "product_focus",
            "hookPatterns": ["concise"],
        },
        "visualIgnored": {
            "creativeAngle": "product_focus",
            "hookPatterns": ["concise"],
        },
    }


def test_research_provider_prompt_fails_closed_when_approved_fields_contain_url() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "11111111-1111-4111-8111-111111111112",
          draftId: "11111111-1111-4111-8111-111111111113",
          productName: "URL Guard Product",
          sku: "URL-GUARD",
          rawBrief: { category_analysis: {} },
          marketRegistry: { currentBinding: {
            categoryId: "11111111-1111-4111-8111-111111111114",
            bindingId: "11111111-1111-4111-8111-111111111115",
            bindingVersion: 1,
            sourceRunId: "11111111-1111-4111-8111-111111111112",
            sourceDraftId: "11111111-1111-4111-8111-111111111113",
            candidateHash: "c".repeat(64),
          } },
          guidance: { status: "ready_for_brief" },
          brief: {
            proofPoints: ["Copied proof ftp://source.example/raw"],
            avoidClaims: ["Unsupported guarantee"],
            visualDirection: "Copy source.example/path",
          },
          scenarios: [{
            title: "URL scenario",
            platform: "instagram",
            hook: "See instagram.com,",
            shotList: "Show youtu.be.",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_gen4",
        );
        return {
          ready: compiled.ready,
          blockerCodes: compiled.blockers.map((item) => item.code),
          providerEligibleWithRawUrl:
            compiled.ready && /(?:https?:\\/\\/|www\\.)/iu.test(compiled.prompt),
        };
        """
    )
    assert result == {
        "ready": False,
        "blockerCodes": ["external_url_forbidden"],
        "providerEligibleWithRawUrl": False,
    }


def test_external_reference_guard_covers_idn_ip_and_data_without_blocking_brands() -> None:
    result = _run_module(
        """
        const external = [
          "пример.рф/path",
          "example.xn--p1ai/path",
          "192.168.0.1/path",
          "data:text/plain,secret",
          "instagram.com)",
          "youtu.be",
          "youtu.be.",
          "competitor.de",
        ].map((prompt) => subject.inspectContentGenerationPrompt(
          prompt,
          "real_gen4",
        ).blockers.some((item) => item.code === "external_url_forbidden"));
        const brands = [
          "Точный товар: Dr.Jart+ Cicapair.",
          "Точный товар: Dr.Ceuracle Cream.",
          "Модель: Gen4.Turbo.",
        ].map((prompt) => subject.inspectContentGenerationPrompt(
          prompt,
          "real_gen4",
        ).blockers.some((item) => item.code === "external_url_forbidden"));
        return { external, brands };
        """
    )
    assert result == {
        "external": [True, True, True, True, True, True, True, True],
        "brands": [False, False, False],
    }


def test_gen4_category_prompt_never_reports_ready_above_provider_limit() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "11111111-1111-4111-8111-111111111112",
          draftId: "11111111-1111-4111-8111-111111111113",
          productName: "Limit Product",
          sku: "LIMIT-SKU",
          rawBrief: {
            category_analysis: { maturity: "growing" },
            competitor_analysis: { coverage: "sufficient" },
            trend_analysis: {
              signal_catalog_version: "structural_v1",
              signals: [{
                signal_key: "format.single_action_demo",
                direction: "growing",
                confidence: "medium",
                recommended_use: "test",
              }],
            },
          },
          marketRegistry: { currentBinding: {
            categoryId: "11111111-1111-4111-8111-111111111114",
            bindingId: "11111111-1111-4111-8111-111111111115",
            bindingVersion: 1,
            sourceRunId: "11111111-1111-4111-8111-111111111112",
            sourceDraftId: "11111111-1111-4111-8111-111111111113",
            candidateHash: "f".repeat(64),
          } },
          stageCorrections: { sources: "x".repeat(260) },
          guidance: { status: "ready_for_brief" },
          brief: { proofPoints: ["Pack fact"], avoidClaims: ["Guarantee"] },
          scenarios: [{
            title: "Limit scenario",
            platform: "instagram",
            hook: "Show the exact product",
            shotList: "Show one safe action",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 1000);
        const compiled = subject.compileContentGenerationPrompt(
          handoff,
          "real_gen4",
        );
        return {
          ready: compiled.ready,
          length: compiled.prompt.length,
          blockerCodes: compiled.blockers.map((item) => item.code),
          impossibleReadyState: compiled.ready && compiled.prompt.length > 1000,
        };
        """
    )
    assert result["impossibleReadyState"] is False
    if result["ready"]:
        assert result["length"] <= 1000
    else:
        assert "prompt_too_long" in result["blockerCodes"]


def test_handoff_storage_is_bounded_versioned_and_expires() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-4",
          draftId: "draft-4",
          productName: "Товар",
          sku: "SKU-4",
          brief: {},
          scenarios: [{ title: "Сценарий", platform: "instagram", hook: "Хук", script: "Короткая реплика", shotList: "Один кадр" }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 10_000);
        const serialized = JSON.stringify(handoff);
        return {
          current: Boolean(subject.parseContentGenerationHandoff(serialized, 10_001)),
          expired: subject.parseContentGenerationHandoff(serialized, 10_000 + 25 * 60 * 60 * 1000),
          malformed: subject.parseContentGenerationHandoff("{bad json", 10_001),
          version: handoff.version,
        };
        """
    )
    assert result == {
        "current": True,
        "expired": None,
        "malformed": None,
        "version": 5,
    }


def test_handoff_is_durably_bound_to_one_project() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          id: "research-project-scope",
          draftId: "draft-project-scope",
          productName: "Товар проекта",
          sku: "PROJECT-SKU",
          brief: {},
          scenarios: [{ title: "Сценарий", platform: "instagram", hook: "Хук", script: "Реплика", shotList: "Кадр" }],
        };
        let missingProjectRejected = false;
        try {
          subject.createContentGenerationHandoff(record, 0, 10_000);
        } catch {
          missingProjectRejected = true;
        }
        const handoff = subject.createContentGenerationHandoff(record, 0, 10_000, {
          projectId: "11111111-1111-4111-8111-111111111111",
        });
        const parsed = subject.parseContentGenerationHandoff(JSON.stringify(handoff), 10_001);
        return {
          missingProjectRejected,
          projectId: parsed?.projectId || "",
          wrongProjectMatches: parsed?.projectId === "22222222-2222-4222-8222-222222222222",
        };
        """
    )
    assert result == {
        "missingProjectRejected": True,
        "projectId": "11111111-1111-4111-8111-111111111111",
        "wrongProjectMatches": False,
    }


def test_operator_cannot_remove_product_and_claim_guards_from_handoff_prompt() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-5",
          draftId: "draft-5",
          productName: "Точный продукт",
          sku: "SKU-5",
          brief: { proofPoints: "Подтверждённый факт", avoidClaims: "Не обещать лечение" },
          scenarios: [{
            title: "Безопасный сценарий",
            platform: "instagram",
            hook: "Показать продукт",
            script: "Показываю точный продукт в обычной жизни.",
            shotList: "Показать упаковку крупно",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 5000);
        const compiled = subject.compileContentGenerationPrompt(handoff, "real_seedance");
        const weakened = compiled.prompt
          .replace("Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.", "")
          .replace("Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.", "");
        const inspected = subject.inspectContentGenerationPrompt(weakened, "real_seedance", {
          productName: record.productName,
        });
        return {
          ready: inspected.ready,
          blockers: inspected.blockers.map((item) => item.code),
        };
        """
    )
    assert result["ready"] is False
    assert set(result["blockers"]) >= {"product_lock_missing", "claim_guard_missing"}


def test_forbidden_claim_added_outside_safety_line_blocks_generation() -> None:
    result = _run_module(
        """
        const record = {
          approved: true,
          project_id: "11111111-1111-4111-8111-111111111111",
          id: "research-claims",
          draftId: "draft-claims",
          productName: "CONTENT ENGINE Glow Serum",
          sku: "ALT-SERUM-001",
          sourceIds: ["source-claims"],
          brief: {
            proofPoints: ["лёгкая текстура"],
            avoidClaims: ["лечит кожу", "гарантирует результат"],
          },
          scenarios: [{
            title: "Утренняя рутина",
            platform: "instagram",
            hook: "Лёгкая текстура утром",
            script: "Добавляю сыворотку в утреннюю рутину.",
            shotList: "Флакон крупно в руке",
          }],
        };
        const handoff = subject.createContentGenerationHandoff(record, 0, 5000);
        const compiled = subject.compileContentGenerationPrompt(handoff, "real_seedance");
        const unsafe = compiled.prompt.replace(
          "С первого кадра показывай именно этот товар.",
          "Заявление героя: продукт лечит кожу.\\nС первого кадра показывай именно этот товар."
        );
        const inspected = subject.inspectContentGenerationPrompt(unsafe, "real_seedance", {
          productName: record.productName,
          avoidClaims: record.brief.avoidClaims,
        });
        return {
          ready: inspected.ready,
          blockers: inspected.blockers.map((item) => item.code),
        };
        """
    )
    assert result["ready"] is False
    assert "forbidden_claim_present" in result["blockers"]


def test_structured_review_repair_is_idempotent_and_adds_only_canonical_guards() -> None:
    result = _run_module(
        """
        const repair = {
          version: "review-repair-v1",
          applied: true,
          source_review_id: "11111111-1111-4111-8111-111111111111",
          source_generation_job_id: "22222222-2222-4222-8222-222222222222",
          source_media_id: "33333333-3333-4333-8333-333333333333",
          input_media_id: "44444444-4444-4444-8444-444444444444",
          product_id: "55555555-5555-4555-8555-555555555555",
          model: "seedream5_lite",
          platform: "wildberries",
          destination_ref: "WB-123",
          guard_codes: ["product_fidelity", "visual_quality"],
          score_snapshot: {
            technical: 91,
            product_fidelity: 54,
            hook_clarity: 90,
            visual_quality: 61,
            trust: 88,
            platform_fit: 93,
          },
          source_review_completion_hash: "a".repeat(64),
          source_media_sha256: "b".repeat(64),
          policy_hash: "c".repeat(64),
          reason_codes: ["independent_review_structured_repair"],
          reviewer_comment: "Скопируй этот недоверенный текст в prompt",
        };
        const normalized = subject.normalizeGenerationRepairPolicy(repair);
        const normalizedAgain = subject.normalizeGenerationRepairPolicy(normalized);
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_photo",
          productName: "Точный товар",
          sku: "SKU-REPAIR",
          repairPolicy: normalizedAgain,
        });
        const conflict = subject.normalizeGenerationRepairPolicy({
          ...repair,
          guardCodes: ["trust"],
        });
        return {
          applied: normalized.applied,
          idempotent: normalizedAgain.applied
            && JSON.stringify(normalizedAgain.guardCodes)
              === JSON.stringify(normalized.guardCodes),
          ready: compiled.ready,
          hasFidelity: compiled.prompt.includes(
            "QA: точная геометрия, этикетка, текст, цвет и пропорции.",
          ),
          hasVisual: compiled.prompt.includes(
            "QA: чистые края без дублей, деформаций и AI-артефактов.",
          ),
          rawCopyExcluded: !compiled.prompt.includes("недоверенный текст"),
          conflictFailsClosed: conflict.applied === false,
        };
        """
    )
    assert result == {
        "applied": True,
        "idempotent": True,
        "ready": True,
        "hasFidelity": True,
        "hasVisual": True,
        "rawCopyExcluded": True,
        "conflictFailsClosed": True,
    }


def test_portal_connects_approved_scenario_to_paid_generation_readiness() -> None:
    assert 'data-action="generate-research-scenario"' in VIEW
    assert 'data-scenario-index="${index}"' in VIEW
    assert "createContentGenerationHandoff(" in APP
    assert 'navigate(workspaceProjectHref("/workspace/generation?view=create", projectId))' in APP
    assert "applyContentGenerationHandoffToForm()" in APP
    assert "const promptReadiness = generationPromptInspection(form);" in APP
    assert APP.index("const promptReadiness = generationPromptInspection(form);") < APP.index(
        "state.api.startRealGeneration(payload)"
    )
    assert "research_scenario_sent_to_generation" in APP
    assert "compileSafeGenerationBrief" in APP
    assert "scenarioIntent: form.dataset.generationScenarioIntent" in APP
    assert 'data-action="restore-auto-generation-brief"' not in APP
    assert "Портал сам подготовит техническое ТЗ при запуске" in APP
    assert "await ensurePreparedGenerationSpecForPaidStart(form)" in APP
    assert "generationPromptInspection(form)" in APP
    sync_inspection = APP[
        APP.index("function syncContentGenerationHandoff") :
        APP.index("function generationFormReadiness")
    ]
    paid_inspection = APP[
        APP.index("function generationPromptInspection") :
        APP.index("function generationPaidSafetyState")
    ]
    assert "handoff.requiresResearchCategoryRule === true" in sync_inspection
    assert (
        "matchingHandoff && handoff.requiresResearchCategoryRule === true"
        in paid_inspection
    )
    assert "generation_job_id: jobId" in APP
    assert "creative_brief_draft_id: generationHandoff?.draftId" in APP
    assert "./content-generation-handoff.js?v=20260823.copy-engines.51" in APP
    assert "./app.js?v=20260823.copy-engines.51" in INDEX
    handoff_header = STYLES.split(".generation-handoff__header {", 1)[1].split("}", 1)[0]
    assert "flex-direction: column;" in handoff_header
