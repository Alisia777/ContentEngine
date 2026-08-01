"""Public fail-closed wrapper around the internal mass planner."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from app.external_learning import CreativeObservation, ProviderModel

from .planner import build_mass_generation_plan as _build_mass_generation_plan
from .schema import MassGenerationPlan, MiniAiContext, MiniAiRules, PlanMode


_VIDEO_PRICE_MINOR_PER_SECOND = {
    ProviderModel.GEN4_TURBO: 5,
    ProviderModel.SEEDANCE2_FAST: 29,
}


def _exact_plan_cost(plan: MassGenerationPlan) -> int:
    """Price every arm instead of assuming the current form duration."""

    price = _VIDEO_PRICE_MINOR_PER_SECOND.get(plan.context.model)
    if price is None:
        return plan.estimated_cost_minor
    return sum(
        arm.planned_count * arm.duration_seconds * price
        for arm in plan.arms
    )


def build_mass_generation_plan(
    context: MiniAiContext,
    observations: Iterable[CreativeObservation] = (),
    *,
    rules: MiniAiRules | None = None,
) -> MassGenerationPlan:
    """Build a fail-closed plan with isolated categories and exact arm pricing."""

    safe_context = context
    if context.category_is_new:
        safe_context = replace(
            context,
            approved_winner_angle=None,
            approved_winner_duration=None,
        )
    plan = _build_mass_generation_plan(safe_context, observations, rules=rules)
    if not plan.executable:
        return plan

    exact_cost = _exact_plan_cost(plan)
    if safe_context.max_budget_minor and exact_cost > safe_context.max_budget_minor:
        return MassGenerationPlan(
            plan_id=f"blocked-budget-{plan.plan_id[-64:]}",
            rules_version=plan.rules_version,
            mode=PlanMode.BLOCKED,
            context=plan.context,
            dimension=plan.dimension,
            arms=(),
            batch_size=0,
            estimated_cost_minor=0,
            blockers=(
                "Стоимость пакета с учётом длительности каждого варианта выше заданного лимита.",
            ),
            warnings=(),
            reason_codes=(
                *plan.reason_codes,
                "batch_budget_exceeded_exact_arm_cost",
            ),
        )
    return replace(plan, estimated_cost_minor=exact_cost)
