from app.external_learning import FunnelDecision, ProviderModel
from app.mini_ai import (
    ExperimentDimension,
    LearningObjective,
    MiniAiContext,
    RiskPreset,
    build_mass_generation_plan,
)


def duration_context(max_budget_minor: int) -> MiniAiContext:
    return MiniAiContext(
        organization_key="contentengine-test",
        learning_category_key="car_audio_amplifier",
        sku="THUNDER-1200",
        platform="wildberries",
        model=ProviderModel.GEN4_TURBO,
        objective=LearningObjective.ORDERS,
        risk_preset=RiskPreset.BALANCED,
        requested_dimension=ExperimentDimension.DURATION,
        requested_batch_size=6,
        # The current native form may still be set to five seconds: $0.25.
        unit_cost_minor=25,
        max_budget_minor=max_budget_minor,
        funnel_decision=FunnelDecision.CREATIVE,
        category_is_new=False,
        approved_winner_angle="demonstration",
    )


def test_duration_plan_prices_each_arm_instead_of_current_form_duration() -> None:
    plan = build_mass_generation_plan(duration_context(max_budget_minor=1_000))
    assert plan.executable is True
    assert {arm.duration_seconds for arm in plan.arms} == {5, 8}
    assert {arm.planned_count for arm in plan.arms} == {3}
    assert plan.estimated_cost_minor == 3 * 5 * 5 + 3 * 8 * 5
    assert plan.estimated_cost_minor == 195


def test_exact_arm_price_can_block_a_plan_that_naive_pricing_would_allow() -> None:
    plan = build_mass_generation_plan(duration_context(max_budget_minor=170))
    assert plan.executable is False
    assert plan.estimated_cost_minor == 0
    assert "длительности каждого варианта" in plan.blockers[0]
    assert "batch_budget_exceeded_exact_arm_cost" in plan.reason_codes
