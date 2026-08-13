from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
PORTAL_EXPERIENCE = (ROOT / "web/app/portal-experience.js").read_text(
    encoding="utf-8"
)


def _function_source(name: str, *, asynchronous: bool = False) -> str:
    prefix = "async function" if asynchronous else "function"
    start = APP.index(f"{prefix} {name}(")
    candidates = [
        position
        for position in (
            APP.find("\nfunction ", start + 1),
            APP.find("\nasync function ", start + 1),
        )
        if position >= 0
    ]
    end = min(candidates) if candidates else len(APP)
    return APP[start:end]


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the final product flow contract")
    result = subprocess.run(
        [node, "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_academy_dispatch_executes_first_shift_and_account_launch_routes() -> None:
    render = _function_source("render")
    payload = _run_node(
        f"""
        const calls = [];
        const state = {{
          authLinkError: null,
          session: true,
          forcePassword: false,
          bootstrapStatus: "ready",
          route: {{ path: "/learn" }},
        }};
        function closeTrainingAchievement() {{}}
        function stopAllTrainingWalkthroughs() {{}}
        function destroyAccountVisualController() {{}}
        function membershipLockDetails() {{ return null; }}
        function isAdminRoute() {{ return false; }}
        function canManageTeam() {{ return false; }}
        function academyRequired() {{ return true; }}
        function navigate(path) {{ calls.push(["navigate", path]); }}
        function renderLearningHome() {{ calls.push(["home"]); }}
        function renderFirstShift() {{ calls.push(["first-shift"]); }}
        function renderAccountLaunch(slug) {{ calls.push(["account", slug]); }}
        function renderTrainingPracticalProject() {{ calls.push(["practical"]); }}
        function renderExam() {{ calls.push(["exam"]); }}
        function renderCourse(code) {{ calls.push(["course", code]); }}
        function accountLaunchSlugFromPath(path) {{
          const normalized = String(path).replace(/\\/+$/u, "");
          if (normalized === "/learn/accounts") return "";
          const match = normalized.match(/^\\/learn\\/accounts\\/(instagram|youtube|vk)$/u);
          return match?.[1] || null;
        }}
        {render}
        for (const path of [
          "/learn/first-shift",
          "/learn/accounts",
          "/learn/accounts/youtube",
        ]) {{
          state.route.path = path;
          render();
        }}
        process.stdout.write(JSON.stringify({{ calls }}));
        """
    )

    assert payload["calls"] == [
        ["first-shift"],
        ["account", ""],
        ["account", "youtube"],
    ]


def test_learning_home_executes_one_primary_action_and_compact_role_select() -> None:
    role_markup = _function_source("learningGateRoleMarkup")
    learning_home = _function_source("renderLearningHome")
    handle_change = _function_source("handleChange")
    payload = _run_node(
        f"""
        const LEARNING_TRACKS = {{
          all: {{ id: "all", shortLabel: "Весь процесс", description: "Общий маршрут" }},
          ai: {{ id: "ai", shortLabel: "AI-креатор", description: "Создание контента" }},
        }};
        const state = {{
          bootstrap: {{ training: {{ completedModules: [], practicalProject: {{}}, exam: {{ passed: false }} }} }},
        }};
        let html = "";
        const events = [];
        function escapeHtml(value) {{ return String(value); }}
        function normalizeLearningTrack(value) {{ return LEARNING_TRACKS[value] ? value : "all"; }}
        function restoreLearningTrack() {{ return "ai"; }}
        function learningCourses() {{ return [{{ code: "intro", title: "Первый блок" }}]; }}
        function normalizeTrainingPracticalProject() {{ return {{ approved: false, status: "not_started" }}; }}
        function trainingCatalogReady() {{ return true; }}
        function hasWorkspaceAccess() {{ return false; }}
        function hasOperationalWorkspaceRole() {{ return false; }}
        function renderLearningScaffold(content) {{ html = content; }}
        {role_markup}
        {learning_home}
        renderLearningHome();

        function handleFormActivity() {{}}
        function persistLearningTrack(value) {{ events.push(["persist", value]); return value; }}
        function track(name, detail) {{ events.push([name, detail.learning_track]); }}
        const document = {{ querySelector: () => ({{ focus: () => events.push(["focus"]) }}) }};
        const window = {{ queueMicrotask: (callback) => callback() }};
        const event = {{ target: {{
          value: "all",
          matches: (selector) => selector === "[data-learning-track-select]",
        }} }};
        {handle_change}
        handleChange(event);

        const role = learningGateRoleMarkup("ai");
        process.stdout.write(JSON.stringify({{
          primaryCount: (html.match(/data-primary-action="true"/g) || []).length,
          roleBeforeRoadmap: html.indexOf("data-learning-gate-role") < html.indexOf("learning-gate-roadmap"),
          roleLabelCount: (role.match(/<label\\b/g) || []).length,
          roleSelectCount: (role.match(/<select\\b/g) || []).length,
          roleActionCount: (role.match(/<(?:a|button)\\b/g) || []).length,
          selected: role.includes('value="ai" selected'),
          events,
        }}));
        """
    )

    assert payload == {
        "primaryCount": 1,
        "roleBeforeRoadmap": True,
        "roleLabelCount": 1,
        "roleSelectCount": 1,
        "roleActionCount": 0,
        "selected": True,
        "events": [
            ["persist", "all"],
            ["focus"],
            ["training_track_selected", "all"],
        ],
    }


def test_academy_reachability_controls_every_workspace_learning_link() -> None:
    academy_required = _function_source("academyRequired")
    academy_reachable = _function_source("academyRoutesReachable")
    page_header = _function_source("pageHeader")
    repair = _function_source("generationRepairMarkup")
    learning = _function_source("generationLearningMarkup")
    payload = _run_node(
        f"""
            let locked = false;
            const window = {{ CONTENTENGINE_DESKTOP_V4: false }};
            const state = {{ bootstrap: null, route: {{ path: "/workspace/generation" }} }};
        function membershipLockDetails() {{ return locked ? {{ reason: "locked" }} : null; }}
        function escapeHtml(value) {{ return String(value); }}
        const WORKSPACE_SECTION_META = {{ generation: {{
          kicker: "Шаг", note: "Один результат", guideHref: "#/learn/video",
        }} }};
        const FACTORY_FLOW = [];
        function factoryFlowStage() {{ return null; }}
        function factoryFlowMarkup() {{ return ""; }}
        function workspaceDirectionMarkup() {{ return ""; }}
        {academy_required}
        {academy_reachable}
        {page_header}
        const cases = [
          {{ accessState: "learning", training: {{ accessWaiver: {{ active: false }} }} }},
          {{ accessState: "learning", training: {{ accessWaiver: {{ active: true }} }} }},
          {{ accessState: "workspace_open", training: {{ accessWaiver: {{ active: false }} }} }},
        ].map((bootstrap) => {{ state.bootstrap = bootstrap; return academyRoutesReachable(); }});
        state.bootstrap = {{ accessState: "learning", training: {{ accessWaiver: {{ active: false }} }} }};
        const requiredHeader = pageHeader("Создание", "Один шаг");
        state.bootstrap = {{ accessState: "workspace_open", training: {{ accessWaiver: {{ active: false }} }} }};
        const completedHeader = pageHeader("Создание", "Один шаг");
        process.stdout.write(JSON.stringify({{
          cases,
          requiredGuide: requiredHeader.includes("#/learn/video"),
          completedGuide: completedHeader.includes("#/learn/video"),
        }}));
        """
    )

    assert payload == {
        "cases": [True, False, False],
        "requiredGuide": True,
        "completedGuide": False,
    }
    for source in (repair, learning):
        assert "academyRoutesReachable()" in source
        assert "trainingAccessWaiverActive()" not in source


def test_course_completion_hands_off_to_the_next_required_academy_action() -> None:
    click = _function_source("handleClick", asynchronous=True)
    start = click.index('if (action === "complete-course")')
    end = click.index('if (action === "refresh-section")', start)
    completion = click[start:end]

    checkpoints = [
        "await state.api.completeModule(moduleCode)",
        "await loadBootstrap()",
        "if (!serverCompleted) throw new Error",
        "const nextCourse",
        "const destination = nextCourse",
        "await flowHandoff(",
    ]
    assert all(checkpoint in completion for checkpoint in checkpoints)
    assert [completion.index(checkpoint) for checkpoint in checkpoints] == sorted(
        completion.index(checkpoint) for checkpoint in checkpoints
    )
    assert "showTrainingAchievement" not in completion
    assert "celebration" not in completion
    assert "training_achievement_unlocked" not in completion
    assert 'navigate("/learn", true)' not in completion
    assert '"/learn/practical"' in completion


def test_generation_archive_executes_browse_and_exact_job_modes() -> None:
    archive_markup = _function_source("generationArchiveMarkup")
    archive_card = _function_source("generationArchiveCardMarkup")
    generation_table = _function_source("generationTable")
    generation_section = _function_source("renderGenerationSection")
    payload = _run_node(
        f"""
        const GENERATION_VISIBLE_CAP = 200;
        const GENERATION_VISIBLE_STEP = 20;
        const GENERATION_ARCHIVE_PAGE_SIZE = 50;
        const state = {{ generationArchive: {{
          loading: false, loadingMore: false, serverLoaded: true,
          error: "", exhausted: true,
        }} }};
        function escapeHtml(value) {{ return String(value); }}
        function formatNumber(value) {{ return String(value); }}
        function generationWeekLabel() {{ return "2026-W31"; }}
        function generationBatchDetails() {{ return {{
          real: true, jobId: "job-1", status: "succeeded", failureCode: "",
          photo: false, duration: 5, audio: false, parameters: {{}},
          reconciliationRequired: false, transientError: "", checkedAt: null,
        }}; }}
        function generationFailureMessage() {{ return ""; }}
        function trustedCachedGenerationUrl() {{ return "https://cdn.example/result.mp4"; }}
        function generationActionsMarkup() {{ return '<button data-generation-mutation>Скачать</button>'; }}
        function generationVideoReferenceLineageMarkup() {{ return '<div data-generation-reference>Reference</div>'; }}
        function generatedVideoTechnicalQaMarkup() {{ return '<div data-generation-qa>QA</div>'; }}
        function generationStageMarkup() {{ return "Готово"; }}
        function generationCostMarkup() {{ return "10 ₽"; }}
        function formatDate() {{ return "03.08.2026"; }}
        function statusBadge() {{ return "Готово"; }}
        {generation_table}
        {archive_markup}
        const item = {{ id: "batch-1", name: "Запуск", sku: "SKU-1", created_at: "2026-08-03" }};
        const filters = {{ visible: 20, period: "4w", status: "all", query: "" }};
        const browse = generationArchiveMarkup([item], [item], [item], filters, false);
        const exact = generationArchiveMarkup([item], [item], [item], filters, true);
        const missing = generationArchiveMarkup([item], [], [], filters, true);
        process.stdout.write(JSON.stringify({{
          browseMode: browse.includes('data-generation-archive-mode="browse"'),
          browseFilter: browse.includes('id="generation-archive-filter-form"'),
          browseOpenCount: (browse.match(/job=job-1/g) || []).length,
          browseMutation: browse.includes("data-generation-mutation"),
          browseQa: browse.includes("data-generation-qa"),
          browsePreview: browse.includes("<video"),
          exactMode: exact.includes('data-generation-archive-mode="exact"'),
          exactFilter: exact.includes('id="generation-archive-filter-form"'),
          exactMutation: exact.includes("data-generation-mutation"),
          exactQa: exact.includes("data-generation-qa"),
          exactPreview: exact.includes("<video"),
          missingFailClosed: missing.includes("Запуск по этой ссылке не найден")
            && missing.includes("не открыл другой запуск"),
        }}));
        """
    )

    assert payload == {
        "browseMode": True,
        "browseFilter": True,
        "browseOpenCount": 1,
        "browseMutation": False,
        "browseQa": False,
        "browsePreview": False,
        "exactMode": True,
        "exactFilter": False,
        "exactMutation": True,
        "exactQa": True,
        "exactPreview": True,
        "missingFailClosed": True,
    }
    assert "generationArchiveCardMarkup(sectionState)" in generation_section
    assert 'safeWorkspaceRouteEntityId("job")' in archive_card
    assert "generationBatchDetails(item).jobId === routeJobId" in archive_card
    assert "routeFilteredBatches.slice(0, filters.visible)" in archive_card
    assert "Boolean(routeJobId)" in archive_card
    assert "export const GENERATION_VISIBLE_STEP = 20" in PORTAL_EXPERIENCE
    assert "export const GENERATION_VISIBLE_CAP = 200" in PORTAL_EXPERIENCE


def test_manager_health_executes_without_budget_or_campaign_markup() -> None:
    health = _function_source("managerDashboardSectionMarkup")
    payload = _run_node(
        f"""
        const state = {{
          managerDashboard: {{ status: "ready", data: {{ queue: [] }} }},
          generationSpend: {{ status: "ready" }},
          operationalHealth: {{ status: "ready" }},
        }};
        function managerDashboardMarkup() {{ return '<section data-health>HEALTH</section>'; }}
        function managerOperationalHealthMarkup() {{ return '<section data-operational>OPS</section>'; }}
        function managerGenerationSpendMarkup() {{ return '<section data-spend>SPEND</section>'; }}
        function canManageGenerationSpendPolicy() {{ return true; }}
        function alertMarkup() {{ return "ALERT"; }}
        {health}
        const ready = managerDashboardSectionMarkup();
        state.managerDashboard = {{ status: "loading", data: null }};
        const loading = managerDashboardSectionMarkup();
        process.stdout.write(JSON.stringify({{
          readyHealth: ready.includes("data-health"),
          readySpend: ready.includes("data-spend"),
          loadingHealth: loading.includes("manager-dashboard-loading"),
          loadingSpend: loading.includes("data-spend"),
        }}));
        """
    )

    assert payload == {
        "readyHealth": True,
        "readySpend": False,
        "loadingHealth": True,
        "loadingSpend": False,
    }
    assert "managerGenerationSpendMarkup" not in health
    assert "generationSpend" not in health
