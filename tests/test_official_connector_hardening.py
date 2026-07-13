from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from typing import Any

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_official_connectors.db")

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.destination_connectors import (
    ConnectionRegistry,
    DestinationConnectorDataError,
    DestinationConnectorSyncService,
    HttpxYouTubeAnalyticsTransport,
    TelegramConnector,
    YouTubeAnalyticsConnector,
)
from app.metrics_intake import OfficialConnectorGateway


VIDEO_ID = "AbCdEf12345"
OTHER_VIDEO_ID = "ZyXwVu98765"
FINAL_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 7)
OBSERVED_AT = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


class StaticCredentialResolver:
    def __init__(self, secret: str | None):
        self.secret = secret
        self.references: list[str] = []

    def resolve(self, credential_ref: str) -> str | None:
        self.references.append(credential_ref)
        return self.secret


class CapturingOfficialTransport:
    def __init__(self, *, rows: list[list[Any]] | None = None):
        self.rows = rows if rows is not None else [[VIDEO_ID, 100, 9, 2, 1, 12.5, 62.5]]
        self.calls: list[dict[str, Any]] = []

    def query_report(self, *, access_token: str, params: dict[str, str | int]) -> dict[str, Any]:
        self.calls.append({"access_token": access_token, "params": dict(params)})
        return {
            "kind": "youtubeAnalytics#result",
            "columnHeaders": [
                {"name": "video", "columnType": "DIMENSION", "dataType": "STRING"},
                {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
                {"name": "likes", "columnType": "METRIC", "dataType": "INTEGER"},
                {"name": "comments", "columnType": "METRIC", "dataType": "INTEGER"},
                {"name": "shares", "columnType": "METRIC", "dataType": "INTEGER"},
                {"name": "estimatedMinutesWatched", "columnType": "METRIC", "dataType": "FLOAT"},
                {"name": "averageViewPercentage", "columnType": "METRIC", "dataType": "FLOAT"},
            ],
            "rows": self.rows,
        }


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = local_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _user(db: Session, *, slug: str) -> tuple[models.Organization, models.UserProfile]:
    organization = models.Organization(name=slug.title(), slug=slug, status="active")
    profile = models.UserProfile(
        supabase_user_id=f"test:{slug}",
        email=f"owner@{slug}.test",
        display_name=f"{slug.title()} Owner",
        is_active=True,
    )
    db.add_all([organization, profile])
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="owner",
            status="active",
        )
    )
    db.commit()
    return organization, profile


def _published_youtube_lineage(
    db: Session,
    *,
    organization: models.Organization,
    profile: models.UserProfile,
    suffix: str,
    final_url: str = FINAL_URL,
) -> tuple[models.PublishingTask, models.DestinationConnection]:
    product = models.Product(
        organization_id=organization.id,
        sku=f"YT-{suffix}",
        brand="Official Metric Brand",
        title=f"Official Metric Product {suffix}",
    )
    guide = models.BrandGuide(brand="Official Metric Brand")
    template = models.CreativeTemplate(name=f"youtube-template-{suffix}")
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="Official Metric Brand",
        platform="youtube",
        name=f"YouTube {suffix}",
        status="active",
    )
    db.add_all([product, guide, template, destination])
    db.flush()
    script_job = models.ScriptJob(
        product_id=product.id,
        template_id=template.id,
        brand_guide_id=guide.id,
    )
    db.add(script_job)
    db.flush()
    variant = models.ScriptVariant(script_job_id=script_job.id, variant_number=1)
    db.add(variant)
    db.flush()
    video_job = models.VideoJob(
        script_variant_id=variant.id,
        organization_id=organization.id,
        created_by_user_profile_id=profile.id,
        product_id=product.id,
        status="completed",
    )
    db.add(video_job)
    db.flush()
    package = models.PublishingPackage(
        video_job_id=video_job.id,
        product_id=product.id,
        brand=product.brand,
        target_platform="youtube",
        title=f"Package {suffix}",
        review_status="approved",
        status="approved",
    )
    db.add(package)
    db.flush()
    task = models.PublishingTask(
        publishing_package_id=package.id,
        destination_id=destination.id,
        platform="youtube",
        status="published_manual",
        final_url=final_url,
        scheduled_at=datetime(2026, 7, 7, 10, 0),
    )
    db.add(task)
    db.flush()
    connection = models.DestinationConnection(
        destination_id=destination.id,
        platform="youtube",
        connection_type="youtube_oauth",
        status="needs_auth",
        auth_status="needs_auth",
        credential_ref="env:YOUTUBE_ANALYTICS_ACCESS_TOKEN",
        settings_json={
            "video_ids": [VIDEO_ID],
            "video_map": {
                VIDEO_ID: {
                    "final_url": final_url,
                    "publishing_task_id": task.id,
                }
            },
        },
    )
    db.add(connection)
    db.commit()
    db.refresh(task)
    db.refresh(connection)
    return task, connection


