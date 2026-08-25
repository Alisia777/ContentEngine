from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
CORE_STYLES = (APP_DIR / "workspace-os-v4.css").read_text(encoding="utf-8")
BUILD = json.loads((APP_DIR / "build.json").read_text(encoding="utf-8"))["id"]
ACTIVE_INDEX = re.sub(r"<!--.*?-->", "", INDEX, flags=re.DOTALL)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_academy_uses_the_single_v44_interface_graph() -> None:
    assert BUILD == "20260823.copy-engines.65"
    assert f'./interface-system.css?v={BUILD}' in ACTIVE_INDEX
    assert './workspace-os-v4.css?v=20260823.copy-engines.65' in ACTIVE_INDEX

    assert f'./workspace-build-guard.js?v={BUILD}' in ACTIVE_INDEX
    assert './workspace-os-v4-loader.js?v=20260823.copy-engines.65' in ACTIVE_INDEX
    assert './app.js?v=20260823.copy-engines.65' in ACTIVE_INDEX

    for retired_asset in (
        "learning-premium.css",
        "learning-premium-components.css",
        "learning-premium-motion.css",
        "learning-premium.js",
    ):
        assert retired_asset not in ACTIVE_INDEX


def test_academy_is_rendered_by_the_gate_not_a_workspace_adapter() -> None:
    render = _between(APP, "function render() {", "\n}\n\nfunction renderLogin")
    academy_gate = _between(
        render,
        "if (academyRequired()) {",
        '\n  if (path === "/learn" || path.startsWith("/learn/"))',
    )

    assert "renderLearningHome()" in academy_gate
    assert "renderFirstShift()" in academy_gate
    assert "accountLaunchSlugFromPath(path)" in academy_gate
    assert "renderTrainingPracticalProject()" in academy_gate
    assert "renderExam()" in academy_gate
    assert "renderCourse(" in academy_gate
    assert "academy:" not in LOADER
    assert "workspace-academy-os-v2" not in LOADER
    assert "workspace-academy-lab-v3" not in LOADER


def test_academy_shell_has_one_content_surface_and_no_local_dock() -> None:
    scaffold = _between(
        APP,
        "function learningScaffold(content, activePath) {",
        "\n}\n\nfunction renderLearningScaffold",
    )
    assert 'class="learning-gate-shell"' in scaffold
    assert scaffold.count('id="main-content"') == 1
    assert scaffold.count('id="workspace-content"') == 1
    for forbidden in (
        'class="workspace-shell"',
        'class="sidebar"',
        "mobileNavMarkup",
        "academy-os-dock",
        "academy-course-os-dock",
        "academy-v2-dock",
        "learning-command-bar",
    ):
        assert forbidden not in scaffold

    assert 'route: "/learn"' not in CORE
    assert 'route.startsWith("/workspace/")' in CORE


def test_academy_layout_is_responsive_and_motion_safe() -> None:
    for selector in (
        ".learning-gate-shell",
        ".learning-gate-topbar",
        ".learning-gate-main",
        ".learning-gate-page",
        ".learning-gate-card",
        ".learning-gate-roadmap",
    ):
        assert selector in CORE_STYLES

    assert "min-width: 0" in CORE_STYLES
    assert "@media (max-width: 640px)" in CORE_STYLES
    assert "@media (prefers-reduced-motion: reduce)" in CORE_STYLES
    reduced_motion = CORE_STYLES.split(
        "@media (prefers-reduced-motion: reduce)", 1
    )[1]
    assert ".learning-gate-page" in reduced_motion
    assert "animation: none" in reduced_motion
    assert ".learning-gate-meter > span" in reduced_motion
    assert "transition: none" in reduced_motion
