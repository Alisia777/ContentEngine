from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_social_metrics_ingestion.db")
os.environ["QVF_AUTH_REQUIRED"] = "false"
os.environ["QVF_PUBLIC_PILOT_MODE"] = "false"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers.api import router as legacy_api_router
from app.routers.social_metrics import router
from app.social_metrics_ingestion import SocialMetricIngestionService, SocialMetricObservation


@pytest.fixture(autouse=True)
def reset_social_metric_db():
    previous_public_mode = os.environ.get("QVF_PUBLIC_PILOT_MODE")
    previous_auth_required = os.environ.get("QVF_AUTH_REQUIRED")
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "false"
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    if previous_public_mode is None:
        os.environ.pop("QVF_PUBLIC_PILOT_MODE", None)
    else:
        os.environ["QVF_PUBLIC_PILOT_MODE"] = previous_public_mode
    if previous_auth_required is None:
        os.environ.pop("QVF_AUTH_REQUIRED", None)
    else:
        os.environ["QVF_AUTH_REQUIRED"] = previous_auth_required
    get_settings.cache_clear()


def make_user(db, *, slug: str) -> PublicPilotUser:
    organization = models.Organization(name=slug.title(), slug=slug, status="active")
    profile = models.UserProfile(
        supabase_user_id=f"test:{slug}",
        email=f"owner@{slug}.test",
        display_name=f"{slug.title()} Owner",
        is_active=True,
    )
    db.add_all([organization, profile])
    db.flush()
    membership = models.Membership(
        organization_id=organization.id,
        user_profile_id=profile.id,
        role="owner",
        status="active",
    )
    db.add(membership)
    db.commit()
    return PublicPilotUser(profile=profile, organization=organization, membership=membership)


def make_published_task(
    db,
    user: PublicPilotUser,
    *,
    suffix: str,
    final_url: str,
    platform: str = "instagram",
    scoped: bool = True,
) -> tuple[models.Product, models.PublishingTask]:
    product = models.Product(
        organization_id=user.organization.id if scoped else None,
        sku=f"SOCIAL-{suffix}",
        brand="Metric Brand",
        title=f"Metric Product {suffix}",
    )
    guide = models.BrandGuide(brand="Metric Brand")
    template = models.CreativeTemplate(name=f"social-template-{suffix}")
    destination = models.PublishingDestination(
        organization_id=user.organization.id if scoped else None,
        brand="Metric Brand",
        platform=platform,
        name=f"Destination {suffix}",
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
        organization_id=user.organization.id if scoped else None,
        created_by_user_profile_id=user.profile.id if scoped else None,
        product_id=product.id if scoped else None,
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
        scheduled_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
    )
    db.add(task)
    db.commit()
    db.refresh(product)
    db.refresh(task)
    return product, task


def observation(
    user: PublicPilotUser,
    task: models.PublishingTask,
    *,
    observed_at: datetime,
    views: int,
    source_type: str = "platform_export",
    source_ref: str = "instagram-export-main",
    idempotency_key: str = "metric-observation-1",
    publishing_task_id: int | None = None,
    final_url: str | None = None,
    external_post_id: str | None = "ig-post-1001",
) -> SocialMetricObservation:
    return SocialMetricObservation(
        organization_id=user.organization.id,
        actor_user_profile_id=user.profile.id,
        source_type=source_type,
        source_ref=source_ref,
        platform="instagram",
        final_url=task.final_url if final_url is None else final_url,
        external_post_id=external_post_id,
        publishing_task_id=publishing_task_id,
        observed_at=observed_at,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        idempotency_key=idempotency_key,
        metrics={
            "views": views,
            "reach": views - 10,
            "impressions": views + 20,
            "likes": 10,
            "comments": 2,
            "shares": 1,
            "saves": 3,
            "clicks": 5,
            "orders": 1,
            "revenue": 1990.0,
            "spend": 100.0,
            "watch_time_seconds": 800.0,
            "retention_rate": 0.65,
        },
    )


