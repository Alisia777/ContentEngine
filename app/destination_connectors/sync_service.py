from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.connection_registry import ConnectionRegistry
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.metrics_collector import DestinationMetricsCollector
from app.destination_connectors.provider_stubs import InstagramConnectorStub, TikTokConnectorStub
from app.destination_connectors.telegram_connector import TelegramConnector
from app.destination_connectors.types import DestinationMetricSyncResult
from app.destination_connectors.youtube_connector import YouTubeAnalyticsConnector


class DestinationConnectorSyncService:
    def __init__(self, db: Session):
        self.db = db

    def sync(self, connection_id: int, *, period_start: date | None = None, period_end: date | None = None) -> DestinationMetricSyncResult:
        connection = ConnectionRegistry(self.db).get(connection_id)
        rows = self._collect(connection, period_start, period_end)
        if rows:
            return DestinationMetricsCollector(self.db).import_rows(
                rows,
                connection=connection,
                period_start=period_start,
                period_end=period_end,
                source=connection.connection_type,
            )
        sync = models.DestinationMetricSync(
            destination_id=connection.destination_id,
            connection_id=connection.id,
            status="partial",
            period_start=period_start,
            period_end=period_end,
            imported_count=0,
            skipped_count=0,
            error_count=0,
            warnings_json=["no_metrics_returned_use_manual_or_csv_import"],
            errors_json=[],
        )
        connection.last_sync_at = models.utcnow()
        self.db.add(sync)
        self.db.commit()
        self.db.refresh(sync)
        return DestinationMetricSyncResult(
            sync_id=sync.id,
            status=sync.status,
            destination_id=sync.destination_id,
            connection_id=sync.connection_id,
            campaign_id=sync.campaign_id,
            period_start=sync.period_start,
            period_end=sync.period_end,
            imported_count=sync.imported_count,
            skipped_count=sync.skipped_count,
            error_count=sync.error_count,
            warnings=sync.warnings_json,
            errors=sync.errors_json,
        )

    def _collect(self, connection: models.DestinationConnection, period_start: date | None, period_end: date | None) -> list[dict[str, Any]]:
        if connection.connection_type in {"manual", "csv"}:
            return list((connection.settings_json or {}).get("mock_metrics") or [])
        if connection.connection_type == "telegram_bot":
            check = TelegramConnector().check(connection)
            if check.status != "connected":
                raise DestinationConnectorDataError(check.message or "Telegram connection is not ready.")
            return TelegramConnector().collect_metrics(connection, period_start, period_end)
        if connection.connection_type == "youtube_oauth":
            check = YouTubeAnalyticsConnector().check(connection)
            if check.status != "connected":
                raise DestinationConnectorDataError(check.message or "YouTube connection is not ready.")
            return YouTubeAnalyticsConnector().collect_metrics(connection, period_start, period_end)
        if connection.connection_type == "instagram_stub":
            return InstagramConnectorStub().collect_metrics(connection, period_start, period_end)
        if connection.connection_type == "tiktok_stub":
            return TikTokConnectorStub().collect_metrics(connection, period_start, period_end)
        raise DestinationConnectorDataError(f"Unsupported connection type: {connection.connection_type}")
