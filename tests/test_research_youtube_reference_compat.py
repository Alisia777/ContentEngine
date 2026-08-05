from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
SCRIPT = (APP / "workspace-research-reference-compat.js").read_text(encoding="utf-8")
STYLE = (APP / "workspace-research-reference-compat.css").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")


def test_youtube_shorts_compatibility_is_loaded_only_for_research() -> None:
    assert 'researchReference' in LOADER
    assert 'route === "/workspace/research"' in LOADER
    assert 'workspace-research-reference-compat.js' in LOADER
    assert 'workspace-research-reference-compat.css' in LOADER


def test_short_watch_and_youtu_be_share_one_video_identity() -> None:
    for marker in (
        'parts[0] === "shorts"',
        'url.pathname === "/watch"',
        'host === "youtu.be"',
        'https://www.youtube.com/watch?v=${id}',
        'sameYoutubeVideo',
    ):
        assert marker in SCRIPT
    assert "GW-NfEVlPGc" not in SCRIPT


def test_air_fryer_uses_narrow_learning_category_and_public_competitor_mode() -> None:
    for marker in (
        'return "air_fryer"',
        'contentengine_reference_source_kind',
        'public_competitor',
        'contentengine_reference_intent',
        'structural_reference',
        'contentengine_reference_learning_mode',
        'candidate_after_qa',
        'learning_category_key',
    ):
        assert marker in SCRIPT
    assert 'auto_train' not in SCRIPT
    assert 'production_winner' not in SCRIPT


def test_bridge_does_not_call_provider_or_auto_submit_business_forms() -> None:
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        ".requestSubmit(",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "service_role",
        "OPENAI_API_KEY",
    ):
        assert forbidden not in SCRIPT


def test_bridge_is_readable_and_javascript_parses() -> None:
    for marker in (
        "Почему пример заблокирован",
        "Подготовить ссылку и повторить",
        "Для аэрогриля — air_fryer",
        "Канонический ролик",
    ):
        assert marker in SCRIPT
    assert STYLE.count("{") == STYLE.count("}")
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    subprocess.run(
        [node, "--check", str(APP / "workspace-research-reference-compat.js")],
        check=True,
        capture_output=True,
        text=True,
    )
