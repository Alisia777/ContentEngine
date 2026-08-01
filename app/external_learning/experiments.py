"""Cold-start and exploit experiment plans for product categories."""

from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Iterable, Sequence

from ._common import (
    DEFAULT_HYPOTHESIS_ANGLES,
    GLOBAL_SAFE_CONTROL_ANGLE,
    LearningPolicyError,
    normalise_text,
    score_cohort,
)
from .creative import select_successful_creatives
from .duration import choose_duration_plan
from .schema import (
    CategoryExperimentPlan,
    CreativeObservation,
    ExperimentArm,
    LearningScope,
    PolicyMode,
    ProviderModel,
)


def _category_angles(
    observations: Sequence[CreativeObservation],
    category_key: str,
) -> tuple[str, ...]:
    category = normalise_text(category_key)
    eligible = [
        item
        for item in observations
        if normalise_text(item.category_key) == category
        and item.activation_eligible
        and item.creative_angle not in {"", "unknown"}
    ]
    if len(eligible) < 6:
        return DEFAULT_HYPOTHESIS_ANGLES

    scores = score_cohort(eligible)
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
    learned = tuple(
        item[0]
        for item in ranked
        if item[0] != GLOBAL_SAFE_CONTROL_ANGLE
    )
    if len(learned) < 2:
        return DEFAULT_HYPOTHESIS_ANGLES
    return tuple(
        dict.fromkeys((*learned, *DEFAULT_HYPOTHESIS_ANGLES))
    )[:3]


def _distinct_hypothesis_angles(
    preferred: Sequence[str],
    *,
    excluded: set[str],
    count: int,
) -> tuple[str, ...]:
    values: list[str] = []
    for candidate in (*preferred, *DEFAULT_HYPOTHESIS_ANGLES):
        value = str(candidate or "").strip()
        if not value or value in excluded or value in values:
            continue
        values.append(value)
        if len(values) == count:
            return tuple(values)
    raise LearningPolicyError("distinct_experiment_angles_unavailable")


def build_category_experiment_plan(
    observations: Iterable[CreativeObservation],
    *,
    category_key: str,
    sku: str,
    platform: str,
    model: ProviderModel,
    require_activation_approval: bool = True,
) -> CategoryExperimentPlan:
    """Build a conservative plan for an existing or new category."""

    source = tuple(observations)
    winners = select_successful_creatives(
        source,
        category_key=category_key,
        sku=sku,
        platform=platform,
        require_activation_approval=require_activation_approval,
        maximum_candidates=1,
        minimum_observations=3,
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
            item
            for item in source
            if item.observation_id == winner.observation_id
        )
        winner_angle = winner_observation.creative_angle
        control_angle = (
            "product_focus"
            if winner_angle == GLOBAL_SAFE_CONTROL_ANGLE
            else GLOBAL_SAFE_CONTROL_ANGLE
        )
        exploration_angle = _distinct_hypothesis_angles(
            _category_angles(source, category_key),
            excluded={winner_angle, control_angle},
            count=1,
        )[0]
        return CategoryExperimentPlan(
            category_key=category_key,
            model=model,
            mode=PolicyMode.EXPLOIT,
            arms=(
                ExperimentArm(
                    name="Проверенный паттерн",
                    creative_angle=winner_angle,
                    duration_seconds=primary_duration,
                    allocation=0.60,
                    source_scope=LearningScope.PRODUCT,
                ),
                ExperimentArm(
                    name="Контроль без обучения",
                    creative_angle=control_angle,
                    duration_seconds=control_duration,
                    allocation=0.20,
                    source_scope=LearningScope.GLOBAL_SAFE,
                    is_control=True,
                ),
                ExperimentArm(
                    name="Ограниченное исследование",
                    creative_angle=exploration_angle,
                    duration_seconds=control_duration,
                    allocation=0.20,
                    source_scope=LearningScope.CATEGORY,
                ),
            ),
            reason_codes=(
                "same_product_winner",
                "minimum_three_independent_observations",
                "control_required",
                "distinct_experiment_angles",
                "bounded_exploration",
                "observational_signal_not_causal_proof",
            ),
            selected_winner_id=winner.observation_id,
        )

    hypotheses = _distinct_hypothesis_angles(
        _category_angles(source, category_key),
        excluded={GLOBAL_SAFE_CONTROL_ANGLE},
        count=2,
    )
    first_duration = durations[0]
    second_duration = durations[1] if len(durations) > 1 else first_duration
    return CategoryExperimentPlan(
        category_key=category_key,
        model=model,
        mode=PolicyMode.EXPLORE,
        arms=(
            ExperimentArm(
                name="Контроль",
                creative_angle=GLOBAL_SAFE_CONTROL_ANGLE,
                duration_seconds=first_duration,
                allocation=0.34,
                source_scope=LearningScope.GLOBAL_SAFE,
                is_control=True,
            ),
            ExperimentArm(
                name="Гипотеза категории A",
                creative_angle=hypotheses[0],
                duration_seconds=second_duration,
                allocation=0.33,
                source_scope=LearningScope.NEW_CATEGORY,
            ),
            ExperimentArm(
                name="Гипотеза категории B",
                creative_angle=hypotheses[1],
                duration_seconds=first_duration,
                allocation=0.33,
                source_scope=LearningScope.NEW_CATEGORY,
            ),
        ),
        reason_codes=(
            "new_or_sparse_category",
            "no_foreign_category_winner",
            "distinct_experiment_angles",
            "three_arm_cold_start",
        ),
    )
