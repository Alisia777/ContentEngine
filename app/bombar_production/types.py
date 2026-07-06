from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.factory_os.types import FactoryAcceptanceReport


class BombarMatrixRowValidation(BaseModel):
    row_number: int
    sku: str | None = None
    product_name: str | None = None
    has_photo: bool = False
    has_price: bool = False
    has_stock: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    normalized: dict[str, Any] = Field(default_factory=dict)
    status: str = "valid"


class BombarMatrixValidationResult(BaseModel):
    source_file: str
    file_type: str
    required_headers: list[str] = Field(default_factory=list)
    supported_headers: list[str] = Field(default_factory=list)
    observed_headers: list[str] = Field(default_factory=list)
    unsupported_headers: list[str] = Field(default_factory=list)
    row_count: int = 0
    valid_row_count: int = 0
    blocked_row_count: int = 0
    missing_required_count: int = 0
    duplicate_sku_count: int = 0
    missing_photo_count: int = 0
    missing_price_count: int = 0
    missing_stock_count: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rows: list[BombarMatrixRowValidation] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BombarSkuReadiness(BaseModel):
    sku: str
    product_name: str | None = None
    product_id: int | None = None
    status: str = "blocked"
    has_photo: bool = False
    has_reference: bool = False
    has_price: bool = False
    has_stock: bool = False
    content_run_count: int = 0
    prompt_pack_count: int = 0
    approved_package_count: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)


class BombarProductionDryRunResult(BaseModel):
    campaign_id: int
    import_id: int | None = None
    status: str = "production_dry_run_ready"
    imported_sku_count: int = 0
    ready_sku_count: int = 0
    blocked_sku_count: int = 0
    prompt_pack_count: int = 0
    missing_references_count: int = 0
    missing_photo_count: int = 0
    missing_price_count: int = 0
    missing_stock_count: int = 0
    approved_package_count: int = 0
    distribution_blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    report_paths: dict[str, str] = Field(default_factory=dict)
    paid_calls_made: int = 0
    safe_mode: dict[str, Any] = Field(default_factory=dict)
    blockers_by_sku: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    sku_readiness: list[BombarSkuReadiness] = Field(default_factory=list)
    validation: BombarMatrixValidationResult | None = None
    factory_steps: list[dict[str, Any]] = Field(default_factory=list)
    factory_acceptance_report: FactoryAcceptanceReport | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
