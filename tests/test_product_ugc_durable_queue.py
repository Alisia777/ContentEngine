from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.database import Base, _ensure_product_ugc_generation_queue_schema
from app.intelligence.types import ProviderVideoStatus
from app.product_ugc_queue import (
    ProductUGCGenerationQueueService,
    ProductUGCGenerationWorker,
    ProductUGCQueueConflict,
    ProductUGCQueueLeaseError,
    ProductUGCQueueOwnershipError,
    ProductUGCSubmissionAmbiguous,
)
from app.product_ugc_queue.mass_projection import (
    project_mass_generation_queue_state,
    project_mass_generation_ready,
)
from app.product_ugc_queue.service import stale_lease_reconciliation_query
from app.runway_recipes import ProductUGCRecipeRunner, RunwayRecipeError


queue_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
QueueTestSession = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=queue_test_engine,
)


def naive_utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def test_stale_reconciliation_locks_and_skips_rows_owned_by_another_reconciler():
    compiled = str(
        stale_lease_reconciliation_query(naive_utcnow()).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).upper()

    assert "FOR UPDATE SKIP LOCKED" in compiled


@pytest.fixture(autouse=True)
def reset_queue_db(monkeypatch, tmp_path):
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("QVF_GENERATION_MODE", "mock")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "false")
    monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=queue_test_engine)
    Base.metadata.create_all(bind=queue_test_engine)
    yield
    get_settings.cache_clear()


def create_scope(db, *, slug: str = "queue-org", email: str = "owner@queue.test"):
    org = models.Organization(name=slug, slug=slug, status="active", settings_json={})
    user = models.UserProfile(
        supabase_user_id=f"queue:{slug}:{email}",
        email=email,
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add_all([org, user])
    db.flush()
    db.add(
        models.Membership(
            organization_id=org.id,
            user_profile_id=user.id,
            role="owner",
            status="active",
            permissions_json=[],
        )
    )
    db.flush()
    return org, user


def create_draft(db, org, *, status: str = "ready_for_paid_preflight", suffix: str = "1"):
    product = models.Product(
        organization_id=org.id,
        sku=f"QUEUE-SKU-{suffix}",
        brand="Queue",
        title="Durable generation product",
        attributes_json={},
        benefits_json=[],
        images_json=[],
        reviews_json=[],
        restrictions_json=[],
    )
    db.add(product)
    db.flush()
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        sku=product.sku,
        variant_key="exact-variant",
        status=status,
        recipe_version="2026-06",
        platform="Instagram Reels",
        language="ru",
        character_image_path="unused-character.png",
        character_image_filename="unused-character.png",
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_asset_ids_json=[],
        product_info="Exact product",
        user_concept="Show exact product",
        creative_inputs_json={},
        duration_seconds=15,
        ratio="720:1280",
        audio_enabled=True,
        estimated_credits=100,
        provider_payload_preview_json={},
        blockers_json=[],
        warnings_json=[],
        local_output_paths_json=[],
        human_review_status="not_generated",
        publishing_readiness="blocked",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def test_success_telemetry_counts_durable_cloud_video_after_local_paths_are_cleared():
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="telemetry-cloud-output")
        draft = create_draft(db, org, status="generated_needs_human_review", suffix="telemetry")
        draft.local_output_paths_json = []
        job = models.ProductUGCGenerationJob(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="telemetry-cloud-output-job",
            status="succeeded",
            attempt_count=1,
            max_attempts=5,
            next_attempt_at=naive_utcnow(),
            provider="runway_product_ugc_recipe",
            provider_task_id="provider-telemetry-cloud-output",
            provider_status="SUCCEEDED",
            completed_at=naive_utcnow(),
            metadata_json={},
        )
        db.add(job)
        db.flush()
        db.add(
            models.MediaArtifact(
                public_id="1" * 32,
                idempotency_key="telemetry-cloud-output-artifact",
                organization_id=org.id,
                created_by_user_profile_id=user.id,
                product_id=draft.product_id,
                product_ugc_recipe_draft_id=draft.id,
                kind="master_video",
                backend_name="supabase",
                bucket="private-media",
                object_key=(
                    f"organizations/{org.id:08d}/products/{draft.product_id:08d}/"
                    f"drafts/{draft.id:08d}/videos/{job.id:08d}/master_video/"
                    f"{'1' * 32}/video.mp4"
                ),
                original_filename="video.mp4",
                mime_type="video/mp4",
                size_bytes=1_024,
                sha256="1" * 64,
                status="ready",
                metadata_json={},
                retention_class="master_365d",
                legal_hold=False,
            )
        )
        db.commit()

        ProductUGCGenerationWorker(db)._record_terminal_event(job)

        event = db.scalar(
            select(models.FactoryEvent).where(
                models.FactoryEvent.event_name == "generation_succeeded"
            )
        )
        assert event is not None
        assert event.properties_json["output_count"] == 1
        assert event.properties_json["queue_status"] == "succeeded"


