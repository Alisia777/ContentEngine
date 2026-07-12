from __future__ import annotations

import asyncio
import base64
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile

from app import models
from app.assets.asset_storage import ProductAssetStorage
from app.assets.errors import AssetKitDataError
from app.config import get_settings
from app.database import Base
from app.intelligence.types import ProviderVideoJob, ProviderVideoStatus
from app.media_storage.backend import StorageBackend, StoredObject
from app.media_storage.local import LocalStorage
from app.media_storage.service import MediaArtifactService
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.routers.public_pilot import _read_bounded_recipe_upload
from app.runway_recipes.errors import RunwayRecipeError
from app.runway_recipes.product_ugc_service import (
    MAX_IMAGE_BYTES,
    ProductImageUpload,
    ProductUGCRecipeService,
)
from app.runway_recipes.runner import ProductUGCRecipeRunner


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class MemoryRemoteStorage(StorageBackend):
    name = "fake-remote"
    bucket = "private-media"

    def __init__(self, *, blank_head_sha256: bool = True) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.blank_head_sha256 = blank_head_sha256
        self.signed_url_calls = 0

    def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        if key in self.objects:
            raise AssertionError("test backend does not allow an implicit overwrite")
        value = bytes(content)
        self.objects[key] = (value, mime_type)
        return self._stored(key, value, mime_type, include_sha=True)

    def head(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        content, mime_type = stored
        return self._stored(
            key,
            content,
            mime_type,
            include_sha=not self.blank_head_sha256,
        )

    def read_bytes(self, key: str) -> bytes:
        return self.objects[key][0]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def create_signed_get_url(
        self,
        key: str,
        *,
        expires_seconds: int,
        download_filename: str | None = None,
    ) -> str:
        self.signed_url_calls += 1
        return f"https://signed.invalid/{key}?token=must-not-be-used"

    def _stored(
        self,
        key: str,
        content: bytes,
        mime_type: str,
        *,
        include_sha: bool,
    ) -> StoredObject:
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest() if include_sha else "",
        )


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


TestSession = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def reset_database(monkeypatch, tmp_path):
    monkeypatch.setenv("QVF_RUNTIME_PROFILE", "development")
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "web-root"))
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-only-runway-secret")
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


@pytest.fixture
def db():
    with TestSession() as session:
        yield session


def create_scope(db: Session, *, slug: str = "durable"):
    organization = models.Organization(
        name=slug,
        slug=slug,
        status="active",
        settings_json={},
    )
    user = models.UserProfile(
        supabase_user_id=f"durable:{slug}",
        email=f"owner@{slug}.test",
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
        title="Durable cloud product",
        category="Cosmetics",
        attributes_json={
            "product_profile": "cosmetic",
            "variant_key": "rose-lumiere",
            "shade": "warm pink",
        },
        benefits_json=["High shine"],
        images_json=[],
        reviews_json=[],
        restrictions_json=["Do not invent medical claims"],
    )
    db.add(product)
    db.commit()
    return organization, user, product


def create_cloud_draft(
    db: Session,
    backend: MemoryRemoteStorage,
    *,
    slug: str = "durable",
):
    organization, user, product = create_scope(db, slug=slug)
    uploads = [
        ProductImageUpload(
            slot="front",
            filename="front.png",
            content=PNG + b"front",
            contract_type="front_packshot",
            primary=True,
        ),
        ProductImageUpload(
            slot="angle",
            filename="angle.png",
            content=PNG + b"angle",
            contract_type="angled_product",
        ),
        ProductImageUpload(
            slot="scale",
            filename="scale.png",
            content=PNG + b"scale",
            contract_type="product_in_hand",
        ),
    ]
    draft = ProductUGCRecipeService(
        db,
        storage_backends={backend.name: backend},
    ).create_draft(
        product_id=product.id,
        created_by_user_profile_id=user.id,
        variant_key="rose-lumiere",
        character_filename="creator.png",
        character_content=PNG,
        product_uploads=uploads,
        task="Показать товар в живом утреннем макияже.",
        creator_profile="Русскоязычная beauty-блогер 27 лет.",
        setting="У зеркала перед выходом из дома.",
        hook="Смотрите, какой живой микрошимер даёт один слой.",
        product_action="Показывает точный флакон рядом с лицом.",
        proof_moment="Поворачивает флакон к свету, чтобы был виден оттенок.",
        spoken_message="Он сияет, но не выглядит тяжёлым на губах.",
        cta="Сохраните оттенок, чтобы не потерять.",
        interaction_mode="presentation",
        likeness_consent=True,
        character_product_free_confirmed=True,
        exact_variant_confirmed=True,
    )
    assert draft.status == "ready_for_paid_preflight"
    return organization, user, product, draft


