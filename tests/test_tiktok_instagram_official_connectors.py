from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from typing import Any

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_tiktok_instagram_connectors.db")

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
    InstagramInsightsConnector,
    TikTokDisplayConnector,
)
from app.metrics_intake import OfficialConnectorGateway, PlatformMetricsMatrix


PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 7)
OBSERVED_AT = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
TIKTOK_VIDEO_ID = "7412345678901234567"
TIKTOK_URL = f"https://www.tiktok.com/@contentfactory/video/{TIKTOK_VIDEO_ID}"
INSTAGRAM_MEDIA_ID = "18012345678901234"
INSTAGRAM_URL = "https://www.instagram.com/reel/DemoCode01"


class StaticCredentialResolver:
    def __init__(self, secret: str | None):
        self.secret = secret
        self.references: list[str] = []

    def resolve(self, credential_ref: str) -> str | None:
        self.references.append(credential_ref)
        return self.secret


class CapturingTikTokTransport:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.error_payload: dict[str, Any] | None = None
        self.metrics = {
            "view_count": 100,
            "like_count": 9,
            "comment_count": 2,
            "share_count": 1,
        }
        self.video_id = TIKTOK_VIDEO_ID

    def query_videos(
        self,
        *,
        access_token: str,
        fields: tuple[str, ...],
        video_ids: list[str],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "access_token": access_token,
                "fields": fields,
                "video_ids": list(video_ids),
            }
        )
        if self.error_payload is not None:
            return self.error_payload
        return {
            "data": {
                "videos": [
                    {
                        "id": self.video_id,
                        **self.metrics,
                    }
                ]
            },
            "error": {"code": "ok", "message": "", "log_id": "provider-log-not-persisted"},
        }


class CapturingInstagramTransport:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.error_payload: dict[str, Any] | None = None
        self.values = {
            "plays": 200,
            "reach": 150,
            "likes": 20,
            "comments": 3,
            "shares": 4,
            "saved": 5,
        }

    def query_media_insights(
        self,
        *,
        access_token: str,
        api_version: str,
        media_id: str,
        metrics: tuple[str, ...],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "access_token": access_token,
                "api_version": api_version,
                "media_id": media_id,
                "metrics": metrics,
            }
        )
        if self.error_payload is not None:
            return self.error_payload
        return {
            "data": [
                {"name": name, "period": "lifetime", "values": [{"value": value}]}
                for name, value in self.values.items()
            ],
            # Provider pagination can contain a credential-bearing URL. The
            # adapter deliberately ignores it and never persists the payload.
            "paging": {
                "next": "https://graph.instagram.com/next?access_token=must-not-persist"
            },
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


def _published_lineage(
    db: Session,
    *,
    organization: models.Organization,
    profile: models.UserProfile,
    platform: str,
    final_url: str,
    external_id: str,
    connection_type: str,
) -> tuple[models.PublishingTask, models.DestinationConnection]:
    suffix = f"{platform}-{organization.id}"
    product = models.Product(
        organization_id=organization.id,
        sku=f"SOCIAL-{suffix}",
        brand="Official Social Brand",
        title=f"Official Social Product {suffix}",
    )
    guide = models.BrandGuide(brand="Official Social Brand")
    template = models.CreativeTemplate(name=f"template-{suffix}")
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="Official Social Brand",
        platform=platform,
        name=f"{platform.title()} {suffix}",
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
        target_platform=platform,
        title=f"Package {suffix}",
        review_status="approved",
        status="approved",
    )
    db.add(package)
    db.flush()
    task = models.PublishingTask(
        publishing_package_id=package.id,
        destination_id=destination.id,
        platform=platform,
        status="published_manual",
        final_url=final_url,
        scheduled_at=datetime(2026, 7, 7, 10, 0),
    )
    db.add(task)
    db.flush()
    map_key = "video_map" if platform == "tiktok" else "media_map"
    settings: dict[str, Any] = {
        map_key: {
            external_id: {
                "final_url": final_url,
                "publishing_task_id": task.id,
            }
        }
    }
    if platform == "instagram":
        settings["api_version"] = "v25.0"
    connection = models.DestinationConnection(
        destination_id=destination.id,
        platform=platform,
        connection_type=connection_type,
        status="needs_auth",
        auth_status="needs_auth",
        credential_ref=f"env:{platform.upper()}_OFFICIAL_ACCESS_TOKEN",
        settings_json=settings,
    )
    db.add(connection)
    db.commit()
    db.refresh(task)
    db.refresh(connection)
    return task, connection


