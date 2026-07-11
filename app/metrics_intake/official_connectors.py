from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.catalog import (
    OFFICIAL_CONNECTOR_CATALOG,
    connector_definition,
    connector_definitions_for_platform,
)
from app.destination_connectors.credential_status import CredentialResolver, EnvironmentCredentialResolver
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.instagram_connector import InstagramInsightsConnector
from app.destination_connectors.tiktok_connector import TikTokDisplayConnector
from app.destination_connectors.youtube_connector import YouTubeAnalyticsConnector
from app.metrics_intake.platform_matrix import PlatformMetricsMatrix


IMPLEMENTED_OFFICIAL_CONNECTORS: dict[str, set[str]] = {}
for _definition in OFFICIAL_CONNECTOR_CATALOG.values():
    IMPLEMENTED_OFFICIAL_CONNECTORS.setdefault(_definition.platform, set()).add(
        _definition.connection_type
    )


class OfficialConnectorGateway:
    """Fail-closed, organization-scoped readiness for implemented adapters only."""

    def __init__(
        self,
        db: Session,
        *,
        credential_resolver: CredentialResolver | None = None,
        youtube_connector: YouTubeAnalyticsConnector | None = None,
        tiktok_connector: TikTokDisplayConnector | None = None,
        instagram_connector: InstagramInsightsConnector | None = None,
    ):
        self.db = db
        self.credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self.youtube_connector = youtube_connector or YouTubeAnalyticsConnector(
            credential_resolver=self.credential_resolver
        )
        self.tiktok_connector = tiktok_connector or TikTokDisplayConnector(
            credential_resolver=self.credential_resolver
        )
        self.instagram_connector = instagram_connector or InstagramInsightsConnector(
            credential_resolver=self.credential_resolver
        )
        self.connectors: dict[str, Any] = {
            "youtube_oauth": self.youtube_connector,
            "tiktok_oauth": self.tiktok_connector,
            "instagram_oauth": self.instagram_connector,
        }

    @staticmethod
    def catalog() -> list[dict[str, Any]]:
        return [
            definition.public_metadata()
            for definition in OFFICIAL_CONNECTOR_CATALOG.values()
        ]

    def readiness(
        self,
        destination_id: int,
        *,
        organization_id: int | None = None,
        platform: str | None = None,
    ) -> dict[str, Any]:
        if isinstance(organization_id, bool) or not isinstance(organization_id, int) or organization_id <= 0:
            return {
                "destination_id": destination_id,
                "ready": False,
                "can_attempt_sync": False,
                "status": "organization_scope_required",
                "blockers": ["organization_id_required"],
            }
        destination = self.db.scalar(
            select(models.PublishingDestination).where(
                models.PublishingDestination.id == destination_id,
                models.PublishingDestination.organization_id == organization_id,
            )
        )
        if destination is None:
            return {
                "destination_id": destination_id,
                "ready": False,
                "can_attempt_sync": False,
                "status": "missing_destination",
                "blockers": ["destination_not_found_in_organization"],
            }

        destination_platform = PlatformMetricsMatrix.normalize_platform(destination.platform)
        platform_name = PlatformMetricsMatrix.normalize_platform(platform or destination.platform)
        config = PlatformMetricsMatrix.config(platform_name)
        public_metadata = self._platform_metadata(platform_name)
        if platform_name != destination_platform:
            return {
                "destination_id": destination_id,
                "platform": platform_name,
                "ready": False,
                "can_attempt_sync": False,
                "status": "blocked",
                "blockers": ["platform_destination_mismatch"],
                "fallbacks": config.fallback_source_types,
                **public_metadata,
            }

        supported_types = IMPLEMENTED_OFFICIAL_CONNECTORS.get(platform_name, set())
        if not supported_types:
            return {
                "destination_id": destination_id,
                "platform": platform_name,
                "ready": False,
                "can_attempt_sync": False,
                "status": "manual_or_csv_only",
                "blockers": ["official_adapter_not_implemented"],
                "fallbacks": config.fallback_source_types,
                **public_metadata,
            }

        connections = list(
            self.db.scalars(
                select(models.DestinationConnection)
                .join(
                    models.PublishingDestination,
                    models.DestinationConnection.destination_id == models.PublishingDestination.id,
                )
                .where(
                    models.DestinationConnection.destination_id == destination_id,
                    models.PublishingDestination.organization_id == organization_id,
                    models.DestinationConnection.connection_type.in_(supported_types),
                )
                .order_by(models.DestinationConnection.id)
            ).all()
        )
        if len(connections) != 1:
            return {
                "destination_id": destination_id,
                "platform": platform_name,
                "ready": False,
                "can_attempt_sync": False,
                "status": "needs_connection" if not connections else "blocked",
                "blockers": [
                    "official_connection_missing" if not connections else "ambiguous_official_connections"
                ],
                "fallbacks": config.fallback_source_types,
                **public_metadata,
            }

        connection = connections[0]
        definition = connector_definition(connection.connection_type)
        connector = self.connectors.get(connection.connection_type)
        blockers: list[str] = []
        if definition is None or connector is None or definition.platform != platform_name:
            blockers.append("official_connector_catalog_mismatch")
        try:
            if connector is not None:
                connector.validate_configuration(
                    connection,
                    organization_id=organization_id,
                )
        except DestinationConnectorDataError as exc:
            raw_code = str(exc).strip().lower()
            blockers.append(
                raw_code
                if len(raw_code) <= 160
                and re.fullmatch(r"[a-z0-9_]+", raw_code)
                and raw_code.startswith(
                    (f"{platform_name}_", "destination_", "organization_", "publishing_task_")
                )
                else f"{platform_name}_connector_configuration_rejected"
            )
        verified = connection.status == "connected" and connection.auth_status == "oauth_verified"
        can_attempt_sync = not blockers
        credential_reference_configured = bool(connection.credential_ref)
        try:
            credential_available = bool(
                connection.credential_ref
                and self.credential_resolver.resolve(connection.credential_ref)
            )
        except Exception:
            credential_available = False
        if can_attempt_sync and not verified:
            blockers.append("credential_not_verified_by_official_api")
        return {
            "destination_id": destination_id,
            "platform": platform_name,
            "connection_id": connection.id,
            "connection_type": connection.connection_type,
            "credential_configured": credential_available,
            "credential_reference_status": (
                "available"
                if credential_available
                else "configured_but_unavailable"
                if credential_reference_configured
                else "missing"
            ),
            "credential_reference_configured": credential_reference_configured,
            "credential_available": credential_available,
            "last_checked_at": (
                connection.last_checked_at.isoformat() if connection.last_checked_at else None
            ),
            "last_sync_at": (
                connection.last_sync_at.isoformat() if connection.last_sync_at else None
            ),
            "ready": can_attempt_sync and verified,
            "can_attempt_sync": can_attempt_sync,
            "status": "ready" if can_attempt_sync and verified else "needs_verification" if can_attempt_sync else "blocked",
            "blockers": blockers,
            "fallbacks": config.fallback_source_types,
            **public_metadata,
        }

    @staticmethod
    def _platform_metadata(platform: str) -> dict[str, Any]:
        definitions = connector_definitions_for_platform(platform)
        if len(definitions) != 1:
            return {
                "required_scopes": [],
                "required_permissions": [],
                "account_requirements": [],
            }
        definition = definitions[0]
        return {
            "api_product": definition.api_product,
            "required_scopes": list(definition.required_scopes),
            "required_permissions": list(definition.required_permissions),
            "account_requirements": list(definition.account_requirements),
            "target_map_key": definition.target_map_key,
            "max_targets_per_request": definition.max_targets_per_request,
            "authorization_verification": "successful_official_api_call_required",
        }

    def sync_stub(
        self,
        destination_id: int,
        *,
        organization_id: int | None = None,
        platform: str | None = None,
    ) -> dict[str, Any]:
        readiness = self.readiness(
            destination_id,
            organization_id=organization_id,
            platform=platform,
        )
        return {
            **readiness,
            "synced": False,
            "message": (
                "sync_stub is intentionally disabled; use DestinationConnectorSyncService "
                "with organization, actor, period, observed_at, and retry-safe sync_key."
            ),
        }
