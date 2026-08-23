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
GUIDED = (ROOT / "web/app/workspace-os-v4-generation-guided.js").read_text(
    encoding="utf-8"
)
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


def test_mock_readiness_guides_user_through_five_explicit_human_steps() -> None:
    empty = _evaluate({"mode": "mock", "count": 5, "maxMockCount": 10})
    assert empty["ready"] is False
    assert empty["total"] == 5
    assert empty["completed"] == 2
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
    assert ready["completed"] == ready["total"] == 5


def test_no_launch_mode_is_selected_or_inferred_implicitly() -> None:
    blank = _evaluate(
        {
            "mode": "",
            "sku": "WB-123",
            "productName": "Точный товар",
            "platform": "instagram",
            "destinationRef": "@brand",
            "mediaCount": 1,
            "count": 5,
            "maxMockCount": 10,
        }
    )
    assert blank["ready"] is False
    assert blank["real"] is False
    assert blank["mock"] is False
    assert blank["modeSelected"] is False
    assert blank["next"]["key"] == "mode"
    assert blank["steps"][0]["label"] == "Способ создания"
    assert all(step["key"] != "count" for step in blank["steps"])


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


def test_internal_auto_brief_is_not_a_separate_human_step() -> None:
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
    assert checking["ready"] is True
    assert checking["completed"] == checking["total"] == 8
    assert all(step["key"] != "safe_brief" for step in checking["steps"])

    value["safeBriefReady"] = True
    ready = _evaluate(value)
    assert ready["ready"] is True
    assert ready["completed"] == ready["total"] == 8


def test_generation_form_updates_readiness_live_and_starts_fail_closed() -> None:
    assert 'from "./generation-form-readiness.js?v=20260805.1"' in APP
    assert "function syncGenerationFormReadiness(form)" in APP
    assert "syncGenerationFormReadiness(form);" in APP
    assert 'id="generation-readiness"' in MODULE_TEXT
    assert 'data-signature="${signature}"' in MODULE_TEXT
    assert "current.dataset.signature !== readiness.signature" in APP
    assert 'id="generation-submit" class="btn btn-block" type="submit" disabled' in APP
    assert "Заполните обязательные шаги" in APP
    assert '"Проверенное авто-ТЗ"' not in MODULE_TEXT
    assert "safeBriefReady: safety.ready" not in APP
    assert "safeBriefState: safety.state" not in APP
    assert "function generationPaidSafetyState(form)" in APP
    assert '? "Готовим ТЗ и проверяем запуск — не повторяйте"' in APP
    assert '? "Создаём dry-run задачи…"' in APP
    assert ': "Проверяем выбранный способ…"' in APP
    mock_submit = APP[
        APP.index("async function submitMockBatch")
        : APP.index("async function submitManualMetric")
    ]
    assert mock_submit.index("setFormBusy(form, false)") < mock_submit.index("form.reset()")
    assert ".generation-readiness__steps" in STYLES
    assert "@media (max-width: 820px)" in STYLES
    assert ".generation-readiness__steps { grid-template-columns: 1fr; }" in STYLES
    assert './styles.css?v=20260730.4' in INDEX
    assert './app.js?v=20260823.copy-engines.50' in INDEX


def test_mode_label_and_auto_brief_status_follow_selected_duration() -> None:
    select_markup = APP[
        APP.index('<select id="generation-mode"'):
        APP.index('id="generation-duration-field"')
    ]
    assert "generationModeChoiceLabel(REAL_SEEDANCE_MODE)" in select_markup
    assert "REAL_GENERATION_SKUS[REAL_SEEDANCE_MODE].label" not in select_markup
    assert '"Ролик с человеком и голосом"' in APP
    assert "Сколько секунд должен длиться ролик?" in APP
    assert "Seedance 2 Fast поддерживает 4, 8, 12 или 15 секунд" in APP
    assert "Gen‑4 Turbo поддерживает 2, 5, 8 или 10 секунд" in APP
    assert "option.hidden = unavailable" in APP


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


def test_new_launch_has_no_hidden_dry_run_default() -> None:
    start = APP.index("const defaultMode = repairReady")
    default_mode = APP[start : APP.index("const defaultCampaignId", start)]
    assert ': "";' in default_mode
    assert 'MOCK_GENERATION_ENABLED\n      ? "mock"' not in default_mode
    assert "Сначала выберите способ создания" in APP
    submit_start = APP.index("async function submitGenerationBatch")
    submit = APP[submit_start : APP.index("function validateGenerationPreflight", submit_start)]
    assert 'String(values.get("generation_mode") || "").trim()' in submit
    assert "Dry-run и платная генерация никогда не выбираются скрыто" in submit
    assert "await submitMockBatch(form, values)" in submit
    assert '["real_photo", "real_seedance", "real_gen4"].includes(' in GUIDED
    assert 'value || "mock") !== "mock"' not in GUIDED
    assert 'String(value.mode || "").trim()' in MODULE_TEXT
    assert 'String(form.elements.generation_mode?.value || "")' in APP
    assert 'submit.dataset.launchPhase = !modeSelected' in APP
    assert '"Выберите способ создания"' in APP


def test_submit_phase_flags_belong_to_the_readiness_owner() -> None:
    handoff_owner = APP[
        APP.index("function syncContentGenerationHandoff(form)") :
        APP.index("function generationVideoReferenceForForm(form)")
    ]
    readiness_owner = APP[
        APP.index("function syncGenerationFormReadiness(form)") :
        APP.index("function applyContentGenerationHandoffToForm()")
    ]
    assert "const modeSelected = Boolean(mode);" in readiness_owner
    assert 'const mock = mode === "mock";' in readiness_owner
    assert "submit.dataset.launchPhase = !modeSelected" in readiness_owner
    assert "const modeSelected = Boolean(mode);" not in handoff_owner
    assert 'const mock = mode === "mock";' not in handoff_owner


def test_paid_mode_outcome_and_human_brief_are_described_truthfully() -> None:
    assert 'id="generation-outcome-copy"' in APP
    assert "function generationOutcomeCopy(mode" in APP
    assert "Одно платное вертикальное UGC-видео с голосом" in APP
    assert "outcomeCopy.textContent = generationOutcomeCopy(mode, sku)" in APP
    assert "form.dataset.generationScenarioIntent" in APP
    assert "Замысел пользователя" in (
        ROOT / "web/app/content-generation-handoff.js"
    ).read_text(encoding="utf-8")
    assert "Опишите цельный сюжет обычным языком" in APP
