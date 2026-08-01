"""Deterministic mass-generation planning for the ContentEngine mini-AI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Iterable, Sequence

from app.external_learning import (
    CreativeObservation,
    FunnelDecision,
    MODEL_DURATION_OPTIONS,
    PolicyMode,
    ProviderModel,
    choose_duration_plan,
    select_successful_creatives,
)

from .rulebook import rules_for_preset
from .schema import (
    ExperimentArm,
    ExperimentDimension,
    MassGenerationPlan,
    MiniAiContext,
    MiniAiRules,
    PlanMode,
)


_ANGLE_LABELS = {
    "demonstration": "Контроль · понятная демонстрация",
    "product_focus": "Товар в центре",
    "problem_first": "Проблема в первом кадре",
    "result_first": "Проверяемый результат первым",
    "trust_builder": "Доверительная подача",
    "curiosity_gap": "Вопрос и любопытство",
}

_ANGLE_INSTRUCTIONS = {
    "demonstration": (
        "С первого кадра покажи точный товар и одно понятное действие. "
        "Не добавляй драматизацию, неподтверждённые свойства или чужие бренды."
    ),
    "product_focus": (
        "С первого кадра точный товар занимает главный план. Покажи форму, "
        "упаковку и одну проверяемую деталь без лишнего сюжета."
    ),
    "problem_first": (
        "Начни с одной узнаваемой бытовой проблемы без преувеличения, затем "
        "покажи точный товар как способ действия, а не как обещание результата."
    ),
    "result_first": (
        "Начни с наблюдаемого и проверяемого результата использования, затем "
        "покажи точный товар и действие, которое к нему привело."
    ),
    "trust_builder": (
        "Используй спокойную естественную подачу: точный товар, реальный масштаб, "
        "один честный аргумент и отсутствие агрессивных обещаний."
    ),
    "curiosity_gap": (
        "Начни с короткого вопроса о способе использования, затем сразу покажи "
        "точный товар и ответ действием в кадре."
    ),
}

_PROOF_INSTRUCTIONS = {
    "product_detail": (
        "Доказательство: крупно покажи одну подтверждённую деталь товара или упаковки."
    ),
    "usage_demo": (
        "Доказательство: покажи одно реальное действие с товаром без обещания эффекта."
    ),
    "feature_closeup": (
        "Доказательство: покажи одну подтверждённую функцию крупным планом и верни товар целиком в кадр."
    ),
}

_CTA_INSTRUCTIONS = {
    "soft_action": "CTA: предложи спокойно посмотреть товар или сохранить ролик без давления.",
    "direct_action": "CTA: один прямой призыв перейти к товару без срочности и ложного дефицита.",
    "no_cta": "CTA отсутствует: ролик заканчивается товаром и проверяемым действием.",
}

_BLOCKED_FUNNEL = {
    FunnelDecision.SUPPLY: (
        "mass_generation_blocked_supply",
        "Массовая генерация остановлена: сначала восстановите наличие и поставку.",
    ),
    FunnelDecision.EXPECTATION: (
        "mass_generation_blocked_expectation",
        "Массовая генерация остановлена: сначала устраните разрыв между обещанием и реальным товаром.",
    ),
    FunnelDecision.ADVERTISING: (
        "mass_generation_blocked_advertising",
        "Массовая генерация не является главным рычагом: сначала исправьте рекламу и распределение трафика.",
    ),
    FunnelDecision.MEASUREMENT: (
        "mass_generation_blocked_measurement",
        "Данных недостаточно для массового запуска. Сначала соберите измеримый базовый контроль.",
    ),
}


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _short_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _allocation_counts(batch_size: int, allocations: Sequence[float]) -> tuple[int, ...]:
    raw = [batch_size * value for value in allocations]
    counts = [max(1, int(value)) for value in raw]
    while sum(counts) > batch_size:
        candidates = [index for index, value in enumerate(counts) if value > 1]
        if not candidates:
            raise ValueError("batch_too_small_for_arms")
        index = min(candidates, key=lambda item: raw[item] - counts[item])
        counts[index] -= 1
    while sum(counts) < batch_size:
        index = max(range(len(counts)), key=lambda item: raw[item] - counts[item])
        counts[index] += 1
    return tuple(counts)


def _blocked_plan(
    context: MiniAiContext,
    rules: MiniAiRules,
    code: str,
    message: str,
) -> MassGenerationPlan:
    payload = {
        "rules": rules.version,
        "context": asdict(context),
        "blocker": code,
    }
    return MassGenerationPlan(
        plan_id=f"blocked-{_short_hash(payload)}",
        rules_version=rules.version,
        mode=PlanMode.BLOCKED,
        context=context,
        dimension=ExperimentDimension.AUTO,
        arms=(),
        batch_size=0,
        estimated_cost_minor=0,
        blockers=(message,),
        reason_codes=(code,),
    )


def _winner_angle(
    observations: Sequence[CreativeObservation],
    context: MiniAiContext,
) -> str | None:
    if context.approved_winner_angle:
        return _normalise(context.approved_winner_angle)
    candidates = select_successful_creatives(
        observations,
        category_key=context.learning_category_key,
        sku=context.sku,
        platform=context.platform,
        require_activation_approval=True,
        maximum_candidates=1,
        minimum_observations=3,
    )
    if not candidates:
        return None
    observation_id = candidates[0].observation_id
    return next(
        (
            _normalise(item.creative_angle)
            for item in observations
            if item.observation_id == observation_id
        ),
        None,
    )


def _base_duration(
    observations: Sequence[CreativeObservation],
    context: MiniAiContext,
) -> int:
    allowed = MODEL_DURATION_OPTIONS[context.model]
    if context.approved_winner_duration in allowed:
        return int(context.approved_winner_duration)
    if context.model is ProviderModel.GEN4_TURBO:
        return 5
    if context.model is ProviderModel.SEEDANCE2_FAST:
        return 8
    return 0


def _resolve_dimension(
    observations: Sequence[CreativeObservation],
    context: MiniAiContext,
) -> ExperimentDimension:
    if context.requested_dimension is not ExperimentDimension.AUTO:
        return context.requested_dimension
    if context.category_is_new:
        return ExperimentDimension.CREATIVE_ANGLE
    angle = _winner_angle(observations, context)
    if not angle:
        return ExperimentDimension.CREATIVE_ANGLE
    duration = choose_duration_plan(
        observations,
        model=context.model,
        category_key=context.learning_category_key,
        sku=context.sku,
        platform=context.platform,
        require_activation_approval=True,
    )
    if duration.mode is not PolicyMode.EXPLOIT:
        return ExperimentDimension.DURATION
    return ExperimentDimension.PROOF_TYPE


def _angle_values(winner: str | None) -> tuple[tuple[str, bool, float], ...]:
    control = "demonstration"
    if winner and winner != control:
        challenger = next(
            value
            for value in ("problem_first", "result_first", "product_focus", "trust_builder")
            if value not in {control, winner}
        )
        return (
            (winner, False, 0.50),
            (control, True, 0.25),
            (challenger, False, 0.25),
        )
    return (
        (control, True, 0.34),
        ("problem_first", False, 0.33),
        ("result_first", False, 0.33),
    )


def _duration_values(
    observations: Sequence[CreativeObservation],
    context: MiniAiContext,
) -> tuple[tuple[int, bool, float], ...]:
    plan = choose_duration_plan(
        observations,
        model=context.model,
        category_key=context.learning_category_key,
        sku=context.sku,
        platform=context.platform,
        require_activation_approval=True,
    )
    values = tuple(arm.seconds for arm in plan.arms)
    if len(values) < 2:
        if context.model is ProviderModel.GEN4_TURBO:
            values = (5, 8)
        elif context.model is ProviderModel.SEEDANCE2_FAST:
            values = (8, 12)
        else:
            values = (0,)
    if len(values) == 1:
        return ((values[0], True, 1.0),)
    first, second = values[:2]
    if plan.mode is PolicyMode.EXPLOIT:
        return ((first, False, 0.70), (second, True, 0.30))
    return ((first, True, 0.50), (second, False, 0.50))


def _arm(
    *,
    context: MiniAiContext,
    dimension: ExperimentDimension,
    value: str | int,
    is_control: bool,
    allocation: float,
    planned_count: int,
    base_duration: int,
    base_angle: str,
    ordinal: int,
) -> ExperimentArm:
    duration = base_duration
    angle = base_angle
    hook = "demonstration"
    proof = "product_detail"
    cta = "soft_action"
    if dimension is ExperimentDimension.CREATIVE_ANGLE:
        angle = str(value)
        hook = str(value)
        instruction = _ANGLE_INSTRUCTIONS.get(angle, _ANGLE_INSTRUCTIONS["demonstration"])
        label = _ANGLE_LABELS.get(angle, angle)
    elif dimension is ExperimentDimension.DURATION:
        duration = int(value)
        instruction = (
            f"Длительность теста: {duration} секунд. Сохрани тот же сценарный угол, "
            "товар, доказательство и CTA; не добавляй новые сцены только ради времени."
        )
        label = f"{duration} секунд"
    elif dimension is ExperimentDimension.PROOF_TYPE:
        proof = str(value)
        instruction = _PROOF_INSTRUCTIONS[proof]
        label = {
            "product_detail": "Контроль · деталь товара",
            "usage_demo": "Демонстрация использования",
            "feature_closeup": "Подтверждённая функция крупно",
        }[proof]
    elif dimension is ExperimentDimension.CTA_STYLE:
        cta = str(value)
        instruction = _CTA_INSTRUCTIONS[cta]
        label = {
            "soft_action": "Контроль · мягкий CTA",
            "direct_action": "Прямой CTA",
            "no_cta": "Без CTA",
        }[cta]
    else:
        raise ValueError("unsupported_experiment_dimension")
    identity = {
        "category": context.learning_category_key,
        "sku": context.sku,
        "platform": context.platform,
        "model": context.model.value,
        "dimension": dimension.value,
        "value": value,
        "ordinal": ordinal,
    }
    return ExperimentArm(
        arm_id=f"arm-{_short_hash(identity)}",
        label_ru=label,
        is_control=is_control,
        allocation=allocation,
        planned_count=planned_count,
        duration_seconds=duration,
        creative_angle=angle,
        hook_type=hook,
        proof_type=proof,
        cta_style=cta,
        instruction_ru=instruction,
        reason_codes=(
            "one_dimension_per_cycle",
            "same_product_category_platform_model",
            "control_retained" if is_control else "bounded_hypothesis",
        ),
    )


def build_mass_generation_plan(
    context: MiniAiContext,
    observations: Iterable[CreativeObservation] = (),
    *,
    rules: MiniAiRules | None = None,
) -> MassGenerationPlan:
    """Build a bounded, explainable plan for one mass-generation cycle."""

    selected_rules = rules or rules_for_preset(context.risk_preset)
    source = tuple(observations)
    if context.model is ProviderModel.SEEDREAM5_LITE:
        return _blocked_plan(
            context,
            selected_rules,
            "mass_video_only",
            "Этот контроллер управляет массовыми видеотестами. Для фото нужен отдельный план.",
        )
    if context.funnel_decision in _BLOCKED_FUNNEL:
        code, message = _BLOCKED_FUNNEL[context.funnel_decision]
        return _blocked_plan(context, selected_rules, code, message)

    dimension = _resolve_dimension(source, context)
    winner = _winner_angle(source, context)
    base_angle = winner or "demonstration"
    base_duration = _base_duration(source, context)

    if dimension is ExperimentDimension.CREATIVE_ANGLE:
        values = _angle_values(winner)
    elif dimension is ExperimentDimension.DURATION:
        values = _duration_values(source, context)
    elif dimension is ExperimentDimension.PROOF_TYPE:
        values = (
            ("product_detail", True, 0.34),
            ("usage_demo", False, 0.33),
            ("feature_closeup", False, 0.33),
        )
    elif dimension is ExperimentDimension.CTA_STYLE:
        values = (
            ("soft_action", True, 0.34),
            ("direct_action", False, 0.33),
            ("no_cta", False, 0.33),
        )
    else:
        return _blocked_plan(
            context,
            selected_rules,
            "dimension_unavailable",
            "Мини-ИИ не смог определить один безопасный вопрос для текущего цикла.",
        )

    maximum = min(selected_rules.maximum_batch_size, 12)
    batch_size = min(context.requested_batch_size, maximum)
    minimum_for_arms = max(selected_rules.minimum_batch_size, len(values) * 2)
    if batch_size < minimum_for_arms:
        return _blocked_plan(
            context,
            selected_rules,
            "batch_too_small",
            f"Для {len(values)} вариантов нужно минимум {minimum_for_arms} запусков: по два на каждый вариант.",
        )
    estimated = batch_size * context.unit_cost_minor
    if context.max_budget_minor and estimated > context.max_budget_minor:
        return _blocked_plan(
            context,
            selected_rules,
            "batch_budget_exceeded",
            "Стоимость пакета выше заданного лимита. Уменьшите число запусков или смените режим.",
        )

    counts = _allocation_counts(batch_size, [float(item[2]) for item in values])
    arms = tuple(
        _arm(
            context=context,
            dimension=dimension,
            value=value,
            is_control=is_control,
            allocation=count / batch_size,
            planned_count=count,
            base_duration=base_duration,
            base_angle=base_angle,
            ordinal=index,
        )
        for index, ((value, is_control, _allocation), count) in enumerate(zip(values, counts, strict=True))
    )
    control = next(item for item in arms if item.is_control)
    if control.allocation < selected_rules.minimum_control_share:
        return _blocked_plan(
            context,
            selected_rules,
            "control_share_too_small",
            "Контрольная группа получила слишком маленькую долю. План остановлен.",
        )

    mode = PlanMode.EXPLOIT_WITH_CONTROL if winner else PlanMode.EXPLORE
    canonical = {
        "rules": selected_rules.version,
        "context": asdict(context),
        "dimension": dimension.value,
        "arms": [asdict(item) for item in arms],
        "batch_size": batch_size,
    }
    warnings = (
        "Вывод будет доступен только после независимого QA, публикации и зрелых метрик.",
        "Автоматическое масштабирование запрещено: winner должен подтвердить человек.",
    )
    return MassGenerationPlan(
        plan_id=f"mini-ai-{_short_hash(canonical)}",
        rules_version=selected_rules.version,
        mode=mode,
        context=context,
        dimension=dimension,
        arms=arms,
        batch_size=batch_size,
        estimated_cost_minor=estimated,
        warnings=warnings,
        reason_codes=(
            "one_question_one_cycle",
            "views_never_define_winner",
            "new_category_isolated" if context.category_is_new else "matched_scope_only",
            "human_approval_before_scale",
        ),
    )
