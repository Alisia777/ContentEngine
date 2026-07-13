from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import hashlib
import re
import uuid

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.product_ugc_queue.errors import (
    ProductUGCQueueConflict,
    ProductUGCQueueLeaseError,
    ProductUGCQueueOwnershipError,
    ProductUGCSubmissionAmbiguous,
)
from app.product_ugc_queue.generation_snapshot_guard import (
    validate_mass_generation_pre_spend,
)
from app.product_ugc_queue.mass_projection import project_mass_generation_queue_state
from app.product_ugc_queue.types import (
    EnqueueResult,
    FailureDisposition,
    QuarantineReconciliationResult,
    QueueOperationalHealth,
    QueueSummary,
    ReconciliationResult,
)


READY_STATUSES = frozenset({"queued", "retry_wait"})
LEASED_STATUSES = frozenset({"leased", "provider_launching", "provider_processing", "downloading"})
PROVIDER_FAILURE_STATUSES = frozenset({"FAILED", "FAILURE", "CANCELLED", "CANCELED", "ERROR"})
RECOVERABLE_DRAFT_STATUSES = frozenset(
    {"provider_launching", "provider_submitted", "provider_processing", "processing", "generating"}
)
WORKER_STATES = frozenset({"starting", "polling", "idle", "working", "ready", "error", "stopping"})
RECONCILIATION_ATTACH_TASK = "attach_existing_provider_task"
RECONCILIATION_CONFIRM_NO_SUBMISSION = "confirm_no_provider_submission"


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def stale_lease_reconciliation_query(now: datetime):
    """Lock expired leases so concurrent reconcilers cannot erase a fresh lease."""

    return (
        select(models.ProductUGCGenerationJob)
        .where(
            models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES),
            or_(
                models.ProductUGCGenerationJob.lease_expires_at.is_(None),
                models.ProductUGCGenerationJob.lease_expires_at <= now,
            ),
        )
        .order_by(models.ProductUGCGenerationJob.id)
        .with_for_update(skip_locked=True)
    )


