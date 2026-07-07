from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ProductLockMode = Literal["reference_i2v", "packshot_overlay", "end_card_packshot", "no_product_generation"]

PRODUCT_LOCK_MODES: tuple[str, ...] = (
    "reference_i2v",
    "packshot_overlay",
    "end_card_packshot",
    "no_product_generation",
)

ONE_REFERENCE_ALLOWED_MODES: tuple[str, ...] = (
    "prompt_only",
    "end_card_packshot",
    "packshot_overlay",
    "no_product_generation",
)

STRICT_ONE_REFERENCE_BLOCKED_MODES: tuple[str, ...] = (
    "ai_generated_product_packaging_scenes",
    "strict_identity_real_smoke",
    "mass_generation_final_product_ads",
)

SCENE_ROLES: tuple[str, ...] = (
    "hook",
    "personal_context",
    "product_reason",
    "proof_demo",
    "texture_or_use_case",
    "cta",
    "end_card",
)

PACKAGING_DRIFT_NEGATIVE_TERMS: tuple[str, ...] = (
    "fake label",
    "distorted text",
    "wrong logo",
    "changed packaging",
    "invented brand text",
    "unreadable label",
    "different product",
    "warped package",
    "AI-generated packaging",
    "changed product size",
    "wrong proportions",
    "stretched/squashed product",
    "scale mismatch",
)


class ProductReferencePolicy(BaseModel):
    product_id: int
    sku: str
    provider: str = "runway"
    product_identity_strict: bool = True
    status: str
    mass_generation_safety_status: str
    approved_reference_count: int = 0
    recommended_reference_count: int = 3
    minimum_strict_reference_count: int = 2
    primary_reference_asset_id: int | None = None
    reference_asset_ids: list[int] = Field(default_factory=list)
    approved_reference_types: list[str] = Field(default_factory=list)
    missing_reference_types: list[str] = Field(default_factory=list)
    product_lock_mode: ProductLockMode = "no_product_generation"
    allowed_modes: list[str] = Field(default_factory=list)
    blocked_modes: list[str] = Field(default_factory=list)
    strict_real_generation_allowed: bool = False
    prompt_only_allowed: bool = True
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class BloggerMeaningSpecOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    demand_hypothesis_id: int | None = None
    creative_spec_id: int | None = None
    creator_persona: dict[str, Any] = Field(default_factory=dict)
    buyer_context: dict[str, Any] = Field(default_factory=dict)
    blogger_story: dict[str, Any] = Field(default_factory=dict)
    authenticity_rules: dict[str, Any] = Field(default_factory=dict)
    scene_intent: list[dict[str, Any]] = Field(default_factory=list)
    hook_options: list[dict[str, Any]] = Field(default_factory=list)
    proof_moment: dict[str, Any] = Field(default_factory=dict)
    cta: dict[str, Any] = Field(default_factory=dict)
    product_lock_rules: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class UGCAdScriptOutput(BaseModel):
    id: int
    blogger_meaning_spec_id: int
    creative_variant_id: int | None = None
    status: str
    duration_seconds: int
    voiceover: dict[str, Any] = Field(default_factory=dict)
    captions: dict[str, Any] = Field(default_factory=dict)
    scene_script: list[dict[str, Any]] = Field(default_factory=list)
