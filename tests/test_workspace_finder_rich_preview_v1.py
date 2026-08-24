from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
BOARD_PATH = APP / "workspace-board-view.js"
FINDER_PATH = APP / "workspace-os-v4-finder.js"
BOARD = BOARD_PATH.read_text(encoding="utf-8")
FINDER = FINDER_PATH.read_text(encoding="utf-8")
FINDER_CSS = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_columns_preview_reuses_only_safe_read_only_card_data() -> None:
    projection = _between(
        FINDER,
        "function finderCardPreviewSource(",
        "\nfunction ensureColumnsProjection()",
    )
    assert 'q(".workspace-board__item-preview img", card)' in projection
    assert "image?.currentSrc" in projection
    assert 'parsed.protocol === "https:" || parsed.protocol === "blob:" || localHttp' in projection
    assert 'parsed.protocol === "http:" && parsed.origin === window.location.origin' in projection
    assert 'create("figure", "ce-v4-finder-column__visual")' in projection
    assert 'create("img", "ce-v4-finder-column__image")' in projection
    assert 'create("figcaption", "ce-v4-finder-column__visual-label", kind.label)' in projection
    for forbidden in ("fetch(", "getApi", ".cloneNode", 'create("button"', 'create("input"'):
        assert forbidden not in projection

    sync = _between(FINDER, "function syncColumnsProjection()", "\nfunction refreshFinderBoard()")
    assert "finderColumnVisual(card, kind)" in sync
    assert "preview.replaceChildren(previewPanel)" in sync
    assert "card.replaceChildren" not in sync


def test_finder_preview_typography_and_rich_visual_have_a_readable_floor() -> None:
    assert "font-size: 9px" not in FINDER_CSS
    assert ".ce-v4-finder-column__visual" in FINDER_CSS
    assert ".ce-v4-finder-column__image" in FINDER_CSS
    assert ".ce-v4-finder-column__visual-label" in FINDER_CSS
    label = _between(
        FINDER_CSS,
        ".ce-v4-finder-column__visual-label {",
        "\n}",
    )
    assert "font-size: 12px" in label


def test_grid_uses_poster_thumbnail_and_image_without_loading_video() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for executable Finder preview contracts")
    module_url = BOARD_PATH.as_uri()
    probe = f"""
const mod = await import({json.dumps(module_url)});
const board = mod.normalizeWorkspaceBoard({{
  items: [
    {{
      id: "poster-video", entity_type: "media", title: "Poster video",
      mime_type: "video/mp4", signed_url: "https://media.example.test/video.mp4",
      poster_url: "https://media.example.test/poster.webp"
    }},
    {{
      id: "thumb-video", entity_type: "media", title: "Thumb video",
      mime_type: "video/mp4", thumbnail_url: "https://media.example.test/thumb.jpg"
    }},
    {{
      id: "image", entity_type: "media", title: "Image",
      mime_type: "image/jpeg", signed_url: "https://media.example.test/image.jpg",
      thumbnail_url: "https://media.example.test/image-thumb.jpg"
    }},
    {{
      id: "unsafe", entity_type: "media", title: "Unsafe",
      mime_type: "video/mp4", signed_url: "https://media.example.test/unsafe.mp4",
      poster_url: "javascript:alert(1)"
    }}
  ]
}});
const grid = mod.workspaceBoardMarkup(board, {{ selectedFolderId: "all" }});
const posterDetail = mod.workspaceBoardMarkup(board, {{
  selectedFolderId: "all", selectedItemKey: "media:poster-video"
}});
const thumbDetail = mod.workspaceBoardMarkup(board, {{
  selectedFolderId: "all", selectedItemKey: "media:thumb-video"
}});
const imageDetail = mod.workspaceBoardMarkup(board, {{
  selectedFolderId: "all", selectedItemKey: "media:image"
}});
process.stdout.write(JSON.stringify({{
  records: Object.fromEntries(board.items.map((item) => [item.id, {{
    previewUrl: item.previewUrl, imagePreviewUrl: item.imagePreviewUrl
  }}])),
  grid,
  posterDetail,
  thumbDetail,
  imageDetail
}}));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", probe],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(completed.stdout)

    assert result["records"]["poster-video"]["imagePreviewUrl"].endswith("poster.webp")
    assert result["records"]["thumb-video"] == {
        "previewUrl": "",
        "imagePreviewUrl": "https://media.example.test/thumb.jpg",
    }
    assert "https://media.example.test/poster.webp" in result["grid"]
    assert "https://media.example.test/thumb.jpg" in result["grid"]
    assert "https://media.example.test/image-thumb.jpg" in result["grid"]
    assert "https://media.example.test/image.jpg" not in result["grid"]
    # Готовый постер всегда побеждает: <video> в сетке остаётся только у ролика
    # БЕЗ картинки — это захват первого кадра по просьбе владельца (24.08,
    # «1й кадр хотелось бы видеть»); он один и помечен data-preview-capture.
    assert result["grid"].count("<video") == 1
    assert 'data-preview-capture="unsafe"' in result["grid"]
    assert "javascript:alert(1)" not in result["grid"]
    assert 'preload="none"' in result["posterDetail"]
    assert 'poster="https://media.example.test/poster.webp"' in result["posterDetail"]
    # Разметка деталей включает и сетку, где живёт единственный capture-<video>
    # ролика без картинки; сам ящик thumb-video видео не монтирует.
    assert result["thumbDetail"].count("<video") == 1
    assert 'data-preview-capture="unsafe"' in result["thumbDetail"]
    assert "https://media.example.test/thumb.jpg" in result["thumbDetail"]
    assert "https://media.example.test/image.jpg" in result["imageDetail"]


def test_finder_javascript_parses() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for Finder syntax checks")
    for path in (BOARD_PATH, FINDER_PATH):
        completed = subprocess.run(
            [node, "--check", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
