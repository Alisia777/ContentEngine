from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MVPAction(BaseModel):
    action_type: str
    label: str
    url: str
    status: str = "available"
    detail: str | None = None
    safe_to_execute: bool = True
    requires_human: bool = False
    requires_spend_gate: bool = False


class MVPBlocker(BaseModel):
    blocker_type: str
    label: str
    detail: str
    severity: str = "blocker"
    next_action: str | None = None


class MVPModuleLink(BaseModel):
    key: str
    label: str
    url: str
    status: str
    summary: str
    internal_route: str | None = None
    number: int = 0
    status_label: str = "Доступно"
    cta_label: str = "Открыть"
    metric_value: str | int | float = 0
    metric_label: str = ""
    note: str | None = None


class MVPWorkspaceSnapshotOutput(BaseModel):
    id: int
    role: str
    status: str
    current_step: str
    primary_action: MVPAction
    secondary_actions: list[MVPAction] = Field(default_factory=list)
    blockers: list[MVPBlocker] = Field(default_factory=list)
    module_links: list[MVPModuleLink] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    control_room_snapshot_id: int | None = None
    smoke_readiness_run_id: int | None = None


class MVPLaunchStep(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class MVPLaunchRunOutput(BaseModel):
    id: int
    product_id: int | None = None
    sku: str | None = None
    status: str
    current_step: str
    completed_steps: list[str] = Field(default_factory=list)
    blockers: list[MVPBlocker] = Field(default_factory=list)
    next_action: MVPAction
    steps: list[MVPLaunchStep] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    one_video_render_plan_id: int | None = None
    smoke_readiness_run_id: int | None = None
    one_video_render_result_id: int | None = None
    output_acceptance_id: int | None = None
