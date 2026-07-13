from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.creator_operations import CreatorOperationsService
from app.database import Base
from app.intelligence.types import ProviderVideoJob
from app.media_storage.backend import StorageBackend, StoredObject
from app.product_ugc_queue import (
    ProductUGCGenerationQueueService,
    ProductUGCGenerationWorker,
    ProductUGCQueueLeaseError,
)
from app.product_ugc_queue.generation_snapshot_guard import (
    _current_template_snapshot,
    canonical_json_sha256,
)
import app.product_ugc_queue.service as queue_service_module
from app.runway_recipes import (
    ProductImageUpload,
    ProductUGCRecipeRequest,
    ProductUGCRecipeService,
    RecipeImageInput,
    RunwayRecipeError,
)


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

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


class MemoryRemoteStorage(StorageBackend):
    name = "fake-remote"
    bucket = "private-media"

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(
        self,
        key: str,
        content: bytes,
        *,
        mime_type: str,
        original_filename: str | None = None,
    ) -> StoredObject:
        value = bytes(content)
        self.objects[key] = (value, mime_type)
        return self._stored(key, value, mime_type)

    def head(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        return self._stored(key, *stored) if stored is not None else None

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
        return f"https://signed.invalid/{key}?token=unused"

    def _stored(self, key: str, content: bytes, mime_type: str) -> StoredObject:
        return StoredObject(
            backend_name=self.name,
            bucket=self.bucket,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )


@pytest.fixture(autouse=True)
def reset_database(monkeypatch, tmp_path):
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-only-secret")
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


def _source_scope(db, monkeypatch, *, backend: MemoryRemoteStorage | None = None):
    organization = models.Organization(
        name="snapshot-spend-guard",
        slug="snapshot-spend-guard",
        status="active",
        settings_json={},
    )
    owner = models.UserProfile(
        supabase_user_id="snapshot-spend-guard:owner",
        email="owner@snapshot-spend-guard.test",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add_all([organization, owner])
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=owner.id,
            role="owner",
            status="active",
            permissions_json=[],
        )
    )
    product = models.Product(
        organization_id=organization.id,
        sku="SNAPSHOT-GUARD-SKU",
        brand="ALTEA",
        title="Exact snapshot guard product",
        description="Exact cosmetic packaging used by the paid-submit guard.",
        category="Cosmetics",
        attributes_json={
            "product_profile": "cosmetic",
            "variant_key": "rose-lumiere",
            "shade": "warm rose",
        },
        benefits_json=["High shine"],
        images_json=[],
        reviews_json=[],
        restrictions_json=["Do not invent medical claims"],
    )
    db.add(product)
    db.commit()

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
    source = ProductUGCRecipeService(
        db,
        storage_backends=({backend.name: backend} if backend is not None else None),
    ).create_draft(
        product_id=product.id,
        created_by_user_profile_id=owner.id,
        variant_key="rose-lumiere",
        character_filename="creator.png",
        character_content=PNG,
        product_uploads=uploads,
        task="Show the exact sealed product and its honest visual benefit.",
        creator_profile="Experienced beauty creator speaking clearly to camera.",
        setting="Natural daylight beside a clean mirror.",
        hook="Here is the exact shade and packaging in daylight.",
        product_action="Holds the sealed product beside the face and rotates it.",
        proof_moment="Shows the label and exact warm rose shade to camera.",
        spoken_message="The gloss looks bright without a heavy visual effect.",
        cta="Save the exact shade for later.",
        interaction_mode="presentation",
        likeness_consent=True,
        character_product_free_confirmed=True,
        exact_variant_confirmed=True,
    )
    assert source.status == "ready_for_paid_preflight"
    assert 0 < source.estimated_credits <= get_settings().mass_generation_credit_limit
    monkeypatch.setattr(
        CreatorOperationsService,
        "final_exam_passed",
        lambda self, user_profile_id: True,
    )
    return organization, owner, product, source


def _create_batch(
    db,
    organization,
    owner,
    source,
    *,
    dry_run: bool,
    key: str,
    quantity: int = 1,
):
    return CreatorOperationsService(db).generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=source.id,
        assignee_user_profile_ids=[owner.id],
        quantity=quantity,
        name="Snapshot spend guard batch",
        idempotency_key=key,
        dry_run=dry_run,
        confirm_real_spend=not dry_run,
        confirmed_total_credits=(
            source.estimated_credits * quantity if not dry_run else 0
        ),
    )


