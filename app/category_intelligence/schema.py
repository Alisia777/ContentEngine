"""Safe, deterministic contracts for category research intelligence.

Only allowlisted structural features are represented here. Raw captions,
prompts, URLs, claims and source prose deliberately have no place in these
schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Final

from app.competitive_intelligence.schema import (
    CtaStyle,
    HookType,
    Pacing,
    ProofType,
    SocialPlatform,
    StructuralProfile,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


class StructuralFeature(StrEnum):
    HOOK_TYPE = "hook_type"
    PACING = "pacing"
    PROOF_TYPE = "proof_type"
    CTA_STYLE = "cta_style"
    SHOT_COUNT_BUCKET = "shot_count_bucket"
    PRODUCT_VISIBILITY = "product_visibility"


STRUCTURAL_FEATURES: Final[tuple[StructuralFeature, ...]] = tuple(StructuralFeature)

_ALLOWED_SIGNAL_VALUES: Final[dict[StructuralFeature, frozenset[str]]] = {
    StructuralFeature.HOOK_TYPE: frozenset(item.value for item in HookType if item is not HookType.UNKNOWN),
    StructuralFeature.PACING: frozenset(item.value for item in Pacing if item is not Pacing.UNKNOWN),
    StructuralFeature.PROOF_TYPE: frozenset(item.value for item in ProofType if item is not ProofType.UNKNOWN),
    StructuralFeature.CTA_STYLE: frozenset(item.value for item in CtaStyle if item is not CtaStyle.UNKNOWN),
    StructuralFeature.SHOT_COUNT_BUCKET: frozenset({"1", "2_4", "5_8", "9_plus"}),
    StructuralFeature.PRODUCT_VISIBILITY: frozenset(
        {"continuous", "early", "late", "intermittent"}
    ),
}


class TrendDirection(StrEnum):
    EMERGING = "emerging"
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    UNCONFIRMED = "unconfirmed"


class TrendFreshness(StrEnum):
    FRESH = "fresh"
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class StructuralSignal:
    """One reusable structural value, never raw creative content."""

    feature: StructuralFeature
    value: str

    def __post_init__(self) -> None:
        if self.value not in _ALLOWED_SIGNAL_VALUES[self.feature]:
            raise ValueError("structural_signal_value_invalid")


@dataclass(frozen=True, slots=True)
class TrendCorroboration:
    unique_accounts: int
    unique_sources: int
    unique_providers: int

    def __post_init__(self) -> None:
        if min(self.unique_accounts, self.unique_sources, self.unique_providers) < 0:
            raise ValueError("corroboration_count_invalid")

    @property
    def sufficient_for_positive_direction(self) -> bool:
        return self.unique_accounts >= 2 and self.unique_sources >= 2


@dataclass(frozen=True, slots=True)
class TrendHypothesis:
    category_key: str
    platform: SocialPlatform
    signal: StructuralSignal
    direction: TrendDirection
    freshness: TrendFreshness
    freshness_score: float
    confidence: float
    corroboration: TrendCorroboration
    recent_count: int
    baseline_count: int
    recent_share: float
    baseline_share: float
    share_delta: float
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.category_key or len(self.category_key) > 80:
            raise ValueError("category_key_invalid")
        for value, code in (
            (self.freshness_score, "freshness_score_invalid"),
            (self.confidence, "confidence_invalid"),
            (self.recent_share, "recent_share_invalid"),
            (self.baseline_share, "baseline_share_invalid"),
        ):
            if not 0 <= value <= 1:
                raise ValueError(code)
        if not -1 <= self.share_delta <= 1:
            raise ValueError("share_delta_invalid")
        if self.recent_count < 0 or self.baseline_count < 0:
            raise ValueError("observation_count_invalid")
        if self.direction in {TrendDirection.EMERGING, TrendDirection.GROWING}:
            if self.recent_count < 2 or not self.corroboration.sufficient_for_positive_direction:
                raise ValueError("positive_trend_requires_corroboration")


class ResearchReadiness(StrEnum):
    BLOCKED = "blocked"
    PARTIAL = "partial"
    READY = "ready"


class ResearchAction(StrEnum):
    COLLECT_RECENT_OBSERVATIONS = "collect_recent_observations"
    DIVERSIFY_SOURCES = "diversify_sources"
    COMPLETE_STRUCTURAL_TAGGING = "complete_structural_tagging"
    COLLECT_BASELINE_OBSERVATIONS = "collect_baseline_observations"
    REVIEW_CORROBORATED_TRENDS = "review_corroborated_trends"
    DESIGN_BOUNDED_EXPERIMENT = "design_bounded_experiment"


@dataclass(frozen=True, slots=True)
class CategoryResearchCoverage:
    category_key: str
    platform: SocialPlatform
    readiness: ResearchReadiness
    total_observations: int
    recent_observations: int
    baseline_observations: int
    informative_observations: int
    unique_accounts: int
    unique_sources: int
    covered_features: tuple[StructuralFeature, ...]
    missing_features: tuple[StructuralFeature, ...]
    freshness: TrendFreshness
    coverage_score: float
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.category_key or len(self.category_key) > 80:
            raise ValueError("category_key_invalid")
        counts = (
            self.total_observations,
            self.recent_observations,
            self.baseline_observations,
            self.informative_observations,
            self.unique_accounts,
            self.unique_sources,
        )
        if min(counts) < 0:
            raise ValueError("coverage_count_invalid")
        if not 0 <= self.coverage_score <= 1:
            raise ValueError("coverage_score_invalid")
        if len(set(self.covered_features)) != len(self.covered_features):
            raise ValueError("covered_features_duplicate")
        if len(set(self.missing_features)) != len(self.missing_features):
            raise ValueError("missing_features_duplicate")
        if set(self.covered_features) & set(self.missing_features):
            raise ValueError("coverage_feature_overlap")


@dataclass(frozen=True, slots=True)
class ProactiveNextAction:
    action: ResearchAction
    priority: int
    target_observation_count: int
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 1 <= self.priority <= 100:
            raise ValueError("priority_invalid")
        if self.target_observation_count < 0:
            raise ValueError("target_observation_count_invalid")


@dataclass(frozen=True, slots=True)
class CategoryResearchAssessment:
    coverage: CategoryResearchCoverage
    hypotheses: tuple[TrendHypothesis, ...]
    next_action: ProactiveNextAction

    def __post_init__(self) -> None:
        for hypothesis in self.hypotheses:
            if hypothesis.category_key != self.coverage.category_key:
                raise ValueError("hypothesis_category_mismatch")
            if hypothesis.platform is not self.coverage.platform:
                raise ValueError("hypothesis_platform_mismatch")


class ContentStage(StrEnum):
    SOURCE_DISCOVERY = "source_discovery"
    CATEGORY_RESEARCH = "category_research"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    CREATIVE_BRIEF = "creative_brief"
    SCENARIO = "scenario"
    SCRIPT = "script"
    PROMPT = "prompt"
    GENERATION = "generation"
    QUALITY_REVIEW = "quality_review"
    PUBLICATION = "publication"
    LEARNING = "learning"


DEFAULT_STAGE_ORDER: Final[tuple[ContentStage, ...]] = tuple(ContentStage)


class StageCorrectionCode(StrEnum):
    INITIAL_OUTPUT = "initial_output"
    SOURCE_COVERAGE_UPDATED = "source_coverage_updated"
    CATEGORY_RECLASSIFIED = "category_reclassified"
    STRUCTURE_RESELECTED = "structure_reselected"
    BRIEF_CONSTRAINTS_UPDATED = "brief_constraints_updated"
    SCENARIO_STRUCTURE_UPDATED = "scenario_structure_updated"
    SCRIPT_STRUCTURE_UPDATED = "script_structure_updated"
    PROMPT_POLICY_UPDATED = "prompt_policy_updated"
    QA_GUARD_UPDATED = "qa_guard_updated"
    PERFORMANCE_EVIDENCE_UPDATED = "performance_evidence_updated"


@dataclass(frozen=True, slots=True)
class StageArtifactVersion:
    """Immutable control-plane version containing structure, not raw prose."""

    version_id: str
    stage: ContentStage
    revision_number: int
    parent_version_id: str | None
    structural_profile: StructuralProfile | None
    correction_codes: tuple[StageCorrectionCode, ...]

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.version_id):
            raise ValueError("version_id_invalid")
        if self.revision_number < 1:
            raise ValueError("revision_number_invalid")
        if self.parent_version_id is not None and not _SHA256.fullmatch(self.parent_version_id):
            raise ValueError("parent_version_id_invalid")
        if not self.correction_codes:
            raise ValueError("correction_codes_required")
        if len(set(self.correction_codes)) != len(self.correction_codes):
            raise ValueError("correction_codes_duplicate")


@dataclass(frozen=True, slots=True)
class StageState:
    stage: ContentStage
    current_version_id: str | None = None
    stale: bool = False
    stale_due_to_version_id: str | None = None

    def __post_init__(self) -> None:
        if self.current_version_id is not None and not _SHA256.fullmatch(self.current_version_id):
            raise ValueError("current_version_id_invalid")
        if self.stale:
            if self.current_version_id is None or self.stale_due_to_version_id is None:
                raise ValueError("stale_state_requires_lineage")
            if not _SHA256.fullmatch(self.stale_due_to_version_id):
                raise ValueError("stale_due_to_version_id_invalid")
        elif self.stale_due_to_version_id is not None:
            raise ValueError("fresh_state_has_stale_lineage")


@dataclass(frozen=True, slots=True)
class StageRevisionGraph:
    stage_order: tuple[ContentStage, ...]
    versions: tuple[StageArtifactVersion, ...]
    states: tuple[StageState, ...]

    def __post_init__(self) -> None:
        if not self.stage_order or len(set(self.stage_order)) != len(self.stage_order):
            raise ValueError("stage_order_invalid")
        if tuple(state.stage for state in self.states) != self.stage_order:
            raise ValueError("stage_states_mismatch")
        version_ids = [version.version_id for version in self.versions]
        if len(set(version_ids)) != len(version_ids):
            raise ValueError("version_id_duplicate")
        versions_by_id = {version.version_id: version for version in self.versions}
        for version in self.versions:
            if version.stage not in self.stage_order:
                raise ValueError("version_stage_unknown")
            if version.parent_version_id is not None and version.parent_version_id not in versions_by_id:
                raise ValueError("parent_version_unknown")
        for state in self.states:
            if state.current_version_id is None:
                continue
            current = versions_by_id.get(state.current_version_id)
            if current is None or current.stage is not state.stage:
                raise ValueError("current_version_unknown")
            if state.stale_due_to_version_id is not None and state.stale_due_to_version_id not in versions_by_id:
                raise ValueError("stale_lineage_unknown")

    def state_for(self, stage: ContentStage) -> StageState:
        for state in self.states:
            if state.stage is stage:
                return state
        raise ValueError("stage_unknown")

    def current_version_for(self, stage: ContentStage) -> StageArtifactVersion | None:
        version_id = self.state_for(stage).current_version_id
        if version_id is None:
            return None
        return next(version for version in self.versions if version.version_id == version_id)
