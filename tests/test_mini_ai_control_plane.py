from __future__ import annotations

from dataclasses import replace

import pytest

from app.external_learning import FunnelDecision, ProviderModel
from app.mini_ai import (
    ArmOutcome,
    ExperimentDimension,
    LearningObjective,
    MiniAiContext,
    MiniAiController,
    MiniAiDecision,
    OutcomeState,
    QaState,
    RiskPreset,
    build_mass_generation_plan,
    evaluate_mass_generation,
    rulebook_ru,
)


def context(**changes) -> MiniAiContext:
    base = MiniAiContext(
        organization_key="contentengine-test",
        learning_category_key="car_audio_amplifier",
        sku="THUNDER-1200",
        platform="wildberries",
        model=ProviderModel.GEN4_TURBO,
        objective=LearningObjective.ORDERS,
        risk_preset=RiskPreset.BALANCED,
        requested_dimension=ExperimentDimension.AUTO,
        requested_batch_size=6,
        unit_cost_minor=40,
        max_budget_minor=10_000,
        funnel_decision=FunnelDecision.CREATIVE,
        category_is_new=True,
    )
    return replace(base, **changes)


def mature_outcome(
    arm_id: str,
    ordinal: int,
    *,
    orders: int,
    carts: int = 10,
    sales_minor: int = 10_000,
    spend_minor: int = 2_000,
    views: int = 100,
    product_ok: bool = True,
    blocker: bool = False,
) -> ArmOutcome:
    return ArmOutcome(
        outcome_id=f"outcome-{arm_id}-{ordinal}",
        arm_id=arm_id,
        job_id=f"job-{arm_id}-{ordinal}",
        state=OutcomeState.SUCCEEDED,
        qa_state=QaState.APPROVED,
        product_fidelity_ok=product_ok,
        critical_blocker=blocker,
        published=True,
        metrics_mature=True,
        orders=orders,
        carts=max(carts, orders),
        sales_minor=sales_minor,
        spend_minor=spend_minor,
        attribution_days=1,
        views=views,
        creator_key=f"creator-{ordinal}",
    )


def test_rulebook_is_explicit_and_human_readable() -> None:
    text = rulebook_ru()
    assert "Один цикл — один вопрос" in text
    assert "Восемь секунд — не закон" in text
    assert "Просмотры не выбирают победителя" in text
    assert "автоматического масштабирования" in text


def test_new_category_gets_three_distinct_arms_and_ignores_foreign_winner() -> None:
    plan = build_mass_generation_plan(
        context(approved_winner_angle="trust_builder", category_is_new=True)
    )
    assert plan.executable is True
    assert plan.dimension is ExperimentDimension.CREATIVE_ANGLE
    assert len(plan.arms) == 3
    assert sum(arm.is_control for arm in plan.arms) == 1
    assert {arm.creative_angle for arm in plan.arms} == {
        "demonstration",
        "problem_first",
        "result_first",
    }
    assert {arm.duration_seconds for arm in plan.arms} == {5}
    assert {arm.proof_type for arm in plan.arms} == {"product_detail"}
    assert {arm.cta_style for arm in plan.arms} == {"soft_action"}
    assert [arm.planned_count for arm in plan.arms] == [2, 2, 2]


def test_duration_is_an_experiment_and_eight_seconds_is_not_locked() -> None:
    gen4 = build_mass_generation_plan(
        context(
            category_is_new=False,
            approved_winner_angle="demonstration",
            requested_dimension=ExperimentDimension.DURATION,
            requested_batch_size=6,
        )
    )
    assert gen4.dimension is ExperimentDimension.DURATION
    assert {arm.duration_seconds for arm in gen4.arms} == {5, 8}
    assert {arm.creative_angle for arm in gen4.arms} == {"demonstration"}

    seedance = build_mass_generation_plan(
        context(
            model=ProviderModel.SEEDANCE2_FAST,
            unit_cost_minor=232,
            category_is_new=False,
            approved_winner_angle="demonstration",
            requested_dimension=ExperimentDimension.DURATION,
            requested_batch_size=6,
        )
    )
    assert {arm.duration_seconds for arm in seedance.arms} == {8, 12}


