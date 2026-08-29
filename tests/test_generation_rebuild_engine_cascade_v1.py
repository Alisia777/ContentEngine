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


def between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_strategy_panel_carries_the_registry_cascade() -> None:
    source = text(INTAKE)
    panel = source[source.index("function strategyPanel()"):source.index("function placeGuidedShell(")]
    # Запись 29.08.2026: пин сдвинут ОСОЗНАННО — панель «Создания» переехала на
    # компактную раскладку (main/rail): каскад больше не пришивается напрямую к
    # panel, а живёт видимой картой внутри main. Инвариант прежний — каскад
    # реестра присутствует и не скрыт.
    assert 'const engines = engineCascadeCard("strategy_video");' in panel
    assert "engines.hidden = false;" in panel
    main_append = between(panel, "main.append(", ");")
    assert "engines," in main_append
    assert 'refreshEngineChoice(form, state, "strategy_video");' in source


def test_legacy_runway_advisor_hides_under_a_selected_strategy() -> None:
    source = text(GUIDED)
    assert "advisor.hidden = strategySelected;" in source
    assert "advisor.hidden = false;\n    advisor.dataset.strategyAdvisoryOnly" not in source
