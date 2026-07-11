from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.credential_status import validate_credential_ref
from app.destination_connectors.errors import DestinationConnectorDataError
from app.metrics_intake.errors import MetricsIntakeDataError


SAFE_SOURCE_TYPES = {"csv", "manual", "manual_csv", "tracking_link", "official_api", "partner_report", "marketplace_csv"}
SAFE_PLATFORMS = {"facebook", "instagram", "youtube", "telegram", "tiktok", "ozon", "wb", "other"}
FORBIDDEN_SETTING_KEYS = {"token", "access_token", "refresh_token", "password", "cookie", "cookies", "session", "secret"}
FORBIDDEN_SETTING_MARKERS = ("access_token", "refresh_token", "client_secret", "password", "cookie", "session")


class MetricsSourceRegistry:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        name: str,
        source_type: str,
        platform: str = "other",
        connection_id: int | None = None,
        status: str = "active",
        settings_json: dict[str, Any] | None = None,
    ) -> models.MetricsSource:
        clean_source_type = self._normalize(source_type)
        clean_platform = self._normalize(platform)
        if clean_source_type not in SAFE_SOURCE_TYPES:
            raise MetricsIntakeDataError(f"Unsupported metrics source type: {source_type}")
        if clean_platform not in SAFE_PLATFORMS:
            clean_platform = "other"
        if connection_id and not self.db.get(models.DestinationConnection, connection_id):
            raise MetricsIntakeDataError(f"Destination connection {connection_id} not found.")
        settings = self._safe_settings(settings_json or {})
        source = models.MetricsSource(
            name=name.strip(),
            source_type=clean_source_type,
            platform=clean_platform,
            connection_id=connection_id,
            status=status,
            settings_json=settings,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def list(self, *, platform: str | None = None, source_type: str | None = None) -> list[models.MetricsSource]:
        query = select(models.MetricsSource).order_by(models.MetricsSource.id.desc())
        if platform:
            query = query.where(models.MetricsSource.platform == self._normalize(platform))
        if source_type:
            query = query.where(models.MetricsSource.source_type == self._normalize(source_type))
        return self.db.scalars(query).all()

    def get(self, source_id: int) -> models.MetricsSource:
        source = self.db.get(models.MetricsSource, source_id)
        if not source:
            raise MetricsIntakeDataError(f"Metrics source {source_id} not found.")
        return source

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower().replace("-", "_")

    @classmethod
    def _safe_settings(cls, settings: dict[str, Any]) -> dict[str, Any]:
        def clean_value(value: Any) -> Any:
            if isinstance(value, dict):
                clean: dict[str, Any] = {}
                for key, nested in value.items():
                    normalized_key = cls._normalize(str(key))
                    if (
                        normalized_key in FORBIDDEN_SETTING_KEYS
                        or any(marker in normalized_key for marker in FORBIDDEN_SETTING_MARKERS)
                        or normalized_key.endswith("_token")
                        or normalized_key.endswith("_secret")
                        or normalized_key.endswith("_password")
                    ):
                        raise MetricsIntakeDataError(
                            "Raw platform secrets must not be stored in metrics source settings."
                        )
                    if normalized_key == "credential_ref":
                        try:
                            clean[str(key)] = validate_credential_ref(str(nested or ""))
                        except DestinationConnectorDataError as exc:
                            raise MetricsIntakeDataError(
                                "credential_ref must be a logical secret reference."
                            ) from exc
                    else:
                        clean[str(key)] = clean_value(nested)
                return clean
            if isinstance(value, list):
                return [clean_value(item) for item in value]
            return value

        return clean_value(settings)
