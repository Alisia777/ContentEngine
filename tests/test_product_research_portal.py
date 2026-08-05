import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web/app/catalog.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/product-research-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "web/app/product-research.css").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-product-research/index.ts"
).read_text(encoding="utf-8")
MIGRATION = (
    ROOT / "supabase/migrations/202607150005_product_research_mvp.sql"
).read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _run_view_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")
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


def _run_api_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable API contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(API, encoding="utf-8")
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


def test_modern_shot_object_preserves_browser_compiler_text_boundary() -> None:
    result = _run_view_module(
        """
        const normalized = subject.normalizeProductResearch({
          run: {
            id: "11111111-1111-4111-8111-111111111112",
            product_name: "Compiler Product",
            sku: "COMPILER-SKU",
          },
          latest_draft: {
            id: "11111111-1111-4111-8111-111111111113",
            status: "approved",
            brief: {
              category_analysis: {},
              scenarios: [{
                title: "Compiler scenario",
                platform: "instagram",
                hook: "Plain hook",
                shot_list: [{
                  seconds: "0-2",
                  visual: "before\\nbuying",
                  voiceover: "neutral",
                  on_screen_text: "без текста",
                }],
              }],
            },
          },
        });
        return {
          hasCategoryAnalysis: normalized.hasCategoryAnalysis,
          shotList: normalized.scenarios[0]?.shotList,
        };
        """
    )
    assert result["hasCategoryAnalysis"] is True
    assert "before\nbuying" in result["shotList"]
    assert "0-2:" in result["shotList"]



def test_shared_research_forms_have_unique_patch_keys() -> None:
    keys = re.findall(r'data-ce-patch-key="([^"]+)"', VIEW)
    expected = {
        'research-brief:${escapeHtml(record?.id)}',
        'research-youtube-${mode}:${escapeHtml(control.runId)}',
        'research-market-existing:${escapeHtml(runId)}',
        'research-market-create:${escapeHtml(runId)}',
        'research-market-reaffirm:${escapeHtml(runId)}',
        'research-market-search:${escapeHtml(runId)}',
        'research-watchlist:${escapeHtml(runId)}',
    }
    assert expected <= set(keys)
    assert len(keys) == len(set(keys))
    shared_run_forms = re.findall(
        r'<form[^>]+data-research-id="[^"]+"[^>]*>',
        VIEW,
    )
    assert len(shared_run_forms) == 7
    assert all('data-ce-patch-key="' in form for form in shared_run_forms)

def test_manager_workspace_exposes_research_without_changing_six_step_factory() -> None:
    assert '["research", "Разбор товара", "⌕"]' in CATALOG
    assert CATALOG.index('["payouts", "Выплаты", "₽"]') < CATALOG.index(
        '["research", "Разбор товара", "⌕"]'
    )
    access = _between(APP, "function canManageProductResearch", "function visibleWorkspaceTabs")
    tabs = _between(APP, "function visibleWorkspaceTabs", "function brandMarkup")
    renderers = _between(APP, "const renderer =", "const initialSectionLoad")
    assert '["owner", "admin", "producer"]' in access
    assert 'key !== "research" || canManageProductResearch()' in tabs
    assert "research: renderProductResearchSection" in renderers
    assert "product-research.css?v=" in INDEX