def test_cumulative_snapshots_are_idempotent_and_replace_instead_of_sum():
    first_seen = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    with SessionLocal() as db:
        user = make_user(db, slug="metric-upsert")
        _product, task = make_published_task(
            db,
            user,
            suffix="UPSERT",
            final_url="https://instagram.com/reel/SAFE-1001/",
        )
        service = SocialMetricIngestionService(db)

        created = service.ingest(observation(user, task, observed_at=first_seen, views=100))
        replay = service.ingest(observation(user, task, observed_at=first_seen, views=100))
        updated = service.ingest(
            replace(
                observation(
                    user,
                    task,
                    observed_at=first_seen + timedelta(hours=1),
                    views=150,
                    source_type="official_connector",
                    source_ref="meta-connection-primary",
                    idempotency_key="metric-observation-2",
                ),
                metrics={"views": 150},
            )
        )
        commerce_update = service.ingest(
            replace(
                observation(
                    user,
                    task,
                    observed_at=first_seen + timedelta(minutes=30),
                    views=100,
                    source_type="manual_csv",
                    source_ref="commerce-report-july",
                    idempotency_key="metric-observation-commerce",
                ),
                metrics={"orders": 2, "revenue": 2500.0},
            )
        )
        stale = service.ingest(
            observation(
                user,
                task,
                observed_at=first_seen - timedelta(minutes=30),
                views=80,
                source_type="manual_csv",
                source_ref="manual-backfill-july",
                idempotency_key="metric-observation-older",
            )
        )

        assert (created.status, replay.status, updated.status, commerce_update.status, stale.status) == (
            "created",
            "unchanged",
            "updated",
            "updated",
            "stale",
        )
        assert len({created.metric_id, replay.metric_id, updated.metric_id, commerce_update.metric_id, stale.metric_id}) == 1
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1
        metric = db.get(models.DestinationPostMetric, created.metric_id)
        assert metric.views == 150
        assert metric.likes == 10
        assert metric.orders == 2
        assert metric.revenue == 2500.0
        assert metric.destination_id == task.destination_id
        assert metric.campaign_id is None
        assert metric.raw_json["ingestion_v1"]["snapshot_semantics"] == "cumulative_replace_not_sum"
        assert metric.raw_json["ingestion_v1"]["unscoped_dimensions_omitted"] == [
            "campaign_id",
            "connection_id",
        ]
        assert metric.raw_json["ingestion_v1"]["source_type"] == "official_connector"
        assert metric.raw_json["ingestion_v1"]["field_provenance"]["views"]["source_type"] == "official_connector"
        assert metric.raw_json["ingestion_v1"]["field_provenance"]["orders"]["source_type"] == "manual_csv"
        assert metric.raw_json["ingestion_v1"]["observed_at"] == "2026-07-08T11:00:00Z"
        assert metric.engagement_rate == 0.106667
        assert metric.ctr == 0.033333
        assert db.scalar(
            select(func.count())
            .select_from(models.AuditLog)
            .where(models.AuditLog.action == "social_metric_observation")
        ) == 4


