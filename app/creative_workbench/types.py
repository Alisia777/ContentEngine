from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkbenchReadiness(BaseModel):
    product_id: int
    sku: str
    product_strategy_ready: bool = False
    offer_strategy_ready: bool = False
    blogger_meaning_ready: bool = False
    ugc_script_ready: bool = False
    creative_quality_passed: bool = False
    reference_policy_passed: bool = False
    prompt_pack_ready: bool = False
    real_smoke_allowed: bool = False
    product_lock_mode: str | None = None
    reference_policy: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class PromptPreviewScene(BaseModel):
    scene_number: int | None = None
    scene_role: str | None = None
    duration_seconds: int | None = None
    scene_prompt: str
    negative_prompt: str | None = None
    product_lock_mode: str | None = None
    reference_count: int = 0
    reference_images: list[str] = Field(default_factory=list)
    identity_constraints: list[str] = Field(default_factory=list)
    geometry_constraints: dict[str, Any] = Field(default_factory=dict)
    blogger_persona: dict[str, Any] = Field(default_factory=dict)
    spoken_line: str | None = None
    caption: str | None = None


class PromptPreviewOutput(BaseModel):
    session_id: int
    prompt_pack_id: int | None = None
    product_lock_mode: str | None = None
    reference_count: int = 0
    negative_prompt: str | None = None
    identity_constraints: list[str] = Field(default_factory=list)
    geometry_constraints: dict[str, Any] = Field(default_factory=dict)
    scenes: list[PromptPreviewScene] = Field(default_factory=list)


class WorkbenchSessionOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    status: str
    product_strategy_spec_id: int | None = None
    offer_strategy_id: int | None = None
    blogger_meaning_spec_id: int | None = None
    ugc_script_id: int | None = None
    creative_quality_score_id: int | None = None
    prompt_pack_id: int | None = None
    strategy_scorecard: dict[str, Any] = Field(default_factory=dict)
    offer_logic: dict[str, Any] = Field(default_factory=dict)
    ugc_script_preview: dict[str, Any] = Field(default_factory=dict)
    scene_intent_table: list[dict[str, Any]] = Field(default_factory=list)
    creative_quality_breakdown: dict[str, Any] = Field(default_factory=dict)
    prompt_preview: dict[str, Any] = Field(default_factory=dict)
    real_smoke_readiness: WorkbenchReadiness
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class BriefPatch(BaseModel):
    buyer_situation: str | None = None
    main_objection: str | None = None
    proof_moment: str | None = None
    cta: str | None = None
    platform_angle: str | None = None
    creator_persona: str | None = None
    product_reason: str | None = None
    must_avoid: list[str] | None = None
    must_include: list[str] | None = None


class RewriteWorkflowOutput(BaseModel):
    session_id: int
    rewrite_request_id: int
    source_ugc_script_id: int
    new_ugc_script_id: int
    before_lines: list[str]
    after_lines: list[str]
    previous_score: dict[str, Any] | None = None
    new_score: dict[str, Any] | None = None
    status: str


class BriefApprovalOutput(BaseModel):
    session_id: int
    approval_id: int
    reviewer_name: str
    status: str
    notes: str | None = None
    approved_at: str | None = None
