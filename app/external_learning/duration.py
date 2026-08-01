"""Duration experiment planning without an eight-second lock."""

from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Iterable, Sequence

from ._common import LearningPolicyError, normalise_text, score_cohort
from .schema import (
    CreativeObservation,
    DurationArm,
    DurationPlan,
    LearningScope,
    MODEL_DURATION_OPTIONS,
    PolicyMode,
    ProviderModel,
)


def cold_start_durations(model: ProviderModel) -> tuple[int, ...]:
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

    all_scores = score_cohort(observations)
    baseline = fmean(all_scores.values()) if all_scores else 0.5
    prior_strength = 4.0
    result: dict[int, tuple[float, int]] = {}
    for duration, group in by_duration.items():
        group_scores = [all_scores[item.observation_id] for item in group]
        support = len(group_scores)
        raw_mean = fmean(group_scores)
        shrunk = (support * raw_mean + prior_strength * baseline) / (
            support + prior_strength
        )
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
    """Choose duration from matched evidence, never a universal 8 seconds."""

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

    category = normalise_text(category_key)
    target_platform = normalise_text(platform)
    target_sku = str(sku or "").strip()
    if not category or not target_platform or not target_sku:
        raise LearningPolicyError("duration_scope_invalid")

    usable = [
        item
        for item in observations
        if item.model is model
        and normalise_text(item.category_key) == category
        and normalise_text(item.platform) == target_platform
        and item.duration_seconds in allowed
        and (
            item.activation_eligible
            if require_activation_approval
            else item.structurally_eligible
        )
    ]
    exact = [item for item in usable if item.sku == target_sku]
    selected = exact if len({item.duration_seconds for item in exact}) >= 2 else usable
    scope = (
        LearningScope.PRODUCT
        if selected is exact and exact
        else LearningScope.CATEGORY
    )
    scores = _duration_scores(selected)

    eligible = [
        (duration, score, support)
        for duration, (score, support) in scores.items()
        if support >= 3
    ]
    eligible.sort(
        key=lambda item: (item[1], item[2], -item[0]),
        reverse=True,
    )
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

    cold = cold_start_durations(model)
    allocation = 1.0 / len(cold)
    return DurationPlan(
        model=model,
        scope=LearningScope.NEW_CATEGORY if not usable else scope,
        mode=PolicyMode.EXPLORE,
        arms=tuple(
            DurationArm(seconds=value, allocation=allocation) for value in cold
        ),
        allowed_durations=allowed,
        evidence_count=len(selected),
        reason_codes=(
            "duration_not_locked_to_eight_seconds",
            "insufficient_matched_duration_evidence",
            "cross_category_duration_forbidden",
        ),
    )