def attach_mass_generation(db, org, user, *jobs):
    batch = models.MassOperationBatch(
        organization_id=org.id,
        created_by_user_profile_id=user.id,
        operation_type="generation",
        name="Durable queue projection batch",
        idempotency_key=f"queue-projection:{jobs[0].id}",
        status="queued",
        dry_run=False,
        total_requested=len(jobs),
        total_accepted=len(jobs),
        total_failed=0,
        parameters_json={},
        results_json=[],
        errors_json=[],
        started_at=models.utcnow(),
    )
    db.add(batch)
    db.flush()
    tasks = []
    results = []
    for sequence, job in enumerate(jobs, start=1):
        draft = db.get(models.ProductUGCRecipeDraft, job.draft_id)
        metadata = dict(job.metadata_json or {})
        metadata.update(
            {
                "source": "mass_operation",
                "mass_operation_batch_id": batch.id,
                "sequence": sequence,
            }
        )
        job.metadata_json = metadata
        task = models.CreatorTask(
            organization_id=org.id,
            assignee_user_profile_id=user.id,
            created_by_user_profile_id=user.id,
            mass_operation_batch_id=batch.id,
            product_id=draft.product_id,
            product_ugc_recipe_draft_id=draft.id,
            task_type="review_generated_video",
            title=f"Review generated video {sequence}",
            status="todo",
            priority=3,
            blockers_json=[],
            result_json={},
            idempotency_key=f"queue-projection:{batch.id}:task:{sequence}",
        )
        db.add(task)
        db.flush()
        tasks.append(task)
        results.append(
            {
                "sequence": sequence,
                "draft_id": draft.id,
                "generation_job_id": job.id,
                "creator_task_id": task.id,
                "status": "queued",
            }
        )
    batch.results_json = results
    db.commit()
    return batch, tasks


def quarantine_ambiguous_job(db, org, user, *, key: str = "ambiguous-for-reconciliation"):
    draft = create_draft(db, org, suffix=key[-12:])
    service = ProductUGCGenerationQueueService(db)
    job = service.enqueue(
        draft_id=draft.id,
        organization_id=org.id,
        requested_by_user_profile_id=user.id,
        idempotency_key=key,
    ).job
    leased = service.lease_job(job.id, worker_id=f"worker:{key}")
    service.begin_provider_submission(job.id, lease_token=leased.lease_token)
    disposition = service.fail(
        job.id,
        lease_token=leased.lease_token,
        error="provider response was lost after submit",
    )
    assert disposition.job.status == "quarantined"
    return draft, disposition.job


def test_enqueue_is_idempotent_and_exactly_one_job_owns_the_draft():
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db)

        first = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key=f"paid-product-ugc:d{draft.id}:v1",
        )
        same_key = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key=f"paid-product-ugc:d{draft.id}:v1",
        )
        different_request_key = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key=f"paid-product-ugc:d{draft.id}:duplicate-click",
        )

        assert first.created is True
        assert same_key.created is False
        assert different_request_key.created is False
        assert first.job.id == same_key.job.id == different_request_key.job.id
        assert first.job.organization_id == org.id
        assert first.job.requested_by_user_profile_id == user.id
        assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 1
        assert db.get(models.ProductUGCRecipeDraft, draft.id).status == "provider_launching"


def test_enqueue_rejects_cross_organization_actor_and_product_scope():
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="owner-org", email="owner@test.local")
        other_org, other_user = create_scope(db, slug="other-org", email="other@test.local")
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db)

        with pytest.raises(ProductUGCQueueOwnershipError):
            service.enqueue(
                draft_id=draft.id,
                organization_id=other_org.id,
                requested_by_user_profile_id=other_user.id,
                idempotency_key="cross-org-attempt",
            )
        with pytest.raises(ProductUGCQueueOwnershipError):
            service.enqueue(
                draft_id=draft.id,
                organization_id=org.id,
                requested_by_user_profile_id=other_user.id,
                idempotency_key="cross-membership-attempt",
            )
        assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 0


def test_lease_heartbeat_expiry_and_reclaim_are_atomic():
    now = [datetime(2026, 7, 11, 10, 0, 0)]
    clock = lambda: now[0]
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db, clock=clock)
        result = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="lease-test",
        )
        leased = service.lease_job(result.job.id, worker_id="worker-a", lease_seconds=30)
        assert leased is not None
        first_token = leased.lease_token
        assert leased.attempt_count == 1
        assert service.lease_job(result.job.id, worker_id="worker-b", lease_seconds=30) is None

        now[0] += timedelta(seconds=20)
        heartbeated = service.heartbeat(result.job.id, lease_token=first_token, lease_seconds=30)
        assert heartbeated.lease_expires_at == now[0] + timedelta(seconds=30)

        now[0] += timedelta(seconds=31)
        report = service.reconcile_stale(stale_after_seconds=0)
        assert report.released_for_retry == 1
        second = service.lease_job(result.job.id, worker_id="worker-b", lease_seconds=30)
        assert second is not None
        assert second.attempt_count == 2
        assert second.lease_token != first_token
        with pytest.raises(ProductUGCQueueLeaseError):
            service.heartbeat(result.job.id, lease_token=first_token)


