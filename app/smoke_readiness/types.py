from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SmokeReadinessBlockerOutput(BaseModel):
    blocker_type: str
    severity: str = "blocker"
    message: str
    recommended_action: str


class SmokeReadinessReport(BaseModel):
    run_id: int
    status: str
    final_decision: str
    auth_mode: dict[str, Any] = Field(default_factory=dict)
    spend_gate_status: dict[str, Any] = Field(default_factory=dict)
    generation_mode: str
    runway_key_configured: bool
    runway_key_value: str = "[redacted]"
    runway_credits_confirmed: bool = False
    requested_plan_id: int | None = None
    requested_plan_exists: bool = False
    rebuilt_plan_id: int | None = None
    product_id: int | None = None
    sku: str | None = None
    one_video_render_plan_id: int | None = None
    prompt_pack_id: int | None = None
    reference_policy_status: dict[str, Any] = Field(default_factory=dict)
    scene_policy_status: dict[str, Any] = Field(default_factory=dict)
    prompt_only_status: str = "not_run"
    mvp_scorecard: dict[str, Any] = Field(default_factory=dict)
    engine_audit_latest_score: float | None = None
    engine_audit_run_id: int | None = None
    control_room_snapshot_id: int | None = None
    control_room_next_action: str | None = None
    blockers: list[SmokeReadinessBlockerOutput] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class SmokeReadinessRunOutput(BaseModel):
    id: int
    status: str
    product_id: int | None = None
    sku: str | None = None
    one_video_render_plan_id: int | None = None
    prompt_pack_id: int | None = None
    engine_audit_run_id: int | None = None
    control_room_snapshot_id: int | None = None
    blockers: list[SmokeReadinessBlockerOutput] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    report: SmokeReadinessReport
