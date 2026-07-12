from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from typing import Iterable
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.owned_targets import normalize_platform, safe_public_url
from app.novice_learning_path import NoviceLearningPathService
from app.publishing.scheduler import PublishingScheduler


FINAL_EXAM_CODE = "portal_operator_exam"
GENERATION_BATCH_LIMIT = 50
GENERATION_ASSIGNEE_LIMIT = 50
GENERATION_CREDIT_LIMIT = 500
PLACEMENT_BATCH_LIMIT = 250
PLACEMENT_DESTINATION_LIMIT = 50
PLACEMENT_INTERVAL_MAX_MINUTES = 10_080
PLACEMENT_MAX_HORIZON_DAYS = 180
PLACEMENT_PLATFORM_HOSTS = {
    "instagram": frozenset({"instagram.com", "www.instagram.com"}),
    "tiktok": frozenset({"tiktok.com", "www.tiktok.com", "m.tiktok.com"}),
    "youtube": frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}),
    "vk": frozenset({"vk.com", "www.vk.com", "m.vk.com"}),
    "vk_clips": frozenset({"vk.com", "www.vk.com", "m.vk.com"}),
    "rutube": frozenset({"rutube.ru", "www.rutube.ru"}),
    "facebook": frozenset({"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"}),
    "telegram": frozenset({"t.me", "telegram.me"}),
    "pinterest": frozenset({"pinterest.com", "www.pinterest.com", "pin.it"}),
    "x": frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"}),
    "twitter": frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"}),
}


class CreatorOperationsError(ValueError):
    pass


