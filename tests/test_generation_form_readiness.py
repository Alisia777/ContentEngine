from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/generation-form-readiness.js"
MODULE_TEXT = MODULE.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _evaluate(value: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation readiness contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            MODULE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = subject.evaluateGenerationFormReadiness({json.dumps(value)});\n"
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


def test_mock_readiness_guides_user_through_four_human_steps() -> None:
    empty = _evaluate({"mode": "mock", "count": 5, "maxMockCount": 10})
    assert empty["ready"] is False
    assert empty["total"] == 4
    assert empty["completed"] == 1
    assert empty["next"]["key"] == "product"

    ready = _evaluate(
        {
            "mode": "mock",
            "sku": "WB-123",
            "productName": "Точный товар",
            "platform": "instagram",
            "destinationRef": "@brand",
            "mediaCount": 1,
            "count": 5,
            "maxMockCount": 10,
        }
    )
    assert ready["ready"] is True
    assert ready["completed"] == ready["total"] == 4


def test_paid_readiness_requires_one_photo_scenario_budget_and_confirmation() -> None:
    value = {
        "mode": "real_seedance",
        "sku": "WB-123",
        "productName": "Точный товар",
        "platform": "instagram",
        "destinationRef": "@brand",
        "mediaCount": 2,
        "brief": "Один безопасный сценарий",
        "campaignId": "campaign-1",
        "spendAllowed": True,
        "confirmationMatches": True,
        "count": 1,
    }
    too_many = _evaluate(value)
    assert too_many["ready"] is False
    assert too_many["next"]["key"] == "media"
    assert "ровно одно" in too_many["next"]["hint"]

    value["mediaCount"] = 1
    ready = _evaluate(value)
    assert ready["ready"] is True
    assert ready["total"] == 6


def test_paid_photo_readiness_uses_photo_specific_steps_and_confirmation() -> None:
    value = {
        "mode": "real_photo",
        "sku": "WB-123",
        "productName": "Точный товар",
        "platform": "tiktok",
        "destinationRef": "@brand",
        "mediaCount": 2,
        "brief": "",
        "campaignId": "campaign-1",
        "spendAllowed": True,
        "confirmationMatches": False,
        "count": 1,
    }
    too_many = _evaluate(value)
    assert too_many["real"] is True
    assert too_many["total"] == 6
    assert too_many["next"]["key"] == "media"
    assert "платного фото" in too_many["next"]["hint"]

    value["mediaCount"] = 1
    missing_composition = _evaluate(value)
    assert missing_composition["next"]["key"] == "brief"
    assert missing_composition["next"]["label"] == "Композиция"
    assert "упаковку и текст" in missing_composition["next"]["hint"]

    value["brief"] = "Точная квадратная композиция без изменения упаковки"
    missing_confirmation = _evaluate(value)
    assert missing_confirmation["next"]["key"] == "confirmation"
    assert "платного фото" in missing_confirmation["next"]["hint"]

    value["confirmationMatches"] = True
    ready = _evaluate(value)
    assert ready["ready"] is True
    assert ready["completed"] == ready["total"] == 6


def test_generation_form_updates_readiness_live_and_starts_fail_closed() -> None:
    assert 'from "./generation-form-readiness.js?v=20260724.2"' in APP
    assert "function syncGenerationFormReadiness(form)" in APP
    assert "syncGenerationFormReadiness(form);" in APP
    assert 'id="generation-readiness"' in MODULE_TEXT
    assert 'data-signature="${signature}"' in MODULE_TEXT
    assert "current.dataset.signature !== readiness.signature" in APP
    assert 'id="generation-submit" class="btn btn-block" type="submit" disabled' in APP
    assert "Заполните обязательные шаги" in APP
    assert '? "Проверяем платный запуск — не повторяйте"' in APP
    assert ': "Создаём тестовые варианты…"' in APP
    mock_submit = APP[
        APP.index("async function submitMockBatch")
        : APP.index("async function submitManualMetric")
    ]
    assert mock_submit.index("setFormBusy(form, false)") < mock_submit.index("form.reset()")
    assert ".generation-readiness__steps" in STYLES
    assert "@media (max-width: 820px)" in STYLES
    assert ".generation-readiness__steps { grid-template-columns: 1fr; }" in STYLES
    assert './styles.css?v=20260724.5' in INDEX
    assert './app.js?v=20260725.22' in INDEX
