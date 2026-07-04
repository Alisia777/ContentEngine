from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.intelligence.types import AllowedClaim


class DemandSignalSet(BaseModel):
    product_id: int
    sku: str
    product_title: str
    performance_flags: list[str] = Field(default_factory=list)
    market_risks: list[str] = Field(default_factory=list)
    stock_risk: str | None = None
    price_positioning: str | None = None
    buyer_objections: list[str] = Field(default_factory=list)
    buyer_language: list[str] = Field(default_factory=list)
    allowed_claims: list[AllowedClaim] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_map: dict[str, Any] = Field(default_factory=dict)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)

    @property
    def flags(self) -> list[str]:
        values = list(self.performance_flags)
        values.extend(self.market_risks)
        if self.stock_risk and "stock_risk" not in values:
            values.append("stock_risk")
        if self.is_weak_data and "no_strong_data" not in values:
            values.append("no_strong_data")
        return list(dict.fromkeys(values))

    @property
    def is_weak_data(self) -> bool:
        return "no marketplace performance data" in self.missing_data and "no recent review insights" in self.missing_data


class DemandRuleRecommendation(BaseModel):
    rule_key: str
    need_type: str
    buyer_need: str
    trigger_situation: str
    pain_point: str
    default_objection: str
    recommended_hook_types: list[str]
    recommended_first_frame: str
    creative_objective: str
    creative_angle: str
    cta_tone: str = "clear"


class DemandHypothesis(BaseModel):
    product_id: int
    sku: str
    product_title: str
    need_type: str
    buyer_need: str
    trigger_situation: str
    pain_point: str
    objection: str
    safe_promise: str
    unsafe_promises_blocked: list[str] = Field(default_factory=list)
    proof_required: list[str] = Field(default_factory=list)
    recommended_hook_types: list[str] = Field(default_factory=list)
    recommended_first_frame: str
    source_refs: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    performance_flags: list[str] = Field(default_factory=list)
    market_risks: list[str] = Field(default_factory=list)
    stock_risk: str | None = None
    buyer_language: list[str] = Field(default_factory=list)
    validation_status: str = "pending"
    real_video_eligible: bool = False
    reasoning: str
    source_map: dict[str, Any] = Field(default_factory=dict)


class DemandValidationReport(BaseModel):
    status: str
    valid: bool
    real_video_eligible: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    blocked_promises: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
