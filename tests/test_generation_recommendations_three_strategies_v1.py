"""Рекомендации ИИ-центра на всех трёх способах создания (23.08.2026).

До этого блок рекомендаций жил в шаге «Замысел» полного мастера, который в
компактных панелях «Копии» и «Дуэта» скрыт стилями — он делал запросы и
оставался невидимым ровно на платных маршрутах. А словарь исследования знал
только режимы моделей, и ИИ не мог посоветовать способ.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "web/app/workspace-generation-research-recommendations.js"
BRIDGE_CSS = ROOT / "web/app/workspace-generation-research-recommendations.css"
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"
RESEARCH_EDGE = ROOT / "supabase/functions/creator-product-research/index.ts"
MIGRATION = ROOT / "supabase/migrations/202608230025_research_recommendation_strategy_v1.sql"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_recommendation_root_follows_the_active_route() -> None:
    source = text(BRIDGE)
    assert 'const COMPACT_ROUTES = new Set(["copy_video", "avatar_video"]);' in source
    assert "function rootHost(form)" in source
    assert '`[data-generation-intake-recommendation="${route}"]`' in source
    assert "function placeRoot(root, form)" in source
    # Корень переезжает при смене маршрута, а не прибивается при первом монтировании.
    assert "placeRoot(root, form);\n  return root;" in text(BRIDGE)
    css = text(BRIDGE_CSS)
    assert ".generation-intake-v4__recommendation > .generation-research-recommendations" in css


def test_one_recommendation_becomes_three_route_specific_briefs() -> None:
    source = text(BRIDGE)
    assert "function formatCopyRecommendation(" in source
    assert "function formatDuetRecommendation(" in source
    assert 'if (route === "copy_video") {' in source
    assert 'if (route === "avatar_video") return formatDuetRecommendation(recommendation);' in source
    assert "route: intakeRoute(form)," in source
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI contracts"
    script = """
      import { formatResearchRecommendation } from %s;
      const item = { recommendation: {
        title: 'Гриль дома', hook: 'Почему все так жарят?',
        key_message: 'Стейк за пять минут без дыма',
        spoken_script: 'Смотрите, как он переворачивает стейк.',
        shot_list: [{ seconds: '0–2', visual: 'Крупный план решётки', voiceover: 'без голоса', on_screen_text: 'без текста' }],
        visual_direction: 'Тёплый свет, крупные планы мяса', cta: 'Попробуйте дома',
        avoid_claims: ['полезнее жарки'], proof_points: ['покрытие'], target_audience: ['повара'],
      } };
      const out = {};
      for (const route of ['copy_video', 'avatar_video', 'strategy_video']) {
        out[route] = formatResearchRecommendation(item, { route, productName: 'Гриль X' });
      }
      process.stdout.write(JSON.stringify(out));
    """ % json.dumps(BRIDGE.resolve().as_uri())
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    briefs = json.loads(result.stdout)
    assert briefs["copy_video"].startswith("СОХРАНИТЬ:")
    assert "Гриль X" in briefs["copy_video"]
    assert "НЕ ОБЕЩАТЬ" in briefs["copy_video"]
    # Речь ведущего — только слова, без заголовков секций.
    assert briefs["avatar_video"] == "Смотрите, как он переворачивает стейк."
    assert briefs["strategy_video"].startswith("ТОВАР:")
    assert "КОНЦЕПЦИЯ:" in briefs["strategy_video"]


def test_research_scenarios_name_a_strategy_with_a_reason() -> None:
    edge = text(RESEARCH_EDGE)
    assert 'enum: ["viral_product_swap", "viral_avatar_ugc", "viral_rebuild"],' in edge
    assert '"recommended_strategy",\n        "strategy_reason",' in edge
    assert 'scenario.recommended_generation_mode === "real_photo" &&\n        scenario.recommended_strategy !== "viral_rebuild"' in edge
    assert 'scenario.recommended_generation_mode === "real_seedance" &&\n        scenario.recommended_strategy === "viral_product_swap"' in edge
    prompt = edge.split("Для каждого сценария также выбери recommended_strategy", 1)[1][:900]
    for word in ("«Копия»", "«Дуэт»", "«Создание»", "strategy_reason"):
        assert word in prompt
    migration = text(MIGRATION)
    assert "''recommended_strategy'', case" in migration
    assert "''strategy_reason'', coalesce(" in migration
    assert "contentengine_decide_ai_research_training_unscoped_v1(jsonb)" in migration


def test_the_screen_shows_the_strategy_advice_and_lets_the_human_switch() -> None:
    source = text(BRIDGE)
    assert "function strategyAdviceNodes(envelope)" in source
    assert "ИИ-центр советует способ:" in source
    assert "data-research-recommendation-switch-route" in source.replace("researchRecommendationSwitchRoute", "data-research-recommendation-switch-route")
    assert "function handleStrategySwitchClick(event)" in source
    # Переключение способа — явный клик человека по кнопке панели маршрутов.
    assert '`[data-generation-intake-route="${route}"]`' in source
    intake = text(INTAKE)
    assert 'if (!DEFAULT_BRIEF_TEMPLATES[route] && route !== "strategy_video") return;' in intake
    for label in ("Что сохранить и как заменить товар", "Речь ведущего", "Концепция нового ролика"):
        assert label in intake