def _sync(
    service: DestinationConnectorSyncService,
    *,
    organization: models.Organization,
    profile: models.UserProfile,
    task: models.PublishingTask,
    connection: models.DestinationConnection,
    observed_at: datetime = OBSERVED_AT,
    sync_key: str,
):
    return service.sync(
        connection.id,
        organization_id=organization.id,
        destination_id=task.destination_id,
        actor_user_profile_id=profile.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        observed_at=observed_at,
        sync_key=sync_key,
    )


def test_catalog_and_platform_matrix_expose_real_scope_and_permission_contract(db: Session):
    catalog = {item["platform"]: item for item in OfficialConnectorGateway(db).catalog()}

    assert PlatformMetricsMatrix.config("tiktok").official_connector_types == ["tiktok_oauth"]
    assert PlatformMetricsMatrix.config("instagram").official_connector_types == ["instagram_oauth"]
    assert PlatformMetricsMatrix.config("Instagram Reels").official_connector_types == [
        "instagram_oauth"
    ]
    assert catalog["tiktok"]["required_scopes"] == ["video.list"]
    assert catalog["tiktok"]["max_targets_per_request"] == 20
    assert catalog["instagram"]["required_permissions"] == [
        "instagram_business_basic",
        "instagram_business_manage_insights",
    ]
    assert catalog["instagram"]["account_requirements"] == [
        "instagram_professional_account"
    ]


def test_tiktok_fake_transport_sync_is_idempotent_and_replaces_cumulative_values(db: Session):
    organization, profile = _user(db, slug="tiktok-official")
    task, connection = _published_lineage(
        db,
        organization=organization,
        profile=profile,
        platform="tiktok",
        final_url=TIKTOK_URL,
        external_id=TIKTOK_VIDEO_ID,
        connection_type="tiktok_oauth",
    )
    secret = "tiktok-oauth-secret-must-not-leak"
    resolver = StaticCredentialResolver(secret)
    transport = CapturingTikTokTransport()
    connector = TikTokDisplayConnector(transport=transport, credential_resolver=resolver)
    service = DestinationConnectorSyncService(db, tiktok_connector=connector)

    first = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        sync_key="tiktok-pull-001",
    )
    replay = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        sync_key="tiktok-pull-001",
    )
    transport.metrics = {
        "view_count": 150,
        "like_count": 12,
        "comment_count": 3,
        "share_count": 2,
    }
    updated = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        observed_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        sync_key="tiktok-pull-002",
    )

    metric = db.scalar(select(models.DestinationPostMetric))
    audits = list(db.scalars(select(models.DestinationConnectionAudit)).all())
    readiness = OfficialConnectorGateway(
        db,
        credential_resolver=resolver,
        tiktok_connector=connector,
    ).readiness(task.destination_id, organization_id=organization.id)
    public = json.dumps(
        {
            "first": first.model_dump(mode="json"),
            "replay": replay.model_dump(mode="json"),
            "updated": updated.model_dump(mode="json"),
            "readiness": readiness,
            "audits": [audit.sanitized_payload_json for audit in audits],
        }
    )

    assert first.status == "completed" and first.accepted_count == 1
    assert replay.unchanged_count == 1
    assert updated.accepted_count == 1
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 1
    assert metric.views == 150
    assert metric.likes == 12
    assert metric.comments == 3
    assert metric.shares == 2
    assert readiness["ready"] is True
    assert readiness["required_scopes"] == ["video.list"]
    assert readiness["credential_available"] is True
    assert transport.calls[0]["fields"] == (
        "id",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
    )
    assert transport.calls[0]["video_ids"] == [TIKTOK_VIDEO_ID]
    assert secret not in public
    assert "TIKTOK_OFFICIAL_ACCESS_TOKEN" not in public


