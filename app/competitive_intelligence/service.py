"""Deterministic discovery ranking and rights-aware action routing."""

from __future__ import annotations

from collections.abc import Iterable
import math

from .schema import (
    CompetitorActionPlan,
    CreativeAction,
    DiscoveryCandidate,
    PublicCreativeObservation,
    SocialPlatform,
    SourceRelationship,
)


class CompetitiveIntelligenceError(ValueError):
    """A fail-closed public-content discovery error."""


def _percentile_ranks(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [1.0]
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    for position, index in enumerate(order):
        ranks[index] = position / (len(values) - 1)
    return ranks


def _action_for(observation: PublicCreativeObservation) -> tuple[CreativeAction, tuple[str, ...]]:
    if observation.can_be_localized_exactly:
        return CreativeAction.LOCALIZE_OWNED, (
            "owned_or_licensed_source",
            "exact_localization_rights_confirmed",
        )
    if observation.source_relationship is SourceRelationship.PUBLIC_COMPETITOR:
        if observation.structural_profile.is_informative:
            return CreativeAction.RECREATE_STRUCTURE, (
                "public_competitor_discovery_only",
                "structure_may_be_adapted_not_copied",
            )
        return CreativeAction.DO_NOT_USE, (
            "public_competitor_without_structural_profile",
        )
    return CreativeAction.DO_NOT_USE, ("rights_not_confirmed",)


def rank_public_creatives(
    observations: Iterable[PublicCreativeObservation],
    *,
    category_key: str,
    platform: SocialPlatform,
    limit: int = 10,
) -> tuple[DiscoveryCandidate, ...]:
    """Rank public videos for human review, never as a business winner.

    Views and engagement are normalized only inside the supplied cohort. They
    are discovery signals and cannot activate ContentEngine's performance
    learning policy without independent business outcomes, QA and rights.
    """

    if not category_key or len(category_key) > 80:
        raise CompetitiveIntelligenceError("category_key_invalid")
    if not 1 <= limit <= 100:
        raise CompetitiveIntelligenceError("limit_invalid")

    deduplicated: dict[tuple[SocialPlatform, str], PublicCreativeObservation] = {}
    for observation in observations:
        if observation.category_key != category_key or observation.platform is not platform:
            continue
        key = (observation.platform, observation.external_content_id)
        current = deduplicated.get(key)
        if current is None or observation.fetched_at > current.fetched_at:
            deduplicated[key] = observation

    eligible = [item for item in deduplicated.values() if item.discovery_eligible]
    if not eligible:
        return ()

    velocities: list[float] = []
    engagements: list[float] = []
    share_rates: list[float] = []
    for item in eligible:
        views = max(0, int(item.views or 0))
        velocities.append(math.log1p(views / max(6.0, item.age_hours)))
        if views:
            engagement = (
                max(0, int(item.likes or 0))
                + 2 * max(0, int(item.comments or 0))
                + 3 * max(0, int(item.shares or 0))
            ) / views
            share_rate = max(0, int(item.shares or 0)) / views
        else:
            engagement = 0.0
            share_rate = 0.0
        engagements.append(engagement)
        share_rates.append(share_rate)

    velocity_rank = _percentile_ranks(velocities)
    engagement_rank = _percentile_ranks(engagements)
    share_rank = _percentile_ranks(share_rates)

    candidates: list[DiscoveryCandidate] = []
    for index, item in enumerate(eligible):
        action, action_reasons = _action_for(item)
        score = (
            0.55 * velocity_rank[index]
            + 0.30 * engagement_rank[index]
            + 0.15 * share_rank[index]
        )
        candidates.append(
            DiscoveryCandidate(
                observation_id=item.observation_id,
                account_key=item.account_key,
                action=action,
                discovery_score=round(score, 6),
                view_velocity=round(math.expm1(velocities[index]), 6),
                engagement_rate=round(engagements[index], 8),
                share_rate=round(share_rates[index], 8),
                structural_profile=item.structural_profile,
                reason_codes=(
                    "discovery_signals_only",
                    "views_are_not_business_outcomes",
                    *action_reasons,
                ),
            )
        )

    candidates.sort(
        key=lambda item: (
            item.action is CreativeAction.DO_NOT_USE,
            -item.discovery_score,
            item.observation_id,
        )
    )
    return tuple(candidates[:limit])


def build_competitor_action_plan(
    observations: Iterable[PublicCreativeObservation],
    *,
    category_key: str,
    platform: SocialPlatform,
    limit: int = 10,
) -> CompetitorActionPlan:
    candidates = rank_public_creatives(
        observations,
        category_key=category_key,
        platform=platform,
        limit=limit,
    )
    usable = tuple(item for item in candidates if item.action is not CreativeAction.DO_NOT_USE)
    if usable:
        reasons = (
            "human_review_required_before_use",
            "competitor_discovery_never_activates_winner",
        )
    else:
        reasons = (
            "no_rights_safe_candidate",
            "start_new_bounded_hypotheses",
            "no_foreign_category_winner",
        )
    return CompetitorActionPlan(
        category_key=category_key,
        platform=platform,
        candidates=candidates,
        fallback_action=CreativeAction.MAKE_NEW,
        reason_codes=reasons,
    )
