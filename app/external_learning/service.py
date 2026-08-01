"""Deterministic performance-learning policies for ContentEngine.

The service intentionally does not fine-tune provider models. It produces a
bounded, auditable policy from mature business outcomes. Every decision can be
recomputed from structured observations and never consumes raw captions,
source prose or model-generated instructions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from math import log1p
from statistics import fmean
from typing import Iterable, Mapping, Sequence

from .schema import (
    CategoryExperimentPlan,
    CreativeCandidate,
    CreativeObservation,
    DurationArm,
    DurationPlan,
    ExperimentArm,
    FunnelDecision,
    FunnelObservation,
    LearningScope,
    MODEL_DURATION_OPTIONS,
    ObservationState,
    PolicyMode,
    ProviderModel,
)


_QEEP_STATUS_MAP: dict[str, FunnelDecision] = {
    "чинить карточку": FunnelDecision.CREATIVE,
    "риск oos": FunnelDecision.SUPPLY,
    "чинить выкуп": FunnelDecision.EXPECTATION,
    "оптимизировать рекламу": FunnelDecision.ADVERTISING,
    "суперзвезда": FunnelDecision.SCALE,
    "масштабировать": FunnelDecision.SCALE,
    "наблюдать": FunnelDecision.OBSERVE,
    "мало данных": FunnelDecision.MEASUREMENT,
}

_DEFAULT_ANGLES: tuple[str, ...] = (
    "demonstration",
    "problem_first",
    "result_first",
)


class LearningPolicyError(ValueError):
    """Raised when a policy would violate a learning boundary."""


def _normalise_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _percentile_ranks(values: Sequence[float]) -> list[float]:
    """Return stable average percentile ranks in [0, 1]."""

    if not values:
        return []
    indexed = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    result = [0.0] * len(values)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        average_rank = (start + end - 1) / 2
        percentile = 1.0 if len(values) == 1 else average_rank / (len(values) - 1)
        for position in range(start, end):
            result[indexed[position][0]] = percentile
        start = end
    return result


def _business_components(observation: CreativeObservation) -> tuple[float, float, float]:
    orders = float(observation.orders or 0)
    days = max(1, observation.attribution_days)
    orders_per_day = orders / days
    conversion_proxy = orders / max(1.0, float(observation.carts or orders or 1))
    sales_per_day = float(observation.sales_minor or 0) / days
    return orders_per_day, conversion_proxy, sales_per_day


def _score_cohort(observations: Sequence[CreativeObservation]) -> dict[str, float]:
    """Score a matched cohort using business outcomes, not raw views.

    Orders/day is the primary signal. Conversion and sales/day add context.
    Views are deliberately absent because a high-reach post is not necessarily
    a commercially successful creative.
    """

    if not observations:
        return {}
    components = [_business_components(item) for item in observations]
    order_ranks = _percentile_ranks([item[0] for item in components])
    conversion_ranks = _percentile_ranks([item[1] for item in components])
    sales_ranks = _percentile_ranks([item[2] for item in components])
    scores: dict[str, float] = {}
    for index, observation in enumerate(observations):
        scores[observation.observation_id] = (
            0.80 * order_ranks[index]
            + 0.12 * conversion_ranks[index]
            + 0.08 * sales_ranks[index]
        )
    return scores


def map_funnel_decision(observation: FunnelObservation) -> FunnelDecision:
    """Resolve a funnel action, preferring the source workbook's diagnosis."""

    source_status = _normalise_text(observation.source_status)
    if source_status in _QEEP_STATUS_MAP:
        return _QEEP_STATUS_MAP[source_status]

    source_action = _normalise_text(observation.source_action)
    if "перв" in source_action and ("экран" in source_action or "контент" in source_action):
        return FunnelDecision.CREATIVE
    if "остат" in source_action or "постав" in source_action:
        return FunnelDecision.SUPPLY
    if "выкуп" in source_action or "ожидани" in source_action:
        return FunnelDecision.EXPECTATION
    if "реклам" in source_action or "дрр" in source_action:
        return FunnelDecision.ADVERTISING
    if "масштаб" in source_action or "увеличить трафик" in source_action:
        return FunnelDecision.SCALE

    if observation.stock is not None and observation.stock <= 0:
        return FunnelDecision.SUPPLY
    if observation.orders is None or observation.orders < 30:
        return FunnelDecision.MEASUREMENT
    if (
        observation.conversion_visit_to_order is not None
        and observation.conversion_visit_to_order < 0.02
    ):
        return FunnelDecision.CREATIVE
    if observation.buyout_rate is not None and observation.buyout_rate < 0.65:
        return FunnelDecision.EXPECTATION
    if observation.drr is not None and observation.drr > 0.35:
        return FunnelDecision.ADVERTISING
    return FunnelDecision.OBSERVE