class SuccessfulProvider:
    def __init__(self) -> None:
        self.create_calls = 0
        self.requests = []

    def create_product_ugc(self, request):
        self.create_calls += 1
        self.requests.append(request)
        return ProviderVideoJob(
            provider="runway_product_ugc_recipe",
            provider_job_id="durable-provider-task",
            status="PENDING",
            raw_response={"id": "durable-provider-task", "status": "PENDING"},
        )

    def get_status(self, provider_job_id):
        return ProviderVideoStatus(
            provider_job_id=provider_job_id,
            status="SUCCEEDED",
            raw_response={"id": provider_job_id, "status": "SUCCEEDED"},
        )

    def download_outputs(self, provider_job_id, target_dir):
        target_dir.mkdir(parents=True, exist_ok=True)
        output = target_dir / "result.mp4"
        output.write_bytes(b"durable-cloud-output")
        return [output]


def enqueue_and_lease(db: Session, organization, user, draft):
    queue = ProductUGCGenerationQueueService(db)
    job = queue.enqueue(
        draft_id=draft.id,
        organization_id=organization.id,
        requested_by_user_profile_id=user.id,
        idempotency_key=f"durable-input:d{draft.id}",
    ).job
    leased = queue.lease_job(job.id, worker_id="durable-worker")
    assert leased is not None
    return queue, job, leased


def test_web_and_worker_use_private_artifacts_across_separate_roots(
    db: Session,
    monkeypatch,
    tmp_path,
):
    backend = MemoryRemoteStorage(blank_head_sha256=True)
    organization, user, _product, draft = create_cloud_draft(db, backend)
    primary = db.get(models.ProductAsset, draft.primary_product_asset_id)
    assert draft.character_image_path is None
    assert draft.character_media_artifact_id is not None
    assert primary.media_artifact_id is not None
    assert primary.source_type == "media_artifact"
    assert primary.source_ref.startswith("media-artifact://")
    assert "?" not in primary.source_ref
    assert db.scalar(select(func.count()).select_from(models.MediaArtifact)) == 4

    queue, job, leased = enqueue_and_lease(db, organization, user, draft)
    worker_root = tmp_path / "different-worker-root"
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(worker_root))
    get_settings.cache_clear()
    provider = SuccessfulProvider()
    result = ProductUGCRecipeRunner(
        db,
        provider_factory=lambda: provider,
        sleep=lambda _seconds: None,
        storage_backends={backend.name: backend},
    ).run(
        draft.id,
        real_run=True,
        generation_job_id=job.id,
        lease_token=leased.lease_token,
    )

    assert result.status == "generated_needs_human_review"
    assert provider.create_calls == 1
    assert provider.requests[0].character_image.uri.startswith("data:image/")
    assert provider.requests[0].product_image.uri.startswith("data:image/")
    assert backend.signed_url_calls == 0
    scratch_parent = worker_root / "worker_scratch"
    assert not scratch_parent.exists() or not any(scratch_parent.iterdir())
    assert db.get(models.ProductUGCGenerationJob, job.id).status == "succeeded"
    assert all(artifact.sha256 for artifact in db.scalars(select(models.MediaArtifact)))


@pytest.mark.parametrize(
    "failure",
    ["missing", "corrupt", "wrong_tenant", "wrong_kind", "archived", "wrong_size"],
)
def test_invalid_private_input_fails_before_spend_or_provider_submit(
    db: Session,
    monkeypatch,
    tmp_path,
    failure: str,
):
    backend = MemoryRemoteStorage(blank_head_sha256=True)
    organization, user, product, draft = create_cloud_draft(db, backend)
    character = db.get(models.MediaArtifact, draft.character_media_artifact_id)
    if failure == "missing":
        backend.objects.pop(character.object_key)
    elif failure == "corrupt":
        content, mime_type = backend.objects[character.object_key]
        backend.objects[character.object_key] = (bytes([content[0] ^ 1]) + content[1:], mime_type)
    elif failure == "wrong_tenant":
        other_org, other_user, other_product = create_scope(db, slug="foreign")
        foreign = MediaArtifactService(db, {backend.name: backend}).store_bytes(
            organization_id=other_org.id,
            created_by_user_profile_id=other_user.id,
            backend_name=backend.name,
            kind="creator_reference",
            content=PNG,
            mime_type="image/png",
            original_filename="foreign.png",
            product_id=other_product.id,
        )
        draft.character_media_artifact_id = foreign.id
        db.commit()
    elif failure == "wrong_kind":
        character.kind = "thumbnail"
        db.commit()
    elif failure == "archived":
        character.status = "archived"
        db.commit()
    else:
        character.size_bytes += 1
        db.commit()

    _queue, job, leased = enqueue_and_lease(db, organization, user, draft)
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "worker-root"))
    get_settings.cache_clear()
    provider = SuccessfulProvider()
    with pytest.raises(RunwayRecipeError):
        ProductUGCRecipeRunner(
            db,
            provider_factory=lambda: provider,
            sleep=lambda _seconds: None,
            storage_backends={backend.name: backend},
        ).run(
            draft.id,
            real_run=True,
            generation_job_id=job.id,
            lease_token=leased.lease_token,
        )
    db.expire_all()
    persisted = db.get(models.ProductUGCGenerationJob, job.id)
    assert provider.create_calls == 0
    assert persisted.spend_guarded_at is None
    assert persisted.provider_task_id is None
    assert backend.signed_url_calls == 0


