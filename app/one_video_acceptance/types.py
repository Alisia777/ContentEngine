from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProductScenePolicyOutput(BaseModel):
    product_id: int
    sku: str
    provider: str = "runway"
    wrapper_reference_count: int = 0
    edible_reference_count: int = 0
    style_reference_count: int = 0
    lifestyle_reference_count: int = 0
    has_bitten_bar_reference: bool = False
    has_bar_in_hand_reference: bool = False
    label_accuracy_required: bool = True
    wrapper_scene_allowed: bool = False
    wrapper_closeup_allowed: bool = False
    unwrapped_product_allowed: bool = False
    bite_scene_allowed: bool = False
    texture_macro_allowed: bool = False
    packshot_overlay_required: bool = True
    end_card_required: bool = True
    edible_kit_ready: bool = False
    approved_wrapper_asset_ids: list[int] = Field(default_factory=list)
    approved_edible_asset_ids: list[int] = Field(default_factory=list)
    approved_style_asset_ids: list[int] = Field(default_factory=list)
    approved_lifestyle_asset_ids: list[int] = Field(default_factory=list)
    blocked_scene_types: list[str] = Field(default_factory=list)
    allowed_scene_types: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    reference_readiness: dict[str, Any] = Field(default_factory=dict)
    reference_policy: dict[str, Any] = Field(default_factory=dict)


class OneVideoScene(BaseModel):
    scene_number: int
    role: str
    starts_at: int
    duration_seconds: int
    spoken_line: str
    caption: str
    visual: str
    product_visibility: str
    camera_motion: str
    safety_constraints: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    provider_prompt_text: str | None = None
    negative_prompt: str | None = None


class OneVideoRenderPlanOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    platform: str
    aspect_ratio: str
    duration_seconds: int
    provider: str
    status: str
    creative_spec_id: int | None = None
    creative_variant_id: int | None = None
    ai_production_brief_id: int | None = None
    director_prompt_pack_id: int | None = None
    prompt_pack_id: int | None = None
    video_generation_variant_id: int | None = None
    product_scene_policy: ProductScenePolicyOutput
    scene_plan: list[OneVideoScene] = Field(default_factory=list)
    prompt_preview: dict[str, Any] = Field(default_factory=dict)
    negative_prompt: str | None = None
    acceptance_checklist: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OneVideoRenderResultOutput(BaseModel):
    id: int
    plan_id: int
    product_id: int
    creative_variant_id: int | None = None
    video_generation_variant_id: int | None = None
    prompt_pack_id: int | None = None
    video_job_id: int | None = None
    output_acceptance_id: int | None = None
    provider: str
    status: str
    max_scenes: int
    provider_job_ids: list[str] = Field(default_factory=list)
    local_output_paths: list[str] = Field(default_factory=list)
    final_video_path: str | None = None
    generation_report_path: str | None = None
    human_review_status: str
    human_review_notes: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
