from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/generation-autopilot.js"
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation autopilot contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            MODULE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_unique_safe_media_is_selected_without_guessing_between_candidates() -> None:
    media = json.dumps(
        [
            {
                "public_id": "media-ready",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "WB-1",
                "product_name": "Точный товар",
            },
            {
                "public_id": "media-unverified",
                "identity_verified": False,
                "rights_confirmed": True,
                "sku": "WB-2",
                "product_name": "Другой товар",
            },
        ],
        ensure_ascii=False,
    )
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({media}, {{ real: true }})"
    ) == "media-ready"
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({media}, {{ real: false }})"
    ) == ""

    two_safe = json.dumps(
        [
            {
                "id": "one",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "WB-1",
                "product_name": "Один",
            },
            {
                "id": "two",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "WB-2",
                "product_name": "Два",
            },
        ],
        ensure_ascii=False,
    )
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({two_safe}, {{ real: true }})"
    ) == ""


def test_platform_autopilot_uses_content_specific_defaults_and_respects_manual_choice() -> None:
    expression = """
    [
      subject.resolveGenerationPlatform({
        mode: "real_photo",
        currentPlatform: "instagram",
      }),
      subject.resolveGenerationPlatform({
        mode: "real_seedance",
        currentPlatform: "instagram",
      }),
      subject.resolveGenerationPlatform({
        mode: "real_photo",
        currentPlatform: "tiktok",
        automaticPlatform: "tiktok",
      }),
      subject.resolveGenerationPlatform({
        mode: "real_photo",
        currentPlatform: "telegram",
        automaticPlatform: "tiktok",
      }),
      subject.resolveGenerationPlatform({
        mode: "mock",
        currentPlatform: "vk",
        automaticPlatform: "tiktok",
      }),
    ]
    """
    assert _evaluate(expression) == [
        {"value": "wildberries", "preferred": "wildberries", "automatic": True},
        {"value": "tiktok", "preferred": "tiktok", "automatic": True},
        {"value": "wildberries", "preferred": "wildberries", "automatic": True},
        {"value": "telegram", "preferred": "wildberries", "automatic": False},
        {"value": "vk", "preferred": "", "automatic": False},
    ]


def test_generation_form_wires_autopilot_with_visible_override_and_cache_busting() -> None:
    assert 'from "./generation-autopilot.js?v=20260725.1"' in APP
    assert "chooseInitialGenerationMedia(exactMedia" in APP
    assert (
        "generationMediaOptionMarkup(item, defaultIsReal, automaticMediaId)"
        in APP
    )
    assert "Единственный проверенный исходник выбран автоматически" in APP
    assert "function syncGenerationAutomaticMedia(form)" in APP
    assert 'generationForm.dataset.generationMediaSelectionTouched = "true"' in APP
    assert "snapshot.generationMediaSelectionTouched" in APP
    assert "resolveGenerationPlatform({" in APP
    assert "delete generationForm.dataset.autoGenerationPlatform" in APP
    assert './app.js?v=20260725.26' in INDEX