def test_concurrent_in_process_retries_create_one_canonical_row():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-concurrent")
        _product, task = make_published_task(
            db,
            user,
            suffix="CONCURRENT",
            final_url="https://instagram.com/reel/CONCURRENT-1001",
        )
        request = observation(
            user,
            task,
            observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            views=100,
            idempotency_key="metric-concurrent-observation",
        )

    def ingest_once() -> str:
        with SessionLocal() as worker_db:
            return SocialMetricIngestionService(worker_db).ingest(request).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _index: ingest_once(), range(2)))

    assert sorted(statuses) == ["created", "unchanged"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1
        assert db.scalar(
            select(func.count())
            .select_from(models.AuditLog)
            .where(models.AuditLog.action == "social_metric_observation")
        ) == 1


def test_overlapping_period_is_quarantined_instead_of_being_summed():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-overlap")
        _product, task = make_published_task(
            db,
            user,
            suffix="OVERLAP",
            final_url="https://instagram.com/reel/OVERLAP-1001",
        )
        service = SocialMetricIngestionService(db)
        first = service.ingest(
            observation(
                user,
                task,
                observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
                views=100,
                idempotency_key="metric-overlap-first",
            )
        )
        overlapping = replace(
            observation(
                user,
                task,
                observed_at=datetime(2026, 7, 10, 10, 0, tzinfo=UTC),
                views=180,
                idempotency_key="metric-overlap-second",
            ),
            period_start=date(2026, 7, 5),
            period_end=date(2026, 7, 9),
        )
        blocked = service.ingest(overlapping)

        assert first.status == "created"
        assert blocked.status == "quarantined"
        assert blocked.reason == "overlapping_metric_period_requires_reconciliation"
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1
        assert db.get(models.DestinationPostMetric, first.metric_id).views == 100


def test_same_idempotency_key_with_changed_payload_is_quarantined():
    seen_at = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
    with SessionLocal() as db:
        user = make_user(db, slug="metric-idempotency-conflict")
        _product, task = make_published_task(
            db,
            user,
            suffix="IDEMPOTENCY",
            final_url="https://instagram.com/reel/SAFE-2001",
        )
        service = SocialMetricIngestionService(db)
        created = service.ingest(
            observation(
                user,
                task,
                observed_at=seen_at,
                views=100,
                publishing_task_id=task.id,
                final_url="",
            )
        )
        conflict = service.ingest(
            observation(
                user,
                task,
                observed_at=seen_at + timedelta(hours=1),
                views=101,
                publishing_task_id=task.id,
                final_url="",
            )
        )

        assert created.status == "created"
        assert conflict.status == "quarantined"
        assert conflict.reason == "idempotency_key_reused_with_different_payload"
        assert db.get(models.DestinationPostMetric, created.metric_id).views == 100
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1


def test_ambiguous_final_url_is_quarantined_without_metric_or_double_audit():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-ambiguous")
        _product_one, task_one = make_published_task(
            db,
            user,
            suffix="AMB-ONE",
            final_url="https://instagram.com/reel/DUPLICATE",
        )
        make_published_task(
            db,
            user,
            suffix="AMB-TWO",
            final_url="https://instagram.com/reel/DUPLICATE/",
        )
        service = SocialMetricIngestionService(db)
        request = observation(
            user,
            task_one,
            observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
            views=100,
            publishing_task_id=None,
            external_post_id=None,
        )
        first = service.ingest(request)
        replay = service.ingest(request)

        assert first.status == "quarantined"
        assert first.reason == "ambiguous_attribution"
        assert first.details == {"candidate_count": 2}
        assert replay.quarantine_id == first.quarantine_id
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 0
        assert db.scalar(
            select(func.count())
            .select_from(models.AuditLog)
            .where(models.AuditLog.action == "social_metric_quarantined")
        ) == 1


def test_cross_org_and_unscoped_lineage_fail_closed_and_never_claim_legacy_product():
    with SessionLocal() as db:
        alpha = make_user(db, slug="metric-alpha")
        beta = make_user(db, slug="metric-beta")
        alpha_product, alpha_task = make_published_task(
            db,
            alpha,
            suffix="ALPHA",
            final_url="https://instagram.com/reel/ALPHA-ONLY",
        )
        legacy_product, legacy_task = make_published_task(
            db,
            beta,
            suffix="LEGACY",
            final_url="https://instagram.com/reel/LEGACY-UNSCOPED",
            scoped=False,
        )
        service = SocialMetricIngestionService(db)

        cross_org = service.ingest(
            observation(
                beta,
                alpha_task,
                observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
                views=50,
                publishing_task_id=alpha_task.id,
            )
        )
        unscoped = service.ingest(
            observation(
                beta,
                legacy_task,
                observed_at=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
                views=60,
                publishing_task_id=legacy_task.id,
                idempotency_key="metric-unscoped",
            )
        )
        alpha_metric = service.ingest(
            observation(
                alpha,
                alpha_task,
                observed_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
                views=70,
                publishing_task_id=alpha_task.id,
                idempotency_key="metric-alpha-owned",
            )
        )

        assert cross_org.reason == "unmatched_or_unowned_post"
        assert unscoped.reason == "unmatched_or_unowned_post"
        assert alpha_metric.status == "created"
        assert service.list_metrics(organization_id=beta.organization.id) == []
        assert [row.id for row in service.list_metrics(organization_id=alpha.organization.id)] == [
            alpha_metric.metric_id
        ]
        db.refresh(alpha_product)
        db.refresh(legacy_product)
        assert alpha_product.organization_id == alpha.organization.id
        assert legacy_product.organization_id is None
        beta_quarantine = service.list_quarantine(organization_id=beta.organization.id)
        assert len(beta_quarantine) == 2
        assert all(row.organization_id == beta.organization.id for row in beta_quarantine)


def test_destination_ownership_and_platform_must_match_the_owned_task():
    with SessionLocal() as db:
        alpha = make_user(db, slug="metric-destination-alpha")
        beta = make_user(db, slug="metric-destination-beta")
        _product, task = make_published_task(
            db,
            alpha,
            suffix="DESTINATION-SCOPE",
            final_url="https://instagram.com/reel/DESTINATION-SCOPE",
        )
        task.destination.organization_id = beta.organization.id
        db.commit()

        foreign_destination = SocialMetricIngestionService(db).ingest(
            observation(
                alpha,
                task,
                observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
                views=100,
                publishing_task_id=task.id,
            )
        )
        assert foreign_destination.reason == "unmatched_or_unowned_post"
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 0

        task.destination.organization_id = alpha.organization.id
        task.destination.platform = "youtube"
        db.commit()
        mismatched_platform = SocialMetricIngestionService(db).ingest(
            observation(
                alpha,
                task,
                observed_at=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
                views=100,
                publishing_task_id=task.id,
                idempotency_key="metric-destination-platform",
            )
        )
        assert mismatched_platform.reason == "unmatched_or_unowned_post"
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 0


def test_existing_legacy_metric_collision_is_quarantined_and_not_overwritten():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-legacy-collision")
        product, task = make_published_task(
            db,
            user,
            suffix="LEGACY-COLLISION",
            final_url="https://instagram.com/reel/LEGACY-COLLISION",
        )
        legacy = models.DestinationPostMetric(
            destination_id=task.destination_id,
            publishing_task_id=task.id,
            product_id=product.id,
            sku=product.sku,
            platform="instagram",
            posted_url=task.final_url,
            provider_post_id="ig-post-1001",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 7),
            views=999,
            raw_json={"source": "old_unsafe_import"},
        )
        db.add(legacy)
        db.commit()

        result = SocialMetricIngestionService(db).ingest(
            observation(
                user,
                task,
                observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
                views=100,
            )
        )
        db.refresh(legacy)
        assert result.status == "quarantined"
        assert result.reason == "legacy_metric_requires_manual_review"
        assert legacy.views == 999
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1


