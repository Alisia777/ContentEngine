from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SpecPromptScene(BaseModel):
    scene_number: int
    scene_role: str
    duration_seconds: int
    prompt_text: str
    negative_prompt: str
    reference_images: list[str] = Field(default_factory=list)
    first_frame_requirements: dict[str, Any] = Field(default_factory=dict)
    camera_motion: str
    composition: str
    lighting: str
    product_accuracy_rules: list[str] = Field(default_factory=list)
    product_geometry_rules: dict[str, Any] = Field(default_factory=dict)
    product_scale_rules: dict[str, Any] = Field(default_factory=dict)
    product_visibility_rules: dict[str, Any] = Field(default_factory=dict)
    caption_text: str
    voiceover_text: str
    provider_params: dict[str, Any] = Field(default_factory=dict)


class SpecPromptPack(BaseModel):
    provider: str
    creative_spec_id: int
    aspect_ratio: str
    duration_seconds: int
    scene_prompts: list[SpecPromptScene]
    provider_params: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class QualityScoreResult(BaseModel):
    score: float
    status: str
    checks: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RealSmokeRunOutput(BaseModel):
    status: str
    product_id: int
    sku: str
    creative_spec_id: int
    creative_variant_id: int
    prompt_pack_id: int
    video_job_id: int | None = None
    provider: str
    provider_job_ids: list[str] = Field(default_factory=list)
    reference_bundle_id: int | None = None
    local_output_paths: list[str] = Field(default_factory=list)
    final_video_path: str | None = None
    generation_report_path: str | None = None
    quality_review_id: int | None = None
    quality_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
