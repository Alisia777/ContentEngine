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
    ContentFormat,
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

_GLOBAL_SAFE_CONTROL_ANGLE = "demonstration"
_DEFAULT_HYPOTHESIS_ANGLES: tuple[str, ...] = (
    "problem_first",
    "result_first",
    "product_focus",
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
    """Resolve a funnel action, preferring the source workbook's diagnosis.

    QEEP already contains a governed `Статус` and `Рекомендуемое действие`.
    Re-guessing the status from loosely detected columns produced the false
    result that there were no creative bottlenecks. The source diagnosis is
    authoritative when present; metrics are only a fallback.
    """

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
    minimum_observations: int = 3,
) -> tuple[CreativeCandidate, ...]:
    """Select winner candidates only inside one matched commercial cohort.

    The function refuses cross-category fallback, excludes multi-post WW
    bundles and only considers Reels with attributable orders. At most one
    candidate per creator survives so that a large account cannot flood the
    policy with near-duplicate successes.
    """

    category = _normalise_text(category_key)
    target_sku = str(sku or "").strip()
    target_platform = _normalise_text(platform)
    if not category or not target_sku or not target_platform:
        raise LearningPolicyError("winner_scope_invalid")
    if maximum_candidates < 1 or maximum_candidates > 10:
        raise LearningPolicyError("winner_limit_invalid")
    if minimum_observations < 3 or minimum_observations > 50:
        raise LearningPolicyError("winner_minimum_observations_invalid")

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
    if len(cohort) < minimum_observations:
        return ()

    # Keep one strongest observation per creator before final ranking.
    preliminary = _score_cohort(cohort)
    by_creator: dict[str, CreativeObservation] = {}
    for observation in cohort:
        creator = observation.creator_key or observation.observation_id
        current = by_creator.get(creator)
        if current is None or preliminary[observation.observation_id] > preliminary[current.observation_id]:
            bym���jם