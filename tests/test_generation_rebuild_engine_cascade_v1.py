"""«Создание» показывает движки из того же реестра, что «Копия» и «Дуэт» (23.08.2026).

Владелица: «в создании ролика только Runway — модели не сходятся, везде
разные». Реестр (202608230021) давал «Созданию» четыре движка fal, но на экране
в шаге «Модель» полного мастера стоял старый каталог Runway «как совет», а
каскад реестра панель «Создания» не рисовала.

Контракт: панель «Создания» несёт тот же каскад «модель → сложность →
длительность»; старый каталог моделей при выбранной стратегии скрыт.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"
GUIDED = ROOT / "web/app/workspace-os-v4-generation-guided.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_strategy_panel_carries_the_registry_cascade() -> None:
    source = text(INTAKE)
    panel = source[source.index("function strategyPanel()"):source.index("function placeGuidedShell(")]
    assert 'panel.append(engineCascadeCard("strategy_video"), host);' in panel
    assert 'refreshEngineChoice(form, state, "strategy_video");' in source


def test_legacy_runway_advisor_hides_under_a_selected_strategy() -> None:
    source = text(GUIDED)
    assert "advisor.hidden = strategySelected;" in source
    assert "advisor.hidden = false;\n    advisor.dataset.strategyAdvisoryOnly" not in source
