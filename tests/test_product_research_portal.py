import json
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
        "creator_start_product_research",
        "creator_product_research_status",
        "creator_save_creative_brief_draft",
        "creator_approve_creative_brief",
    ):
        assert function_name in API

    start = _between(API, "async startProductResearch", "productResearchStatus(runId)")
    status = _between(API, "productResearchStatus(runId)", "saveCreativeBriefDraft")
    save = _between(API, "  saveCreativeBriefDraft(runId", "  approveCreativeBrief(draftId")
    approve = _between(API, "  approveCreativeBrief(draftId", "  requireResearchRunId")
    invoke = _between(API, "async invokeProductResearch", "recordMetric(snapshot)")
    assert 'action: "analyze"' in start
    assert "research_id: runId" in start
    assert "onRunCreated({ id: runId" in start
    assert "run_id: this.requireResearchRunId(runId)" in status
    assert "title: draft?.title" in save
    assert "source_ids: draft?.source_ids" in save
    assert "task_blueprint: draft?.task_blueprint" in save
    assert "draft_id: normalizedDraftId" in approve
    assert "body: payload" in invoke
    assert "body: this.withOrganization(payload)" not in invoke


def test_start_form_is_source_aware_paid_and_requires_human_review() -> None:
    start = _between(VIEW, "export function productResearchInputMarkup", "export function productResearchProgressMarkup")
    for field in (
        'name="product_name"',
        'name="sku"',
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
              creative_potential: { score: 74, confidence_label: "medium", summary: "Есть потенциал" },
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
          sourceClaim: normalized.sources[0].claim,
          scenarioEditors: (html.match(/class="product-research-scenario"/g) || []).length,
          disclaimer: html.includes("не гарантирует просмотры или продажи"),
          sourceLinkSafe: html.includes('rel="noopener noreferrer nofollow"'),
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
        "sourceClaim": "Вес 900 г",
        "scenarioEditors": 3,
        "disclaimer": True,
        "sourceLinkSafe": True,
    }


def test_approval_saves_a_new_version_before_creating_tasks() -> None:
    submit = _between(APP, "async function submitProductResearchBrief", "function mergeProductResearchBrief")
    blueprint = _between(APP, "function productResearchTaskBlueprint", "function splitResearchLines")
    assert "saveCreativeBriefDraft" in submit
    assert "approveCreativeBrief" in submit
    assert submit.index("saveCreativeBriefDraft") < submit.index("approveCreativeBrief")
    assert 'form.elements.approve_ack?.checked !== true' in submit
    assert 'state.sections.tasks.status = "idle"' in submit
    assert "product_research_approved" in submit
    assert 'task_type: "general"' in blueprint
    assert "assignee_id: scenario.assignee_id" in blueprint


def test_research_run_and_approval_recover_after_reload() -> None:
    assert "persistProductResearchRunId(run?.id)" in APP
    assert "restoreProductResearchSession()" in APP
    assert "window.sessionStorage.getItem(key)" in APP
    assert "state.api.productResearchStatus(runId)" in APP
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
        'html[data-portal-theme="altea-dark"]',
        "@media (max-width: 820px)",
        "@media (max-width: 560px)",
        "@media (prefers-reduced-motion: reduce)",
        ".product-research-scenarios",
        ".product-research-score-ring",
    ):
        assert contract in CSS