def _service(
    db: Session,
    *,
    resolver: StaticCredentialResolver,
    transport: CapturingOfficialTransport,
) -> DestinationConnectorSyncService:
    connector = YouTubeAnalyticsConnector(
        transport=transport,
        credential_resolver=resolver,
    )
    return DestinationConnectorSyncService(db, youtube_connector=connector)


def test_default_connectors_never_construct_mock_clients_or_read_mock_rows(db: Session):
    organization, profile = _user(db, slug="no-mocks")
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="Safe",
        platform="telegram",
        name="Safe Telegram",
    )
    db.add(destination)
    db.commit()

    with pytest.raises(DestinationConnectorDataError, match="mock_metrics"):
        ConnectionRegistry(db).create(
            destination.id,
            "manual",
            settings_json={"mock_metrics": [{"views": 999999}]},
        )
    with pytest.raises(DestinationConnectorDataError, match="Raw credentials"):
        ConnectionRegistry(db).create(
            destination.id,
            "manual",
            settings_json={"oauth": {"client_secret_value": "must-not-enter-db"}},
        )

    legacy = models.DestinationConnection(
        destination_id=destination.id,
        platform="telegram",
        connection_type="manual",
        status="connected",
        auth_status="manual_only",
        settings_json={"mock_metrics": [{"views": 999999}]},
    )
    db.add(legacy)
    db.commit()
    with pytest.raises(DestinationConnectorDataError, match="official_adapter_unavailable"):
        DestinationConnectorSyncService(db).sync(
            legacy.id,
            organization_id=organization.id,
            destination_id=destination.id,
            actor_user_profile_id=profile.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            observed_at=OBSERVED_AT,
            sync_key="manual-mock-must-never-sync",
        )

    assert isinstance(YouTubeAnalyticsConnector().transport, HttpxYouTubeAnalyticsTransport)
    assert TelegramConnector().client is None
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


def test_missing_credential_fails_closed_before_transport_and_does_not_expose_reference(db: Session):
    organization, profile = _user(db, slug="missing-secret")
    task, connection = _published_youtube_lineage(
        db,
        organization=organization,
        profile=profile,
        suffix="MISSING",
    )
    resolver = StaticCredentialResolver(None)
    transport = CapturingOfficialTransport()
    with pytest.raises(DestinationConnectorDataError, match="credential_reference_unresolved"):
        _service(db, resolver=resolver, transport=transport).sync(
            connection.id,
            organization_id=organization.id,
            destination_id=task.destination_id,
            actor_user_profile_id=profile.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            observed_at=OBSERVED_AT,
            sync_key="missing-secret-attempt",
        )

    readiness = OfficialConnectorGateway(
        db,
        credential_resolver=resolver,
        youtube_connector=YouTubeAnalyticsConnector(
            transport=transport,
            credential_resolver=resolver,
        ),
    ).readiness(task.destination_id, organization_id=organization.id)
    serialized = json.dumps(readiness)
    assert readiness["ready"] is False
    assert readiness["can_attempt_sync"] is False
    assert transport.calls == []
    assert "YOUTUBE_ANALYTICS_ACCESS_TOKEN" not in serialized
    assert "env:" not in serialized
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


def test_official_sync_is_organization_and_destination_scoped_before_api_call(db: Session):
    alpha, alpha_profile = _user(db, slug="connector-alpha")
    beta, beta_profile = _user(db, slug="connector-beta")
    task, connection = _published_youtube_lineage(
        db,
        organization=alpha,
        profile=alpha_profile,
        suffix="ALPHA",
    )
    resolver = StaticCredentialResolver("oauth-secret-that-must-not-leak")
    transport = CapturingOfficialTransport()

    with pytest.raises(DestinationConnectorDataError, match="not_found_in_organization"):
        _service(db, resolver=resolver, transport=transport).sync(
            connection.id,
            organization_id=beta.id,
            destination_id=task.destination_id,
            actor_user_profile_id=beta_profile.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            observed_at=OBSERVED_AT,
            sync_key="foreign-org-attempt",
        )

    readiness = OfficialConnectorGateway(
        db,
        credential_resolver=resolver,
    ).readiness(task.destination_id, organization_id=beta.id)
    assert readiness["status"] == "missing_destination"
    assert transport.calls == []
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