def test_instagram_fake_transport_normalizes_available_metrics_and_discards_signed_paging(db: Session):
    organization, profile = _user(db, slug="instagram-official")
    task, connection = _published_lineage(
        db,
        organization=organization,
        profile=profile,
        platform="instagram",
        final_url=INSTAGRAM_URL,
        external_id=INSTAGRAM_MEDIA_ID,
        connection_type="instagram_oauth",
    )
    secret = "instagram-oauth-secret-must-not-leak"
    resolver = StaticCredentialResolver(secret)
    transport = CapturingInstagramTransport()
    connector = InstagramInsightsConnector(transport=transport, credential_resolver=resolver)
    service = DestinationConnectorSyncService(db, instagram_connector=connector)

    first = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        sync_key="instagram-pull-001",
    )
    replay = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        sync_key="instagram-pull-001",
    )
    transport.values = {
        "views": 260,
        "plays": 250,
        "reach": 190,
        "likes": 27,
        "comments": 4,
        "shares": 6,
        "saved": 8,
    }
    updated = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        observed_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        sync_key="instagram-pull-002",
    )

    metric = db.scalar(select(models.DestinationPostMetric))
    audits = list(db.scalars(select(models.DestinationConnectionAudit)).all())
    readiness = OfficialConnectorGateway(
        db,
        credential_resolver=resolver,
        instagram_connector=connector,
    ).readiness(task.destination_id, organization_id=organization.id)
    persisted = json.dumps(
        {
            "metric": metric.raw_json,
            "connection": {
                "error": connection.error_message,
                "settings": connection.settings_json,
            },
            "audits": [audit.sanitized_payload_json for audit in audits],
            "readiness": readiness,
            "results": [first.model_dump(mode="json"), updated.model_dump(mode="json")],
        }
    )

    assert first.accepted_count == 1
    assert replay.unchanged_count == 1
    assert updated.accepted_count == 1
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 1
    assert metric.views == 260  # views wins over the legacy plays alias; never summed.
    assert metric.likes == 27
    assert metric.comments == 4
    assert metric.shares == 6
    assert metric.saves == 8
    assert metric.raw_json["reach"] == 190
    assert transport.calls[0]["api_version"] == "v25.0"
    assert transport.calls[0]["media_id"] == INSTAGRAM_MEDIA_ID
    assert readiness["ready"] is True
    assert readiness["required_permissions"] == [
        "instagram_business_basic",
        "instagram_business_manage_insights",
    ]
    assert secret not in persisted
    assert "must-not-persist" not in persisted
    assert "INSTAGRAM_OFFICIAL_ACCESS_TOKEN" not in persisted


