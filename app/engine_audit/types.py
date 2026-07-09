from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EngineAuditDimension(BaseModel):
    key: str
    label: str
    score: float
    status: str
    reasons: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    next_action: str
    module_links: list[dict[str, str]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class EngineAuditOutput(BaseModel):
    id: int
    scope_type: str
    scope_id: int | None = None
    status: str
    overall_score: float
    total_score: float
    score_scale: str = "1_to_10"
    dimensions: list[EngineAuditDimension]
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    road_to_10: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    report_path: str | None = None