def test_browser_api_uses_narrow_research_rpcs_and_exact_edge_payload() -> None:
    for function_name in (
        "creator_start_project_research",
        "creator_project_research_status",
        "creator_save_project_creative_brief_draft",
        "creator_approve_project_creative_brief",
    ):
        assert function_name in API

    start = _between(
        API,
        "async startProductResearch",
        "async productResearchStatus(runId, options = {})",
    )
    status = _between(
        API,
        "async productResearchStatus(runId, options = {})",
        "researchStageControlStatus",
    )
    save = _between(API, "  saveCreativeBriefDraft(runId", "  approveCreativeBrief(draftId")
    approve = _between(API, "  approveCreativeBrief(draftId", "  requireResearchRunId")
    invoke = _between(API, "async invokeProductResearch", "recordMetric(snapshot)")
    assert 'action: "analyze"' in start
    assert "research_id: runId" in start
    assert "paid_analysis_ack" in start
    assert "const normalizedProjectId = requiredProjectId(" in start
    assert "onRunCreated({" in start and "project_id: normalizedProjectId" in start
    assert "const normalizedRunId = this.requireResearchRunId(runId)" in status
    assert "const scopedPayload = this.withOrganization({" in status
    assert "run_id: normalizedRunId" in status
    assert "const projectScopedPayload = {" in status
    assert "project_id: requiredProjectId(options.project_id ?? options.projectId)" in status
    assert "this.call(RPC.productResearchStatus, projectScopedPayload)" in status
    assert "title: draft?.title" in save
    assert "source_ids: draft?.source_ids" in save
    assert "task_blueprint: draft?.task_blueprint" in save
    assert "draft_id: normalizedDraftId" in approve
    for source in (start, status, save, approve):
        assert "requiredProjectId(" in source
        assert "project_id" in source
    assert "body: payload" in invoke
    assert "body: this.withOrganization(payload)" not in invoke


def test_browser_api_exposes_confirmed_audited_category_retirement() -> None:
    assert (
        'retireResearchMarketCategory: "creator_retire_research_market_category"'
        in API
    )
    retire = _between(
        API,
        "  async retireResearchMarketCategory",
        "  searchResearchMarketCategories",
    )
    assert "isUuid(normalizedCategoryId)" in retire
    assert "reason.length < 3 || reason.length > 500" in retire
    assert "options.confirmation !== true" in retire
    assert "this.mutate(RPC.retireResearchMarketCategory" in retire
    assert "category_id: normalizedCategoryId" in retire
    assert "confirmation: true" in retire


def test_start_form_is_source_aware_paid_and_requires_human_review() -> None:
    start = _between(VIEW, "export function productResearchInputMarkup", "export function productResearchProgressMarkup")
    for field in (
        'name="product_name"',
        'name="sku"',
        'name="category_name"',
        'name="research_focus"',
        'name="competitor_references"',
        'name="marketplace_url"',
        'name="platforms"',
        'name="objective"',
        'name="known_facts"',
        'name="paid_analysis_ack" required',
        'name="human_review_ack" required',
    ):
        assert field in start
    assert 'name="source_media_ids"' in VIEW
    assert "Запустить платный анализ и собрать 3 сценария" in start
    assert "Повторный клик с теми же вводными не создаст второй запуск" in start
    assert "Не входит в чужие кабинеты" in start
    assert "ИИ готовит черновик" in start
    assert 'name="platforms" value="wildberries"' in start
    assert "не разрешение копировать чужие тексты" in start
    assert "Для каких площадок готовим контент" in start
    assert 'values.get("category_name")' in APP
    assert 'values.get("competitor_references")' in APP
    assert 'values.has("paid_analysis_ack")' in APP
    assert "paid_analysis_ack: true" in APP
    assert "input?.paid_analysis_ack !== true" in API
    assert "Категория пользователем не задана" in APP
    assert "самостоятельно найти сопоставимые публичные предложения" in APP