def test_revoked_membership_blocks_first_paid_submit_after_enqueue():
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db)
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="revoked-before-spend",
        ).job
        leased = service.lease_job(job.id, worker_id="worker-revoked")
        membership = db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == org.id,
                models.Membership.user_profile_id == user.id,
            )
        )
        membership.status = "revoked"
        db.commit()

        with pytest.raises(ProductUGCQueueOwnershipError):
            service.begin_provider_submission(job.id, lease_token=leased.lease_token)
        db.refresh(job)
        assert job.spend_guarded_at is None
        assert job.provider_task_id is None


def test_retry_backoff_is_bounded_and_becomes_terminal_at_attempt_limit():
    now = [datetime(2026, 7, 11, 11, 0, 0)]
    clock = lambda: now[0]
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(
            db,
            clock=clock,
            retry_base_seconds=7,
            retry_max_seconds=20,
        )
        queued = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="retry-test",
            max_attempts=2,
        ).job
        first = service.lease_job(queued.id, worker_id="worker-a")
        disposition = service.fail(
            queued.id,
            lease_token=first.lease_token,
            error="temporary polling failure",
            retryable=True,
        )
        assert disposition.will_retry is True
        assert disposition.job.next_attempt_at == now[0] + timedelta(seconds=7)
        assert service.lease_job(queued.id, worker_id="too-early") is None

        now[0] += timedelta(seconds=7)
        second = service.lease_job(queued.id, worker_id="worker-b")
        terminal = service.fail(
            queued.id,
            lease_token=second.lease_token,
            error="temporary polling failure again",
            retryable=True,
        )
        assert terminal.will_retry is False
        assert terminal.job.status == "failed_terminal"
        assert terminal.job.terminal_reason == "retry_exhausted"
        assert terminal.job.attempt_count == terminal.job.max_attempts == 2


def test_retry_wait_keeps_mass_generation_task_and_batch_actionable():
    now = [datetime(2026, 7, 11, 11, 30, 0)]
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="projection-retry")
        draft = create_draft(db, org, suffix="projection-retry")
        service = ProductUGCGenerationQueueService(db, clock=lambda: now[0])
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="projection-retry-job",
            max_attempts=2,
        ).job
        batch, tasks = attach_mass_generation(db, org, user, job)

        leased = service.lease_job(job.id, worker_id="projection-retry-worker")
        disposition = service.fail(
            job.id,
            lease_token=leased.lease_token,
            error="temporary download timeout",
            error_code="DOWNLOAD_TIMEOUT",
            retryable=True,
        )

        db.refresh(batch)
        db.refresh(tasks[0])
        assert disposition.will_retry is True
        assert tasks[0].status == "todo"
        assert tasks[0].blockers_json == []
        assert tasks[0].result_json["generation_queue_status"] == "retry_wait"
        assert batch.status == "queued"
        assert batch.total_failed == 0
        assert batch.completed_at is None
        assert batch.errors_json == []
        assert batch.results_json[0]["status"] == "retry_wait"


def test_terminal_generation_failure_blocks_linked_work_with_action_and_is_idempotent():
    now = [datetime(2026, 7, 11, 11, 45, 0)]
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="projection-terminal")
        draft = create_draft(db, org, suffix="projection-terminal")
        service = ProductUGCGenerationQueueService(db, clock=lambda: now[0])
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="projection-terminal-job",
            max_attempts=1,
        ).job
        batch, tasks = attach_mass_generation(db, org, user, job)

        foreign_org, foreign_user = create_scope(
            db,
            slug="projection-foreign",
            email="foreign@projection.test",
        )
        foreign_task = models.CreatorTask(
            organization_id=foreign_org.id,
            assignee_user_profile_id=foreign_user.id,
            created_by_user_profile_id=foreign_user.id,
            mass_operation_batch_id=batch.id,
            product_ugc_recipe_draft_id=draft.id,
            task_type="review_generated_video",
            title="Must remain outside projection",
            status="todo",
            priority=3,
            blockers_json=[],
            result_json={},
            idempotency_key="projection-foreign-task",
        )
        db.add(foreign_task)
        db.commit()

        leased = service.lease_job(job.id, worker_id="projection-terminal-worker")
        disposition = service.fail(
            job.id,
            lease_token=leased.lease_token,
            error="provider permanently rejected the request",
            error_code="PROVIDER_REJECTED",
            retryable=False,
        )
        project_mass_generation_queue_state(db, disposition.job, now=now[0])
        project_mass_generation_queue_state(db, disposition.job, now=now[0])
        db.commit()

        db.refresh(batch)
        db.refresh(tasks[0])
        db.refresh(foreign_task)
        assert disposition.will_retry is False
        assert tasks[0].status == "blocked"
        assert len(tasks[0].blockers_json) == 1
        blocker = tasks[0].blockers_json[0]
        assert blocker["code"] == "generation_terminal_failure"
        assert blocker["generation_job_id"] == job.id
        assert "Owner/admin" in blocker["action"]
        failure = tasks[0].result_json["generation_failure"]
        assert failure["error_code"] == "PROVIDER_REJECTED"
        assert "ручной повтор" in failure["action"]
        assert batch.status == "completed_with_errors"
        assert batch.total_failed == 1
        assert batch.results_json[0]["status"] == "failed_terminal"
        assert len(batch.errors_json) == 1
        assert batch.errors_json[0]["generation_job_id"] == job.id
        assert foreign_task.status == "todo"
        assert foreign_task.blockers_json == []


