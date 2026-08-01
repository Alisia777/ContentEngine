from __future__ import annotations

from dataclasses import replace
from datetime import date

from app.external_learning import (
    ContentFormat,
    CreativeObservation,
    FunnelDecision,
    FunnelObservation,
    LearningScope,
    ObservationState,
    PolicyMode,
    ProviderModel,
    build_category_experiment_plan,
    choose_duration_plan,
    map_funnel_decision,
    mark_harly_attribution_state,
    select_successful_creatives,
)


def creative(
    observation_id: str,
    *,
    category: str = "pet_care",
    sku: str = "PET-1",
    platform: str = "instagram",
    model: ProviderModel = ProviderModel.SEEDANCE2_FAST,
    duration: int | None = 8,
    orders: int = 5,
    carts: int = 20,
    sales_minor: int = 10_000,
    days: int = 3,
    creator: str = "creator-a",
    content_format: ContentFormat = ContentFormat.REEL,
    bundle_size: int = 1,
    complete: bool = True,
    state: ObservationState = ObservationState.ELIGIBLE,
    qa: bool = True,
    rights: bool = True,
    angle: str = "demonstration",
) -> CreativeObservation:
    return CreativeObservation(
        observation_id=observation_id,
        category_key=category,
        sku=sku,
        platform=platform,
        model=model,
        content_format=content_format,
        published_on=date(2026, 7, 25),
        creator_key=creator,
        ww_code=f"WW-{observation_id}",
        bundle_size=bundle_size,
        attribution_days=days,
        attribution_complete=complete,
        duration_seconds=duration,
        carts=carts,
        orders=orders,
        sales_minor=sales_minor,
        creative_angle=angle,
        hook_type="problem_first",
        cta_style="soft_action",
        proof_type="visual_demo",
        state=state,
        qa_approved=qa,
        rights_confirmed=rights,
    )


def test_seedance_duration_is_not_locked_to_eight_seconds_on_cold_start() -> None:
    plan = choose_duration_plan(
        [],
        model=ProviderModel.SEEDANCE2_FAST,
        category_key="new_pet_category",
        sku="NEW-1",
        platform="instagram",
    )

    assert plan.mode is PolicyMode.EXPLORE
    assert plan.scope is LearningScope.NEW_CATEGORY
    assert [arm.seconds for arm in plan.arms] == [8, 12]
    assert [arm.allocation for arm in plan.arms] == [0.5, 0.5]
    assert plan.allowed_durations == (4, 8, 12, 15)
    assert "duration_not_locked_to_eight_seconds" in plan.reason_codes


def test_gen4_cold_start_tests_short_and_medium_instead_of_forcing_eight() -> None:
    plan = choose_duration_plan(
        [],
        model=ProviderModel.GEN4_TURBO,
        category_key="new_category",
        sku="NEW-2",
        platform="vk",
    )

    assert [arm.seconds for arm in plan.arms] == [5, 8]
    assert plan.allowed_durations == (2, 5, 8, 10)


def test_duration_learning_requires_two_mature_duration_arms() -> None:
    observations = [
        creative(f"eight-{index}", duration=8, orders=10 + index, creator=f"c{index}")
        for index in range(5)
    ]
    plan = choose_duration_plan(
        observations,
        model=ProviderModel.SEEDANCE2_FAST,
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
        require_activation_approval=True,
    )

    assert plan.mode is PolicyMode.EXPLORE
    assert [arm.seconds for arm in plan.arms] == [8, 12]
    assert "insufficient_matched_duration_evidence" in plan.reason_codes


def test_duration_can_learn_twelve_seconds_when_business_outcomes_are_better() -> None:
    observations = []
    for index in range(4):
        observations.append(
            creative(
                f"eight-{index}",
                duration=8,
                orders=2 + index,
                carts=25,
                sales_minor=5_000 + index * 100,
                creator=f"eight-c{index}",
            )
        )
        observations.append(
            creative(
                f"twelve-{index}",
                duration=12,
                orders=20 + index,
                carts=30,
                sales_minor=40_000 + index * 1_000,
                creator=f"twelve-c{index}",
            )
        )

    plan = choose_duration_plan(
        observations,
        model=ProviderModel.SEEDANCE2_FAST,
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
        require_activation_approval=True,
    )

    assert plan.mode is PolicyMode.EXPLOIT
    assert plan.scope is LearningScope.PRODUCT
    assert plan.arms[0].seconds == 12
    assert plan.arms[0].allocation == 0.70
    assert plan.arms[1].seconds == 8
    assert plan.arms[1].allocation == 0.30


