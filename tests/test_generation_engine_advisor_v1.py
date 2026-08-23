"""ИИ-центр советует движок «Копии» по фактам запуска, человек может выбрать иной.

Советчик — чистый модуль (web/app/generation-engine-advisor.js): исполняется в
Node на таблице случаев. Экран (generation-strategy-intake-v4.js) обязан
ставить совет по умолчанию, но явный выбор человека — выше совета.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADVISOR = ROOT / "web/app/generation-engine-advisor.js"
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"
ADVISOR_SOURCE = ADVISOR.read_text(encoding="utf-8")
INTAKE_SOURCE = INTAKE.read_text(encoding="utf-8")

PIKA = "fal:fal-ai/pika/v2/pikaswaps"
KLING_STD = "fal:fal-ai/kling-video/o3/standard/video-to-video/edit"
KLING_PRO = "fal:fal-ai/kling-video/o3/pro/video-to-video/edit"
HORSE = "fal:alibaba/happy-horse/video-edit"
SEEDANCE = "fal:bytedance/seedance-2.5/reference-to-video"
MINIMAX = "fal:minimax/h3/reference-to-video"
ALEPH = "runway:aleph2"


def _route(
    engine_id: str,
    *,
    tier: str,
    price_kind: str,
    rate: int | None,
    family: str = "edit",
    images: int,
    style: str,
    min_side: int | None = None,
    duration_source: str = "source_video",
    window: tuple[int, int] = (3, 15),
    keeps_audio: bool = True,
    recommended: bool = False,
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "id": engine_id,
        "label": engine_id.split(":", 1)[1],
        "tier": tier,
        "priceKind": price_kind,
        "priceRateMinor": rate,
        "minDurationSeconds": window[0],
        "maxDurationSeconds": window[1],
        "durationSource": duration_source,
        "engineFamily": family,
        "inputProfile": {
            "video": {
                "min_seconds": window[0],
                "max_seconds": window[1],
                "min_short_side_px": min_side,
                "max_long_side_px": None,
            },
            "images": {"max": images, "style": style},
            "keeps_source_audio": keeps_audio,
        },
        "recommended": recommended,
        "enabled": enabled,
    }


ROUTES = [
    _route(PIKA, tier="cheap", price_kind="usd_minor_per_run", rate=47, images=1,
           style="region", window=(1, 15), recommended=True),
    _route(KLING_STD, tier="cheap", price_kind="usd_minor_per_second", rate=13,
           images=4, style="at_refs", min_side=720),
    _route(KLING_PRO, tier="medium", price_kind="usd_minor_per_second", rate=17,
           images=4, style="at_refs", min_side=720),
    _route(HORSE, tier="medium", price_kind="usd_minor_per_second", rate=14,
           images=5, style="at_refs", min_side=320),
    _route(SEEDANCE, tier="premium", price_kind="usd_minor_per_second", rate=58,
           images=6, style="at_refs", min_side=300, window=(4, 15),
           keeps_audio=False),
    _route(MINIMAX, tier="cheap", price_kind="usd_minor_per_second", rate=6,
           family="regenerate", images=5, style="named_refs",
           duration_source="operator_choice", window=(5, 15), keeps_audio=False),
    _route(ALEPH, tier="premium", price_kind="runway_credit_tiers", rate=None,
           images=0, style="none", window=(4, 15), keeps_audio=False),
]


def _advise(facts: dict[str, object], routes: list[dict[str, object]] = ROUTES):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the advisor contract")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        (directory / ADVISOR.name).write_text(ADVISOR_SOURCE, encoding="utf-8")
        (directory / "contract.js").write_text(
            "import { adviseGenerationEngine } from './generation-engine-advisor.js';\n"
            f"const routes = {json.dumps(routes)};\n"
            f"const facts = {json.dumps(facts, ensure_ascii=False)};\n"
            "process.stdout.write(JSON.stringify(adviseGenerationEngine({ routes, facts })));\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [node, "contract.js"], cwd=directory, capture_output=True,
            text=True, encoding="utf-8", timeout=20, check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_large_product_with_several_photos_gets_a_multi_angle_editor() -> None:
    advice = _advise({
        "sourceDurationSeconds": 12, "sourceShortSidePx": 1080,
        "productImageCount": 4, "productCategory": "household",
        "brief": "мангал ROASTER с боковыми столиками",
    })
    assert advice["engineId"] == KLING_STD
    assert advice["basis"]["wantsAngles"] is True
    assert any("ракурс" in reason for reason in advice["reasons"])
    assert advice["alternatives"][0]["engineId"] == HORSE
    assert advice["excluded"] == []


def test_small_product_with_one_photo_gets_the_flat_price_editor() -> None:
    advice = _advise({
        "sourceDurationSeconds": 5, "productImageCount": 1,
        "productCategory": "cosmetics", "brief": "крем для лица",
    })
    assert advice["engineId"] == PIKA
    assert advice["basis"]["wantsAngles"] is False
    assert any("за ролик целиком" in reason for reason in advice["reasons"])


def test_low_resolution_source_excludes_engines_that_need_720px() -> None:
    advice = _advise({
        "sourceDurationSeconds": 12, "sourceShortSidePx": 540,
        "productImageCount": 4, "productCategory": "household", "brief": "",
    })
    assert advice["engineId"] == HORSE
    excluded = {item["engineId"]: item["reason"] for item in advice["excluded"]}
    assert KLING_STD in excluded and KLING_PRO in excluded
    assert "720px" in excluded[KLING_STD]
    assert HORSE not in excluded


def test_source_longer_than_every_editor_falls_back_to_regeneration() -> None:
    advice = _advise({
        "sourceDurationSeconds": 20, "productImageCount": 2,
        "productCategory": "apparel", "brief": "",
    })
    # Пересборщик тоже не берёт референс длиннее 15 с — совета нет.
    assert advice["engineId"] is None
    assert {item["engineId"] for item in advice["excluded"]} == {
        PIKA, KLING_STD, KLING_PRO, HORSE, SEEDANCE, MINIMAX, ALEPH,
    }


def test_regeneration_is_only_advised_when_no_editor_fits() -> None:
    routes = [route for route in ROUTES if route["id"] in {MINIMAX, KLING_STD}]
    advice = _advise({
        "sourceDurationSeconds": 10, "sourceShortSidePx": 600,
        "productImageCount": 4, "productCategory": "household", "brief": "",
    }, routes)
    assert advice["engineId"] == MINIMAX
    assert any("пересобирает" in reason for reason in advice["reasons"])
    assert advice["excluded"][0]["engineId"] == KLING_STD


def test_budget_ceiling_excludes_engines_that_cost_more() -> None:
    advice = _advise({
        "sourceDurationSeconds": 8, "productImageCount": 3,
        "productCategory": "electronics", "brief": "", "budgetMinorPerRun": 60,
    })
    assert advice["engineId"] == PIKA
    excluded = {item["engineId"] for item in advice["excluded"]}
    assert {KLING_STD, KLING_PRO, HORSE, SEEDANCE, ALEPH} <= excluded
    assert MINIMAX not in excluded


def test_premium_regeneration_is_never_the_default_while_an_editor_fits() -> None:
    for count in (1, 4, 9):
        advice = _advise({
            "sourceDurationSeconds": 6, "sourceShortSidePx": 1080,
            "productImageCount": count, "productCategory": "other", "brief": "",
        })
        assert advice["engineId"] != SEEDANCE, count
        assert advice["engineId"] != MINIMAX, count


def test_disabled_routes_and_unknown_facts_are_tolerated() -> None:
    routes = [{**route, "enabled": False} for route in ROUTES]
    advice = _advise({}, routes)
    assert advice["engineId"] is None
    assert advice["version"] == "generation-engine-advisor-v1"
    advice = _advise({"brief": None, "productImageCount": "x"})
    assert advice["engineId"] == PIKA


def test_advisor_is_pure() -> None:
    for forbidden in ("document.", "window.", "fetch(", "localStorage", "sessionStorage"):
        assert forbidden not in ADVISOR_SOURCE


def test_screen_prefers_human_choice_over_advice_and_re_advises_otherwise() -> None:
    # Советчик грузится лениво: стенды исполняют intake-v4 без него, и экран
    # обязан работать с прежней отметкой реестра, пока модуль не подъехал.
    assert "import(" + chr(10) + '  "./generation-engine-advisor.js?v=' in INTAKE_SOURCE
    assert 'typeof adviseGenerationEngine === "function"' in INTAKE_SOURCE
    assert ").catch(() => null);" in INTAKE_SOURCE
    render = INTAKE_SOURCE.split("function renderEngineChoice(", 1)[1].split(
        "let copyChecklistBusy = false;", 1
    )[0]
    assert "adviseGenerationEngine({" in render
    assert "? copyEngineFacts(form, state)" in render
    assert ": rebuildEngineFacts(form, state)," in render
    human = render.index("const humanChoice = cascade.humanChoice === true")
    selected = render.index("const selectedEngine = humanChoice")
    advised = render.index("|| advisedEngine")
    registry = render.index("engine.recommended && engine.enabled")
    assert human < selected < advised < registry
    assert "recommended: engine.id === advisedId," in render
    assert "engineAdviceNote(selectedEngine, activeEngine, advice)" in render
    assert "humanChoice: cascade.humanChoice === true && humanChoice !== null," in render
    chip = INTAKE_SOURCE.split("function captureExpressCommittedInput(", 1)[1].split(
        "function applyExpressDefaults(", 1
    )[0]
    assert "humanChoice: true," in chip
    note = INTAKE_SOURCE.split("function engineAdviceNote(", 1)[1].split(
        "function engineLabelById(", 1
    )[0]
    assert "выбор человека важнее совета" in note
    assert "ИИ-центру нечего посоветовать" in note
    assert "Отсеяно:" in note
