"""Outcome aggregation and deterministic conclusions for the mini-AI."""

from __future__ import annotations

from collections import defaultdict
from math import inf
from typing import Iterable, Sequence

from .rulebook import rules_for_preset
from .schema import (
    ArmOutcome,
    ArmSummary,
    ExperimentDimension,
    LearningObjective,
    MassGenerationPlan,
    MiniAiConclusion,
    MiniAiDecision,
    MiniAiRules,
    OutcomeState,
    QaState,
)


def _next_dimension(value: ExperimentDimension) -> ExperimentDimension:
    return {
        ExperimentDimension.CREATIVE_ANGLE: ExperimentDimension.DURATION,
        ExperimentDimension.DURATION: ExperimentDimension.PROOF_TYPE,
        ExperimentDimension.PROOF_TYPE: ExperimentDimension.CTA_STYLE,
        ExperimentDimension.CTA_STYLE: ExperimentDimension.CREATIVE_ANGLE,
    }.get(value, ExperimentDimension.AUTO)


def _objective_value(
    objective: LearningObjective,
    *,
    orders_per_day: float,
    conversion: float,
    sales_per_day_minor: float,
    qa_rate: float,
    cost_per_order_minor: float | None,
) -> float:
    if objective is LearningObjective.ORDERS:
        return orders_per_day
    if objective is LearningObjective.SALES:
        return sales_per_day_minor
    if objective is LearningObjective.CONVERSION:
        return conversion
    if objective is LearningObjective.QA_ACCEPTANCE:
        return qa_rate
    if cost_per_order_minor is None:
        return -inf
    return -cost_per_order_minor


def _arm_summary(
    arm_id: str,
    outcomes: Sequence[ArmOutcome],
    objective: LearningObjective,
) -> ArmSummary:
    completed = [item for item in outcomes if item.completed]
    succeeded = [item for item in outcomes if item.state is OutcomeState.SUCCEEDED]
    eligible = [item for item in outcomes if item.commercially_eligible]
    qa_decided = [
        item
        for item in succeeded
        if item.qa_state in {QaState.APPROVED, QaState.NEEDS_CHANGES, QaState.REJECTED}
    ]
    approved = sum(item.qa_state is QaState.APPROVED for item in succeeded)
    failed = sum(item.state in {OutcomeState.FAILED, OutcomeState.CANCELLED} for item in outcomes)
    critical = sum(item.critical_blocker for item in outcomes)
    mismatches = sum(not item.product_fidelity_ok for item in outcomes)
    orders = sum(item.orders or 0 for item in eligible)
    carts = sum(item.carts or 0 for item in eligible)
    sales_minor = sum(item.sales_minor or 0 for item in eligible)
    spend_minor = sum(item.spend_minor or 0 for item in eligible)
    days = sum(item.attribution_days for item in eligible)
    views = sum(item.views or 0 for item in eligible)
    orders_per_day = orders / max(1, days)
    conversion = orders / max(1, carts)
    sales_per_day = sales_minor / max(1, days)
    qa_rate = approved / max(1, len(qa_decided))
    cost_per_order = spend_minor / orders if orders > 0 else None
    value = _objective_value(
        objective,
        orders_per_day=orders_per_day,
        conversion=conversion,
        sales_per_day_minor=sales_per_day,
        qa_rate=qa_rate,
        cost_per_order_minor=cost_per_order,
    )
    return ArmSummary(
        arm_id=arm_id,
        completed=len(completed),
        eligible=len(eligible),
        approved=approved,
        failed=failed,
        critical_blockers=critical,
        product_mismatches=mismatches,
        orders=orders,
        carts=carts,
        sales_minor=sales_minor,
        spend_minor=spend_minor,
        attribution_days=days,
        views=views,
        independent_jobs=len({item.job_id for item in outcomes}),
        independent_creators=len({item.creator_key for item in eligible if item.creator_key}),
        orders_per_day=round(orders_per_day, 6),
        conversion=round(conversion, 6),
        sales_per_day_minor=round(sales_per_day, 2),
        qa_rate=round(qa_rate, 6),
        cost_per_order_minor=(round(cost_per_order, 2) if cost_per_order is not None else None),
        objective_value=round(value, 6) if value not in {inf, -inf} else value,
    )


def _primary_metric_label(objective: LearningObjective) -> str:
    return {
        LearningObjective.ORDERS: "заказов в день",
        LearningObjective.SALES: "продаж в день",
        LearningObjective.CONVERSION: "конверсии корзина → заказ",
        LearningObjective.QA_ACCEPTANCE: "доли принятия QA",
        LearningObjective.COST_PER_ORDER: "стоимости заказа",
    }[objective]


