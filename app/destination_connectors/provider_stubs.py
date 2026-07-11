from __future__ import annotations

from datetime import date
from typing import Any

from app import models
from app.destination_connectors.errors import DestinationConnectorDataError


class OfficialProviderPendingConnector:
    auth_status = "official_adapter_unavailable"

    def collect_metrics(self, connection: models.DestinationConnection, period_start: date | None, period_end: date | None) -> list[dict[str, Any]]:
        raise DestinationConnectorDataError(
            "Official provider adapter is unavailable; use explicit manual or CSV import."
        )

    def readiness_warning(self) -> dict[str, Any]:
        return {
            "blocker": "official_provider_adapter_unavailable",
            "manual_csv_metrics_available": True,
        }


class InstagramConnectorStub(OfficialProviderPendingConnector):
    platform = "Instagram"


class TikTokConnectorStub(OfficialProviderPendingConnector):
    platform = "TikTok"