def test_manual_retry_reopens_only_generation_failure_projection():
    now = [datetime(2026, 7, 11, 11, 50, 0)]
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="projection-manual-retry")
        draft = create_draft(db, org, suffix="projection-manual-retry")
        service = ProductUGCGenerationQueueService(db, clock=lambda: now[0])
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="projection-manual-retry-job",
            max_attempts=1,
        ).job
        batch, tasks = attach_mass_generation(db, org, user, job)
        leased = service.lease_job(job.id, worker_id="projection-manual-retry-worker")
        terminal = service.fail(
            job.id,
            lease_token=leased.lease_token,
            error="local storage was temporarily unavailable",
            error_code="STORAGE_UNAVAILABLE",
            retryable=True,
        )
        assert terminal.job.terminal_reason == "retry_exhausted"

        retried = service.manual_retry(
            job.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
        )

        db.refresh(batch)
        db.refresh(tasks[0])
        assert retried.status == "retry_wait"
        assert tasks[0].status == "todo"
        assert tasks[0].blockers_json == []
        assert "generation_failure" not in tasks[0].result_json
        assert tasks[0].result_json["last_generation_failure"]["error_code"] == "STORAGE_UNAVAILABLE"
        assert batch.status == "queued"
        assert batch.total_failed == 0
        assert batch.completed_at is None
        assert batch.errors_json == []
        assert batch.results_json[0]["status"] == "retry_wait"


def test_quarantine_blocks_mass_work_until_owner_reconciliation_reopens_it():
    now = [datetime(2026, 7, 11, 11, 52, 0)]
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="projection-quarantine")
        draft = create_draft(db, org, suffix="projection-quarantine")
        service = ProductUGCGenerationQueueService(db, clock=lambda: now[0])
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="projection-quarantine-job",
        ).job
        leased = service.lease_job(job.id, worker_id="projection-quarantine-worker")
        service.begin_provider_submission(job.id, lease_token=leased.lease_token)
        # This test exercises failure projection after an already-ambiguous
        # legacy submit. Attach the synthetic mass lineage only after the spend
        # guard; real mass jobs must carry the full immutable snapshot contract.
        batch, tasks = attach_mass_generation(db, org, user, job)

        quarantined = service.fail(
            job.id,
            lease_token=leased.lease_token,
            error="provider response was lost after the paid submit",
        )
        db.refresh(batch)
        db.refresh(tasks[0])
        assert quarantined.will_retry is False
        assert quarantined.quarantined is True
        assert tasks[0].status == "blocked"
        assert tasks[0].blockers_json[0]["code"] == (
            "generation_quarantine_requires_reconciliation"
        )
        assert "Автоматический повтор запрещён" in tasks[0].blockers_json[0]["action"]
        assert batch.status == "completed_with_errors"
        assert batch.total_failed == 1

        reconciled = service.reconcile_confirm_no_provider_submission(
            job.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
            evidence_reference="provider-console-case-projection-quarantine",
            reason=(
                "Provider console history and support evidence confirm that no generation "
                "submission exists."
            ),
            idempotency_key="projection-quarantine-reconciliation",
            confirmed_no_submission=True,
        )

        db.refresh(batch)
        db.refresh(tasks[0])
        assert reconciled.job.status == "retry_wait"
        assert tasks[0].status == "todo"
        assert tasks[0].blockers_json == []
        assert batch.status == "queued"
        assert batch.total_failed == 0
        assert batch.errors_json == []