def mark_harly_attribution_state(
    observation: CreativeObservation,
    *,
    source_found_in_top100: bool,
) -> CreativeObservation:
    """Apply Harly/WW attribution semantics without inventing zeros."""

    if not source_found_in_top100:
        return replace(
            observation,
            state=ObservationState.CENSORED_MISSING,
            attribution_complete=False,
        )
    if observation.bundle_size > 1:
        return replace(observation, state=ObservationState.AMBIGUOUS_BUNDLE)
    if observation.orders is None:
        return replace(observation, state=ObservationState.IMMATURE)
    return replace(observation, state=ObservationState.ELIGIBLE)


def select_successful_creatives(
    observations: Iterable[CreativeObservation],
    *,
    category_key: str,
    sku: str,
    platform: str,
    require_activation_approval: bool = False,
    maximum_candidates: int = 3,
) -> tuple[CreativeCandidate, ...]:
    """Select winners only inside one matched category/SKU/platform cohort."""

    category = _normalise_text(category_key)
    target_sku = str(sku or "").strip()
    target_platform = _normalise_text(platform)
    if not category or not target_sku or not target_platform:
        raise LearningPolicyError("winner_scope_invalid")
    if maximum_candidates < 1 or maximum_candidates > 10:
        raise LearningPolicyError("winner_limit_invalid")

    cohort = [
        observation
        for observation in observations
        if _normalise_text(observation.category_key) == category
        and observation.sku == target_sku
        and _normalise_text(observation.platform) == target_platform
        and (
            observation.activation_eligible
            if require_activation_approval
            else observation.structurally_eligible
        )
    ]
    if len(cohort) < 2:
        return ()

    preliminary = _score_cohort(cohort)
    by_creator: dict[str, CreativeObservation] = {}
    for observation in cohort:
        creator = observation.creator_key or observation.observation_id
        current = by_creator.get(creator)
        if current is None or preliminary[observation.observation_id] > preliminary[current.observation_id]:
            by_creator[creator] = observation
    cohort = list(by_creator.values())
    if len(cohort) < 2:
        return ()

    scores = _score_cohort(cohort)
    ranked = sorted(
        cohort,
        key=lambda item: (
            _business_components(item)[0],
            scores[item.observation_id],
            _business_components(item)[2],
            item.observation_id,
        ),
        reverse=True,
    )
    top_orders = _business_components(ranked[0])[0]
    second_orders = _business_components(ranked[1])[0]
    top_score = scores[ranked[0].observation_id]
    second_score = scores[ranked[1].observation_id]
    clear_order_lead = top_orders - second_orders >= max(0.5, second_orders * 0.10)
    if top_score < 0.60 or (not clear_order_lead and top_score - second_score < 0.08):
        return ()

    result: list[CreativeCandidate] = []
    for item in ranked[:maximum_candidates]:
        orders_per_day, conversion_proxy, _sales_per_day = _business_components(item)
        result.append(
            CreativeCandidate(
                observation_id=item.observation_id,
                score=round(scores[item.observation_id], 6),
                orders_per_day=round(orders_per_day, 6),
                conversion_proxy=round(conversion_proxy, 6),
                scope=LearningScope.PRODUCT,
                reason_codes=(
                    "same_category",
                    "same_sku",
                    "same_platform",
                    "orders_per_day_primary",
                    "views_never_define_winner",
                    "single_publication_attribution",
                ),
            )
        )
    return tuple(result)


def _cold_start_durations(model: ProviderModel) -> tuple[int, ...]:
    if model is ProviderModel.GEN4_TURBO:
        return (5, 8)
    if model is ProviderModel.SEEDANCE2_FAST:
        return (8, 12)
    return (0,)


def _duration_scores(
    observations: Sequence[CreativeObservation],
) -> dict[int, tuple[float, int]]:
    by_duration: dict[int, list[CreativeObservation]] = defaultdict(list)
    for observation in observations:
        if observation.duration_seconds is not None:
            by_duration[observation.duration_seconds].append(observation)
    if len(by_duration) < 2:
        return {}

    all_scores = _score_cohort(observations)
    baseline = fmean(all_scores.values()) if all_scores else 0.5
    prior_strength = 4.0
    result: dict[int, tuple[float, int]] = {}
    for duration, group in by_duration.items():
        group_scores = [all_scores[item.observation_id] for item in group]
        support = len(group_scores)
        raw_mean = fmean(group_scores)
        shrunk = (support * raw_mean + prior_strength * baseline) / (support + prior_strength)
        result[duration] = (shrunk, support)
    return result


