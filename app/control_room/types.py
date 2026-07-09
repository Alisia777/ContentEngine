from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ControlRoomItem(BaseModel):
    label: str
    status: str = "open"
    detail: str | None = None
    target_module: str
    target_url: str
    severity: str = "normal"
    payload: dict[str, Any] = Field(default_factory=dict)


class ControlRoomActionOutput(BaseModel):
    id: int | None = None
    action_type: str
    role: str
    target_module: str
    target_url: str
    status: str
    safe_to_execute: bool
    requires_human: bool
    requires_spend_gate: bool
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ControlRoomSnapshotOutput(BaseModel):
    id: int
    scope_type: str
    scope_id: int | None = None
    role: str
    overall_status: str
    engine_audit_run_id: int | None = None
    summary: dict[str, Any]
    scorecard: dict[str, Any]
    ready_items: list[ControlRoomItem]
    blocked_items: list[ControlRoomItem]
    review_queue: list[ControlRoomItem]
    safe_actions: list[ControlRoomActionOutput]
    gated_actions: list[ControlRoomActionOutput]
    next_actions: list[ControlRoomActionOutput]