def test_category_competitor_trend_stages_are_visible_editable_and_guided() -> None:
    result = _run_view_module(
        """
        const normalized = subject.normalizeProductResearch({
          run: { id: "run-v2", status: "completed" },
          sources: [{
            id: "db-source-1",
            title: "Source one",
            source_url: "https://example.com/one",
            metadata: {
              model_source_id: "source-1",
              publisher: "Example Publisher",
              provider_citation_verified: true,
            },
            published_at: "2026-08-01T10:00:00.000Z",
            fetched_at: "2026-08-03T10:00:00.000Z",
          }, {
            id: "db-source-2",
            title: "Source two",
            source_url: "https://example.org/two",
            metadata: { model_source_id: "source-2" },
          }],
          latest_draft: {
            id: "draft-v2",
            source_ids: ["source-1", "source-2"],
            brief: {
              category_analysis: {
                category_name: "hair_styling",
                maturity: "emerging",
                definition: "A bounded styling category.",
                buyer_jobs: ["shape hair quickly"],
                substitute_categories: ["hair dryer"],
                unknowns: ["seasonality"],
                source_ids: ["source-1"],
              },
              competitor_analysis: {
                coverage: "limited",
                competitors: [{
                  name: "Competitor A",
                  positioning: "Fast styling",
                  price_positioning: "mid",
                  recurring_formats: ["demo"],
                  strengths: ["clear proof"],
                  weaknesses: ["generic hook"],
                  reusable_structures: ["problem then demo"],
                  source_ids: ["source-1"],
                }],
                saturated_patterns: [{ pattern: "generic unboxing", source_ids: ["source-1"] }],
                content_gaps: [{ gap: "proof in real conditions", source_ids: ["source-2"] }],
                limitations: ["web-only snapshot"],
              },
              trend_analysis: {
                as_of: "2026-08-03",
                signals: [{
                  signal: "comparison demos",
                  direction: "growing",
                  confidence: "medium",
                  evidence: "two public sources",
                  source_ids: ["source-1", "source-2"],
                  recommended_use: "test",
                }],
                limitations: ["short window"],
              },
              guidance: {
                status: "needs_user_decision",
                recommended_next_step: "Confirm the category boundary",
                reason: "The substitute set overlaps.",
                questions_for_user: ["Is this styling or drying?"],
                suggested_actions: ["Confirm category", "Test one structure"],
              },
              human_stage_corrections: {
                category: "Keep styling only",
                competitors: "Exclude marketplaces without the same use case",
              },
              scenarios: [{}, {}, {}],
            },
          },
        });
        const html = subject.productResearchResultMarkup(normalized);
        const readyHtml = subject.productResearchResultMarkup({
          ...normalized,
          guidance: {
            status: "ready_for_brief",
            recommended_next_step: "Review the brief",
            reason: "Evidence is sufficient for a bounded hypothesis.",
            questions_for_user: [],
            suggested_actions: ["Review"],
          },
        });
        const approvedLegacyHtml = subject.productResearchResultMarkup({
          ...normalized,
          approved: true,
          taskIds: ["task-legacy"],
          humanResearchDecision: {},
        });
        const approvedStoredHtml = subject.productResearchResultMarkup({
          ...normalized,
          approved: true,
          taskIds: ["task-guarded"],
          humanResearchDecision: {
            guidanceStatus: "needs_user_decision",
            coldStartOverride: true,
            strategy: "Run a bounded test",
          },
        });
        return {
          category: normalized.categoryAnalysis.categoryName,
          modelSourceId: normalized.sources[0].modelId,
          maturity: normalized.categoryAnalysis.maturity,
          competitors: normalized.competitorAnalysis.competitors.length,
          gapSources: normalized.competitorAnalysis.contentGaps[0].sourceIds,
          trendDirection: normalized.trendAnalysis.signals[0].direction,
          nextStep: normalized.guidance.recommendedNextStep,
          correction: normalized.stageCorrections.category,
          stages: (html.match(/data-research-stage=/g) || []).length,
          correctionsBoundToBrief: html.includes('form="product-research-brief-form" name="category_correction"'),
          competitorStructureVisible: html.includes("problem then demo"),
          competitorAnalysisVisible: html.includes("clear proof") && html.includes("generic hook"),
          competitorLimitationsVisible: html.includes("web-only snapshot"),
          substituteVisible: html.includes("hair dryer"),
          guidanceVisible: html.includes("Confirm the category boundary"),
          guidanceDetailsVisible: html.includes("Is this styling or drying?")
            && html.includes("Test one structure"),
          overrideRequired: html.includes('name="research_gap_override_ack"'),
          readySkipsOverride: !readyHtml.includes('name="research_gap_override_ack"'),
          legacyAckIsUnknown: approvedLegacyHtml.includes(
            "Подтверждение cold start не зафиксировано",
          ),
          storedAckIsVisible: approvedStoredHtml.includes(
            "Осознанный cold start подтверждён",
          ) && approvedStoredHtml.includes(
            'name="research_gap_override_ack" checked disabled',
          ),
          evidenceLinked: html.includes('href="https://example.com/one"')
            && html.includes("Source one"),
          provenanceVisible: html.includes("Заявленный издатель: Example Publisher")
            && html.includes("Дата страницы (извлечена ИИ): 2026-08-01")
            && html.includes("URL подтверждён поисковым провайдером"),
          canonicalDraftSources: normalized.sourceIds,
        };
        """
    )
    assert result == {
        "category": "hair_styling",
        "modelSourceId": "source-1",
        "maturity": "emerging",
        "competitors": 1,
        "gapSources": ["source-2"],
        "trendDirection": "growing",
        "nextStep": "Confirm the category boundary",
        "correction": "Keep styling only",
        "stages": 4,
        "correctionsBoundToBrief": True,
        "competitorStructureVisible": True,
        "competitorAnalysisVisible": True,
        "competitorLimitationsVisible": True,
        "substituteVisible": True,
        "guidanceVisible": True,
        "guidanceDetailsVisible": True,
        "overrideRequired": True,
        "readySkipsOverride": True,
        "legacyAckIsUnknown": True,
        "storedAckIsVisible": True,
        "evidenceLinked": True,
        "provenanceVisible": True,
        "canonicalDraftSources": ["source-1", "source-2"],
    }


