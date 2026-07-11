from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.catalog import connector_definition
from app.destination_connectors.credential_status import sanitize_payload
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.instagram_connector import InstagramInsightsConnector
from app.destination_connectors.tiktok_connector import TikTokDisplayConnector
from app.destination_connectors.types import OfficialConnectorSyncResult
from app.destination_connectors.youtube_connector import YouTubeAnalyticsConnector


class DestinationConnectorSyncService:
    """Organization-scoped official sync boundary.

    Manual/CSV imports have their own explicit collectors. Pending provider adapters
    are never interpreted as successful syncs, and no settings_json mock rows are
    read here.
    """

    def __init__(
        self,
        db: Session,
        *,
        youtube_connector: YouTubeAnalyticsConnector | None = None,
        tiktok_connector: TikTokDisplayConnector | None = None,
        instagram_connector: InstagramInsightsConnector | None = None,
        ingestion_factory: Callable[[Session], Any] | None = None,
    ):
        self.db = db
        self.youtube_connector = youtube_connector or YouTubeAnalyticsConnector()
        self.tiktok_connector = tiktok_connector or TikTokDisplayConnector()
        self.instagram_connector = instagram_connector or InstagramInsightsConnector()
        self.connectors: dict[str, Any] = {
            "youtube_oauth": self.youtube_connector,
            "tiktok_oauth": self.tiktok_connector,
            "instagram_oauth": self.instagram_connector,
        }
        self.ingestion_factory = ingestion_factory

    def sync(
        self,
        connection_id: int,
        *,
        organization_id: int | None = None,
        destination_id: int | None = None,
        actor_user_profile_id: int | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        observed_at: datetime | None = None,
        sync_key: str | None = None,
    ) -> OfficialConnectorSyncResult:
        organization_id = self._positive_id(organization_id, "organization_id")
        destination_id = self._positive_id(destination_id, "destination_id")
        actor_user_profile_id = self._positive_id(actor_user_profile_id, "actor_user_profile_id")
        connection_id = self._positive_id(connection_id, "connection_id")
        if period_start is None or period_end is None:
            raise DestinationConnectorDataError("period_start_and_period_end_are_required")
        if period_end < period_start:
            raise DestinationConnectorDataError("period_end_must_not_precede_period_start")
        if observed_at is None or observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise DestinationConnectorDataError("observed_at_must_include_timezone")
        observed_at = observed_at.astimezone(UTC)
        if period_end > observed_at.date():
            raise DestinationConnectorDataError("period_end_must_not_follow_observed_at")
        sync_key = str(sync_key or "").strip()
        if not sync_key or len(sync_key) > 200:
            raise DestinationConnectorDataError("sync_key_is_required_and_must_be_at_most_200_characters")

        self._require_actor(organization_id=organization_id, actor_user_profile_id=actor_user_profile_id)
        connection = self._owned_connection(
            organization_id=organization_id,
            destination_id=destination_id,
            connection_id=connection_id,
        )
        definition = connector_definition(connection.connection_type)
        connector = self.connectors.get(connection.connection_type)
        if definition is None or connector is None:
            raise DestinationConnectorDataError(
                "official_adapter_unavailable_use_explicit_manual_or_csv_import"
            )

        try:
            snapshots = connector.collect_metrics(
                connection,
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
            )
        except DestinationConnectorDataError as exc:
            safe_code = self._safe_failure_code(str(exc), platform=definition.platform)
            self._record_connection_failure(
                connection,
                error_code=safe_code,
                display_name=definition.display_name,
                platform=definition.platform,
            )
            raise DestinationConnectorDataError(safe_code) from exc

        # Local imports prevent the package cycle
        # social_metrics_ingestion -> metrics_intake -> destination_connectors.
        from app.social_metrics_ingestion.errors import SocialMetricAccessError, SocialMetricValidationError
        from app.social_metrics_ingestion.service import SocialMetricIngestionService
        from app.social_metrics_ingestion.types import SocialMetricObservation

        ingestion = (
            self.ingestion_factory(self.db)
            if self.ingestion_factory is not None
            else SocialMetricIngestionService(self.db)
        )
        results: list[dict[str, object]] = []
        accepted = 0
        unchanged = 0
        quarantined = 0
        errors = 0
        sync_digest = hashlib.sha256(sync_key.encode("utf-8")).hexdigest()[:20]
        for snapshot in snapshots:
            external_post_id = str(snapshot.external_post_id)
            post_digest = hashlib.sha256(external_post_id.encode("utf-8")).hexdigest()[:12]
            try:
                result = ingestion.ingest(
                    SocialMetricObservation(
                        organization_id=organization_id,
                        actor_user_profile_id=actor_user_profile_id,
                        source_type="official_connector",
                        source_ref=f"{definition.source_ref_prefix}:{connection.id}",
                        platform=definition.platform,
                        observed_at=observed_at,
                        period_start=period_start,
                        period_end=period_end,
                        metrics=snapshot.metrics,
                        final_url=snapshot.final_url,
                        external_post_id=external_post_id,
                        publishing_task_id=snapshot.publishing_task_id,
                        idempotency_key=(
                            f"{definition.idempotency_prefix}:{connection.id}:"
                            f"{sync_digest}:{post_digest}"
                        ),
                    )
                )
            except (SocialMetricAccessError, SocialMetricValidationError):
                errors += 1
                results.append(
                    {
                        "external_post_id": external_post_id,
                        definition.target_id_label: external_post_id,
                        "status": "error",
                        "reason": "social_metric_ingestion_rejected",
                    }
                )
                continue

            if result.disposition == "quarantine":
                quarantined += 1
            elif result.status in {"unchanged", "stale"}:
                unchanged += 1
            else:
                accepted += 1
            results.append(
                {
                    "external_post_id": external_post_id,
                    definition.target_id_label: external_post_id,
                    "status": result.status,
                    "disposition": result.disposition,
                    "metric_id": result.metric_id,
                    "quarantine_id": result.quarantine_id,
                    "reason": result.reason,
                }
            )

        now = datetime.now(UTC).replace(tzinfo=None)
        connection.status = "connected"
        connection.auth_status = "oauth_verified"
        connection.error_message = None
        connection.last_checked_at = now
        connection.last_sync_at = now
        status = self._result_status(
            snapshots=len(snapshots),
            quarantined=quarantined,
            errors=errors,
        )
        self.db.add(
            models.DestinationConnectionAudit(
                destination_id=destination_id,
                connection_id=connection.id,
                event_type="official_metric_sync",
                status=status,
                message=f"Official {definition.display_name} metric sync completed.",
                sanitized_payload_json=sanitize_payload(
                    {
                        "organization_id": organization_id,
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                        "row_count": len(snapshots),
                        "accepted_count": accepted,
                        "unchanged_count": unchanged,
                        "quarantined_count": quarantined,
                        "error_count": errors,
                    }
                ),
            )
        )
        self.db.commit()
        return OfficialConnectorSyncResult(
            status=status,
            organization_id=organization_id,
            destination_id=destination_id,
            connection_id=connection.id,
            platform=definition.platform,
            period_start=period_start,
            period_end=period_end,
            requested_count=len(snapshots),
            accepted_count=accepted,
            unchanged_count=unchanged,
            quarantined_count=quarantined,
            error_count=errors,
            results=results,
            warnings=["manual_review_required_for_quarantined_rows"] if quarantined else [],
        )

    def _owned_connection(
        self,
        *,
        organization_id: int,
        destination_id: int,
        connection_id: int,
    ) -> models.DestinationConnection:
        connection = self.db.scalar(
            select(models.DestinationConnection)
            .join(
                models.PublishingDestination,
                models.DestinationConnection.destination_id == models.PublishingDestination.id,
            )
            .where(
                models.DestinationConnection.id == connection_id,
                models.DestinationConnection.destination_id == destination_id,
                models.PublishingDestination.organization_id == organization_id,
            )
        )
        if connection is None:
            raise DestinationConnectorDataError("destination_connection_not_found_in_organization")
        return connection

    def _require_actor(self, *, organization_id: int, actor_user_profile_id: int) -> None:
        organization = self.db.get(models.Organization, organization_id)
        profile = self.db.get(models.UserProfile, actor_user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == actor_user_profile_id,
                models.Membership.status == "active",
            )
        )
        if (
            organization is None
            or organization.status != "active"
            or profile is None
            or not profile.is_active
            or membership is None
        ):
            raise DestinationConnectorDataError("active_organization_membership_required")

    def _record_connection_failure(
        self,
        connection: models.DestinationConnection,
        *,
        error_code: str,
        display_name: str,
        platform: str,
    ) -> None:
        safe_code = self._safe_failure_code(error_code, platform=platform)
        connection.status = "error"
        if "authorization_failed" in safe_code or "credential" in safe_code:
            connection.auth_status = "needs_auth"
        connection.error_message = safe_code
        connection.last_checked_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.add(
            models.DestinationConnectionAudit(
                destination_id=connection.destination_id,
                connection_id=connection.id,
                event_type="official_metric_sync_failed",
                status="error",
                message=f"Official {display_name} metric sync failed.",
                sanitized_payload_json={"error_code": safe_code},
            )
        )
        self.db.commit()

    @staticmethod
    def _positive_id(value: int | None, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DestinationConnectorDataError(f"{field}_is_required_and_must_be_positive")
        return value

    @staticmethod
    def _safe_failure_code(error_code: str, *, platform: str) -> str:
        normalized = error_code.strip().lower()
        safe_platform = platform if platform in {"youtube", "tiktok", "instagram"} else "social"
        allowed_prefixes = (
            f"{safe_platform}_",
            "period_",
            "publishing_task_",
            "destination_",
            "organization_",
        )
        if (
            len(normalized) <= 160
            and re.fullmatch(r"[a-z0-9_]+", normalized)
            and normalized.startswith(allowed_prefixes)
        ):
            return normalized
        return f"{safe_platform}_official_connector_failed"

    @staticmethod
    def _result_status(*, snapshots: int, quarantined: int, errors: int) -> str:
        if snapshots == 0:
            return "completed_no_data"
        if errors or quarantined:
            return "partial"
        return "completed"
