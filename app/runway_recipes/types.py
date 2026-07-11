from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RecipeImageInput(BaseModel):
    uri: str


class ProductUGCRecipeRequest(BaseModel):
    """Wire contract for POST /v1/recipes/product_ugc."""

    model_config = ConfigDict(populate_by_name=True)

    version: str = "2026-06"
    character_image: RecipeImageInput = Field(serialization_alias="characterImage")
    product_image: RecipeImageInput = Field(serialization_alias="productImage")
    product_info: str = Field(serialization_alias="productInfo", max_length=2500)
    user_concept: str = Field(serialization_alias="userConcept", max_length=3500)
    duration: int = Field(default=15, ge=4, le=15)
    ratio: Literal["720:1280", "1080:1920"] = "720:1280"
    audio: bool = True


class RecipeGate(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class ProductUGCRecipeDraftOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    variant_key: str | None = None
    status: str
    recipe_version: str
    platform: str
    language: str
    character_image_filename: str
    likeness_consent: bool
    exact_variant_confirmed: bool
    product_asset_ids: list[int] = Field(default_factory=list)
    primary_product_asset_id: int | None = None
    product_info: str
    user_concept: str
    creative_inputs: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: int
    ratio: str
    audio_enabled: bool
    estimated_credits: int
    payload_preview: dict[str, Any] = Field(default_factory=dict)
    gates: list[RecipeGate] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider_task_id: str | None = None
    provider_status: str | None = None
    local_output_paths: list[str] = Field(default_factory=list)
    generation_report_path: str | None = None
    human_review_status: str = "not_generated"
    human_review_notes: str | None = None
    publishing_readiness: str = "blocked"


class ProductUGCRecipeRunOutput(BaseModel):
    draft_id: int
    status: str
    provider_task_id: str | None = None
    provider_status: str | None = None
    local_output_paths: list[str] = Field(default_factory=list)
    generation_report_path: str | None = None
    human_review_status: str
    publishing_readiness: str