class ProductUGCGenerationQueueService:
    """Transactional queue with leases and an at-most-once provider spend guard."""

    def __init__(
        self,
        db: Session,
        *,
        clock: Callable[[], datetime] = utcnow,
        retry_base_seconds: int = 5,
        retry_max_seconds: int = 300,
    ) -> None:
        self.db = db
        self.clock = clock
        self.retry_base_seconds = max(1, retry_base_seconds)
        self.retry_max_seconds = max(self.retry_base_seconds, retry_max_seconds)

    def enqueue(
        self,
        *,
        draft_id: int,
        organization_id: int,
        requested_by_user_profile_id: int,
        idempotency_key: str,
        max_attempts: int = 5,
        allow_unscoped_product: bool = False,
    ) -> EnqueueResult:
        key = self._validate_idempotency_key(idempotency_key)
        if not 1 <= max_attempts <= 20:
            raise ProductUGCQueueConflict("max_attempts must be between 1 and 20.")
        self._validate_actor(organization_id, requested_by_user_profile_id)

        existing = self.db.scalar(
            select(models.ProductUGCGenerationJob).where(
                models.ProductUGCGenerationJob.idempotency_key == key
            )
        )
        if existing:
            self._validate_existing_scope(existing, draft_id=draft_id, organization_id=organization_id)
            return EnqueueResult(job=existing, created=False)

        existing = self.db.scalar(
            select(models.ProductUGCGenerationJob).where(
                models.ProductUGCGenerationJob.draft_id == draft_id
            )
        )
        if existing:
            self._validate_existing_scope(existing, draft_id=draft_id, organization_id=organization_id)
            return EnqueueResult(job=existing, created=False)

        draft = self.db.get(models.ProductUGCRecipeDraft, draft_id)
        if not draft:
            raise ProductUGCQueueConflict(f"Product UGC draft {draft_id} was not found.")
        product = self.db.get(models.Product, draft.product_id)
        if not product:
            raise ProductUGCQueueConflict(f"Product {draft.product_id} was not found.")
        if product.organization_id != organization_id:
            if not (allow_unscoped_product and product.organization_id is None):
                raise ProductUGCQueueOwnershipError("Product UGC draft is outside this organization.")
        if draft.status != "ready_for_paid_preflight" or draft.blockers_json:
            raise ProductUGCQueueConflict("Only a paid-preflight-ready draft can be enqueued.")

        now = self.clock()
        job = models.ProductUGCGenerationJob(
            draft_id=draft.id,
            organization_id=organization_id,
            requested_by_user_profile_id=requested_by_user_profile_id,
            idempotency_key=key,
            status="queued",
            attempt_count=0,
            max_attempts=max_attempts,
            next_attempt_at=now,
            provider="runway_product_ugc_recipe",
            provider_status="QUEUED",
            metadata_json={"source": "public_paid_action", "spend_policy": "at_most_once"},
        )
        self.db.add(job)
        draft.status = "provider_launching"
        draft.provider_status = "QUEUED"
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            winner = self.db.scalar(
                select(models.ProductUGCGenerationJob).where(
                    or_(
                        models.ProductUGCGenerationJob.draft_id == draft_id,
                        models.ProductUGCGenerationJob.idempotency_key == key,
                    )
                )
            )
            if not winner:
                raise
            self._validate_existing_scope(winner, draft_id=draft_id, organization_id=organization_id)
            return EnqueueResult(job=winner, created=False)
        self.db.refresh(job)
        return EnqueueResult(job=job, created=True)

    def lease_job(
        self,
        job_id: int,
        *,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> models.ProductUGCGenerationJob | None:
        if not worker_id.strip():
            raise ProductUGCQueueLeaseError("worker_id is required.")
        now = self.clock()
        expires = now + timedelta(seconds=max(5, lease_seconds))
        token = uuid.uuid4().hex
        result = self.db.execute(
            update(models.ProductUGCGenerationJob)
            .where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.status.in_(READY_STATUSES),
                models.ProductUGCGenerationJob.next_attempt_at <= now,
                models.ProductUGCGenerationJob.attempt_count
                < models.ProductUGCGenerationJob.max_attempts,
            )
            .values(
                status="leased",
                attempt_count=models.ProductUGCGenerationJob.attempt_count + 1,
                lease_owner=worker_id[:255],
                lease_token=token,
                lease_expires_at=expires,
                heartbeat_at=now,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            return None
        self._touch_worker_heartbeat(
            worker_id=worker_id,
            state="working",
            current_job_id=job_id,
            now=now,
        )
        self.db.commit()
        job = self.db.get(models.ProductUGCGenerationJob, job_id)
        return job

    def lease_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 30,
        organization_id: int | None = None,
    ) -> models.ProductUGCGenerationJob | None:
        now = self.clock()
        query = (
            select(models.ProductUGCGenerationJob.id)
            .where(
                models.ProductUGCGenerationJob.status.in_(READY_STATUSES),
                models.ProductUGCGenerationJob.next_attempt_at <= now,
                models.ProductUGCGenerationJob.attempt_count
                < models.ProductUGCGenerationJob.max_attempts,
            )
            .order_by(
                models.ProductUGCGenerationJob.next_attempt_at.asc(),
                models.ProductUGCGenerationJob.created_at.asc(),
                models.ProductUGCGenerationJob.id.asc(),
            )
            .limit(1)
        )
        if organization_id is not None:
            query = query.where(models.ProductUGCGenerationJob.organization_id == organization_id)
        candidate_id = self.db.scalar(query)
        if candidate_id is None:
            return None
        return self.lease_job(candidate_id, worker_id=worker_id, lease_seconds=lease_seconds)

    def heartbeat(
        self,
        job_id: int,
        *,
        lease_token: str,
        lease_seconds: int = 30,
    ) -> models.ProductUGCGenerationJob:
        now = self.clock()
        worker_id = self.db.scalar(
            select(models.ProductUGCGenerationJob.lease_owner).where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.lease_token == lease_token,
            )
        )
        result = self.db.execute(
            update(models.ProductUGCGenerationJob)
            .where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.lease_token == lease_token,
                models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES),
                models.ProductUGCGenerationJob.lease_expires_at > now,
            )
            .values(
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=max(5, lease_seconds)),
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise ProductUGCQueueLeaseError("Generation lease is no longer owned by this worker.")
        if worker_id:
            self._touch_worker_heartbeat(
                worker_id=worker_id,
                state="working",
                current_job_id=job_id,
                now=now,
            )
        self.db.commit()
        return self._require_job(job_id)

    def require_live_lease(
        self,
        job_id: int,
        *,
        lease_token: str,
    ) -> models.ProductUGCGenerationJob:
        job = self._require_job(job_id)
        now = self.clock()
        if (
            job.lease_token != lease_token
            or job.status not in LEASED_STATUSES
            or not job.lease_expires_at
            or job.lease_expires_at <= now
        ):
            raise ProductUGCQueueLeaseError("Generation lease expired or belongs to another worker.")
        return job

    def begin_provider_submission(
        self,
        job_id: int,
        *,
        lease_token: str,
        lease_seconds: int = 30,
        provider_payload: object | None = None,
    ) -> models.ProductUGCGenerationJob:
        job = self.require_live_lease(job_id, lease_token=lease_token)
        if job.provider_task_id:
            return job
        if job.spend_guarded_at:
            raise ProductUGCSubmissionAmbiguous(
                "Provider submission was already spend-guarded but has no provider task id."
            )
        self._validate_initial_spend_authority(job)
        validate_mass_generation_pre_spend(
            self.db,
            job,
            provider_payload=provider_payload,
        )
        now = self.clock()
        result = self.db.execute(
            update(models.ProductUGCGenerationJob)
            .where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.lease_token == lease_token,
                models.ProductUGCGenerationJob.status == "leased",
                models.ProductUGCGenerationJob.spend_guarded_at.is_(None),
                models.ProductUGCGenerationJob.provider_task_id.is_(None),
                models.ProductUGCGenerationJob.lease_expires_at > now,
            )
            .values(
                status="provider_launching",
                spend_guarded_at=now,
                provider_status="SUBMITTING",
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=max(5, lease_seconds)),
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            current = self._require_job(job_id)
            if current.spend_guarded_at and not current.provider_task_id:
                raise ProductUGCSubmissionAmbiguous(
                    "Provider submission outcome is unknown; automatic resubmission is forbidden."
                )
            raise ProductUGCQueueLeaseError("Could not acquire the provider spend guard.")
        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft:
            draft.status = "provider_launching"
            draft.provider_status = "SUBMITTING"
        self.db.commit()
        return self._require_job(job_id)

    def validate_provider_submission_inputs(
        self,
        job_id: int,
        *,
        lease_token: str,
    ) -> models.ProductUGCGenerationJob:
        """Validate immutable mass inputs before request materialization/preflight."""

        job = self.require_live_lease(job_id, lease_token=lease_token)
        if job.provider_task_id:
            return job
        validate_mass_generation_pre_spend(
            self.db,
            job,
            provider_payload=None,
            require_provider_payload=False,
        )
        # This is an early, DB-only stale-input check. Release its row locks
        # before private-object materialization so up to 50 jobs in one batch
        # do not serialize behind remote storage I/O. begin_provider_submission
        # repeats the full validation and commits the atomic spend guard.
        self.db.commit()
        return job

    def record_provider_submission(
        self,
        job_id: int,
        *,
        lease_token: str,
        provider_task_id: str,
        provider_status: str,
        lease_seconds: int = 30,
    ) -> models.ProductUGCGenerationJob:
        task_id = provider_task_id.strip()
        if not task_id:
            raise ProductUGCQueueConflict("Provider task id is required after a paid submit.")
        job = self.require_live_lease(job_id, lease_token=lease_token)
        if job.provider_task_id:
            if job.provider_task_id != task_id:
                raise ProductUGCQueueConflict("Provider task identity cannot be replaced.")
            return job
        if not job.spend_guarded_at:
            raise ProductUGCQueueConflict("Provider submission must be spend-guarded before the network call.")
        now = self.clock()
        try:
            result = self.db.execute(
                update(models.ProductUGCGenerationJob)
                .where(
                    models.ProductUGCGenerationJob.id == job_id,
                    models.ProductUGCGenerationJob.lease_token == lease_token,
                    models.ProductUGCGenerationJob.provider_task_id.is_(None),
                    models.ProductUGCGenerationJob.spend_guarded_at.is_not(None),
                )
                .values(
                    status="provider_processing",
                    provider_task_id=task_id[:255],
                    provider_status=(provider_status or "PENDING")[:80],
                    provider_submitted_at=now,
                    heartbeat_at=now,
                    lease_expires_at=now + timedelta(seconds=max(5, lease_seconds)),
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                raise ProductUGCQueueConflict("Provider submission state changed concurrently.")
            draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
            if draft:
                draft.provider_task_id = task_id[:255]
                draft.provider_status = (provider_status or "PENDING")[:80]
                draft.status = "provider_submitted"
            if job.lease_owner:
                self._touch_worker_heartbeat(
                    worker_id=job.lease_owner,
                    state="working",
                    current_job_id=job_id,
                    now=now,
                )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ProductUGCQueueConflict("Provider task id is already attached to another generation job.") from exc
        return self._require_job(job_id)

    def record_provider_status(
        self,
        job_id: int,
        *,
        lease_token: str,
        provider_status: str,
        lease_seconds: int = 30,
    ) -> models.ProductUGCGenerationJob:
        job = self.require_live_lease(job_id, lease_token=lease_token)
        if not job.provider_task_id:
            raise ProductUGCQueueConflict("Cannot poll a job without a provider task id.")
        now = self.clock()
        status = (provider_status or "UNKNOWN").upper()[:80]
        result = self.db.execute(
            update(models.ProductUGCGenerationJob)
            .where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.lease_token == lease_token,
                models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES),
            )
            .values(
                status="provider_processing",
                provider_status=status,
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=max(5, lease_seconds)),
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise ProductUGCQueueLeaseError("Generation lease was lost while recording provider status.")
        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft:
            draft.status = "provider_submitted"
            draft.provider_status = status
        if job.lease_owner:
            self._touch_worker_heartbeat(
                worker_id=job.lease_owner,
                state="working",
                current_job_id=job_id,
                now=now,
            )
        self.db.commit()
        return self._require_job(job_id)

    def mark_downloading(
        self,
        job_id: int,
        *,
        lease_token: str,
        lease_seconds: int = 60,
    ) -> models.ProductUGCGenerationJob:
        job = self.require_live_lease(job_id, lease_token=lease_token)
        now = self.clock()
        result = self.db.execute(
            update(models.ProductUGCGenerationJob)
            .where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.lease_token == lease_token,
                models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES),
            )
            .values(
                status="downloading",
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=max(10, lease_seconds)),
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise ProductUGCQueueLeaseError("Generation lease was lost before download.")
        if job.lease_owner:
            self._touch_worker_heartbeat(
                worker_id=job.lease_owner,
                state="working",
                current_job_id=job_id,
                now=now,
            )
        self.db.commit()
        return self._require_job(job_id)

    def mark_succeeded(
        self,
        job_id: int,
        *,
        lease_token: str,
    ) -> models.ProductUGCGenerationJob:
        job = self.require_live_lease(job_id, lease_token=lease_token)
        if not job.provider_task_id:
            raise ProductUGCQueueConflict("A generation cannot succeed without a provider task id.")
        now = self.clock()
        worker_id = job.lease_owner
        result = self.db.execute(
            update(models.ProductUGCGenerationJob)
            .where(
                models.ProductUGCGenerationJob.id == job_id,
                models.ProductUGCGenerationJob.lease_token == lease_token,
                models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES),
            )
            .values(
                status="succeeded",
                provider_status="SUCCEEDED",
                completed_at=now,
                terminal_reason=None,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                next_attempt_at=now,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise ProductUGCQueueLeaseError("Generation lease was lost before completion.")
        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft:
            draft.status = "generated_needs_human_review"
            draft.provider_status = "SUCCEEDED"
            draft.human_review_status = "needs_human_review"
            draft.publishing_readiness = "blocked"
        if worker_id:
            self._touch_worker_heartbeat(
                worker_id=worker_id,
                state="ready",
                current_job_id=None,
                last_job_id=job_id,
                now=now,
            )
        self.db.commit()
        return self._require_job(job_id)

    def fail(
        self,
        job_id: int,
        *,
        lease_token: str,
        error: Exception | str,
        error_code: str = "WORKER_ERROR",
        retryable: bool = True,
        provider_terminal: bool = False,
    ) -> FailureDisposition:
        job = self._require_owned_lease(job_id, lease_token=lease_token)
        now = self.clock()
        worker_id = job.lease_owner
        message = self._safe_message(error)
        ambiguous = bool(job.spend_guarded_at and not job.provider_task_id)
        exhausted = job.attempt_count >= job.max_attempts
        if ambiguous:
            status = "quarantined"
            reason = "provider_submission_outcome_unknown"
        elif provider_terminal:
            status = "failed_terminal"
            reason = "provider_terminal_failure"
        elif not retryable:
            status = "failed_terminal"
            reason = "non_retryable_failure"
        elif exhausted:
            status = "failed_terminal"
            reason = "retry_exhausted"
        else:
            status = "retry_wait"
            reason = None

        will_retry = status == "retry_wait"
        delay = self._backoff_seconds(job.attempt_count) if will_retry else 0
        job.status = status
        job.last_error_code = error_code[:120]
        job.last_error_message = message
        job.terminal_reason = reason
        job.quarantined_at = now if status == "quarantined" else None
        job.completed_at = now if status in {"quarantined", "failed_terminal"} else None
        job.next_attempt_at = now + timedelta(seconds=delay)
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        job.heartbeat_at = now
        if ambiguous:
            metadata = dict(job.metadata_json or {})
            metadata["current_quarantine_incident_key"] = (
                metadata.get("current_quarantine_incident_key") or uuid.uuid4().hex
            )
            job.metadata_json = metadata

        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft:
            warnings = list(draft.warnings_json or [])
            warning = f"Generation worker: {message}"
            if warning not in warnings:
                warnings.append(warning)
            draft.warnings_json = warnings[-50:]
            draft.publishing_readiness = "blocked"
            if status == "quarantined":
                draft.status = "provider_submission_unknown"
                draft.provider_status = "UNKNOWN_REQUIRES_RECONCILIATION"
                draft.human_review_status = "needs_human_review"
            elif status == "failed_terminal":
                draft.status = "provider_failed"
                draft.provider_status = draft.provider_status or "FAILED"
                draft.human_review_status = "needs_human_review"
            elif job.provider_task_id:
                draft.status = "provider_submitted"
                draft.provider_task_id = job.provider_task_id
                draft.provider_status = job.provider_status or draft.provider_status
            else:
                draft.status = "provider_launching"
                draft.provider_status = "RETRY_WAIT"
        project_mass_generation_queue_state(self.db, job, now=now)
        if worker_id:
            self._touch_worker_heartbeat(
                worker_id=worker_id,
                state="ready",
                current_job_id=None,
                last_job_id=job_id,
                last_error_code=error_code,
                now=now,
            )
        self.db.commit()
        self.db.refresh(job)
        return FailureDisposition(job=job, will_retry=will_retry, quarantined=ambiguous)

    def manual_retry(
        self,
        job_id: int,
        *,
        organization_id: int,
        actor_user_profile_id: int,
    ) -> models.ProductUGCGenerationJob:
        """Requeue only when doing so cannot repeat an ambiguous provider submit."""

        self._validate_actor(organization_id, actor_user_profile_id)
        job = self._require_job(job_id)
        if job.organization_id != organization_id:
            raise ProductUGCQueueOwnershipError("Generation job is outside this organization.")
        if job.status in READY_STATUSES:
            return job
        if job.status == "quarantined" or (job.spend_guarded_at and not job.provider_task_id):
            raise ProductUGCSubmissionAmbiguous(
                "Unknown provider-submit outcome requires manual provider reconciliation; retry is forbidden."
            )
        if job.status != "failed_terminal":
            raise ProductUGCQueueConflict("Only a terminal failed job can be retried manually.")
        if (job.provider_status or "").upper() in PROVIDER_FAILURE_STATUSES:
            raise ProductUGCQueueConflict("A terminal provider task cannot be restarted as a new paid submit.")

        now = self.clock()
        metadata = dict(job.metadata_json or {})
        retries = list(metadata.get("manual_retries") or [])
        retries.append({"actor_user_profile_id": actor_user_profile_id, "at": now.isoformat()})
        metadata["manual_retries"] = retries[-20:]
        job.metadata_json = metadata
        job.status = "retry_wait"
        job.max_attempts = max(job.max_attempts, job.attempt_count + 1)
        job.next_attempt_at = now
        job.last_error_code = None
        job.last_error_message = None
        job.terminal_reason = None
        job.completed_at = None
        job.quarantined_at = None
        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft:
            draft.status = "provider_submitted" if job.provider_task_id else "provider_launching"
            draft.provider_status = job.provider_status or "RETRY_WAIT"
        project_mass_generation_queue_state(self.db, job, now=now)
        self.db.commit()
        self.db.refresh(job)
        return job

    def record_worker_heartbeat(
        self,
        *,
        worker_id: str,
        state: str,
        current_job_id: int | None = None,
        last_job_id: int | None = None,
        last_error_code: str | None = None,
        supervised: bool = False,
    ) -> models.ProductUGCQueueWorkerHeartbeat:
        """Persist worker liveness without storing its hostname/process identity."""

        now = self.clock()
        row = self._touch_worker_heartbeat(
            worker_id=worker_id,
            state=state,
            current_job_id=current_job_id,
            last_job_id=last_job_id,
            last_error_code=last_error_code,
            supervised=supervised,
            now=now,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def operational_health(
        self,
        *,
        organization_id: int | None = None,
        healthy_within_seconds: int = 120,
    ) -> QueueOperationalHealth:
        """Return a secret-free queue readiness and lag snapshot."""

        now = self.clock()
        healthy_window = max(30, min(int(healthy_within_seconds), 3600))
        ready_predicates = [
            models.ProductUGCGenerationJob.status.in_(READY_STATUSES),
            models.ProductUGCGenerationJob.next_attempt_at <= now,
            models.ProductUGCGenerationJob.attempt_count
            < models.ProductUGCGenerationJob.max_attempts,
        ]
        active_predicates = [models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES)]
        org_predicate = None
        if organization_id is not None:
            org_predicate = models.ProductUGCGenerationJob.organization_id == organization_id
            ready_predicates.append(org_predicate)
            active_predicates.append(org_predicate)

        ready_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(models.ProductUGCGenerationJob)
                .where(*ready_predicates)
            )
            or 0
        )
        active_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(models.ProductUGCGenerationJob)
                .where(*active_predicates)
            )
            or 0
        )
        oldest_due_at = self.db.scalar(
            select(func.min(models.ProductUGCGenerationJob.next_attempt_at)).where(
                *ready_predicates
            )
        )
        oldest_created_at = self.db.scalar(
            select(func.min(models.ProductUGCGenerationJob.created_at)).where(
                *ready_predicates
            )
        )
        stale_lease_predicates = [
            models.ProductUGCGenerationJob.status.in_(LEASED_STATUSES),
            or_(
                models.ProductUGCGenerationJob.lease_expires_at.is_(None),
                models.ProductUGCGenerationJob.lease_expires_at <= now,
            ),
        ]
        if org_predicate is not None:
            stale_lease_predicates.append(org_predicate)
        stale_lease_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(models.ProductUGCGenerationJob)
                .where(*stale_lease_predicates)
            )
            or 0
        )

        newest_worker = self.db.scalar(
            select(models.ProductUGCQueueWorkerHeartbeat)
            .where(
                models.ProductUGCQueueWorkerHeartbeat.is_supervised.is_(True),
                models.ProductUGCQueueWorkerHeartbeat.state != "stopping",
            )
            .order_by(
                models.ProductUGCQueueWorkerHeartbeat.heartbeat_at.desc(),
                models.ProductUGCQueueWorkerHeartbeat.id.desc(),
            )
            .limit(1)
        )
        heartbeat_age_seconds = None
        last_heartbeat_at = None
        worker_state = "not_seen"
        worker_ready = False
        if newest_worker is not None:
            heartbeat_age_seconds = max(
                0,
                int((now - newest_worker.heartbeat_at).total_seconds()),
            )
            last_heartbeat_at = newest_worker.heartbeat_at.isoformat()
            worker_ready = heartbeat_age_seconds <= healthy_window
            worker_state = newest_worker.state if worker_ready else "stale"

        queue_lag_seconds = (
            max(0, int((now - oldest_due_at).total_seconds())) if oldest_due_at else 0
        )
        oldest_ready_age_seconds = (
            max(0, int((now - oldest_created_at).total_seconds()))
            if oldest_created_at
            else 0
        )
        readiness = "ready" if worker_ready and stale_lease_count == 0 else "blocked"
        return {
            "readiness": readiness,
            "worker_state": worker_state,
            "worker_ready": worker_ready,
            "last_heartbeat_at": last_heartbeat_at,
            "heartbeat_age_seconds": heartbeat_age_seconds,
            "healthy_within_seconds": healthy_window,
            "ready_jobs": ready_count,
            "active_jobs": active_count,
            "stale_leases": stale_lease_count,
            "queue_lag_seconds": queue_lag_seconds,
            "oldest_ready_age_seconds": oldest_ready_age_seconds,
            "attention_required": bool(
                not worker_ready or stale_lease_count or queue_lag_seconds > healthy_window
            ),
        }

    def reconcile_attach_existing_provider_task(
        self,
        job_id: int,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        provider_task_id: str,
        evidence_reference: str,
        reason: str,
        idempotency_key: str,
        confirmed_provider_task: bool,
    ) -> QuarantineReconciliationResult:
        if not confirmed_provider_task:
            raise ProductUGCQueueConflict(
                "Explicit confirmation of the provider task is required."
            )
        task_id = self._validate_provider_task_id(provider_task_id)
        return self._reconcile_quarantine(
            job_id,
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            action=RECONCILIATION_ATTACH_TASK,
            provider_task_id=task_id,
            evidence_reference=evidence_reference,
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def reconcile_confirm_no_provider_submission(
        self,
        job_id: int,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        evidence_reference: str,
        reason: str,
        idempotency_key: str,
        confirmed_no_submission: bool,
    ) -> QuarantineReconciliationResult:
        if not confirmed_no_submission:
            raise ProductUGCQueueConflict(
                "Explicit confirmation that the provider has no submission is required."
            )
        return self._reconcile_quarantine(
            job_id,
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            action=RECONCILIATION_CONFIRM_NO_SUBMISSION,
            provider_task_id=None,
            evidence_reference=evidence_reference,
            reason=reason,
            idempotency_key=idempotency_key,
        )

    def _reconcile_quarantine(
        self,
        job_id: int,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        action: str,
        provider_task_id: str | None,
        evidence_reference: str,
        reason: str,
        idempotency_key: str,
    ) -> QuarantineReconciliationResult:
        """Atomically preserve evidence and release exactly one quarantined job."""

        self._validate_reconciliation_actor(organization_id, actor_user_profile_id)
        key = self._validate_idempotency_key(idempotency_key)
        evidence = self._validate_evidence_reference(evidence_reference)
        reason_text = self._validate_reconciliation_reason(reason)
        evidence_sha256 = self._reconciliation_evidence_sha256(
            action=action,
            provider_task_id=provider_task_id,
            evidence_reference=evidence,
            reason=reason_text,
        )

        existing = self.db.scalar(
            select(models.ProductUGCQueueReconciliation).where(
                models.ProductUGCQueueReconciliation.idempotency_key == key
            )
        )
        if existing is not None:
            job = self._require_job(job_id)
            if job.organization_id != organization_id:
                raise ProductUGCQueueOwnershipError(
                    "Generation job is outside this organization."
                )
            self._validate_existing_reconciliation(
                existing,
                job_id=job_id,
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action=action,
                provider_task_id=provider_task_id,
                evidence_sha256=evidence_sha256,
            )
            job_metadata = dict(job.metadata_json or {})
            current_incident_key = job_metadata.get("current_quarantine_incident_key")
            if (
                current_incident_key
                and current_incident_key != existing.quarantine_incident_key
            ):
                raise ProductUGCQueueConflict(
                    "Reconciliation idempotency key belongs to an earlier quarantine incident."
                )
            return QuarantineReconciliationResult(
                job=job,
                reconciliation=existing,
                created=False,
            )

        job = self.db.scalar(
            select(models.ProductUGCGenerationJob)
            .where(models.ProductUGCGenerationJob.id == job_id)
            .with_for_update()
        )
        if not job or job.organization_id != organization_id:
            raise ProductUGCQueueOwnershipError(
                "Generation job is outside this organization."
            )
        if (
            job.status != "quarantined"
            or not job.spend_guarded_at
            or job.provider_task_id
            or job.terminal_reason != "provider_submission_outcome_unknown"
        ):
            raise ProductUGCQueueConflict(
                "Only an unresolved ambiguous provider submission can be reconciled."
            )

        now = self.clock()
        job_metadata = dict(job.metadata_json or {})
        quarantine_incident_key = str(
            job_metadata.get("current_quarantine_incident_key") or uuid.uuid4().hex
        )[:64]
        reconciliation = models.ProductUGCQueueReconciliation(
            generation_job_id=job.id,
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            action=action,
            idempotency_key=key,
            provider_task_id=provider_task_id,
            quarantine_incident_key=quarantine_incident_key,
            evidence_reference=evidence,
            reason=reason_text,
            evidence_sha256=evidence_sha256,
            job_status_before=job.status,
            job_status_after="retry_wait",
            created_at=now,
        )
        self.db.add(reconciliation)
        try:
            self.db.flush()
            metadata = dict(job.metadata_json or {})
            reconciliation_ids = list(metadata.get("quarantine_reconciliation_ids") or [])
            if reconciliation.id not in reconciliation_ids:
                reconciliation_ids.append(reconciliation.id)
            metadata["quarantine_reconciliation_ids"] = reconciliation_ids[-20:]
            metadata["last_quarantine_reconciliation_action"] = action
            metadata.pop("current_quarantine_incident_key", None)
            metadata["last_resolved_quarantine_incident_key"] = quarantine_incident_key

            common_values = {
                "status": "retry_wait",
                "max_attempts": max(job.max_attempts, job.attempt_count + 1),
                "next_attempt_at": now,
                "lease_owner": None,
                "lease_token": None,
                "lease_expires_at": None,
                "terminal_reason": None,
                "quarantined_at": None,
                "completed_at": None,
                "metadata_json": metadata,
                "updated_at": now,
            }
            if action == RECONCILIATION_ATTACH_TASK:
                common_values.update(
                    {
                        "provider_task_id": provider_task_id,
                        "provider_status": "PENDING_RECONCILED",
                        "provider_submitted_at": (
                            job.provider_submitted_at or job.spend_guarded_at or now
                        ),
                        "last_error_code": "MANUALLY_RECONCILED_EXISTING_TASK",
                        "last_error_message": (
                            "Owner/admin attached a provider task verified in the provider console."
                        ),
                    }
                )
            else:
                common_values.update(
                    {
                        "requested_by_user_profile_id": actor_user_profile_id,
                        "provider_status": "RETRY_APPROVED_NO_SUBMISSION",
                        "provider_submitted_at": None,
                        "spend_guarded_at": None,
                        "last_error_code": "MANUALLY_CONFIRMED_NO_SUBMISSION",
                        "last_error_message": (
                            "Owner/admin confirmed that the provider console contains no submission."
                        ),
                    }
                )
            updated = self.db.execute(
                update(models.ProductUGCGenerationJob)
                .where(
                    models.ProductUGCGenerationJob.id == job.id,
                    models.ProductUGCGenerationJob.organization_id == organization_id,
                    models.ProductUGCGenerationJob.status == "quarantined",
                    models.ProductUGCGenerationJob.spend_guarded_at.is_not(None),
                    models.ProductUGCGenerationJob.provider_task_id.is_(None),
                    models.ProductUGCGenerationJob.terminal_reason
                    == "provider_submission_outcome_unknown",
                )
                .values(**common_values)
                .execution_options(synchronize_session=False)
            )
            if updated.rowcount != 1:
                raise ProductUGCQueueConflict(
                    "Generation reconciliation state changed concurrently."
                )

            draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
            if draft:
                warnings = [
                    item
                    for item in list(draft.warnings_json or [])
                    if not str(item).startswith("Automatic paid retry blocked:")
                ]
                warnings.append(
                    "Provider ambiguity was resolved by an owner/admin and recorded in the append-only audit."
                )
                draft.warnings_json = warnings[-50:]
                draft.publishing_readiness = "blocked"
                draft.human_review_status = "needs_human_review"
                if action == RECONCILIATION_ATTACH_TASK:
                    draft.provider_task_id = provider_task_id
                    draft.provider_status = "PENDING_RECONCILED"
                    draft.status = "provider_submitted"
                else:
                    draft.provider_task_id = None
                    draft.provider_status = "RETRY_APPROVED_NO_SUBMISSION"
                    draft.status = "provider_launching"

            # The SQL update intentionally bypasses ORM synchronization. Load
            # the new retry state before reopening the linked creator work and
            # mass-operation batch in this same transaction.
            self.db.flush()
            self.db.expire(job)
            job = self._require_job(job.id)
            project_mass_generation_queue_state(self.db, job, now=now)

            self.db.add(
                models.AuditLog(
                    user_profile_id=actor_user_profile_id,
                    organization_id=organization_id,
                    action="product_ugc_queue_quarantine_reconciled",
                    status="allowed",
                    reason="Ambiguous provider submission was manually reconciled.",
                    entity_type="product_ugc_generation_job",
                    entity_id=str(job.id),
                    metadata_json={
                        "reconciliation_id": reconciliation.id,
                        "resolution": action,
                    },
                )
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            winner = self.db.scalar(
                select(models.ProductUGCQueueReconciliation).where(
                    models.ProductUGCQueueReconciliation.idempotency_key == key
                )
            )
            if winner is not None:
                self._validate_existing_reconciliation(
                    winner,
                    job_id=job_id,
                    organization_id=organization_id,
                    actor_user_profile_id=actor_user_profile_id,
                    action=action,
                    provider_task_id=provider_task_id,
                    evidence_sha256=evidence_sha256,
                )
                winner_job = self._require_job(job_id)
                current_incident_key = dict(
                    winner_job.metadata_json or {}
                ).get("current_quarantine_incident_key")
                if (
                    current_incident_key
                    and current_incident_key != winner.quarantine_incident_key
                ):
                    raise ProductUGCQueueConflict(
                        "Reconciliation idempotency key belongs to an earlier quarantine incident."
                    )
                return QuarantineReconciliationResult(
                    job=winner_job,
                    reconciliation=winner,
                    created=False,
                )
            raise ProductUGCQueueConflict(
                "Provider task or reconciliation identity is already in use."
            ) from exc
        except Exception:
            self.db.rollback()
            raise

        self.db.expire_all()
        return QuarantineReconciliationResult(
            job=self._require_job(job_id),
            reconciliation=self.db.get(
                models.ProductUGCQueueReconciliation,
                reconciliation.id,
            ),
            created=True,
        )

    def reconcile_stale(
        self,
        *,
        stale_after_seconds: int = 300,
    ) -> ReconciliationResult:
        """Recover expired leases and quarantine ambiguous legacy draft states."""

        now = self.clock()
        cutoff = now - timedelta(seconds=max(0, stale_after_seconds))
        released = terminal = quarantined = recovered = 0

        # PostgreSQL compiles this as FOR UPDATE SKIP LOCKED. A leasing worker
        # or another reconciler therefore cannot change the row between the
        # stale predicate and the state transition committed below. SQLite
        # ignores the locking clause in isolated development/tests.
        stale_jobs = list(self.db.scalars(stale_lease_reconciliation_query(now)))
        for job in stale_jobs:
            draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
            if job.spend_guarded_at and not job.provider_task_id:
                self._quarantine_reconciled_job(job, draft, now)
                project_mass_generation_queue_state(self.db, job, now=now)
                quarantined += 1
            elif (job.provider_status or "").upper() in PROVIDER_FAILURE_STATUSES:
                self._terminal_reconciled_job(job, draft, now, "provider_terminal_failure")
                project_mass_generation_queue_state(self.db, job, now=now)
                terminal += 1
            elif job.attempt_count >= job.max_attempts:
                self._terminal_reconciled_job(job, draft, now, "retry_exhausted")
                project_mass_generation_queue_state(self.db, job, now=now)
                terminal += 1
            else:
                self._release_reconciled_job(job, draft, now)
                project_mass_generation_queue_state(self.db, job, now=now)
                released += 1

        exhausted_ready_jobs = list(
            self.db.scalars(
                select(models.ProductUGCGenerationJob).where(
                    models.ProductUGCGenerationJob.status.in_(READY_STATUSES),
                    models.ProductUGCGenerationJob.attempt_count
                    >= models.ProductUGCGenerationJob.max_attempts,
                )
            )
        )
        for job in exhausted_ready_jobs:
            draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
            self._terminal_reconciled_job(job, draft, now, "retry_exhausted")
            project_mass_generation_queue_state(self.db, job, now=now)
            terminal += 1

        job_exists = exists(
            select(models.ProductUGCGenerationJob.id).where(
                models.ProductUGCGenerationJob.draft_id == models.ProductUGCRecipeDraft.id
            )
        )
        orphan_drafts = list(
            self.db.scalars(
                select(models.ProductUGCRecipeDraft).where(
                    models.ProductUGCRecipeDraft.status.in_(RECOVERABLE_DRAFT_STATUSES),
                    models.ProductUGCRecipeDraft.updated_at <= cutoff,
                    ~job_exists,
                )
            )
        )
        for draft in orphan_drafts:
            product = self.db.get(models.Product, draft.product_id)
            if not product or product.organization_id is None:
                self._quarantine_orphan_draft(draft, now, "missing_organization_scope")
                quarantined += 1
                continue
            has_provider_task = bool(draft.provider_task_id)
            recovered_job = models.ProductUGCGenerationJob(
                draft_id=draft.id,
                organization_id=product.organization_id,
                requested_by_user_profile_id=None,
                idempotency_key=f"recovered-product-ugc-draft:{draft.id}",
                status="retry_wait" if has_provider_task else "quarantined",
                attempt_count=0,
                max_attempts=5,
                next_attempt_at=now,
                provider="runway_product_ugc_recipe",
                provider_task_id=draft.provider_task_id,
                provider_status=draft.provider_status or ("UNKNOWN" if has_provider_task else "UNKNOWN_REQUIRES_RECONCILIATION"),
                spend_guarded_at=draft.updated_at,
                provider_submitted_at=draft.updated_at if has_provider_task else None,
                terminal_reason=None if has_provider_task else "provider_submission_outcome_unknown",
                quarantined_at=None if has_provider_task else now,
                completed_at=None if has_provider_task else now,
                metadata_json={
                    "source": "restart_reconciliation",
                    "legacy_orphan": True,
                    **(
                        {"current_quarantine_incident_key": uuid.uuid4().hex}
                        if not has_provider_task
                        else {}
                    ),
                },
            )
            try:
                with self.db.begin_nested():
                    self.db.add(recovered_job)
                    self.db.flush()
            except IntegrityError:
                continue
            if has_provider_task:
                draft.status = "provider_submitted"
                recovered += 1
                released += 1
            else:
                self._quarantine_orphan_draft(draft, now, "provider_submission_outcome_unknown")
                quarantined += 1

        self.db.commit()
        return ReconciliationResult(
            released_for_retry=released,
            terminal_failures=terminal,
            quarantined=quarantined,
            recovered_drafts=recovered,
        )

    def summary(self, job: models.ProductUGCGenerationJob) -> QueueSummary:
        now = self.clock()
        return {
            "id": job.id,
            "draft_id": job.draft_id,
            "organization_id": job.organization_id,
            "status": job.status,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None,
            "lease_active": bool(job.lease_expires_at and job.lease_expires_at > now),
            "lease_expires_at": job.lease_expires_at.isoformat() if job.lease_expires_at else None,
            "heartbeat_at": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
            "provider_task_id": job.provider_task_id,
            "provider_status": job.provider_status,
            "will_retry": job.status == "retry_wait",
            "quarantined": job.status == "quarantined",
            "last_error_code": job.last_error_code,
            "last_error_message": job.last_error_message,
            "terminal_reason": job.terminal_reason,
            "quarantined_at": job.quarantined_at.isoformat() if job.quarantined_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "reconciliation_required": bool(
                job.status == "quarantined"
                and job.spend_guarded_at
                and not job.provider_task_id
            ),
        }

    def _touch_worker_heartbeat(
        self,
        *,
        worker_id: str,
        state: str,
        current_job_id: int | None = None,
        last_job_id: int | None = None,
        last_error_code: str | None = None,
        supervised: bool | None = None,
        now: datetime,
    ) -> models.ProductUGCQueueWorkerHeartbeat:
        raw_worker_id = (worker_id or "").strip()
        if not raw_worker_id:
            raise ProductUGCQueueLeaseError("worker_id is required for liveness tracking.")
        normalized_state = (state or "").strip().lower()
        if normalized_state not in WORKER_STATES:
            raise ProductUGCQueueConflict("Unknown worker heartbeat state.")
        worker_key = hashlib.sha256(raw_worker_id.encode("utf-8")).hexdigest()
        row = self.db.scalar(
            select(models.ProductUGCQueueWorkerHeartbeat).where(
                models.ProductUGCQueueWorkerHeartbeat.worker_key == worker_key
            )
        )
        if row is None:
            row = models.ProductUGCQueueWorkerHeartbeat(
                worker_key=worker_key,
                is_supervised=bool(supervised),
                state=normalized_state,
                current_job_id=current_job_id,
                last_job_id=last_job_id,
                processed_job_count=1 if last_job_id is not None else 0,
                last_error_code=self._safe_error_code(last_error_code),
                started_at=now,
                heartbeat_at=now,
            )
            self.db.add(row)
            return row
        if last_job_id is not None and row.last_job_id != last_job_id:
            row.processed_job_count = int(row.processed_job_count or 0) + 1
        if supervised is not None:
            row.is_supervised = bool(supervised)
        row.state = normalized_state
        row.current_job_id = current_job_id
        if last_job_id is not None:
            row.last_job_id = last_job_id
        row.last_error_code = self._safe_error_code(last_error_code)
        row.heartbeat_at = now
        return row

    def _validate_reconciliation_actor(
        self,
        organization_id: int,
        user_profile_id: int,
    ) -> None:
        organization = self.db.get(models.Organization, organization_id)
        user = self.db.get(models.UserProfile, user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
                models.Membership.role.in_(["owner", "admin"]),
            )
        )
        if not organization or organization.status != "active":
            raise ProductUGCQueueOwnershipError("Organization is missing or inactive.")
        if not user or not user.is_active or user.status != "active" or membership is None:
            raise ProductUGCQueueOwnershipError(
                "Quarantine reconciliation requires an active owner or admin."
            )

    @staticmethod
    def _validate_existing_reconciliation(
        existing: models.ProductUGCQueueReconciliation,
        *,
        job_id: int,
        organization_id: int,
        actor_user_profile_id: int,
        action: str,
        provider_task_id: str | None,
        evidence_sha256: str,
    ) -> None:
        if (
            existing.generation_job_id != job_id
            or existing.organization_id != organization_id
            or existing.actor_user_profile_id != actor_user_profile_id
            or existing.action != action
            or existing.provider_task_id != provider_task_id
            or existing.evidence_sha256 != evidence_sha256
        ):
            raise ProductUGCQueueConflict(
                "Reconciliation idempotency key belongs to another decision."
            )

    @staticmethod
    def _validate_provider_task_id(value: str) -> str:
        task_id = (value or "").strip()
        if (
            len(task_id) < 3
            or len(task_id) > 255
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]+", task_id)
        ):
            raise ProductUGCQueueConflict(
                "Provider task id must be copied exactly from the provider console."
            )
        return task_id

    @staticmethod
    def _validate_evidence_reference(value: str) -> str:
        evidence = (value or "").strip()
        if (
            len(evidence) < 5
            or len(evidence) > 200
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]+", evidence)
            or "?" in evidence
            or "#" in evidence
            or evidence.lower().startswith(("http://", "https://", "bearer", "sk-", "key_"))
        ):
            raise ProductUGCQueueConflict(
                "Use a non-secret provider audit/reference id without URL parameters."
            )
        return evidence

    @staticmethod
    def _validate_reconciliation_reason(value: str) -> str:
        reason = " ".join((value or "").strip().split())
        if len(reason) < 12 or len(reason) > 800:
            raise ProductUGCQueueConflict(
                "Reconciliation reason must contain 12 to 800 characters."
            )
        secret_pattern = re.compile(
            r"(?:bearer\s+\S+|api[_ -]?key\s*[:=]|secret\s*[:=]|token\s*[:=]|"
            r"https?://\S+[?#]|\b(?:sk|rk|pk)-[A-Za-z0-9_-]{8,}|\bkey_[A-Za-z0-9_-]{8,})",
            flags=re.IGNORECASE,
        )
        if secret_pattern.search(reason):
            raise ProductUGCQueueConflict(
                "Reconciliation reason must not contain credentials or signed URLs."
            )
        return reason

    @staticmethod
    def _reconciliation_evidence_sha256(
        *,
        action: str,
        provider_task_id: str | None,
        evidence_reference: str,
        reason: str,
    ) -> str:
        canonical = "\0".join(
            [action, provider_task_id or "", evidence_reference, reason]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_error_code(value: str | None) -> str | None:
        if not value:
            return None
        normalized = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(value).strip())
        return normalized[:120] or None

    def _validate_existing_scope(
        self,
        job: models.ProductUGCGenerationJob,
        *,
        draft_id: int,
        organization_id: int,
    ) -> None:
        if job.draft_id != draft_id or job.organization_id != organization_id:
            raise ProductUGCQueueConflict("Idempotency key belongs to another generation scope.")

    def _validate_actor(self, organization_id: int, user_profile_id: int) -> None:
        organization = self.db.get(models.Organization, organization_id)
        user = self.db.get(models.UserProfile, user_profile_id)
        if not organization or organization.status != "active":
            raise ProductUGCQueueOwnershipError("Organization is missing or inactive.")
        if not user or not user.is_active or user.status != "active":
            raise ProductUGCQueueOwnershipError("User is missing or inactive.")
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        if not membership:
            raise ProductUGCQueueOwnershipError("User is not an active member of this organization.")

    def _validate_initial_spend_authority(
        self,
        job: models.ProductUGCGenerationJob,
    ) -> None:
        """Recheck authority immediately before the first paid provider POST.

        Enqueue-time permission is not durable authority: an organization can be
        suspended or a membership can be revoked while a job waits in the queue.
        Existing provider tasks remain resumable, but a brand-new spend requires
        an active owner/admin at the moment the spend guard is acquired.
        """

        requester_id = job.requested_by_user_profile_id
        if requester_id is None:
            raise ProductUGCQueueOwnershipError(
                "Initial provider submission requires an attributable active owner or admin."
            )
        # Hold authority rows through the spend-guard commit. A concurrent
        # suspension/revocation must serialize either wholly before this check
        # (and reject) or wholly after the paid-submit reservation.
        organization = self.db.scalar(
            select(models.Organization)
            .where(models.Organization.id == job.organization_id)
            .with_for_update()
        )
        profile = self.db.scalar(
            select(models.UserProfile)
            .where(models.UserProfile.id == requester_id)
            .with_for_update()
        )
        membership = self.db.scalar(
            select(models.Membership)
            .where(
                models.Membership.organization_id == job.organization_id,
                models.Membership.user_profile_id == requester_id,
            )
            .with_for_update()
        )
        if not organization or organization.status != "active":
            raise ProductUGCQueueOwnershipError(
                "Organization is inactive; a new paid provider submission is forbidden."
            )
        if (
            not profile
            or not profile.is_active
            or profile.status != "active"
            or membership is None
            or membership.status != "active"
            or membership.role not in {"owner", "admin"}
        ):
            raise ProductUGCQueueOwnershipError(
                "Paid generation authority was revoked before provider submission."
            )

    def _require_job(self, job_id: int) -> models.ProductUGCGenerationJob:
        job = self.db.get(models.ProductUGCGenerationJob, job_id)
        if not job:
            raise ProductUGCQueueConflict(f"Product UGC generation job {job_id} was not found.")
        self.db.refresh(job)
        return job

    def _require_owned_lease(
        self,
        job_id: int,
        *,
        lease_token: str,
    ) -> models.ProductUGCGenerationJob:
        job = self._require_job(job_id)
        if (
            job.lease_token != lease_token
            or job.status not in LEASED_STATUSES
            or not job.lease_expires_at
            or job.lease_expires_at <= self.clock()
        ):
            raise ProductUGCQueueLeaseError("Generation lease belongs to another worker.")
        return job

    def _release_reconciled_job(self, job, draft, now: datetime) -> None:
        job.status = "retry_wait"
        job.next_attempt_at = now
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        job.heartbeat_at = now
        job.last_error_code = "STALE_LEASE_RECOVERED"
        job.last_error_message = "Worker lease expired; the same provider task will be resumed."
        if draft:
            draft.status = "provider_submitted" if job.provider_task_id else "provider_launching"
            draft.provider_status = job.provider_status or "RETRY_WAIT"

    def _terminal_reconciled_job(self, job, draft, now: datetime, reason: str) -> None:
        job.status = "failed_terminal"
        job.terminal_reason = reason
        if reason == "provider_terminal_failure":
            job.last_error_code = "PROVIDER_TERMINAL_FAILURE"
            job.last_error_message = "Provider task is terminal and cannot be restarted as another paid submit."
        else:
            job.last_error_code = "RETRY_EXHAUSTED"
            job.last_error_message = "Generation retry budget was exhausted."
        job.completed_at = now
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        if draft:
            draft.status = "provider_failed"
            draft.publishing_readiness = "blocked"

    def _quarantine_reconciled_job(self, job, draft, now: datetime) -> None:
        job.status = "quarantined"
        job.terminal_reason = "provider_submission_outcome_unknown"
        job.last_error_code = "AMBIGUOUS_PROVIDER_SUBMISSION"
        job.last_error_message = "Paid submit may have reached the provider, but no task id was persisted."
        job.quarantined_at = now
        job.completed_at = now
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        metadata = dict(job.metadata_json or {})
        metadata["current_quarantine_incident_key"] = (
            metadata.get("current_quarantine_incident_key") or uuid.uuid4().hex
        )
        job.metadata_json = metadata
        if draft:
            self._quarantine_orphan_draft(draft, now, "provider_submission_outcome_unknown")

    @staticmethod
    def _quarantine_orphan_draft(draft, now: datetime, reason: str) -> None:
        draft.status = "provider_submission_unknown"
        draft.provider_status = "UNKNOWN_REQUIRES_RECONCILIATION"
        draft.publishing_readiness = "blocked"
        draft.human_review_status = "needs_human_review"
        warnings = list(draft.warnings_json or [])
        warning = f"Automatic paid retry blocked: {reason}. Reconcile in the provider console."
        if warning not in warnings:
            warnings.append(warning)
        draft.warnings_json = warnings[-50:]
        draft.updated_at = now

    def _backoff_seconds(self, attempt_count: int) -> int:
        exponent = max(0, attempt_count - 1)
        return min(self.retry_max_seconds, self.retry_base_seconds * (2**exponent))

    @staticmethod
    def _validate_idempotency_key(value: str) -> str:
        key = (value or "").strip()
        if not key or len(key) > 200 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", key):
            raise ProductUGCQueueConflict("A stable, non-secret idempotency key is required.")
        return key

    @staticmethod
    def _safe_message(error: Exception | str) -> str:
        message = str(error).replace("\n", " ").strip()
        message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.IGNORECASE)
        message = re.sub(r"key_[A-Za-z0-9_-]+", "[redacted-key]", message)
        message = re.sub(
            r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{8,}",
            "[redacted-key]",
            message,
            flags=re.IGNORECASE,
        )
        message = re.sub(
            r"(?i)\b(api[_ -]?key|secret|token)\s*[:=]\s*\S+",
            r"\1=[redacted]",
            message,
        )
        message = re.sub(r"(https?://[^\s\"']+)\?[^\s\"']+", r"\1?[redacted]", message)
        return (message or "Unknown generation worker failure")[:800]