def _create_preview_backed_batch(db, organization, owner, source, *, key: str):
    preview = _create_batch(
        db,
        organization,
        owner,
        source,
        dry_run=True,
        key=f"{key}:preview",
    )
    parameters = dict(preview.parameters_json or {})
    working = CreatorOperationsService(db).generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=source.id,
        assignee_user_profile_ids=[owner.id],
        quantity=1,
        name="Snapshot preview-backed working batch",
        idempotency_key=f"{key}:working",
        dry_run=False,
        confirm_real_spend=True,
        confirmed_total_credits=source.estimated_credits,
        _expected_template_snapshot=parameters["template_snapshot"],
        _expected_template_snapshot_sha256=parameters[
            "template_snapshot_sha256"
        ],
        _source_dry_run_batch_id=preview.id,
    )
    return preview, working


def _built_request(snapshot_draft: dict[str, object], *, concept: str | None = None):
    return ProductUGCRecipeRequest(
        version=str(snapshot_draft["recipe_version"]),
        character_image=RecipeImageInput(uri="data:image/png;base64,Y2hhcmFjdGVy"),
        product_image=RecipeImageInput(uri="data:image/png;base64,cHJvZHVjdA=="),
        product_info=str(snapshot_draft["product_info"]),
        user_concept=concept or str(snapshot_draft["user_concept"]),
        duration=int(snapshot_draft["duration_seconds"]),
        ratio=str(snapshot_draft["ratio"]),
        audio=bool(snapshot_draft["audio_enabled"]),
    )


def _job_for_batch(db, batch):
    result = batch.results_json[0]
    return db.get(models.ProductUGCGenerationJob, result["generation_job_id"])


def test_guard_snapshot_serializer_matches_creator_snapshot_with_private_artifacts(monkeypatch):
    with TestSession() as db:
        backend = MemoryRemoteStorage()
        organization, owner, _product, source = _source_scope(
            db,
            monkeypatch,
            backend=backend,
        )
        primary = db.get(models.ProductAsset, source.primary_product_asset_id)
        assert source.character_media_artifact_id is not None
        assert primary.media_artifact_id is not None
        assert primary.source_type == "media_artifact"

        preview = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=True,
            key="snapshot-parity-preview",
        )
        stored = preview.parameters_json["template_snapshot"]
        current = _current_template_snapshot(
            db,
            source,
            organization_id=organization.id,
        )

        assert current == stored
        assert canonical_json_sha256(current) == preview.parameters_json[
            "template_snapshot_sha256"
        ]
        assert "metadata_json" not in stored["media_artifacts"][0]
        assert "retention_class" not in stored["media_artifacts"][0]
        assert stored["product"]["benefits_json"] == ["High shine"]


def test_mutated_launch_draft_blocks_provider_call_and_spend(monkeypatch):
    calls = {"build": 0, "create": 0}

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("stale launch draft must be blocked before provider spend")

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key="snapshot-launch-mismatch",
        )
        snapshot_draft = batch.parameters_json["template_snapshot"]["draft"]
        job = _job_for_batch(db, batch)
        launch = db.get(models.ProductUGCRecipeDraft, job.draft_id)
        launch.product_info = "Changed after owner approval and before provider submit."
        db.commit()
        def build_request(self, draft, **kwargs):
            calls["build"] += 1
            return _built_request(snapshot_draft)

        monkeypatch.setattr(ProductUGCRecipeService, "provider_request", build_request)

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=MustNotSubmitProvider,
            sleep=lambda _: None,
        ).process_job(job.id)

        assert calls == {"build": 0, "create": 0}
        assert result.provider_task_id is None
        assert result.spend_guarded_at is None
        assert result.status == "failed_terminal"
        assert result.last_error_code == "PRODUCTUGCSPENDVALIDATIONERROR"


def test_valid_alias_payload_with_materialized_uris_crosses_spend_guard(monkeypatch):
    calls = {"create": 0, "payload": None}

    class SubmitOnceProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            calls["payload"] = request.model_dump(mode="json", by_alias=True)
            return ProviderVideoJob(
                provider="runway",
                provider_job_id="snapshot-guard-provider-task",
                status="PENDING",
                raw_response={},
            )

        def get_status(self, provider_job_id):
            raise RuntimeError("stop after the durable provider task id is recorded")

    with TestSession() as db:
        backend = MemoryRemoteStorage()
        organization, owner, _product, source = _source_scope(
            db,
            monkeypatch,
            backend=backend,
        )
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key="snapshot-valid-provider-payload",
        )
        job = _job_for_batch(db, batch)
        monkeypatch.setattr(
            "app.media_storage.recipe_inputs.get_storage_backends",
            lambda: {backend.name: backend},
        )

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=SubmitOnceProvider,
            sleep=lambda _: None,
        ).process_job(job.id)

        assert calls["create"] == 1
        assert result.spend_guarded_at is not None
        assert result.provider_task_id == "snapshot-guard-provider-task"
        assert result.status == "retry_wait"
        assert calls["payload"]["characterImage"]["uri"].startswith(
            "data:image/png;base64,"
        )
        assert calls["payload"]["productImage"]["uri"].startswith(
            "data:image/png;base64,"
        )


