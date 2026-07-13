from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.media_storage.backend import StorageBackend
from app.media_storage.product_ugc_sync import ProductUGCMediaArtifactSyncService
from app.media_storage.recipe_inputs import ProductUGCRecipeInputMaterializer
from app.product_ugc_queue import (
    ProductUGCGenerationQueueService,
    ProductUGCQueueConflict,
    ProductUGCQueueLeaseError,
    ProductUGCQueueOwnershipError,
    ProductUGCSpendValidationError,
)
from app.runway_recipes.errors import RunwayRecipeError
from app.runway_recipes.product_ugc_service import ProductUGCRecipeService
from app.runway_recipes.provider import RunwayRecipeProvider
from app.runway_recipes.types import ProductUGCRecipeRunOutput


SUCCESS_STATUSES = {"SUCCEEDED", "SUCCESS", "COMPLETED", "COMPLETE", "DONE"}
FAILURE_STATUSES = {"FAILED", "FAILURE", "CANCELLED", "CANCELED", "ERROR"}


class ProductUGCRecipeRunner:
    def __init__(
        self,
        db: Session,
        *,
        provider_factory: Callable[[], RunwayRecipeProvider] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        storage_backends: Mapping[str, StorageBackend] | None = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.provider_factory = provider_factory or RunwayRecipeProvider
        self.sleep = sleep
        self.storage_backends = (
            dict(storage_backends) if storage_backends is not None else None
        )

    def validate_preflight(self, draft_id: int, *, real_run: bool = False):
        self._preflight(real_run=real_run)
        service = ProductUGCRecipeService(
            self.db,
            storage_backends=self.storage_backends,
        )
        draft = service.get(draft_id)
        service.provider_request(draft)
        return service.output(draft)

    def run(
        self,
        draft_id: int,
        *,
        real_run: bool = False,
        preclaimed: bool = False,
        generation_job_id: int | None = None,
        lease_token: str | None = None,
        queue_lease_seconds: int = 300,
    ) -> ProductUGCRecipeRunOutput:
        if generation_job_id is not None:
            if not lease_token:
                raise ProductUGCQueueLeaseError("A lease token is required for durable generation work.")
            return self._run_queued(
                draft_id,
                generation_job_id=generation_job_id,
                lease_token=lease_token,
                queue_lease_seconds=queue_lease_seconds,
                real_run=real_run,
            )

        draft = None
        direct_submit_blocked = False
        errors: list[str] = []
        try:
            self._preflight(real_run=real_run)
            service = ProductUGCRecipeService(
                self.db,
                storage_backends=self.storage_backends,
            )
            draft = service.get(draft_id)
            durable_job = self.db.scalar(
                select(models.ProductUGCGenerationJob).where(
                    models.ProductUGCGenerationJob.draft_id == draft.id
                )
            )
            if durable_job:
                direct_submit_blocked = True
                raise RunwayRecipeError(
                    "This Product UGC draft is owned by the durable queue; direct provider submit is forbidden."
                )
            if draft.product and draft.product.organization_id is not None:
                direct_submit_blocked = True
                raise RunwayRecipeError(
                    "Organization-scoped paid generation must be enqueued through the durable queue."
                )
            if preclaimed:
                if draft.status != "provider_launching":
                    raise RunwayRecipeError("Product UGC draft was not reserved by the paid UI action.")
            else:
                claimed = self.db.execute(
                    update(type(draft))
                    .where(type(draft).id == draft.id, type(draft).status == "ready_for_paid_preflight")
                    .values(status="provider_launching", provider_status="SUBMITTING")
                )
                if claimed.rowcount != 1:
                    raise RunwayRecipeError("Product UGC draft is already running or is not paid-run ready.")
                self.db.commit()
                self.db.refresh(draft)
            request = service.provider_request(draft)
            provider = self.provider_factory()
            target_dir = self.settings.media_root / "provider" / "runway_product_ugc" / f"draft_{draft.id}"
            task = provider.create_product_ugc(request)
            draft.provider_task_id = task.provider_job_id
            draft.provider_status = task.status
            draft.status = "provider_submitted"
            self.db.commit()
            self._poll(provider, draft)
            paths = provider.download_outputs(task.provider_job_id, target_dir)
            if not paths or any(not path.exists() or path.stat().st_size <= 0 for path in paths):
                raise RunwayRecipeError("Runway Product UGC output was not downloaded or is empty.")
            draft.local_output_paths_json = [path.as_posix() for path in paths]
            draft.status = "generated_needs_human_review"
            draft.provider_status = "SUCCEEDED"
            draft.human_review_status = "needs_human_review"
            draft.publishing_readiness = "blocked"
        except Exception as exc:
            if direct_submit_blocked:
                raise
            errors.append(self._safe_error(exc))
            if draft is not None:
                draft.status = "provider_failed"
                draft.provider_status = draft.provider_status or "FAILED"
                draft.human_review_status = "needs_human_review"
                draft.publishing_readiness = "blocked"
                warnings = list(draft.warnings_json or [])
                warnings.append(f"Provider run failed: {errors[-1]}")
                draft.warnings_json = warnings
                draft.generation_report_path = self._write_report(draft, errors=errors)
                self.db.commit()
            raise
        draft.generation_report_path = self._write_report(draft, errors=errors)
        self.db.commit()
        self.db.refresh(draft)
        return self.output(draft)

    def _run_queued(
        self,
        draft_id: int,
        *,
        generation_job_id: int,
        lease_token: str,
        queue_lease_seconds: int,
        real_run: bool,
    ) -> ProductUGCRecipeRunOutput:
        """Run one leased durable job without ever repeating a paid submit."""

        queue = ProductUGCGenerationQueueService(self.db)
        job = queue.require_live_lease(generation_job_id, lease_token=lease_token)
        if job.draft_id != draft_id:
            raise ProductUGCQueueConflict("Generation lease does not belong to this Product UGC draft.")

        draft = None
        errors: list[str] = []
        try:
            service = ProductUGCRecipeService(
                self.db,
                storage_backends=self.storage_backends,
            )
            draft = service.get(draft_id)
            provider = self.provider_factory()
            target_dir = self.settings.media_root / "provider" / "runway_product_ugc" / f"draft_{draft.id}"

            # Once a provider task id exists, retries only resume that task.
            # No request payload is rebuilt and create_product_ugc is never called.
            if job.provider_task_id:
                draft.provider_task_id = job.provider_task_id
                draft.provider_status = job.provider_status or draft.provider_status or "PENDING"
                draft.status = "provider_submitted"
                self.db.commit()
            else:
                # Spend configuration gates only a new provider POST. Once a
                # provider task id is durable, disabling new spend must not
                # prevent polling/downloading an already-paid result.
                self._preflight(real_run=real_run)
                queue.validate_provider_submission_inputs(
                    job.id,
                    lease_token=lease_token,
                )
                materializer = ProductUGCRecipeInputMaterializer(
                    self.db,
                    backends=self.storage_backends,
                )
                with materializer.materialize(
                    draft,
                    organization_id=job.organization_id,
                    generation_job_id=job.id,
                ) as inputs:
                    if inputs.character_path is None and inputs.product_path is None:
                        request = service.provider_request(draft)
                    else:
                        request = service.provider_request(
                            draft,
                            materialized_character_path=inputs.character_path,
                            materialized_product_path=inputs.product_path,
                        )
                    queue.begin_provider_submission(
                        job.id,
                        lease_token=lease_token,
                        lease_seconds=queue_lease_seconds,
                        provider_payload=request,
                    )
                    # The spend guard above is committed before this network call.
                    # Any exception before the task id is durably recorded becomes
                    # quarantine, because the provider may still have accepted it.
                    task = provider.create_product_ugc(request)
                    job = queue.record_provider_submission(
                        job.id,
                        lease_token=lease_token,
                        provider_task_id=task.provider_job_id,
                        provider_status=task.status,
                        lease_seconds=queue_lease_seconds,
                    )
                draft = service.get(draft_id)

            self._poll(
                provider,
                draft,
                queue=queue,
                generation_job_id=job.id,
                lease_token=lease_token,
                lease_seconds=queue_lease_seconds,
            )
            queue.mark_downloading(
                job.id,
                lease_token=lease_token,
                lease_seconds=max(queue_lease_seconds, 300),
            )
            paths = provider.download_outputs(job.provider_task_id, target_dir)
            if not paths or any(not path.exists() or path.stat().st_size <= 0 for path in paths):
                raise RunwayRecipeError("Runway Product UGC output was not downloaded or is empty.")
            draft = service.get(draft_id)
            draft.local_output_paths_json = [path.as_posix() for path in paths]
            draft.status = "generated_needs_human_review"
            draft.provider_status = "SUCCEEDED"
            draft.human_review_status = "needs_human_review"
            draft.publishing_readiness = "blocked"
            draft.generation_report_path = self._write_report(draft, errors=errors)
            self.db.commit()
            # The queue is not terminally successful until its output and
            # report are durable in shared tenant storage.  A storage failure
            # therefore follows the ordinary leased retry path and cannot
            # leave a "succeeded" job whose web process cannot read the file.
            media_sync = ProductUGCMediaArtifactSyncService(
                self.db,
                backends=self.storage_backends,
            )
            artifacts = media_sync.sync_generation_job(job.id)
            # Stage the creator-task projection in the same transaction that
            # commits terminal queue success. A lost lease cannot expose a
            # review task for a job that did not become succeeded.
            media_sync.mark_creator_work_ready(
                job.id,
                artifacts,
                require_succeeded=False,
                commit=False,
            )
            queue.mark_succeeded(job.id, lease_token=lease_token)
        except Exception as exc:
            self.db.rollback()
            errors.append(self._safe_error(exc))
            draft = self.db.get(models.ProductUGCRecipeDraft, draft_id)
            provider_status = (draft.provider_status or "").upper() if draft else ""
            provider_terminal = provider_status in FAILURE_STATUSES
            metadata = dict(job.metadata_json or {})
            mass_preflight_blocked = bool(
                isinstance(exc, RunwayRecipeError)
                and draft is not None
                and draft.status == "blocked"
                and not job.provider_task_id
                and not job.spend_guarded_at
                and metadata.get("generation_template_snapshot_schema")
                == "generation_template_snapshot_v1"
            )
            retryable = not provider_terminal and not isinstance(
                exc,
                (
                    ProductUGCQueueOwnershipError,
                    ProductUGCSpendValidationError,
                ),
            ) and not mass_preflight_blocked
            if draft:
                provider_failure = (draft.creative_inputs_json or {}).get("provider_failure") or {}
                if provider_failure.get("retry_allowed") is False:
                    retryable = False
            try:
                queue.fail(
                    generation_job_id,
                    lease_token=lease_token,
                    error=exc,
                    error_code=exc.__class__.__name__.upper()[:120],
                    retryable=retryable,
                    provider_terminal=provider_terminal,
                )
                draft = self.db.get(models.ProductUGCRecipeDraft, draft_id)
                if draft:
                    draft.generation_report_path = self._write_report(draft, errors=errors)
                    self.db.commit()
            except (ProductUGCQueueLeaseError, ProductUGCQueueConflict):
                self.db.rollback()
            raise

        draft = self.db.get(models.ProductUGCRecipeDraft, draft_id)
        self.db.refresh(draft)
        return self.output(draft)

    def output(self, draft) -> ProductUGCRecipeRunOutput:
        return ProductUGCRecipeRunOutput(
            draft_id=draft.id,
            status=draft.status,
            provider_task_id=draft.provider_task_id,
            provider_status=draft.provider_status,
            local_output_paths=draft.local_output_paths_json or [],
            generation_report_path=draft.generation_report_path,
            human_review_status=draft.human_review_status,
            publishing_readiness=draft.publishing_readiness,
        )

    def _poll(
        self,
        provider: RunwayRecipeProvider,
        draft,
        *,
        queue: ProductUGCGenerationQueueService | None = None,
        generation_job_id: int | None = None,
        lease_token: str | None = None,
        lease_seconds: int = 300,
    ) -> None:
        deadline = time.monotonic() + self.settings.max_provider_poll_seconds
        while time.monotonic() < deadline:
            if queue and generation_job_id is not None and lease_token:
                queue.heartbeat(
                    generation_job_id,
                    lease_token=lease_token,
                    lease_seconds=lease_seconds,
                )
            status = provider.get_status(draft.provider_task_id)
            normalized = status.status.upper()
            if queue and generation_job_id is not None and lease_token:
                queue.record_provider_status(
                    generation_job_id,
                    lease_token=lease_token,
                    provider_status=normalized,
                    lease_seconds=lease_seconds,
                )
                self.db.refresh(draft)
            else:
                draft.provider_status = normalized
                self.db.commit()
            if normalized in SUCCESS_STATUSES:
                return
            if normalized in FAILURE_STATUSES:
                metadata = status.raw_response or {}
                failure_code = str(metadata.get("failure_code") or "PROVIDER_FAILED")
                failure = str(metadata.get("failure") or "Provider task failed.")
                non_retryable = failure_code.startswith("SAFETY.INPUT") or failure_code.startswith("INPUT_PREPROCESSING.SAFETY")
                creative_inputs = dict(draft.creative_inputs_json or {})
                creative_inputs["provider_failure"] = {
                    "code": failure_code,
                    "message": failure,
                    "retry_allowed": not non_retryable,
                }
                draft.creative_inputs_json = creative_inputs
                self.db.commit()
                retry_note = " Do not retry this input." if non_retryable else ""
                raise RunwayRecipeError(
                    f"Runway Product UGC task ended with status {normalized} ({failure_code}): {failure}.{retry_note}"
                )
            self.sleep(3)
        raise RunwayRecipeError("Runway Product UGC task timed out before completion.")

    def _preflight(self, *, real_run: bool) -> None:
        if not real_run:
            raise ProviderConfigurationError("Product UGC Recipe requires explicit --real-run.")
        if self.settings.generation_mode != "real":
            raise ProviderConfigurationError("Product UGC Recipe requires QVF_GENERATION_MODE=real.")
        if not self.settings.allow_real_spend:
            raise ProviderConfigurationError("Product UGC Recipe requires QVF_ALLOW_REAL_SPEND=true.")
        if not os.getenv("RUNWAYML_API_SECRET"):
            raise ProviderConfigurationError("RUNWAYML_API_SECRET is missing.")

    def _write_report(self, draft, *, errors: list[str]) -> str:
        report = {
            "run_type": "runway_product_ugc_recipe",
            "recipe_version": draft.recipe_version,
            "draft_id": draft.id,
            "product_id": draft.product_id,
            "sku": draft.sku,
            "variant_key": draft.variant_key,
            "provider": "runway",
            "provider_task_id": draft.provider_task_id,
            "provider_status": draft.provider_status,
            "provider_failure": (draft.creative_inputs_json or {}).get("provider_failure"),
            "product_asset_ids": draft.product_asset_ids_json or [],
            "primary_product_asset_id": draft.primary_product_asset_id,
            "payload_preview": draft.provider_payload_preview_json or {},
            "local_output_paths": draft.local_output_paths_json or [],
            "human_review_status": draft.human_review_status,
            "publishing_readiness": "blocked",
            "errors": errors,
            "created_at": datetime.now(UTC).isoformat(),
        }
        report_dir = self.settings.media_root / "generation_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"product_ugc_recipe_draft_{draft.id}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path.as_posix()

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc).replace("\n", " ").strip()
        message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.IGNORECASE)
        message = re.sub(r"key_[A-Za-z0-9_-]+", "[redacted-key]", message)
        message = re.sub(r"data:[^;\s]+;base64,[A-Za-z0-9+/=]+", "data:[redacted]", message)
        message = re.sub(r"(https?://[^\s\"']+)\?[^\s\"']+", r"\1?[redacted]", message)
        return (message or exc.__class__.__name__)[:800]