def test_one_cycle_never_changes_multiple_main_dimensions() -> None:
    creative = build_mass_generation_plan(context())
    assert len({arm.duration_seconds for arm in creative.arms}) == 1
    assert len({arm.proof_type for arm in creative.arms}) == 1
    assert len({arm.cta_style for arm in creative.arms}) == 1

    duration = build_mass_generation_plan(
        context(
            category_is_new=False,
            approved_winner_angle="problem_first",
            requested_dimension=ExperimentDimension.DURATION,
        )
    )
    assert len({arm.creative_angle for arm in duration.arms}) == 1
    assert len({arm.proof_type for arm in duration.arms}) == 1
    assert len({arm.cta_style for arm in duration.arms}) == 1


def test_plan_is_deterministic_for_same_context() -> None:
    first = build_mass_generation_plan(context())
    second = build_mass_generation_plan(context())
    assert first.plan_id == second.plan_id
    assert first.arms == second.arms


def test_wrong_funnel_lever_blocks_mass_generation() -> None:
    plan = build_mass_generation_plan(context(funnel_decision=FunnelDecision.SUPPLY))
    assert plan.executable is False
    assert "наличие" in plan.blockers[0]


def test_batch_budget_and_minimum_sample_are_enforced() -> None:
    too_small = build_mass_generation_plan(context(requested_batch_size=4))
    assert too_small.executable is False
    assert "минимум 6" in too_small.blockers[0]

    too_expensive = build_mass_generation_plan(
        context(requested_batch_size=6, unit_cost_minor=400, max_budget_minor=1_000)
    )
    assert too_expensive.executable is False
    assert "выше заданного лимита" in too_expensive.blockers[0]


def test_no_outcomes_produces_no_fake_conclusion() -> None:
    plan = build_mass_generation_plan(context())
    conclusion = evaluate_mass_generation(plan, [])
    assert conclusion.decision is MiniAiDecision.COLLECT_MORE
    assert conclusion.winner_arm_id is None
    assert "результатов ещё нет" in conclusion.summary_ru


def test_succeeded_but_unpublished_result_waits_for_mature_metrics() -> None:
    plan = build_mass_generation_plan(context())
    arm = plan.arms[0]
    outcome = ArmOutcome(
        outcome_id="one",
        arm_id=arm.arm_id,
        job_id="job-one",
        state=OutcomeState.SUCCEEDED,
        qa_state=QaState.APPROVED,
        published=False,
        metrics_mature=False,
        orders=3,
        carts=10,
    )
    conclusion = evaluate_mass_generation(plan, [outcome])
    assert conclusion.decision is MiniAiDecision.WAIT_METRICS
    assert "просмотрам" in conclusion.next_action_ru.lower()


def test_first_product_mismatch_stops_the_whole_batch() -> None:
    plan = build_mass_generation_plan(context())
    outcomes = [
        mature_outcome(plan.arms[0].arm_id, 1, orders=1, product_ok=False),
    ]
    conclusion = evaluate_mass_generation(plan, outcomes)
    assert conclusion.decision is MiniAiDecision.PAUSE_QUALITY
    assert "подменил" in conclusion.summary_ru


def test_critical_blocker_stops_before_more_spend() -> None:
    plan = build_mass_generation_plan(context())
    outcomes = [mature_outcome(plan.arms[1].arm_id, 1, orders=2, blocker=True)]
    conclusion = evaluate_mass_generation(plan, outcomes)
    assert conclusion.decision is MiniAiDecision.PAUSE_QUALITY
    assert "критического" in conclusion.summary_ru


