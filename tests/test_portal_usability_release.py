import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
EXPERIENCE = (ROOT / "web" / "app" / "portal-experience.js").read_text(encoding="utf-8")
EXPERIENCE_CSS = (ROOT / "web" / "app" / "portal-experience.css").read_text(encoding="utf-8")
STYLES = (ROOT / "web" / "app" / "styles.css").read_text(encoding="utf-8")
THEME_BOOTSTRAP = (ROOT / "web" / "app" / "theme-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")
INTERFACE_SYSTEM = (ROOT / "web" / "app" / "interface-system.css").read_text(encoding="utf-8")


def _node() -> str:
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("Node.js is required for executable portal contracts")
    return executable


def _run_module_javascript(body: str) -> dict:
    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "subject.mjs").write_text(EXPERIENCE, encoding="utf-8")
        (module_directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const payload = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [_node(), "contract.mjs"],
            cwd=module_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _run_theme_bootstrap() -> dict:
    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "subject.js").write_text(THEME_BOOTSTRAP, encoding="utf-8")
        (module_directory / "contract.mjs").write_text(
            """
            import { readFileSync } from "node:fs";
            import { runInNewContext } from "node:vm";

            const source = readFileSync("./subject.js", "utf8");
            function apply(saved, blocked = false) {
              const dataset = {};
              let browserColor = "";
              const context = {
                window: {
                  localStorage: {
                    getItem: () => {
                      if (blocked) throw new Error("blocked");
                      return saved;
                    },
                  },
                },
                document: {
                  documentElement: { dataset },
                  querySelector: () => ({
                    setAttribute: (_name, value) => { browserColor = value; },
                  }),
                },
                Set,
                String,
              };
              runInNewContext(source, context);
              return { theme: dataset.portalTheme, browserColor };
            }

            process.stdout.write(JSON.stringify({
              dark: apply("OBSIDIAN"),
              unknown: apply("unsafe-theme"),
              blocked: apply(null, true),
            }));
            """,
            encoding="utf-8",
        )
        result = subprocess.run(
            [_node(), "contract.mjs"],
            cwd=module_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _dark_theme_tokens() -> dict[str, str]:
    match = re.search(
        r':root\[data-portal-theme="obsidian"\]\s*\{(?P<body>.*?)\n\}',
        INTERFACE_SYSTEM,
        flags=re.DOTALL,
    )
    assert match is not None, "The obsidian token block is missing"
    return {
        name.removeprefix("portal-"): value
        for name, value in re.findall(
            r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;",
            match.group("body"),
        )
    }


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_obsidian_theme_is_the_safe_normalized_product_palette() -> None:
    result = _run_module_javascript(
        """
        const writes = [];
        const storage = {
          getItem: () => "OBSIDIAN",
          setItem: (key, value) => writes.push([key, value]),
        };
        return {
          ids: subject.PORTAL_THEMES.map((theme) => theme.id),
          normalized: subject.normalizePortalTheme("  OBSIDIAN  "),
          read: subject.readPortalThemePreference(storage),
          persisted: subject.persistPortalThemePreference("obsidian", storage),
          fallback: subject.normalizePortalTheme("dark-but-unregistered"),
          writes,
        };
        """
    )

    assert result == {
        "ids": ["obsidian"],
        "normalized": "obsidian",
        "read": "obsidian",
        "persisted": "obsidian",
        "fallback": "obsidian",
        "writes": [["contentengine.portal-theme.v1", "obsidian"]],
    }


def test_prepaint_theme_bootstrap_supports_and_fails_open_to_obsidian() -> None:
    assert _run_theme_bootstrap() == {
        "dark": {"theme": "obsidian", "browserColor": "#0b0908"},
        "unknown": {"theme": "obsidian", "browserColor": "#0b0908"},
        "blocked": {"theme": "obsidian", "browserColor": "#0b0908"},
    }
    assert INDEX.index("theme-bootstrap.js") < INDEX.index("portal-experience.css")


def test_dark_palette_meets_core_wcag_contrast_budgets() -> None:
    tokens = _dark_theme_tokens()
    required_tokens = {
        "canvas",
        "surface",
        "surface-soft",
        "ink",
        "ink-soft",
        "action-bg",
        "action-ink",
        "link",
        "accent-ink",
        "danger-ink",
        "danger-bg",
        "warning-ink",
        "warning-bg",
        "success-ink",
        "success-bg",
        "info-ink",
        "info-bg",
    }
    assert required_tokens <= tokens.keys()
    assert "color-scheme: dark" in _between(
        INTERFACE_SYSTEM,
        ':root[data-portal-theme="obsidian"]',
        "html[data-portal-theme=\"obsidian\"] body",
    )
    assert _relative_luminance(tokens["canvas"]) < 0.03
    assert _relative_luminance(tokens["surface"]) < 0.04

    text_pairs = (
        ("ink", "surface"),
        ("ink-soft", "surface"),
        ("action-ink", "action-bg"),
        ("link", "canvas"),
        ("link", "surface-soft"),
        ("accent-ink", "surface"),
        ("danger-ink", "danger-bg"),
        ("warning-ink", "warning-bg"),
        ("success-ink", "success-bg"),
        ("info-ink", "info-bg"),
    )
    failures = {
        f"{foreground}/{background}": _contrast_ratio(tokens[foreground], tokens[background])
        for foreground, background in text_pairs
        if _contrast_ratio(tokens[foreground], tokens[background]) < 4.5
    }
    assert failures == {}


def test_obsidian_browser_chrome_and_mobile_shell_are_wired() -> None:
    picker = _between(APP, "function themePickerMarkup", "function applyPortalTheme")
    theme_application = _between(APP, "function applyPortalTheme", "function sidebarFooterMarkup")

    assert 'role="group"' in picker
    assert 'aria-label="Оформление портала"' in picker
    assert 'data-theme-value="${escapeHtml(theme.id)}"' in picker
    assert 'aria-pressed="${state.portalTheme === theme.id ? "true" : "false"}"' in picker
    assert 'obsidian: "#0b0908"' in theme_application
    assert "meta[name=\"theme-color\"]" in theme_application
    assert "browserColors" in THEME_BOOTSTRAP
    assert 'obsidian: "#0b0908"' in THEME_BOOTSTRAP
    assert ".workspace-contextbar" in INTERFACE_SYSTEM
    assert "linear-gradient(145deg, #ee955b, #d4642b 76%)" in INTERFACE_SYSTEM
    assert ".mobile-nav-trigger { width: 44px; height: 44px; }" in EXPERIENCE_CSS


def test_interface_scales_fluidly_and_motion_stays_accessible() -> None:
    for marker in (
        "--page-gutter: clamp(28px, 4vw, 72px)",
        "@media (min-width: 1500px)",
        "font-size: clamp(16px, 0.9vw, 19px)",
        "--sidebar-width: clamp(320px, 17vw, 344px)",
        "--content-max: 1840px",
        "@media (min-width: 2200px)",
        "--content-max: 1960px",
        "@media (max-width: 820px)",
        "width: 100%",
    ):
        assert marker in INTERFACE_SYSTEM

    for marker in (
        "@media (prefers-reduced-motion: no-preference)",
        "luxe-page-enter",
        "luxe-surface-enter",
        "luxe-sidebar-enter",
        "luxe-grid-drift",
        "luxe-glow-drift",
        "luxe-drawer-enter",
        "luxe-toast-enter",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
        "animation-iteration-count: 1 !important",
        "scroll-behavior: auto !important",
    ):
        assert marker in INTERFACE_SYSTEM

    assert "./interface-system.css?v=20260730.9" in INDEX


def test_login_error_keeps_safe_email_context_and_moves_focus_to_password() -> None:
    login = _between(APP, "function renderLogin", "function renderResetRequest")
    submit_login = _between(APP, "async function submitLogin", "async function submitReset")

    assert 'function renderLogin(message = "", rememberedEmail = "")' in login
    assert 'value="${escapeHtml(rememberedEmail)}"' in login
    assert '<details class="auth-access-guide">' in login
    assert "message ? '#login-form input[name=\"password\"]' : \"#login-form input\"" in login
    assert "renderLogin(authErrorMessage(error), email)" in submit_login
    assert 'input name="password"' in login
    assert "rememberedPassword" not in login
    assert ".auth-access-guide summary" in STYLES
    assert "min-height: 46px" in _between(STYLES, ".auth-access-guide summary", ".auth-access-guide summary::-webkit-details-marker")


def test_login_timeout_explains_service_restart_without_blaming_credentials() -> None:
    submit_login = _between(APP, "async function submitLogin", "async function submitReset")
    error_mapper = _between(APP, "function authErrorMessage", "function actionErrorMessage")

    assert "const AUTH_SERVICE_UNAVAILABLE_MESSAGE =" in APP
    assert "Сервис входа временно недоступен или перезапускается" in APP
    assert "Аккаунт и пароль не изменены" in APP
    assert "AUTH_SERVICE_UNAVAILABLE_MESSAGE" in submit_login
    assert 'error?.code === "ui_timeout"' in error_mapper


def test_password_reset_copy_describes_the_actual_two_step_flow() -> None:
    reset = _between(APP, "function renderResetRequest", "function renderAuthLinkError")

    assert "Получите ссылку для нового пароля" in reset
    assert "Новый пароль вы зададите после перехода" in reset
    assert "Получить ссылку" in reset
    assert "<h2 id=\"reset-title\">Задайте новый пароль</h2>" not in reset


def test_workspace_rerender_preserves_control_identity_selection_and_focus() -> None:
    workspace = _between(APP, "function renderWorkspace", "function workspaceInitialLoadingMarkup")

    assert workspace.index("captureWorkspaceFocus(existingContent)") < workspace.index("existingContent.innerHTML = content")
    assert workspace.index("existingContent.innerHTML = content") < workspace.index(
        "restoreWorkspaceFocus(existingContent, focusedControl, section)"
    )
    for identity_hook in (
        "active.id",
        "active.dataset?.action",
        'active.getAttribute?.("name")',
        "active.dataset?.jobId",
        "active.dataset?.outputAction",
        "workspaceFormKey(active.form",
        "active.value",
        "active.selectionStart",
        "active.selectionEnd",
    ):
        assert identity_hook in workspace
    assert "window.queueMicrotask" in workspace
    assert 'container.querySelector("#generation-archive-summary")' in workspace
    assert "target.focus({ preventScroll: true })" in workspace
    assert "target.setSelectionRange" in workspace
    assert "item.dataset?.jobId === identity.jobId" in workspace
    assert "formKey === identity.formKey" in workspace


def test_generation_archive_has_clear_busy_live_empty_retry_and_table_semantics() -> None:
    archive = _between(APP, "function generationArchiveMarkup", "function submitGenerationArchiveFilters")
    table = _between(APP, "function generationTable", "function renderTasksSection")

    for hook in (
        'aria-busy="${archive.loading || archive.loadingMore ? "true" : "false"}"',
        'id="generation-archive-submit"',
        'id="generation-archive-summary"',
        'tabindex="-1"',
        'aria-live="polite"',
        'aria-atomic="true"',
        'role="alert"',
        'data-action="reset-generation-filters"',
        'data-action="load-more-generation"',
        "archive.error ?",
        "generation-mobile-hint",
    ):
        assert hook in archive
    assert "Период, статус и поиск применяются на сервере ко всему архиву" in archive
    assert "Повторить загрузку истории" in archive
    assert 'disabled' in archive and "archive.loadingMore" in archive
    assert '<caption class="sr-only">Архив запусков генерации контента</caption>' in table
    assert table.count('scope="col"') == 5
    assert ".generation-mobile-hint { display: inline; }" in EXPERIENCE_CSS
    submit_filters = _between(APP, "function submitGenerationArchiveFilters", "async function loadMoreGenerationArchive")
    reset_filters = _between(APP, 'if (action === "reset-generation-filters")', 'if (action === "show-more-generation")')
    assert 'form.removeAttribute("data-dirty")' in submit_filters
    assert 'removeAttribute("data-dirty")' in reset_filters
    assert "await reloadGenerationArchive()" in submit_filters
    assert "await reloadGenerationArchive()" in reset_filters
    assert "focusGenerationArchiveSummary()" in submit_filters


def test_ready_generated_video_task_routes_decision_through_content_review() -> None:
    tasks = _between(APP, "function renderTasksSection", "function renderProductResearchSection")
    assert "Ролик готов. Откройте проверку контента" in tasks
    assert "Не принимайте и не блокируйте эту задачу напрямую." in tasks
    assert "Итог фиксируется только внутри проверки контента." in tasks
    generated_branch = _between(
        tasks,
        'if (generatedVideoReady && ["submitted", "review"].includes(status))',
        'if (status === "todo")',
    )
    assert 'action("blocked"' not in generated_branch


def test_obsidian_component_overrides_keep_controls_and_status_icons_readable() -> None:
    dark_overrides = INTERFACE_SYSTEM

    for selector in (
        ".btn-secondary",
        ".workspace-contextbar",
        ".nav-link-stage.active",
        ".alert-danger",
        ".alert-success",
    ):
        assert selector in dark_overrides

    for foreground, background in (
        ("#ffffff", "#286b59"),
        ("#ffffff", "#8b3b36"),
        ("#ffffff", "#6b4f1a"),
    ):
        assert _contrast_ratio(foreground, background) >= 4.5


def test_motion_and_touch_contracts_remain_calm_and_accessible() -> None:
    atmosphere = _between(APP, "function brandAtmosphereMarkup", "function themePickerMarkup")
    reduced_motion = INTERFACE_SYSTEM[INTERFACE_SYSTEM.rindex("@media (prefers-reduced-motion: reduce)") :]

    assert "brand-grid" in atmosphere
    assert atmosphere.count('<span class="brand-glow') == 2
    assert "pointer-events: none" in _between(EXPERIENCE_CSS, ".brand-atmosphere {", "/* Generation archive")
    assert "display: none" in reduced_motion
    assert "petal" not in atmosphere.lower()
    assert "min-height: 46px" in EXPERIENCE_CSS
    assert ".mobile-nav-trigger { width: 44px; height: 44px; }" in EXPERIENCE_CSS
    assert ".generation-archive .btn-small { min-height: 44px; }" in EXPERIENCE_CSS
