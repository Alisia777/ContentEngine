from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
RECOVERY = (APP / "workspace-research-reference-recovery.js").read_text(
    encoding="utf-8"
)
RECOVERY_CSS = (APP / "workspace-research-reference-recovery.css").read_text(
    encoding="utf-8"
)
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")


def test_research_route_loads_reference_recovery_lazily() -> None:
    assert 'match: (route) => route === "/workspace/research"' in LOADER
    assert "workspace-research-reference-recovery.css?v=20260805.1" in LOADER
    assert "workspace-research-reference-recovery.js?v=20260805.1" in LOADER


def test_youtube_short_watch_and_share_forms_use_one_video_identity() -> None:
    for marker in (
        'host === "youtu.be"',
        '["shorts", "embed", "live"]',
        'url.searchParams.get("v")',
        'https://www.youtube.com/watch?v=${videoId}',
        'YOUTUBE_ID',
    ):
        assert marker in RECOVERY


def test_air_fryer_is_a_narrow_learning_category_inside_electronics() -> None:
    assert 'hidden.name = "learning_category_key"' in RECOVERY
    assert '["air_fryer", "Аэрогрили"]' in RECOVERY
    assert 'hidden.value = broad === "electronics" || !broad ? "air_fryer"' in RECOVERY
    assert "Электроника слишком широкая для обучения" in RECOVERY


def test_recovery_never_bypasses_server_safety_or_autosubmits_business_forms() -> None:
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "requestSubmit",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "DOMParser",
        "new MutationObserver",
    ):
        assert forbidden not in RECOVERY
    assert "button.click()" in RECOVERY
    assert "не обхода остальных проверок" in RECOVERY


def test_reference_recovery_is_readable_and_mobile_safe() -> None:
    for marker in (
        "min-height: 44px",
        "font-size: 14px",
        "@media (max-width: 680px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert marker in RECOVERY_CSS
    assert RECOVERY_CSS.count("{") == RECOVERY_CSS.count("}")


def test_reference_recovery_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    subprocess.run(
        [node, "--check", str(APP / "workspace-research-reference-recovery.js")],
        check=True,
        capture_output=True,
        text=True,
    )
