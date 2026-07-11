from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.destination_connectors.catalog import OFFICIAL_CONNECTION_TYPES


CONNECTION_TYPES = {
    "manual",
    "csv",
    "telegram_bot",
    "instagram_stub",
    "tiktok_stub",
    *OFFICIAL_CONNECTION_TYPES,
}


class DestinationConnectionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    destination_id: int
    platform: str
    connection_type: str
    status: str
    auth_status: str
    credential_configured: bool = False
    last_checked_at: datetime | None = None
    last_sync_at: datetime | None = None
    error_message: str | None = None
    settings_json: dict[str, Any] = Field(default_factory=dict)


class DestinationConnectionReadiness(BaseModel):
    connection_id: int
    destination_id: int
    platform: str
    connection_type: str
    status: str
    auth_status: str
    credential_required: bool
    credential_configured: bool
    last_checked_at: datetime | None = None
    last_sync_at: datetime | None = None
    error_message: str | None = None
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    account_requirements: list[str] = Field(default_factory=list)


class CredentialCheckResult(BaseModel):
    status: str
    auth_status: str
    credential_required: bool
    credential_configured: bool
    message: str | None = None


class DestinationMetricSyncResult(BaseModel):
    sync_id: int
    status: str
    destination_id: int | None = None
    connection_id: int | None = None
    campaign_id: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    imported_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DestinationMetricsSummary(BaseModel):
    campaign_id: int
    metric_count: int
    total_views: int
    total_clicks: int
    total_orders: int
    total_revenue: float
    total_spend: float
    missing_metrics: list[dict[str, Any]] = Field(default_factory=list)
    by_destination: list[dict[str, Any]] = Field(default_factory=list)
    by_platform: list[dict[str, Any]] = Field(default_factory=list)
    by_sku: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)


class DestinationConnectorOverview(BaseModel):
    total_destinations: int
    connected: int
    needs_auth: int
    manual_only: int
    token_expired: int
    last_sync: datetime | None = None


class OfficialConnectorSyncResult(BaseModel):
    status: str
    organization_id: int
    destination_id: int
    connection_id: int
    platform: str
    period_start: date
    period_end: date
    requested_count: int = 0
    accepted_count: int = 0
    unchanged_count: int = 0
    quarantined_count: int = 0
    error_count: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
