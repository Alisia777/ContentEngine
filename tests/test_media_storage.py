from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.media_storage import (
    LocalStorage,
    MediaArtifactError,
    MediaArtifactOwnershipError,
    MediaArtifactService,
    ProductUGCMediaArtifactSyncService,
    S3CompatibleStorage,
    StorageSecurityError,
    SupabaseStorage,
    build_storage_backend,
)
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers import media_library


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    with TestSession() as session:
        yield session


def create_scope(db: Session, *, slug: str):
    organization = models.Organization(
        name=slug,
        slug=slug,
        status="active",
        settings_json={},
    )
    user = models.UserProfile(
        supabase_user_id=f"media:{slug}",
        email=f"owner@{slug}.test",
        display_name=f"Owner {slug}",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add_all([organization, user])
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=user.id,
            role="owner",
            status="active",
            permissions_json=[],
        )
    )
    product = models.Product(
        organization_id=organization.id,
        sku=f"SKU-{slug}",
        brand="ALTEA",
        title=f"Product {slug}",
        attributes_json={},
        benefits_json=[],
        images_json=[],
        reviews_json=[],
        restrictions_json=[],
    )
    db.add(product)
    db.commit()
    return organization, user, product


def local_backend(tmp_path: Path, *, now: datetime | None = None) -> LocalStorage:
    instant = now or datetime(2026, 7, 12, 8, 0, tzinfo=UTC)
    return LocalStorage(
        tmp_path,
        bucket="private-media",
        signing_secret="test-signing-secret-at-least-16",
        public_base_url="https://media.test/local",
        clock=lambda: instant,
    )


def test_local_storage_rejects_escape_and_uses_expiring_signature(tmp_path: Path):
    backend = local_backend(tmp_path)
    stored = backend.put_bytes(
        "organizations/00000001/master_video/abc.mp4",
        b"video-bytes",
        mime_type="video/mp4",
    )

    assert stored.sha256
    assert backend.read_bytes(stored.key) == b"video-bytes"
    with pytest.raises(StorageSecurityError):
        backend.put_bytes("../../outside.mp4", b"x", mime_type="video/mp4")

    signed = backend.create_signed_get_url(
        stored.key,
        expires_seconds=60,
        download_filename="result.mp4",
    )
    params = parse_qs(urlsplit(signed).query)
    assert backend.validate_signed_get(
        stored.key,
        expires_at=int(params["expires"][0]),
        disposition=params["disposition"][0],
        signature=params["signature"][0],
    )
    assert not backend.validate_signed_get(
        stored.key,
        expires_at=int(params["expires"][0]),
        disposition=params["disposition"][0],
        signature="0" * 64,
    )


def test_artifact_service_persists_tenant_metadata_but_never_signed_url(db: Session, tmp_path: Path):
    organization, user, product = create_scope(db, slug="alpha")
    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})
    retention_until = datetime(2027, 1, 1)

    artifact = service.store_bytes(
        organization_id=organization.id,
        created_by_user_profile_id=user.id,
        backend_name="local",
        kind="master_video",
        content=b"canonical-video",
        mime_type="video/mp4",
        original_filename="campaign.mp4",
        product_id=product.id,
        retention_class="master_365d",
        retention_until=retention_until,
        metadata={"provider": "runway"},
    )

    assert artifact.object_key.startswith(f"organizations/{organization.id:08d}/")
    assert artifact.product_id == product.id
    assert artifact.created_by_user_profile_id == user.id
    assert artifact.retention_until == retention_until
    assert artifact.sha256
    signed = service.signed_get_url(
        artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=user.id,
        expires_seconds=120,
        download=True,
    )
    assert "signature=" in signed

    db.expire_all()
    persisted = db.scalar(select(models.MediaArtifact).where(models.MediaArtifact.id == artifact.id))
    persisted_text = " ".join(
        [
            persisted.object_key,
            str(persisted.metadata_json),
            str(persisted.object_version),
            str(persisted.etag),
        ]
    )
    assert "signature=" not in persisted_text
    assert "https://media.test" not in persisted_text


