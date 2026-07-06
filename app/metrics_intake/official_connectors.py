from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.platform_matrix import PlatformMetricsMatrix


class OfficialConnectorGateway:
    def __init__(self, db: Session):
        self.db = db

    def readiness(self, destination_id: int, *, platform: str | None = None) -> dict[str, Any]:
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            return {"destination_id": destination_id, "status": "missing_destination", "ready": False, "blockers": ["destination_not_found"]}
        platform_name = PlatformMetricsMatrix.normalize_platform(platform or destination.platform)
        config = PlatformMetricsMatrix.config(platform_name)
        connections = self.db.scalars(
            select(models.DestinationConnection).where(models.DestinationConnection.destination_id == destination_id)
        ).all()
        official = [
            connection
            for connection in connections
            if connection.connection_type in config.official_connector_types or connection.connection_type == "official_api"
        ]
        if not config.official_connector_types:
            return {
                "destination_id": destination_id,
                "platform": platform_name,
                "ready": False,
                "status": "manual_or_partner_report",
                "blockers": ["platform_has_no_configured_official_connector"],
                "fallbacks": config.fallback_source_types,
            }
        if not official:
            return {
                "destination_id": destination_id,
                "platform": platform_name,
                "ready": False,
                "status": "needs_connection",
                "blockers": ["official_connection_missing"],
                "fallbacks": config.fallback_source_types,
            }
        connection = official[0]
        blockers = []
        if connection.auth_status != "token_valid":
            blockers.append("oauth_or_token_not_valid")
        if not connection.credential_ref:
            blockers.append("credential_ref_missing")
        return {
            "destination_id": destination_id,
            "platform": platform_name,
            "connection_id": connection.id,
            "connection_type": connection.connection_type,
            "ready": not blockers,
            "status": "ready" if not blockers else "blocked",
            "blockers": blockers,
            "fallbacks": config.fallback_source_types,
        }

    def sync_stub(self, destination_id: int, *, platform: str | None = None) -> dict[str, Any]:
        readiness = self.readiness(destination_id, platform=platform)
        if not readiness["ready"]:
            return {**readiness, "synced": False, "message": "Official metrics sync is gated until authorized access is ready."}
        return {**readiness, "synced": False, "message": "Official connector adapter is ready but external API calls are disabled in MVP/tests."}
