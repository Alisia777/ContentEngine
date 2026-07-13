from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


TERMINAL_FAILURE_STATUSES = frozenset({"failed_terminal", "quarantined"})
READY_FOR_CREATOR_STATUSES = frozenset({"ready_for_review", "done", "succeeded"})
PENDING_STATUSES = frozenset({"planned", "queued", "retry_wait"})
GENERATION_FAILURE_BLOCKER_CODES = frozenset(
    {
        "generation_terminal_failure",
        "generation_quarantine_requires_reconciliation",
    }
)
GENERATION_ERROR_SOURCE = "mass_generation_projection"


def project_mass_generation_queue_state(
    db: Session,
    job: models.ProductUGCGenerationJob,
    *,
    now: datetime,
) -> None:
    """Project retry or terminal queue state into creator work and its batch.

    Queue rows are the source of truth. This projection only follows explicit,
    organization-scoped lineage through a generation result or creator task;
    an untrusted/malformed batch id in job metadata can never cross tenants.
    """

    if job.status not in {"retry_wait", *TERMINAL_FAILURE_STATUSES}:
        return
    batch, tasks = _linked_batch_and_tasks(db, job)
    if batch is None:
        return

    if job.status == "retry_wait":
        for task in tasks:
            _make_task_retryable(task, job)
        _upsert_batch_result(batch, job, tasks, status="retry_wait")
        _remove_generation_error(batch, job.id)
    else:
        failure = _failure_details(job)
        for task in tasks:
            _block_task(task, job, failure)
        _upsert_batch_result(
            batch,
            job,
            tasks,
            status=job.status,
            failure=failure,
        )
        _replace_generation_error(batch, job, failure)

    recompute_mass_generation_batch(batch, now=now)


def project_mass_generation_ready(
    db: Session,
    job: models.ProductUGCGenerationJob,
    *,
    media_artifact_public_id: str,
    now: datetime,
) -> None:
    """Project one durable output into its mass-generation result."""

    batch, tasks = _linked_batch_and_tasks(db, job)
    if batch is None:
        return
    for task in tasks:
        _make_task_ready(task, job)
    _upsert_batch_result(
        batch,
        job,
        tasks,
        status="ready_for_review",
        media_artifact_public_id=media_artifact_public_id,
    )
    _remove_generation_error(batch, job.id)
    recompute_mass_generation_batch(batch, now=now)


def recompute_mass_generation_batch(
    batch: models.MassOperationBatch,
    *,
    now: datetime,
) -> None:
    """Derive batch counters and lifecycle from per-job result states."""

    results = [
        dict(item) for item in (batch.results_json or []) if isinstance(item, dict)
    ]
    statuses = [str(item.get("status") or "queued") for item in results]
    failed_job_ids = {
        _as_int(item.get("generation_job_id"))
        for item in results
        if str(item.get("status") or "") in TERMINAL_FAILURE_STATUSES
    }
    failed_job_ids.discard(None)
    batch.results_json = results
    batch.total_failed = len(failed_job_ids)

    settled = TERMINAL_FAILURE_STATUSES | READY_FOR_CREATOR_STATUSES
    if results and all(status in settled for status in statuses):
        batch.status = "completed_with_errors" if failed_job_ids else "completed"
        batch.completed_at = batch.completed_at or now
        return

    batch.completed_at = None
    if statuses and all(status in PENDING_STATUSES for status in statuses):
        batch.status = "queued"
    elif statuses:
        batch.status = "running"


