from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import replace
from threading import RLock
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.platform_matrix import PlatformMetricsMatrix
from app.social_metrics_ingestion.errors import SocialMetricAccessError, SocialMetricValidationError
from app.social_metrics_ingestion.types import SocialMetricIngestionResult, SocialMetricObservation


SOURCE_TYPES = {
    "manual_entry",
    "manual_csv",
    "platform_export",
    "official_connector",
    "partner_report",
}
SOCIAL_PLATFORMS = {"facebook", "instagram", "youtube", "tiktok", "telegram", "vk", "partner", "other"}
PUBLISHED_TASK_STATUSES = {"published", "published_manual", "published_api", "done"}
PLATFORM_HOST_SUFFIXES = {
    "facebook": {"facebook.com", "fb.watch"},
    "instagram": {"instagram.com"},
    "youtube": {"youtube.com", "youtu.be"},
    "tiktok": {"tiktok.com"},
    "telegram": {"t.me", "telegram.me"},
    "vk": {"vk.com"},
}
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.test", "localhost", "mock.social"}
INTEGER_METRICS = {
    "views",
    "reach",
    "impressions",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "orders",
}
FLOAT_METRICS = {"revenue", "spend", "watch_time_seconds", "retention_rate"}
ALL_METRICS = INTEGER_METRICS | FLOAT_METRICS
SECRET_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "secret",
    "signature",
    "token",
}
EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
SAFE_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_INGEST_LOCK = RLock()