def test_multi_item_batch_finishes_with_errors_after_other_output_is_ready():
    now = datetime(2026, 7, 11, 11, 55, 0)
    with QueueTestSession() as db:
        org, user = create_scope(db, slug="projection-multi")
        first_draft = create_draft(db, org, suffix="projection-multi-1")
        second_draft = create_draft(db, org, suffix="projection-multi-2")
        service = ProductUGCGenerationQueueService(db, clock=lambda: now)
        first_job = service.enqueue(
            draft_id=first_draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="projection-multi-job-1",
            max_attempts=1,
        ).job
        second_job = service.enqueue(
            draft_id=second_draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="projection-multi-job-2",
            max_attempts=1,
        ).job
        batch, tasks = attach_mass_generation(db, org, user, first_job, second_job)

        leased = service.lease_job(first_job.id, worker_id="projection-multi-worker")
        service.fail(
            first_job.id,
            lease_token=leased.lease_token,
            error="first item failed permanently",
            retryable=False,
        )
        db.refresh(batch)
        assert batch.status == "running"
        assert batch.total_failed == 1
        assert batch.completed_at is None

        project_mass_generation_ready(
            db,
            second_job,
            media_artifact_public_id="artifact-ready-2",
            now=now,
        )
        db.commit()
        db.refresh(batch)
        db.refresh(tasks[1])
        assert batch.status == "completed_with_errors"
        assert batch.total_failed == 1
        assert batch.completed_at == now
        assert [item["status"] for item in batch.results_json] == [
            "failed_terminal",
            "ready_for_review",
        ]


def test_spend_guard_without_provider_task_is_quarantined_and_never_retryable():
    now = [datetime(2026, 7, 11, 12, 0, 0)]
    clock = lambda: now[0]
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db, clock=clock)
        queued = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="ambiguous-submit",
        ).job
        leased = service.lease_job(queued.id, worker_id="worker-a", lease_seconds=30)
        service.begin_provider_submission(queued.id, lease_token=leased.lease_token, lease_seconds=30)

        now[0] += timedelta(seconds=31)
        report = service.reconcile_stale(stale_after_seconds=0)
        job = db.get(models.ProductUGCGenerationJob, queued.id)
        assert report.quarantined == 1
        assert job.status == "quarantined"
        assert job.terminal_reason == "provider_submission_outcome_unknown"
        assert db.get(models.ProductUGCRecipeDraft, draft.id).status == "provider_submission_unknown"
        assert service.lease_job(job.id, worker_id="unsafe-resubmit") is None
        with pytest.raises(ProductUGCSubmissionAmbiguous):
            service.manual_retry(
                job.id,
                organization_id=org.id,
                actor_user_profile_id=user.id,
            )


def test_worker_submit_exception_is_at_most_once_and_quarantined(monkeypatch):
    calls = {"create": 0}

    class AmbiguousProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise TimeoutError("connection closed after request body was sent")

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-only-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.runway_recipes.product_ugc_service.ProductUGCRecipeService.provider_request",
        lambda self, draft: object(),
    )

    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        job = ProductUGCGenerationQueueService(db).enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="worker-ambiguous",
        ).job
        worker = ProductUGCGenerationWorker(db, provider_factory=AmbiguousProvider, sleep=lambda _: None)
        first = worker.process_job(job.id)
        second = worker.process_job(job.id)

        assert calls["create"] == 1
        assert first.status == second.status == "quarantined"
        assert second.provider_task_id is None
        assert second.spend_guarded_at is not None


def test_direct_runner_cannot_bypass_a_durable_job_or_spend_twice(monkeypatch):
    calls = {"create": 0}

    class ForbiddenDirectProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("direct provider submission must be blocked")

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-only-secret")
    get_settings.cache_clear()

    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        job = ProductUGCGenerationQueueService(db).enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="no-direct-bypass",
        ).job
        with pytest.raises(RunwayRecipeError, match="durable queue"):
            ProductUGCRecipeRunner(
                db,
                provider_factory=ForbiddenDirectProvider,
                sleep=lambda _: None,
            ).run(draft.id, real_run=True, preclaimed=True)

        db.expire_all()
        assert calls["create"] == 0
        assert db.get(models.ProductUGCGenerationJob, job.id).status == "queued"
        assert db.get(models.ProductUGCRecipeDraft, draft.id).status == "provider_launching"


