"""Runtime regressions for truthful state in the guided generation wizard.

The harness mirrors the live form's native SKU, product-name and brief
requirements, then verifies the guided adapter's cross-step and media rules.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "workspace-os-v4-generation-guided.js"
HARNESS = ROOT / "tests" / "fixtures" / "workspace_generation_guided_state_v493_harness.html"


def _chrome_path() -> str | None:
    candidates = (
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    )
    return next((str(path) for path in candidates if path and Path(path).exists()), None)


def test_generation_guided_state_harness_covers_the_reported_failure_boundaries() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    for observable in (
        "persistedLaunchClampsToProduct",
        "nameWithoutSkuIsRejected",
        "skuWithoutNameIsRejected",
        "emptyRealBriefIsRejected",
        "realWithoutMediaIsRejected",
        "mockWithoutMediaIsRejected",
        "mockExplicitlyCreatesNoVideo",
        "mockExplicitlyCreatesNoFile",
    ):
        assert observable in source
    assert "workspace-os-v4-generation-guided.js?fixture=v493-state-guardrails" in source
    assert "contentengine.desktop.v4.generation-guided.v2" in source


def test_generation_guided_restores_only_a_valid_step_and_tells_the_truth_about_mock() -> None:
    chrome = _chrome_path()
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for generation wizard runtime QA")

    result = None
    last_stdout = ""
    # Chrome can occasionally dump a file:// document before its cold dynamic
    # module import has entered the virtual-time queue. Retry only the explicit
    # untouched WAIT sentinel; a real FAIL/ERROR remains immediately visible.
    for _attempt in range(3):
        with tempfile.TemporaryDirectory(prefix="ce-generation-guided-v493-") as profile:
            completed = subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--allow-file-access-from-files",
                    "--virtual-time-budget=8000",
                    "--window-size=1280,900",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    HARNESS.resolve().as_uri(),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        last_stdout = completed.stdout
        result = re.search(
            r'<output id="result"[^>]*>[^<]*</output>',
            completed.stdout,
        )
        assert result, completed.stdout[-4_000:]
        if result.group(0) != '<output id="result">WAIT</output>':
            break

    assert result, last_stdout[-4_000:]
    assert 'data-passed="true"' in result.group(0), result.group(0)


def test_generation_guided_module_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable for JavaScript syntax validation")

    subprocess.run(
        [node, "--check", str(MODULE)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
