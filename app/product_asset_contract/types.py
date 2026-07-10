from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssetClassification(BaseModel):
    asset_id: int
    contract_type: str
    family: str
    eligible: bool
    variant_key: str | None = None
    expected_variant_key: str | None = None
    variant_status: str = "not_applicable"
    evidence: list[str] = Field(default_factory=list)


class ScenePermissionOutput(BaseModel):
    product_profile: str
    current_tier: str
    interaction_mode: str = "use_case"
    wrapper_scene_allowed: bool = False
    wrapper_closeup_allowed: bool = False
    opening_scene_allowed: bool = False
    unwrapped_product_allowed: bool = False
    cutaway_proof_allowed: bool = False
    bite_scene_allowed: bool = False
    near_mouth_allowed: bool = False
    texture_macro_allowed: bool = False
    use_case_scene_allowed: bool = False
    interaction_scene_allowed: bool = False
    application_scene_allowed: bool = False
    try_on_scene_allowed: bool = False
    demonstration_scene_allowed: bool = False
    tasting_scene_allowed: bool = False
    packshot_overlay_required: bool = True
    end_card_required: bool = True
    provider_generated_packaging_allowed: bool = False
    provider_generated_product_allowed: bool = False
    product_compositor_ready: bool = False
    compositor_mode: str = "blocked"
    allowed_scenes: list[str] = Field(default_factory=list)
    blocked_scenes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ProductAssetTierOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    variant_key: str | None = None
    product_profile: str
    current_tier: str
    wrapper_refs_count: int = 0
    edible_refs_count: int = 0
    style_refs_count: int = 0
    lifestyle_refs_count: int = 0
    identity_refs_count: int = 0
    use_case_refs_count: int = 0
    classified_assets: list[AssetClassification] = Field(default_factory=list)
    variant_mismatch_asset_ids: list[int] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    allowed_scenes: list[str] = Field(default_factory=list)
    blocked_scenes: list[str] = Field(default_factory=list)
    permissions: ScenePermissionOutput
    blockers: list[str] = Field(default_factory=list)


class ProductAssetRequirementOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    variant_key: str | None = None
    product_profile: str
    required_tier: str
    purpose: str
    required_asset_types: list[str] = Field(default_factory=list)
    missing_asset_types: list[str] = Field(default_factory=list)
    status: str
    current_tier: str
    end_card_required: bool = False
    human_review_required: bool = True
    permission: dict[str, Any] = Field(default_factory=dict)
