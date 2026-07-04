from __future__ import annotations

from pydantic import BaseModel, Field


class FirstFrameOptionOutput(BaseModel):
    hook_text: str
    visual_concept: str
    text_overlay: str
    product_placement: str
    camera_motion: str
    composition: str
    required_assets: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    product_visible_by_second: float = 1.0
    source_flags: list[str] = Field(default_factory=list)


class CreativeVariantOutput(BaseModel):
    hook_text: str
    first_frame: FirstFrameOptionOutput
    scene_plan: list[dict]
    scene_pacing: dict
    cta_framing: str
    visual_style: str
    product_reveal_timing: float = 1.0
    asset_refs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class VariantScoreResult(BaseModel):
    score: float
    safe: bool
    dimensions: dict[str, float]
    risk_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
