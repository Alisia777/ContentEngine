"""Typed contracts for the controllable ContentEngine mini-AI.

The mini-AI is an experiment controller, not an unconstrained language model.
It may choose bounded experiment arms and explain evidence, but it cannot
change product facts, bypass QA, spend outside the approved budget, or declare
an observational signal to be causal proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from app.external_learning import FunnelDecision, ProviderModel


class LearningObjective(StrEnum):
    ORDERS = "orders"
    SALES = "sales"
    CONVERSION = "conversion"
    QA_ACCEPTANCE = "qa_acceptance"
    COST_PER_ORDER = "cost_per_order"


class ExperimentDimension(StrEnum):
    AUTO = "auto"
    CREATIVE_ANGLE = "creative_angle"
    DURATION = "duration"
    PROOF_TYPE = "proof_type"
    CTA_STYLE = "cta_style"


class RiskPreset(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    EXPLORATORY = "exploratory"


class PlanMode(StrEnum):
    BLOCKED = "blocked"
    EXPLORE = "explore"
    EXPLOIT_WITH_CONTROL = "exploit_with_control"


class OutcomeState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CENSORED = "censored"


class QaState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_CHANGES = "needs_changes"
    REJECTED = "rejected"


class MiniAiDecision(StrEnum):
    BLOCKED = "blocked"
    PAUSE_QUALITY = "pause_quality"
    PAUSE_TECHNICAL = "pause_technical"
    WAIT_METRICS = "wait_metrics"
    COLLECT_MORE = "collect_more"
    KEEP_CONTROL = "keep_control"
    PROMOTE_WITH_CONTROL = "promote_with_control"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class MiniAiContext:
    organization_key: str
    learning_category_key: str
    sku: str
    platform: str
    model: ProviderModel
    objective: LearningObjective = LearningObjective.ORDERS
    risk_preset: RiskPreset = RiskPreset.BALANCED
    requested_dimension: ExperimentDimension = ExperimentDimension.AUTO
    requested_batch_size: int = 6
    unit_cost_minor: int = 0
    max_budget_minor: int = 0
    funnel_decision: FunnelDecision = FunnelDecision.OBSERVE
    category_is_new: bool = False
    approved_winner_angle: str | None = None
    approved_winner_duration: int | None = None

    def __post_init__(self) -> None:
        for value, code, maximum in (
            (self.organization_key, "organization_key_invalid", 160),
            (self.learning_category_key, "learning_category_key_invalid", 120),
            (self.sku, "sku_invalid", 120),
            (self.platform, "platform_invalid", 80),
        ):
            cleaned = str(value or "").strip()
            if not cleaned or len(cleaned) > maximum:
                raise ValueError(code)
        if self.requested_batch_size < 1 or self.requested_batch_size > 50:
            raise ValueError("batch_size_invalid")
        if self.unit_cost_minor < 0 or self.max_budget_minor < 0:
            raise ValueError("budget_invalid")
        if self.max_budget_minor and self.unit_cost_minor > self.max_budget_minor:
            raise ValueError("single_run_exceeds_budget")


@dataclass(frozen=True, slots=True)
class MiniAiRules:
    version: str = "mini-ai-rulebook-v1"
    minimum_batch_size: int = 4
    maximum_batch_size: int = 12
    maximum_arms: int = 3
    minimum_control_share: float = 0.20
    minimum_observations_per_arm: int = 3
    minimum_total_observations: int = 6
    minimum_relative_uplift: float = 0.15
    minimum_orders_per_day_gap: float = 0.25
    minimum_sales_per_day_gap_minor: int = 500
    minimum_conversion_gap: float = 0.03
    minimum_qa_gap: float = 0.10
    minimum_cost_per_order_improvement: float = 0.15
    minimum_qa_rate: float = 0.70
    maximum_failure_rate: float = 0.30
    maximum_critical_blockers: int = 0
    pause_on_product_mismatch: bool = True
    retain_control_after_winner: bool = True
    winner_allocation: float = 0.70
    control_allocation: float = 0.30
    one_dimension_per_cycle: bool = True
    views_can_select_winner: bool = False
    cross_category_transfer_allowed: bool = False
    human_approval_required_for_scale: bool = True

    def __post_init__(self) -> None:
        if self.minimum_batch_size < 2:
            raise ValueError("minimum_batch_size_invalid")
        if self.maximum_batch_size < self.minimum_batch_size:
            raise ValueError("maximum_batch_size_invalid")
        if self.maximum_arms not in {2, 3}:
            raise ValueError("maximum_arms_invalid")
        if not 0.15 <= self.minimum_control_share <= 0.50:
            raise ValueError("control_share_invalid")
        if abs(self.winner_allocation + self.control_allocation - 1) > 0.0001:
            raise ValueError("winner_control_allocation_invalid")


@dataclass(frozen=True, slots=True)
class ExperimentArm:
    arm_id: str
    label_ru: str
    is_control: bool
    allocation: float
    planned_count: int
    duration_seconds: int
    creative_angle: str
    hook_type: str
    proof_type: str
    cta_style: str
    instruction_ru: str
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.arm_id or len(self.arm_id) > 80:
            raise ValueError("arm_id_invalid")
        if not 0 < self.allocation <= 1:
            raise ValueError("arm_allocation_invalid")
        if self.planned_count < 1:
            raise ValueError("arm_count_invalid")
        if self.duration_seconds < 0 or self.duration_seconds > 60:
            raise ValueError("arm_duration_invalid")
        if len(self.instruction_ru.strip()) < 10 or len(self.instruction_ru) > 600:
            raise ValueError("arm_instruction_invalid")


@dataclass(frozen=True, slots=True)
class MassGenerationPlan:
    plan_id: str
    rules_version: str
    mode: PlanMode
    context: MiniAiContext
    dimension: ExperimentDimension
    arms: tuple[ExperimentArm, ...]
    batch_size: int
    estimated_cost_minor: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return self.mode is not PlanMode.BLOCKED and not self.blockers and bool(self.arms)

    def __post_init__(self) -> None:
        if not self.plan_id or len(self.plan_id) > 96:
            raise ValueError("plan_id_invalid")
        if self.mode is PlanMode.BLOCKED:
            if self.arms:
                raise ValueError("blocked_plan_has_arms")
            return
        if len(self.arms) < 2 or len(self.arms) > 3:
            raise ValueError("plan_arm_count_invalid")
        if sum(arm.planned_count for arm in self.arms) != self.batch_size:
            raise ValueError("plan_batch_count_mismatch")
        if abs(sum(arm.allocation for arm in self.arms) - 1) > 0.001:
            raise ValueError("plan_allocation_mismatch")
        controls = [arm for arm in self.arms if arm.is_control]
        if len(controls) != 1:
            raise ValueError("plan_control_invalid")


@dataclass(frozen=True, slots=True)
class ArmOutcome:
    outcome_id: str
    arm_id: str
    job_id: str
    state: OutcomeState
    qa_state: QaState = QaState.PENDING
    product_fidelity_ok: bool = True
    critical_blocker: bool = False
    published: bool = False
    metrics_mature: bool = False
    orders: int | None = None
    carts: int | None = None
    sales_minor: int | None = None
    spend_minor: int | None = None
    attribution_days: int = 1
    views: int | None = None
    creator_key: str = ""

    def __post_init__(self) -> None:
        if not self.outcome_id or not self.arm_id or not self.job_id:
            raise ValueError("outcome_identity_invalid")
        if self.attribution_days < 1 or self.attribution_days > 365:
            raise ValueError("outcome_window_invalid")
        for value, code in (
            (self.orders, "orders_invalid"),
            (self.carts, "carts_invalid"),
            (self.sales_minor, "sales_invalid"),
            (self.spend_minor, "spend_invalid"),
            (self.views, "views_invalid"),
        ):
            if value is not None and value < 0:
                raise ValueError(code)
        if self.orders is not None and self.carts is not None and self.orders > self.carts:
            raise ValueError("orders_exceed_carts")

    @property
    def completed(self) -> bool:
        return self.state in {
            OutcomeState.SUCCEEDED,
            OutcomeState.FAILED,
            OutcomeState.CANCELLED,
        }

    @property
    def commercially_eligible(self) -> bool:
        return (
            self.state is OutcomeState.SUCCEEDED
            and self.qa_state is QaState.APPROVED
            and self.product_fidelity_ok
            and not self.critical_blocker
            and self.published
            and self.metrics_mature
            and self.orders is not None
        )


@dataclass(frozen=True, slots=True)
class ArmSummary:
    arm_id: str
    completed: int
    eligible: int
    approved: int
    failed: int
    critical_blockers: int
    product_mismatches: int
    orders: int
    carts: int
    sales_minor: int
    spend_minor: int
    attribution_days: int
    views: int
    independent_jobs: int
    independent_creators: int
    orders_per_day: float
    conversion: float
    sales_per_day_minor: float
    qa_rate: float
    cost_per_order_minor: float | None
    objective_value: float


@dataclass(frozen=True, slots=True)
class MiniAiConclusion:
    decision: MiniAiDecision
    confidence: str
    summary_ru: str
    next_action_ru: str
    winner_arm_id: str | None = None
    control_arm_id: str | None = None
    recommended_allocations: Mapping[str, float] = field(default_factory=dict)
    arm_summaries: tuple[ArmSummary, ...] = ()
    blockers: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    next_dimension: ExperimentDimension = ExperimentDimension.AUTO