def _linked_batch_and_tasks(
    db: Session,
    job: models.ProductUGCGenerationJob,
) -> tuple[models.MassOperationBatch | None, list[models.CreatorTask]]:
    metadata_batch_id = _as_int(
        _mapping(job.metadata_json).get("mass_operation_batch_id")
    )
    # Discover legacy task lineage without locking, then lock every candidate
    # batch in stable id order before any creator task. The spend guard uses the
    # same batch -> task order, preventing stale reconciliation from deadlocking
    # a worker at the paid-submit boundary.
    discovered_task_batch_ids = {
        _as_int(value)
        for value in db.scalars(
            select(models.CreatorTask.mass_operation_batch_id)
            .where(
                models.CreatorTask.organization_id == job.organization_id,
                models.CreatorTask.product_ugc_recipe_draft_id == job.draft_id,
                models.CreatorTask.task_type == "review_generated_video",
                models.CreatorTask.mass_operation_batch_id.is_not(None),
            )
            .distinct()
        )
    }
    discovered_task_batch_ids.discard(None)
    candidate_ids = set(discovered_task_batch_ids)
    if metadata_batch_id is not None:
        candidate_ids.add(metadata_batch_id)
    locked_batches: list[models.MassOperationBatch] = []
    for batch_id in sorted(candidate_ids):
        batch = db.scalar(
            select(models.MassOperationBatch)
            .where(
                models.MassOperationBatch.id == batch_id,
                models.MassOperationBatch.organization_id == job.organization_id,
                models.MassOperationBatch.operation_type == "generation",
                models.MassOperationBatch.dry_run.is_(False),
            )
            .with_for_update()
        )
        if batch is not None:
            locked_batches.append(batch)

    scoped_tasks = list(
        db.scalars(
            select(models.CreatorTask)
            .where(
                models.CreatorTask.organization_id == job.organization_id,
                models.CreatorTask.product_ugc_recipe_draft_id == job.draft_id,
                models.CreatorTask.task_type == "review_generated_video",
                models.CreatorTask.mass_operation_batch_id.is_not(None),
            )
            .with_for_update()
        )
    )
    for batch in locked_batches:
        batch_tasks = [
            task for task in scoped_tasks if task.mass_operation_batch_id == batch.id
        ]
        result_linked = any(
            _as_int(item.get("generation_job_id")) == job.id
            for item in (batch.results_json or [])
            if isinstance(item, dict)
        )
        if result_linked or batch_tasks:
            return batch, batch_tasks
    return None, []


def _upsert_batch_result(
    batch: models.MassOperationBatch,
    job: models.ProductUGCGenerationJob,
    tasks: list[models.CreatorTask],
    *,
    status: str,
    failure: dict[str, Any] | None = None,
    media_artifact_public_id: str | None = None,
) -> None:
    results = [
        dict(item) for item in (batch.results_json or []) if isinstance(item, dict)
    ]
    matched = [
        item
        for item in results
        if _as_int(item.get("generation_job_id")) == job.id
    ]
    if not matched:
        primary_task = tasks[0] if tasks else None
        matched = [
            {
                "draft_id": job.draft_id,
                "generation_job_id": job.id,
                "creator_task_id": primary_task.id if primary_task else None,
                "assignee_user_profile_id": (
                    primary_task.assignee_user_profile_id if primary_task else None
                ),
            }
        ]
        results.extend(matched)

    for item in matched:
        item["status"] = status
        item["attempt_count"] = int(job.attempt_count or 0)
        item["max_attempts"] = int(job.max_attempts or 0)
        if status == "retry_wait":
            prior_failure = _pop_failure_fields(item)
            if prior_failure:
                item["last_generation_failure"] = prior_failure
            item["next_attempt_at"] = (
                job.next_attempt_at.isoformat() if job.next_attempt_at else None
            )
        elif status in TERMINAL_FAILURE_STATUSES:
            item.pop("next_attempt_at", None)
            item["terminal_reason"] = job.terminal_reason
            item["error_code"] = job.last_error_code
            item["error_message"] = (failure or {}).get("message")
            item["failed_at"] = job.completed_at.isoformat() if job.completed_at else None
            item["action_required"] = str((failure or {}).get("action") or "")
        elif status == "ready_for_review":
            prior_failure = _pop_failure_fields(item)
            if prior_failure:
                item["last_generation_failure"] = prior_failure
            item.pop("next_attempt_at", None)
            item["media_artifact_public_id"] = media_artifact_public_id

    batch.results_json = results


def _block_task(
    task: models.CreatorTask,
    job: models.ProductUGCGenerationJob,
    failure: dict[str, Any],
) -> None:
    if task.status in {"done", "cancelled"}:
        return
    blocker = {
        "code": failure["blocker_code"],
        "generation_job_id": job.id,
        "queue_status": job.status,
        "reason": failure["reason"],
        "message": failure["message"],
        "action": failure["action"],
        "action_url": "/workbench?tab=video",
    }
    blockers = [
        item
        for item in list(task.blockers_json or [])
        if not _is_job_failure_blocker(item, job.id)
    ]
    blockers.append(blocker)
    task.blockers_json = blockers
    task.result_json = {
        **_mapping(task.result_json),
        "generation_job_id": job.id,
        "generation_queue_status": job.status,
        "generation_failure": {
            "reason": failure["reason"],
            "error_code": job.last_error_code,
            "message": failure["message"],
            "action": failure["action"],
            "failed_at": job.completed_at.isoformat() if job.completed_at else None,
        },
    }
    task.status = "blocked"
    task.completed_at = None


