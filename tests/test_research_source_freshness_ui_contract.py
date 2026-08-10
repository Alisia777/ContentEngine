import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/product-research-view.js").read_text(encoding="utf-8")
GENERATION_SPEC = (ROOT / "web/app/generation-spec.js").read_text(
    encoding="utf-8"
)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _run_view_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable UI contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(VIEW, encoding="utf-8")
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


def test_new_research_form_restores_safe_inputs_but_not_spend_confirmation() -> None:
    result = _run_view_module(
        """
        const html = subject.productResearchInputMarkup({
          notice: "Прежний снимок сохранён; запуск не выполнен.",
          media: [{
            id: "media-1",
            title: "Упаковка",
            kind: "product_photo",
            status: "ready",
            mime_type: "image/webp",
            sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          }],
          defaults: {
            productName: "Тестовый товар",
            sku: "SKU-42",
            categoryName: "Уход",
            researchFocus: "Перепроверить доказательства",
            marketplaceUrl: "https://example.com/product/42",
            competitorReferences: "@public-reference",
            knownFacts: "Объём подтверждён этикеткой",
            objective: "education",
            platforms: ["instagram", "youtube"],
            sourceMediaIds: ["media-1"],
            previousResearchId: "11111111-1111-4111-8111-111111111111",
          },
        });
        return {
          product: html.includes('name="product_name" value="Тестовый товар"'),
          sku: html.includes('name="sku" value="SKU-42"'),
          category: html.includes('name="category_name" value="Уход"'),
          marketplace: html.includes('value="https://example.com/product/42"'),
          media: html.includes('name="source_media_ids" value="media-1" checked'),
          instagram: html.includes('name="platforms" value="instagram" checked'),
          youtube: html.includes('name="platforms" value="youtube" checked'),
          objective: html.includes('value="education" selected'),
          restore: html.includes('data-action="restore-previous-product-research"'),
          paidUnchecked: html.includes('name="paid_analysis_ack" required')
            && !html.includes('name="paid_analysis_ack" required checked'),
        };
        """
    )
    assert all(result.values()), result


def test_durable_objective_recovers_research_context_after_reload() -> None:
    result = _run_view_module(
        """
        const objective = [
          "Подготовить контент для узнаваемости товара и бренда",
          "Категория пользователя: Уход",
          "Приоритет исследования: Проверить сезонный спрос",
          "Ориентиры конкурентов пользователя (проверить публичными источниками, не копировать):",
          "@public-one",
          "https://example.com/public-two",
          "Подтверждённые вводные пользователя: Объём подтверждён этикеткой",
        ].join("\\n");
        const normalized = subject.normalizeProductResearch({
          run: {
            id: "11111111-1111-4111-8111-111111111111",
            status: "completed",
            input: {
              objective,
              marketplace_url: "https://example.com/product/42",
              source_media_ids: ["media-1"],
              platforms: ["instagram", "youtube"],
            },
          },
        });
        return normalized.researchInput;
        """
    )
    assert result["objectiveKey"] == "awareness"
    assert result["researchFocus"] == "Проверить сезонный спрос"
    assert result["competitorReferences"] == (
        "@public-one\nhttps://example.com/public-two"
    )
    assert result["knownFacts"] == "Объём подтверждён этикеткой"
    assert result["sourceMediaIds"] == ["media-1"]
    assert result["platforms"] == ["instagram", "youtube"]