def test_store_bytes_keeps_committed_object_when_refresh_fails(
    db: Session,
    tmp_path: Path,
    monkeypatch,
):
    organization, user, product = create_scope(db, slug="refresh-store-bytes")
    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})
    content = b"committed-before-refresh-failure"

    def fail_refresh(_instance, *_args, **_kwargs):
        raise RuntimeError("simulated refresh failure after commit")

    monkeypatch.setattr(db, "refresh", fail_refresh)
    with pytest.raises(RuntimeError, match="refresh failure after commit"):
        service.store_bytes(
            organization_id=organization.id,
            created_by_user_profile_id=user.id,
            backend_name="local",
            kind="master_video",
            content=content,
            mime_type="video/mp4",
            product_id=product.id,
        )

    with TestSession() as verification_db:
        persisted = verification_db.scalar(
            select(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == organization.id,
                models.MediaArtifact.kind == "master_video",
            )
        )
        assert persisted is not None
        object_key = persisted.object_key

    assert backend.read_bytes(object_key) == content


def test_idempotent_store_keeps_committed_object_when_refresh_fails(
    db: Session,
    tmp_path: Path,
    monkeypatch,
):
    organization, user, product = create_scope(db, slug="refresh-idempotent")
    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})
    source = tmp_path / "worker-output.mp4"
    content = b"durable-idempotent-worker-output"
    source.write_bytes(content)
    idempotency_key = "refresh-failure-after-durable-commit"

    def fail_refresh(_instance, *_args, **_kwargs):
        raise RuntimeError("simulated refresh failure after commit")

    monkeypatch.setattr(db, "refresh", fail_refresh)
    with pytest.raises(RuntimeError, match="refresh failure after commit"):
        service.store_file_idempotent(
            organization_id=organization.id,
            created_by_user_profile_id=user.id,
            backend_name="local",
            idempotency_key=idempotency_key,
            kind="master_video",
            source=source,
            mime_type="video/mp4",
            product_id=product.id,
        )

    with TestSession() as verification_db:
        persisted = verification_db.scalar(
            select(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == organization.id,
                models.MediaArtifact.idempotency_key == idempotency_key,
            )
        )
        assert persisted is not None
        persisted_id = persisted.id
        object_key = persisted.object_key
        retry = MediaArtifactService(
            verification_db,
            {backend.name: backend},
        ).store_file_idempotent(
            organization_id=organization.id,
            created_by_user_profile_id=user.id,
            backend_name="local",
            idempotency_key=idempotency_key,
            kind="master_video",
            source=source,
            mime_type="video/mp4",
            product_id=product.id,
        )
        assert retry.id == persisted_id

    assert backend.read_bytes(object_key) == content


def test_signed_get_fails_closed_across_organizations_and_corrupt_prefix(
    db: Session,
    tmp_path: Path,
):
    organization_a, user_a, product_a = create_scope(db, slug="tenant-a")
    organization_b, user_b, _product_b = create_scope(db, slug="tenant-b")
    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})
    artifact = service.store_bytes(
        organization_id=organization_a.id,
        created_by_user_profile_id=user_a.id,
        backend_name="local",
        kind="provider_output",
        content=b"private-video",
        mime_type="video/mp4",
        product_id=product_a.id,
    )

    with pytest.raises(MediaArtifactOwnershipError):
        service.signed_get_url(
            artifact.public_id,
            organization_id=organization_b.id,
            actor_user_profile_id=user_b.id,
        )

    artifact.object_key = (
        f"organizations/{organization_b.id:08d}/products/unassigned/drafts/unassigned/"
        f"videos/unassigned/provider_output/{artifact.public_id}.mp4"
    )
    db.commit()
    with pytest.raises(MediaArtifactOwnershipError):
        service.signed_get_url(
            artifact.public_id,
            organization_id=organization_a.id,
            actor_user_profile_id=user_a.id,
        )


