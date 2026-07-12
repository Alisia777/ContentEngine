from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.media_storage import LocalStorage, MediaArtifactService
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.publishing import ManualUploadProvider, PublishingPackageService, PublishingScheduler
from app.publishing.errors import (
    PublishingAuthorizationError,
    PublishingSourceNotFound,
    PublishingSourceStateError,
)
from app.routers import media_library


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    with TestSession() as session:
        yield session


def _scope(db: Session, *, slug: str, role: str = "owner"):
    organization = models.Organization(name=slug, slug=slug, status="active", settings_json={})
    profile = models.UserProfile(
        supabase_user_id=f"artifact-publishing:{slug}:{role}",
        email=f"{role}@{slug}.test",
        display_name=f"{role.title()} {slug}",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add_all([organization, profile])
    db.flush()
    membership = models.Membership(
        organization_id=organization.id,
        user_profile_id=profile.id,
        role=role,
        status="active",
        permissions_json=[],
    )
    product = models.Product(
        organization_id=organization.id,
        sku=f"SKU-{slug}",
        brand="ALTEA",
        title=f"Product {slug}",
        category="beauty",
        product_url="https://shop.test/product",
        attributes_json={},
        benefits_json=["Visible benefit"],
        images_json=[],
        reviews_json=[],
        restrictions_json=[],
    )
    db.add_all([membership, product])
    db.commit()
    return organization, profile, membership, product


def _artifact(
    db: Session,
    tmp_path: Path,
    organization,
    profile,
    product,
    *,
    kind: str = "master_video",
):
    backend = LocalStorage(
        tmp_path / f"objects-{organization.id}",
        bucket="private-media",
        signing_secret="cloud-artifact-test-signing-secret",
        public_base_url="https://media.test/local",
    )
    artifact = MediaArtifactService(db, {backend.name: backend}).store_bytes(
        organization_id=organization.id,
        created_by_user_profile_id=profile.id,
        backend_name=backend.name,
        kind=kind,
        content=b"durable-cloud-video",
        mime_type="video/mp4",
        original_filename="approved.mp4",
        product_id=product.id,
        metadata={"provider": "test"},
    )
    return artifact, backend


def _destination(db: Session, organization, *, platform: str = "instagram"):
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="ALTEA",
        platform=platform,
        name=f"{platform} owned",
        status="active",
        posting_mode="manual",
        auth_status="manual_only",
        allowed_formats_json=["vertical_video"],
        daily_limit=2,
        weekly_limit=5,
    )
    db.add(destination)
    db.commit()
    return destination


def test_ready_cloud_artifact_creates_one_approved_package_without_local_path_or_capability(
    db: Session,
    tmp_path: Path,
):
    organization, profile, _membership, product = _scope(db, slug="cloud-package")
    artifact, _backend = _artifact(
        db,
        tmp_path,
        organization,
        profile,
        product,
        kind="provider_output",
    )
    service = PublishingPackageService(db)

    first = service.create_from_media_artifact(
        public_id=artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=profile.id,
        platform="Instagram",
        confirm_human_review=True,
    )
    repeated = service.create_from_media_artifact(
        media_artifact_id=artifact.id,
        organization_id=organization.id,
        actor_user_profile_id=profile.id,
        platform="instagram",
        confirm_human_review=True,
    )

    assert repeated.id == first.id
    assert first.organization_id == organization.id
    assert first.media_artifact_id == artifact.id
    assert first.product_id == product.id
    assert first.video_job_id is None
    assert first.video_file_path is None
    assert first.status == first.review_status == "approved"
    assert first.metadata_json["human_review"]["reviewer_role"] == "owner"
    assert db.query(models.PublishingPackage).count() == 1
    assert db.query(models.Review).count() == 1
    persisted = json.dumps(first.metadata_json).casefold()
    assert "signed_url" not in persisted
    assert "signature=" not in persisted
    assert "secret" not in persisted


@pytest.mark.parametrize("role", ["owner", "admin", "reviewer"])
def test_artifact_approval_roles_are_authoritative_memberships(
    db: Session,
    tmp_path: Path,
    role: str,
):
    organization, profile, _membership, product = _scope(db, slug=f"role-{role}", role=role)
    artifact, _backend = _artifact(db, tmp_path, organization, profile, product)

    package = PublishingPackageService(db).create_from_media_artifact(
        public_id=artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=profile.id,
        platform="telegram",
        confirm_human_review=True,
    )
    assert package.metadata_json["human_review"]["reviewer_role"] == role


def test_viewer_missing_confirmation_cross_tenant_and_archived_artifact_are_blocked(
    db: Session,
    tmp_path: Path,
):
    organization, owner, membership, product = _scope(db, slug="blocked-source")
    artifact, _backend = _artifact(db, tmp_path, organization, owner, product)
    service = PublishingPackageService(db)

    with pytest.raises(PublishingSourceStateError):
        service.create_from_media_artifact(
            public_id=artifact.public_id,
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            platform="instagram",
            confirm_human_review=False,
        )

    membership.role = "viewer"
    db.commit()
    with pytest.raises(PublishingAuthorizationError):
        service.create_from_media_artifact(
            public_id=artifact.public_id,
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            platform="instagram",
            confirm_human_review=True,
        )

    membership.role = "owner"
    artifact.status = "ready"
    artifact.archived_at = None
    artifact.kind = "video_preview"
    db.commit()
    with pytest.raises(PublishingSourceStateError):
        service.create_from_media_artifact(
            public_id=artifact.public_id,
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            platform="instagram",
            confirm_human_review=True,
        )

    other_org, other_owner, _other_membership, _other_product = _scope(db, slug="other-source")
    with pytest.raises(PublishingSourceNotFound):
        service.create_from_media_artifact(
            public_id=artifact.public_id,
            organization_id=other_org.id,
            actor_user_profile_id=other_owner.id,
            platform="instagram",
            confirm_human_review=True,
        )

    membership.role = "owner"
    artifact.status = "archived"
    artifact.archived_at = models.utcnow()
    db.commit()
    with pytest.raises(PublishingSourceStateError):
        service.create_from_media_artifact(
            public_id=artifact.public_id,
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            platform="instagram",
            confirm_human_review=True,
        )


