from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"


def source(name: str) -> str:
    return (APP / name).read_text(encoding="utf-8")


def test_reference_visual_layer_is_loaded_after_the_canonical_desktop_shell() -> None:
    index = source("index.html")
    canonical = 'href="./workspace-os-v4.css'
    reference = 'href="./workspace-ui-reference-v1.css'

    assert canonical in index
    assert reference in index
    assert index.index(canonical) < index.index(reference)


def test_home_desktop_has_a_command_centre_and_human_in_the_loop_ai_centre() -> None:
    desktop = source("workspace-os-v4.js")

    assert 'className = "ce-v4-desktop-command"' not in desktop
    assert 'create("section", "ce-v4-desktop-command")' in desktop
    assert 'create("aside", "ce-v4-desktop-assistant")' in desktop
    assert "ИИ предлагает. Человек решает." in desktop
    assert "Поправить вручную" in desktop
    assert "Подтвердить применение" in desktop
    assert "desktop.append(desktopCommandCenter(snapshot), desktopAssistant(snapshot))" in desktop


def test_each_strategy_is_exposed_as_one_semantic_subform_module() -> None:
    view = source("generation-strategy-view.js")
    guided = source("workspace-os-v4-generation-guided.js")

    # The pure view projects the server catalog; it must not duplicate the
    # canonical strategy IDs or labels as another client-side authority.
    assert "const EXPECTED_STRATEGY_COUNT = 3" in view
    assert "strategyCardMarkup(strategy, state.selected_strategy_id, moduleIndex)" in view
    assert 'data-generation-strategy-module="${escapeHtml(strategy.strategy_id)}"' in view
    assert 'data-state="${selected ? "selected"' in view
    assert "fieldset.dataset.generationStrategyModule = row.strategy_id" in guided
    assert "brief.dataset.generationStrategyForm = strategyId" in guided
    assert "fieldset.dataset.generationStrategyForm = row.strategy_id" in guided
    assert 'fieldset.dataset.state = "editing"' in guided
    assert "setStrategyModuleState(form, \"loading\")" in guided
    assert "setStrategyModuleState(form, \"blocked\")" in guided
    # Готовность строже, чем «файлы на месте»: модуль обязан знать про маршрут
    # и про роли, которые форма собрать не умеет. Раньше здесь было прибито
    # выражение `missing.length || incompleteSources ? "blocked" : "ready"` —
    # оно и было тем самым враньём: «готово» показывалось стратегии без единого
    # исполнимого маршрута.
    #
    # Поведение проверяется исполняемо в
    # tests/test_generation_strategy_module_readiness_v1.py; здесь остаётся
    # только связь модуля с этими решениями.
    assert 'setStrategyModuleState(form, notReady ? "blocked" : "ready")' in guided
    assert "strategyRouteUnavailable(" in guided
    assert "strategyUnsupportedRequiredRoles(" in guided
    assert "productShort" in guided

    # There is still exactly one protected authority form. Strategy modules are
    # subforms/fieldsets and therefore cannot create a second paid submit path.
    assert source("app.js").count('<form id="mock-batch-form"') == 1
    assert "<form" not in view


def test_each_selected_model_gets_its_own_server_catalog_profile() -> None:
    guided = source("workspace-os-v4-generation-guided.js")

    assert 'section.dataset.provider = String(model.provider || "")' in guided
    assert 'section.dataset.model = String(model.model || "")' in guided
    assert 'section.dataset.contentKind = String(model.contentKind || "")' in guided
    assert 'section.dataset.profileState = "ready"' in guided
    assert "section.dataset.generationModelForm = nextKey" in guided
    assert "brief.maxLength = exactPromptLimit" in guided
    assert "const promptTooLong = promptLength > exactPromptLimit" in guided
    assert 'section.dataset.profileState = profileBlocked ? "blocked" : "ready"' in guided
    assert "ПРОФИЛЬ ВЫБРАННОЙ МОДЕЛИ" in guided
    assert "Авторитет: серверный каталог" in guided
    assert "Лимит инструкции — ${exactPromptLimit} знаков." in guided


def test_ai_centre_recommendation_technical_selection_and_local_template_are_distinct() -> None:
    guided = source("workspace-os-v4-generation-guided.js")
    intake = source("generation-strategy-intake-v4.js")

    assert "Технический подбор модели" in guided
    assert "Система сравнивает совместимость" in guided
    assert "DEFAULT_BRIEF_TEMPLATES" in intake
    assert "Локальный шаблон, не рекомендация ИИ-центра." in intake
    assert "Вставить базовый шаблон" in intake
    assert "function prefillCopyRecommendation" not in intake


def test_unverified_ai_centre_lineage_cannot_silently_prefill_the_brief() -> None:
    guided = source("workspace-os-v4-generation-guided.js")
    start = guided.index("function intakeHandoffCanPrefillBrief")
    end = guided.index("function normalizeIntakeHandoff", start)
    guard = guided[start:end]

    assert "ai_center_unverified" not in guard
    assert "ai_center" in guard
    assert "ai_center_edited" in guard
    assert "operator" in guard


def test_reference_css_uses_live_data_hooks_and_keeps_the_ai_human_color_split() -> None:
    css = source("workspace-ui-reference-v1.css")

    assert css.count("body.contentengine-desktop-v4") > 500
    assert '.ce-v4-model-card[data-recommended="true"]' in css
    assert '.gi-tab[data-state="active"]' in css
    assert '.gi-chip[data-recommended="true"]' in css
    assert '[data-generation-strategy-module="viral_product_swap"]' in css
    assert '[data-generation-strategy-module="viral_avatar_ugc"]' in css
    assert '[data-generation-strategy-module="viral_rebuild"]' in css
    assert '[data-source="ai_center_unverified"]' in css
    assert "--ce-ref-violet: #b08cfc" in css
    assert "--ce-ref-gold: #fdd06e" in css


def test_reference_visual_layer_never_shrinks_interface_copy_below_twelve_pixels() -> None:
    css = source("workspace-ui-reference-v1.css")
    declared_sizes = [
        float(match.group(1))
        for match in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", css)
    ]

    assert declared_sizes
    assert min(declared_sizes) >= 12


def test_inactive_window_snapshots_have_route_aware_static_layouts() -> None:
    css = source("workspace-ui-reference-v1.css")

    for marker in (
        ".ce-v4-window__snapshot",
        '.ce-v4-window__snapshot[data-ce-v4-window-snapshot-kind="finder"]',
        '.ce-v4-window__snapshot[data-ce-v4-window-snapshot-kind="stats"]',
        '.ce-v4-window__snapshot[data-ce-v4-window-snapshot-kind="review"]',
        '.ce-v4-window__snapshot[data-ce-v4-window-snapshot-kind="generation"]',
        '.ce-v4-window__snapshot[data-ce-v4-window-snapshot-kind="ai"]',
        ".ce-v4-window__snapshot-grid",
        ".ce-v4-window__snapshot-sidebar",
        ".ce-v4-window__snapshot-inspector",
    ):
        assert marker in css

    assert css.count("{") == css.count("}")