def _make_task_retryable(
    task: models.CreatorTask,
    job: models.ProductUGCGenerationJob,
) -> None:
    if task.status in {"done", "cancelled"}:
        return
    result = _mapping(task.result_json)
    prior_failure = result.pop("generation_failure", None)
    if prior_failure:
        result["last_generation_failure"] = prior_failure
    result["generation_job_id"] = job.id
    result["generation_queue_status"] = "retry_wait"
    result["next_attempt_at"] = (
        job.next_attempt_at.isoformat() if job.next_attempt_at else None
    )
    task.result_json = result
    task.blockers_json = [
        item
        for item in list(task.blockers_json or [])
        if not _is_job_failure_blocker(item, job.id)
    ]
    if task.status == "blocked" and not task.blockers_json:
        task.status = "todo"


def _failure_details(job: models.ProductUGCGenerationJob) -> dict[str, str]:
    message = (
        "Генерация остановлена без готового видео. "
        "Техническая причина сохранена в журнале очереди для owner/admin."
    )
    if job.status == "quarantined":
        return {
            "blocker_code": "generation_quarantine_requires_reconciliation",
            "reason": str(job.terminal_reason or "provider_submission_outcome_unknown"),
            "message": message,
            "action": (
                "Owner/admin должен сверить отправку с кабинетом провайдера в очереди "
                "генерации. Автоматический повтор запрещён до завершения сверки."
            ),
        }
    if job.terminal_reason == "provider_terminal_failure":
        action = (
            "Owner/admin должен проверить отказ провайдера, исправить рецепт или исходники "
            "и запустить новую подтверждённую генерацию."
        )
    else:
        action = (
            "Owner/admin должен проверить журнал ошибки, исправить входные данные или "
            "инфраструктуру и запустить безопасный ручной повтор, когда он разрешён."
        )
    return {
        "blocker_code": "generation_terminal_failure",
        "reason": str(job.terminal_reason or "terminal_generation_failure"),
        "message": message,
        "action": action,
    }


def _make_task_ready(
    task: models.CreatorTask,
    job: models.ProductUGCGenerationJob,
) -> None:
    if task.status in {"done", "cancelled"}:
        return
    result = _mapping(task.result_json)
    prior_failure = result.pop("generation_failure", None)
    if prior_failure:
        result["last_generation_failure"] = prior_failure
    result["generation_job_id"] = job.id
    result["generation_queue_status"] = "ready_for_review"
    result.pop("next_attempt_at", None)
    task.result_json = result
    task.blockers_json = [
        item
        for item in list(task.blockers_json or [])
        if not _is_job_failure_blocker(item, job.id)
    ]
    if task.status == "blocked" and not task.blockers_json:
        task.status = "todo"


def _replace_generation_error(
    batch: models.MassOperationBatch,
    job: models.ProductUGCGenerationJob,
    failure: dict[str, Any],
) -> None:
    errors = [
        dict(item)
        for item in (batch.errors_json or [])
        if isinstance(item, dict)
        if not (
            item.get("source") == GENERATION_ERROR_SOURCE
            and _as_int(item.get("generation_job_id")) == job.id
        )
    ]
    errors.append(
        {
            "source": GENERATION_ERROR_SOURCE,
            "generation_job_id": job.id,
            "draft_id": job.draft_id,
            "status": job.status,
            "terminal_reason": job.terminal_reason,
            "error_code": job.last_error_code,
            "error": failure["message"],
            "action_required": failure["action"],
        }
    )
    batch.errors_json = errors


def _remove_generation_error(batch: models.MassOperationBatch, job_id: int) -> None:
    batch.errors_json = [
        dict(item)
        for item in (batch.errors_json or [])
        if isinstance(item, dict)
        if not (
            item.get("source") == GENERATION_ERROR_SOURCE
            and _as_int(item.get("generation_job_id")) == job_id
        )
    ]


def _pop_failure_fields(item: dict[str, Any]) -> dict[str, Any]:
    failure: dict[str, Any] = {}
    for key in (
        "terminal_reason",
        "error_code",
        "error_message",
        "failed_at",
        "action_required",
    ):
        value = item.pop(key, None)
        if value is not None:
            failure[key] = value
    return failure


def _is_job_failure_blocker(value: Any, job_id: int) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("code") in GENERATION_FAILURE_BLOCKER_CODES
        and _as_int(value.get("generation_job_id")) == job_id
    )


def _as_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