def test_placeholder_post_url_cannot_become_a_measurable_social_result():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-placeholder")
        _product, task = make_published_task(
            db,
            user,
            suffix="PLACEHOLDER",
            final_url="https://mock.social/posts/not-a-real-post",
        )
        result = SocialMetricIngestionService(db).ingest(
            observation(
                user,
                task,
                observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
                views=1_000_000,
                publishing_task_id=task.id,
            )
        )

        assert result.status == "quarantined"
        assert result.reason == "publishing_task_final_url_is_not_a_real_platform_post"
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 0


def test_api_derives_identity_from_public_user_and_rejects_spoofed_scope():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-api")
        _product, task = make_published_task(
            db,
            user,
            suffix="API",
            final_url="https://instagram.com/reel/API-SAFE",
        )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_public_user] = lambda: user
    payload = {
        "source_type": "platform_export",
        "source_ref": "instagram-export-api",
        "platform": "instagram",
        "external_post_id": "api-post-1",
        "final_url": task.final_url,
        "publishing_task_id": task.id,
        "observed_at": "2026-07-08T10:00:00Z",
        "period_start": "2026-07-01",
        "period_end": "2026-07-07",
        "idempotency_key": "api-observation-1",
        "metrics": {"views": 100, "likes": 5},
    }
    with TestClient(app) as client:
        accepted = client.post("/api/social-metrics", json=payload)
        spoofed = client.post(
            "/api/social-metrics",
            json={**payload, "organization_id": 999, "user_profile_id": 999},
        )
        listed = client.get("/api/social-metrics")

    assert accepted.status_code == 202
    assert accepted.json()["status"] == "created"
    assert spoofed.status_code == 422
    assert len(listed.json()) == 1
    assert listed.json()[0]["publishing_task_id"] == task.id
    with SessionLocal() as db:
        metric = db.get(models.DestinationPostMetric, accepted.json()["metric_id"])
        assert metric.raw_json["ingestion_v1"]["organization_id"] == user.organization.id
        assert metric.raw_json["ingestion_v1"]["actor_user_profile_id"] == user.profile.id