def test_wildberries_research_reaches_the_paid_analysis_boundary() -> None:
    result = _run_api_module(
        """
        const calls = [];
        const api = Object.create(subject.CreatorApi.prototype);
        api.mutate = async (rpc, payload) => {
          calls.push({
            kind: "rpc",
            rpc,
            platforms: payload.platforms,
            project_id: payload.project_id,
            product_category: payload.product_category,
          });
          return { run: { id: "research-run-1", status: "queued" } };
        };
        api.invokeProductResearch = async (payload) => {
          calls.push({ kind: "edge", payload });
          return { ok: true };
        };
        const accepted = await api.startProductResearch({
          product_name: "Точный товар",
          sku: "WB-100",
          product_category: "electronics",
          platforms: ["wildberries"],
          project_id: "11111111-1111-4111-8111-111111111111",
          paid_analysis_ack: true,
        });
        const acceptedOzon = await api.startProductResearch({
          product_name: "Точный товар",
          sku: "OZON-100",
          product_category: "electronics",
          platforms: ["ozon"],
          project_id: "11111111-1111-4111-8111-111111111111",
          paid_analysis_ack: true,
        });
        let rejectedCode = "";
        try {
          await api.startProductResearch({
            product_name: "Точный товар",
            sku: "WB-100",
            product_category: "electronics",
            platforms: ["telegram"],
            project_id: "11111111-1111-4111-8111-111111111111",
            paid_analysis_ack: true,
          });
        } catch (error) {
          rejectedCode = String(error?.code || "");
        }
        return {
          platforms: subject.PRODUCT_RESEARCH_PLATFORMS,
          calls,
          acceptedId: accepted.run.id,
          acceptedOzonId: acceptedOzon.run.id,
          rejectedCode,
        };
        """
    )
    assert result == {
        "platforms": ["instagram", "youtube", "vk", "wildberries", "ozon"],
        "calls": [
            {
                "kind": "rpc",
                "rpc": "creator_start_project_research",
                "platforms": ["wildberries"],
                "project_id": "11111111-1111-4111-8111-111111111111",
                "product_category": "electronics",
            },
            {
                "kind": "edge",
                "payload": {
                    "action": "analyze",
                    "research_id": "research-run-1",
                    "project_id": "11111111-1111-4111-8111-111111111111",
                },
            },
            {
                "kind": "rpc",
                "rpc": "creator_start_project_research",
                "platforms": ["ozon"],
                "project_id": "11111111-1111-4111-8111-111111111111",
                "product_category": "electronics",
            },
            {
                "kind": "edge",
                "payload": {
                    "action": "analyze",
                    "research_id": "research-run-1",
                    "project_id": "11111111-1111-4111-8111-111111111111",
                },
            },
        ],
        "acceptedId": "research-run-1",
        "acceptedOzonId": "research-run-1",
        "rejectedCode": "product_research_platform_required",
    }
    assert "PRODUCT_RESEARCH_PLATFORM_SET.has(item)" in APP
    assert 'name="platforms" value="wildberries"' in VIEW
    assert 'name="platforms" value="ozon"' in VIEW
    assert '"wildberries",' in EDGE[
        EDGE.index("const PLATFORMS = new Set([") :
        EDGE.index("]);", EDGE.index("const PLATFORMS = new Set([")) + 3
    ]
    assert "'instagram', 'youtube', 'vk', 'wildberries', 'ozon'" in MIGRATION