def test_artifact_links_require_same_tenant_and_metadata_rejects_capabilities(
    db: Session,
    tmp_path: Path,
):
    organization_a, user_a, _product_a = create_scope(db, slug="links-a")
    _organization_b, _user_b, product_b = create_scope(db, slug="links-b")
    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})

    with pytest.raises(MediaArtifactOwnershipError):
        service.store_bytes(
            organization_id=organization_a.id,
            created_by_user_profile_id=user_a.id,
            backend_name="local",
            kind="product_reference",
            content=b"image",
            mime_type="image/png",
            product_id=product_b.id,
        )
    with pytest.raises(MediaArtifactError):
        service.store_bytes(
            organization_id=organization_a.id,
            created_by_user_profile_id=user_a.id,
            backend_name="local",
            kind="generation_report",
            content=b"{}",
            mime_type="application/json",
            metadata={"provider": {"result": "https://secret.test/out?signature=x"}},
        )
    assert list((tmp_path / backend.bucket).rglob("*")) == []


def test_archive_restore_and_creator_filter_are_tenant_scoped(db: Session, tmp_path: Path):
    organization, user, product = create_scope(db, slug="library")
    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})
    first = service.store_bytes(
        organization_id=organization.id,
        created_by_user_profile_id=user.id,
        backend_name="local",
        kind="master_video",
        content=b"one",
        mime_type="video/mp4",
        product_id=product.id,
    )
    service.store_bytes(
        organization_id=organization.id,
        created_by_user_profile_id=user.id,
        backend_name="local",
        kind="thumbnail",
        content=b"two",
        mime_type="image/png",
        product_id=product.id,
    )

    archived = service.archive(
        first.public_id,
        organization_id=organization.id,
        actor_user_profile_id=user.id,
    )
    assert archived.status == "archived"
    assert len(
        service.list_owned(
            organization_id=organization.id,
            product_id=product.id,
            created_by_user_profile_id=user.id,
            include_archived=False,
        )
    ) == 1
    restored = service.restore(
        first.public_id,
        organization_id=organization.id,
        actor_user_profile_id=user.id,
    )
    assert restored.status == "ready"


def test_s3_presigned_get_is_ttl_bounded_and_never_contains_secret():
    now = datetime(2026, 7, 12, 8, 30, tzinfo=UTC)
    backend = S3CompatibleStorage(
        endpoint_url="https://objects.example.test",
        bucket="private-media",
        region="ru-central1",
        access_key_id="AKIAEXAMPLE",
        secret_access_key="super-secret-signing-key",
        clock=lambda: now,
    )

    signed = backend.create_signed_get_url(
        "organizations/00000001/master_video/a file.mp4",
        expires_seconds=300,
        download_filename="result.mp4",
    )
    query = parse_qs(urlsplit(signed).query)
    assert query["X-Amz-Expires"] == ["300"]
    assert query["X-Amz-SignedHeaders"] == ["host"]
    assert query["X-Amz-Signature"][0]
    assert "super-secret-signing-key" not in signed


def test_remote_backends_stream_worker_file_with_integrity_metadata(tmp_path: Path):
    source = tmp_path / "large-worker-output.mp4"
    source.write_bytes(b"streamed-video-chunk" * 1000)
    seen: dict[str, object] = {}

    def s3_handler(request: httpx.Request) -> httpx.Response:
        seen["s3_body"] = request.read()
        seen["s3_sha"] = request.headers["x-amz-meta-sha256"]
        return httpx.Response(200, headers={"etag": '"etag-1"'})

    s3 = S3CompatibleStorage(
        endpoint_url="https://objects.example.test",
        bucket="private-media",
        region="us-east-1",
        access_key_id="AKIAEXAMPLE",
        secret_access_key="secret",
        client=httpx.Client(transport=httpx.MockTransport(s3_handler)),
    )
    stored = s3.put_file(
        "organizations/00000001/master_video/output.mp4",
        source,
        mime_type="video/mp4",
    )
    assert seen["s3_body"] == source.read_bytes()
    assert seen["s3_sha"] == stored.sha256
    assert stored.size_bytes == source.stat().st_size

    def supabase_handler(request: httpx.Request) -> httpx.Response:
        seen["supabase_body"] = request.read()
        seen["supabase_sha"] = json.loads(
            base64.b64decode(request.headers["x-metadata"]).decode("utf-8")
        )["sha256"]
        return httpx.Response(200, json={"id": "object-version-1"})

    supabase = SupabaseStorage(
        project_url="https://project.supabase.co",
        bucket="private-media",
        service_role_key="service-role",
        client=httpx.Client(transport=httpx.MockTransport(supabase_handler)),
    )
    supabase_stored = supabase.put_file(
        "organizations/00000001/master_video/output.mp4",
        source,
        mime_type="video/mp4",
    )
    assert seen["supabase_body"] == source.read_bytes()
    assert seen["supabase_sha"] == supabase_stored.sha256