class CreatorOperationsService:
    """Organization-scoped bulk work for creator teams.

    Bulk generation clones a fully validated Product UGC draft. Each clone gets
    its own durable queue row, provider-spend idempotency key, and creator task.
    Bulk placement delegates to the existing warm-up/limit-aware scheduler.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def generation_batch(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        template_draft_id: int,
        assignee_user_profile_ids: list[int],
        quantity: int,
        name: str,
        idempotency_key: str,
        dry_run: bool,
        confirm_real_spend: bool,
        confirmed_total_credits: int | None = None,
    ) -> models.MassOperationBatch:
        actor = self._membership(organization_id, actor_user_profile_id)
        if actor.role not in {"owner", "admin", "producer"}:
            raise CreatorOperationsError("generation_batch_role_required")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError) as exc:
            raise CreatorOperationsError("invalid_quantity") from exc
        if quantity < 1 or quantity > GENERATION_BATCH_LIMIT:
            raise CreatorOperationsError(f"quantity_must_be_1_to_{GENERATION_BATCH_LIMIT}")
        template_draft_id = self._bounded_positive_ids(
            [template_draft_id],
            "template_draft",
            limit=1,
        )[0]
        assignee_ids = self._bounded_positive_ids(
            assignee_user_profile_ids,
            "assignee",
            limit=GENERATION_ASSIGNEE_LIMIT,
        )
        if not assignee_ids:
            raise CreatorOperationsError("at_least_one_assignee_required")
        normalized_name = self._name(name)
        key = self._idempotency_key(idempotency_key)
        confirmed_credits = self._nonnegative_int(
            confirmed_total_credits,
            "confirmed_total_credits",
        )
        fingerprint = self._request_fingerprint(
            "generation",
            {
                "actor_user_profile_id": actor_user_profile_id,
                "template_draft_id": template_draft_id,
                "assignee_user_profile_ids": assignee_ids,
                "quantity": quantity,
                "name": normalized_name,
                "dry_run": bool(dry_run),
                "confirm_real_spend": bool(confirm_real_spend),
                "confirmed_total_credits": confirmed_credits,
            },
        )
        existing = self._existing_batch(organization_id, key)
        if existing is not None:
            return self._validate_existing_batch(existing, "generation", fingerprint)

        template_query = select(models.ProductUGCRecipeDraft).where(
            models.ProductUGCRecipeDraft.id == template_draft_id
        )
        if not dry_run:
            template_query = template_query.with_for_update()
        template = self.db.scalar(template_query)
        if template is None or template.product.organization_id != organization_id:
            raise CreatorOperationsError("template_draft_not_found")
        if template.status != "ready_for_paid_preflight" or template.blockers_json:
            raise CreatorOperationsError("template_draft_not_ready")
        assignees = self._qualified_assignees(organization_id, assignee_ids)
        estimated_credit_per_item = max(int(template.estimated_credits or 0), 0)
        estimated_credits = estimated_credit_per_item * quantity
        if not dry_run:
            if actor.role not in {"owner", "admin"}:
                raise CreatorOperationsError("real_spend_owner_admin_required")
            if not self.settings.allow_real_spend or not confirm_real_spend:
                raise CreatorOperationsError("real_spend_gate_required")
            if estimated_credit_per_item < 1:
                raise CreatorOperationsError("template_credit_estimate_required")
            if estimated_credits > GENERATION_CREDIT_LIMIT:
                raise CreatorOperationsError(
                    f"generation_credit_limit_exceeded:{estimated_credits}>{GENERATION_CREDIT_LIMIT}"
                )
            if confirmed_credits != estimated_credits:
                raise CreatorOperationsError(
                    f"confirmed_total_credits_must_equal_{estimated_credits}"
                )
        planned = [
            {
                "sequence": index,
                "assignee_user_profile_id": assignees[(index - 1) % len(assignees)],
                "template_draft_id": template.id,
                "estimated_credits": estimated_credit_per_item,
                "status": "planned",
            }
            for index in range(1, quantity + 1)
        ]
        batch = models.MassOperationBatch(
            organization_id=organization_id,
            created_by_user_profile_id=actor_user_profile_id,
            operation_type="generation",
            name=normalized_name,
            idempotency_key=key,
            status="validated" if dry_run else "queued",
            dry_run=bool(dry_run),
            total_requested=quantity,
            total_accepted=quantity if dry_run else 0,
            total_failed=0,
            parameters_json={
                "template_draft_id": template.id,
                "assignee_user_profile_ids": assignees,
                "quantity": quantity,
                "estimated_credits": estimated_credits,
                "confirmed_total_credits": confirmed_credits,
                "credit_limit": GENERATION_CREDIT_LIMIT,
                "real_spend_requested": not dry_run,
                "request_fingerprint": fingerprint,
            },
            results_json=planned if dry_run else [],
            errors_json=[],
            started_at=None if dry_run else models.utcnow(),
            completed_at=models.utcnow() if dry_run else None,
        )
        try:
            self.db.add(batch)
            self.db.flush()
            if dry_run:
                self.db.commit()
                self.db.refresh(batch)
                return batch

            results: list[dict[str, object]] = []
            for sequence in range(1, quantity + 1):
                assignee_id = assignees[(sequence - 1) % len(assignees)]
                draft = self._clone_draft(
                    template,
                    batch=batch,
                    sequence=sequence,
                    actor_user_profile_id=actor_user_profile_id,
                    assignee_user_profile_id=assignee_id,
                )
                job = self._generation_job(
                    batch=batch,
                    draft=draft,
                    actor_user_profile_id=actor_user_profile_id,
                    sequence=sequence,
                )
                task = self._generation_task(
                    batch=batch,
                    draft=draft,
                    assignee_user_profile_id=assignee_id,
                    actor_user_profile_id=actor_user_profile_id,
                    sequence=sequence,
                )
                results.append(
                    {
                        "sequence": sequence,
                        "draft_id": draft.id,
                        "generation_job_id": job.id,
                        "creator_task_id": task.id,
                        "assignee_user_profile_id": assignee_id,
                        "status": "queued",
                    }
                )
            batch.results_json = results
            batch.errors_json = []
            batch.total_accepted = len(results)
            batch.total_failed = 0
            # The bulk request is accepted atomically; provider work remains in
            # the durable queue and must not be represented as already complete.
            batch.status = "queued"
            self.db.commit()
            self.db.refresh(batch)
            return batch
        except IntegrityError as exc:
            self.db.rollback()
            winner = self._existing_batch(organization_id, key)
            if winner is not None:
                return self._validate_existing_batch(winner, "generation", fingerprint)
            raise CreatorOperationsError("generation_batch_transaction_conflict") from exc
        except CreatorOperationsError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise CreatorOperationsError("generation_batch_transaction_failed") from exc

    def placement_batch(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        package_ids: list[int],
        destination_ids: list[int],
        start_at: datetime,
        interval_minutes: int,
        name: str,
        idempotency_key: str,
        dry_run: bool,
        assignee_user_profile_ids: list[int] | None = None,
    ) -> models.MassOperationBatch:
        actor = self._membership(organization_id, actor_user_profile_id)
        if actor.role not in {"owner", "admin", "operator"}:
            raise CreatorOperationsError("placement_batch_role_required")
        package_ids = self._bounded_positive_ids(
            package_ids,
            "package",
            limit=PLACEMENT_BATCH_LIMIT,
        )
        destination_ids = self._bounded_positive_ids(
            destination_ids,
            "destination",
            limit=PLACEMENT_DESTINATION_LIMIT,
        )
        if not package_ids:
            raise CreatorOperationsError(f"package_count_must_be_1_to_{PLACEMENT_BATCH_LIMIT}")
        if not destination_ids:
            raise CreatorOperationsError("at_least_one_destination_required")
        assignee_ids = self._bounded_positive_ids(
            [actor_user_profile_id]
            if assignee_user_profile_ids is None
            else assignee_user_profile_ids,
            "assignee",
            limit=GENERATION_ASSIGNEE_LIMIT,
        )
        if not assignee_ids:
            raise CreatorOperationsError("at_least_one_assignee_required")
        assignees = self._qualified_assignees(organization_id, assignee_ids)
        try:
            interval_minutes = int(interval_minutes)
        except (TypeError, ValueError) as exc:
            raise CreatorOperationsError("invalid_interval_minutes") from exc
        if not 1 <= interval_minutes <= PLACEMENT_INTERVAL_MAX_MINUTES:
            raise CreatorOperationsError(
                f"interval_minutes_must_be_1_to_{PLACEMENT_INTERVAL_MAX_MINUTES}"
            )
        start_at = self._normalize_placement_start(start_at)
        normalized_name = self._name(name)
        key = self._idempotency_key(idempotency_key)
        fingerprint = self._request_fingerprint(
            "placement",
            {
                "actor_user_profile_id": actor_user_profile_id,
                "package_ids": package_ids,
                "destination_ids": destination_ids,
                "assignee_user_profile_ids": assignees,
                "start_at": start_at.isoformat(),
                "interval_minutes": interval_minutes,
                "name": normalized_name,
                "dry_run": bool(dry_run),
            },
        )
        existing = self._existing_batch(organization_id, key)
        if existing is not None:
            return self._validate_existing_batch(existing, "placement", fingerprint)
        end_at = start_at + timedelta(minutes=(len(package_ids) - 1) * interval_minutes)
        self._validate_placement_window(start_at, end_at)

        packages = self._require_owned_packages(
            organization_id,
            package_ids,
            lock=not dry_run,
        )
        destinations = self._require_owned_destinations(
            organization_id,
            destination_ids,
            lock=not dry_run,
        )

        batch = models.MassOperationBatch(
            organization_id=organization_id,
            created_by_user_profile_id=actor_user_profile_id,
            operation_type="placement",
            name=normalized_name,
            idempotency_key=key,
            status="running",
            dry_run=bool(dry_run),
            total_requested=len(package_ids),
            parameters_json={
                "package_ids": package_ids,
                "destination_ids": destination_ids,
                "assignee_user_profile_ids": assignees,
                "start_at": start_at.isoformat(),
                "interval_minutes": interval_minutes,
                "request_fingerprint": fingerprint,
            },
            started_at=models.utcnow(),
        )
        try:
            self.db.add(batch)
            self.db.flush()
            scheduler = PublishingScheduler(self.db)
            planned: list[dict[str, object]] = []
            errors: list[dict[str, object]] = []
            reserved_daily: dict[tuple[int, object], int] = {}
            reserved_weekly: dict[tuple[int, object], int] = {}
            existing_scheduled_packages = set(
                self.db.scalars(
                    select(models.PublishingTask.publishing_package_id).where(
                        models.PublishingTask.publishing_package_id.in_(package_ids),
                        models.PublishingTask.status.in_(PublishingScheduler.COUNTED_STATUSES),
                    )
                ).all()
            )
            for index, package_id in enumerate(package_ids):
                destination_id = destination_ids[index % len(destination_ids)]
                assignee_id = assignees[index % len(assignees)]
                package = packages[package_id]
                destination = destinations[destination_id]
                scheduled_at = start_at + timedelta(minutes=index * interval_minutes)
                blockers: list[str] = []
                if package_id in existing_scheduled_packages:
                    blockers.append("publishing_package_already_scheduled")
                with self.db.no_autoflush:
                    validation = scheduler.validate(package, destination, scheduled_at)
                blockers.extend(self._media_aware_blockers(package, organization_id, validation["blockers"]))
                day_key = (destination.id, scheduled_at.date())
                week_start = scheduled_at.date() - timedelta(days=scheduled_at.weekday())
                week_key = (destination.id, week_start)
                if validation["daily_count"] + reserved_daily.get(day_key, 0) >= destination.daily_limit:
                    blockers.append("daily_publishing_limit_reached_in_batch")
                if validation["weekly_count"] + reserved_weekly.get(week_key, 0) >= destination.weekly_limit:
                    blockers.append("weekly_publishing_limit_reached_in_batch")
                blockers = list(dict.fromkeys(blockers))
                if blockers:
                    errors.append(
                        {
                            "package_id": package.id,
                            "destination_id": destination.id,
                            "scheduled_at": scheduled_at.isoformat(),
                            "error": ";".join(blockers),
                        }
                    )
                    continue
                reserved_daily[day_key] = reserved_daily.get(day_key, 0) + 1
                reserved_weekly[week_key] = reserved_weekly.get(week_key, 0) + 1
                planned.append(
                    {
                        "package_id": package.id,
                        "destination_id": destination.id,
                        "assignee_user_profile_id": assignee_id,
                        "scheduled_at": scheduled_at.isoformat(),
                        "schedule_validation": {
                            **validation,
                            "allowed": True,
                            "blockers": [],
                        },
                    }
                )

            batch.results_json = planned
            batch.errors_json = errors
            if dry_run:
                batch.total_accepted = len(planned)
                batch.total_failed = len(errors)
                batch.status = "validated" if not errors else "completed_with_errors"
                batch.completed_at = models.utcnow()
                self.db.commit()
                self.db.refresh(batch)
                return batch
            if errors:
                # Scheduling is deliberately all-or-nothing. A dry-run must be
                # corrected before any real placement task is persisted.
                batch.total_accepted = 0
                batch.total_failed = len(package_ids)
                batch.status = "blocked"
                batch.completed_at = models.utcnow()
                batch.errors_json = [
                    *errors,
                    {"error": "atomic_placement_batch_cancelled"},
                ]
                self.db.commit()
                self.db.refresh(batch)
                return batch

            created_results: list[dict[str, object]] = []
            for sequence, plan in enumerate(planned, start=1):
                destination = destinations[int(plan["destination_id"])]
                package = packages[int(plan["package_id"])]
                task = models.PublishingTask(
                    publishing_package_id=int(plan["package_id"]),
                    destination_id=destination.id,
                    platform=destination.platform,
                    status="scheduled",
                    scheduled_at=datetime.fromisoformat(str(plan["scheduled_at"])),
                    operator_name=f"user:{actor_user_profile_id}",
                    raw_response_json={
                        "schedule_validation": plan["schedule_validation"],
                        "bulk_schedule": True,
                        "mass_operation_batch_id": batch.id,
                    },
                )
                self.db.add(task)
                self.db.flush()
                creator_task = self._placement_task(
                    batch=batch,
                    package=package,
                    destination=destination,
                    publishing_task=task,
                    assignee_user_profile_id=int(plan["assignee_user_profile_id"]),
                    actor_user_profile_id=actor_user_profile_id,
                    sequence=sequence,
                )
                created_results.append(
                    {
                        **plan,
                        "publishing_task_id": task.id,
                        "creator_task_id": creator_task.id,
                        "media_artifact_id": package.media_artifact_id,
                        "status": "todo",
                    }
                )
            batch.results_json = created_results
            batch.errors_json = []
            batch.total_accepted = len(created_results)
            batch.total_failed = 0
            # The batch is accepted, but people still have to publish each
            # assigned video and submit its canonical public URL.
            batch.status = "queued"
            batch.completed_at = None
            self.db.commit()
            self.db.refresh(batch)
            return batch
        except IntegrityError as exc:
            self.db.rollback()
            winner = self._existing_batch(organization_id, key)
            if winner is not None:
                return self._validate_existing_batch(winner, "placement", fingerprint)
            raise CreatorOperationsError("placement_batch_transaction_conflict") from exc
        except CreatorOperationsError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise CreatorOperationsError("placement_batch_transaction_failed") from exc

    def task_inbox(
        self,
        *,
        organization_id: int,
        viewer_user_profile_id: int,
        status: str | None = None,
        limit: int = 100,
    ) -> list[models.CreatorTask]:
        membership = self._membership(organization_id, viewer_user_profile_id)
        query = select(models.CreatorTask).where(models.CreatorTask.organization_id == organization_id)
        if membership.role not in {"owner", "admin"}:
            query = query.where(models.CreatorTask.assignee_user_profile_id == viewer_user_profile_id)
        if status:
            query = query.where(models.CreatorTask.status == status)
        return list(
            self.db.scalars(
                query.order_by(
                    models.CreatorTask.priority.desc(),
                    models.CreatorTask.due_at,
                    models.CreatorTask.id,
                ).limit(min(max(int(limit), 1), 250))
            )
        )

    def payout_ledger(
        self,
        *,
        organization_id: int,
        viewer_user_profile_id: int,
        limit: int = 100,
    ) -> list[models.CreatorPayout]:
        membership = self._membership(organization_id, viewer_user_profile_id)
        query = select(models.CreatorPayout).where(models.CreatorPayout.organization_id == organization_id)
        if membership.role not in {"owner", "admin"}:
            query = query.where(models.CreatorPayout.user_profile_id == viewer_user_profile_id)
        return list(
            self.db.scalars(
                query.order_by(models.CreatorPayout.created_at.desc(), models.CreatorPayout.id.desc()).limit(
                    min(max(int(limit), 1), 250)
                )
            )
        )

    def review_generated_task(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        task_id: int,
        decision: str,
        notes: str | None = None,
    ) -> models.CreatorTask:
        membership = self._membership(organization_id, actor_user_profile_id)
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise CreatorOperationsError("invalid_review_decision")
        cleaned_notes = " ".join(str(notes or "").strip().split())[:2000]
        if normalized_decision == "reject" and len(cleaned_notes) < 10:
            raise CreatorOperationsError("rejection_reason_too_short")

        task = self.db.scalar(
            select(models.CreatorTask)
            .where(
                models.CreatorTask.id == int(task_id),
                models.CreatorTask.organization_id == organization_id,
            )
            .with_for_update()
        )
        if task is None or task.task_type != "review_generated_video":
            raise CreatorOperationsError("review_task_not_found")
        if (
            membership.role not in {"owner", "admin"}
            and task.assignee_user_profile_id != actor_user_profile_id
        ):
            raise CreatorOperationsError("review_task_assignee_required")

        previous = dict(task.result_json or {}).get("review_decision")
        if task.status in {"done", "cancelled"}:
            if previous == normalized_decision:
                return task
            raise CreatorOperationsError("review_task_already_finalized")
        artifact = self.db.get(models.MediaArtifact, task.media_artifact_id)
        if (
            artifact is None
            or artifact.organization_id != organization_id
            or artifact.status != "ready"
            or artifact.deleted_at is not None
            or artifact.kind not in {"master_video", "provider_output"}
            or artifact.size_bytes <= 0
        ):
            raise CreatorOperationsError("review_video_not_ready")
        draft = self.db.get(models.ProductUGCRecipeDraft, task.product_ugc_recipe_draft_id)
        if draft is None or draft.product.organization_id != organization_id:
            raise CreatorOperationsError("review_draft_not_found")

        now = models.utcnow()
        task.submitted_at = now
        task.result_json = {
            **dict(task.result_json or {}),
            "review_decision": normalized_decision,
            "review_notes": cleaned_notes,
            "reviewed_by_user_profile_id": actor_user_profile_id,
            "reviewed_at": now.isoformat(),
            "media_artifact_public_id": artifact.public_id,
        }
        draft.human_review_notes = cleaned_notes or None
        if normalized_decision == "approve":
            task.status = "done"
            task.completed_at = now
            task.blockers_json = []
            draft.human_review_status = "approved"
            draft.publishing_readiness = "ready_for_publishing_package"
        else:
            task.status = "blocked"
            task.completed_at = None
            task.blockers_json = [
                {
                    "code": "human_review_changes_requested",
                    "reason": cleaned_notes,
                }
            ]
            draft.human_review_status = "changes_requested"
            draft.publishing_readiness = "blocked"
        self.db.commit()
        self.db.refresh(task)
        return task

    def complete_manual_placement(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        task_id: int,
        final_url: str,
    ) -> models.CreatorTask:
        membership = self._membership(organization_id, actor_user_profile_id)
        task_lookup = self.db.scalar(
            select(models.CreatorTask)
            .where(
                models.CreatorTask.id == int(task_id),
                models.CreatorTask.organization_id == organization_id,
            )
        )
        if task_lookup is None or task_lookup.task_type != "manual_placement":
            raise CreatorOperationsError("placement_task_not_found")
        batch = self.db.scalar(
            select(models.MassOperationBatch)
            .where(
                models.MassOperationBatch.id == task_lookup.mass_operation_batch_id,
                models.MassOperationBatch.organization_id == organization_id,
            )
            .with_for_update()
        )
        if batch is None or batch.operation_type != "placement" or batch.dry_run:
            raise CreatorOperationsError("placement_task_lineage_invalid")
        # Serialize completion per batch, then lock creator tasks in one stable
        # order so two assignees cannot deadlock while finishing the last items.
        batch_tasks = list(
            self.db.scalars(
                select(models.CreatorTask)
                .where(
                    models.CreatorTask.organization_id == organization_id,
                    models.CreatorTask.mass_operation_batch_id == batch.id,
                    models.CreatorTask.task_type == "manual_placement",
                )
                .order_by(models.CreatorTask.id)
                .with_for_update()
            )
        )
        task = next((item for item in batch_tasks if item.id == task_lookup.id), None)
        if task is None or len(batch_tasks) != batch.total_accepted or not batch_tasks:
            raise CreatorOperationsError("placement_batch_task_count_mismatch")
        if (
            membership.role not in {"owner", "admin"}
            and task.assignee_user_profile_id != actor_user_profile_id
        ):
            raise CreatorOperationsError("placement_task_assignee_required")

        publishing_task = self.db.scalar(
            select(models.PublishingTask)
            .where(models.PublishingTask.id == task.publishing_task_id)
            .with_for_update()
        )
        if (
            publishing_task is None
        ):
            raise CreatorOperationsError("placement_task_lineage_invalid")
        package = self.db.get(models.PublishingPackage, publishing_task.publishing_package_id)
        destination = self.db.get(models.PublishingDestination, publishing_task.destination_id)
        product = self.db.get(models.Product, package.product_id) if package is not None else None
        if (
            package is None
            or destination is None
            or product is None
            or package.organization_id != organization_id
            or product.organization_id != organization_id
            or destination.organization_id != organization_id
            or task.product_id != package.product_id
            or task.media_artifact_id != package.media_artifact_id
            or normalize_platform(publishing_task.platform) != normalize_platform(destination.platform)
            or normalize_platform(package.target_platform) != normalize_platform(destination.platform)
        ):
            raise CreatorOperationsError("placement_task_lineage_invalid")

        canonical_url = self._canonical_placement_url(final_url, destination)
        task_result = dict(task.result_json or {})
        existing_task_url = str(task_result.get("final_url") or "").strip()
        existing_publishing_url = str(publishing_task.final_url or "").strip()
        if task.status == "done":
            if (
                publishing_task.status != "published_manual"
                or not existing_task_url
                or not existing_publishing_url
                or self._canonical_placement_url(existing_task_url, destination) != canonical_url
                or self._canonical_placement_url(existing_publishing_url, destination) != canonical_url
            ):
                raise CreatorOperationsError("placement_final_url_mismatch")
            return task
        if task.status not in {"todo", "in_progress", "submitted", "review"}:
            raise CreatorOperationsError("placement_task_not_completable")
        if existing_task_url and self._canonical_placement_url(existing_task_url, destination) != canonical_url:
            raise CreatorOperationsError("placement_final_url_mismatch")
        if existing_publishing_url:
            if self._canonical_placement_url(existing_publishing_url, destination) != canonical_url:
                raise CreatorOperationsError("placement_final_url_mismatch")
            if publishing_task.status != "published_manual":
                raise CreatorOperationsError("placement_publishing_task_already_finalized")
        elif publishing_task.status not in {"scheduled", "manual_upload_required"}:
            raise CreatorOperationsError("placement_publishing_task_not_completable")

        results = [dict(item) for item in list(batch.results_json or []) if isinstance(item, dict)]
        result_indexes = [
            index
            for index, item in enumerate(results)
            if item.get("creator_task_id") == task.id
            and item.get("publishing_task_id") == publishing_task.id
        ]
        if len(results) != len(list(batch.results_json or [])) or len(result_indexes) != 1:
            raise CreatorOperationsError("placement_batch_result_lineage_invalid")

        now = models.utcnow()
        actor_label = f"user:{actor_user_profile_id}"
        publishing_task.status = "published_manual"
        publishing_task.final_url = canonical_url
        publishing_task.operator_name = actor_label
        publishing_task.error_message = None
        publishing_task.raw_response_json = {
            **dict(publishing_task.raw_response_json or {}),
            "published_manual": {
                "operator_name": actor_label,
                "actor_user_profile_id": actor_user_profile_id,
                "final_url": canonical_url,
                "completed_at": now.isoformat(),
            },
        }
        task.status = "done"
        task.submitted_at = now
        task.completed_at = now
        task.blockers_json = []
        task.result_json = {
            **task_result,
            "final_url": canonical_url,
            "publishing_task_id": publishing_task.id,
            "completed_by_user_profile_id": actor_user_profile_id,
            "completed_at": now.isoformat(),
        }
        result_index = result_indexes[0]
        results[result_index] = {
            **results[result_index],
            "status": "done",
            "final_url": canonical_url,
            "completed_at": now.isoformat(),
        }
        batch.results_json = results
        all_done = all(item.status == "done" for item in batch_tasks)
        batch.status = "completed" if all_done else "running"
        batch.completed_at = now if all_done else None
        self.db.commit()
        self.db.refresh(task)
        return task

    def _clone_draft(
        self,
        template: models.ProductUGCRecipeDraft,
        *,
        batch: models.MassOperationBatch,
        sequence: int,
        actor_user_profile_id: int,
        assignee_user_profile_id: int,
    ) -> models.ProductUGCRecipeDraft:
        suffix = f"batch-{batch.id}-{sequence}"
        variant_base = str(template.variant_key or template.sku or "variant")[: max(1, 159 - len(suffix))]
        creative_inputs = deepcopy(template.creative_inputs_json or {})
        creative_inputs["mass_batch"] = {
            "batch_id": batch.id,
            "sequence": sequence,
            "assignee_user_profile_id": assignee_user_profile_id,
        }
        draft = models.ProductUGCRecipeDraft(
            product_id=template.product_id,
            created_by_user_profile_id=actor_user_profile_id,
            assigned_to_user_profile_id=assignee_user_profile_id,
            sku=template.sku,
            variant_key=f"{variant_base}-{suffix}"[:160],
            status="ready_for_paid_preflight",
            recipe_version=template.recipe_version,
            platform=template.platform,
            language=template.language,
            character_image_path=template.character_image_path,
            character_media_artifact_id=template.character_media_artifact_id,
            character_image_filename=template.character_image_filename,
            likeness_consent=template.likeness_consent,
            exact_variant_confirmed=template.exact_variant_confirmed,
            product_asset_ids_json=deepcopy(template.product_asset_ids_json or []),
            primary_product_asset_id=template.primary_product_asset_id,
            product_info=template.product_info,
            user_concept=template.user_concept,
            creative_inputs_json=creative_inputs,
            duration_seconds=template.duration_seconds,
            ratio=template.ratio,
            audio_enabled=template.audio_enabled,
            estimated_credits=template.estimated_credits,
            provider_payload_preview_json=deepcopy(template.provider_payload_preview_json or {}),
            blockers_json=[],
            warnings_json=deepcopy(template.warnings_json or []),
            provider_task_id=None,
            provider_status=None,
            local_output_paths_json=[],
            generation_report_path=None,
            human_review_status="not_generated",
            publishing_readiness="blocked",
            human_review_notes=None,
        )
        self.db.add(draft)
        self.db.flush()
        return draft

    def _generation_job(
        self,
        *,
        batch: models.MassOperationBatch,
        draft: models.ProductUGCRecipeDraft,
        actor_user_profile_id: int,
        sequence: int,
    ) -> models.ProductUGCGenerationJob:
        job = models.ProductUGCGenerationJob(
            draft_id=draft.id,
            organization_id=batch.organization_id,
            requested_by_user_profile_id=actor_user_profile_id,
            idempotency_key=f"mass-generation:{batch.id}:{sequence}",
            status="queued",
            attempt_count=0,
            max_attempts=5,
            next_attempt_at=models.utcnow(),
            provider="runway_product_ugc_recipe",
            provider_status="QUEUED",
            metadata_json={
                "source": "mass_operation",
                "mass_operation_batch_id": batch.id,
                "sequence": sequence,
                "spend_policy": "at_most_once",
            },
        )
        draft.status = "provider_launching"
        draft.provider_status = "QUEUED"
        self.db.add(job)
        self.db.flush()
        return job

    def _generation_task(
        self,
        *,
        batch: models.MassOperationBatch,
        draft: models.ProductUGCRecipeDraft,
        assignee_user_profile_id: int,
        actor_user_profile_id: int,
        sequence: int,
    ) -> models.CreatorTask:
        task = models.CreatorTask(
            organization_id=batch.organization_id,
            assignee_user_profile_id=assignee_user_profile_id,
            created_by_user_profile_id=actor_user_profile_id,
            mass_operation_batch_id=batch.id,
            product_id=draft.product_id,
            product_ugc_recipe_draft_id=draft.id,
            task_type="review_generated_video",
            title=f"Проверить ролик {draft.sku} · {sequence}/{batch.total_requested}",
            instructions="После генерации проверьте товар, упаковку, обещания и правила площадки.",
            status="todo",
            priority=3,
            checklist_json=[
                "Открыть master-видео",
                "Сверить SKU и упаковку",
                "Проверить правила выбранной площадки",
                "Одобрить или вернуть с конкретной причиной",
            ],
            idempotency_key=f"mass-generation:{batch.id}:task:{sequence}",
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _placement_task(
        self,
        *,
        batch: models.MassOperationBatch,
        package: models.PublishingPackage,
        destination: models.PublishingDestination,
        publishing_task: models.PublishingTask,
        assignee_user_profile_id: int,
        actor_user_profile_id: int,
        sequence: int,
    ) -> models.CreatorTask:
        destination_label = " · ".join(
            part
            for part in (destination.platform, destination.name, destination.handle)
            if part
        )
        task = models.CreatorTask(
            organization_id=batch.organization_id,
            assignee_user_profile_id=assignee_user_profile_id,
            created_by_user_profile_id=actor_user_profile_id,
            mass_operation_batch_id=batch.id,
            product_id=package.product_id,
            media_artifact_id=package.media_artifact_id,
            publishing_task_id=publishing_task.id,
            task_type="manual_placement",
            title=f"Разместить видео · {destination.platform} · {sequence}/{batch.total_requested}",
            instructions=(
                f"Опубликуйте одобренное видео в направлении {destination_label}. "
                "Используйте подготовленные текст и ссылку, затем вставьте публичный HTTPS URL публикации."
            ),
            status="todo",
            priority=3,
            due_at=publishing_task.scheduled_at,
            checklist_json=[
                "Открыть одобренное видео",
                f"Опубликовать в {destination_label}",
                "Проверить публичную публикацию",
                "Сохранить финальный URL публикации",
            ],
            result_json={
                "destination_id": destination.id,
                "destination_platform": destination.platform,
                "destination_name": destination.name,
                "destination_handle": destination.handle,
                "destination_url": destination.url,
                "publishing_task_id": publishing_task.id,
                "media_artifact_id": package.media_artifact_id,
            },
            blockers_json=[],
            idempotency_key=f"mass-placement:{batch.id}:task:{sequence}",
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _qualified_assignees(self, organization_id: int, values: Iterable[int]) -> list[int]:
        result: list[int] = []
        for user_profile_id in values:
            membership = self._membership(organization_id, user_profile_id)
            if membership.role not in {"owner", "admin", "producer", "reviewer", "operator", "trainee"}:
                raise CreatorOperationsError(f"assignee_role_not_supported:{user_profile_id}")
            if not self.final_exam_passed(user_profile_id):
                raise CreatorOperationsError(f"assignee_final_exam_required:{user_profile_id}")
            result.append(user_profile_id)
        return result

    def final_exam_passed(self, user_profile_id: int) -> bool:
        return FINAL_EXAM_CODE in NoviceLearningPathService(self.db).verified_certification_codes(
            user_profile_id=int(user_profile_id)
        )

    def _membership(self, organization_id: int, user_profile_id: int) -> models.Membership:
        organization = self.db.get(models.Organization, organization_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        profile = self.db.get(models.UserProfile, user_profile_id)
        if (
            organization is None
            or organization.status != "active"
            or membership is None
            or profile is None
            or not profile.is_active
            or profile.status != "active"
        ):
            raise CreatorOperationsError("active_membership_required")
        return membership

    def _require_owned_packages(
        self,
        organization_id: int,
        package_ids: list[int],
        *,
        lock: bool,
    ) -> dict[int, models.PublishingPackage]:
        query = (
            select(models.PublishingPackage)
            .join(models.Product)
            .where(
                models.PublishingPackage.id.in_(package_ids),
                models.PublishingPackage.organization_id == organization_id,
                models.Product.organization_id == organization_id,
            )
            .order_by(models.PublishingPackage.id)
        )
        if lock:
            query = query.with_for_update()
        rows = self.db.scalars(query).all()
        if len(rows) != len(package_ids):
            raise CreatorOperationsError("publishing_package_not_found")
        return {row.id: row for row in rows}

    def _require_owned_destinations(
        self,
        organization_id: int,
        destination_ids: list[int],
        *,
        lock: bool,
    ) -> dict[int, models.PublishingDestination]:
        query = (
            select(models.PublishingDestination)
            .where(
                models.PublishingDestination.id.in_(destination_ids),
                models.PublishingDestination.organization_id == organization_id,
            )
            .order_by(models.PublishingDestination.id)
        )
        if lock:
            query = query.with_for_update()
        rows = self.db.scalars(query).all()
        if len(rows) != len(destination_ids):
            raise CreatorOperationsError("publishing_destination_not_found")
        return {row.id: row for row in rows}

    def _media_aware_blockers(
        self,
        package: models.PublishingPackage,
        organization_id: int,
        blockers: Iterable[str],
    ) -> list[str]:
        result = list(blockers)
        missing_local_video = "Video file must exist and be non-empty."
        if missing_local_video not in result or not package.media_artifact_id:
            return result
        artifact = self.db.get(models.MediaArtifact, package.media_artifact_id)
        if (
            artifact is not None
            and artifact.organization_id == organization_id
            and artifact.status == "ready"
            and artifact.deleted_at is None
            and artifact.kind in {"provider_output", "master_video"}
            and artifact.size_bytes > 0
        ):
            result.remove(missing_local_video)
        return result

    def _existing_batch(self, organization_id: int, idempotency_key: str) -> models.MassOperationBatch | None:
        return self.db.scalar(
            select(models.MassOperationBatch).where(
                models.MassOperationBatch.organization_id == organization_id,
                models.MassOperationBatch.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _validate_existing_batch(
        existing: models.MassOperationBatch,
        operation_type: str,
        fingerprint: str,
    ) -> models.MassOperationBatch:
        stored = dict(existing.parameters_json or {}).get("request_fingerprint")
        if existing.operation_type != operation_type or stored != fingerprint:
            raise CreatorOperationsError("idempotency_key_reused_with_different_payload")
        return existing

    @staticmethod
    def _positive_ids(values: Iterable[int], label: str) -> list[int]:
        result = []
        for raw in values:
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise CreatorOperationsError(f"invalid_{label}_id") from exc
            if value <= 0:
                raise CreatorOperationsError(f"invalid_{label}_id")
            if value not in result:
                result.append(value)
        return result

    @classmethod
    def _bounded_positive_ids(
        cls,
        values: Iterable[int],
        label: str,
        *,
        limit: int,
    ) -> list[int]:
        raw_values = list(values)
        if len(raw_values) > limit:
            raise CreatorOperationsError(f"{label}_count_exceeds_{limit}")
        result = cls._positive_ids(raw_values, label)
        if len(result) > limit:
            raise CreatorOperationsError(f"{label}_count_exceeds_{limit}")
        return result

    @staticmethod
    def _idempotency_key(value: str) -> str:
        normalized = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]{7,179}", normalized):
            raise CreatorOperationsError("invalid_idempotency_key")
        return normalized

    @staticmethod
    def _name(value: str) -> str:
        normalized = " ".join(str(value or "").split())
        if not 3 <= len(normalized) <= 180:
            raise CreatorOperationsError("invalid_batch_name")
        return normalized

    @staticmethod
    def _nonnegative_int(value: int | None, label: str) -> int:
        if value is None:
            return 0
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise CreatorOperationsError(f"invalid_{label}") from exc
        if normalized < 0:
            raise CreatorOperationsError(f"invalid_{label}")
        return normalized

    @staticmethod
    def _request_fingerprint(operation_type: str, payload: dict[str, object]) -> str:
        canonical = json.dumps(
            {"operation_type": operation_type, **payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_placement_start(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise CreatorOperationsError("invalid_start_at")
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @staticmethod
    def _validate_placement_window(start_at: datetime, end_at: datetime) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        horizon = now + timedelta(days=PLACEMENT_MAX_HORIZON_DAYS)
        if start_at < now - timedelta(minutes=5):
            raise CreatorOperationsError("start_at_is_in_the_past")
        if start_at > horizon:
            raise CreatorOperationsError(
                f"start_at_exceeds_{PLACEMENT_MAX_HORIZON_DAYS}_day_horizon"
            )
        if end_at > horizon:
            raise CreatorOperationsError(
                f"schedule_exceeds_{PLACEMENT_MAX_HORIZON_DAYS}_day_horizon"
            )

    @staticmethod
    def _canonical_placement_url(
        value: str,
        destination: models.PublishingDestination,
    ) -> str:
        try:
            canonical = safe_public_url(
                value,
                error_code="placement_final_url_invalid",
            )
        except DestinationConnectorDataError as exc:
            raise CreatorOperationsError("placement_final_url_invalid") from exc
        if len(canonical) > 500:
            raise CreatorOperationsError("placement_final_url_invalid")
        platform = normalize_platform(destination.platform)
        allowed_hosts = set(PLACEMENT_PLATFORM_HOSTS.get(platform, ()))
        if not allowed_hosts and destination.url:
            try:
                destination_url = safe_public_url(
                    destination.url,
                    error_code="placement_destination_url_invalid",
                )
            except DestinationConnectorDataError as exc:
                raise CreatorOperationsError("placement_destination_url_invalid") from exc
            destination_host = (urlsplit(destination_url).hostname or "").lower().rstrip(".")
            if destination_host:
                allowed_hosts.add(destination_host)
        if not allowed_hosts:
            raise CreatorOperationsError("placement_destination_domain_required")
        host = (urlsplit(canonical).hostname or "").lower().rstrip(".")
        if host not in allowed_hosts:
            raise CreatorOperationsError("placement_final_url_host_mismatch")
        return canonical

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = " ".join(str(exc).split())[:300]
        lowered = message.casefold()
        for marker in ("token", "secret", "password", "authorization", "apikey", "api_key"):
            if marker in lowered:
                return "operation_failed_redacted"
        return message or exc.__class__.__name__