def test_retry_with_provider_task_resumes_poll_and_download_without_new_submit(monkeypatch, tmp_path):
    calls = {"create": 0, "poll": 0, "download": 0}

    class ResumeProvider:
        def create_product_ugc(self, request):
            calls["create"] += 1
            raise AssertionError("existing provider task must never be submitted again")

        def get_status(self, provider_job_id):
            calls["poll"] += 1
            assert provider_job_id == "existing-provider-task"
            return ProviderVideoStatus(
                provider_job_id=provider_job_id,
                status="SUCCEEDED",
                raw_response={"id": provider_job_id, "status": "SUCCEEDED"},
            )

        def download_outputs(self, provider_job_id, target_dir):
            calls["download"] += 1
            target_dir.mkdir(parents=True, exist_ok=True)
            output = target_dir / "resumed.mp4"
            output.write_bytes(b"durable-resumed-video")
            return [output]

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-only-secret")
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "media"))
    get_settings.cache_clear()

    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db, retry_base_seconds=1)
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="resume-provider-task",
        ).job
        leased = service.lease_job(job.id, worker_id="crashed-worker")
        service.begin_provider_submission(job.id, lease_token=leased.lease_token)
        service.record_provider_submission(
            job.id,
            lease_token=leased.lease_token,
            provider_task_id="existing-provider-task",
            provider_status="PENDING",
        )
        service.fail(
            job.id,
            lease_token=leased.lease_token,
            error="poll transport failed",
            retryable=True,
        )
        persisted = db.get(models.ProductUGCGenerationJob, job.id)
        persisted.next_attempt_at = naive_utcnow() - timedelta(seconds=1)
        db.commit()

        result = ProductUGCGenerationWorker(
            db,
            provider_factory=ResumeProvider,
            sleep=lambda _: None,
        ).process_job(job.id)
        draft = db.get(models.ProductUGCRecipeDraft, draft.id)
        assert result.status == "succeeded"
        assert result.provider_task_id == "existing-provider-task"
        assert calls == {"create": 0, "poll": 1, "download": 1}
        assert draft.status == "generated_needs_human_review"
        assert len(draft.local_output_paths_json) == 1


def test_restart_reconciliation_recovers_known_task_and_quarantines_unknown_submit():
    old = naive_utcnow() - timedelta(hours=1)
    with QueueTestSession() as db:
        org, _user = create_scope(db)
        unknown = create_draft(db, org, status="provider_launching", suffix="unknown")
        known = create_draft(db, org, status="provider_submitted", suffix="known")
        known.provider_task_id = "known-provider-task"
        known.provider_status = "RUNNING"
        unknown.updated_at = old
        known.updated_at = old
        db.commit()

        report = ProductUGCGenerationQueueService(db).reconcile_stale(stale_after_seconds=300)
        unknown_job = db.scalar(
            select(models.ProductUGCGenerationJob).where(
                models.ProductUGCGenerationJob.draft_id == unknown.id
            )
        )
        known_job = db.scalar(
            select(models.ProductUGCGenerationJob).where(
                models.ProductUGCGenerationJob.draft_id == known.id
            )
        )
        assert report.quarantined == 1
        assert report.recovered_drafts == 1
        assert unknown_job.status == "quarantined"
        assert unknown_job.provider_task_id is None
        assert known_job.status == "retry_wait"
        assert known_job.provider_task_id == "known-provider-task"
        assert db.get(models.ProductUGCRecipeDraft, unknown.id).status == "provider_submission_unknown"
        assert db.get(models.ProductUGCRecipeDraft, known.id).status == "provider_submitted"


def test_manual_retry_and_summary_expose_safe_operator_state_only():
    now = [datetime(2026, 7, 11, 13, 0, 0)]
    clock = lambda: now[0]
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org)
        service = ProductUGCGenerationQueueService(db, clock=clock)
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="manual-retry-summary",
            max_attempts=1,
        ).job
        leased = service.lease_job(job.id, worker_id="worker-secret")
        terminal = service.fail(
            job.id,
            lease_token=leased.lease_token,
            error="pre-submit configuration was temporarily unavailable",
            retryable=True,
        ).job
        assert terminal.status == "failed_terminal"

        retried = service.manual_retry(
            job.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
        )
        summary = service.summary(retried)
        assert retried.status == "retry_wait"
        assert retried.max_attempts == 2
        assert summary["will_retry"] is True
        assert summary["attempt_count"] == 1
        assert "lease_token" not in summary
        assert "lease_owner" not in summary
        assert summary["terminal_reason"] is None


def test_queue_summary_redacts_credentials_and_signed_url_parameters():
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org, suffix="redaction")
        service = ProductUGCGenerationQueueService(db)
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="queue-secret-redaction",
        ).job
        leased = service.lease_job(job.id, worker_id="redaction-worker")
        failed = service.fail(
            job.id,
            lease_token=leased.lease_token,
            error=(
                "Bearer bearer-value token=token-value "
                "sk-1234567890 https://provider.test/output?signature=signed-value"
            ),
            retryable=False,
        ).job
        summary = service.summary(failed)
        safe_message = summary["last_error_message"]
        assert "bearer-value" not in safe_message
        assert "token-value" not in safe_message
        assert "sk-1234567890" not in safe_message
        assert "signed-value" not in safe_message
        assert "[redacted" in safe_message