def test_supabase_head_reads_checksum_from_user_metadata():
    sha256 = "c" * 64

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/object/info/" in str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "object-version-1",
                "metadata": {"size": 42, "mimetype": "image/png"},
                "user_metadata": {"sha256": sha256},
            },
        )

    backend = SupabaseStorage(
        project_url="https://project.supabase.co",
        bucket="private-media",
        service_role_key="service-role",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    stored = backend.head("organizations/00000001/product_reference/input.png")

    assert stored is not None
    assert stored.sha256 == sha256
    assert stored.size_bytes == 42


def test_supabase_backend_requests_short_lived_signed_url_without_leaking_service_key():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "signedURL": "/storage/v1/object/sign/private-media/organizations/1/video.mp4?token=ephemeral"
            },
        )

    backend = SupabaseStorage(
        project_url="https://project.supabase.co",
        bucket="private-media",
        service_role_key="server-only-service-role-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    signed = backend.create_signed_get_url(
        "organizations/00000001/master_video/video.mp4",
        expires_seconds=180,
    )

    assert signed.startswith("https://project.supabase.co/storage/v1/object/sign/")
    assert "token=ephemeral" in signed
    assert "server-only-service-role-key" not in signed
    assert requests[0].headers["authorization"] == "Bearer server-only-service-role-key"
    assert requests[0].method == "POST"


def test_backend_factory_refuses_local_or_implicit_storage_in_production(tmp_path: Path):
    settings = SimpleNamespace(media_root=tmp_path, local_session_secret="session-secret-for-tests")
    with pytest.raises(StorageSecurityError):
        build_storage_backend(
            settings=settings,
            environ={"QVF_DEPLOYMENT_ENV": "production"},
        )
    with pytest.raises(StorageSecurityError):
        build_storage_backend(
            settings=settings,
            environ={"QVF_DEPLOYMENT_ENV": "production", "QVF_STORAGE_BACKEND": "local"},
        )

    backend = build_storage_backend(settings=settings, environ={"QVF_DEPLOYMENT_ENV": "test"})
    assert isinstance(backend, LocalStorage)


