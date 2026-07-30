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


def test_paid_readiness_accepts_up_to_five_product_angles() -> None:
    value = {
        "mode": "real_seedance",
        "sku": "WB-123",
        "productName": "Точный товар",
        "productCategory": "cosmetics",
        "platform": "instagram",
        "destinationRef": "@brand",
        "mediaCount": 6,
        "brief": "Один безопасный сценарий",
        "campaignId": "campaign-1",
        "spendAllowed": True,
        "confirmationMatches": True,
        "safeBriefReady": True,
        "count": 1,
    }
    too_many = _evaluate(value)
    assert too_many["ready"] is False
    assert too_many["next"]["key"] == "media"
    assert "до пяти" in too_many["next"]["hint"]

    value["mediaCount"] = 5
    ready = _evaluate(value)
    assert ready["ready"] is True
    assert ready["total"] == 8


def test_paid_photo_readiness_uses_photo_specific_steps_and_confirmation() -> None:
    value = {
        "mode": "real_photo",
        "sku": "WB-123",
        "productName": "Точный товар",
        "productCategory": "cosmetics",
        "platform": "tiktok",
        "destinationRef": "@brand",
        "mediaCount": 6,
        "brief": "",
        "campaignId": "campaign-1",
        "spendAllowed": True,
        "confirmationMatches": False,
        "safeBriefReady": True,
        "count": 1,
    }
    too_many = _evaluate(value)
    assert too_many["real"] is True
    assert too_many["total"] == 8
    assert too_many["next"]["key"] == "media"
    assert "до пяти" in too_many["next"]["hint"]

    value["mediaCount"] = 3
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
    assert ready["completed"] == ready["total"] == 8


def test_paid_readiness_does_not_claim_launch_before_auto_brief_is_verified() -> None:
    value = {
        "mode": "real_seedance",
        "sku": "WB-123",
        "productName": "Пароварка",
        "productCategory": "household",
        "platform": "tiktok",
        "destinationRef": "@brand",
        "mediaCount": 3,
        "brief": "Безопасное авто-ТЗ",
        "campaignId": "campaign-1",
        "spendAllowed": True,
        "confirmationMatches": True,
        "safeBriefReady": False,
        "safeBriefHint": "Идёт бесплатная проверка авто-ТЗ.",
        "count": 1,
    }
    checking = _evaluate(value)
    assert checking["ready"] is False
    assert checking["completed"] == 7
    assert checking["total"] == 8
    assert checking["next"]["key"] == "safe_brief"
    assert checking["next"]["hint"] == "Идёт бесплатная проверка авто-ТЗ."

    value["safeBriefReady"] = True
    ready = _evaluate(value)
    assert ready["ready"] is True
    assert ready["completed"] == ready["total"] == 8


def test_generation_form_updates_readiness_live_and_starts_fail_closed() -> None:
    assert 'from "./generation-form-readiness.js?v=20260729.2"' in APP
    assert "function syncGenerationFormReadiness(form)" in APP
    assert "syncGenerationFormReadiness(form);" in APP
    assert 'id="generation-readiness"' in MODULE_TEXT
    assert 'data-signature="${signature}"' in MODULE_TEXT
    assert "current.dataset.signature !== readiness.signature" in APP
    assert 'id="generation-submit" class="btn btn-block" type="submit" disabled' in APP
    assert "Заполните обязательные шаги" in APP
    assert '"Проверенное авто-ТЗ"' in MODULE_TEXT
    assert "safeBriefReady: safety.ready" in APP
    assert "safeBriefState: safety.state" in APP
    assert "function generationPaidSafetyState(form)" in APP
    assert '? "Проверяем платный запуск — не повторяйте"' in APP
    assert ': "Создаём dry-run задачи…"' in APP
    mock_submit = APP[
        APP.index("async function submitMockBatch")
        : APP.index("async function submitManualMetric")
    ]
    assert mock_submit.index("setFormBusy(form, false)") < mock_submit.index("form.reset()")
    assert ".generation-readiness__steps" in STYLES
    assert "@media (max-width: 820px)" in STYLES
    assert ".generation-readiness__steps { grid-template-columns: 1fr; }" in STYLES
    assert './styles.css?v=20260729.3' in INDEX
    assert './app.js?v=20260730.1' in INDEX


def test_mode_label_and_auto_brief_status_follow_selected_duration() -> None:
    select_markup = APP[
        APP.index('<select id="generation-mode"'):
        APP.index('id="generation-duration-field"')
    ]
    assert "generationModeChoiceLabel(REAL_SEEDANCE_MODE)" in select_markup
    assert "REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE].label" not in select_markup
    assert '"Блогер + голос · Seedance 2 Fast"' in APP
    assert (
        "`Авто-ТЗ готово: ${durationSeconds} секунд, точный товар и короткая дословная реплика.`"
        in APP
    )


def test_mock_mode_truthfully_describes_tasks_without_media_rendering() -> None:
    ready = _evaluate(
        {
            "mode": "mock",
            "sku": "WB-123",
            "productName": "Точный товар",
            "platform": "instagram",
            "destinationRef": "@brand",
            "mediaCount": 1,
            "count": 5,
            "maxMockCount": 50,
        }
    )
    assert ready["ready"] is True

    assert "Dry-run задач · без файлов и списаний" in APP
    assert "Изображение и видео в dry-run не создаются" in APP
    assert "Количество dry-run задач" in APP
    assert "Этот текст не запускает рендер" in APP
    assert "Создать dry-run задач" in APP
    assert "Фото и видео не генерировались" in APP
    assert "Dry-run задач · медиафайлы не создавались" in APP
    assert "Будут созданы задачи без фото или видео" in MODULE_TEXT


def test_paid_mode_outcome_and_human_brief_are_described_truthfully() -> None:
    assert 'id="generation-outcome-copy"' in APP
    assert "function generationOutcomeCopy(mode" in APP
    assert "Одно платное вертикальное UGC-видео с голосом" in APP
    assert "outcomeCopy.textContent = generationOutcomeCopy(mode, sku)" in APP
    assert "form.dataset.generationScenarioIntent" in APP
    assert "Замысел пользователя" in (
        ROOT / "web/app/content-generation-handoff.js"
    ).read_text(encoding="utf-8")
    assert "Опишите сцену своими словами" in APP
