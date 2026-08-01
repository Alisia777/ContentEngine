"""Strict schemas for ContentEngine's external performance-learning core.

The module deliberately models only bounded, structural and performance data.
Raw captions, URLs, prompts, claims and source prose are not reusable learning
features and are therefore absent from the schemas below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Final


class ProviderModel(StrEnum):
    GEN4_TURBO = "gen4_turbo"
    SEEDANCE2_FAST = "seedance2_fast"
    SEEDREAM5_LITE = "seedream5_lite"


class ContentFormat(StrEnum):
    REEL = "reel"
    POST = "post"
    UNKNOWN = "unknown"


class ObservationState(StrEnum):
    ELIGIBLE = "eligible"
    AMBIGUOUS_BUNDLE = "ambiguous_bundle"
    CENSORED_MISSING = "censored_missing"
    IMMATURE = "immature"
    INVALID = "invalid"


class LearningScope(StrEnum):
    PRODUCT = "product"
    CATEGORY = "category"
    NEW_CATEGORY = "new_category"
    GLOBAL_SAFE = "global_safe"
    NOT_APPLICABLE = "not_applicable"


class PolicyMode(StrEnum):
    EXPLOIT = "exploit"
    EXPLORE = "explore"
    COLLECT_MORE_DATA = "collect_more_data"
    NOT_APPLICABLE = "not_applicable"


class FunnelDecision(StrEnum):
    CREATIVE = "creative"
    SUPPLY = "supply"
    EXPECTATION = "expectation"
    ADVERTISING = "advertising"
    SCALE = "scale"
    OBSERVE = "observe"
    MEASUREMENT = "measurement"


MODEL_DURATION_OPTIONS: Final[dict[ProviderModel, tuple[int, ...]]] = {
    ProviderModel.GEN4_TURBO: (2, 5, 8, 10),
    ProviderModel.SEEDANCE2_FAST: (4, 8, 12, 15),
    ProviderModel.SEEDREAM5_LITE: (0,),
}


@dataclass(frozen=True, slots=True)
class CreativeObservation:
    """One attributable creative outcome.

    An observation can be retained for audit while being ineligible for
    learning. This is essential for WW bundles, top-100 API censoring and
    posts that are not videos.
    """

    observation_id: str
    category_key: str
    sku: str
    platform: str
    model: ProviderModel
    content_format: ContentFormat
    published_on: date
    creator_key: str = ""
    ww_code: str = ""
    bundle_size: int = 1
    attribution_days: int = 1
    attribution_complete: bool = True
    duration_seconds: int | None = None
    views: int | None = None
    carts: int | None = None
    orders: int | None = None
    sales_minor: int | None = None
    margin_minor: int | None = None
    hook_type: str = "unknown"
    creative_angle: str = "unknown"
    cta_style: str = "unknown"
    proof_type: str = "unknown"
    state: ObservationState = ObservationState.ELIGIBLE
    qa_approved: bool = False
    rights_confirmed: bool = False

    def __post_init__(self) -> None:
        if not self.observation_id or len(self.observation_id) > 180:
            raise ValueError("observation_id_invalid")
        if not self.category_key or len(self.category_key) > 80:
            raise ValueError("category_key_invalid")
        if not self.sku or len(self.sku) > 120:
            raise ValueError("sku_invalid")
        if not self.platform or len(self.platform) > 80:
            raise ValueError("platform_invalid")
        if self.bundle_size < 1 or self.bundle_size > 100:
            raise ValueError("bundle_size_invalid")
        if self.attribution_days < 1 or self.attribution_days > 90:
            raise ValueError("attribution_days_invalid")
        for value, code in (
            (self.views, "views_invalid"),
            (self.carts, "carts_invalid"),
            (self.orders, "orders_invalid"),
            (self.sales_minor, "sales_minor_invalid"),
            (self.margin_minor, "margin_minor_invalid"),
        ):
            if value is not None and value < 0:
                raise ValueError(code)
        allowed = MODEL_DURATION_OPTIONS[self.model]
        if self.duration_seconds is not None and self.duration_seconds not in allowed:
            raise ValueError("duration_not_supported_by_model")

    @property
    def is_video(self) -> bool:
        return self.content_format is ContentFormat.REEL

    @property
    def structurally_eligible(self) -> bool:
        return (
            self.state is ObservationState.ELIGIBLE
            and self.is_video
            and self.bundle_size == 1
            and self.attribution_complete
            and self.orders is not None
        )

    @property
    def activation_eligible(self) -> bool:
        return self.structurally_eligible and self.qa_approved and self.rights_confirmed


@dataclass(frozen=True, slots=True)
class FunnelObservation:
    category_key: str
    sku: str
    platform: str
    source_status: str = ""
    source_action: str = ""
    visits: int | None = None
    carts: int | None = None
    orders: int | None = None
    sales_minor: int | None = None
    stock: int | None = None
    conversion_visit_to_order: float | None = None
    buyout_rate: float | None = None
    drr: float | None = None
    margin_rate: float | None = None

    def __post_init__(self) -> None:
        if not self.category_key or len(self.category_key) > 80:
            raise ValueError("category_key_invalid")
        if not self.sku or len(self.sku) > 120:
            raise ValueError("sku_invalid")
        if not self.platform or len(self.platform) > 80:
            raise ValueError("platform_invalid")
        for value, code in (
            (self.visits, "visits_invalid"),
            (self.carts, "carts_invalid"),
            (self.orders, "orders_invalid"),
            (self.sales_minor, "sales_minor_invalid"),
            (self.stock, "stock_invalid"),
        ):
            if value is not None and value < 0:
                raise ValueError(code)
        for value, code in (
            (self.conversion_visit_to_order, "conversion_invalid"),
            (self.buyout_rate, "buyout_invalid"),
            (self.drr, "drr_invalid"),
            (self.margin_rate, "margin_invalid"),
        ):
            if value is not None and not 0 <= value <= 1.5:
                raise ValueError(code)


@dataclass(frozen=True, slots=True)
class DurationArm:
    seconds: int
    allocation: float
    evidence_count: int = 0
    score: float | None = None

    def __post_init__(self) -> None:
        if self.seconds < 0 or self.seconds > 60:
            raise ValueError("duration_arm_invalid")
        if not 0 < self.allocation <= 1:
            raise ValueError("allocation_invalid")
        if self.evidence_count < 0:
            raise ValueError("evidence_count_invalid")
        if self.score is not None and not 0 <= self.score <= 1:
            raise ValueError("score_invalid")


@dataclass(frozen=True, slots=True)
class DurationPlan:
    model: ProviderModel
    scope: LearningScope
    mode: PolicyMode
    arms: tuple[DurationArm, ...]
    allowed_durations: tuple[int, ...]
    evidence_count: int
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.evidence_count < 0:
            raise ValueError("evidence_count_invalid")
        if tuple(self.allowed_durations) != MODEL_DURATION_OPTIONS[self.model]:
            raise ValueError("allowed_duration_contract_mismatch")
        if self.model is ProviderModel.SEEDREAM5_LITE:
            if self.mode is not PolicyMode.NOT_APPLICABLE or self.arms != (DurationArm(0, 1.0),):
                raise ValueError("photo_duration_plan_invalid")
        elif not self.arms:
            raise ValueError("duration_arms_required")
        if any(arm.seconds not in self.allowed_durations for arm in self.arms):
            raise ValueError("duration_arm_not_allowed")
        total = sum(arm.allocation for arm in self.arms)
        if abs(total - 1.0) > 1e-9:
            raise ValueError("duration_allocation_invalid")


@dataclass(frozen=True, slots=True)
class CreativeCandidate:
    observation_id: str
    score: float
    orders_per_day: float
    conversion_proxy: float
    scope: LearningScope
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("candidate_score_invalid")
        if self.orders_per_day < 0 or self.conversion_proxy < 0:
            raise ValueError("candidate_metric_invalid")


@dataclass(frozen=True, slots=True)
class ExperimentArm:
    name: str
    creative_angle: str
    duration_seconds: int
    allocation: float
    source_scope: LearningScope
    is_control: bool = False

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 120:
            raise ValueError("experiment_arm_name_invalid")
        if not self.creative_angle or len(self.creative_angle) > 80:
            raise ValueError("creative_angle_invalid")
        if self.duration_seconds < 0 or self.duration_seconds > 60:
            raise ValueError("duration_invalid")
        if not 0 < self.allocation <= 1:
            raise ValueError("allocation_invalid")


@dataclass(frozen=True, slots=True)
class CategoryExperimentPlan:
    category_key: str
    model: ProviderModel
    mode: PolicyMode
    arms: tuple[ExperimentArm, ...]
    reason_codes: tuple[str, ...]
    selected_winner_id: str | None = None

    def __post_init__(self) -> None:
        if not self.category_key or len(self.category_key) > 80:
            raise ValueError("category_key_invalid")
        if not self.arms:
            raise ValueError("experiment_arms_required")
        if abs(sum(arm.allocation for arm in self.arms) - 1.0) > 1e-9:
            raise ValueError("experiment_allocation_invalid")
        allowed = MODEL_DURATION_OPTIONS[self.model]
        if any(arm.duration_seconds not in allowed for arm in self.arms):
            raise ValueError("experiment_duration_not_allowed")