def test_worker_sync_and_library_survive_without_worker_filesystem(
    db: Session,
    tmp_path: Path,
    monkeypatch,
):
    organization, user, product = create_scope(db, slug="worker-library")
    membership = db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == user.id,
        )
    )
    worker_dir = tmp_path / "worker-ephemeral"
    worker_dir.mkdir()
    output = worker_dir / "provider-output.mp4"
    report = worker_dir / "generation.json"
    output.write_bytes(b"real-provider-video-from-worker")
    report.write_text('{"status":"succeeded"}', encoding="utf-8")
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        sku=product.sku,
        variant_key="exact-variant",
        status="generated_needs_human_review",
        recipe_version="2026-06",
        platform="Instagram Reels",
        language="ru",
        character_image_path=str(worker_dir / "creator.png"),
        character_image_filename="creator.png",
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_asset_ids_json=[],
        product_info="Exact product",
        user_concept="Creator demonstrates exact product",
        creative_inputs_json={},
        duration_seconds=15,
        ratio="720:1280",
        audio_enabled=True,
        estimated_credits=100,
        provider_payload_preview_json={},
        blockers_json=[],
        warnings_json=[],
        provider_task_id="runway-task-1",
        provider_status="SUCCEEDED",
        local_output_paths_json=[output.as_posix()],
        generation_report_path=report.as_posix(),
        human_review_status="needs_human_review",
        publishing_readiness="blocked",
    )
    db.add(draft)
    db.flush()
    generation_job = models.ProductUGCGenerationJob(
        draft_id=draft.id,
        organization_id=organization.id,
        requested_by_user_profile_id=user.id,
        idempotency_key=f"product-ugc-paid:d{draft.id}:v1",
        status="downloading",
        attempt_count=1,
        max_attempts=5,
        next_attempt_at=models.utcnow(),
        provider="runway_product_ugc_recipe",
        provider_task_id="runway-task-1",
        provider_status="SUCCEEDED",
        metadata_json={},
    )
    db.add(generation_job)
    batch = models.MassOperationBatch(
        organization_id=organization.id,
        created_by_user_profile_id=user.id,
        operation_type="generation",
        name="Worker integration batch",
        idempotency_key="media-worker-batch-1",
        status="queued",
        dry_run=False,
        total_requested=1,
        total_accepted=1,
        total_failed=0,
        parameters_json={},
        results_json=[],
        errors_json=[],
    )
    db.add(batch)
    db.flush()
    generation_job.metadata_json = {"mass_operation_batch_id": batch.id}
    task = models.CreatorTask(
        organization_id=organization.id,
        assignee_user_profile_id=user.id,
        created_by_user_profile_id=user.id,
        mass_operation_batch_id=batch.id,
        product_id=product.id,
        product_ugc_recipe_draft_id=draft.id,
        task_type="review_generated_video",
        title="Review generated video",
        status="todo",
        priority=3,
        idempotency_key="media-worker-review-task-1",
    )
    db.add(task)
    db.flush()
    batch.results_json = [
        {
            "generation_job_id": generation_job.id,
            "creator_task_id": task.id,
            "status": "queued",
        }
    ]
    db.commit()

    backend = LocalStorage(
        tmp_path / "object-store",
        bucket="private-media",
        signing_secret="integration-signing-secret-123",
        public_base_url="/media-library/local",
    )
    sync_service = ProductUGCMediaArtifactSyncService(
        db,
        {backend.name: backend},
    )
    records = sync_service.sync_generation_job(generation_job.id)
    repeated = sync_service.sync_generation_job(generation_job.id)
    assert [item.public_id for item in repeated] == [item.public_id for item in records]
    assert {item.kind for item in records} == {"master_video", "generation_report"}
    assert db.query(models.MediaArtifact).count() == 2

    generation_job.status = "succeeded"
    db.commit()
    sync_service.mark_creator_work_ready(generation_job.id, records)
    db.refresh(task)
    db.refresh(batch)
    assert task.media_artifact_id == next(
        item.id for item in records if item.kind == "master_video"
    )
    assert task.result_json["media_artifact_public_id"]
    assert batch.status == "completed"
    assert batch.results_json[0]["status"] == "ready_for_review"

    output.unlink()
    report.unlink()
    assert not output.exists()

    artifact_service = MediaArtifactService(db, {backend.name: backend})
    monkeypatch.setattr(media_library, "get_storage_backends", lambda: {backend.name: backend})
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(media_library.router)

    def override_db():
        yield db

    app.dependency_overrides[media_library.get_db] = override_db
    app.dependency_overrides[media_library.get_media_artifact_service] = lambda: artifact_service
    app.dependency_overrides[get_current_public_user] = lambda: PublicPilotUser(
        profile=user,
        organization=organization,
        membership=membership,
    )
    client = TestClient(app)
    page = client.get("/media-library")
    assert page.status_code == 200
    assert records[0].public_id in page.text
    assert "signature=" not in page.text

    redirect = client.get(
        f"/media-library/{records[0].public_id}/access",
        follow_redirects=False,
    )
    assert redirect.status_code == 307
    assert "signature=" in redirect.headers["location"]
    playback = client.get(redirect.headers["location"])
    assert playback.status_code == 200
    assert playback.content == b"real-provider-video-from-worker"


