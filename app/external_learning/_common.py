"""Shared deterministic helpers for external performance learning."""

from __future__ import annotations

from math import log1p
from typing import Sequence

from .schema import CreativeObservation


GLOBAL_SAFE_CONTROL_ANGLE = "demonstration"
DEFAULT_HYPOTHESIS_ANGLES: tuple[str, ...] = (
    "problem_first",
    "result_first",
    "product_focus",
)


class LearningPolicyError(ValueError):
    """Raised when a policy would violate a learning boundary."""


def normalise_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def percentile_ranks(values: Sequence[float]) -> list[float]:
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


def business_components(
    observation: CreativeObservation,
) -> tuple[float, float, float]:
    orders = float(observation.orders or 0)
    days = max(1, observation.attribution_days)
    orders_per_day = orders / days
    conversion_proxy = orders / max(1.0, float(observation.carts or orders or 1))
    sales_per_day = float(observation.sales_minor or 0) / days
    return orders_per_day, conversion_proxy, sales_per_day


def score_cohort(
    observations: Sequence[CreativeObservation],
) -> dict[str, float]:
    """Score a matched cohort using business outcomes, never raw views."""

    if not observations:
        return {}
    components = [business_components(item) for item in observations]
    order_ranks = percentile_ranks([item[0] for item in components])
    conversion_ranks = percentile_ranks([item[1] for item in components])
    sales_ranks = percentile_ranks([item[2] for item in components])
    scores: dict[str, float] = {}
    for index, observation in enumerate(observations):
        scores[observation.observation_id] = (
            0.80 * order_ranks[index]
            + 0.12 * conversion_ranks[index]
            + 0.08 * sales_ranks[index]
        )
    return scores


def safe_log_business_value(observation: CreativeObservation) -> float:
    """A bounded audit helper; it is not a policy score."""

    orders = max(0, observation.orders or 0)
    sales = max(0, observation.sales_minor or 0)
    return log1p(orders) + 0.25 * log1p(sales / 100)
