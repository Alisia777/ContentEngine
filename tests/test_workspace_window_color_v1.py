from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "web" / "app" / "workspace-window-color-v1.css"
CORE_PATH = ROOT / "web" / "app" / "workspace-os-v4.js"
INDEX_PATH = ROOT / "web" / "app" / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_window_colour_layer_uses_real_shell_contract_without_manager_changes():
    css = _read(CSS_PATH)
    core = _read(CORE_PATH)

    assert 'shell.dataset.ceV4WindowRoute = path' in core
    assert 'shell.dataset.ceV4WindowApp = record.appLabel' in core
    assert 'shell.classList.toggle("is-active", visible)' in core
    assert 'shell.classList.toggle("is-key-window", active)' in core
    assert 'shell.classList.remove("is-inactive")' in core
    assert 'shell.classList.toggle("is-minimized", minimized)' in core

    for selector in (
        '[data-ce-v4-window-route="/workspace/home"]',
        '[data-ce-v4-window-route="/workspace/board"]',
        '[data-ce-v4-window-route="/workspace/media"]',
        '[data-ce-v4-window-route="/workspace/generation"]',
        '[data-ce-v4-window-route="/workspace/review"]',
        '[data-ce-v4-window-route="/workspace/placement"]',
        '[data-ce-v4-window-route="/workspace/stats"]',
        '[data-ce-v4-window-route="/workspace/payouts"]',
        '[data-ce-v4-window-route="/workspace/research"]',
        '[data-ce-v4-window-route="/workspace/ai"]',
        '[data-ce-v4-window-route="/workspace/team"]',
        '[data-ce-v4-window-route="/workspace/feedback"]',
        '[data-ce-v4-window-route="/workspace/tasks"]',
        '[data-ce-v4-window-route="/workspace/work"]',
    ):
        assert selector in css


def test_all_live_window_headers_keep_full_colour_with_accessible_focus_states():
    css = _read(CSS_PATH)

    assert ".ce-v4-window__titlebar::before" in css
    assert ".ce-v4-window__titlebar::after" in css
    assert "pointer-events: none" in css
    assert ".ce-v4-window__titlebar > *" in css
    assert ".ce-v4-window.is-active" in css
    assert ".is-inactive" not in css
    assert ".ce-v4-window.is-minimized" in css
    assert ".ce-v4-window.is-dragging" in css
    assert ".ce-v4-window.is-zoomed" in css
    assert ".ce-v4-window:focus-visible" in css
    assert "@media (prefers-contrast: more)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: none" in css


def test_window_colour_layer_does_not_restyle_macos_traffic_lights():
    css = _read(CSS_PATH)

    for control in (
        ".ce-v4-window__close::before",
        ".ce-v4-window__minimize::before",
        ".ce-v4-window__zoom::before",
    ):
        assert control not in css

    # The decorative header glow cannot intercept close/minimise/zoom clicks.
    titlebar_decorators = css.split(".ce-v4-window__titlebar::before,", 1)[1]
    assert "pointer-events: none" in titlebar_decorators


def test_window_colour_layer_is_loaded_with_the_current_build_key():
    index = _read(INDEX_PATH)
    assert './workspace-window-color-v1.css?v=20260826.rebuild-clean.53' in index
