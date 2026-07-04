from __future__ import annotations

from pydantic import BaseModel, Field


class ProductAssetDescriptor(BaseModel):
    source_ref: str
    source_type: str
    asset_type: str
    filename: str | None = None
    extension: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    exists: bool = False
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AssetValidationReport(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    real_generation_allowed: bool = False
    missing_assets: list[str] = Field(default_factory=list)


class ProductAssetKitOutput(BaseModel):
    product_id: int
    sku: str
    assets: list[ProductAssetDescriptor] = Field(default_factory=list)
    required_assets: list[str] = Field(default_factory=lambda: ["packshot", "label_closeup", "lifestyle"])
    missing_assets: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_report: AssetValidationReport | None = None
    real_generation_allowed: bool = False
