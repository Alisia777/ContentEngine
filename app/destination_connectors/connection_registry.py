from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.catalog import connector_definition
from app.destination_connectors.credential_status import (
    CredentialStatusService,
    public_settings,
    sanitize_payload,
    validate_credential_ref,
    validate_non_secret_settings,
)
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.types import (
    CONNECTION_TYPES,
    DestinationConnectionReadiness,
    DestinationConnectionView,
    DestinationConnectorOverview,
)


class ConnectionRegistry:
    def __init__(self, db: Session):
        self.db = db
        self.credentials = CredentialStatusService()

    def create(
        self,
        destination_id: int,
        connection_type: str,
        *,
        credential_ref: str | None = None,
        settings_json: dict[str, Any] | None = None,
    ) -> models.DestinationConnection:
        destination = self._destination(destination_id)
        connection_type = self._connection_type(connection_type)
        safe_ref = validate_credential_ref(credential_ref)
        status, auth_status = self._initial_status(connection_type, safe_ref)
        connection = models.DestinationConnection(
            destination_id=destination.id,
            platform=destination.platform,
            connection_type=connection_type,
            status=status,
            auth_status=auth_status,
            credential_ref=safe_ref,
            settings_json=validate_non_secret_settings(settings_json),
        )
        self.db.add(connection)
        self.db.flush()
        self._audit(
            destination.id,
            connection.id,
            "connection_created",
            connection.status,
            "Destination connection created.",
            {"connection_type": connection_type, "credential_configured": self.credentials.is_configured(safe_ref)},
        )
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def list(self) -> list[models.DestinationConnection]:
        return self.db.scalars(select(models.DestinationConnection).order_by(models.DestinationConnection.id)).all()

    def list_for_destination(self, destination_id: int) -> list[models.DestinationConnection]:
        return self.db.scalars(
            select(models.DestinationConnection)
            .where(models.DestinationConnection.destination_id == destination_id)
            .order_by(models.DestinationConnection.id)
        ).all()

    def get(self, connection_id: int) -> models.DestinationConnection:
        connection = self.db.get(models.DestinationConnection, connection_id)
        if not connection:
            raise DestinationConnectorDataError(f"DestinationConnection {connection_id} not found.")
        return connection

    def update(self, connection_id: int, **values: Any) -> models.DestinationConnection:
        connection = self.get(connection_id)
        if "connection_type" in values and values["connection_type"]:
            values["connection_type"] = self._connection_type(values["connection_type"])
        if "credential_ref" in values:
            values["credential_ref"] = validate_credential_ref(values["credential_ref"])
        if "settings_json" in values and values["settings_json"] is None:
            values["settings_json"] = {}
        if "settings_json" in values:
            values["settings_json"] = validate_non_secret_settings(values["settings_json"])
        for key, value in values.items():
            if value is not None and hasattr(connection, key):
                setattr(connection, key, value)
        self._audit(
            connection.destination_id,
            connection.id,
            "connection_updated",
            connection.status,
            "Destination connection updated.",
            {"updated_fields": sorted(values), "credential_configured": self.credentials.is_configured(connection.credential_ref)},
        )
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def check(self, connection_id: int) -> DestinationConnectionReadiness:
        connection = self.get(connection_id)
        result = self.credentials.check(connection)
        connection.status = result.status
        connection.auth_status = result.auth_status
        connection.last_checked_at = datetime.now(UTC).replace(tzinfo=None)
        connection.error_message = None if result.status == "connected" else result.message
        self._audit(
            connection.destination_id,
            connection.id,
            "credential_check",
            result.status,
            result.message,
            {"credential_configured": result.credential_configured, "credential_required": result.credential_required},
        )
        self.db.commit()
        self.db.refresh(connection)
        return self.readiness(connection)

    def readiness(self, connection: models.DestinationConnection) -> DestinationConnectionReadiness:
        check = self.credentials.check(connection)
        definition = connector_definition(connection.connection_type)
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        next_actions: list[dict[str, Any]] = []
        if check.status != "connected":
            if check.auth_status == "official_adapter_unavailable":
                blockers.append({"blocker": "official_adapter_unavailable", "source": "destination_connectors"})
                next_actions.append({"action": "use_manual_or_csv_import", "source": "destination_connectors"})
            elif check.status == "needs_verification":
                blockers.append({"blocker": "official_credential_not_verified", "source": "destination_connectors"})
                next_actions.append({"action": "run_scoped_official_sync", "source": "destination_connectors"})
            else:
                blockers.append({"blocker": "destination_connection_needs_auth", "source": "destination_connectors"})
                next_actions.append({"action": "configure_credential_ref", "source": "destination_connectors"})
        if connection.connection_type in {"manual", "csv", "instagram_stub", "tiktok_stub", "telegram_bot"}:
            warnings.append({"warning": "manual_or_csv_metrics_required", "source": "destination_connectors"})
        return DestinationConnectionReadiness(
            connection_id=connection.id,
            destination_id=connection.destination_id,
            platform=connection.platform,
            connection_type=connection.connection_type,
            status=connection.status,
            auth_status=connection.auth_status,
            credential_required=check.credential_required,
            credential_configured=check.credential_configured,
            last_checked_at=connection.last_checked_at,
            last_sync_at=connection.last_sync_at,
            error_message=connection.error_message,
            blockers=blockers,
            warnings=warnings,
            next_actions=next_actions,
            required_scopes=list(definition.required_scopes) if definition else [],
            required_permissions=list(definition.required_permissions) if definition else [],
            account_requirements=list(definition.account_requirements) if definition else [],
        )

    def view(self, connection: models.DestinationConnection) -> DestinationConnectionView:
        return DestinationConnectionView(
            id=connection.id,
            destination_id=connection.destination_id,
            platform=connection.platform,
            connection_type=connection.connection_type,
            status=connection.status,
            auth_status=connection.auth_status,
            credential_configured=self.credentials.is_configured(connection.credential_ref),
            last_checked_at=connection.last_checked_at,
            last_sync_at=connection.last_sync_at,
            error_message=connection.error_message,
            settings_json=public_settings(connection.settings_json),
        )

    def overview(self) -> DestinationConnectorOverview:
        total_destinations = self.db.scalar(select(func.count(models.PublishingDestination.id))) or 0
        connections = self.list()
        last_sync = max((item.last_sync_at for item in connections if item.last_sync_at), default=None)
        return DestinationConnectorOverview(
            total_destinations=total_destinations,
            connected=sum(1 for item in connections if item.status == "connected"),
            needs_auth=sum(1 for item in connections if item.status == "needs_auth"),
            manual_only=sum(1 for item in connections if item.auth_status == "manual_only"),
            token_expired=sum(1 for item in connections if item.status == "token_expired" or item.auth_status == "token_expired"),
            last_sync=last_sync,
        )

    def _destination(self, destination_id: int) -> models.PublishingDestination:
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise DestinationConnectorDataError(f"PublishingDestination {destination_id} not found.")
        return destination

    @staticmethod
    def _connection_type(connection_type: str) -> str:
        normalized = (connection_type or "").strip()
        if normalized not in CONNECTION_TYPES:
            raise DestinationConnectorDataError(f"Unsupported connection type: {connection_type}")
        return normalized

    @staticmethod
    def _initial_status(connection_type: str, credential_ref: str | None) -> tuple[str, str]:
        if connection_type in {"manual", "csv"}:
            return "connected", "manual_only"
        if connection_type in {"instagram_stub", "tiktok_stub", "telegram_bot"}:
            return "blocked", "official_adapter_unavailable"
        return ("not_configured", "needs_auth") if not credential_ref else ("needs_auth", "needs_auth")

    def _audit(
        self,
        destination_id: int,
        connection_id: int | None,
        event_type: str,
        status: str,
        message: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            models.DestinationConnectionAudit(
                destination_id=destination_id,
                connection_id=connection_id,
                event_type=event_type,
                status=status,
                message=message,
                sanitized_payload_json=sanitize_payload(payload),
            )
        )
