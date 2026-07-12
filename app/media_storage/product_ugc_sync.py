from __future__ import annotations

from datetime import timedelta
import mimetypes
from pathlib import Path
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.media_storage.backend import StorageBackend
from app.media_storage.errors import MediaArtifactOwnershipError, MediaArtifactStateError
from app.media_storage.factory import get_storage_backends
from app.media_storage.service import MediaArtifactService


class ProductUGCMediaArtifactSyncService:
    """Persist completed worker outputs into the shared tenant library."""

    def __init__(
        self,
        db: Session,
        backends: Mapping[str, StorageBackend] | None = None,
    ) -> None:
        self.db = db
        self.backends = dict(backends or get_storage_backends())
        if len(self.backends) != 1:
            raise MediaArtifactStateError("Product UGC sync requires one active storage backend.")
        self.backend_name = next(iter(self.backends))
        self.artifacts = MediaArtifactService(db, self.backends)

    def sync_generation_job(self, generation_job_id: int) -> list[models.MediaArtifact]:
        job = self.db.get(models.ProductUGCGenerationJob, generation_job_id)
        if job is None:
            raise MediaArtifactStateError("Product UGC generation job was not found.")
        draft = self.db.get(models.ProductUGCRecipeDraft, job.draft_id)
        if draft is None or draft.product is None:
            raise MediaArtifactStateError("Product UGC draft was not found.")
        if draft.product.organization_id != job.organization_id:
            raise MediaArtifactOwnershipError("Product UGC media scope does not match the queue organization.")
        if job.requested_by_user_profile_id is None:
            raise MediaArtifactOwnershipError("Product UGC media has no attributable creator.")
        output_paths = [Path(value) for value in (draft.local_output_paths_json or [])]
        if not output_paths:
            raise MediaArtifactStateError("Successful Product UGC generation has no downloaded output.")

        scratch_paths = list(output_paths)
        now = models.utcnow()
        records: list[models.MediaArtifact] = []
        for index, source in enumerate(output_paths):
            records.append(
                self.artifacts.store_file_idempotent(
                    organization_id=job.organization_id,
                    created_by_user_profile_id=job.requested_by_user_profile_id,
                    backend_name=self.backend_name,
                    idempotency_key=f"product-ugc:d{draft.id}:output:{index}",
                    kind="master_video",
                    source=source,
                    mime_type=mimetypes.guess_type(source.name)[0] or "video/mp4",
                    original_filename=source.name,
                    product_id=draft.product_id,
                    product_ugc_recipe_draft_id=draft.id,
                    retention_class="master_365d",
                    retention_until=now + timedelta(days=365),
                    metadata={
                        "provider": job.provider,
                        "provider_task_id": job.provider_task_id,
                        "output_index": index,
                    },
                    trusted_worker=True,
                )
            )
        if draft.generation_report_path:
            report = Path(draft.generation_report_path)
            scratch_paths.append(report)
            records.append(
                self.artifacts.store_file_idempotent(
                    organization_id=job.organization_id,
                    created_by_user_profile_id=job.requested_by_user_profile_id,
                    backend_name=self.backend_name,
                    idempotency_key=f"product-ugc:d{draft.id}:generation-report",
                    kind="generation_report",
                    source=report,
                    mime_type="application/json",
                    original_filename=report.name,
                    product_id=draft.product_id,
                    product_ugc_recipe_draft_id=draft.id,
                    retention_class="audit_365d",
                    retention_until=now + timedelta(days=365),
                    metadata={"provider": job.provider, "provider_task_id": job.provider_task_id},
                    trusted_worker=True,
                )
            )

        job = self.db.get(models.ProductUGCGenerationJob, generation_job_id)
        metadata = dict(job.metadata_json or {})
        metadata["media_artifacts"] = [
            {"public_id": item.public_id, "kind": item.kind} for item in records
        ]
        job.metadata_json = metadata
        settings = get_settings()
        clear_cloud_scratch = (
            settings.runtime_profile == "production" and self.backend_name != "local"
        )
        if clear_cloud_scratch:
            # The worker filesystem is scratch space only. Once the tenant
            # artifacts are durable, never leave DB pointers to ephemeral files.
            draft.local_output_paths_json = []
            draft.generation_report_path = None
        self.db.commit()
        self.db.refresh(job)
        if clear_cloud_scratch:
            for source in scratch_paths:
                try:
                    source.unlink(missing_ok=True)
                except OSError:
                    # Container scratch is non-canonical and will disappear on
                    # recycle; artifact durability must not be rolled back.
                    pass
        return records

    def mark_creator_work_ready(
        self,
        generation_job_id: int,
        artifacts: list[models.MediaArtifact],
        *,
        require_succeeded: bool = True,
        commit: bool = True,
    ) -> None:
        """Attach durable output to creator work after queue success.

        The worker stages this projection without committing, then the queue
        commits it atomically with terminal success. Reconciliation callers may
        use the default post-success, self-committing mode.
        """

        job = self.db.get(models.ProductUGCGenerationJob, generation_job_id)
        if job is None or (
            require_succeeded and job.status != "succeeded"
        ) or (
            not require_succeeded and job.status not in {"downloading", "succeeded"}
        ):
            raise MediaArtifactStateError("Generation job must succeed before creator review.")
        primary = next(
            (
                item
                for item in artifacts
                if item.kind in {"master_video", "provider_output"}
                and item.organization_id == job.organization_id
                and item.status == "ready"
                and item.deleted_at is None
            ),
            None,
        )
        if primary is None:
            raise MediaArtifactStateError("Successful generation has no ready video artifact.")

        tasks = list(
            self.db.scalars(
                select(models.CreatorTask).where(
                    models.CreatorTask.organization_id == job.organization_id,
                    models.CreatorTask.product_ugc_recipe_draft_id == job.draft_id,
                    models.CreatorTask.task_type == "review_generated_video",
                )
            )
        )
        for task in tasks:
            task.media_artifact_id = primary.id
            task.result_json = {
                **dict(task.result_json or {}),
                "media_artifact_public_id": primary.public_id,
                "generation_job_id": job.id,
                "ready_for_review_at": models.utcnow().isoformat(),
            }

        metadata = dict(job.metadata_json or {})
        raw_batch_id = metadata.get("mass_operation_batch_id")
        try:
            batch_id = int(raw_batch_id) if raw_batch_id is not None else None
        except (TypeError, ValueError):
            batch_id = None
        if batch_id is not None:
            batch = self.db.get(models.MassOperationBatch, batch_id)
            if batch is not None and batch.organization_id == job.organization_id:
                results = [dict(item) for item in (batch.results_json or [])]
                for item in results:
                    if int(item.get("generation_job_id") or 0) == job.id:
                        item["status"] = "ready_for_review"
                        item["media_artifact_public_id"] = primary.public_id
                batch.results_json = results
                ready_count = sum(item.get("status") == "ready_for_review" for item in results)
                batch.status = "completed" if results and ready_count == len(results) else "running"
                if batch.status == "completed":
                    batch.completed_at = models.utcnow()

        if commit:
            self.db.commit()
