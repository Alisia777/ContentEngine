from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.intelligence.types import AllowedClaim


class HookCandidate(BaseModel):
    hook_type: str
    hook_text: str
    viewer_promise: str
    rationale: str
    source_flags: list[str] = Field(default_factory=list)


class FirstFrameSpec(BaseModel):
    visual_hook: str
    text_overlay: str
    product_visible_by_second: float = 1.5
    product_display: str
    composition: str
    viewer_promise: str


class CreativeScene(BaseModel):
    scene_number: int
    role: str
    starts_at: int
    duration_seconds: int
    visual: str
    caption: str
    voiceover: str
    claim_refs: list[str] = Field(default_factory=list)
    product_display: str
    camera_motion: str
    composition: str
    lighting: str
    emotion: str
    cta: str | None = None

    @property
    def ends_at(self) -> int:
        return self.starts_at + self.duration_seconds


class QualityRubricItem(BaseModel):
    key: str
    label: str
    check_type: str = "metadata"
    weight: int = 1


class QualityRubric(BaseModel):
    items: list[QualityRubricItem]
    notes: list[str] = Field(default_factory=list)


class CreativeSpecValidationReport(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CreativeSpec(BaseModel):
    product_id: int
    sku: str
    product_title: str
    platform: str
    format: str
    aspect_ratio: str
    duration_seconds: int
    creative_objective: str
    creative_angle: str
    hook_candidates: list[HookCandidate]
    selected_hook: HookCandidate
    hook_type: str
    hook_text: str
    viewer_promise: str
    first_frame_spec: FirstFrameSpec
    scene_plan: list[CreativeScene]
    captions: list[str]
    voiceover: list[str]
    visual_style: str
    product_display_rules: list[str]
    must_include: list[str]
    must_avoid: list[str]
    allowed_claims: list[AllowedClaim] = Field(default_factory=list)
    allowed_claim_refs: list[str] = Field(default_factory=list)
    reference_images: list[str] = Field(default_factory=list)
    source_map: dict[str, Any] = Field(default_factory=dict)
    quality_rubric: QualityRubric
    warnings: list[str] = Field(default_factory=list)
    validation_report: CreativeSpecValidationReport | None = None
    cta: str
