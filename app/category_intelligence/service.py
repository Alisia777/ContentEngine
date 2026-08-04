"""Facade for category readiness, next actions and immutable stage revisions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json

from app.competitive_intelligence.schema import PublicCreativeObservation, SocialPlatform, StructuralProfile

from .schema import (
    DEFAULT_STAGE_ORDER,
    STRUCTURAL_FEATURES,
    CategoryResearchAssessment,
    CategoryResearchCoverage,
    ContentStage,
    ProactiveNextAction,
    ResearchAction,
    ResearchReadiness,
    StageArtifactVersion,
    StageCorrectionCode,
    StageRevisionGraph,
    StageState,
    TrendDirection,
    TrendHypothesis,
)
from .trends import (
    analyze_category_trends,
    build_observation_windows,
    freshness_for,
    structural_signals,
)


class CategoryIntelligenceError(ValueError):
    """A deterministic category-intelligence contract error."""


def _coverage_readiness(
    *,
    recent_count: int,
    baseline_count: int,
    informative_count: int,
    total_count: int,
    account_count: int,
    source_count: int,
    covered_count: int,
) -> ResearchReadiness:
    if recent_count < 2 or account_count < 2 or source_count < 2:
        return ResearchReadiness.BLOCKED
    informative_ratio = informative_count / total_count if total_count else 0.0
    if recent_count < 4 or baseline_count < 4 or informative_ratio < 0.75 or covered_count < 4:
        return ResearchReadiness.PARTIAL
    return ResearchReadiness.READY


def _next_action_for(
    coverage: CategoryResearchCoverage,
    *,
    positive_hypothesis_count: int,
) -> ProactiveNextAction:
    if coverage.recent_observations < 2:
        return ProactiveNextAction(
            action=ResearchAction.COLLECT_RECENT_OBSERVATIONS,
            priority=100,
            target_observation_count=4,
            reason_codes=("recent_window_insufficient", "collect_structure_only"),
        )
    if coverage.unique_accounts < 2 or coverage.unique_sources < 2:
        return ProactiveNextAction(
            action=ResearchAction.DIVERSIFY_SOURCES,
            priority=95,
            target_observation_count=2,
            reason_codes=(
                "independent_corroboration_required",
                "single_account_cannot_activate_positive_trend",
            ),
        )
    informative_ratio = (
        coverage.informative_observations / coverage.total_observations
        if coverage.total_observations
        else 0.0
    )
    if informative_ratio < 0.75 or len(coverage.covered_features) < 4:
        return ProactiveNextAction(
            action=ResearchAction.COMPLETE_STRUCTURAL_TAGGING,
            priority=90,
            target_observation_count=max(4, coverage.total_observations),
            reason_codes=("structural_coverage_incomplete", "raw_content_not_required"),
        )
    if coverage.baseline_observations < 4:
        return ProactiveNextAction(
            action=ResearchAction.COLLECT_BASELINE_OBSERVATIONS,
            priority=85,
            target_observation_count=4,
            reason_codes=("baseline_window_insufficient", "recent_change_needs_baseline"),
        )
    if coverage.recent_observations < 4:
        return ProactiveNextAction(
            action=ResearchAction.COLLECT_RECENT_OBSERVATIONS,
            priority=80,
            target_observation_count=4,
            reason_codes=("recent_window_below_ready_threshold", "collect_structure_only"),
        )
    if positive_hypothesis_count:
        return ProactiveNextAction(
            action=ResearchAction.REVIEW_CORROBORATED_TRENDS,
            priority=75,
            target_observation_count=0,
            reason_codes=("human_review_before_experiment", "trend_is_hypothesis_not_winner"),
        )
    return ProactiveNextAction(
        action=ResearchAction.DESIGN_BOUNDED_EXPERIMENT,
        priority=70,
        target_observation_count=0,
        reason_codes=("coverage_ready", "retain_control_arm", "human_activation_required"),
    )


def assess_category_research(
    observations: Iterable[PublicCreativeObservation],
    *,
    category_key: str,
    platform: SocialPlatform,
    as_of: datetime,
    recent_window_days: int = 7,
    baseline_window_days: int = 28,
) -> CategoryResearchAssessment:
    """Assess evidence coverage and always return one safe next action."""

    items = tuple(observations)
    windows = build_observation_windows(
        items,
        category_key=category_key,
        platform=platform,
        as_of=as_of,
        recent_window_days=recent_window_days,
        baseline_window_days=baseline_window_days,
    )
    hypotheses = analyze_category_trends(
        items,
        category_key=category_key,
        platform=platform,
        as_of=as_of,
        recent_window_days=recent_window_days,
        baseline_window_days=baseline_window_days,
    )
    all_observations = windows.all
    informative = tuple(item for item in all_observations if item.structural_profile.is_informative)
    accounts = {item.account_key for item in all_observations}
    sources = {item.source_locator_hash for item in all_observations}
    covered = {
        signal.feature
        for observation in informative
        for signal in structural_signals(observation.structural_profile)
    }
    covered_features = tuple(feature for feature in STRUCTURAL_FEATURES if feature in covered)
    missing_features = tuple(feature for feature in STRUCTURAL_FEATURES if feature not in covered)
    freshness, _freshness_score = freshness_for(
        windows.recent or all_observations,
        as_of=as_of,
        recent_window_days=recent_window_days,
    )

    total_count = len(all_observations)
    informative_ratio = len(informative) / total_count if total_count else 0.0
    volume_score = min(1.0, total_count / 8)
    recent_score = min(1.0, len(windows.recent) / 4)
    baseline_score = min(1.0, len(windows.baseline) / 4)
    diversity_score = min(1.0, min(len(accounts), len(sources)) / 3)
    structure_score = (len(covered_features) / len(STRUCTURAL_FEATURES)) * informative_ratio
    coverage_score = round(
        0.15 * volume_score
        + 0.20 * recent_score
        + 0.20 * baseline_score
        + 0.20 * diversity_score
        + 0.25 * structure_score,
        6,
    )
    readiness = _coverage_readiness(
        recent_count=len(windows.recent),
        baseline_count=len(windows.baseline),
        informative_count=len(informative),
        total_count=total_count,
        account_count=len(accounts),
        source_count=len(sources),
        covered_count=len(covered_features),
    )
    reason_codes: list[str] = ["structure_only_no_raw_content"]
    if len(windows.recent) < 4:
        reason_codes.append("recent_coverage_below_ready_threshold")
    if len(windows.baseline) < 4:
        reason_codes.append("baseline_coverage_below_ready_threshold")
    if len(accounts) < 2 or len(sources) < 2:
        reason_codes.append("independent_source_coverage_missing")
    if informative_ratio < 0.75 or len(covered_features) < 4:
        reason_codes.append("structural_tagging_incomplete")
    if readiness is ResearchReadiness.READY:
        reason_codes.append("category_research_ready")

    coverage = CategoryResearchCoverage(
        category_key=category_key,
        platform=platform,
        readiness=readiness,
        total_observations=total_count,
        recent_observations=len(windows.recent),
        baseline_observations=len(windows.baseline),
        informative_observations=len(informative),
        unique_accounts=len(accounts),
        unique_sources=len(sources),
        covered_features=covered_features,
        missing_features=missing_features,
        freshness=freshness,
        coverage_score=coverage_score,
        reason_codes=tuple(reason_codes),
    )
    positive_count = sum(
        item.direction in {TrendDirection.EMERGING, TrendDirection.GROWING}
        for item in hypotheses
    )
    return CategoryResearchAssessment(
        coverage=coverage,
        hypotheses=hypotheses,
        next_action=_next_action_for(coverage, positive_hypothesis_count=positive_count),
    )


def new_stage_revision_graph(
    stage_order: tuple[ContentStage, ...] = DEFAULT_STAGE_ORDER,
) -> StageRevisionGraph:
    """Create an empty immutable stage graph."""

    return StageRevisionGraph(
        stage_order=stage_order,
        versions=(),
        states=tuple(StageState(stage=stage) for stage in stage_order),
    )


def _profile_payload(profile: StructuralProfile | None) -> dict[str, str] | None:
    if profile is None:
        return None
    return {
        "hook_type": profile.hook_type.value,
        "pacing": profile.pacing.value,
        "proof_type": profile.proof_type.value,
        "cta_style": profile.cta_style.value,
        "shot_count_bucket": profile.shot_count_bucket,
        "product_visibility": profile.product_visibility,
    }


def _validated_codes(
    correction_codes: Iterable[StageCorrectionCode],
    *,
    initial: bool,
) -> tuple[StageCorrectionCode, ...]:
    codes = tuple(correction_codes)
    if not codes or any(not isinstance(code, StageCorrectionCode) for code in codes):
        raise CategoryIntelligenceError("correction_codes_invalid")
    if len(set(codes)) != len(codes):
        raise CategoryIntelligenceError("correction_codes_duplicate")
    contains_initial = StageCorrectionCode.INITIAL_OUTPUT in codes
    if initial != contains_initial or (initial and len(codes) != 1):
        raise CategoryIntelligenceError("initial_output_code_invalid")
    return tuple(sorted(codes, key=lambda item: item.value))


def _append_stage_version(
    graph: StageRevisionGraph,
    *,
    stage: ContentStage,
    structural_profile: StructuralProfile | None,
    correction_codes: tuple[StageCorrectionCode, ...],
) -> StageRevisionGraph:
    if stage not in graph.stage_order:
        raise CategoryIntelligenceError("stage_unknown")
    parent = graph.current_version_for(stage)
    revision_number = 1 + sum(version.stage is stage for version in graph.versions)
    identity_payload = {
        "stage": stage.value,
        "revision_number": revision_number,
        "parent_version_id": parent.version_id if parent else None,
        "structural_profile": _profile_payload(structural_profile),
        "correction_codes": [code.value for code in correction_codes],
    }
    version_id = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    version = StageArtifactVersion(
        version_id=version_id,
        stage=stage,
        revision_number=revision_number,
        parent_version_id=parent.version_id if parent else None,
        structural_profile=structural_profile,
        correction_codes=correction_codes,
    )

    changed_index = graph.stage_order.index(stage)
    states: list[StageState] = []
    for index, state in enumerate(graph.states):
        if state.stage is stage:
            states.append(StageState(stage=stage, current_version_id=version_id))
        elif index > changed_index and state.current_version_id is not None:
            states.append(
                replace(
                    state,
                    stale=True,
                    stale_due_to_version_id=version_id,
                )
            )
        else:
            states.append(state)
    return StageRevisionGraph(
        stage_order=graph.stage_order,
        versions=graph.versions + (version,),
        states=tuple(states),
    )


def record_stage_output(
    graph: StageRevisionGraph,
    *,
    stage: ContentStage,
    structural_profile: StructuralProfile | None = None,
) -> StageRevisionGraph:
    """Record the first immutable output for a stage."""

    if graph.current_version_for(stage) is not None:
        raise CategoryIntelligenceError("stage_output_already_exists")
    return _append_stage_version(
        graph,
        stage=stage,
        structural_profile=structural_profile,
        correction_codes=_validated_codes((StageCorrectionCode.INITIAL_OUTPUT,), initial=True),
    )


def correct_stage(
    graph: StageRevisionGraph,
    *,
    stage: ContentStage,
    correction_codes: Iterable[StageCorrectionCode],
    structural_profile: StructuralProfile | None = None,
) -> StageRevisionGraph:
    """Append a revision and mark every materialized downstream stage stale."""

    if graph.current_version_for(stage) is None:
        raise CategoryIntelligenceError("stage_output_missing")
    return _append_stage_version(
        graph,
        stage=stage,
        structural_profile=structural_profile,
        correction_codes=_validated_codes(correction_codes, initial=False),
    )


@dataclass(frozen=True, slots=True)
class CategoryIntelligenceService:
    """Pure in-memory facade; persistence and provider ingestion are external adapters."""

    recent_window_days: int = 7
    baseline_window_days: int = 28

    def __post_init__(self) -> None:
        if not 1 <= self.recent_window_days <= 90:
            raise CategoryIntelligenceError("recent_window_days_invalid")
        if not 1 <= self.baseline_window_days <= 365:
            raise CategoryIntelligenceError("baseline_window_days_invalid")

    def analyze_trends(
        self,
        observations: Iterable[PublicCreativeObservation],
        *,
        category_key: str,
        platform: SocialPlatform,
        as_of: datetime,
    ) -> tuple[TrendHypothesis, ...]:
        return analyze_category_trends(
            observations,
            category_key=category_key,
            platform=platform,
            as_of=as_of,
            recent_window_days=self.recent_window_days,
            baseline_window_days=self.baseline_window_days,
        )

    def assess_research(
        self,
        observations: Iterable[PublicCreativeObservation],
        *,
        category_key: str,
        platform: SocialPlatform,
        as_of: datetime,
    ) -> CategoryResearchAssessment:
        return assess_category_research(
            observations,
            category_key=category_key,
            platform=platform,
            as_of=as_of,
            recent_window_days=self.recent_window_days,
            baseline_window_days=self.baseline_window_days,
        )
