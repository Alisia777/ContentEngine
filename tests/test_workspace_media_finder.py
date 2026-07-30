from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-media-finder.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-media-finder.css").read_text(encoding="utf-8")


def test_media_finder_assets_load_after_the_desktop_layer() -> None:
    assert './workspace-media-finder.css?v=20260731.1' in INDEX
    assert './workspace-media-finder.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-desktop-os.css') < INDEX.index('./workspace-media-finder.css')
    assert INDEX.index('./workspace-generation-os.js') < INDEX.index('./workspace-media-finder.js')


def test_media_finder_anchors_match_the_native_materials_screen() -> None:
    for marker in (
        'id="media-upload-form"',
        'split-grid-media',
        'class="media-grid"',
        'class="card media-card"',
        'class="media-preview"',
        'class="media-info"',
    ):
        assert marker in APP


def test_materials_are_recomposed_into_a_finder_library() -> None:
    for marker in (
        'const MEDIA_ROUTE = "/workspace/media"',
        'ContentEngine Finder',
        'Умные папки',
        'data-media-folder="all"',
        'data-media-folder="photos"',
        'data-media-folder="videos"',
        'data-media-folder="product"',
        'data-media-folder="reference"',
        'data-media-view="grid"',
        'data-media-view="list"',
        'layout?.remove()',
        'q(".media-finder-library__content", finder).append(library)',
    ):
        assert marker in SCRIPT


def test_quick_look_supports_space_navigation_and_native_urls() -> None:
    for marker in (
        'media-quicklook-backdrop',
        'QUICK LOOK',
        'event.key === " "',
        'event.key === "ArrowLeft"',
        'event.key === "ArrowRight"',
        'event.key === "Escape"',
        'document.createElement("video")',
        'document.createElement("img")',
        'В генерацию',
        'Проверить',
    ):
        assert marker in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "cloneNode" not in SCRIPT


def test_upload_form_is_moved_not_recreated() -> None:
    for marker in (
        'uploadCard.classList.add("media-finder-upload-card")',
        'q("[data-media-upload-parking]", finder).append(uploadCard)',
        'q(".media-finder-upload-sheet__body", overlay).append(card)',
        'parking.append(card)',
    ):
        assert marker in SCRIPT


def test_finder_geometry_is_responsive_and_reduced_motion_safe() -> None:
    for marker in (
        'body.contentengine-media-finder-open .workspace-shell > .sidebar',
        '.media-finder-shell',
        '.media-finder-sidebar',
        '.media-finder-native-library .media-grid',
        '.media-quicklook',
        '.media-finder-upload-sheet',
        '@media (max-width: 820px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
        'animation-duration: 0.01ms !important',
    ):
        assert marker in CSS


def test_media_finder_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-media-finder.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_media_finder_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