def test_creator_media_visibility_is_limited_to_owned_or_assigned_artifacts(
    db: Session,
    tmp_path: Path,
):
    organization, owner, product = create_scope(db, slug="creator-privacy")

    def add_creator(identity: str):
        profile = models.UserProfile(
            supabase_user_id=f"media:{identity}",
            email=f"{identity}@example.test",
            display_name=identity.title(),
            status="active",
            is_active=True,
            metadata_json={},
        )
        db.add(profile)
        db.flush()
        membership = models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="producer",
            status="active",
            permissions_json=[],
        )
        db.add(membership)
        db.flush()
        return profile, membership

    creator_a, _membership_a = add_creator("creator-a")
    creator_b, membership_b = add_creator("creator-b")
    db.commit()

    backend = local_backend(tmp_path)
    service = MediaArtifactService(db, {backend.name: backend})
    artifact = service.store_bytes(
        organization_id=organization.id,
        created_by_user_profile_id=creator_a.id,
        backend_name="local",
        kind="master_video",
        content=b"creator-a-private-video",
        mime_type="video/mp4",
        product_id=product.id,
    )

    assert service.list_owned(
        organization_id=organization.id,
        visible_to_user_profile_id=creator_b.id,
    ) == []
    with pytest.raises(MediaArtifactOwnershipError):
        service.signed_get_url(
            artifact.public_id,
            organization_id=organization.id,
            actor_user_profile_id=creator_b.id,
        )
    with pytest.raises(MediaArtifactOwnershipError):
        service.signed_get_url(
            artifact.public_id,
            organization_id=organization.id,
            actor_user_profile_id=creator_b.id,
            allow_team_scope=True,
        )
    assert "signature=" in service.signed_get_url(
        artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        allow_team_scope=True,
    )

    task = models.CreatorTask(
        organization_id=organization.id,
        assignee_user_profile_id=creator_b.id,
        created_by_user_profile_id=owner.id,
        product_id=product.id,
        media_artifact_id=artifact.id,
        task_type="review_generated_video",
        title="Review assigned video",
        status="todo",
        priority=3,
        idempotency_key="creator-privacy-assignment-1",
    )
    db.add(task)
    db.commit()

    assert [
        item.public_id
        for item in service.list_owned(
            organization_id=organization.id,
            visible_to_user_profile_id=creator_b.id,
        )
    ] == [artifact.public_id]
    assert "signature=" in service.signed_get_url(
        artifact.public_id,
        organization_id=organization.id,
        actor_user_profile_id=creator_b.id,
        allow_team_scope=False,
    )

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(media_library.router)

    def override_db():
        yield db

    current_user = {"value": creator_b, "membership": membership_b}
    app.dependency_overrides[media_library.get_db] = override_db
    app.dependency_overrides[media_library.get_media_artifact_service] = lambda: service
    app.dependency_overrides[get_current_public_user] = lambda: PublicPilotUser(
        profile=current_user["value"],
        organization=organization,
        membership=current_user["membership"],
    )
    client = TestClient(app)

    page = client.get("/media-library")
    assert page.status_code == 200
    assert artifact.public_id in page.text
    assert "Чужие ролики команды недоступны" in page.text
    assert client.get(f"/media-library?creator_id={creator_a.id}").status_code == 400
    access = client.get(
        f"/media-library/{artifact.public_id}/access",
        follow_redirects=False,
    )
    assert access.status_code == 307

    task.status = "cancelled"
    db.commit()
    assert artifact.public_id not in client.get("/media-library").text
    assert client.get(
        f"/media-library/{artifact.public_id}/access",
        follow_redirects=False,
    ).status_code == 404
