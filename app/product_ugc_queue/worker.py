from __future__ import annotations

import os
import socket
import time
import uuid
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.product_telemetry import ProductTelemetryService
from app.product_ugc_queue.service import ProductUGCGenerationQueueService
from app.runway_recipes.provider import RunwayRecipeProvider
from app.runway_recipes.runner import ProductUGCRecipeRunner


class ProductUGCGenerationWorker:
    """Claims durable jobs and delegates provider work to the recipe runner."""

    def __init__(
        self,
        db: Session,
        *,
        worker_id: str | None = None,
        provider_factory: Callable[[], RunwayRecipeProvider] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        lease_seconds: int = 300,
        supervised: bool = False,
    ) -> None:
        self.db = db
        self.worker_id = worker_id or self.default_worker_id()
        self.provider_factory = provider_factory
        self.sleep = sleep
        self.lease_seconds = max(30, lease_seconds)
        self.supervised = bool(supervised)

    def process_job(self, job_id: int) -> models.ProductUGCGenerationJob:
        queue = ProductUGCGenerationQueueService(self.db)
        self._beat(state="polling")
        leased = queue.lease_job(
            job_id,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if leased is None:
            job = self.db.get(models.ProductUGCGenerationJob, job_id)
            if not job:
                raise ValueError(f"Product UGC generation job {job_id} was not found.")
            self._beat(state="idle")
            return job

        runner = ProductUGCRecipeRunner(
            self.db,
            provider_factory=self.provider_factory,
            sleep=self.sleep,
        )
        try:
            runner.run(
                leased.draft_id,
                real_run=True,
                generation_job_id=leased.id,
                lease_token=leased.lease_token,
                queue_lease_seconds=self.lease_seconds,
            )
        except Exception:
            # Runner persists retry/terminal/quarantine state. Background and
            # external workers can inspect the durable row without secrets.
            self.db.rollback()
        self.db.expire_all()
        job = self.db.get(models.ProductUGCGenerationJob, job_id)
        if not job:
            raise ValueError(f"Product UGC generation job {job_id} disappeared.")
        self._record_terminal_event(job)
        self._beat(
            state="ready",
            last_job_id=job.id,
            last_error_code=job.last_error_code,
        )
        return job

    def process_next(self, *, organization_id: int | None = None) -> models.ProductUGCGenerationJob | None:
        queue = ProductUGCGenerationQueueService(self.db)
        self._beat(state="polling")
        # Long-running workers must reclaim leases from peers that crash after
        # this process has already started; startup reconciliation alone is not
        # sufficient for a durable queue.
        queue.reconcile_stale()
        leased = queue.lease_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
            organization_id=organization_id,
        )
        if leased is None:
            self._beat(state="idle")
            return None
        # The row is already leased, so invoke the runner directly instead of
        # trying to claim the same job a second time.
        runner = ProductUGCRecipeRunner(
            self.db,
            provider_factory=self.provider_factory,
            sleep=self.sleep,
        )
        try:
            runner.run(
                leased.draft_id,
                real_run=True,
                generation_job_id=leased.id,
                lease_token=leased.lease_token,
                queue_lease_seconds=self.lease_seconds,
            )
        except Exception:
            self.db.rollback()
        self.db.expire_all()
        job = self.db.get(models.ProductUGCGenerationJob, leased.id)
        if job is not None:
            self._record_terminal_event(job)
            self._beat(
                state="ready",
                last_job_id=job.id,
                last_error_code=job.last_error_code,
            )
        return job

    def heartbeat(self, *, state: str = "idle") -> None:
        """Public liveness pulse for supervised loops and graceful shutdown."""

        self._beat(state=state)

    def _beat(
        self,
        *,
        state: str,
        current_job_id: int | None = None,
        last_job_id: int | None = None,
        last_error_code: str | None = None,
    ) -> None:
        try:
            ProductUGCGenerationQueueService(self.db).record_worker_heartbeat(
                worker_id=self.worker_id,
                state=state,
                current_job_id=current_job_id,
                last_job_id=last_job_id,
                last_error_code=last_error_code,
                supervised=self.supervised,
            )
        except Exception:
            # Liveness instrumentation cannot cause another paid submit or
            # prevent safe polling/downloading of an existing provider task.
            self.db.rollback()

    def _record_terminal_event(self, job: models.ProductUGCGenerationJob) -> None:
        """Emit the same durable milestone from web and standalone workers."""

        if job.status not in {"succeeded", "failed_terminal", "quarantined"}:
            return
        if not job.requested_by_user_profile_id:
            return
        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft is None:
            return
        role = self.db.scalar(
            select(models.Membership.role).where(
                models.Membership.organization_id == job.organization_id,
                models.Membership.user_profile_id == job.requested_by_user_profile_id,
                models.Membership.status == "active",
            )
        ) or "system_worker"
        event_name = "generation_succeeded" if job.status == "succeeded" else "generation_failed"
        durable_output_count = self.db.scalar(
            select(func.count(models.MediaArtifact.id)).where(
                models.MediaArtifact.organization_id == job.organization_id,
                models.MediaArtifact.product_ugc_recipe_draft_id == draft.id,
                models.MediaArtifact.kind.in_(("master_video", "provider_output")),
                models.MediaArtifact.status == "ready",
                models.MediaArtifact.deleted_at.is_(None),
            )
        ) or 0
        properties = (
            {
                "output_count": int(durable_output_count)
                or len(draft.local_output_paths_json or []),
                "queue_status": job.status,
            }
            if job.status == "succeeded"
            else {
                "provider_status": draft.provider_status or draft.status,
                "queue_status": job.status,
                "terminal_reason": job.terminal_reason,
            }
        )
        try:
            ProductTelemetryService(self.db).record_event(
                event_name=event_name,
                organization_id=job.organization_id,
                user_profile_id=job.requested_by_user_profile_id,
                role=str(role),
                idempotency_key=f"{event_name}:d{draft.id}",
                factory_run_id=f"product_ugc:{draft.id}",
                entity_type="product_ugc_recipe_draft",
                entity_id=str(draft.id),
                product_id=draft.product_id,
                sku=draft.sku,
                properties=properties,
            )
        except Exception:
            # Telemetry is observability, never a reason to retry paid provider work.
            self.db.rollback()
        finally:
            self.db.expire_all()

    @staticmethod
    def default_worker_id() -> str:
        return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