def test_high_views_with_zero_orders_cannot_beat_control() -> None:
    plan = build_mass_generation_plan(
        context(requested_batch_size=9, category_is_new=True)
    )
    control = next(arm for arm in plan.arms if arm.is_control)
    challengers = [arm for arm in plan.arms if not arm.is_control]
    outcomes: list[ArmOutcome] = []
    for index in range(3):
        outcomes.append(
            mature_outcome(
                control.arm_id,
                index,
                orders=2,
                carts=10,
                views=100,
            )
        )
        outcomes.append(
            mature_outcome(
                challengers[0].arm_id,
                index,
                orders=0,
                carts=10,
                views=1_000_000,
            )
        )
        outcomes.append(
            mature_outcome(
                challengers[1].arm_id,
                index,
                orders=1,
                carts=10,
                views=100_000,
            )
        )
    conclusion = evaluate_mass_generation(plan, outcomes)
    assert conclusion.decision is MiniAiDecision.KEEP_CONTROL
    assert conclusion.winner_arm_id == control.arm_id
    assert any("Просмотры" in item for item in conclusion.evidence)


def test_clear_business_winner_is_promoted_but_control_remains() -> None:
    plan = build_mass_generation_plan(
        context(requested_batch_size=9, category_is_new=True)
    )
    control = next(arm for arm in plan.arms if arm.is_control)
    winner, weak = [arm for arm in plan.arms if not arm.is_control]
    outcomes: list[ArmOutcome] = []
    for index in range(3):
        outcomes.extend(
            (
                mature_outcome(control.arm_id, index, orders=1, carts=10, sales_minor=10_000),
                mature_outcome(winner.arm_id, index, orders=4, carts=10, sales_minor=40_000),
                mature_outcome(weak.arm_id, index, orders=0, carts=10, sales_minor=1_000),
            )
        )
    conclusion = evaluate_mass_generation(plan, outcomes)
    assert conclusion.decision is MiniAiDecision.PROMOTE_WITH_CONTROL
    assert conclusion.winner_arm_id == winner.arm_id
    assert conclusion.recommended_allocations[winner.arm_id] == pytest.approx(0.70)
    assert conclusion.recommended_allocations[control.arm_id] == pytest.approx(0.30)
    assert conclusion.next_dimension is ExperimentDimension.DURATION
    assert "причинность" in conclusion.summary_ru


def test_two_results_per_arm_are_not_enough_to_declare_winner() -> None:
    plan = build_mass_generation_plan(context())
    outcomes: list[ArmOutcome] = []
    for arm in plan.arms:
        for index in range(2):
            outcomes.append(mature_outcome(arm.arm_id, index, orders=10 if not arm.is_control else 1))
    conclusion = evaluate_mass_generation(plan, outcomes)
    assert conclusion.decision is MiniAiDecision.COLLECT_MORE
    assert conclusion.winner_arm_id is None


def test_duplicate_generation_job_is_rejected() -> None:
    plan = build_mass_generation_plan(context())
    first = mature_outcome(plan.arms[0].arm_id, 1, orders=1)
    second = replace(
        mature_outcome(plan.arms[1].arm_id, 1, orders=2),
        job_id=first.job_id,
    )
    with pytest.raises(ValueError, match="duplicate_generation_job"):
        evaluate_mass_generation(plan, [first, second])


def test_controller_advances_only_after_a_supported_conclusion() -> None:
    controller = MiniAiController()
    plan = controller.plan(context(requested_batch_size=9))
    control = next(arm for arm in plan.arms if arm.is_control)
    winner, weak = [arm for arm in plan.arms if not arm.is_control]
    outcomes: list[ArmOutcome] = []
    for index in range(3):
        outcomes.extend(
            (
                mature_outcome(control.arm_id, index, orders=1),
                mature_outcome(winner.arm_id, index, orders=4),
                mature_outcome(weak.arm_id, index, orders=0),
            )
        )
    conclusion = controller.conclude(plan, outcomes)
    next_context = controller.next_context(plan, conclusion)
    assert next_context.requested_dimension is ExperimentDimension.DURATION
    assert next_context.approved_winner_angle == winner.creative_angle

    blocked = controller.plan(context(funnel_decision=FunnelDecision.SUPPLY))
    blocked_conclusion = controller.conclude(blocked, [])
    with pytest.raises(ValueError, match="conclusion_not_ready_for_next_cycle"):
        controller.next_context(blocked, blocked_conclusion)
