from __future__ import annotations

from datetime import date
from typing import Any

from app import models


class OfficialProviderPendingConnector:
    auth_status = "needs_app_review"

    def collect_metrics(self, connection: models.DestinationConnection, period_start: date | None, period_end: date | None) -> list[dict[str, Any]]:
        return list((connection.settings_json or {}).get("mock_metrics") or [])

    def readiness_warning(self) -> dict[str, Any]:
        return {"warning": "official_provider_pending", "manual_csv_metrics_available": True}


class InstagramConnectorStub(OfficialProviderPendingConnector):
    platform = "Instagram"


class TikTokConnectorStub(OfficialProviderPendingConnector):
    platform = "TikTok"