def test_new_category_does_not_copy_a_winner_from_another_category() -> None:
    foreign = [
        creative(
            "foreign-winner",
            category="pet_care",
            sku="PET-1",
            orders=100,
            sales_minor=500_000,
            creator="foreign-creator",
            angle="problem_first",
        ),
        creative(
            "foreign-control",
            category="pet_care",
            sku="PET-1",
            orders=1,
            sales_minor=500,
            creator="foreign-control",
            angle="demonstration",
        ),
    ]

    plan = build_category_experiment_plan(
        foreign,
        category_key="home_appliances",
        sku="AIRFRYER-1",
        platform="instagram",
        model=ProviderModel.SEEDANCE2_FAST,
        require_activation_approval=True,
    )

    assert plan.mode is PolicyMode.EXPLORE
    assert plan.selected_winner_id is None
    assert "no_foreign_category_winner" in plan.reason_codes
    assert len(plan.arms) == 3
    assert any(arm.is_control for arm in plan.arms)
    assert all(
        arm.source_scope in {LearningScope.GLOBAL_SAFE, LearningScope.NEW_CATEGORY}
        for arm in plan.arms
    )


def test_successful_creative_is_selected_by_orders_not_views() -> None:
    high_views_no_orders = creative(
        "views-only",
        orders=0,
        carts=100,
        sales_minor=0,
        creator="creator-views",
    )
    high_views_no_orders = replace(high_views_no_orders, views=1_000_000)
    seller = creative(
        "seller",
        orders=30,
        carts=40,
        sales_minor=100_000,
        creator="creator-seller",
    )
    control = creative(
        "control",
        orders=2,
        carts=20,
        sales_minor=3_000,
        creator="creator-control",
    )

    candidates = select_successful_creatives(
        [high_views_no_orders, seller, control],
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
    )

    assert candidates
    assert candidates[0].observation_id == "seller"


def test_orders_per_day_remains_primary_over_conversion_proxy() -> None:
    high_orders = creative(
        "high-orders",
        orders=35,
        carts=100,
        sales_minor=90_000,
        creator="orders-creator",
    )
    conversion_darling = creative(
        "conversion-darling",
        orders=8,
        carts=8,
        sales_minor=40_000,
        creator="conversion-creator",
    )
    control = creative(
        "control-orders",
        orders=2,
        carts=20,
        sales_minor=4_000,
        creator="control-creator",
    )

    candidates = select_successful_creatives(
        [conversion_darling, high_orders, control],
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
    )

    assert candidates
    assert candidates[0].observation_id == "high-orders"
    assert "orders_per_day_primary" in candidates[0].reason_codes


def test_harly_same_day_ww_bundle_is_not_taught_as_three_winners() -> None:
    bundled = creative(
        "bundle-a",
        bundle_size=3,
        orders=40,
        creator="creator-a",
    )
    bundled = mark_harly_attribution_state(bundled, source_found_in_top100=True)
    control = creative(
        "control",
        orders=2,
        creator="creator-b",
    )

    assert bundled.state is ObservationState.AMBIGUOUS_BUNDLE
    assert not bundled.structurally_eligible
    assert not select_successful_creatives(
        [bundled, control],
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
    )


def test_harly_top100_miss_is_censored_not_a_zero_result() -> None:
    missing = creative("not-in-top100", orders=0)
    missing = mark_harly_attribution_state(
        missing,
        source_found_in_top100=False,
    )

    assert missing.state is ObservationState.CENSORED_MISSING
    assert not missing.attribution_complete
    assert not missing.structurally_eligible


def test_static_post_is_not_used_to_train_video_policy() -> None:
    post = creative(
        "post",
        content_format=ContentFormat.POST,
        orders=100,
        creator="post-creator",
    )
    reel = creative("reel", orders=10, creator="reel-creator")

    assert not post.structurally_eligible
    assert not select_successful_creatives(
        [post, reel],
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
    )


def test_creator_dominance_is_capped_before_winner_selection() -> None:
    observations = [
        creative("same-a", orders=50, creator="same"),
        creative("same-b", orders=45, creator="same"),
        creative("same-c", orders=40, creator="same"),
        creative("control", orders=2, creator="other"),
    ]

    candidates = select_successful_creatives(
        observations,
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
    )

    assert len(candidates) <= 2
    assert sum(item.observation_id.startswith("same-") for item in candidates) <= 1


def test_qeep_source_status_is_authoritative() -> None:
    observation = FunnelObservation(
        category_key="supplements",
        sku="QEEP-1",
        platform="wb",
        source_status="Чинить карточку",
        source_action="Переработать первый экран, оффер и контент",
        visits=300_000,
        orders=12_000,
        conversion_visit_to_order=0.04,
        stock=5_000,
    )

    assert map_funnel_decision(observation) is FunnelDecision.CREATIVE


def test_qeep_oos_is_not_misdiagnosed_as_a_creative_problem() -> None:
    observation = FunnelObservation(
        category_key="supplements",
        sku="QEEP-2",
        platform="wb",
        source_status="Риск OOS",
        source_action="Пополнить остаток; не наращивать рекламу до поставки",
        visits=500_000,
        orders=20_000,
        conversion_visit_to_order=0.08,
        stock=0,
    )

    assert map_funnel_decision(observation) is FunnelDecision.SUPPLY


def test_activation_requires_rights_and_human_qa() -> None:
    observations = [
        creative("candidate", orders=50, qa=False, rights=False, creator="a"),
        creative("control", orders=2, qa=True, rights=True, creator="b"),
    ]

    assert not select_successful_creatives(
        observations,
        category_key="pet_care",
        sku="PET-1",
        platform="instagram",
        require_activation_approval=True,
    )