@pytest.mark.parametrize("platform", ["tiktok", "instagram"])
def test_new_connectors_reject_cross_org_before_fake_transport(
    db: Session,
    platform: str,
):
    owner_org, owner_profile = _user(db, slug=f"{platform}-owner")
    foreign_org, foreign_profile = _user(db, slug=f"{platform}-foreign")
    is_tiktok = platform == "tiktok"
    task, connection = _published_lineage(
        db,
        organization=owner_org,
        profile=owner_profile,
        platform=platform,
        final_url=TIKTOK_URL if is_tiktok else INSTAGRAM_URL,
        external_id=TIKTOK_VIDEO_ID if is_tiktok else INSTAGRAM_MEDIA_ID,
        connection_type="tiktok_oauth" if is_tiktok else "instagram_oauth",
    )
    resolver = StaticCredentialResolver("secret")
    tiktok_transport = CapturingTikTokTransport()
    instagram_transport = CapturingInstagramTransport()
    service = DestinationConnectorSyncService(
        db,
        tiktok_connector=TikTokDisplayConnector(
            transport=tiktok_transport,
            credential_resolver=resolver,
        ),
        instagram_connector=InstagramInsightsConnector(
            transport=instagram_transport,
            credential_resolver=resolver,
        ),
    )

    with pytest.raises(DestinationConnectorDataError, match="not_found_in_organization"):
        service.sync(
            connection.id,
            organization_id=foreign_org.id,
            destination_id=task.destination_id,
            actor_user_profile_id=foreign_profile.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            observed_at=OBSERVED_AT,
            sync_key=f"{platform}-cross-org",
        )

    assert tiktok_transport.calls == []
    assert instagram_transport.calls == []
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


@pytest.mark.parametrize("platform", ["tiktok", "instagram"])
def test_strict_owned_target_map_blocks_mismatch_before_fake_transport(
    db: Session,
    platform: str,
):
    organization, profile = _user(db, slug=f"{platform}-strict-map")
    is_tiktok = platform == "tiktok"
    task, connection = _published_lineage(
        db,
        organization=organization,
        profile=profile,
        platform=platform,
        final_url=TIKTOK_URL if is_tiktok else INSTAGRAM_URL,
        external_id=TIKTOK_VIDEO_ID if is_tiktok else INSTAGRAM_MEDIA_ID,
        connection_type="tiktok_oauth" if is_tiktok else "instagram_oauth",
    )
    map_key = "video_map" if is_tiktok else "media_map"
    settings = dict(connection.settings_json)
    settings[map_key] = dict(settings[map_key])
    settings[map_key][TIKTOK_VIDEO_ID if is_tiktok else INSTAGRAM_MEDIA_ID] = {
        "final_url": (
            f"https://www.tiktok.com/@other/video/{TIKTOK_VIDEO_ID}"
            if is_tiktok
            else "https://www.instagram.com/reel/AnotherCode02"
        ),
        "publishing_task_id": task.id,
    }
    connection.settings_json = settings
    db.commit()
    resolver = StaticCredentialResolver("secret")
    tiktok_transport = CapturingTikTokTransport()
    instagram_transport = CapturingInstagramTransport()
    service = DestinationConnectorSyncService(
        db,
        tiktok_connector=TikTokDisplayConnector(
            transport=tiktok_transport,
            credential_resolver=resolver,
        ),
        instagram_connector=InstagramInsightsConnector(
            transport=instagram_transport,
            credential_resolver=resolver,
        ),
    )

    with pytest.raises(DestinationConnectorDataError, match="target_final_url_mismatch"):
        _sync(
            service,
            organization=organization,
            profile=profile,
            task=task,
            connection=connection,
            sync_key=f"{platform}-strict-map-mismatch",
        )

    assert tiktok_transport.calls == []
    assert instagram_transport.calls == []
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0


def test_signed_url_is_rejected_before_connection_persistence(db: Session):
    organization, _profile = _user(db, slug="signed-url")
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="Safe",
        platform="instagram",
        name="Safe Instagram",
    )
    db.add(destination)
    db.commit()

    with pytest.raises(DestinationConnectorDataError, match="Signed URLs"):
        ConnectionRegistry(db).create(
            destination.id,
            "instagram_oauth",
            credential_ref="env:INSTAGRAM_ACCESS_TOKEN",
            settings_json={
                "media_map": {
                    INSTAGRAM_MEDIA_ID: {
                        "publishing_task_id": 1,
                        "final_url": f"{INSTAGRAM_URL}?access_token=must-not-store",
                    }
                }
            },
        )

    assert db.scalar(select(func.count(models.DestinationConnection.id))) == 0
    assert "must-not-store" not in json.dumps(
        [row.sanitized_payload_json for row in db.scalars(select(models.DestinationConnectionAudit))]
    )