def test_status_normalization_reads_canonical_sources_draft_and_forecast() -> None:
    result = _run_view_module(
        """
        const raw = {
          ok: true,
          run: { id: "run-1", status: "completed", summary: {} },
          sources: [{
            id: "source-1",
            source_type: "marketplace_page",
            source_url: "https://example.com/product",
            title: "Карточка товара",
            trust_level: "official",
            extracted_facts: [{ statement: "Вес 900 г" }],
          }],
          latest_draft: {
            id: "draft-1",
            title: "Три ролика",
            source_ids: ["source-1"],
            task_blueprint: [{ title: "Задача 1" }],
            brief: {
              summary: "Понятное резюме товара",
              audience: [{ name: "Спортсмен", profile: "Тренируется регулярно" }],
              facts: [{ statement: "Вес 900 г" }],
              claims: { forbidden: [{ claim: "Гарантирует результат" }] },
              scenarios: [0, 1, 2].map((index) => ({
                title: `Сценарий ${index + 1}`,
                platform: index === 1 ? "YouTube Shorts" : "Instagram Reels",
                hook: `Хук ${index + 1}`,
                spoken_script: `Реплика ${index + 1}`,
                shot_list: [{ seconds: "0–2", visual: "Товар", voiceover: "Смотрите", on_screen_text: "900 г" }],
              })),
              creative_potential: {
                score: 74,
                confidence_label: "medium",
                summary: "Есть потенциал",
                recommended_scenario_position: 2,
                recommended_scenario_reason:
                  "Самый ясный первый тест с точным товаром и простым исполнением",
              },
            },
          },
          forecasts: [{
            score: 74,
            confidence: 0.63,
            factors: { strengths: ["Понятный товар"], risks: ["Типовой хук"], summary: "Есть потенциал" },
          }],
        };
        const normalized = subject.normalizeProductResearch(raw);
        const html = subject.productResearchResultMarkup(normalized);
        return {
          id: normalized.id,
          draftId: normalized.draftId,
          sourceIds: normalized.sourceIds,
          score: normalized.score,
          confidence: normalized.confidence,
          scenarios: normalized.scenarios.length,
          recommendedPosition: normalized.recommendedScenarioPosition,
          recommendedIndex: normalized.recommendedScenarioIndex,
          recommendedReason: normalized.recommendedScenarioReason,
          sourceClaim: normalized.sources[0].claim,
          scenarioEditors: (html.match(/class="product-research-scenario"/g) || []).length,
          disclaimer: html.includes("не гарантирует просмотры или продажи"),
          sourceLinkSafe: html.includes('rel="noopener noreferrer nofollow"'),
          recommendationVisible: html.includes(
            "Лучший первый эксперимент — сценарий 2",
          ) && html.includes("Рекомендуем начать"),
        };
        """
    )
    assert result == {
        "id": "run-1",
        "draftId": "draft-1",
        "sourceIds": ["source-1"],
        "score": 74,
        "confidence": "medium",
        "scenarios": 3,
        "recommendedPosition": 2,
        "recommendedIndex": 1,
        "recommendedReason": (
            "Самый ясный первый тест с точным товаром и простым исполнением"
        ),
        "sourceClaim": "Вес 900 г",
        "scenarioEditors": 3,
        "disclaimer": True,
        "sourceLinkSafe": True,
        "recommendationVisible": True,
    }