def test_injected_official_response_is_normalized_idempotent_and_cumulative_safe(db: Session):
    organization, profile = _user(db, slug="youtube-official")
    task, connection = _published_youtube_lineage(
        db,
        organization=organization,
        profile=profile,
        suffix="OFFICIAL",
    )
    secret = "oauth-secret-that-must-not-leak"
    resolver = StaticCredentialResolver(secret)
    transport = CapturingOfficialTransport()
    service = _service(db, resolver=resolver, transport=transport)

    first = service.sync(
        connection.id,
        organization_id=organization.id,
        destination_id=task.destination_id,
        actor_user_profile_id=profile.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        observed_at=OBSERVED_AT,
        sync_key="youtube-pull-001",
    )
    replay = service.sync(
        connection.id,
        organization_id=organization.id,
        destination_id=task.destination_id,
        actor_user_profile_id=profile.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        observed_at=OBSERVED_AT,
        sync_key="youtube-pull-001",
    )
    transport.rows = [[VIDEO_ID, 150, 12, 3, 2, 20.0, 70.0]]
    updated = service.sync(
        connection.id,
        organization_id=organization.id,
        destination_id=task.destination_id,
        actor_user_profile_id=profile.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        observed_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        sync_key="youtube-pull-002",
    )

    metric = db.scalar(select(models.DestinationPostMetric))
    db.refresh(connection)
    readiness = OfficialConnectorGateway(
        db,
        credential_resolver=resolver,
        youtube_connector=YouTubeAnalyticsConnector(
            transport=transport,
            credential_resolver=resolver,
        ),
    ).readiness(task.destination_id, organization_id=organization.id)
    public_payload = json.dumps(
        {
            "first": first.model_dump(mode="json"),
            "replay": replay.model_dump(mode="json"),
            "updated": updated.model_dump(mode="json"),
            "readiness": readiness,
        }
    )

    assert first.status == "completed"
    assert first.accepted_count == 1
    assert replay.unchanged_count == 1
    assert updated.accepted_count == 1
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 1
    assert metric.views == 150
    assert metric.likes == 12
    assert metric.watch_time_seconds == 1200.0
    assert metric.retention_rate == 0.7
    assert connection.auth_status == "oauth_verified"
    assert readiness["ready"] is True
    assert readiness["credential_reference_configured"] is True
    assert readiness["credential_available"] is True
    assert readiness["credential_reference_status"] == "available"
    assert readiness["last_sync_at"] is not None
    assert all(call["access_token"] == secret for call in transport.calls)
    assert all("access_token" not in call["params"] for call in transport.calls)
    assert transport.calls[0]["params"]["ids"] == "channel==MINE"
    assert transport.calls[0]["params"]["dimensions"] == "video"
    assert transport.calls[0]["params"]["filters"] == f"video=={VIDEO_ID}"
    assert secret not in public_payload
    assert "env:YOUTUBE_ANALYTICS_ACCESS_TOKEN" not in public_payload


def test_official_attribution_errors_are_quarantined_without_cross_post_fallback(db: Session):
    organization, profile = _user(db, slug="youtube-quarantine")
    task, connection = _published_youtube_lineage(
        db,
        organization=organization,
        profile=profile,
        suffix="QUARANTINE",
    )
    connection.settings_json = {
        "video_ids": [VIDEO_ID],
        "video_map": {
            VIDEO_ID: {
                "final_url": f"https://youtu.be/{OTHER_VIDEO_ID}",
                "publishing_task_id": task.id,
            }
        },
    }
    db.commit()
    resolver = StaticCredentialResolver("oauth-secret")
    transport = CapturingOfficialTransport()

    result = _service(db, resolver=resolver, transport=transport).sync(
        connection.id,
        organization_id=organization.id,
        destination_id=task.destination_id,
        actor_user_profile_id=profile.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        observed_at=OBSERVED_AT,
        sync_key="youtube-unmatched-post",
    )

    quarantine = db.scalar(
        select(models.AuditLog).where(models.AuditLog.action == "social_metric_quarantined")
    )
    assert result.status == "partial"
    assert result.quarantined_count == 1
    assert result.accepted_count == 0
    assert quarantine is not None
    assert quarantine.organization_id == organization.id
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


def test_invalid_official_response_fails_closed_without_partial_metric_write(db: Session):
    organization, profile = _user(db, slug="youtube-invalid-response")
    task, connection = _published_youtube_lineage(
        db,
        organization=organization,
        profile=profile,
        suffix="INVALID",
    )
    resolver = StaticCredentialResolver("oauth-secret")
    transport = CapturingOfficialTransport(
        rows=[["Unrequested99", 100, 9, 2, 1, 12.5, 62.5]],
    )

    with pytest.raises(DestinationConnectorDataError, match="unrequested_or_duplicate_video"):
        _service(db, resolver=resolver, transport=transport).sync(
            connection.id,
            organization_id=organization.id,
            destination_id=task.destination_id,
            actor_user_profile_id=profile.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            observed_at=OBSERVED_AT,
            sync_key="invalid-official-response",
        )

    db.refresh(connection)
    assert connection.status == "error"
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


@pytest.mark.parametrize("platform", ["telegram", "wb"])
def test_unimplemented_platforms_are_honestly_blocked_with_manual_fallback(db: Session, platform: str):
    organization, _profile = _user(db, slug=f"blocked-{platform}")
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="Blocked",
        platform=platform,
        name=f"Blocked {platform}",
    )
    db.add(destination)
    db.commit()

    readiness = OfficialConnectorGateway(db).readiness(
        destination.id,
        organization_id=organization.id,
    )

    assert readiness["ready"] is False
    assert readiness["can_attempt_sync"] is False
    assert readiness["status"] == "manual_or_csv_only"
    assert readiness["blockers"] == ["official_adapter_not_implemented"]
    assert any("manual" in source for source in readiness["fallbacks"])