class SocialMetricIngestionService:
    """Fail-closed ingestion of cumulative post metrics into one canonical snapshot.

    DestinationPostMetric has no organization or database-level ingestion key in the
    legacy schema. This boundary therefore requires an organization-owned Product ->
    PublishingPackage -> PublishingTask chain, stores ownership provenance in raw_json,
    and refuses to adopt old rows that do not carry that provenance.
    """

    def __init__(self, db: Session):
        self.db = db

    def ingest(self, observation: SocialMetricObservation) -> SocialMetricIngestionResult:
        # The legacy table has no unique canonical/observation keys. Serialize the
        # read-modify-write section in this process; a future schema migration must
        # add database unique constraints before multi-worker ingestion is enabled.
        with _INGEST_LOCK:
            return self._ingest_locked(observation)

    def _ingest_locked(self, observation: SocialMetricObservation) -> SocialMetricIngestionResult:
        normalized = self._normalize_and_validate(observation)
        self._require_active_member(
            organization_id=normalized.organization_id,
            user_profile_id=normalized.actor_user_profile_id,
        )
        observation_key = self._observation_key(normalized)
        payload_hash = self._payload_hash(normalized)

        task_or_result = self._resolve_task(
            normalized,
            observation_key=observation_key,
            payload_hash=payload_hash,
        )
        if isinstance(task_or_result, SocialMetricIngestionResult):
            return task_or_result
        task = task_or_result
        package = task.publishing_package
        product = package.product if package else None
        if not package or not product or product.organization_id != normalized.organization_id:
            return self._quarantine(
                normalized,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="unowned_or_unscoped_publishing_lineage",
            )

        canonical_key = self._canonical_key(normalized, task.id)
        replay = self._accepted_observation(
            organization_id=normalized.organization_id,
            observation_key=observation_key,
        )
        if len(replay) > 1:
            return self._quarantine(
                normalized,
                observation_key=observation_key,
                payload_hash=payload_hash,
                canonical_key=canonical_key,
                reason="duplicate_idempotency_ledger_entries",
            )
        if replay:
            audit = replay[0]
            metadata = audit.metadata_json or {}
            if metadata.get("payload_hash") != payload_hash or metadata.get("canonical_key") != canonical_key:
                return self._quarantine(
                    normalized,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="idempotency_key_reused_with_different_payload",
                )
            metric = self._owned_metric_by_id(
                organization_id=normalized.organization_id,
                metric_id=metadata.get("metric_id"),
            )
            if metric is None:
                return self._quarantine(
                    normalized,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="idempotency_ledger_target_missing",
                )
            result = self._result(
                status="unchanged",
                metric=metric,
                observation=normalized,
                observation_key=observation_key,
                canonical_key=canonical_key,
                details={"idempotent_replay": True},
            )
            self.db.rollback()
            return result

        existing_or_result = self._canonical_metric(
            normalized,
            task=task,
            canonical_key=canonical_key,
            observation_key=observation_key,
            payload_hash=payload_hash,
        )
        if isinstance(existing_or_result, SocialMetricIngestionResult):
            return existing_or_result
        metric = existing_or_result
        metrics_to_apply = dict(normalized.metrics)

        if metric is not None:
            latest = self._latest_observation(metric)
            if latest is None:
                return self._quarantine(
                    normalized,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="legacy_metric_requires_manual_review",
                )
            metrics_to_apply, stale_fields, same_fields, conflict_fields = self._field_update_decision(
                metric,
                observation=normalized,
            )
            if conflict_fields:
                return self._quarantine(
                    normalized,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="conflicting_field_observation_at_same_timestamp",
                )
            if not metrics_to_apply:
                stale_only = bool(stale_fields)
                self._record_accepted_observation(
                    normalized,
                    metric=metric,
                    canonical_key=canonical_key,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    result="stale_ignored" if stale_only else "same_snapshot",
                )
                self.db.commit()
                return self._result(
                    status="stale" if stale_only else "unchanged",
                    metric=metric,
                    observation=normalized,
                    observation_key=observation_key,
                    canonical_key=canonical_key,
                    details={
                        "snapshot_updated": False,
                        "stale_fields": sorted(stale_fields),
                        "same_fields": sorted(same_fields),
                    },
                )

        created = metric is None
        metric = metric or models.DestinationPostMetric(platform=normalized.platform)
        applied_observation = replace(normalized, metrics=metrics_to_apply)
        self._apply_snapshot(
            metric,
            observation=applied_observation,
            task=task,
            product=product,
            canonical_key=canonical_key,
            observation_key=observation_key,
            payload_hash=payload_hash,
        )
        if created:
            self.db.add(metric)
        self.db.flush()
        self._record_accepted_observation(
            normalized,
            metric=metric,
            canonical_key=canonical_key,
            observation_key=observation_key,
            payload_hash=payload_hash,
            result="created" if created else "updated",
        )
        self.db.commit()
        self.db.refresh(metric)
        return self._result(
            status="created" if created else "updated",
            metric=metric,
            observation=normalized,
            observation_key=observation_key,
            canonical_key=canonical_key,
            details={"snapshot_updated": True, "applied_fields": sorted(metrics_to_apply)},
        )

    def list_metrics(self, *, organization_id: int, limit: int = 50) -> list[models.DestinationPostMetric]:
        organization_id = self._positive_id(organization_id, "organization_id")
        limit = min(max(int(limit), 1), 100)
        rows = self.db.scalars(
            select(models.DestinationPostMetric)
            .join(
                models.PublishingTask,
                models.DestinationPostMetric.publishing_task_id == models.PublishingTask.id,
            )
            .join(
                models.PublishingPackage,
                models.PublishingTask.publishing_package_id == models.PublishingPackage.id,
            )
            .join(models.Product, models.PublishingPackage.product_id == models.Product.id)
            .join(
                models.PublishingDestination,
                models.PublishingTask.destination_id == models.PublishingDestination.id,
            )
            .where(
                models.Product.organization_id == organization_id,
                models.PublishingDestination.organization_id == organization_id,
            )
            .order_by(models.DestinationPostMetric.id.desc())
        ).all()
        return [row for row in rows if self._metric_ingestion_org(row) == organization_id][:limit]

    def list_quarantine(self, *, organization_id: int, limit: int = 50) -> list[models.AuditLog]:
        organization_id = self._positive_id(organization_id, "organization_id")
        limit = min(max(int(limit), 1), 100)
        return list(
            self.db.scalars(
                select(models.AuditLog)
                .where(
                    models.AuditLog.organization_id == organization_id,
                    models.AuditLog.action == "social_metric_quarantined",
                    models.AuditLog.status == "blocked",
                )
                .order_by(models.AuditLog.id.desc())
                .limit(limit)
            ).all()
        )

    def _normalize_and_validate(self, observation: SocialMetricObservation) -> SocialMetricObservation:
        organization_id = self._positive_id(observation.organization_id, "organization_id")
        actor_id = self._positive_id(observation.actor_user_profile_id, "actor_user_profile_id")
        source_type = str(observation.source_type or "").strip().lower()
        if source_type not in SOURCE_TYPES:
            raise SocialMetricValidationError("source_type is not supported")
        source_ref = str(observation.source_ref or "").strip()
        if not SAFE_REF_RE.fullmatch(source_ref):
            raise SocialMetricValidationError("source_ref must be a safe logical source identifier")

        platform = self._normalize_platform(observation.platform)
        if platform not in SOCIAL_PLATFORMS:
            raise SocialMetricValidationError("platform is not a supported social destination")
        final_url = self._normalize_url(observation.final_url) if observation.final_url else None
        external_post_id = str(observation.external_post_id or "").strip() or None
        if external_post_id and not EXTERNAL_ID_RE.fullmatch(external_post_id):
            raise SocialMetricValidationError("external_post_id has an invalid format")
        if not final_url and not external_post_id:
            raise SocialMetricValidationError("final_url or external_post_id is required")

        publishing_task_id = None
        if observation.publishing_task_id is not None:
            publishing_task_id = self._positive_id(observation.publishing_task_id, "publishing_task_id")
        idempotency_key = str(observation.idempotency_key or "").strip() or None
        if idempotency_key and not SAFE_IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise SocialMetricValidationError("idempotency_key has an invalid format")

        observed_at = observation.observed_at
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise SocialMetricValidationError("observed_at must include a timezone")
        observed_at = observed_at.astimezone(UTC).replace(tzinfo=None)
        now = datetime.now(UTC).replace(tzinfo=None)
        if observed_at > now + timedelta(minutes=5):
            raise SocialMetricValidationError("observed_at cannot be in the future")
        if observation.period_end < observation.period_start:
            raise SocialMetricValidationError("period_end must be on or after period_start")
        if (observation.period_end - observation.period_start).days > 366:
            raise SocialMetricValidationError("metric period cannot exceed 366 days")
        if observation.period_end > observed_at.date():
            raise SocialMetricValidationError("period_end cannot be later than observed_at")

        metrics = self._validated_metrics(observation.metrics)
        return SocialMetricObservation(
            organization_id=organization_id,
            actor_user_profile_id=actor_id,
            source_type=source_type,
            source_ref=source_ref,
            platform=platform,
            observed_at=observed_at,
            period_start=observation.period_start,
            period_end=observation.period_end,
            metrics=metrics,
            final_url=final_url,
            external_post_id=external_post_id,
            publishing_task_id=publishing_task_id,
            idempotency_key=idempotency_key,
        )

    def _validated_metrics(self, metrics: dict[str, int | float | None]) -> dict[str, int | float | None]:
        if not isinstance(metrics, dict):
            raise SocialMetricValidationError("metrics must be an object")
        unknown = set(metrics) - ALL_METRICS
        if unknown:
            raise SocialMetricValidationError(f"unsupported metric fields: {', '.join(sorted(unknown))}")
        cleaned: dict[str, int | float | None] = {}
        for name, value in metrics.items():
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise SocialMetricValidationError(f"{name} must be a finite number")
            if float(value) < 0:
                raise SocialMetricValidationError(f"{name} cannot be negative")
            if name in INTEGER_METRICS:
                if int(value) != float(value):
                    raise SocialMetricValidationError(f"{name} must be an integer")
                cleaned[name] = int(value)
            else:
                cleaned[name] = round(float(value), 6)
        if cleaned.get("retention_rate") is not None and float(cleaned["retention_rate"]) > 1:
            raise SocialMetricValidationError("retention_rate must be between 0 and 1")
        if not cleaned:
            raise SocialMetricValidationError("at least one metric value is required")
        return cleaned

    def _require_active_member(self, *, organization_id: int, user_profile_id: int) -> None:
        bind = self.db.get_bind()
        if bind.dialect.name == "sqlite":
            # A no-op UPDATE obtains SQLite's database write lock inside the
            # current transaction, including when SQLAlchemy already autobegan
            # it with a read. This closes the multi-process insert race.
            lock_result = self.db.execute(
                text("UPDATE organizations SET id = id WHERE id = :organization_id"),
                {"organization_id": organization_id},
            )
            organization = self.db.get(models.Organization, organization_id) if lock_result.rowcount == 1 else None
        else:
            organization = self.db.scalar(
                select(models.Organization)
                .where(models.Organization.id == organization_id)
                .with_for_update()
            )
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        profile = self.db.get(models.UserProfile, user_profile_id)
        if (
            membership is None
            or profile is None
            or not profile.is_active
            or organization is None
            or organization.status != "active"
        ):
            self.db.rollback()
            raise SocialMetricAccessError("active organization membership is required")

    def _resolve_task(
        self,
        observation: SocialMetricObservation,
        *,
        observation_key: str,
        payload_hash: str,
    ) -> models.PublishingTask | SocialMetricIngestionResult:
        scoped_tasks = self.db.scalars(
            select(models.PublishingTask)
            .join(
                models.PublishingPackage,
                models.PublishingTask.publishing_package_id == models.PublishingPackage.id,
            )
            .join(models.Product, models.PublishingPackage.product_id == models.Product.id)
            .join(
                models.PublishingDestination,
                models.PublishingTask.destination_id == models.PublishingDestination.id,
            )
            .where(
                models.Product.organization_id == observation.organization_id,
                models.PublishingDestination.organization_id == observation.organization_id,
            )
            .order_by(models.PublishingTask.id)
        ).all()
        platform_tasks = [
            task
            for task in scoped_tasks
            if self._normalize_platform(task.platform) == observation.platform
            and task.destination is not None
            and self._normalize_platform(task.destination.platform) == observation.platform
            and task.publishing_package is not None
            and self._normalize_platform(task.publishing_package.target_platform) == observation.platform
        ]
        task_by_id = {task.id: task for task in platform_tasks}
        signal_sets: list[set[int]] = []

        if observation.publishing_task_id is not None:
            explicit = {observation.publishing_task_id} if observation.publishing_task_id in task_by_id else set()
            if not explicit:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    reason="unmatched_or_unowned_post",
                )
            signal_sets.append(explicit)

        if observation.final_url:
            url_ids = set()
            for task in platform_tasks:
                task_url = self._normalized_stored_url(task.final_url)
                if task_url and task_url == observation.final_url:
                    url_ids.add(task.id)
            if not url_ids:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    reason="unmatched_or_unowned_post",
                )
            signal_sets.append(url_ids)

        external_ids: set[int] = set()
        if observation.external_post_id:
            existing_metrics = self.db.scalars(
                select(models.DestinationPostMetric)
                .join(
                    models.PublishingTask,
                    models.DestinationPostMetric.publishing_task_id == models.PublishingTask.id,
                )
                .join(
                    models.PublishingPackage,
                    models.PublishingTask.publishing_package_id == models.PublishingPackage.id,
                )
                .join(models.Product, models.PublishingPackage.product_id == models.Product.id)
                .where(
                    models.Product.organization_id == observation.organization_id,
                    models.DestinationPostMetric.provider_post_id == observation.external_post_id,
                )
            ).all()
            external_ids.update(
                metric.publishing_task_id
                for metric in existing_metrics
                if metric.publishing_task_id in task_by_id
                and self._normalize_platform(metric.platform) == observation.platform
            )
            jobs = self.db.scalars(
                select(models.PublishingJob)
                .join(
                    models.PublishingPackage,
                    models.PublishingJob.publishing_package_id == models.PublishingPackage.id,
                )
                .join(models.Product, models.PublishingPackage.product_id == models.Product.id)
                .where(
                    models.Product.organization_id == observation.organization_id,
                    models.PublishingJob.provider_post_id == observation.external_post_id,
                )
            ).all()
            package_ids = {job.publishing_package_id for job in jobs}
            external_ids.update(task.id for task in platform_tasks if task.publishing_package_id in package_ids)
            if external_ids:
                signal_sets.append(external_ids)
            elif not observation.final_url and observation.publishing_task_id is None:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    reason="unmatched_or_unowned_post",
                )

        if not signal_sets:
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="unmatched_or_unowned_post",
            )
        candidate_ids = set.intersection(*signal_sets)
        if not candidate_ids:
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="conflicting_post_identity",
            )
        if len(candidate_ids) != 1:
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="ambiguous_attribution",
                candidate_count=len(candidate_ids),
            )
        task = task_by_id[next(iter(candidate_ids))]
        normalized_task_url = self._normalized_stored_url(task.final_url)
        if task.status not in PUBLISHED_TASK_STATUSES or not normalized_task_url:
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="publishing_task_is_not_confirmed_published",
            )
        if not self._url_matches_platform(normalized_task_url, observation.platform):
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="publishing_task_final_url_is_not_a_real_platform_post",
            )
        if observation.final_url and normalized_task_url != observation.final_url:
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                reason="conflicting_post_identity",
            )
        return task

    def _canonical_metric(
        self,
        observation: SocialMetricObservation,
        *,
        task: models.PublishingTask,
        canonical_key: str,
        observation_key: str,
        payload_hash: str,
    ) -> models.DestinationPostMetric | SocialMetricIngestionResult | None:
        period_rows = self.db.scalars(
            select(models.DestinationPostMetric).where(
                models.DestinationPostMetric.publishing_task_id == task.id,
                models.DestinationPostMetric.period_start.is_not(None),
                models.DestinationPostMetric.period_end.is_not(None),
                models.DestinationPostMetric.period_start <= observation.period_end,
                models.DestinationPostMetric.period_end >= observation.period_start,
            )
        ).all()
        period_rows = [
            metric
            for metric in period_rows
            if self._normalize_platform(metric.platform) == observation.platform
        ]
        candidates = [
            metric
            for metric in period_rows
            if metric.period_start == observation.period_start
            and metric.period_end == observation.period_end
        ]
        if len(candidates) > 1:
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                canonical_key=canonical_key,
                reason="duplicate_canonical_metric_rows",
            )
        if any(metric not in candidates for metric in period_rows):
            return self._quarantine(
                observation,
                observation_key=observation_key,
                payload_hash=payload_hash,
                canonical_key=canonical_key,
                reason="overlapping_metric_period_requires_reconciliation",
            )
        if candidates:
            metric = candidates[0]
            if self._normalize_platform(metric.platform) != observation.platform:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="canonical_metric_identity_conflict",
                )
            ingestion = (metric.raw_json or {}).get("ingestion_v1")
            if not isinstance(ingestion, dict):
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="legacy_metric_requires_manual_review",
                )
            if ingestion.get("organization_id") != observation.organization_id or ingestion.get("canonical_key") != canonical_key:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="canonical_metric_scope_conflict",
                )
            if metric.product_id != task.publishing_package.product_id:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="canonical_metric_scope_conflict",
                )
            metric_url = self._normalized_stored_url(metric.posted_url)
            task_url = self._normalized_stored_url(task.final_url)
            if metric.posted_url and (metric_url is None or metric_url != task_url):
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="canonical_metric_identity_conflict",
                )
            if observation.external_post_id and metric.provider_post_id and metric.provider_post_id != observation.external_post_id:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="canonical_metric_identity_conflict",
                )
            return metric

        task_final_url = self._normalized_stored_url(task.final_url)
        identity_clauses = [models.DestinationPostMetric.posted_url.is_not(None)]
        if observation.external_post_id:
            identity_clauses.append(models.DestinationPostMetric.provider_post_id == observation.external_post_id)
        possible_rows = self.db.scalars(
            select(models.DestinationPostMetric).where(
                models.DestinationPostMetric.period_start == observation.period_start,
                models.DestinationPostMetric.period_end == observation.period_end,
                or_(*identity_clauses),
            )
        ).all()
        for metric in possible_rows:
            if self._normalize_platform(metric.platform) != observation.platform:
                continue
            url_matches = bool(
                task_final_url
                and self._normalized_stored_url(metric.posted_url) == task_final_url
            )
            external_id_matches = bool(
                observation.external_post_id
                and metric.provider_post_id == observation.external_post_id
            )
            if not url_matches and not external_id_matches:
                continue
            metric_org = self._metric_owner_org(metric)
            if metric_org in {None, observation.organization_id}:
                return self._quarantine(
                    observation,
                    observation_key=observation_key,
                    payload_hash=payload_hash,
                    canonical_key=canonical_key,
                    reason="legacy_metric_collision_requires_manual_review",
                )
        return None

    def _apply_snapshot(
        self,
        metric: models.DestinationPostMetric,
        *,
        observation: SocialMetricObservation,
        task: models.PublishingTask,
        product: models.Product,
        canonical_key: str,
        observation_key: str,
        payload_hash: str,
    ) -> None:
        values = observation.metrics
        previous_raw = metric.raw_json or {}
        previous_ingestion = previous_raw.get("ingestion_v1", {})
        previous_latest = self._latest_observation(metric)
        field_provenance = dict(previous_ingestion.get("field_provenance") or {})
        metric.destination_id = task.destination_id
        metric.connection_id = None
        # Campaign is still legacy-global and has no organization_id. Do not
        # attach it until ownership can be proven by the schema.
        metric.campaign_id = None
        metric.publishing_task_id = task.id
        metric.product_id = product.id
        metric.sku = product.sku
        metric.platform = observation.platform
        metric.posted_url = self._normalized_stored_url(task.final_url)
        metric.provider_post_id = observation.external_post_id or metric.provider_post_id
        metric.period_start = observation.period_start
        metric.period_end = observation.period_end
        for name in ["views", "likes", "comments", "shares", "saves", "clicks", "orders", "revenue", "spend", "watch_time_seconds", "retention_rate"]:
            if name in values:
                setattr(metric, name, values[name])
                field_provenance[name] = {
                    "observed_at": observation.observed_at.isoformat() + "Z",
                    "source_type": observation.source_type,
                    "source_ref": observation.source_ref,
                    "observation_key": observation_key,
                }
        for name in ["reach", "impressions"]:
            if name in values:
                field_provenance[name] = {
                    "observed_at": observation.observed_at.isoformat() + "Z",
                    "source_type": observation.source_type,
                    "source_ref": observation.source_ref,
                    "observation_key": observation_key,
                }
        metric.engagement_rate = self._ratio(
            sum(int(getattr(metric, name) or 0) for name in ["likes", "comments", "shares", "saves"]),
            metric.views,
        )
        metric.ctr = self._ratio(metric.clicks, metric.views)
        metric.conversion_rate = self._ratio(metric.orders, metric.clicks)
        incoming_is_latest = previous_latest is None or observation.observed_at >= previous_latest
        latest_observation = (
            {
                "actor_user_profile_id": observation.actor_user_profile_id,
                "latest_observation_key": observation_key,
                "payload_hash": payload_hash,
                "source_type": observation.source_type,
                "source_ref": observation.source_ref,
                "observed_at": observation.observed_at.isoformat() + "Z",
            }
            if incoming_is_latest
            else {
                "actor_user_profile_id": previous_ingestion.get("actor_user_profile_id"),
                "latest_observation_key": previous_ingestion.get("latest_observation_key"),
                "payload_hash": previous_ingestion.get("payload_hash"),
                "source_type": previous_ingestion.get("source_type"),
                "source_ref": previous_ingestion.get("source_ref"),
                "observed_at": previous_ingestion.get("observed_at"),
            }
        )
        metric.raw_json = {
            "ingestion_v1": {
                "status": "accepted",
                "organization_id": observation.organization_id,
                "canonical_key": canonical_key,
                **latest_observation,
                "last_applied_observation_key": observation_key,
                "last_applied_observed_at": observation.observed_at.isoformat() + "Z",
                "external_post_id": metric.provider_post_id,
                "final_url": self._safe_public_url(metric.posted_url),
                "period_start": observation.period_start.isoformat(),
                "period_end": observation.period_end.isoformat(),
                "snapshot_semantics": "cumulative_replace_not_sum",
                "source_verification": "declared_by_authenticated_actor",
                "unscoped_dimensions_omitted": ["campaign_id", "connection_id"],
                "field_provenance": field_provenance,
            },
            "reach": values["reach"] if "reach" in values else previous_raw.get("reach"),
            "impressions": values["impressions"] if "impressions" in values else previous_raw.get("impressions"),
        }

    def _record_accepted_observation(
        self,
        observation: SocialMetricObservation,
        *,
        metric: models.DestinationPostMetric,
        canonical_key: str,
        observation_key: str,
        payload_hash: str,
        result: str,
    ) -> None:
        self.db.add(
            models.AuditLog(
                user_profile_id=observation.actor_user_profile_id,
                organization_id=observation.organization_id,
                action="social_metric_observation",
                status="allowed",
                reason=result,
                entity_type="social_metric_observation",
                entity_id=observation_key,
                metadata_json={
                    "metric_id": metric.id,
                    "publishing_task_id": metric.publishing_task_id,
                    "canonical_key": canonical_key,
                    "payload_hash": payload_hash,
                    "source_type": observation.source_type,
                    "source_ref": observation.source_ref,
                    "observed_at": observation.observed_at.isoformat() + "Z",
                    "period_start": observation.period_start.isoformat(),
                    "period_end": observation.period_end.isoformat(),
                    "result": result,
                },
            )
        )

    def _quarantine(
        self,
        observation: SocialMetricObservation,
        *,
        observation_key: str,
        payload_hash: str,
        reason: str,
        canonical_key: str | None = None,
        candidate_count: int | None = None,
    ) -> SocialMetricIngestionResult:
        existing = self.db.scalar(
            select(models.AuditLog)
            .where(
                models.AuditLog.organization_id == observation.organization_id,
                models.AuditLog.action == "social_metric_quarantined",
                models.AuditLog.status == "blocked",
                models.AuditLog.entity_id == observation_key,
                models.AuditLog.reason == reason,
            )
            .order_by(models.AuditLog.id)
        )
        if existing is None:
            metadata: dict[str, Any] = {
                "payload_hash": payload_hash,
                "canonical_key": canonical_key,
                "source_type": observation.source_type,
                "source_ref": observation.source_ref,
                "platform": observation.platform,
                "external_post_id": observation.external_post_id,
                "final_url": self._safe_public_url(observation.final_url),
                "declared_publishing_task_id": observation.publishing_task_id,
                "observed_at": observation.observed_at.isoformat() + "Z",
                "period_start": observation.period_start.isoformat(),
                "period_end": observation.period_end.isoformat(),
                "metrics": observation.metrics,
            }
            if candidate_count is not None:
                metadata["candidate_count"] = candidate_count
            existing = models.AuditLog(
                user_profile_id=observation.actor_user_profile_id,
                organization_id=observation.organization_id,
                action="social_metric_quarantined",
                status="blocked",
                reason=reason,
                entity_type="social_metric_observation",
                entity_id=observation_key,
                metadata_json=metadata,
            )
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
        return SocialMetricIngestionResult(
            status="quarantined",
            disposition="quarantine",
            quarantine_id=existing.id,
            reason=reason,
            canonical_key=canonical_key,
            observation_key=observation_key,
            observed_at=observation.observed_at,
            period_start=observation.period_start,
            period_end=observation.period_end,
            details={"candidate_count": candidate_count} if candidate_count is not None else {},
        )

    def _accepted_observation(self, *, organization_id: int, observation_key: str) -> list[models.AuditLog]:
        return list(
            self.db.scalars(
                select(models.AuditLog).where(
                    models.AuditLog.organization_id == organization_id,
                    models.AuditLog.action == "social_metric_observation",
                    models.AuditLog.status == "allowed",
                    models.AuditLog.entity_id == observation_key,
                )
            ).all()
        )

    def _owned_metric_by_id(self, *, organization_id: int, metric_id: Any) -> models.DestinationPostMetric | None:
        try:
            metric_id = int(metric_id)
        except (TypeError, ValueError):
            return None
        metric = self.db.scalar(
            select(models.DestinationPostMetric)
            .join(
                models.PublishingTask,
                models.DestinationPostMetric.publishing_task_id == models.PublishingTask.id,
            )
            .join(
                models.PublishingPackage,
                models.PublishingTask.publishing_package_id == models.PublishingPackage.id,
            )
            .join(models.Product, models.PublishingPackage.product_id == models.Product.id)
            .join(
                models.PublishingDestination,
                models.PublishingTask.destination_id == models.PublishingDestination.id,
            )
            .where(
                models.DestinationPostMetric.id == metric_id,
                models.Product.organization_id == organization_id,
                models.PublishingDestination.organization_id == organization_id,
            )
        )
        if metric is None or self._metric_ingestion_org(metric) != organization_id:
            return None
        return metric

    def _metric_owner_org(self, metric: models.DestinationPostMetric) -> int | None:
        raw_org = self._metric_ingestion_org(metric)
        if raw_org is not None:
            return raw_org
        if metric.product_id:
            product = self.db.get(models.Product, metric.product_id)
            if product:
                return product.organization_id
        if metric.publishing_task_id:
            task = self.db.get(models.PublishingTask, metric.publishing_task_id)
            package = task.publishing_package if task else None
            product = package.product if package else None
            return product.organization_id if product else None
        return None

    @staticmethod
    def _metric_ingestion_org(metric: models.DestinationPostMetric) -> int | None:
        value = (metric.raw_json or {}).get("ingestion_v1", {}).get("organization_id")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _latest_observation(metric: models.DestinationPostMetric) -> datetime | None:
        value = (metric.raw_json or {}).get("ingestion_v1", {}).get("observed_at")
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            return None

    def _field_update_decision(
        self,
        metric: models.DestinationPostMetric,
        *,
        observation: SocialMetricObservation,
    ) -> tuple[dict[str, int | float | None], set[str], set[str], set[str]]:
        raw = metric.raw_json or {}
        ingestion = raw.get("ingestion_v1", {})
        provenance = ingestion.get("field_provenance") or {}
        fallback_time = self._latest_observation(metric)
        apply_values: dict[str, int | float | None] = {}
        stale_fields: set[str] = set()
        same_fields: set[str] = set()
        conflict_fields: set[str] = set()
        for name, incoming_value in observation.metrics.items():
            current_value = raw.get(name) if name in {"reach", "impressions"} else getattr(metric, name, None)
            field_time = self._provenance_time(provenance.get(name))
            if field_time is None and current_value is not None:
                # Compatibility for rows written by the first P1 revision,
                # before per-field provenance was introduced.
                field_time = fallback_time
            if field_time is None or observation.observed_at > field_time:
                apply_values[name] = incoming_value
            elif observation.observed_at < field_time:
                stale_fields.add(name)
            elif self._metric_values_equal(current_value, incoming_value):
                same_fields.add(name)
            else:
                conflict_fields.add(name)
        return apply_values, stale_fields, same_fields, conflict_fields

    @staticmethod
    def _provenance_time(value: Any) -> datetime | None:
        if not isinstance(value, dict) or not isinstance(value.get("observed_at"), str):
            return None
        try:
            return datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            return None

    @staticmethod
    def _metric_values_equal(left: Any, right: Any) -> bool:
        if isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
            return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
        return left == right

    @staticmethod
    def _result(
        *,
        status: str,
        metric: models.DestinationPostMetric,
        observation: SocialMetricObservation,
        observation_key: str,
        canonical_key: str,
        details: dict[str, Any],
    ) -> SocialMetricIngestionResult:
        return SocialMetricIngestionResult(
            status=status,
            disposition="accepted",
            metric_id=metric.id,
            canonical_key=canonical_key,
            observation_key=observation_key,
            publishing_task_id=metric.publishing_task_id,
            observed_at=observation.observed_at,
            period_start=observation.period_start,
            period_end=observation.period_end,
            details=details,
        )

    @classmethod
    def _normalize_platform(cls, value: Any) -> str:
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        for marker, canonical in [
            ("instagram", "instagram"),
            ("youtube", "youtube"),
            ("tiktok", "tiktok"),
            ("telegram", "telegram"),
            ("facebook", "facebook"),
            ("vkontakte", "vk"),
        ]:
            if marker in raw:
                return canonical
        return PlatformMetricsMatrix.normalize_platform(raw)

    @staticmethod
    def _normalize_url(value: str | None) -> str:
        text = str(value or "").strip()
        try:
            parts = urlsplit(text)
            port = parts.port
        except ValueError as exc:
            raise SocialMetricValidationError("final_url is invalid") from exc
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise SocialMetricValidationError("final_url must be an absolute HTTP(S) URL")
        if parts.username or parts.password:
            raise SocialMetricValidationError("final_url cannot contain credentials")
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        if any(key.lower() in SECRET_QUERY_KEYS for key, _value in query_pairs):
            raise SocialMetricValidationError("final_url cannot contain credential-like query parameters")
        host = parts.hostname.lower().rstrip(".")
        default_port = (parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)
        netloc = host if port is None or default_port else f"{host}:{port}"
        path = parts.path or "/"
        if path != "/":
            path = path.rstrip("/")
        query = urlencode(sorted(query_pairs))
        normalized = urlunsplit((parts.scheme.lower(), netloc, path, query, ""))
        if len(normalized) > 500:
            raise SocialMetricValidationError("final_url is too long")
        return normalized

    @classmethod
    def _normalized_stored_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return cls._normalize_url(value)
        except SocialMetricValidationError:
            return None

    @classmethod
    def _safe_public_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        parts = urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def _url_matches_platform(value: str, platform: str) -> bool:
        host = (urlsplit(value).hostname or "").lower().rstrip(".")
        if (
            not host
            or host in PLACEHOLDER_HOSTS
            or host.endswith(".test")
            or host.endswith(".local")
            or host in {"127.0.0.1", "::1"}
        ):
            return False
        allowed_suffixes = PLATFORM_HOST_SUFFIXES.get(platform)
        if not allowed_suffixes:
            return True
        return any(host == suffix or host.endswith(f".{suffix}") for suffix in allowed_suffixes)

    @classmethod
    def _observation_key(cls, observation: SocialMetricObservation) -> str:
        if observation.idempotency_key:
            identity = {
                "organization_id": observation.organization_id,
                "source_type": observation.source_type,
                "source_ref": observation.source_ref,
                "client_key": observation.idempotency_key,
            }
        else:
            identity = {
                "organization_id": observation.organization_id,
                "source_type": observation.source_type,
                "source_ref": observation.source_ref,
                "platform": observation.platform,
                "final_url": observation.final_url,
                "external_post_id": observation.external_post_id,
                "period_start": observation.period_start.isoformat(),
                "period_end": observation.period_end.isoformat(),
                "observed_at": observation.observed_at.isoformat(),
            }
        return "smi:" + cls._hash_json(identity)

    @classmethod
    def _canonical_key(cls, observation: SocialMetricObservation, task_id: int) -> str:
        return "smc:" + cls._hash_json(
            {
                "organization_id": observation.organization_id,
                "publishing_task_id": task_id,
                "platform": observation.platform,
                "period_start": observation.period_start.isoformat(),
                "period_end": observation.period_end.isoformat(),
            }
        )

    @classmethod
    def _payload_hash(cls, observation: SocialMetricObservation) -> str:
        return cls._hash_json(
            {
                "source_type": observation.source_type,
                "source_ref": observation.source_ref,
                "platform": observation.platform,
                "final_url": observation.final_url,
                "external_post_id": observation.external_post_id,
                "publishing_task_id": observation.publishing_task_id,
                "observed_at": observation.observed_at.isoformat(),
                "period_start": observation.period_start.isoformat(),
                "period_end": observation.period_end.isoformat(),
                "metrics": observation.metrics,
            }
        )

    @staticmethod
    def _hash_json(value: dict[str, Any]) -> str:
        serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _positive_id(value: Any, field: str) -> int:
        if isinstance(value, bool):
            raise SocialMetricValidationError(f"{field} must be a positive integer")
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise SocialMetricValidationError(f"{field} must be a positive integer") from exc
        if result <= 0:
            raise SocialMetricValidationError(f"{field} must be a positive integer")
        return result

    @staticmethod
    def _ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
        if numerator is None or denominator in {None, 0}:
            return None
        return round(float(numerator) / float(denominator), 6)
