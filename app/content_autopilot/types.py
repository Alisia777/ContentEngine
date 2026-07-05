from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


SAFE_ACTIONS = {
    "prepare_content_run",
    "run_prompt_only",
    "build_prompt_pack",
    "create_publishing_package",
    "request_regeneration",
    "request_geometry_regeneration",
    "import_performance_stats",
    "create_queue_item",
}

PAID_ACTIONS = {"run_real_smoke"}
PUBLISHING_ACTIONS = {"schedule_publishing_task", "publish_manual_upload"}
HUMAN_REVIEW_ACTIONS = {
    "add_product_reference",
    "add_geometry_lock",
    "human_review",
    "approve_for_publishing",
    "publishing_approval",
    "schedule_publishing_task",
    "run_real_smoke",
}


class ContentStateSnapshot(BaseModel):
    product_id: int
    sku: str
    content_run_id: int | None = None
    content_run_status: str | None = None
    has_demand: bool = False
    has_creative_spec: bool = False
    has_selected_variant: bool = False
    has_prompt_pack: bool = False
    reference_readiness: dict[str, Any] = Field(default_factory=dict)
    geometry_readiness: dict[str, Any] = Field(default_factory=dict)
    has_video_output: bool = False
    generation_report_exists: bool = False
    video_job_id: int | None = None
    video_status: str | None = None
    video_review_status: str | None = None
    human_review_required: bool = False
    publishing_readiness: dict[str, Any] = Field(default_factory=dict)
    has_publishing_package: bool = False
    publishing_package_id: int | None = None
    publishing_package_status: str | None = None
    has_publishing_task: bool = False
    publishing_task_status: str | None = None
    performance_data_status: str = "missing"
    performance_strength: str = "unknown"
    latest_metric_id: int | None = None
    identity_mismatch_detected: bool = False
    geometry_mismatch_detected: bool = False
    real_smoke_gate_ready: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)
    inspected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AutopilotDecisionResult(BaseModel):
    product_id: int
    sku: str
    content_run_id: int | None = None
    decision_type: str = "next_action"
    recommended_action: str
    confidence_score: float = 0.8
    status: str = "recommended"
    blockers: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    human_review_required: bool = False
    can_execute_safely: bool = False
    queue_type: str = "autopilot"
    priority: int = 50


class AutopilotExecutionResult(BaseModel):
    decision_id: int
    status: str
    action: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    executed: bool = False


class AutopilotRunResult(BaseModel):
    id: int
    status: str
    scope_type: str
    product_ids: list[int] = Field(default_factory=list)
    total_checked: int = 0
    total_ready: int = 0
    total_blocked: int = 0
    total_needs_human_review: int = 0
    total_actions_executed: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)


class AutopilotDashboard(BaseModel):
    products_checked: int = 0
    ready: int = 0
    blocked: int = 0
    needs_human_review: int = 0
    publishing_ready: int = 0
    top_blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    queue: list[dict[str, Any]] = Field(default_factory=list)
    human_review_queue: list[dict[str, Any]] = Field(default_factory=list)
    recent_runs: list[dict[str, Any]] = Field(default_factory=list)