def test_instagram_canonical_identity_conflict_is_quarantined_not_summed(db: Session):
    organization, profile = _user(db, slug="instagram-quarantine")
    task, connection = _published_lineage(
        db,
        organization=organization,
        profile=profile,
        platform="instagram",
        final_url=INSTAGRAM_URL,
        external_id=INSTAGRAM_MEDIA_ID,
        connection_type="instagram_oauth",
    )
    resolver = StaticCredentialResolver("secret")
    transport = CapturingInstagramTransport()
    connector = InstagramInsightsConnector(transport=transport, credential_resolver=resolver)
    service = DestinationConnectorSyncService(db, instagram_connector=connector)
    _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        sync_key="instagram-before-conflict",
    )
    metric = db.scalar(select(models.DestinationPostMetric))
    metric.provider_post_id = "different-owned-media"
    db.commit()
    transport.values["plays"] = 999

    result = _sync(
        service,
        organization=organization,
        profile=profile,
        task=task,
        connection=connection,
        observed_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
        sync_key="instagram-conflict",
    )

    db.refresh(metric)
    quarantine = db.scalar(
        select(models.AuditLog).where(models.AuditLog.action == "social_metric_quarantined")
    )
    assert result.status == "partial"
    assert result.quarantined_count == 1
    assert metric.views == 200
    assert quarantine is not None and quarantine.organization_id == organization.id


@pytest.mark.parametrize("platform", ["tiktok", "instagram"])
def test_provider_error_payload_is_reduced_to_safe_code_and_never_persisted(
    db: Session,
    platform: str,
):
    organization, profile = _user(db, slug=f"{platform}-safe-failure")
    is_tiktok = platform == "tiktok"
    task, connection = _published_lineage(
        db,
        organization=organization,
        profile=profile,
        platform=platform,
        final_url=TIKTOK_URL if is_tiktok else INSTAGRAM_URL,
        external_id=TIKTOK_VIDEO_ID if is_tiktok else INSTAGRAM_MEDIA_ID,
        connection_type="tiktok_oauth" if is_tiktok else "instagram_oauth",
    )
    marker = "raw-provider-message-with-access-token=must-not-persist"
    resolver = StaticCredentialResolver("oauth-secret")
    tiktok_transport = CapturingTikTokTransport()
    instagram_transport = CapturingInstagramTransport()
    if is_tiktok:
        tiktok_transport.error_payload = {
            "data": {},
            "error": {"code": "access_token_invalid", "message": marker},
        }
    else:
        instagram_transport.error_payload = {
            "error": {"type": "OAuthException", "message": marker}
        }
    service = DestinationConnectorSyncService(
        db,
        tiktok_connector=TikTokDisplayConnector(
            transport=tiktok_transport,
            credential_resolver=resolver,
        ),
        instagram_connector=InstagramInsightsConnector(
            transport=instagram_transport,
            credential_resolver=resolver,
        ),
    )

    expected = f"{platform}_official_api_rejected_request"
    with pytest.raises(DestinationConnectorDataError, match=expected):
        _sync(
            service,
            organization=organization,
            profile=profile,
            task=task,
            connection=connection,
            sync_key=f"{platform}-safe-provider-failure",
        )

    db.refresh(connection)
    audits = list(db.scalars(select(models.DestinationConnectionAudit)).all())
    persisted = json.dumps(
        {
            "error_message": connection.error_message,
            "audits": [
                {
                    "message": audit.message,
                    "payload": audit.sanitized_payload_json,
                }
                for audit in audits
            ],
        }
    )
    assert connection.error_message == expected
    assert marker not in persisted
    assert "must-not-persist" not in persisted
    assert db.scalar(select(func.count(models.DestinationPostMetric.id))) == 0
