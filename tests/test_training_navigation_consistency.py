from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web/app/catalog.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_learning_and_workspace_process_maps_share_the_same_seven_steps() -> None:
    flow = _between(APP, "const FACTORY_FLOW", "const HOME_SECTION_KEYS")
    portal = _between(APP, "function portalWorkflowMarkup", "function courseCardMarkup")
    learning_home = _between(APP, "function renderLearningHome", "function renderAccountLaunch")
    workspace_home = _between(APP, "function renderHomeSection", "function realGenerationSku")
    factory_header = _between(APP, "function factoryFlowMarkup", "function sectionBody")

    assert re.findall(r'key:\s*"([a-z]+)"', flow) == [
        "media",
        "generation",
        "review",
        "tasks",
        "placement",
        "stats",
        "payouts",
    ]
    assert flow.count("learning:") == 7
    assert "FACTORY_FLOW.map((item, index)" in portal
    assert "const steps = [" not in portal
    assert portal.count("FACTORY_FLOW.length") >= 2
    assert "--workflow-step-count:${FACTORY_FLOW.length}" in portal
    assert "Один товар проходит ${FACTORY_FLOW.length} понятных этапов" in learning_home
    assert "по ${FACTORY_FLOW.length} рабочим этапам" in learning_home
    assert "<h2>${FACTORY_FLOW.length} этапов одного результата</h2>" in workspace_home
    assert "--workflow-step-count:${FACTORY_FLOW.length}" in workspace_home
    assert "--workflow-step-count:${FACTORY_FLOW.length}" in factory_header
    assert "шесть понятных этапов" not in APP
    assert "по шести рабочим этапам" not in APP
    assert STYLES.count(
        "repeat(var(--workflow-step-count, 7), minmax(0, 1fr))"
    ) == 3


def test_post_exam_role_gate_names_the_manager_action_and_keeps_practice_secondary() -> None:
    learning_home = _between(APP, "function renderLearningHome", "function renderAccountLaunch")
    exam = _between(APP, "function renderExam", "function questionMarkup")
    learning_scaffold = _between(APP, "function learningScaffold", "function renderWorkspace")
    submit_exam = _between(APP, "async function submitExam", "async function submitGenerationBatch")

    assert "Экзамен сдан — рабочую роль назначает руководитель" in learning_home
    assert "Руководитель команды должен назначить вам рабочую роль" in learning_home
    assert "учебная смена ниже остаётся необязательной тренировкой" in learning_home
    assert 'data-action="retry-bootstrap"' in learning_home
    assert 'const nextHref = rolePending\n    ? "#/learn"' in learning_home
    assert 'const nextHref = rolePending\n    ? "#/learn/first-shift"' not in learning_home

    assert "const workspaceReady = hasWorkspaceAccess();" in exam
    assert "Экзамен сдан — роль назначает руководитель" in exam
    assert "учебная смена остаётся дополнительной тренировкой" in exam
    assert exam.index('data-action="retry-bootstrap"') < exam.index(
        'href="#/learn/first-shift"'
    )
    assert "Роль назначает руководитель" in learning_scaffold
    assert (
        "Теперь руководитель должен назначить вам рабочую роль."
        in submit_exam
    )


def test_simple_and_all_tools_navigation_modes_are_persistent_and_non_destructive() -> None:
    simple_keys = _between(
        CATALOG,
        "export const SIMPLE_WORKSPACE_TAB_KEYS",
        "]);",
    )
    navigation_tabs = _between(
        APP,
        "function workspaceNavigationTabs",
        "function brandMarkup",
    )
    scaffold = _between(APP, "function workspaceScaffold", "function canManageTeam")
    mobile = _between(APP, "function mobileNavMarkup", "async function loadSection")
    picker = _between(
        APP,
        "function navigationModePickerMarkup",
        "function applyPortalTheme",
    )
    apply_mode = _between(
        APP,
        "function applyNavigationMode",
        "function sidebarFooterMarkup",
    )
    route_gate = _between(APP, "function render()", "function renderLogin")

    assert 'id: "simple"' in CATALOG
    assert 'label: "Простой"' in CATALOG
    assert 'id: "all"' in CATALOG
    assert 'label: "Все инструменты"' in CATALOG
    assert 'NAVIGATION_MODE_STORAGE_KEY = "contentengine.navigation-mode.v1"' in CATALOG
    for key in (
        "home",
        "media",
        "generation",
        "review",
        "tasks",
        "placement",
        "stats",
        "payouts",
    ):
        assert f'"{key}"' in simple_keys
    for advanced_key in ("board", "research", "feedback", "team"):
        assert f'"{advanced_key}"' not in simple_keys

    assert 'state.navigationMode === "all"' in navigation_tabs
    assert "simpleKeys.has(key) || key === activeSection" in navigation_tabs
    assert "workspaceNavigationTabs(activeSection)" in scaffold
    assert "workspaceNavigationTabs(activeSection).map" in mobile
    assert "visibleWorkspaceTabs().some" in route_gate
    assert "workspaceNavigationTabs().some" not in route_gate

    assert 'data-action="set-navigation-mode"' in picker
    assert 'aria-label="Режим рабочего меню"' in picker
    assert "aria-pressed=" in picker
    assert "NAVIGATION_MODE_STORAGE_KEY" in apply_mode
    assert "safeStorageSet(" in apply_mode
    assert "document.documentElement.dataset.navigationMode" in apply_mode
    assert 'action === "set-navigation-mode"' in APP
    assert "event.key === NAVIGATION_MODE_STORAGE_KEY" in APP

    for selector in (
        ".navigation-mode-picker",
        ".navigation-mode-options",
        ".navigation-mode-option",
        ".navigation-mode-option:focus-visible",
    ):
        assert selector in STYLES
    assert "min-height: 44px" in _between(
        STYLES,
        ".navigation-mode-option {",
        ".navigation-mode-option:hover",
    )
