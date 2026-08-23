import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
VISUAL = (APP_DIR / "content-factory-visual-v2.css").read_text(encoding="utf-8")
INTAKE_CSS = (APP_DIR / "generation-strategy-intake-v4.css").read_text(encoding="utf-8")
INTAKE_JS = (APP_DIR / "generation-strategy-intake-v4.js").read_text(encoding="utf-8")
BUILD = json.loads((APP_DIR / "build.json").read_text(encoding="utf-8"))["id"]


def test_visual_layer_is_cache_versioned_and_loaded_after_reference_layer() -> None:
    marker = f'./content-factory-visual-v2.css?v={BUILD}'
    assert marker in INDEX
    assert INDEX.index("workspace-ui-reference-v1.css") < INDEX.index(marker)


def test_login_visual_changes_presentation_without_changing_auth_contract() -> None:
    assert 'class="auth-visual-stage"' in APP
    assert "Весь контент-путь." in APP
    assert 'id="login-form"' in APP
    assert 'name="email"' in APP
    assert 'autocomplete="username"' in APP
    assert 'name="password"' in APP
    assert 'autocomplete="current-password"' in APP
    assert "signInWithPassword({ email, password })" in APP
    assert ".auth-visual-window" in VISUAL
    assert ".auth-card :is(input, textarea, select)" in VISUAL


def test_generation_has_visual_routes_models_and_media_first_product_cards() -> None:
    for route_visual in ('art: "swap"', 'art: "avatar"', 'art: "strategy"'):
        assert route_visual in INTAKE_JS
    assert "button.dataset.visual = visual.art" in INTAKE_JS
    for model_visual in ('return "pika"', 'return "kling"', 'return "runway"'):
        assert model_visual in INTAKE_JS
    assert "const MODEL_VISUALS" in INTAKE_JS
    assert "modelVisualNode(visual)" in INTAKE_JS
    assert 'image.src = new URL(asset.image, import.meta.url).href' in INTAKE_JS
    assert "ИИ-центр рекомендует" in INTAKE_JS
    assert "человек может выбрать другую модель" in INTAKE_JS
    assert "--surface: #0b1726" in VISUAL
    assert "grid-template-rows: minmax(156px, 1fr) auto" in VISUAL
    assert "max-width: none" in VISUAL
    assert "aspect-ratio: 4 / 3" in VISUAL
    assert "object-fit: contain" in VISUAL
    assert ".gi-model-choice__visual" in INTAKE_CSS
    assert ".gi-model-choice__image" in INTAKE_CSS
    assert "@media (prefers-reduced-motion: reduce)" in INTAKE_CSS


def test_project_cards_use_a_local_multi_scene_cover_atlas() -> None:
    atlas = APP_DIR / "assets" / "content-factory-project-covers-v2.png"
    assert atlas.is_file()
    assert atlas.stat().st_size > 100_000
    assert 'url("./assets/content-factory-project-covers-v2.png")' in VISUAL
    assert "background-size: 100% 100%, 200% 200%" in VISUAL
    for position in ("100% 0", "0 100%", "100% 100%"):
        assert position in VISUAL


def test_project_ai_sources_do_not_fall_back_to_the_legacy_brown_skin() -> None:
    assert "body.contentengine-desktop-v4 .ai-exact-youtube-sources" in VISUAL
    assert "body.contentengine-desktop-v4 .ai-exact-youtube-source" in VISUAL
    assert "linear-gradient(145deg, rgba(14,30,51,.91)" in VISUAL
    assert ".ai-exact-youtube-source__actions .btn-secondary" in VISUAL


def test_visual_motion_is_bounded_and_has_reduced_motion_fallback() -> None:
    assert "@media (prefers-reduced-motion: no-preference)" in VISUAL
    assert "@media (prefers-reduced-motion: reduce)" in VISUAL
    assert "ce-v2-surface-in" in VISUAL
    assert "transition-duration: .01ms !important" in VISUAL
