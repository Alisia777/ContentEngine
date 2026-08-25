import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
CSS = (APP_DIR / "auth-kpp-scene.css").read_text(encoding="utf-8")
POINTER = (APP_DIR / "auth-kpp-pointer.js").read_text(encoding="utf-8")
BUILD = json.loads((APP_DIR / "build.json").read_text(encoding="utf-8"))["id"]


def test_kpp_scene_replaces_the_previous_skin_without_touching_auth() -> None:
    asset = APP_DIR / "assets" / "contentengine-login-kpp-bg.webp"
    assert asset.is_file()
    assert asset.stat().st_size < 1_000_000
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == (
        "a90b2fb5d5b2ef04394110481ad70d0ffa57e6a475515548358bc0f125646f12"
    )

    style_marker = f'./auth-kpp-scene.css?v={BUILD}'
    pointer_marker = f'./auth-kpp-pointer.js?v={BUILD}'
    preload_marker = f'./assets/contentengine-login-kpp-bg.webp?v={BUILD}'
    assert style_marker in INDEX
    assert pointer_marker in INDEX
    assert preload_marker in INDEX
    assert INDEX.index("content-factory-visual-v2.css") < INDEX.index(style_marker)
    assert INDEX.index(style_marker) < INDEX.index("workspace-build-guard.css")
    assert "login-cinematic.css" not in INDEX
    assert "contentengine-login-bg.webp" not in INDEX
    assert not (APP_DIR / "login-cinematic.css").exists()
    assert not (APP_DIR / "assets" / "contentengine-login-bg.webp").exists()

    for marker in (
        'id="login-form"',
        'name="email"',
        'type="email"',
        'autocomplete="username"',
        'name="password"',
        'type="password"',
        'autocomplete="current-password"',
        'minlength="8"',
        "signInWithPassword({ email, password })",
        'href="#/reset-password"',
        "function brandAtmosphereMarkup()",
    ):
        assert marker in APP


def test_kpp_weather_is_layered_bounded_and_mobile_safe() -> None:
    assert 'url("./assets/contentengine-login-kpp-bg.webp")' in CSS
    for marker in (
        ".auth-story::before",
        ".auth-story::after",
        ".auth-message::before",
        ".auth-message::after",
        ".auth-visual-orbit--one",
        ".auth-visual-orbit--two",
        ".auth-visual-spark--one",
        ".auth-visual-spark--two",
        "auth-kpp-clouds-far 68s",
        "auth-kpp-clouds-near 56s",
        "auth-kpp-factory-breath 8.4s",
        "auth-kpp-rain-far 1.55s",
        "auth-kpp-rain-mid 1.02s",
        "auth-kpp-rain-front 0.72s",
        "auth-kpp-droplets 17s",
        "auth-kpp-light-pulse 27s",
        "@media (max-width: 820px)",
        "@media (prefers-reduced-motion: reduce)",
        "pointer-events: none",
        "100dvh",
    ):
        assert marker in CSS

    assert 'class="auth-visual-stage" aria-hidden="true"' in APP
    assert "grid-template-columns: minmax(0, 1fr) var(--auth-kpp-panel)" in CSS
    assert "width: min(100%, 460px)" in CSS


def test_pointer_parallax_is_event_driven_and_respects_user_preferences() -> None:
    for marker in (
        'window.matchMedia("(prefers-reduced-motion: reduce)")',
        'window.matchMedia("(hover: hover) and (pointer: fine)")',
        'document.addEventListener("pointermove"',
        '"--auth-kpp-shift-x"',
        '"--auth-kpp-shift-y"',
    ):
        assert marker in POINTER

    bundle = f"{CSS}\n{POINTER}".casefold()
    for forbidden in (
        "requestanimationframe(",
        "setinterval(",
        "<video",
        "<canvas",
        "webgl",
        "lottie",
        "http://",
        "https://",
    ):
        assert forbidden not in bundle


def test_kpp_visual_does_not_claim_fake_auth_or_health_capabilities() -> None:
    bundle = f"{CSS}\n{POINTER}"
    for forbidden in (
        "remember-me",
        "AES-256",
        "TLS 1.3",
        "Все системы готовы",
        "вы под контролем",
    ):
        assert forbidden not in bundle
