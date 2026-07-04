from typing import Any

from pydantic import BaseModel, Field


class ProductFact(BaseModel):
    fact: str
    source: str


class AllowedClaim(BaseModel):
    claim: str
    source_type: str
    source_key: str


class ContentLearning(BaseModel):
    platform: str
    creative_angle: str | None = None
    hook_text: str | None = None
    ctr: float | None = None
    retention_rate: float | None = None
    orders: int | None = None


class CreativeIntelligencePack(BaseModel):
    sku: str
    product_id: int
    product_title: str
    product_facts: list[ProductFact] = Field(default_factory=list)
    allowed_claims: list[AllowedClaim] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    performance_flags: list[str] = Field(default_factory=list)
    buyer_objections: list[str] = Field(default_factory=list)
    buyer_language: list[str] = Field(default_factory=list)
    content_learnings: list[ContentLearning] = Field(default_factory=list)
    market_risks: list[str] = Field(default_factory=list)
    stock_risk: str | None = None
    price_positioning: str | None = None
    recommended_objective: str
    recommended_creative_angles: list[str] = Field(default_factory=list)
    recommended_video_formats: list[str] = Field(default_factory=list)
    source_map: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    reasoning_summary: str


class ScriptBriefOutput(BaseModel):
    sku: str
    product_title: str
    objective: str
    creative_angle: str
    target_audience: str | None = None
    reasoning_summary: str
    allowed_claims: list[AllowedClaim] = Field(default_factory=list)
    buyer_objections: list[str] = Field(default_factory=list)
    buyer_language: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    visual_direction: list[str] = Field(default_factory=list)
    scene_count: int = 4
    duration_seconds: int = 15
    aspect_ratio: str = "9:16"
    missing_data: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)


class GeneratedSceneOutput(BaseModel):
    scene_number: int
    time_start: float
    time_end: float
    visual_description: str
    voiceover: str
    caption: str
    claim_refs: list[str] = Field(default_factory=list)
    video_prompt: str
    negative_prompt: str


class GeneratedScriptOutput(BaseModel):
    creative_angle: str
    hook: str
    key_message: str
    scenes: list[GeneratedSceneOutput]
    final_cta: str
    compliance_notes: list[str] = Field(default_factory=list)
    missing_data_notes: list[str] = Field(default_factory=list)


class PromptSceneOutput(BaseModel):
    scene_number: int
    duration_seconds: int
    prompt_text: str
    negative_prompt: str
    reference_images: list[str] = Field(default_factory=list)
    camera_motion: str = "slow product-focused movement"
    style: str = "realistic vertical marketplace product video"
    safety_constraints: list[str] = Field(default_factory=list)


class PromptPackOutput(BaseModel):
    provider: str
    aspect_ratio: str
    duration_seconds: int
    scene_prompts: list[PromptSceneOutput]


class ProviderVideoJob(BaseModel):
    provider: str
    provider_job_id: str
    status: str
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ProviderVideoStatus(BaseModel):
    provider_job_id: str
    status: str
    raw_response: dict[str, Any] = Field(default_factory=dict)

