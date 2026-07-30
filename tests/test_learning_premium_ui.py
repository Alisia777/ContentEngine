from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
CORE = (APP_DIR / "learning-premium.css").read_text(encoding="utf-8")
COMPONENTS = (APP_DIR / "learning-premium-components.css").read_text(encoding="utf-8")
MOTION = (APP_DIR / "learning-premium-motion.css").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "learning-premium.js").read_text(encoding="utf-8")


def test_learning_premium_assets_are_loaded_after_the_base_interface() -> None:
    markers = (
        './learning-premium.css?v=20260730.1',
        './learning-premium-components.css?v=20260730.1',
        './learning-premium-motion.css?v=20260730.1',
        './learning-premium.js?v=20260730.1',
    )
    for marker in markers:
        assert marker in INDEX

    assert INDEX.index("./interface-system.css") < INDEX.index("./learning-premium.css")
    assert INDEX.index("./app.js") < INDEX.index("./learning-premium.js")


def test_learning_enhancement_is_scoped_and_does_not_call_the_api() -> None:
    for marker in (
        'const LEARNING_HOME_SELECTOR = ".learning-page:not(.course-page)"',
        'return path === "/learn"',
        "new MutationObserver(queueMount)",
        'root.classList.add("learning-premium-v3")',
        "new AbortController()",
    ):
        assert marker in SCRIPT

    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT


def test_learning_navigation_and_card_grouping_are_progressive() -> None:
    for marker in (
        "learning-command-bar",
        "data-learning-scroll-target",
        "learning-assessment-grid",
        "learning-option-grid",
        "groupAssessmentCards(root)",
        "groupOptionalCards(root)",
    ):
        assert marker in SCRIPT

    assert 'root.querySelector(".learning-assessment-grid") || root.querySelector(".training-practical-card")' in SCRIPT


def test_learning_motion_is_accessible_and_responsive() -> None:
    for marker in (
        "@media (prefers-reduced-motion: no-preference)",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
        "@media (max-width: 820px)",
        "@media (max-width: 520px)",
        "top: 70px",
        "grid-template-columns: 1fr",
    ):
        assert marker in MOTION

    assert "top: calc(clamp(78px, 5vw, 92px) + 14px)" in CORE
    assert "scroll-margin-top" in CORE


def test_learning_visual_system_has_clear_states_and_workflow() -> None:
    for marker in (
        ".learning-page.learning-premium-v3 .learning-hero",
        ".learning-command-bar",
        ".learning-premium-scroll-progress",
    ):
        assert marker in CORE

    for marker in (
        ".learning-page.learning-premium-v3 .learning-now",
        ".learning-page.learning-premium-v3 .learning-safety-gate",
        ".learning-page.learning-premium-v3 .portal-workflow",
        ".learning-page.learning-premium-v3 .course-card.current",
        ".learning-assessment-grid",
    ):
        assert marker in COMPONENTS