def test_changed_built_provider_payload_blocks_provider_call(monkeypatch):
    calls = {"create": 0}

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("changed provider payload must not be submitted")

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key="snapshot-built-payload-mismatch",
        )
        snapshot_draft = batch.parameters_json["template_snapshot"]["draft"]
        job = _job_for_batch(db, batch)
        monkeypatch.setattr(
            ProductUGCRecipeService,
            "provider_request",
            lambda self, draft, **kwargs: _built_request(
                snapshot_draft,
                concept="A payload changed after validation.",
            ),
        )

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=MustNotSubmitProvider,
            sleep=lambda _: None,
        ).process_job(job.id)

        assert calls["create"] == 0
        assert result.spend_guarded_at is None
        assert result.provider_task_id is None
        assert result.status == "failed_terminal"


@pytest.mark.parametrize(
    "mutation",
    (
        "real_spend_not_confirmed",
        "confirmed_total_changed",
        "sequence_overflow",
        "metadata_missing",
        "stored_limit_changed",
        "runtime_limit_exceeded",
    ),
)
def test_mutated_approval_contract_never_reaches_provider(monkeypatch, mutation):
    calls = {"create": 0}

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("invalid owner approval must fail before provider spend")

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key=f"snapshot-approval-{mutation}",
        )
        job = _job_for_batch(db, batch)
        parameters = dict(batch.parameters_json or {})
        metadata = dict(job.metadata_json or {})
        if mutation == "real_spend_not_confirmed":
            parameters["real_spend_requested"] = False
        elif mutation == "confirmed_total_changed":
            parameters["confirmed_total_credits"] = int(
                parameters["estimated_credits"]
            ) - 1
        elif mutation == "sequence_overflow":
            metadata["sequence"] = int(batch.total_requested) + 1
        elif mutation == "metadata_missing":
            metadata.pop("provider_payload_sha256")
        elif mutation == "stored_limit_changed":
            parameters["credit_limit"] = int(parameters["credit_limit"]) - 1
        elif mutation == "runtime_limit_exceeded":
            monkeypatch.setenv("QVF_MASS_GENERATION_CREDIT_LIMIT", "500")
            get_settings.cache_clear()
            parameters["credit_limit"] = 500
            assert int(parameters["estimated_credits"]) > 500
        batch.parameters_json = parameters
        job.metadata_json = metadata
        db.commit()

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=MustNotSubmitProvider,
            sleep=lambda _: None,
        ).process_job(job.id)

        assert calls["create"] == 0
        assert result.spend_guarded_at is None
        assert result.provider_task_id is None
        assert result.status == "failed_terminal"


def test_mass_preflight_block_is_terminal_without_retry_churn(monkeypatch):
    calls = {"build": 0, "create": 0}

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("blocked preflight must never reach provider")

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key="snapshot-preflight-terminal",
        )
        job = _job_for_batch(db, batch)

        def block_during_preflight(self, draft, **kwargs):
            calls["build"] += 1
            draft.status = "blocked"
            draft.blockers_json = ["new_launch_gate"]
            self.db.commit()
            raise RunwayRecipeError(
                "Product UGC draft is blocked; create a new validated preview."
            )

        monkeypatch.setattr(
            ProductUGCRecipeService,
            "provider_request",
            block_during_preflight,
        )
        worker = ProductUGCGenerationWorker(
            db,
            provider_factory=MustNotSubmitProvider,
            sleep=lambda _: None,
        )
        first = worker.process_job(job.id)
        second = worker.process_job(job.id)

        assert calls == {"build": 1, "create": 0}
        assert first.status == second.status == "failed_terminal"
        assert second.attempt_count == 1
        assert second.spend_guarded_at is None
        assert second.provider_task_id is None


