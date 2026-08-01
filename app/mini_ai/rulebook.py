"""Human-readable, immutable rules for the ContentEngine mini-AI."""

from __future__ import annotations

from dataclasses import replace

from .schema import MiniAiRules, RiskPreset


DEFAULT_RULES = MiniAiRules()


_PRESET_OVERRIDES = {
    RiskPreset.CONSERVATIVE: {
        "maximum_batch_size": 6,
        "minimum_relative_uplift": 0.20,
        "minimum_qa_rate": 0.80,
        "maximum_failure_rate": 0.20,
        "winner_allocation": 0.65,
        "control_allocation": 0.35,
    },
    RiskPreset.BALANCED: {},
    RiskPreset.EXPLORATORY: {
        "maximum_batch_size": 12,
        "minimum_relative_uplift": 0.12,
        "minimum_qa_rate": 0.65,
        "maximum_failure_rate": 0.35,
        "winner_allocation": 0.70,
        "control_allocation": 0.30,
    },
}


RULES_RU: tuple[tuple[str, str], ...] = (
    (
        "Один цикл — один вопрос",
        "В одном массовом тесте меняется только один главный фактор: сценарный угол, длительность, доказательство или CTA.",
    ),
    (
        "Точный товар неизменяем",
        "SKU, категория, площадка, исходники, свойства, цена и разрешённые claims не меняются между вариантами.",
    ),
    (
        "Новая категория начинает с нуля",
        "Победитель косметики, корма, автозвука или другой категории не переносится в новый товар. Разрешён только безопасный контроль.",
    ),
    (
        "Контроль остаётся всегда",
        "Даже после появления победителя минимум 20% следующего теста остаётся за контрольным вариантом.",
    ),
    (
        "Восемь секунд — не закон",
        "Длительность выбирается только по matched-результатам той же категории, SKU, площадки и модели.",
    ),
    (
        "Просмотры не выбирают победителя",
        "Главный сигнал — заказы, продажи, конверсия, стоимость заказа и независимый QA. Просмотры используются только как диагностика.",
    ),
    (
        "Нет зрелых данных — нет вывода",
        "Мини-ИИ прямо пишет, что данных мало, и назначает следующий сбор. Он не придумывает победителя из двух роликов.",
    ),
    (
        "Первый критический дефект останавливает пакет",
        "Подмена товара, упаковки, логотипа, обязательного реквизита или иной критический QA-блокер ставит очередь на паузу.",
    ),
    (
        "Массовость ограничена",
        "За один управляемый пакет запускается не более 12 вариантов, последовательно и внутри серверных лимитов кампании.",
    ),
    (
        "Вывод объясним",
        "Каждое решение содержит факты, пороги, контроль, ограничения, уверенность и конкретный следующий шаг.",
    ),
    (
        "Никакого автоматического масштабирования",
        "Даже устойчивый winner требует человеческого подтверждения перед увеличением доли и бюджета.",
    ),
)


def rules_for_preset(preset: RiskPreset) -> MiniAiRules:
    """Return a validated rulebook for one bounded risk preset."""

    overrides = _PRESET_OVERRIDES[preset]
    return replace(DEFAULT_RULES, **overrides)


def rulebook_ru(rules: MiniAiRules = DEFAULT_RULES) -> str:
    """Render the rulebook in the same language operators see in the portal."""

    lines = [f"Свод правил мини-ИИ · {rules.version}"]
    for index, (title, text) in enumerate(RULES_RU, start=1):
        lines.append(f"{index}. {title}. {text}")
    lines.extend(
        (
            f"Порог зрелости: не меньше {rules.minimum_observations_per_arm} результатов на каждый вариант.",
            f"Порог QA: не ниже {rules.minimum_qa_rate:.0%}.",
            f"Максимальная доля технических ошибок: {rules.maximum_failure_rate:.0%}.",
            f"Минимальный относительный отрыв winner: {rules.minimum_relative_uplift:.0%}.",
        )
    )
    return "\n".join(lines)