def choose_duration_plan(
    observations: Iterable[CreativeObservation],
    *,
    model: ProviderModel,
    category_key: str,
    sku: str,
    platform: str,
    require_activation_approval: bool = False,
) -> DurationPlan:
    """Choose duration without hard-coding eight seconds.

    Product evidence wins over category evidence. Foreign categories are never
    consulted. With no mature matched evidence, eight seconds is only one arm.
    """

    allowed = MODEL_DURATION_OPTIONS[model]
    if model is ProviderModel.SEEDREAM5_LITE:
        return DurationPlan(
            model=model,
            scope=LearningScope.NOT_APPLICABLE,
            mode=PolicyMode.NOT_APPLICABLE,
            arms=(DurationArm(0, 1.0),),
            allowed_durations=allowed,
            evidence_count=0,
            reason_codes=("photo_mode",),
        )

    category = _normalise_text(category_key)
    target_platform = _normalise_text(platform)
    target_sku = str(sku or "").strip()
    if not category or not target_platform or not target_sku:
        raise LearningPolicyError("duration_scope_invalid")

    usable = [
        item
        for item in observations
        if item.model is model
        and _normalise_text(item.category_key) == category
        and _normalise_text(item.platform) == target_platform
        and item.duration_seconds in allowed
        and (
            item.activation_eligible
            if require_activation_approval
            else item.structurally_eligible
        )
    ]
    exact = [item for item in usable if item.sku == target_sku]
    selected = exact if len({item.duration_seconds for item in exact}) >= 2 else usable
    scope = LearningScope.PRODUCT if selected is exact and exact else LearningScope.CATEGORY
    scores = _duration_scores(selected)

    eligible = [
        (duration, score, support)
        for duration, (score, support) in scores.items()
        if support >= 3
    ]
    eligible.sort(key=lambda item: (item[1], item[2], -item[0]), reverse=True)
    if len(eligible) >= 2:
        winner, second = eligible[0], eligible[1]
        if winner[1] >= 0.58 and winner[1] - second[1] >= 0.04:
            return DurationPlan(
                model=model,
                scope=scope,
                mode=PolicyMode.EXPLOIT,
                arms=(
                    DurationArm(
                        seconds=winner[0],
                        allocation=0.70,
                        evidence_count=winner[2],
                        score=round(winner[1], 6),
                    ),
                    DurationArm(
                        seconds=second[0],
                        allocation=0.30,
                        evidence_count=second[2],
                        score=round(second[1], 6),
                    ),
                ),
                allowed_durations=allowed,
                evidence_count=len(selected),
                reason_codes=(
                    "matched_duration_evidence",
                    "business_outcome_scoring",
                    "control_arm_retained",
                ),
            )

    cold = _cold_start_durations(model)
    allocation = 1.0 / len(cold)
    return DurationPlan(
        model=model,
        scope=LearningScope.NEW_CATEGORY if not usable else scope,
        mode=PolicyMode.EXPLORE,
        arms=tuple(DurationArm(seconds=value, allocation=allocation) for value in cold),
        allowed_durations=allowed,
        evidence_count=len(selected),
        reason_codes=(
            "duration_not_locked_to_eight_seconds",
            "insufficient_matched_duration_evidence",
            "cross_category_duration_forbidden",
        ),
    )


def _category_angles(
    observations: Sequence[CreativeObservation],
    category_key: str,
) -> tuple[str, ...]:
    category = _normalise_text(category_key)
    eligible = [
        item
        for item in observations
        if _normalise_text(item.category_key) == category
        and item.activation_eligible
        and item.creative_angle not in {"", "unknown"}
    ]
    if len(eligible) < 6:
        return _DEFAULT_ANGLES

    scores = _score_cohort(eligible)
    by_angle: dict[str, list[float]] = defaultdict(list)
    for item in eligible:
        by_angle[item.creative_angle].append(scores[item.observation_id])
    ranked = sorted(
        (
            (angle, fmean(values), len(values))
            for angle, values in by_angle.items()
            if len(values) >= 3
        ),
        key=lambda item: (item[1], item[2], item[0]),
        reverse=True,
    )
    if len(ranked) < 2:
        return _DEFAULT_ANGLES
    return tuple(item[0] for item in ranked[:3])