def test_lease_expiring_during_locked_validation_cannot_acquire_spend_guard(
    monkeypatch,
):
    calls = {"create": 0}
    now = [datetime(2030, 1, 1, 12, 0, 0)]

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key="snapshot-lease-expiry",
        )
        job = _job_for_batch(db, batch)
        service = ProductUGCGenerationQueueService(db, clock=lambda: now[0])
        leased = service.lease_job(
            job.id,
            worker_id="snapshot-expiring-worker",
            lease_seconds=5,
        )
        assert leased is not None
        service.validate_provider_submission_inputs(
            job.id,
            lease_token=leased.lease_token,
        )
        assert db.in_transaction() is False

        original_guard = queue_service_module.validate_mass_generation_pre_spend

        def delayed_guard(*args, **kwargs):
            original_guard(*args, **kwargs)
            now[0] += timedelta(seconds=6)

        monkeypatch.setattr(
            queue_service_module,
            "validate_mass_generation_pre_spend",
            delayed_guard,
        )
        snapshot_draft = batch.parameters_json["template_snapshot"]["draft"]
        with pytest.raises(ProductUGCQueueLeaseError):
            service.begin_provider_submission(
                job.id,
                lease_token=leased.lease_token,
                lease_seconds=5,
                provider_payload=_built_request(snapshot_draft),
            )
            MustNotSubmitProvider().create_product_ugc(None)

        db.expire_all()
        persisted = db.get(models.ProductUGCGenerationJob, job.id)
        assert calls["create"] == 0
        assert persisted.spend_guarded_at is None
        assert persisted.provider_task_id is None


@pytest.mark.parametrize(
    "mutation",
    (
        "status",
        "failed_count",
        "errors",
        "accepted_count",
        "completed_at",
        "quantity",
        "estimated_credits",
        "assignees",
    ),
)
def test_tampered_preview_approval_cannot_authorize_working_batch(
    monkeypatch,
    mutation,
):
    calls = {"create": 0}

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("tampered preview must not authorize provider spend")

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        preview, working = _create_preview_backed_batch(
            db,
            organization,
            owner,
            source,
            key=f"snapshot-preview-tamper-{mutation}",
        )
        parameters = dict(preview.parameters_json or {})
        if mutation == "status":
            preview.status = "blocked"
        elif mutation == "failed_count":
            preview.total_failed = 1
        elif mutation == "errors":
            preview.errors_json = [{"error": "approval changed"}]
        elif mutation == "accepted_count":
            preview.total_accepted = 0
        elif mutation == "completed_at":
            preview.completed_at = None
        elif mutation == "quantity":
            parameters["quantity"] = 2
        elif mutation == "estimated_credits":
            parameters["estimated_credits"] = int(
                parameters["estimated_credits"]
            ) + 1
        elif mutation == "assignees":
            parameters["assignee_user_profile_ids"] = []
        preview.parameters_json = parameters
        db.commit()
        job = _job_for_batch(db, working)

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=MustNotSubmitProvider,
            sleep=lambda _: None,
        ).process_job(job.id)

        assert calls["create"] == 0
        assert result.status == "failed_terminal"
        assert result.spend_guarded_at is None
        assert result.provider_task_id is None


@pytest.mark.parametrize(
    "mutation",
    ("incomplete", "duplicate_sequence", "duplicate_job", "requester"),
)
def test_invalid_global_working_result_shape_never_reaches_provider(
    monkeypatch,
    mutation,
):
    calls = {"create": 0}

    class MustNotSubmitProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("invalid global batch lineage must block spend")

    with TestSession() as db:
        organization, owner, _product, source = _source_scope(db, monkeypatch)
        batch = _create_batch(
            db,
            organization,
            owner,
            source,
            dry_run=False,
            key=f"snapshot-global-results-{mutation}",
            quantity=2,
        )
        results = [dict(item) for item in batch.results_json]
        first_job = db.get(
            models.ProductUGCGenerationJob,
            results[0]["generation_job_id"],
        )
        if mutation == "incomplete":
            results.pop()
        elif mutation == "duplicate_sequence":
            results[1]["sequence"] = results[0]["sequence"]
        elif mutation == "duplicate_job":
            results[1]["generation_job_id"] = results[0]["generation_job_id"]
        elif mutation == "requester":
            first_job.requested_by_user_profile_id = None
        batch.results_json = results
        db.commit()

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=MustNotSubmitProvider,
            sleep=lambda _: None,
        ).process_job(first_job.id)

        assert calls["create"] == 0
        assert result.status == "failed_terminal"
        assert result.spend_guarded_at is None
        assert result.provider_task_id is None