def test_known_provider_task_retry_does_not_require_recipe_inputs(
    db: Session,
    monkeypatch,
    tmp_path,
):
    backend = MemoryRemoteStorage(blank_head_sha256=True)
    organization, user, _product, draft = create_cloud_draft(db, backend)
    queue, job, leased = enqueue_and_lease(db, organization, user, draft)
    queue.begin_provider_submission(job.id, lease_token=leased.lease_token)
    queue.record_provider_submission(
        job.id,
        lease_token=leased.lease_token,
        provider_task_id="existing-provider-task",
        provider_status="PENDING",
    )
    backend.objects.clear()
    # Operations may disable all new paid submissions during an incident. An
    # already-created provider task must still be polled and downloaded.
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "false")
    monkeypatch.setenv("QVF_GENERATION_MODE", "mock")
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "resume-worker-root"))
    get_settings.cache_clear()
    provider = SuccessfulProvider()

    result = ProductUGCRecipeRunner(
        db,
        provider_factory=lambda: provider,
        sleep=lambda _seconds: None,
        storage_backends={backend.name: backend},
    ).run(
        draft.id,
        real_run=True,
        generation_job_id=job.id,
        lease_token=leased.lease_token,
    )

    assert result.status == "generated_needs_human_review"
    assert provider.create_calls == 0
    assert db.get(models.ProductUGCGenerationJob, job.id).provider_task_id == "existing-provider-task"


def test_idempotent_preexisting_object_with_blank_head_hash_is_read_verified(
    db: Session,
    tmp_path,
):
    backend = MemoryRemoteStorage(blank_head_sha256=True)
    organization, user, product = create_scope(db, slug="blank-head")
    source = tmp_path / "worker-output.mp4"
    source.write_bytes(b"verified-preexisting-worker-output")
    idempotency_key = "blank-head-preexisting-output"
    public_id = hashlib.sha256(
        f"media-artifact\0{organization.id}\0{idempotency_key}".encode("utf-8")
    ).hexdigest()[:32]
    object_key = MediaArtifactService.build_object_key(
        organization_id=organization.id,
        public_id=public_id,
        kind="master_video",
        original_filename=source.name,
        product_id=product.id,
    )
    backend.put_bytes(
        object_key,
        source.read_bytes(),
        mime_type="video/mp4",
        original_filename=source.name,
    )
    service = MediaArtifactService(db, {backend.name: backend})

    artifact = service.store_file_idempotent(
        organization_id=organization.id,
        created_by_user_profile_id=user.id,
        backend_name=backend.name,
        idempotency_key=idempotency_key,
        kind="master_video",
        source=source,
        mime_type="video/mp4",
        original_filename=source.name,
        product_id=product.id,
    )
    repeated = service.store_file_idempotent(
        organization_id=organization.id,
        created_by_user_profile_id=user.id,
        backend_name=backend.name,
        idempotency_key=idempotency_key,
        kind="master_video",
        source=source,
        mime_type="video/mp4",
        original_filename=source.name,
        product_id=product.id,
    )

    assert artifact.id == repeated.id
    assert artifact.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert backend.head(object_key).sha256 == ""
    assert backend.signed_url_calls == 0


def test_local_product_upload_is_rejected_for_production(db: Session, tmp_path):
    organization, user, product = create_scope(db, slug="production-local")
    backend = LocalStorage(
        tmp_path / "objects",
        bucket="private-media",
        signing_secret="test-signing-secret-at-least-16",
    )
    storage = ProductAssetStorage(db, backends={backend.name: backend})
    storage.settings = SimpleNamespace(
        runtime_profile="production",
        storage_backend="local",
        media_root=tmp_path / "web-root",
    )
    with pytest.raises(AssetKitDataError, match="forbidden in production"):
        storage.upload_file(
            product.id,
            filename="product.png",
            content=PNG,
            created_by_user_profile_id=user.id,
        )
    assert db.scalar(select(func.count()).select_from(models.MediaArtifact)) == 0


def test_recipe_upload_reader_enforces_limit_and_closes_file():
    upload = UploadFile(
        filename="too-large.png",
        file=io.BytesIO(b"x" * (MAX_IMAGE_BYTES + 1)),
    )
    with pytest.raises(RunwayRecipeError, match="превышает лимит"):
        asyncio.run(_read_bounded_recipe_upload(upload, label="Фото блогера"))
    assert upload.file.closed