def test_worker_health_is_durable_secret_free_and_reports_queue_lag():
    now = [datetime(2026, 7, 11, 14, 0, 0)]
    clock = lambda: now[0]
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft = create_draft(db, org, suffix="health")
        service = ProductUGCGenerationQueueService(db, clock=clock)
        job = service.enqueue(
            draft_id=draft.id,
            organization_id=org.id,
            requested_by_user_profile_id=user.id,
            idempotency_key="worker-health-lag",
        ).job

        service.record_worker_heartbeat(
            worker_id="ephemeral-web-background",
            state="idle",
            supervised=False,
        )
        before = service.operational_health(
            organization_id=org.id,
            healthy_within_seconds=30,
        )
        assert before["worker_ready"] is False
        assert before["ready_jobs"] == 1
        assert before["readiness"] == "blocked"

        row = service.record_worker_heartbeat(
            worker_id="host-with-sensitive-topology:1234:opaque-instance",
            state="idle",
            supervised=True,
        )
        assert row.worker_key != "host-with-sensitive-topology:1234:opaque-instance"
        assert len(row.worker_key) == 64
        assert not hasattr(row, "worker_id")
        healthy = service.operational_health(
            organization_id=org.id,
            healthy_within_seconds=30,
        )
        assert healthy["worker_ready"] is True
        assert healthy["worker_state"] == "idle"
        assert healthy["queue_lag_seconds"] == 0

        now[0] += timedelta(seconds=45)
        stale = service.operational_health(
            organization_id=org.id,
            healthy_within_seconds=30,
        )
        assert stale["worker_ready"] is False
        assert stale["worker_state"] == "stale"
        assert stale["queue_lag_seconds"] == 45
        assert stale["attention_required"] is True
        assert "worker_key" not in stale
        assert "lease_token" not in stale
        assert db.get(models.ProductUGCGenerationJob, job.id).status == "queued"


def test_owner_attaches_verified_provider_task_with_append_only_idempotent_evidence():
    with QueueTestSession() as db:
        org, user = create_scope(db)
        draft, quarantined = quarantine_ambiguous_job(db, org, user, key="attach-existing")
        service = ProductUGCGenerationQueueService(db)

        first = service.reconcile_attach_existing_provider_task(
            quarantined.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
            provider_task_id="provider-task-existing-42",
            evidence_reference="provider-audit-2026-42",
            reason="Нашёл точную задачу по времени, товару и параметрам запуска.",
            idempotency_key="reconcile:attach-existing:42",
            confirmed_provider_task=True,
        )
        replay = service.reconcile_attach_existing_provider_task(
            quarantined.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
            provider_task_id="provider-task-existing-42",
            evidence_reference="provider-audit-2026-42",
            reason="Нашёл точную задачу по времени, товару и параметрам запуска.",
            idempotency_key="reconcile:attach-existing:42",
            confirmed_provider_task=True,
        )

        assert first.created is True
        assert replay.created is False
        assert replay.reconciliation.id == first.reconciliation.id
        assert first.job.status == "retry_wait"
        assert first.job.provider_task_id == "provider-task-existing-42"
        assert first.job.spend_guarded_at is not None
        assert db.get(models.ProductUGCRecipeDraft, draft.id).provider_task_id == "provider-task-existing-42"
        assert db.scalar(
            select(func.count()).select_from(models.ProductUGCQueueReconciliation)
        ) == 1
        audit = db.scalar(
            select(models.AuditLog).where(
                models.AuditLog.action == "product_ugc_queue_quarantine_reconciled"
            )
        )
        assert audit.metadata_json == {
            "reconciliation_id": first.reconciliation.id,
            "resolution": "attach_existing_provider_task",
        }
        assert "provider-task-existing-42" not in str(audit.metadata_json)

        leased = service.lease_job(first.job.id, worker_id="resume-known-task")
        guarded = service.begin_provider_submission(
            first.job.id,
            lease_token=leased.lease_token,
        )
        assert guarded.provider_task_id == "provider-task-existing-42"
        assert guarded.provider_status == "PENDING_RECONCILED"

        record = db.get(models.ProductUGCQueueReconciliation, first.reconciliation.id)
        record.reason = "Попытка изменить неизменяемое доказательство после решения."
        with pytest.raises(ValueError, match="append-only"):
            db.commit()
        db.rollback()


