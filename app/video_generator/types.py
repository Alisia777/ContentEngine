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
