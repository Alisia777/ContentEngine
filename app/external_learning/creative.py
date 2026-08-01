"""Creative attribution, winner selection and bounded priors."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from statistics import fmean
from typing import Iterable, Mapping

from ._common import (
    LearningPolicyError,
    business_components,
    normalise_text,
    score_cohort,
)
from .schema import (
    CreativeCandidate,
    CreativeObservation,
    LearningScope,
    ObservationState,
)


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
    """Select winner candidates inside one matched commercial cohort."""

    category = normalise_text(category_key)
    target_sku = str(sku or "").strip()
    target_platform = normalise_text(platform)
    if not category or not target_sku or not target_platform:
        raise LearningPolicyError("winner_scope_invalid")
    if maximum_candidates < 1 or maximum_candidates > 10:
        raise LearningPolicyError("winner_limit_invalid")
    if minimum_observations < 3 or minimum_observations > 50:
        raise LearningPolicyError("winner_minimum_observations_invalid")

    cohort = [
        observation
        for observation in observations
        if normalise_text(observation.category_key) == category
        and observation.sku == target_sku
        and normalise_text(observation.platform) == target_platform
        and (
            observation.activation_eligible
            if require_activation_approval
            else observation.structurally_eligible
        )
    ]
    if len(cohort) < minimum_observations:
        return ()

    preliminary = score_cohort(cohort)
    by_creator: dict[str, CreativeObservation] = {}
    for observation in cohort:
        creator = observation.creator_key or observation.observation_id
        current = by_creator.get(creator)
        if (
            current is None
            or preliminary[observation.observation_id]
            > preliminary[current.observation_id]
        ):
            by_creator[creator] = observation
    cohort = list(by_creator.values())
    if len(cohort) < minimum_observations:
        return ()

    scores = score_cohort(cohort)
    ranked = sorted(
        cohort,
        key=lambda item: (
            business_components(item)[0],
            scores[item.observation_id],
            business_components(item)[2],
            item.observation_id,
        ),
        reverse=True,
    )
    top_orders = business_components(ranked[0])[0]
    second_orders = business_components(ranked[1])[0]
    top_score = scores[ranked[0].observation_id]
    second_score = scores[ranked[1].observation_id]
    clear_order_lead = top_orders - second_orders >= max(
        0.5,
        second_orders * 0.10,
    )
    if top_score < 0.60 or (
        not clear_order_lead and top_score - second_score < 0.08
    ):
        return ()

    result: list[CreativeCandidate] = []
    for item in ranked[:maximum_candidates]:
        orders_per_day, conversion_proxy, _sales_per_day = business_components(item)
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
                    "minimum_three_independent_observations",
                    "observational_signal_not_causal_proof",
                ),
            )
        )
    return tuple(result)


def aggregate_feature_prior(
    observations: Iterable[CreativeObservation],
    *,
    category_key: str,
    feature_name: str,
    require_activation_approval: bool = True,
    minimum_support: int = 4,
) -> Mapping[str, tuple[float, int]]:
    """Compute shrunken category priors for one allowlisted enum feature."""

    if feature_name not in {
        "hook_type",
        "creative_angle",
        "cta_style",
        "proof_type",
    }:
        raise LearningPolicyError("feature_not_allowlisted")
    category = normalise_text(category_key)
    usable = [
        item
        for item in observations
        if normalise_text(item.category_key) == category
        and (
            item.activation_eligible
            if require_activation_approval
            else item.structurally_eligible
        )
    ]
    if len(usable) < minimum_support:
        return {}
    scores = score_cohort(usable)
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
    return dict(
        sorted(
            result.items(),
            key=lambda item: (item[1][0], item[1][1]),
            reverse=True,
        )
    )