def test_approval_saves_a_new_version_before_creating_tasks() -> None:
    submit = _between(APP, "async function submitProductResearchBrief", "function mergeProductResearchBrief")
    merge = _between(APP, "function mergeProductResearchBrief", "function productResearchTaskBlueprint")
    blueprint = _between(APP, "function productResearchTaskBlueprint", "function splitResearchLines")
    autoprepare = _between(
        APP,
        "function prepareRecommendedResearchHandoff",
        "function clearContentGenerationHandoff",
    )
    assert "saveCreativeBriefDraft" in submit
    assert "approveCreativeBrief" in submit
    assert submit.index("saveCreativeBriefDraft") < submit.index("approveCreativeBrief")
    assert 'form.elements.approve_ack?.checked !== true' in submit
    assert 'state.sections.tasks.status = "idle"' in submit
    assert "product_research_approved" in submit
    assert "prepareRecommendedResearchHandoff" in submit
    assert "recommended_scenario_position" in submit
    assert 'guidanceStatus !== "ready_for_brief"' in submit
    assert "draft.stage_corrections?.strategy" in submit
    assert "form.elements.research_gap_override_ack?.checked !== true" in submit
    assert "human_stage_corrections" in merge
    assert "human_research_decision" in merge
    assert "draft.research_gap_override_ack === true" in merge
    assert 'guidance_status: String(original.guidance?.status || "").trim()' in merge
    assert "draft.stage_corrections?.competitors" in merge
    assert 'task_type: "general"' in blueprint
    assert "Корректировка разбора конкурентов человеком" in blueprint
    assert "Решение пользователя для следующего этапа" in blueprint
    assert "instructions: fitProductResearchTaskInstructions([" in blueprint
    assert "assignee_id: scenario.assignee_id" in blueprint
    assert "scenario.position === recommendedScenarioPosition ? 4 : 3" in blueprint
    assert "createContentGenerationHandoff(record, recommendedIndex, Date.now()," in autoprepare
    assert "projectId: currentWorkspaceProjectId()" in autoprepare
    assert "persistContentGenerationHandoff(handoff)" in autoprepare
    for forbidden in (
        "realGenerationPreflight",
        "submitRealGeneration",
        "startRealGeneration",
        "real_spend_confirmation",
    ):
        assert forbidden not in autoprepare
    manual_handoff = _between(
        APP,
        'if (action === "generate-research-scenario")',
        'if (action === "dismiss-generation-handoff")',
    )
    assert "normalizeGenerationRepairPolicy" in manual_handoff
    assert "Новый сценарий не должен подменять активный repair-контекст" in manual_handoff