def build_category_experiment_plan(
    observations: Iterable[CreativeObservation],
    *,
    category_key: str,
    sku: str,
    platform: str,
    model: ProviderModel,
    require_activation_approval: bool = True,
) -> CategoryExperimentPlan:
    """Build a conservative plan for an existing or brand-new category."""

    source = tuple(observations)
    winners = select_successful_creatives(
        source,
        category_key=category_key,
        sku=sku,
        platform=platform,
        require_activation_approval=require_activation_approval,
        maximum_candidates=1,
    )
    duration = choose_duration_plan(
        source,
        model=model,
        category_key=category_key,
        sku=sku,
        platform=platform,
        require_activation_approval=require_activation_approval,
    )

    if model is ProviderModel.SEEDREAM5_LITE:
        return CategoryExperimentPlan(
            category_key=category_key,
            model=model,
            mode=PolicyMode.EXPLORE,
            arms=(
                ExperimentArm(
                    name="Контрольное товарное фото",
                    creative_angle="product_focus",
                    duration_seconds=0,
                    allocation=1.0,
                    source_scope=LearningScope.GLOBAL_SAFE,
                    is_control=True,
                ),
            ),
            reason_codes=("photo_mode", "no_video_duration"),
        )

    durations = [arm.seconds for arm in duration.arms]
    if winners:
        winner = winners[0]
        primary_duration = durations[0]
        control_duration = durations[1] if len(durations) > 1 else durations[0]
        winner_observation = next(
            item for item in source if item.observation_id == winner.observation_id
        )
        return CategoryExperimentPlan(
            category_key=category_key,
            model=model,
            mode=PolicyMode.EXPLOIT,
            arms=(
                ExperimentArm(
                    name="Проверенный паттерн",
                    creative_angle=winner_observation.creative_angle,
                    duration_seconds=primary_duration,
                    allocation=0.60,
                    source_scope=LearningScope.PRODUCT,
                ),
                ExperimentArm(
                    name="Контроль без обучения",
                    creative_angle="demonstration",
                    duration_seconds=control_duration,
                    allocation=0.20,
                    source_scope=LearningScope.GLOBAL_SAFE,
                    is_control=True,
                ),
                ExperimentArm(
                    name="Ограниченное исследование",
                    creative_angle="problem_first",
                    duration_seconds=control_duration,
                    allocation=0.20,
                    source_scope=LearningScope.CATEGORY,
                ),
            ),
            reason_codes=(
                "same_product_winner",
                "control_required",
                "bounded_exploration",
            ),
            selected_winner_id=winner.observation_id,
        )

    angles = _category_angles(source, category_key)
    first_duration = durations[0]
    second_duration = durations[1] if len(durations) > 1 else first_duration
    return CategoryExperimentPlan(
        category_key=category_key,
        model=model,
        mode=PolicyMode.EXPLORE,
        arms=(
            ExperimentArm(
                name="Контроль",
                creative_angle="demonstration",
                duration_seconds=first_duration,
                allocation=0.34,
                source_scope=LearningScope.GLOBAL_SAFE,
                is_control=True,
            ),
            ExperimentArm(
                name="Гипотеза категории A",
                creative_angle=angles[0],
                duration_seconds=second_duration,
                allocation=0.33,
                source_scope=LearningScope.NEW_CATEGORY,
            ),
            ExperimentArm(
                name="Гипотеза категории B",
                creative_angle=angles[1],
                duration_seconds=first_duration,
                allocation=0.33,
                source_scope=LearningScope.NEW_CATEGORY,
            ),
        ),
        reason_codes=(
            "new_or_sparse_category",
            "no_foreign_category_winner",
            "three_arm_cold_start",
        ),
    )


def aggregate_feature_prior(
    observations: Iterable[CreativeObservation],
    *,
    category_key: str,
    feature_name: str,
    require_activation_approval: bool = True,
    minimum_support: int = 4,
) -> Mapping[str, tuple[float, int]]:
    """Compute shrunken category priors for one allowlisted enum feature."""

    if feature_name not in {"hook_type", "creative_angle", "cta_style", "proof_type"}:
        raise LearningPolicyError("feature_not_allowlisted")
    category = _normalise_text(category_key)
    usable = [
        item
        for item in observations
        if _normalise_text(item.category_key) == category
        and (
            item.activation_eligible
            if require_activation_approval
            else item.structurally_eligible
        )
    ]
    if len(usable) < minimum_support:
        return {}
    scores = _score_cohort(usable)
    baseline = fmean(scores.values()) if scores else 0.5
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in usable:
        value = str(getattr(item, feature_name) or "unknown")
        if value != "unknown":
            grouped[value].append(scores[item.observation_id])
    prior_strength = 5.0
    result: dict[str, tuple[float, int]] = {}
    for value, values in grouped.items():
        support = len(values)
        if support < minimum_support:
            continue
        raw_mean = fmean(values)
        shrunk = (support * raw_mean + prior_strength * baseline) / (
            support + prior_strength
        )
        result[value] = (round(shrunk, 6), support)
    return dict(sorted(result.items(), key=lambda item: (item[1][0], item[1][1]), reverse=True))


def safe_log_business_value(observation: CreativeObservation) -> float:
    """A bounded audit helper; it is not a policy score."""

    orders = max(0, observation.orders or 0)
    sales = max(0, observation.sales_minor or 0)
    return log1p(orders) + 0.25 * log1p(sales / 100)