def test_safe_metric_reads_reject_inactive_membership():
    with SessionLocal() as db:
        user = make_user(db, slug="metric-inactive-reader")
        user.membership.status = "inactive"
        db.commit()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_public_user] = lambda: user
    with TestClient(app) as client:
        metrics = client.get("/api/social-metrics")
        quarantine = client.get("/api/social-metrics/quarantine")

    assert metrics.status_code == 403
    assert metrics.json()["detail"] == "active_membership_required"
    assert quarantine.status_code == 403


def test_public_mode_rejects_anonymous_before_dev_user_auto_provisioning():
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/api/social-metrics")

    assert response.status_code == 401
    assert response.json()["detail"] == "authentication_required"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.UserProfile)) == 0
        assert db.scalar(select(func.count()).select_from(models.Membership)) == 0


@pytest.mark.parametrize(
    ("public_mode", "auth_required"),
    [("true", "false"), ("false", "true")],
)
def test_strict_mode_blocks_legacy_global_metric_read_and_import(public_mode: str, auth_required: str):
    with SessionLocal() as db:
        user = make_user(db, slug="metric-legacy-guard")
        _product, task = make_published_task(
            db,
            user,
            suffix="LEGACY-GUARD",
            final_url="https://instagram.com/reel/LEGACY-GUARD",
        )
        created = SocialMetricIngestionService(db).ingest(
            observation(
                user,
                task,
                observed_at=datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
                views=100,
            )
        )

    os.environ["QVF_PUBLIC_PILOT_MODE"] = public_mode
    os.environ["QVF_AUTH_REQUIRED"] = auth_required
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(legacy_api_router)
    with TestClient(app) as client:
        leaked_read = client.get("/api/destination-connectors/metrics")
        unsafe_import = client.post(
            "/api/destination-connectors/metrics/import-csv",
            files={
                "file": (
                    "foreign.csv",
                    (
                        "platform,posted_url,period_start,period_end,views\n"
                        f"instagram,{task.final_url},2026-07-01,2026-07-07,999999\n"
                    ),
                    "text/csv",
                )
            },
        )
        unsafe_intake = client.post(
            "/api/metrics-intake/import-csv",
            json={
                "csv_text": "platform,posted_url,period_start,period_end,views\ninstagram,https://instagram.com/reel/x,2026-07-01,2026-07-07,999\n",
                "source_type": "manual_csv",
            },
        )
        tower_read = client.get("/api/destination-control-tower/campaigns/1/snapshot")
        campaign_read = client.get("/api/campaign-performance/1/summary")

    expected_detail = {
        "code": "organization_safe_metrics_route_required",
        "message": "This legacy metrics route has no provable organization scope.",
        "replacement": "/api/social-metrics",
    }
    assert leaked_read.status_code == 409
    assert leaked_read.json()["detail"] == expected_detail
    assert unsafe_import.status_code == 409
    assert unsafe_import.json()["detail"] == expected_detail
    assert unsafe_intake.status_code == 409
    assert unsafe_intake.json()["detail"] == expected_detail
    assert tower_read.status_code == 409
    assert campaign_read.status_code == 409
    with SessionLocal() as db:
        metric = db.get(models.DestinationPostMetric, created.metric_id)
        assert metric.views == 100
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1
        assert db.scalar(
            select(func.count())
            .select_from(models.AuditLog)
            .where(models.AuditLog.action == "metrics_import")
        ) == 0