def test_no_submission_confirmation_requires_owner_and_reopens_exactly_one_spend_guard():
    with QueueTestSession() as db:
        org, user = create_scope(db)
        _draft, quarantined = quarantine_ambiguous_job(db, org, user, key="confirm-absent")
        membership = db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == org.id,
                models.Membership.user_profile_id == user.id,
            )
        )
        membership.role = "reviewer"
        db.commit()
        service = ProductUGCGenerationQueueService(db)

        with pytest.raises(ProductUGCQueueOwnershipError, match="owner or admin"):
            service.reconcile_confirm_no_provider_submission(
                quarantined.id,
                organization_id=org.id,
                actor_user_profile_id=user.id,
                evidence_reference="support-case-absent-1",
                reason="Поддержка и история задач подтверждают отсутствие отправки.",
                idempotency_key="reconcile:no-submit:1",
                confirmed_no_submission=True,
            )
        membership.role = "owner"
        db.commit()

        with pytest.raises(ProductUGCQueueConflict, match="Explicit confirmation"):
            service.reconcile_confirm_no_provider_submission(
                quarantined.id,
                organization_id=org.id,
                actor_user_profile_id=user.id,
                evidence_reference="support-case-absent-1",
                reason="Поддержка и история задач подтверждают отсутствие отправки.",
                idempotency_key="reconcile:no-submit:1",
                confirmed_no_submission=False,
            )
        with pytest.raises(ProductUGCQueueConflict, match="credentials"):
            service.reconcile_confirm_no_provider_submission(
                quarantined.id,
                organization_id=org.id,
                actor_user_profile_id=user.id,
                evidence_reference="support-case-absent-1",
                reason="Проверил token=secret-value и считаю, что задачи у провайдера нет.",
                idempotency_key="reconcile:no-submit:secret",
                confirmed_no_submission=True,
            )

        result = service.reconcile_confirm_no_provider_submission(
            quarantined.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
            evidence_reference="support-case-absent-1",
            reason="Поддержка и история задач подтверждают отсутствие отправки.",
            idempotency_key="reconcile:no-submit:1",
            confirmed_no_submission=True,
        )
        replay = service.reconcile_confirm_no_provider_submission(
            quarantined.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
            evidence_reference="support-case-absent-1",
            reason="Поддержка и история задач подтверждают отсутствие отправки.",
            idempotency_key="reconcile:no-submit:1",
            confirmed_no_submission=True,
        )
        assert result.created is True
        assert replay.created is False
        assert result.job.status == "retry_wait"
        assert result.job.spend_guarded_at is None
        assert result.job.provider_task_id is None
        assert result.job.requested_by_user_profile_id == user.id

        leased = service.lease_job(result.job.id, worker_id="new-authorized-attempt")
        guarded = service.begin_provider_submission(
            result.job.id,
            lease_token=leased.lease_token,
        )
        assert guarded.spend_guarded_at is not None
        assert guarded.provider_task_id is None
        second_incident = service.fail(
            result.job.id,
            lease_token=leased.lease_token,
            error="second submit response was also lost",
        ).job
        assert second_incident.status == "quarantined"
        with pytest.raises(ProductUGCQueueConflict, match="earlier quarantine incident"):
            service.reconcile_confirm_no_provider_submission(
                result.job.id,
                organization_id=org.id,
                actor_user_profile_id=user.id,
                evidence_reference="support-case-absent-1",
                reason="Поддержка и история задач подтверждают отсутствие отправки.",
                idempotency_key="reconcile:no-submit:1",
                confirmed_no_submission=True,
            )


def test_database_trigger_rejects_direct_reconciliation_mutation():
    with QueueTestSession() as db:
        org, user = create_scope(db)
        _draft, quarantined = quarantine_ambiguous_job(db, org, user, key="trigger-guard")
        result = ProductUGCGenerationQueueService(db).reconcile_confirm_no_provider_submission(
            quarantined.id,
            organization_id=org.id,
            actor_user_profile_id=user.id,
            evidence_reference="support-trigger-guard",
            reason="Проверка кабинета подтверждает, что задачи у провайдера нет.",
            idempotency_key="reconcile:trigger-guard",
            confirmed_no_submission=True,
        )
        reconciliation_id = result.reconciliation.id

    _ensure_product_ugc_generation_queue_schema(queue_test_engine)
    with pytest.raises(DatabaseError, match="append-only"):
        with queue_test_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE product_ugc_queue_reconciliations "
                    "SET reason = 'forbidden direct rewrite' WHERE id = :record_id"
                ),
                {"record_id": reconciliation_id},
            )


def test_legacy_sqlite_install_creates_queue_table_and_unique_indexes(tmp_path):
    bind = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    Base.metadata.create_all(bind=bind)
    models.ProductUGCGenerationJob.__table__.drop(bind=bind)

    _ensure_product_ugc_generation_queue_schema(bind)

    db_inspector = inspect(bind)
    assert "product_ugc_generation_jobs" in db_inspector.get_table_names()
    indexes = {row["name"] for row in db_inspector.get_indexes("product_ugc_generation_jobs")}
    assert "uq_product_ugc_generation_job_draft" in indexes
    assert "uq_product_ugc_generation_job_idempotency" in indexes
    assert "uq_product_ugc_generation_job_provider_task" in indexes
    assert "product_ugc_queue_worker_heartbeats" in db_inspector.get_table_names()
    assert "product_ugc_queue_reconciliations" in db_inspector.get_table_names()
    with bind.connect() as connection:
        trigger_names = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND name LIKE 'product_ugc_queue_reconciliation_%'"
                )
            ).scalars()
        )
    assert trigger_names == {
        "product_ugc_queue_reconciliation_no_update",
        "product_ugc_queue_reconciliation_no_delete",
    }