def _primary_metric(summary: ArmSummary, objective: LearningObjective) -> float:
    if objective is LearningObjective.ORDERS:
        return summary.orders_per_day
    if objective is LearningObjective.SALES:
        return summary.sales_per_day_minor
    if objective is LearningObjective.CONVERSION:
        return summary.conversion
    if objective is LearningObjective.QA_ACCEPTANCE:
        return summary.qa_rate
    return summary.cost_per_order_minor if summary.cost_per_order_minor is not None else inf


def _winner_gap(
    winner: ArmSummary,
    control: ArmSummary,
    objective: LearningObjective,
) -> tuple[float, float, bool]:
    winner_value = _primary_metric(winner, objective)
    control_value = _primary_metric(control, objective)
    if objective is LearningObjective.COST_PER_ORDER:
        if winner_value == inf or control_value == inf or control_value <= 0:
            return 0.0, 0.0, False
        absolute = control_value - winner_value
        relative = absolute / control_value
        return absolute, relative, absolute > 0
    absolute = winner_value - control_value
    denominator = abs(control_value) if abs(control_value) > 1e-9 else 1.0
    relative = absolute / denominator
    return absolute, relative, absolute > 0


def _absolute_gap_required(objective: LearningObjective, rules: MiniAiRules) -> float:
    return {
        LearningObjective.ORDERS: rules.minimum_orders_per_day_gap,
        LearningObjective.SALES: float(rules.minimum_sales_per_day_gap_minor),
        LearningObjective.CONVERSION: rules.minimum_conversion_gap,
        LearningObjective.QA_ACCEPTANCE: rules.minimum_qa_gap,
        LearningObjective.COST_PER_ORDER: 0.0,
    }[objective]


def _format_metric(summary: ArmSummary, objective: LearningObjective) -> str:
    if objective is LearningObjective.ORDERS:
        return f"{summary.orders_per_day:.2f} заказа/день"
    if objective is LearningObjective.SALES:
        return f"{summary.sales_per_day_minor / 100:.2f} ₽/день"
    if objective is LearningObjective.CONVERSION:
        return f"{summary.conversion:.1%}"
    if objective is LearningObjective.QA_ACCEPTANCE:
        return f"{summary.qa_rate:.1%}"
    if summary.cost_per_order_minor is None:
        return "нет заказов"
    return f"{summary.cost_per_order_minor / 100:.2f} ₽/заказ"


def _base_conclusion(
    plan: MassGenerationPlan,
    decision: MiniAiDecision,
    summary_ru: str,
    next_action_ru: str,
    *,
    summaries: Sequence[ArmSummary],
    blockers: Sequence[str] = (),
    evidence: Sequence[str] = (),
    reason_codes: Sequence[str] = (),
    confidence: str = "low",
) -> MiniAiConclusion:
    control = next((item.arm_id for item in plan.arms if item.is_control), None)
    return MiniAiConclusion(
        decision=decision,
        confidence=confidence,
        summary_ru=summary_ru,
        next_action_ru=next_action_ru,
        control_arm_id=control,
        arm_summaries=tuple(summaries),
        blockers=tuple(blockers),
        evidence=tuple(evidence),
        reason_codes=tuple(reason_codes),
        next_dimension=plan.dimension,
    )


