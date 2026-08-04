from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-desktop-os.js").read_text(encoding="utf-8")
CSS_FILES = (
    APP_DIR / "workspace-desktop-os.css",
    APP_DIR / "workspace-desktop-review.css",
    APP_DIR / "workspace-desktop-review-form.css",
    APP_DIR / "workspace-desktop-review-result.css",
    APP_DIR / "workspace-desktop-academy.css",
    APP_DIR / "workspace-desktop-responsive.css",
)
CSS = "\n".join(path.read_text(encoding="utf-8") for path in CSS_FILES)


def test_legacy_desktop_os_assets_are_absent_from_the_active_graph() -> None:
    active_assets = set(re.findall(
        r'^\s*<(?:link|script)\b[^>]*\b(?:href|src)="([^"]+)"',
        INDEX,
        flags=re.MULTILINE,
    ))
    retired_names = (
        "workspace-desktop-os.css",
        "workspace-desktop-review.css",
        "workspace-desktop-review-form.css",
        "workspace-desktop-review-result.css",
        "workspace-desktop-academy.css",
        "workspace-desktop-responsive.css",
        "workspace-desktop-os.js",
    )
    assert not any(any(name in asset for name in retired_names) for asset in active_assets)
    assert "./workspace-os-v4.css?v=20260804.os4.10" in active_assets
    assert "./workspace-os-v4-loader.js?v=20260804.os4.10" in active_assets


def test_review_is_recomposed_as_real_spaces_not_a_two_column_dashboard() -> None:
    for marker in (
        'const REVIEW_ROUTE = "/workspace/review"',
        'review-os-workbench',
        'data-review-os-space="result"',
        'data-review-os-space="new"',
        'data-review-os-space="history"',
        'setupReviewForm',
        'setupReviewResult',
        'review-os-result-panels',
        'review-os-step-dock',
    ):
        assert marker in SCRIPT or marker in CSS
    assert '.review-desktop-os > .content-review-layout' in CSS
    assert '.review-os-form > [data-ce-os-panel].is-active' in CSS
    assert '.review-os-result-panel.is-active' in CSS
    assert 'grid-template-rows: 74px minmax(0, 1fr) 66px' in CSS


def test_mac_dock_is_real_navigation_not_decoration() -> None:
    for marker in (
        'collectDockItems',
        'ce-mac-dock',
        'data-ce-dock-route',
        '--ce-dock-scale',
        'updateDockMagnification',
        'requestAnimationFrame',
        'data-ce-open-mission',
    ):
        assert marker in SCRIPT or marker in CSS
    assert '.ce-mac-dock__item.is-active > i' in CSS
    assert '@media (max-width: 640px)' in CSS


def test_academy_uses_the_same_workspace_language() -> None:
    for marker in (
        'setupAcademyHome',
        'setupAcademyCourse',
        'academy-os-window',
        'academy-os-panels',
        'academy-os-dock',
        'academy-course-os-window',
        'academy-course-os-dock',
    ):
        assert marker in SCRIPT or marker in CSS
    assert '.academy-os-panel.is-active' in CSS
    assert '.academy-course-os-panel.is-active' in CSS
    assert '.academy-os-panel--courses .course-grid' in CSS


def test_desktop_os_keeps_backend_and_existing_forms_authoritative() -> None:
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "cloneNode" not in SCRIPT
    assert "new FormData" not in SCRIPT
    assert "input.value" not in SCRIPT
    assert "textarea.value" not in SCRIPT
    assert "panel.inert = !active" in SCRIPT
    assert "append(form)" in SCRIPT


def test_motion_and_accessibility_have_safe_fallbacks() -> None:
    for marker in (
        'REDUCED_MOTION',
        'prefers-reduced-motion: reduce',
        'aria-hidden',
        'aria-current',
        'aria-label',
        'event.target instanceof Element',
    ):
        assert marker in SCRIPT or marker in CSS
    assert 'animation-duration: 0.01ms !important' in CSS
    assert 'transition-duration: 0.01ms !important' in CSS


def test_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-desktop-os.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_css_structure_is_balanced_and_immersive() -> None:
    for path in CSS_FILES:
        source = path.read_text(encoding="utf-8")
        assert source.count("{") == source.count("}"), path.name
    assert 'body.contentengine-review-os-open .workspace-shell > .sidebar' in CSS
    assert 'body.contentengine-academy-os-open .workspace-shell > .sidebar' in CSS
    assert '.review-os-space.is-active' in CSS