def test_task_instructions_are_bounded_without_losing_the_safety_suffix() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")
    helper = _between(
        APP,
        "function fitProductResearchTaskInstructions",
        "function splitResearchLines",
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        script = Path(temporary_directory) / "contract.mjs"
        script.write_text(
            helper
            + "\n"
            + "const safety = 'Ручная проверка перед сдачей обязательна.';\n"
            + "const longValue = fitProductResearchTaskInstructions(['я'.repeat(16000), safety]);\n"
            + "const shortValue = fitProductResearchTaskInstructions(['Сценарий', safety]);\n"
            + "const guardedValue = fitProductResearchTaskInstructions([\n"
            + "  { text: 'Необязательный контекст: ' + 'к'.repeat(14000), minLength: 100, weight: 1 },\n"
            + "  { text: 'Решение пользователя: сначала безопасный тест. STRATEGY-END', minLength: 600, weight: 10 },\n"
            + "  { text: 'Подтверждённые доказательства: ' + 'д'.repeat(2400) + ' PROOF-END', minLength: 3000, weight: 9 },\n"
            + "  { text: 'Запрещённые обещания: ' + 'з'.repeat(2400) + ' AVOID-END', minLength: 3000, weight: 10 },\n"
            + "  { text: safety, minLength: 500, weight: 100 },\n"
            + "]);\n"
            + "process.stdout.write(JSON.stringify({\n"
            + "  longLength: longValue.length,\n"
            + "  safetyPreserved: longValue.endsWith(safety),\n"
            + "  truncationExplained: longValue.includes('полностью — в связанном ТЗ'),\n"
            + "  mandatorySectionsPreserved: guardedValue.includes('STRATEGY-END')\n"
            + "    && guardedValue.includes('PROOF-END')\n"
            + "    && guardedValue.includes('AVOID-END')\n"
            + "    && guardedValue.endsWith(safety),\n"
            + "  guardedLength: guardedValue.length,\n"
            + "  shortValue,\n"
            + "}));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, script.name],
            cwd=temporary_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "longLength": 12000,
        "safetyPreserved": True,
        "truncationExplained": True,
        "mandatorySectionsPreserved": True,
        "guardedLength": 12000,
        "shortValue": "Сценарий\nРучная проверка перед сдачей обязательна.",
    }


def test_alternative_brief_envelope_keeps_raw_research_sections_for_save() -> None:
    result = _run_view_module(
        """
        const normalized = subject.normalizeProductResearch({
          run: {
            id: "run-backcompat",
            status: "completed",
            brief: {
              hidden_provider_field: "KEEP-ME",
              category_analysis: { category_name: "category" },
              competitor_analysis: { coverage: "limited" },
              trend_analysis: { as_of: "2026-08-03" },
              guidance: { status: "needs_more_evidence" },
              scenarios: [{}, {}, {}],
            },
          },
        });
        return {
          hidden: normalized.rawBrief.hidden_provider_field,
          categoryKept: Boolean(normalized.rawBrief.category_analysis),
          guidanceKept: Boolean(normalized.rawBrief.guidance),
        };
        """
    )
    assert result == {"hidden": "KEEP-ME", "categoryKept": True, "guidanceKept": True}


def test_research_run_and_approval_recover_after_reload() -> None:
    assert "persistProductResearchRunId(run?.id)" in APP
    assert "restoreProductResearchSession()" in APP
    assert "window.sessionStorage.getItem(key)" in APP
    poll = _between(
        APP,
        "async function pollProductResearchStatus({ silent = false } = {})",
        "function aiProductCategoryIds()",
    )
    assert "const projectId = currentWorkspaceProjectId()" in poll
    assert "state.api.productResearchStatus(runId, {" in poll
    assert "...productResearchOutcomeStatusOptions()" in poll
    assert "projectId," in poll
    assert "clearProductResearchRunId()" in APP
    assert 'name="scenario_${index}_assignee_id" required' in VIEW

    result = _run_view_module(
        """
        const normalized = subject.normalizeProductResearch({
          run: { id: "run-1", status: "completed" },
          latest_draft: { id: "draft-1", status: "approved", brief: { scenarios: [{}, {}, {}] } },
          approval: { status: "approved", draft_id: "draft-1", task_count: 3 },
          task_ids: ["task-1", "task-2", "task-3"],
        });
        const html = subject.productResearchResultMarkup(normalized, {
          members: [{ profile_id: "member-1", display_name: "Сергей", status: "active" }],
          defaultAssigneeId: "member-1",
        });
        return {
          approved: normalized.approved,
          status: normalized.status,
          tasks: normalized.taskIds.length,
          locked: html.includes("Сохранение заблокировано"),
          recovered: html.includes("Задачи созданы: 3"),
        };
        """
    )
    assert result == {
        "approved": True,
        "status": "approved",
        "tasks": 3,
        "locked": True,
        "recovered": True,
    }


def test_research_ui_has_loading_error_dark_mobile_and_reduced_motion_states() -> None:
    progress = _between(VIEW, "export function productResearchProgressMarkup", "export function productResearchResultMarkup")
    assert 'role="status"' in progress
    assert 'role="alert"' in progress
    assert 'aria-live="polite"' in progress
    assert "Проверить статус" in progress
    assert "Начать заново" in progress
    for contract in (
        'html[data-portal-theme="obsidian"]',
        "@media (max-width: 820px)",
        "@media (max-width: 560px)",
        "@media (prefers-reduced-motion: reduce)",
        ".product-research-scenarios",
        ".product-research-score-ring",
    ):
        assert contract in CSS