def evaluate_mass_generation(
    plan: MassGenerationPlan,
    outcomes: Iterable[ArmOutcome],
    *,
    rules: MiniAiRules | None = None,
) -> MiniAiConclusion:
    """Evaluate one cycle and produce an auditable Russian conclusion."""

    selected_rules = rules or rules_for_preset(plan.context.risk_preset)
    if not plan.executable:
        return _base_conclusion(
            plan,
            MiniAiDecision.BLOCKED,
            "Пакет не может быть запущен: правила нашли блокирующее условие.",
            plan.blockers[0] if plan.blockers else "Исправьте контекст и соберите план заново.",
            summaries=(),
            blockers=plan.blockers,
            reason_codes=("plan_not_executable",),
        )

    source = tuple(outcomes)
    arm_ids = {arm.arm_id for arm in plan.arms}
    if any(item.arm_id not in arm_ids for item in source):
        raise ValueError("outcome_arm_not_in_plan")
    if len({item.outcome_id for item in source}) != len(source):
        raise ValueError("duplicate_outcome_id")
    if len({item.job_id for item in source}) != len(source):
        raise ValueError("duplicate_generation_job")

    grouped: dict[str, list[ArmOutcome]] = defaultdict(list)
    for item in source:
        grouped[item.arm_id].append(item)
    summaries = tuple(
        _arm_summary(arm.arm_id, grouped[arm.arm_id], plan.context.objective)
        for arm in plan.arms
    )
    total_completed = sum(item.completed for item in summaries)
    total_failed = sum(item.failed for item in summaries)
    total_critical = sum(item.critical_blockers for item in summaries)
    total_mismatches = sum(item.product_mismatches for item in summaries)

    if selected_rules.pause_on_product_mismatch and total_mismatches:
        return _base_conclusion(
            plan,
            MiniAiDecision.PAUSE_QUALITY,
            "Очередь остановлена: хотя бы один ролик изменил или подменил точный товар.",
            "Не запускайте следующие варианты. Сначала разберите исходники, ТЗ и причину подмены товара.",
            summaries=summaries,
            blockers=(f"Подмена товара: {total_mismatches}",),
            evidence=("Первый product-fidelity дефект останавливает массовый пакет.",),
            reason_codes=("product_fidelity_stop",),
        )
    if total_critical > selected_rules.maximum_critical_blockers:
        return _base_conclusion(
            plan,
            MiniAiDecision.PAUSE_QUALITY,
            "Очередь остановлена из-за критического QA-блокера.",
            "Исправьте общий шаблон, затем начните новый пакет — не продолжайте размножать дефект.",
            summaries=summaries,
            blockers=(f"Критических блокеров: {total_critical}",),
            reason_codes=("critical_qa_stop",),
        )
    if total_completed >= selected_rules.minimum_total_observations:
        failure_rate = total_failed / max(1, total_completed)
        if failure_rate > selected_rules.maximum_failure_rate:
            return _base_conclusion(
                plan,
                MiniAiDecision.PAUSE_TECHNICAL,
                f"Техническая доля ошибок достигла {failure_rate:.0%}; сравнивать креативы сейчас нельзя.",
                "Остановите очередь и исправьте провайдера, исходники или технический контракт запуска.",
                summaries=summaries,
                blockers=(f"Технические ошибки: {total_failed} из {total_completed}",),
                reason_codes=("technical_failure_rate_stop",),
            )

    if not source:
        return _base_conclusion(
            plan,
            MiniAiDecision.COLLECT_MORE,
            "План готов, но результатов ещё нет.",
            "Запустите варианты по очереди. Мини-ИИ не сделает вывод до QA, публикации и зрелых метрик.",
            summaries=summaries,
            reason_codes=("no_outcomes",),
        )

    immature = sum(
        item.state is OutcomeState.SUCCEEDED and not item.commercially_eligible
        for item in source
    )
    if immature:
        return _base_conclusion(
            plan,
            MiniAiDecision.WAIT_METRICS,
            "Часть роликов создана, но ещё не прошла полный путь до зрелых метрик.",
            "Дождитесь независимого QA, публикации и окна атрибуции. Не выбирайте winner по ранним просмотрам.",
            summaries=summaries,
            evidence=(f"Незрелых успешных результатов: {immature}",),
            reason_codes=("metrics_not_mature", "views_ignored"),
        )

    insufficient = [
        item.arm_id
        for item in summaries
        if item.eligible < selected_rules.minimum_observations_per_arm
    ]
    if insufficient:
        return _base_conclusion(
            plan,
            MiniAiDecision.COLLECT_MORE,
            "Выборка пока слишком мала для честного вывода.",
            (
                "Доберите минимум "
                f"{selected_rules.minimum_observations_per_arm} зрелых результата на каждый вариант."
            ),
            summaries=summaries,
            evidence=(f"Недостаточно данных по arms: {', '.join(insufficient)}",),
            reason_codes=("minimum_arm_support_not_reached",),
        )

    qa_floor_failures = [
        item for item in summaries if item.qa_rate < selected_rules.minimum_qa_rate
    ]
    if qa_floor_failures:
        return _base_conclusion(
            plan,
            MiniAiDecision.PAUSE_QUALITY,
            "Массовый пакет не прошёл минимальный уровень качества.",
            "Сначала исправьте общий шаблон и повторите маленький контрольный пакет.",
            summaries=summaries,
            blockers=tuple(
                f"{item.arm_id}: QA {item.qa_rate:.0%}"
                for item in qa_floor_failures
            ),
            reason_codes=("qa_floor_not_reached",),
        )

    control_arm = next(item for item in plan.arms if item.is_control)
    control = next(item for item in summaries if item.arm_id == control_arm.arm_id)
    challengers = [item for item in summaries if item.arm_id != control.arm_id]
    if plan.context.objective is LearningObjective.COST_PER_ORDER:
        ranked = sorted(
            challengers,
            key=lambda item: item.cost_per_order_minor if item.cost_per_order_minor is not None else inf,
        )
    else:
        ranked = sorted(challengers, key=lambda item: item.objective_value, reverse=True)
    challenger = ranked[0]
    absolute, relative, direction_ok = _winner_gap(
        challenger,
        control,
        plan.context.objective,
    )
    absolute_required = _absolute_gap_required(plan.context.objective, selected_rules)
    relative_required = (
        selected_rules.minimum_cost_per_order_improvement
        if plan.context.objective is LearningObjective.COST_PER_ORDER
        else selected_rules.minimum_relative_uplift
    )
    qa_not_worse = challenger.qa_rate + 0.05 >= control.qa_rate
    winner_clear = (
        direction_ok
        and absolute >= absolute_required
        and relative >= relative_required
        and qa_not_worse
    )
    label = _primary_metric_label(plan.context.objective)
    evidence = (
        f"Контроль: {_format_metric(control, plan.context.objective)}; QA {control.qa_rate:.0%}.",
        f"Лучший challenger: {_format_metric(challenger, plan.context.objective)}; QA {challenger.qa_rate:.0%}.",
        f"Разница по метрике «{label}»: {absolute:+.3f} ({relative:+.1%}).",
        "Просмотры не использовались для выбора победителя.",
    )

    if winner_clear:
        confidence = "high" if min(control.eligible, challenger.eligible) >= 6 else "medium"
        allocations = {
            challenger.arm_id: selected_rules.winner_allocation,
            control.arm_id: selected_rules.control_allocation,
        }
        return MiniAiConclusion(
            decision=MiniAiDecision.PROMOTE_WITH_CONTROL,
            confidence=confidence,
            summary_ru=(
                "Есть устойчивый challenger, который превзошёл контроль по бизнес-метрике "
                "и не ухудшил QA. Это наблюдаемый winner, а не доказанная причинность."
            ),
            next_action_ru=(
                "После подтверждения человеком перенесите winner в следующий цикл, но оставьте "
                f"контроль {selected_rules.control_allocation:.0%}. Следующий вопрос: "
                f"{_next_dimension(plan.dimension).value}."
            ),
            winner_arm_id=challenger.arm_id,
            control_arm_id=control.arm_id,
            recommended_allocations=allocations,
            arm_summaries=summaries,
            evidence=evidence,
            reason_codes=(
                "business_metric_uplift",
                "qa_not_worse",
                "control_retained",
                "human_approval_required",
                "observational_not_causal",
            ),
            next_dimension=_next_dimension(plan.dimension),
        )

    if control.objective_value >= challenger.objective_value or not direction_ok:
        return MiniAiConclusion(
            decision=MiniAiDecision.KEEP_CONTROL,
            confidence="medium",
            summary_ru="Ни одна гипотеза не превзошла контроль достаточно уверенно.",
            next_action_ru=(
                "Оставьте контроль основным. Не масштабируйте красивый, но слабый вариант; "
                "назначьте новую ограниченную гипотезу в том же измерении."
            ),
            winner_arm_id=control.arm_id,
            control_arm_id=control.arm_id,
            recommended_allocations={control.arm_id: 0.80, challenger.arm_id: 0.20},
            arm_summaries=summaries,
            evidence=evidence,
            reason_codes=("control_not_beaten", "views_ignored"),
            next_dimension=plan.dimension,
        )

    return MiniAiConclusion(
        decision=MiniAiDecision.COLLECT_MORE,
        confidence="low",
        summary_ru="Challenger выглядит лучше, но разрыв ещё не прошёл пороги устойчивости.",
        next_action_ru=(
            "Продолжите тот же matched-тест без изменения других факторов. "
            "Не добавляйте новый сценарий, пока текущий вопрос не закрыт."
        ),
        control_arm_id=control.arm_id,
        arm_summaries=summaries,
        evidence=evidence,
        reason_codes=("gap_below_promotion_threshold", "one_question_continues"),
        next_dimension=plan.dimension,
    )
