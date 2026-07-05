from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.creative.product_geometry import (
    default_product_geometry_rules,
    default_product_scale_rules,
    default_product_visibility_rules,
)
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


class ProductGeometrySpec(BaseModel):
    product_id: int
    sku: str
    primary_reference_asset_id: int | None = None
    geometry_lock_enabled: bool = True
    preserve_silhouette: bool = True
    preserve_height_width_ratio: bool = True
    preserve_cap_size_and_position: bool = True
    preserve_label_size_and_position: bool = True
    preserve_bottle_body_shape: bool = True
    scene_scale_rules_json: dict[str, Any] = Field(default_factory=default_product_scale_rules)
    forbidden_geometry_changes_json: list[str] = Field(
        default_factory=lambda: [
            "changed product size",
            "wrong proportions",
            "stretched bottle",
            "squashed bottle",
            "oversized product",
            "miniature product",
            "changed silhouette",
            "label area changed",
            "product scale mismatch",
        ]
    )
    human_geometry_notes: str | None = None


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
    product_geometry_spec: ProductGeometrySpec
    product_geometry_rules: dict[str, Any] = Field(default_factory=default_product_geometry_rules)
    product_scale_rules: dict[str, Any] = Field(default_factory=default_product_scale_rules)
    product_visibility_rules: dict[str, Any] = Field(default_factory=default_product_visibility_rules)
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
