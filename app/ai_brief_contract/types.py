from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


NEGATIVE_PROMPT_TERMS: tuple[str, ...] = (
    "fake label",
    "distorted text",
    "changed packaging",
    "wrong logo",
    "invented brand text",
    "unreadable label",
    "different product",
    "warped package",
    "wrong proportions",
    "scale mismatch",
    "generic ad voice",
    "commercial announcer tone",
    "no personal context",
    "no proof moment",
)

REQUIRED_SCENE_TIMELINE: tuple[dict[str, Any], ...] = (
    {"role": "hook", "start": 0, "end": 2},
    {"role": "personal_context", "start": 2, "end": 5},
    {"role": "product_reason", "start": 5, "end": 8},
    {"role": "proof_demo", "start": 8, "end": 12},
    {"role": "cta", "start": 12, "end": 15},
)


class AIProductionBriefOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    status: str
    platform: str
    format: str
    one_sentence_thesis: str | None = None
    viewer_takeaway: str | None = None
    buyer_situation: str | None = None
    main_objection: str | None = None
    reason_to_believe: str | None = None
    proof_moment: str | None = None
    cta: str | None = None
    product_lock_mode: str | None = None
    reference_requirements: dict[str, Any] = Field(default_factory=dict)
    must_show: list[str] = Field(default_factory=list)
    must_say: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    scene_count: int
    duration_seconds: int
    brief: dict[str, Any] = Field(default_factory=dict)
    brief_markdown: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SceneBlueprintOutput(BaseModel):
    id: int
    ai_production_brief_id: int
    scene_order: int
    scene_role: str
    start_second: float
    end_second: float
    viewer_goal: str | None = None
    visual_action: str | None = None
    spoken_line: str | None = None
    onscreen_text: str | None = None
    caption_text: str | None = None
    product_visibility: str | None = None
    camera_framing: str | None = None
    broll_notes: str | None = None
    transition_notes: str | None = None
    must_show: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)


class DirectorPromptPackOutput(BaseModel):
    id: int
    ai_production_brief_id: int
    prompt_pack_id: int | None = None
    status: str
    system_instruction: str | None = None
    provider_prompt: dict[str, Any] = Field(default_factory=dict)
    negative_prompt: str | None = None
    asset_instructions: dict[str, Any] = Field(default_factory=dict)
    overlay_instructions: dict[str, Any] = Field(default_factory=dict)
    end_card_instructions: dict[str, Any] = Field(default_factory=dict)
    quality_checklist: list[str] = Field(default_factory=list)


class BriefQualityCheckOutput(BaseModel):
    id: int
    ai_production_brief_id: int
    status: str
    score: float
    missing_fields: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    failure_risks: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