def test_server_handoff_denial_disables_every_scenario_generation_action() -> None:
    result = _run_view_module(
        """
        const scenario = {
          title: "Точный демонстрационный тест",
          platform: "youtube",
          generationMode: "real_gen4",
          hook: "Товар сразу в кадре",
          script: "",
          shotList: "Крупный план товара",
          taskTitle: "Снять тест",
        };
        const record = {
          id: "11111111-1111-4111-8111-111111111111",
          draftId: "22222222-2222-4222-8222-222222222222",
          status: "approved",
          approved: true,
          taskIds: ["33333333-3333-4333-8333-333333333333"],
          productName: "Тестовый товар",
          sku: "SKU-42",
          brief: { title: "ТЗ" },
          scenarios: [scenario, { ...scenario }, { ...scenario }],
          recommendedScenarioIndex: 0,
          recommendedScenarioPosition: 1,
        };
        const denied = subject.productResearchResultMarkup(record, {
          stageControl: {
            available: true,
            runId: record.id,
            guidance: {
              currentDraftId: record.draftId,
              generationHandoffAllowed: false,
            },
          },
          view: "handoff",
        });
        const allowed = subject.productResearchResultMarkup(record, {
          stageControl: {
            available: true,
            runId: record.id,
            guidance: {
              currentDraftId: record.draftId,
              generationHandoffAllowed: true,
            },
          },
          view: "handoff",
        });
        const prepared = subject.productResearchResultMarkup(record, {
          stageControl: {
            available: true,
            runId: record.id,
            guidance: {
              currentDraftId: record.draftId,
              generationHandoffAllowed: true,
            },
          },
          recommendedPrepared: true,
          view: "handoff",
        });
        const unavailable = subject.productResearchResultMarkup(record, {
          stageControl: null,
          view: "handoff",
        });
        const deniedButtons = denied.match(
          /<button[^>]*data-action="generate-research-scenario"[^>]*>/g,
        ) || [];
        const allowedButtons = allowed.match(
          /<button[^>]*data-action="generate-research-scenario"[^>]*>/g,
        ) || [];
        return {
          warning: denied.includes("Исследование устарело"),
          newResearch: denied.includes('data-action="new-product-research"'),
          deniedButtons: deniedButtons.length === 3
            && deniedButtons.every((button) => button.includes("disabled")),
          allowedButtons: allowedButtons.length >= 3
            && allowedButtons.every((button) => !button.includes("disabled")),
          preparedRechecks: prepared.includes(
            'data-action="generate-research-scenario"',
          ) && !prepared.includes('#/workspace/generation?view=create'),
          unavailableFailsClosed: unavailable.includes(
            'data-action="new-product-research"',
          ) && !unavailable.includes('#/workspace/generation?view=create'),
        };
        """
    )
    assert all(result.values()), result


def test_stale_generation_action_prepares_form_without_provider_or_spend() -> None:
    handler = _between(
        APP,
        'if (specAction === "start_new_research")',
        'if (specAction === "confirm_spend")',
    )
    assert '"start_new_research"' in GENERATION_SPEC
    assert '"recompute_research"' not in GENERATION_SPEC
    assert "productResearchPrefillFromSnapshot" in handler
    assert "invalidateGenerationStateForResearch(researchId)" in handler
    assert "beginNewProductResearch" in handler
    assert 'productResearchStatusKind(currentResearch?.status) === "active"' in handler
    assert 'navigate("/workspace/research", true)' in handler
    assert handler.index("productResearchStatusKind") < handler.index(
        "invalidateGenerationStateForResearch"
    )
    assert handler.index("invalidateGenerationStateForResearch") < handler.index(
        "beginNewProductResearch"
    )
    for forbidden in (
        "startProductResearch",
        "startRealGeneration",
        "submitRealGeneration",
        "realGenerationPreflight",
    ):
        assert forbidden not in handler


def test_generation_click_rechecks_server_gate_before_handoff_creation() -> None:
    handler = _between(
        APP,
        'if (action === "generate-research-scenario")',
        'if (action === "dismiss-generation-handoff")',
    )
    assert "await loadResearchStageControl" in handler
    assert "stageControl.guidance?.generationHandoffAllowed !== true" in handler
    assert handler.index("await loadResearchStageControl") < handler.index(
        "createContentGenerationHandoff"
    )
    assert "invalidateGenerationStateForResearch(runId)" in handler
    assert "beginNewProductResearch" in handler


def test_source_correction_clears_only_matching_generation_context() -> None:
    correction = _between(
        APP,
        "async function submitProductResearchSourceCorrection",
        "async function submitProductResearchCollectionPolicy",
    )
    invalidator = _between(
        APP,
        "function invalidateGenerationStateForResearch",
        "function productResearchObjectiveKey",
    )
    assert "loadResearchStageControl({ runId, silent: true })" in correction
    assert "invalidateGenerationStateForResearch(runId)" in correction
    assert correction.index("invalidateGenerationStateForResearch(runId)") < correction.index(
        "await Promise.all"
    )
    assert "handoffMatches" in invalidator
    assert "generationSpecMatches" in invalidator
    assert "clearContentGenerationHandoff()" in invalidator
    assert "resetGenerationSpecState()" in invalidator
    assert "clearGenerationFormDraft()" in invalidator
    assert "if (!handoffMatches && !generationSpecMatches) return false" in invalidator
