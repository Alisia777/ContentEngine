from pathlib import Path
import re
import struct


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
VIEW_PATH = APP_DIR / "ai-learning-control-room.js"
CSS_PATH = APP_DIR / "ai-learning-control-room.css"
ASSET_PATH = APP_DIR / "assets" / "content-factory-ai-center-human-review-v1.png"


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", header[16:24])


def test_ai_center_journey_uses_one_local_decorative_human_review_scene() -> None:
    view = VIEW_PATH.read_text(encoding="utf-8")
    asset_name = "content-factory-ai-center-human-review-v1.png"

    assert ASSET_PATH.is_file()
    assert ASSET_PATH.stat().st_size > 1_000_000
    width, height = _png_dimensions(ASSET_PATH)
    assert width >= 1600
    assert height >= 900

    assert view.count(asset_name) == 1
    assert "AI_LEARNING_HUMAN_REVIEW_VISUAL_URL = new URL(" in view
    assert "import.meta.url" in view
    assert 'data-ai-recommendation-art aria-hidden="true"' in view
    assert 'src="${escapeHtml(AI_LEARNING_HUMAN_REVIEW_VISUAL_URL)}"' in view
    assert f'width="{width}" height="{height}"' in view
    assert 'loading="lazy" decoding="async"' in view

    journey_start = view.index('<section class="ai-learning-decision-journey"')
    scene_start = view.index('data-ai-recommendation-art', journey_start)
    flow_start = view.index('class="ai-learning-decision-journey__flow"', scene_start)
    assert journey_start < scene_start < flow_start

    scene = view[scene_start:flow_start]
    assert all(label in scene for label in (
        "ИИ предлагает",
        "Человек проверяет",
        "Решение фиксируется",
    ))
    assert not re.search(r"<(?:button|form|input|select|textarea)\b", scene)
    assert "data-action=" not in scene
    assert "href=" not in scene


def test_ai_center_scene_is_responsive_and_respects_reduced_motion() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")

    assert ".ai-learning-decision-journey__scene > img" in css
    assert "object-fit: cover" in css
    assert "@keyframes ai-learning-scene-drift" in css
    assert ".ai-learning-decision-journey__scene-flow" in css
    assert "backdrop-filter: blur(16px)" in css

    tablet = css.split("@media (max-width: 1040px)", maxsplit=1)[1]
    assert ".ai-learning-decision-journey__scene" in tablet
    assert "object-position: 54% 47%" in tablet

    mobile = css.split("@media (max-width: 680px)", maxsplit=1)[1]
    assert ".ai-learning-decision-journey__scene-flow" in mobile
    assert "grid-template-columns: minmax(0, 1fr)" in mobile
    assert "object-position: 62% 48%" in mobile

    reduced_motion = css.rsplit("@media (prefers-reduced-motion: reduce)", maxsplit=1)[1]
    assert ".ai-learning-decision-journey__scene > img" in reduced_motion
    assert "animation: none !important" in reduced_motion

    visual_pass = css.split(
        "/* 2026 desktop visual pass: navy glass, readable density and reference accents. */",
        maxsplit=1,
    )[1]
    rem_sizes = [
        float(match.group(1))
        for match in re.finditer(
            r"font-size\s*:\s*(?:clamp\(\s*)?(0?\.\d+)rem",
            visual_pass,
        )
    ]
    assert rem_sizes
    assert min(rem_sizes) >= 0.75


def test_ai_center_runtime_import_uses_current_content_factory_build() -> None:
    app = (APP_DIR / "app.js").read_text(encoding="utf-8")
    assert (
        'from "./ai-learning-control-room.js?v=20260826.rebuild-clean.12"'
        in app
    )