def test_scheduler_accepts_ready_artifact_and_legacy_file_but_rejects_invalid_artifact_fallback(
    db: Session,
    tmp_path: Path,
):
    organization, owner, _membership, product = _scope(db, slug="scheduler-source")
    artifact, _backend = _artifact(db, tmp_path, organization, owner, product)
    destination = _destination(db, organization)
    service = PublishingPackageService(db)
    package = service.create_from_media_artifact(
        public_id=artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        platform="instagram",
        confirm_human_review=True,
    )
    scheduler = PublishingScheduler(db)

    cloud_validation = scheduler.validate(package, destination, datetime(2026, 7, 14, 12, 0))
    assert cloud_validation["allowed"] is True
    assert cloud_validation["media_source"] == "media_artifact"

    legacy_file = tmp_path / "legacy.mp4"
    legacy_file.write_bytes(b"legacy-video")
    legacy = models.PublishingPackage(
        video_job_id=None,
        product_id=product.id,
        brand=product.brand,
        target_platform="instagram",
        title="Legacy",
        hashtags_json=[],
        video_file_path=str(legacy_file),
        metadata_json={},
        review_status="approved",
        status="approved",
    )
    db.add(legacy)
    db.commit()
    legacy_validation = scheduler.validate(legacy, destination, datetime(2026, 7, 15, 12, 0))
    assert legacy_validation["allowed"] is True
    assert legacy_validation["media_source"] == "legacy_local_file"

    package.video_file_path = str(legacy_file)
    artifact.kind = "video_preview"
    db.commit()
    invalid = scheduler.validate(package, destination, datetime(2026, 7, 16, 12, 0))
    assert invalid["allowed"] is False
    assert invalid["media_source"] == "media_artifact"


def test_manual_upload_payload_uses_internal_artifact_route_not_signed_url(
    db: Session,
    tmp_path: Path,
):
    organization, owner, _membership, product = _scope(db, slug="manual-cloud")
    artifact, backend = _artifact(db, tmp_path, organization, owner, product)
    destination = _destination(db, organization)
    package = PublishingPackageService(db).create_from_media_artifact(
        public_id=artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        platform="instagram",
        confirm_human_review=True,
    )
    task = PublishingScheduler(db).schedule(
        package=package,
        destination=destination,
        scheduled_at=datetime(2026, 7, 14, 12, 0),
    )
    task = ManualUploadProvider(db).run(task)
    payload = task.raw_response_json["manual_upload"]

    assert payload["video_file_path"] is None
    assert payload["media_artifact"] == {
        "public_id": artifact.public_id,
        "download_path": f"/media-library/{artifact.public_id}/access?download=true",
    }
    persisted = json.dumps(task.raw_response_json).casefold()
    assert backend.signing_secret.decode("utf-8").casefold() not in persisted
    assert "signature=" not in persisted


def test_media_library_bridge_is_role_scoped_and_idempotent(db: Session, tmp_path: Path):
    organization, owner, membership, product = _scope(db, slug="media-ui")
    artifact, backend = _artifact(db, tmp_path, organization, owner, product)
    artifact_service = MediaArtifactService(db, {backend.name: backend})
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(media_library.router)

    def override_db():
        yield db

    app.dependency_overrides[media_library.get_db] = override_db
    app.dependency_overrides[media_library.get_media_artifact_service] = lambda: artifact_service
    app.dependency_overrides[get_current_public_user] = lambda: PublicPilotUser(
        profile=owner,
        organization=organization,
        membership=membership,
    )
    client = TestClient(app)

    page = client.get("/media-library")
    assert page.status_code == 200
    assert f"/media-library/{artifact.public_id}/publishing-package" in page.text
    first = client.post(
        f"/media-library/{artifact.public_id}/publishing-package",
        data={"platform": "instagram", "confirm_human_review": "true"},
        follow_redirects=False,
    )
    repeated = client.post(
        f"/media-library/{artifact.public_id}/publishing-package",
        data={"platform": "instagram", "confirm_human_review": "true"},
        follow_redirects=False,
    )
    assert first.status_code == repeated.status_code == 303
    assert first.headers["location"] == repeated.headers["location"]
    assert db.query(models.PublishingPackage).count() == 1
    success_page = client.get(first.headers["location"])
    assert success_page.status_code == 200
    assert 'href="/creator-operations?tab=placement"' in success_page.text
    assert 'href="/publishing"' not in success_page.text

    membership.role = "viewer"
    db.commit()
    forbidden = client.post(
        f"/media-library/{artifact.public_id}/publishing-package",
        data={"platform": "telegram", "confirm_human_review": "true"},
    )
    assert forbidden.status_code == 403
