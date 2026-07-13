from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, exists, func, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app import models
from app.config import get_settings
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.owned_targets import normalize_platform, safe_public_url
from app.novice_learning_path import NoviceLearningPathService
from app.product_ugc_queue.generation_snapshot_guard import (
    GENERATION_TEMPLATE_SNAPSHOT_SCHEMA,
    canonical_json_sha256,
)
from app.publishing.manual_upload import ManualUploadProvider
from app.publishing.publication_identity import (
    PublicationIdentityError,
    canonical_publication_url,
    claim_publication_identity,
)
from app.publishing.scheduler import PublishingScheduler


FINAL_EXAM_CODE = "portal_operator_exam"
GENERATION_BATCH_LIMIT = 50
GENERATION_ASSIGNEE_LIMIT = 50
PLACEMENT_BATCH_LIMIT = 250
PLACEMENT_DESTINATION_LIMIT = 50
PLACEMENT_INTERVAL_MAX_MINUTES = 10_080
PLACEMENT_MAX_HORIZON_DAYS = 180
PLACEMENT_PAYOUT_MAX_MINOR = 100_000_000
MANUAL_METRIC_COUNT_MAX = 10_000_000_000
MANUAL_METRIC_REVENUE_MAX_MINOR = 100_000_000_000


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
        _expected_template_snapshot: dict[str, object] | None = None,
        _expected_template_snapshot_sha256: str | None = None,
        _source_dry_run_batch_id: int | None = None,
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
        fingerprint_payload: dict[str, object] = {
            "actor_user_profile_id": actor_user_profile_id,
            "template_draft_id": template_draft_id,
            "assignee_user_profile_ids": assignee_ids,
            "quantity": quantity,
            "name": normalized_name,
            "dry_run": bool(dry_run),
            "confirm_real_spend": bool(confirm_real_spend),
            "confirmed_total_credits": confirmed_credits,
        }
        if _expected_template_snapshot_sha256 is not None:
            fingerprint_payload["template_snapshot_sha256"] = (
                _expected_template_snapshot_sha256
            )
        if _source_dry_run_batch_id is not None:
            fingerprint_payload["source_dry_run_batch_id"] = int(
                _source_dry_run_batch_id
            )
        fingerprint = self._request_fingerprint("generation", fingerprint_payload)
        existing = self._existing_batch(organization_id, key)
        if existing is not None:
            return self._validate_existing_batch(existing, "generation", fingerprint)

        template_query = (
            select(models.ProductUGCRecipeDraft)
            .where(models.ProductUGCRecipeDraft.id == template_draft_id)
            .with_for_update()
        )
        template = self.db.scalar(template_query)
        if template is None:
            raise CreatorOperationsError("template_draft_not_found")
        product = self.db.scalar(
            select(models.Product)
            .where(models.Product.id == template.product_id)
            .with_for_update()
        )
        if product is None or product.organization_id != organization_id:
            raise CreatorOperationsError("template_draft_not_found")
        template_snapshot = self._generation_template_snapshot(
            template,
            product=product,
            organization_id=organization_id,
            lock_related=True,
        )
        template_snapshot_sha256 = self._generation_template_snapshot_hash(
            template_snapshot
        )
        if (
            _expected_template_snapshot is not None
            or _expected_template_snapshot_sha256 is not None
        ):
            if (
                not self._valid_generation_template_snapshot(
                    _expected_template_snapshot,
                    _expected_template_snapshot_sha256,
                )
            ):
                raise CreatorOperationsError(
                    "dry_run_template_snapshot_integrity_invalid:create_new_dry_run"
                )
            if template_snapshot_sha256 != _expected_template_snapshot_sha256:
                changed_fields = self._generation_template_snapshot_changes(
                    _expected_template_snapshot,
                    template_snapshot,
                )
                raise CreatorOperationsError(
                    "generation_template_changed_since_dry_run:"
                    f"{','.join(changed_fields)}:create_new_dry_run"
                )
        if template.status != "ready_for_paid_preflight" or template.blockers_json:
            raise CreatorOperationsError("template_draft_not_ready")
        assignees = self._qualified_assignees(organization_id, assignee_ids)
        estimated_credit_per_item = max(int(template.estimated_credits or 0), 0)
        estimated_credits = estimated_credit_per_item * quantity
        credit_limit = int(self.settings.mass_generation_credit_limit)
        if not dry_run:
            if actor.role not in {"owner", "admin"}:
                raise CreatorOperationsError("real_spend_owner_admin_required")
            if not self.settings.allow_real_spend or not confirm_real_spend:
                raise CreatorOperationsError("real_spend_gate_required")
            if estimated_credit_per_item < 1:
                raise CreatorOperationsError("template_credit_estimate_required")
            if estimated_credits > credit_limit:
                raise CreatorOperationsError(
                    f"generation_credit_limit_exceeded:{estimated_credits}>{credit_limit}"
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
                "credit_limit": credit_limit,
                "real_spend_requested": not dry_run,
                "template_snapshot": template_snapshot,
                "template_snapshot_sha256": template_snapshot_sha256,
                "source_dry_run_batch_id": _source_dry_run_batch_id,
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
                    template_snapshot=template_snapshot,
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
        payout_per_post_minor: int = 0,
        start_timezone: str = "Europe/Moscow",
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
        payout_minor = self._nonnegative_int(
            payout_per_post_minor,
            "payout_per_post_minor",
        )
        if payout_minor > PLACEMENT_PAYOUT_MAX_MINOR:
            raise CreatorOperationsError(
                f"payout_per_post_minor_exceeds_{PLACEMENT_PAYOUT_MAX_MINOR}"
            )
        if payout_minor and actor.role not in {"owner", "admin"}:
            raise CreatorOperationsError("payout_rate_owner_admin_required")
        try:
            interval_minutes = int(interval_minutes)
        except (TypeError, ValueError) as exc:
            raise CreatorOperationsError("invalid_interval_minutes") from exc
        if not 1 <= interval_minutes <= PLACEMENT_INTERVAL_MAX_MINUTES:
            raise CreatorOperationsError(
                f"interval_minutes_must_be_1_to_{PLACEMENT_INTERVAL_MAX_MINUTES}"
            )
        start_at = self._normalize_placement_start(start_at, start_timezone)
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
                "start_timezone": start_timezone,
                "interval_minutes": interval_minutes,
                "payout_per_post_minor": payout_minor,
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
                "start_timezone": start_timezone,
                "interval_minutes": interval_minutes,
                "payout_per_post_minor": payout_minor,
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
                assignee_id = assignees[index % len(assignees)]
                package = packages[package_id]
                scheduled_at = start_at + timedelta(minutes=index * interval_minutes)
                common_blockers: list[str] = []
                if package_id in existing_scheduled_packages:
                    common_blockers.append("publishing_package_already_scheduled")
                try:
                    self._tracking_target_url(package)
                except CreatorOperationsError as exc:
                    common_blockers.append(str(exc))
                compatible_destinations = [
                    destinations[destination_id]
                    for destination_id in destination_ids
                    if normalize_platform(destinations[destination_id].platform)
                    == normalize_platform(package.target_platform)
                    and destinations[destination_id].brand.strip().casefold()
                    == package.brand.strip().casefold()
                ]
                if not compatible_destinations:
                    errors.append(
                        {
                            "package_id": package.id,
                            "destination_id": None,
                            "scheduled_at": scheduled_at.isoformat(),
                            "error": "compatible_destination_required",
                            "error_codes": ["compatible_destination_required"],
                            "package_platform": normalize_platform(package.target_platform),
                            "package_brand": package.brand,
                            "action": "Выберите активную площадку с той же платформой и брендом.",
                        }
                    )
                    continue
                rotation = index % len(compatible_destinations)
                compatible_destinations = (
                    compatible_destinations[rotation:] + compatible_destinations[:rotation]
                )
                selected: tuple[
                    models.PublishingDestination,
                    dict[str, object],
                    tuple[int, object],
                    tuple[int, object],
                ] | None = None
                candidate_errors: list[dict[str, object]] = []
                for destination in compatible_destinations:
                    with self.db.no_autoflush:
                        validation = scheduler.validate(package, destination, scheduled_at)
                    blockers = [
                        *common_blockers,
                        *self._media_aware_blockers(
                            package,
                            organization_id,
                            validation["blockers"],
                        ),
                    ]
                    day_key = (destination.id, scheduled_at.date())
                    week_start = scheduled_at.date() - timedelta(days=scheduled_at.weekday())
                    week_key = (destination.id, week_start)
                    if (
                        validation["daily_count"]
                        + reserved_daily.get(day_key, 0)
                        >= destination.daily_limit
                    ):
                        blockers.append("daily_publishing_limit_reached_in_batch")
                    if (
                        validation["weekly_count"]
                        + reserved_weekly.get(week_key, 0)
                        >= destination.weekly_limit
                    ):
                        blockers.append("weekly_publishing_limit_reached_in_batch")
                    blockers = list(
                        dict.fromkeys(
                            self._placement_blocker_code(item) for item in blockers
                        )
                    )
                    if blockers:
                        candidate_errors.append(
                            {
                                "destination_id": destination.id,
                                "destination_name": destination.name,
                                "error_codes": blockers,
                            }
                        )
                        continue
                    selected = (destination, validation, day_key, week_key)
                    break
                if selected is None:
                    error_codes = list(
                        dict.fromkeys(
                            code
                            for candidate in candidate_errors
                            for code in list(candidate.get("error_codes") or [])
                        )
                    )
                    errors.append(
                        {
                            "package_id": package.id,
                            "destination_id": None,
                            "scheduled_at": scheduled_at.isoformat(),
                            "error": ";".join(error_codes) or "compatible_destination_unavailable",
                            "error_codes": error_codes or ["compatible_destination_unavailable"],
                            "candidate_errors": candidate_errors,
                            "action": "Устраните препятствия площадки или выберите другую совместимую площадку.",
                        }
                    )
                    continue
                destination, validation, day_key, week_key = selected
                reserved_daily[day_key] = reserved_daily.get(day_key, 0) + 1
                reserved_weekly[week_key] = reserved_weekly.get(week_key, 0) + 1
                planned.append(
                    {
                        "package_id": package.id,
                        "destination_id": destination.id,
                        "assignee_user_profile_id": assignee_id,
                        "payout_per_post_minor": payout_minor,
                        "scheduled_at": scheduled_at.isoformat(),
                        "matched_destination": {
                            "id": destination.id,
                            "name": destination.name,
                            "platform": normalize_platform(destination.platform),
                            "brand": destination.brand,
                        },
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
                tracking_link = self._ensure_tracking_link(
                    publishing_task=task,
                    package=package,
                    destination=destination,
                    batch=batch,
                    sequence=sequence,
                )
                manual_upload = ManualUploadProvider(self.db).payload(task)
                task.raw_response_json = {
                    **dict(task.raw_response_json or {}),
                    "manual_upload": manual_upload,
                }
                creator_task = self._placement_task(
                    batch=batch,
                    package=package,
                    destination=destination,
                    publishing_task=task,
                    assignee_user_profile_id=int(plan["assignee_user_profile_id"]),
                    actor_user_profile_id=actor_user_profile_id,
                    sequence=sequence,
                    tracking_link=tracking_link,
                    manual_upload=manual_upload,
                )
                created_results.append(
                    {
                        **plan,
                        "publishing_task_id": task.id,
                        "creator_task_id": creator_task.id,
                        "media_artifact_id": package.media_artifact_id,
                        "tracking_link_id": tracking_link.id,
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

    def promote_dry_run_batch(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        batch_id: int,
        confirm_real_spend: bool = False,
        confirmed_total_credits: int = 0,
    ) -> models.MassOperationBatch:
        """Revalidate and launch an immutable dry-run without re-entering it."""

        self._membership(organization_id, actor_user_profile_id)
        preview = self.db.scalar(
            select(models.MassOperationBatch)
            .where(
                models.MassOperationBatch.id == int(batch_id),
                models.MassOperationBatch.organization_id == organization_id,
                models.MassOperationBatch.dry_run.is_(True),
            )
            .with_for_update()
        )
        if preview is None:
            raise CreatorOperationsError("dry_run_batch_not_found")
        if (
            preview.status != "validated"
            or int(preview.total_failed or 0) != 0
            or bool(preview.errors_json)
        ):
            raise CreatorOperationsError("dry_run_batch_must_be_clean_before_launch")
        parameters = dict(preview.parameters_json or {})
        promoted_id = parameters.get("promoted_to_batch_id")
        if promoted_id is not None:
            promoted = self.db.scalar(
                select(models.MassOperationBatch).where(
                    models.MassOperationBatch.id == int(promoted_id),
                    models.MassOperationBatch.organization_id == organization_id,
                    models.MassOperationBatch.dry_run.is_(False),
                )
            )
            if promoted is None:
                raise CreatorOperationsError("dry_run_promotion_lineage_invalid")
            return promoted

        launch_name = f"{preview.name[:164].rstrip()} · запуск"
        launch_key = (
            f"promote:{preview.operation_type}:{organization_id}:{preview.id}"
        )
        if preview.operation_type == "generation":
            template_snapshot = parameters.get("template_snapshot")
            template_snapshot_sha256 = parameters.get("template_snapshot_sha256")
            if not self._valid_generation_template_snapshot(
                template_snapshot,
                template_snapshot_sha256,
            ):
                raise CreatorOperationsError(
                    "dry_run_template_snapshot_missing_or_invalid:create_new_dry_run"
                )
            recovered = self._existing_batch(organization_id, launch_key)
            if recovered is not None:
                recovered_parameters = dict(recovered.parameters_json or {})
                if (
                    recovered.operation_type != "generation"
                    or recovered.dry_run
                    or int(recovered_parameters.get("source_dry_run_batch_id") or 0)
                    != preview.id
                    or not self._valid_generation_template_snapshot(
                        recovered_parameters.get("template_snapshot"),
                        recovered_parameters.get("template_snapshot_sha256"),
                    )
                    or recovered_parameters.get("template_snapshot_sha256")
                    != template_snapshot_sha256
                    or int(recovered_parameters.get("template_draft_id") or 0)
                    != int(parameters.get("template_draft_id") or 0)
                ):
                    raise CreatorOperationsError(
                        "dry_run_promotion_orphan_lineage_invalid"
                    )
                promoted = recovered
            else:
                promoted = self.generation_batch(
                    organization_id=organization_id,
                    actor_user_profile_id=actor_user_profile_id,
                    template_draft_id=int(parameters.get("template_draft_id") or 0),
                    assignee_user_profile_ids=list(
                        parameters.get("assignee_user_profile_ids") or []
                    ),
                    quantity=int(parameters.get("quantity") or 0),
                    name=launch_name,
                    idempotency_key=launch_key,
                    dry_run=False,
                    confirm_real_spend=confirm_real_spend,
                    confirmed_total_credits=confirmed_total_credits,
                    _expected_template_snapshot=template_snapshot,
                    _expected_template_snapshot_sha256=template_snapshot_sha256,
                    _source_dry_run_batch_id=preview.id,
                )
        elif preview.operation_type == "placement":
            try:
                stored_start = datetime.fromisoformat(
                    str(parameters.get("start_at") or "")
                )
            except ValueError as exc:
                raise CreatorOperationsError("dry_run_start_at_invalid") from exc
            if stored_start.tzinfo is None:
                stored_start = stored_start.replace(tzinfo=UTC)
            promoted = self.placement_batch(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                package_ids=list(parameters.get("package_ids") or []),
                destination_ids=list(parameters.get("destination_ids") or []),
                assignee_user_profile_ids=list(
                    parameters.get("assignee_user_profile_ids") or []
                ),
                start_at=stored_start,
                start_timezone=str(parameters.get("start_timezone") or "UTC"),
                interval_minutes=int(parameters.get("interval_minutes") or 0),
                payout_per_post_minor=int(
                    parameters.get("payout_per_post_minor") or 0
                ),
                name=launch_name,
                idempotency_key=launch_key,
                dry_run=False,
            )
        else:
            raise CreatorOperationsError("dry_run_operation_not_supported")

        refreshed_preview = self.db.get(models.MassOperationBatch, preview.id)
        if refreshed_preview is None:
            raise CreatorOperationsError("dry_run_batch_not_found")
        refreshed_preview.parameters_json = {
            **dict(refreshed_preview.parameters_json or {}),
            "promoted_to_batch_id": promoted.id,
            "promoted_by_user_profile_id": actor_user_profile_id,
            "promoted_at": models.utcnow().isoformat(),
        }
        promoted.parameters_json = {
            **dict(promoted.parameters_json or {}),
            "source_dry_run_batch_id": refreshed_preview.id,
        }
        self.db.commit()
        self.db.refresh(promoted)
        return promoted

    def task_inbox(
        self,
        *,
        organization_id: int,
        viewer_user_profile_id: int,
        status: str | None = None,
        status_group: str = "all",
        assignee_user_profile_id: int | None = None,
        mass_operation_batch_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[models.CreatorTask]:
        membership = self._membership(organization_id, viewer_user_profile_id)
        query = select(models.CreatorTask).where(models.CreatorTask.organization_id == organization_id)
        if membership.role not in {"owner", "admin"}:
            query = query.where(models.CreatorTask.assignee_user_profile_id == viewer_user_profile_id)
            if (
                assignee_user_profile_id is not None
                and int(assignee_user_profile_id) != viewer_user_profile_id
            ):
                raise CreatorOperationsError("task_assignee_filter_not_allowed")
        elif assignee_user_profile_id is not None:
            query = query.where(
                models.CreatorTask.assignee_user_profile_id
                == int(assignee_user_profile_id)
            )
        if mass_operation_batch_id is not None:
            query = query.where(
                models.CreatorTask.mass_operation_batch_id
                == int(mass_operation_batch_id)
            )
        if status:
            query = query.where(models.CreatorTask.status == status)
        normalized_group = str(status_group or "all").strip().casefold()
        if normalized_group == "active":
            query = query.where(models.CreatorTask.status.not_in(["done", "cancelled"]))
        elif normalized_group == "completed":
            query = query.where(models.CreatorTask.status.in_(["done", "cancelled"]))
        elif normalized_group != "all":
            raise CreatorOperationsError("invalid_task_status_group")
        if normalized_group == "completed":
            ordering = (
                models.CreatorTask.completed_at.desc(),
                models.CreatorTask.id.desc(),
            )
        else:
            ordering = (
                case(
                    (models.CreatorTask.status.not_in(["done", "cancelled"]), 0),
                    else_=1,
                ),
                models.CreatorTask.priority.desc(),
                models.CreatorTask.due_at,
                models.CreatorTask.id,
            )
        return list(
            self.db.scalars(
                query.order_by(*ordering)
                .offset(min(max(int(offset), 0), 1_000_000))
                .limit(min(max(int(limit), 1), 250))
            )
        )

    def payout_ledger(
        self,
        *,
        organization_id: int,
        viewer_user_profile_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[models.CreatorPayout]:
        membership = self._membership(organization_id, viewer_user_profile_id)
        query = select(models.CreatorPayout).where(models.CreatorPayout.organization_id == organization_id)
        if membership.role not in {"owner", "admin"}:
            query = query.where(models.CreatorPayout.user_profile_id == viewer_user_profile_id)
        return list(
            self.db.scalars(
                query.order_by(models.CreatorPayout.created_at.desc(), models.CreatorPayout.id.desc())
                .offset(min(max(int(offset), 0), 1_000_000))
                .limit(min(max(int(limit), 1), 250))
            )
        )

    def workload_snapshot(
        self,
        *,
        organization_id: int,
        viewer_user_profile_id: int,
    ) -> dict[str, int]:
        membership = self._membership(organization_id, viewer_user_profile_id)
        task_scope = [models.CreatorTask.organization_id == organization_id]
        payout_scope = [models.CreatorPayout.organization_id == organization_id]
        if membership.role not in {"owner", "admin"}:
            task_scope.append(
                models.CreatorTask.assignee_user_profile_id == viewer_user_profile_id
            )
            payout_scope.append(
                models.CreatorPayout.user_profile_id == viewer_user_profile_id
            )
        task_totals = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (models.CreatorTask.status.not_in(["done", "cancelled"]), 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("tasks_open"),
                func.coalesce(
                    func.sum(
                        case(
                            (models.CreatorTask.status == "done", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("tasks_done"),
                func.coalesce(
                    func.sum(
                        case(
                            (models.CreatorTask.status == "cancelled", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("tasks_cancelled"),
            ).where(*task_scope)
        ).one()
        payout_totals = self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                models.CreatorPayout.status.in_(["pending", "approved"]),
                                models.CreatorPayout.amount_minor,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("payout_pending_minor"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                models.CreatorPayout.status == "paid",
                                models.CreatorPayout.amount_minor,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("payout_paid_minor"),
            ).where(*payout_scope)
        ).one()
        tasks_done = int(task_totals.tasks_done or 0)
        tasks_cancelled = int(task_totals.tasks_cancelled or 0)
        return {
            "tasks_open": int(task_totals.tasks_open or 0),
            "tasks_done": tasks_done,
            "tasks_cancelled": tasks_cancelled,
            "tasks_closed": tasks_done + tasks_cancelled,
            "payout_pending_minor": int(payout_totals.payout_pending_minor or 0),
            "payout_paid_minor": int(payout_totals.payout_paid_minor or 0),
        }

    def performance_snapshot(
        self,
        *,
        organization_id: int,
        viewer_user_profile_id: int,
    ) -> dict[str, int | float]:
        """Return tenant-safe latest-snapshot metrics for measurable placements.

        Canonical imports may contain several non-overlapping reporting periods;
        those periods are summed. Manual cumulative snapshots have no period and
        only their newest row is used. If canonical periods exist for a post,
        they take precedence over manual snapshots to prevent double counting.
        """

        membership = self._membership(organization_id, viewer_user_profile_id)
        publication_scope = [
            models.PublishingPackage.organization_id == organization_id,
        ]
        if membership.role not in {"owner", "admin"}:
            publication_scope.append(
                exists(
                    select(models.CreatorTask.id).where(
                        models.CreatorTask.organization_id == organization_id,
                        models.CreatorTask.publishing_task_id == models.PublishingTask.id,
                        models.CreatorTask.assignee_user_profile_id == viewer_user_profile_id,
                        models.CreatorTask.task_type == "manual_placement",
                        models.CreatorTask.status != "cancelled",
                    )
                )
            )

        published_placements = self.db.scalar(
            select(func.count(models.PublishingTask.id))
            .select_from(models.PublishingTask)
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id == models.PublishingTask.publishing_package_id,
            )
            .where(
                *publication_scope,
                models.PublishingTask.final_url.is_not(None),
                models.PublishingTask.final_url != "",
            )
        ) or 0
        tracking_click_scope = (
            select(func.count(models.TrackingClick.id))
            .select_from(models.TrackingClick)
            .join(
                models.PublishingTask,
                models.PublishingTask.id == models.TrackingClick.publishing_task_id,
            )
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id
                == models.PublishingTask.publishing_package_id,
            )
            .where(*publication_scope)
        )
        tracking_clicks_raw = self.db.scalar(tracking_click_scope) or 0
        tracking_clicks = self.db.scalar(
            tracking_click_scope.where(
                models.TrackingClick.metadata_json["tracking_v1"][
                    "accepted_for_human_kpi"
                ]
                .as_boolean()
                .is_(True)
            )
        ) or 0
        overlapping_period_metric = aliased(models.DestinationPostMetric)
        period_row_has_overlap = exists(
            select(overlapping_period_metric.id).where(
                overlapping_period_metric.publishing_task_id
                == models.DestinationPostMetric.publishing_task_id,
                overlapping_period_metric.id != models.DestinationPostMetric.id,
                overlapping_period_metric.period_start.is_not(None),
                overlapping_period_metric.period_end.is_not(None),
                overlapping_period_metric.period_start
                <= models.DestinationPostMetric.period_end,
                overlapping_period_metric.period_end
                >= models.DestinationPostMetric.period_start,
            )
        )
        quarantined_metric_rows = self.db.scalar(
            select(func.count(models.DestinationPostMetric.id))
            .select_from(models.DestinationPostMetric)
            .join(
                models.PublishingTask,
                models.PublishingTask.id
                == models.DestinationPostMetric.publishing_task_id,
            )
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id
                == models.PublishingTask.publishing_package_id,
            )
            .where(
                *publication_scope,
                models.DestinationPostMetric.period_start.is_not(None),
                models.DestinationPostMetric.period_end.is_not(None),
                period_row_has_overlap,
            )
        ) or 0
        period_rows = (
            select(
                models.DestinationPostMetric.publishing_task_id.label("publishing_task_id"),
                func.coalesce(func.sum(models.DestinationPostMetric.views), 0).label("views"),
                func.coalesce(func.sum(models.DestinationPostMetric.clicks), 0).label("clicks"),
                func.coalesce(func.sum(models.DestinationPostMetric.orders), 0).label("orders"),
                func.coalesce(func.sum(models.DestinationPostMetric.revenue), 0.0).label("revenue"),
            )
            .select_from(models.DestinationPostMetric)
            .join(
                models.PublishingTask,
                models.PublishingTask.id == models.DestinationPostMetric.publishing_task_id,
            )
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id == models.PublishingTask.publishing_package_id,
            )
            .where(
                *publication_scope,
                models.DestinationPostMetric.period_start.is_not(None),
                models.DestinationPostMetric.period_end.is_not(None),
                ~period_row_has_overlap,
            )
            .group_by(models.DestinationPostMetric.publishing_task_id)
        )
        usable_period_metric = aliased(models.DestinationPostMetric)
        conflicting_period_metric = aliased(models.DestinationPostMetric)
        usable_period_has_overlap = exists(
            select(conflicting_period_metric.id).where(
                conflicting_period_metric.publishing_task_id
                == usable_period_metric.publishing_task_id,
                conflicting_period_metric.id != usable_period_metric.id,
                conflicting_period_metric.period_start.is_not(None),
                conflicting_period_metric.period_end.is_not(None),
                conflicting_period_metric.period_start
                <= usable_period_metric.period_end,
                conflicting_period_metric.period_end
                >= usable_period_metric.period_start,
            )
        ).correlate(usable_period_metric)
        has_period_rows = exists(
            select(usable_period_metric.id).where(
                usable_period_metric.publishing_task_id
                == models.DestinationPostMetric.publishing_task_id,
                usable_period_metric.period_start.is_not(None),
                usable_period_metric.period_end.is_not(None),
                ~usable_period_has_overlap,
            )
        )
        latest_unperioded_metric_ids = (
            select(func.max(models.DestinationPostMetric.id).label("metric_id"))
            .select_from(models.DestinationPostMetric)
            .join(
                models.PublishingTask,
                models.PublishingTask.id == models.DestinationPostMetric.publishing_task_id,
            )
            .join(
                models.PublishingPackage,
                models.PublishingPackage.id == models.PublishingTask.publishing_package_id,
            )
            .where(
                *publication_scope,
                models.DestinationPostMetric.publishing_task_id.is_not(None),
                models.DestinationPostMetric.period_start.is_(None),
                models.DestinationPostMetric.period_end.is_(None),
                ~has_period_rows,
            )
            .group_by(models.DestinationPostMetric.publishing_task_id)
            .subquery()
        )
        latest_unperioded_rows = select(
            models.DestinationPostMetric.publishing_task_id.label("publishing_task_id"),
            func.coalesce(models.DestinationPostMetric.views, 0).label("views"),
            func.coalesce(models.DestinationPostMetric.clicks, 0).label("clicks"),
            func.coalesce(models.DestinationPostMetric.orders, 0).label("orders"),
            func.coalesce(models.DestinationPostMetric.revenue, 0.0).label("revenue"),
        ).join(
            latest_unperioded_metric_ids,
            latest_unperioded_metric_ids.c.metric_id == models.DestinationPostMetric.id,
        )
        canonical_rows = union_all(period_rows, latest_unperioded_rows).subquery()
        totals = self.db.execute(
            select(
                func.count(func.distinct(canonical_rows.c.publishing_task_id)).label(
                    "tracked_placements"
                ),
                func.coalesce(func.sum(canonical_rows.c.views), 0).label("views"),
                func.coalesce(func.sum(canonical_rows.c.clicks), 0).label("clicks"),
                func.coalesce(func.sum(canonical_rows.c.orders), 0).label("orders"),
                func.coalesce(func.sum(canonical_rows.c.revenue), 0.0).label("revenue"),
            )
            .select_from(canonical_rows)
        ).one()
        return {
            "published_placements": int(published_placements),
            "tracking_clicks": int(tracking_clicks),
            "tracking_clicks_raw": int(tracking_clicks_raw),
            "tracked_placements": int(totals.tracked_placements or 0),
            "views": int(totals.views or 0),
            "clicks": int(totals.clicks or 0),
            "orders": int(totals.orders or 0),
            "revenue": float(totals.revenue or 0.0),
            "quarantined_metric_rows": int(quarantined_metric_rows),
        }

    def decide_payout(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        payout_id: int,
        decision: str,
        notes: str | None = None,
    ) -> models.CreatorPayout:
        membership = self._membership(organization_id, actor_user_profile_id)
        if membership.role not in {"owner", "admin"}:
            raise CreatorOperationsError("payout_manager_role_required")
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise CreatorOperationsError("invalid_payout_decision")
        cleaned_notes = " ".join(str(notes or "").strip().split())[:2000]
        if normalized_decision == "reject" and len(cleaned_notes) < 10:
            raise CreatorOperationsError("payout_rejection_reason_too_short")
        payout = self._payout_for_update(organization_id, payout_id)
        if normalized_decision == "approve":
            if payout.status in {"approved", "paid"}:
                return payout
            if payout.status != "pending":
                raise CreatorOperationsError("payout_not_approvable")
            payout.status = "approved"
            payout.approved_by_user_profile_id = actor_user_profile_id
            payout.approved_at = models.utcnow()
        else:
            if payout.status == "rejected":
                return payout
            if payout.status != "pending":
                raise CreatorOperationsError("payout_not_rejectable")
            payout.status = "rejected"
            payout.reason = (
                f"{str(payout.reason or 'Начисление').strip()} · Отклонено: {cleaned_notes}"
            )
        self.db.commit()
        self.db.refresh(payout)
        return payout

    def mark_payout_paid(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        payout_id: int,
        external_payment_reference: str,
    ) -> models.CreatorPayout:
        membership = self._membership(organization_id, actor_user_profile_id)
        if membership.role not in {"owner", "admin"}:
            raise CreatorOperationsError("payout_manager_role_required")
        reference = " ".join(str(external_payment_reference or "").strip().split())
        if not 3 <= len(reference) <= 180 or any(ord(char) < 32 for char in reference):
            raise CreatorOperationsError("external_payment_reference_invalid")
        payout = self._payout_for_update(organization_id, payout_id)
        if payout.status == "paid":
            if payout.external_payment_reference == reference:
                return payout
            raise CreatorOperationsError("external_payment_reference_mismatch")
        if payout.status != "approved" or payout.approved_by_user_profile_id is None:
            raise CreatorOperationsError("payout_must_be_approved_first")
        payout.status = "paid"
        payout.external_payment_reference = reference
        payout.paid_at = models.utcnow()
        self.db.commit()
        self.db.refresh(payout)
        return payout

    def review_generated_task(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        task_id: int,
        expected_media_artifact_id: int,
        expected_media_artifact_public_id: str,
        expected_media_artifact_sha256: str,
        decision: str,
        notes: str | None = None,
        confirm_video_watched: bool = False,
    ) -> models.CreatorTask:
        membership = self._membership(organization_id, actor_user_profile_id)
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approve", "reject"}:
            raise CreatorOperationsError("invalid_review_decision")
        cleaned_notes = " ".join(str(notes or "").strip().split())[:2000]
        if confirm_video_watched is not True:
            raise CreatorOperationsError("video_review_watch_confirmation_required")
        if len(cleaned_notes) < 10:
            raise CreatorOperationsError(
                "rejection_reason_too_short"
                if normalized_decision == "reject"
                else "approval_review_notes_too_short"
            )

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

        artifact = self.db.scalar(
            select(models.MediaArtifact)
            .where(
                models.MediaArtifact.id == task.media_artifact_id,
                models.MediaArtifact.organization_id == organization_id,
            )
            .with_for_update()
        )
        if (
            artifact is None
            or artifact.status != "ready"
            or artifact.deleted_at is not None
            or artifact.kind not in {"master_video", "provider_output"}
            or str(artifact.mime_type or "").split(";", 1)[0].strip().lower()
            != "video/mp4"
            or artifact.size_bytes <= 0
            or re.fullmatch(r"[0-9a-f]{64}", str(artifact.sha256 or "")) is None
        ):
            raise CreatorOperationsError("review_video_not_ready")

        # The browser posts the immutable identity of the exact MP4 opened by
        # the reviewer.  Compare it only after locking both the task pointer
        # and artifact row, so a worker cannot replace the pointer or bytes in
        # the gap between page rendering and the approval transaction.
        if (
            not isinstance(expected_media_artifact_id, int)
            or isinstance(expected_media_artifact_id, bool)
            or expected_media_artifact_id != artifact.id
            or expected_media_artifact_public_id != artifact.public_id
            or expected_media_artifact_sha256 != artifact.sha256
        ):
            raise CreatorOperationsError("review_video_identity_mismatch")

        previous = dict(task.result_json or {}).get("review_decision")
        if task.status in {"done", "cancelled"}:
            if previous == normalized_decision:
                return task
            raise CreatorOperationsError("review_task_already_finalized")
        draft = self.db.scalar(
            select(models.ProductUGCRecipeDraft)
            .where(models.ProductUGCRecipeDraft.id == task.product_ugc_recipe_draft_id)
            .with_for_update()
        )
        if draft is None or draft.product.organization_id != organization_id:
            raise CreatorOperationsError("review_draft_not_found")

        creative_inputs = dict(draft.creative_inputs_json or {})
        blocked_artifacts = [
            dict(item)
            for item in list(creative_inputs.get("blocked_media_artifacts_v1") or [])
            if isinstance(item, dict)
        ]
        artifact_was_rejected = any(
            item.get("media_artifact_id") == artifact.id
            or item.get("public_id") == artifact.public_id
            or item.get("sha256") == artifact.sha256
            for item in blocked_artifacts
        )
        if normalized_decision == "approve" and artifact_was_rejected:
            raise CreatorOperationsError("review_rejected_artifact_requires_regeneration")
        if task.status == "blocked" and previous == "reject":
            if normalized_decision == "reject" and artifact_was_rejected:
                return task
            if artifact_was_rejected:
                raise CreatorOperationsError("review_rejected_artifact_requires_regeneration")

        now = models.utcnow()
        task.submitted_at = now
        task.result_json = {
            **dict(task.result_json or {}),
            "review_decision": normalized_decision,
            "review_notes": cleaned_notes,
            "reviewed_by_user_profile_id": actor_user_profile_id,
            "reviewed_at": now.isoformat(),
            "media_artifact_id": artifact.id,
            "media_artifact_public_id": artifact.public_id,
            "media_artifact_sha256": artifact.sha256,
        }
        draft.human_review_notes = cleaned_notes or None
        if normalized_decision == "approve":
            task.status = "done"
            task.completed_at = now
            task.blockers_json = []
            draft.human_review_status = "approved"
            draft.publishing_readiness = "ready_for_publishing_package"
            creative_inputs["approved_media_artifact_v1"] = {
                "media_artifact_id": artifact.id,
                "public_id": artifact.public_id,
                "sha256": artifact.sha256,
                "provider_task_id": draft.provider_task_id,
                "reviewed_by_user_profile_id": actor_user_profile_id,
                "reviewed_at": now.isoformat(),
            }
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
            rejected_identity = {
                "media_artifact_id": artifact.id,
                "public_id": artifact.public_id,
                "sha256": artifact.sha256,
                "provider_task_id": draft.provider_task_id,
                "rejected_by_user_profile_id": actor_user_profile_id,
                "rejected_at": now.isoformat(),
                "reason": cleaned_notes,
            }
            if not artifact_was_rejected:
                blocked_artifacts.append(rejected_identity)
            creative_inputs["blocked_media_artifacts_v1"] = blocked_artifacts
            creative_inputs.pop("approved_media_artifact_v1", None)
        draft.creative_inputs_json = creative_inputs
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
        # Serialize final-URL acceptance across every placement batch in the
        # organization. A batch-only lock would allow two concurrent batches
        # to accept the same post and create duplicate payouts.
        organization_lock = self.db.scalar(
            select(models.Organization.id)
            .where(models.Organization.id == organization_id)
            .with_for_update()
        )
        if organization_lock is None:
            raise CreatorOperationsError("active_membership_required")
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

        try:
            canonical_url = claim_publication_identity(
                self.db,
                task=publishing_task,
                final_url=final_url,
            )
        except PublicationIdentityError as exc:
            raise CreatorOperationsError(exc.code) from exc
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
        payout_minor = self._nonnegative_int(
            dict(batch.parameters_json or {}).get("payout_per_post_minor", 0),
            "payout_per_post_minor",
        )
        if payout_minor:
            self.db.add(
                models.CreatorPayout(
                    organization_id=organization_id,
                    user_profile_id=task.assignee_user_profile_id,
                    creator_task_id=task.id,
                    publishing_task_id=publishing_task.id,
                    amount_minor=payout_minor,
                    currency="RUB",
                    status="pending",
                    reason=(
                        f"Подтверждённое размещение · {destination.platform} · "
                        f"задача #{task.id}"
                    ),
                    idempotency_key=f"placement:{batch.id}:task:{task.id}:payout",
                )
            )
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
        event_key = f"publication_completed:publishing_task:{publishing_task.id}"
        existing_event = self.db.scalar(
            select(models.FactoryEvent).where(models.FactoryEvent.idempotency_key == event_key)
        )
        if existing_event is None:
            self.db.add(
                models.FactoryEvent(
                    event_name="publication_completed",
                    event_version=1,
                    occurred_at=now,
                    received_at=now,
                    organization_id=organization_id,
                    user_profile_id=actor_user_profile_id,
                    role=membership.role,
                    factory_run_id=f"mass_placement:{batch.id}",
                    entity_type="publishing_task",
                    entity_id=str(publishing_task.id),
                    product_id=package.product_id,
                    sku=product.sku,
                    publishing_task_id=publishing_task.id,
                    source="server",
                    idempotency_key=event_key,
                    properties_json={
                        "platform": destination.platform,
                        "mass_operation_batch_id": batch.id,
                        "creator_task_id": task.id,
                        "assignee_user_profile_id": task.assignee_user_profile_id,
                    },
                )
            )
        self.db.commit()
        self.db.refresh(task)
        return task

    def record_manual_metrics(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        task_id: int,
        views: int,
        clicks: int,
        orders: int,
        revenue_minor: int,
        allow_correction: bool = False,
        correction_reason: str | None = None,
    ) -> models.DestinationPostMetric:
        membership = self._membership(organization_id, actor_user_profile_id)
        counts = {
            "views": self._nonnegative_int(views, "views"),
            "clicks": self._nonnegative_int(clicks, "clicks"),
            "orders": self._nonnegative_int(orders, "orders"),
        }
        if any(value > MANUAL_METRIC_COUNT_MAX for value in counts.values()):
            raise CreatorOperationsError("manual_metric_count_too_large")
        normalized_revenue_minor = self._nonnegative_int(revenue_minor, "revenue_minor")
        if normalized_revenue_minor > MANUAL_METRIC_REVENUE_MAX_MINOR:
            raise CreatorOperationsError("manual_metric_revenue_too_large")
        creator_task = self.db.scalar(
            select(models.CreatorTask)
            .where(
                models.CreatorTask.id == int(task_id),
                models.CreatorTask.organization_id == organization_id,
                models.CreatorTask.task_type == "manual_placement",
            )
            .with_for_update()
        )
        if creator_task is None:
            raise CreatorOperationsError("placement_task_not_found")
        if (
            membership.role not in {"owner", "admin"}
            and creator_task.assignee_user_profile_id != actor_user_profile_id
        ):
            raise CreatorOperationsError("placement_task_assignee_required")
        publishing_task = self.db.get(models.PublishingTask, creator_task.publishing_task_id)
        package = (
            self.db.get(models.PublishingPackage, publishing_task.publishing_package_id)
            if publishing_task is not None
            else None
        )
        destination = (
            self.db.get(models.PublishingDestination, publishing_task.destination_id)
            if publishing_task is not None
            else None
        )
        product = self.db.get(models.Product, package.product_id) if package is not None else None
        if (
            creator_task.status != "done"
            or publishing_task is None
            or publishing_task.status != "published_manual"
            or not publishing_task.final_url
            or package is None
            or destination is None
            or product is None
            or package.organization_id != organization_id
            or destination.organization_id != organization_id
            or product.organization_id != organization_id
            or creator_task.product_id != product.id
        ):
            raise CreatorOperationsError("manual_metrics_publication_required")
        prior_metric = next(
            (
                item
                for item in self.db.scalars(
                    select(models.DestinationPostMetric)
                    .where(
                        models.DestinationPostMetric.publishing_task_id
                        == publishing_task.id,
                        models.DestinationPostMetric.period_start.is_(None),
                        models.DestinationPostMetric.period_end.is_(None),
                    )
                    .order_by(models.DestinationPostMetric.id.desc())
                    .limit(50)
                )
                if dict(item.raw_json or {}).get("source")
                == "manual_creator_cumulative_snapshot"
            ),
            None,
        )
        decreases = []
        if prior_metric is not None:
            prior_values = {
                "views": int(prior_metric.views or 0),
                "clicks": int(prior_metric.clicks or 0),
                "orders": int(prior_metric.orders or 0),
                "revenue_minor": int(round(float(prior_metric.revenue or 0.0) * 100)),
            }
            submitted_values = {**counts, "revenue_minor": normalized_revenue_minor}
            decreases = [
                key
                for key, prior_value in prior_values.items()
                if submitted_values[key] < prior_value
            ]
        cleaned_correction_reason = " ".join(
            str(correction_reason or "").strip().split()
        )[:2000]
        if decreases:
            if allow_correction is not True:
                raise CreatorOperationsError(
                    "manual_metrics_cumulative_decrease_requires_correction"
                )
            if membership.role not in {"owner", "admin"}:
                raise CreatorOperationsError("manual_metrics_correction_manager_required")
            if len(cleaned_correction_reason) < 10:
                raise CreatorOperationsError("manual_metrics_correction_reason_too_short")
        metric = models.DestinationPostMetric(
            destination_id=destination.id,
            publishing_task_id=publishing_task.id,
            product_id=product.id,
            sku=product.sku,
            platform=normalize_platform(destination.platform),
            posted_url=publishing_task.final_url,
            views=counts["views"],
            clicks=counts["clicks"],
            orders=counts["orders"],
            revenue=normalized_revenue_minor / 100.0,
            raw_json={
                "source": "manual_creator_cumulative_snapshot",
                "submitted_by_user_profile_id": actor_user_profile_id,
                "creator_task_id": creator_task.id,
                "mass_operation_batch_id": creator_task.mass_operation_batch_id,
                "previous_manual_metric_id": (
                    prior_metric.id if prior_metric is not None else None
                ),
                "cumulative_correction": (
                    {
                        "confirmed": True,
                        "reason": cleaned_correction_reason,
                        "decreased_fields": decreases,
                    }
                    if decreases
                    else None
                ),
            },
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def _payout_for_update(
        self,
        organization_id: int,
        payout_id: int,
    ) -> models.CreatorPayout:
        payout = self.db.scalar(
            select(models.CreatorPayout)
            .where(
                models.CreatorPayout.id == int(payout_id),
                models.CreatorPayout.organization_id == organization_id,
            )
            .with_for_update()
        )
        if payout is None:
            raise CreatorOperationsError("payout_not_found")
        return payout

    def _generation_template_snapshot(
        self,
        template: models.ProductUGCRecipeDraft,
        *,
        product: models.Product,
        organization_id: int,
        lock_related: bool,
    ) -> dict[str, object]:
        raw_asset_ids = deepcopy(template.product_asset_ids_json or [])
        referenced_asset_ids: set[int] = set()
        for raw_id in [*raw_asset_ids, template.primary_product_asset_id]:
            try:
                asset_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if asset_id > 0:
                referenced_asset_ids.add(asset_id)

        assets: list[models.ProductAsset] = []
        if referenced_asset_ids:
            asset_query = (
                select(models.ProductAsset)
                .where(
                    models.ProductAsset.id.in_(sorted(referenced_asset_ids)),
                    models.ProductAsset.product_id == template.product_id,
                )
                .order_by(models.ProductAsset.id)
            )
            if lock_related:
                asset_query = asset_query.with_for_update()
            assets = list(self.db.scalars(asset_query).all())

        referenced_artifact_ids: set[int] = set()
        for raw_id in [
            template.character_media_artifact_id,
            *(asset.media_artifact_id for asset in assets),
        ]:
            try:
                artifact_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if artifact_id > 0:
                referenced_artifact_ids.add(artifact_id)

        artifacts: list[models.MediaArtifact] = []
        if referenced_artifact_ids:
            artifact_query = (
                select(models.MediaArtifact)
                .where(
                    models.MediaArtifact.id.in_(sorted(referenced_artifact_ids)),
                    models.MediaArtifact.organization_id == organization_id,
                )
                .order_by(models.MediaArtifact.id)
            )
            if lock_related:
                artifact_query = artifact_query.with_for_update()
            artifacts = list(self.db.scalars(artifact_query).all())

        found_asset_ids = {int(asset.id) for asset in assets}
        found_artifact_ids = {int(artifact.id) for artifact in artifacts}
        return {
            "schema": GENERATION_TEMPLATE_SNAPSHOT_SCHEMA,
            "draft": {
                "id": int(template.id),
                "organization_id": int(organization_id),
                "product_id": int(template.product_id),
                "sku": template.sku,
                "variant_key": template.variant_key,
                "status": template.status,
                "recipe_version": template.recipe_version,
                "platform": template.platform,
                "language": template.language,
                "character_image_path": template.character_image_path,
                "character_media_artifact_id": template.character_media_artifact_id,
                "character_image_filename": template.character_image_filename,
                "likeness_consent": bool(template.likeness_consent),
                "exact_variant_confirmed": bool(template.exact_variant_confirmed),
                "product_asset_ids_json": raw_asset_ids,
                "primary_product_asset_id": template.primary_product_asset_id,
                "product_info": template.product_info,
                "user_concept": template.user_concept,
                "creative_inputs_json": deepcopy(template.creative_inputs_json or {}),
                "duration_seconds": int(template.duration_seconds),
                "ratio": template.ratio,
                "audio_enabled": bool(template.audio_enabled),
                "estimated_credits": int(template.estimated_credits or 0),
                "provider_payload_preview_json": deepcopy(
                    template.provider_payload_preview_json or {}
                ),
                "blockers_json": deepcopy(template.blockers_json or []),
                "warnings_json": deepcopy(template.warnings_json or []),
            },
            "product": {
                "id": int(product.id),
                "organization_id": int(organization_id),
                "sku": product.sku,
                "brand": product.brand,
                "title": product.title,
                "description": product.description,
                "category": product.category,
                "attributes_json": deepcopy(product.attributes_json or {}),
                "benefits_json": deepcopy(product.benefits_json or []),
                "restrictions_json": deepcopy(product.restrictions_json or []),
            },
            "product_assets": [
                {
                    "id": int(asset.id),
                    "product_id": int(asset.product_id),
                    "asset_kit_id": int(asset.asset_kit_id),
                    "media_artifact_id": asset.media_artifact_id,
                    "source_ref": asset.source_ref,
                    "source_type": asset.source_type,
                    "asset_type": asset.asset_type,
                    "asset_role": asset.asset_role,
                    "filename": asset.filename,
                    "extension": asset.extension,
                    "mime_type": asset.mime_type,
                    "width": asset.width,
                    "height": asset.height,
                    "exists": bool(asset.exists),
                    "status": asset.status,
                    "is_primary_reference": bool(asset.is_primary_reference),
                    "is_safe_for_real_generation": bool(
                        asset.is_safe_for_real_generation
                    ),
                    "manual_label": asset.manual_label,
                    "review_status": asset.review_status,
                    "review_notes": asset.review_notes,
                    "checksum": asset.checksum,
                    "metadata_json": deepcopy(asset.metadata_json or {}),
                }
                for asset in assets
            ],
            "missing_product_asset_ids": sorted(
                referenced_asset_ids - found_asset_ids
            ),
            "media_artifacts": [
                {
                    "id": int(artifact.id),
                    "public_id": artifact.public_id,
                    "organization_id": int(artifact.organization_id),
                    "product_id": artifact.product_id,
                    "kind": artifact.kind,
                    "backend_name": artifact.backend_name,
                    "bucket": artifact.bucket,
                    "object_key": artifact.object_key,
                    "object_version": artifact.object_version,
                    "etag": artifact.etag,
                    "original_filename": artifact.original_filename,
                    "mime_type": artifact.mime_type,
                    "size_bytes": int(artifact.size_bytes),
                    "sha256": artifact.sha256,
                    "status": artifact.status,
                    "archived_at": self._snapshot_datetime(artifact.archived_at),
                    "delete_requested_at": self._snapshot_datetime(
                        artifact.delete_requested_at
                    ),
                    "deleted_at": self._snapshot_datetime(artifact.deleted_at),
                }
                for artifact in artifacts
            ],
            "missing_media_artifact_ids": sorted(
                referenced_artifact_ids - found_artifact_ids
            ),
        }

    @staticmethod
    def _generation_template_snapshot_hash(snapshot: dict[str, object]) -> str:
        return canonical_json_sha256(snapshot)

    @staticmethod
    def _generation_template_snapshot_changes(
        expected: dict[str, object],
        current: dict[str, object],
    ) -> list[str]:
        changes: list[str] = []
        expected_draft = expected.get("draft")
        current_draft = current.get("draft")
        if isinstance(expected_draft, dict) and isinstance(current_draft, dict):
            for key in sorted(set(expected_draft) | set(current_draft)):
                if expected_draft.get(key) != current_draft.get(key):
                    changes.append(f"draft.{key}")
        elif expected_draft != current_draft:
            changes.append("draft")
        for section in (
            "schema",
            "product",
            "product_assets",
            "missing_product_asset_ids",
            "media_artifacts",
            "missing_media_artifact_ids",
        ):
            if expected.get(section) != current.get(section):
                changes.append(section)
        return changes[:8] or ["snapshot"]

    @classmethod
    def _valid_generation_template_snapshot(
        cls,
        snapshot: object,
        snapshot_sha256: object,
    ) -> bool:
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema") != GENERATION_TEMPLATE_SNAPSHOT_SCHEMA
            or not isinstance(snapshot_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", snapshot_sha256) is None
        ):
            return False
        try:
            return cls._generation_template_snapshot_hash(snapshot) == snapshot_sha256
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _snapshot_datetime(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    def _clone_draft(
        self,
        template: models.ProductUGCRecipeDraft,
        *,
        template_snapshot: dict[str, object],
        batch: models.MassOperationBatch,
        sequence: int,
        actor_user_profile_id: int,
        assignee_user_profile_id: int,
    ) -> models.ProductUGCRecipeDraft:
        source = template_snapshot.get("draft")
        if not isinstance(source, dict) or int(source.get("id") or 0) != int(template.id):
            raise CreatorOperationsError("generation_template_snapshot_invalid")
        creative_inputs = deepcopy(source.get("creative_inputs_json") or {})
        creative_inputs["mass_batch"] = {
            "batch_id": batch.id,
            "sequence": sequence,
            "assignee_user_profile_id": assignee_user_profile_id,
        }
        draft = models.ProductUGCRecipeDraft(
            product_id=int(source["product_id"]),
            created_by_user_profile_id=actor_user_profile_id,
            assigned_to_user_profile_id=assignee_user_profile_id,
            sku=source["sku"],
            # Catalog variant identity is a preflight input, not a row-unique
            # execution id. Per-clone identity lives in the durable job key and
            # mass_batch lineage below.
            variant_key=source.get("variant_key"),
            status="ready_for_paid_preflight",
            recipe_version=source["recipe_version"],
            platform=source["platform"],
            language=source["language"],
            character_image_path=source.get("character_image_path"),
            character_media_artifact_id=source.get("character_media_artifact_id"),
            character_image_filename=source["character_image_filename"],
            likeness_consent=source["likeness_consent"],
            exact_variant_confirmed=source["exact_variant_confirmed"],
            product_asset_ids_json=deepcopy(source.get("product_asset_ids_json") or []),
            primary_product_asset_id=source.get("primary_product_asset_id"),
            product_info=source["product_info"],
            user_concept=source["user_concept"],
            creative_inputs_json=creative_inputs,
            duration_seconds=source["duration_seconds"],
            ratio=source["ratio"],
            audio_enabled=source["audio_enabled"],
            estimated_credits=source["estimated_credits"],
            provider_payload_preview_json=deepcopy(
                source.get("provider_payload_preview_json") or {}
            ),
            blockers_json=[],
            warnings_json=deepcopy(source.get("warnings_json") or []),
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
        batch_parameters = dict(batch.parameters_json or {})
        template_snapshot = batch_parameters.get("template_snapshot")
        snapshot_draft = (
            template_snapshot.get("draft")
            if isinstance(template_snapshot, dict)
            else None
        )
        if not isinstance(snapshot_draft, dict):
            raise CreatorOperationsError("generation_template_snapshot_invalid")
        provider_payload = snapshot_draft.get("provider_payload_preview_json") or {}
        if not isinstance(provider_payload, dict):
            raise CreatorOperationsError("generation_provider_payload_snapshot_invalid")
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
                "generation_template_snapshot_schema": template_snapshot.get(
                    "schema"
                ),
                "generation_template_snapshot_hash": batch_parameters.get(
                    "template_snapshot_sha256"
                ),
                "source_preview_batch_id": batch_parameters.get(
                    "source_dry_run_batch_id"
                ),
                "source_batch_id": batch.id,
                "source_template_draft_id": snapshot_draft.get("id"),
                "launch_draft_id": draft.id,
                "estimated_credits_per_item": int(
                    snapshot_draft.get("estimated_credits") or 0
                ),
                "provider_payload_sha256": self._generation_template_snapshot_hash(
                    provider_payload
                ),
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
        tracking_link: models.TrackingLink,
        manual_upload: dict[str, object],
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
                "Скопируйте подготовленные текст, CTA и отслеживаемую ссылку ниже, "
                "затем вставьте публичный HTTPS URL публикации."
            ),
            status="todo",
            priority=3,
            due_at=publishing_task.scheduled_at,
            checklist_json=[
                "Открыть одобренное видео",
                "Скопировать подготовленный текст без изменения фактов",
                "Использовать отслеживаемую ссылку вместо прямой ссылки на товар",
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
                "tracking_link_id": tracking_link.id,
                "manual_upload": manual_upload,
            },
            blockers_json=[],
            idempotency_key=f"mass-placement:{batch.id}:task:{sequence}",
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _tracking_target_url(self, package: models.PublishingPackage) -> str:
        candidate = str(
            package.utm_url
            or package.product_url
            or getattr(package.product, "product_url", None)
            or ""
        ).strip()
        if not candidate:
            raise CreatorOperationsError("tracking_target_url_required")
        try:
            return safe_public_url(candidate, error_code="tracking_target_url_invalid")
        except DestinationConnectorDataError as exc:
            raise CreatorOperationsError("tracking_target_url_invalid") from exc

    def _ensure_tracking_link(
        self,
        *,
        publishing_task: models.PublishingTask,
        package: models.PublishingPackage,
        destination: models.PublishingDestination,
        batch: models.MassOperationBatch,
        sequence: int,
    ) -> models.TrackingLink:
        target_url = self._tracking_target_url(package)
        existing = self.db.scalar(
            select(models.TrackingLink).where(
                models.TrackingLink.publishing_task_id == publishing_task.id
            )
        )
        if existing is not None:
            if (
                existing.target_url != target_url
                or existing.destination_id != destination.id
                or existing.product_id != package.product_id
            ):
                raise CreatorOperationsError("tracking_link_lineage_invalid")
            return existing
        slug_seed = (
            f"{batch.id}:{sequence}:{publishing_task.id}:{package.id}:{destination.id}"
        )
        link = models.TrackingLink(
            slug=f"mp-{publishing_task.id}-{hashlib.sha256(slug_seed.encode('utf-8')).hexdigest()[:12]}",
            target_url=target_url,
            publishing_task_id=publishing_task.id,
            destination_id=destination.id,
            product_id=package.product_id,
            sku=package.product.sku,
            creative_variant_id=package.creative_variant_id,
            status="active",
        )
        self.db.add(link)
        self.db.flush()
        return link

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

    def final_exam_passed_user_ids(self, user_profile_ids: Iterable[int]) -> set[int]:
        return NoviceLearningPathService(self.db).verified_user_ids_for_module(
            user_profile_ids=tuple(int(item) for item in user_profile_ids),
            module_code=FINAL_EXAM_CODE,
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

    @staticmethod
    def _placement_blocker_code(value: str) -> str:
        message = " ".join(str(value or "").split())
        exact = {
            "PublishingPackage must be approved before scheduling.": "publishing_package_not_approved",
            "PublishingPackage review_status must be approved before scheduling.": "publishing_package_review_required",
            "Package platform must match destination platform.": "package_platform_mismatch",
            "Package brand must match destination brand.": "package_brand_mismatch",
            "Package and destination must belong to the same organization.": "package_destination_organization_mismatch",
            "Posting mode is disabled.": "destination_posting_disabled",
            "API posting requires configured valid platform credentials.": "destination_api_credentials_required",
            "Daily limit must be at least 1.": "destination_daily_limit_invalid",
            "Weekly limit must be at least 1.": "destination_weekly_limit_invalid",
            "Video file must exist and be non-empty.": "publishing_video_missing",
            "Media artifact package requires organization-scoped human review.": "publishing_media_review_required",
        }
        if message in exact:
            return exact[message]
        if message.startswith("Destination must be active;"):
            return "destination_not_active"
        if message.startswith("Daily publishing limit reached:"):
            return "daily_publishing_limit_reached"
        if message.startswith("Weekly publishing limit reached:"):
            return "weekly_publishing_limit_reached"
        if message.startswith("Media artifact"):
            return "publishing_media_artifact_invalid"
        return message or "placement_validation_failed"

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
    def _normalize_placement_start(
        value: datetime,
        timezone_name: str = "Europe/Moscow",
    ) -> datetime:
        if not isinstance(value, datetime):
            raise CreatorOperationsError("invalid_start_at")
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        normalized_timezone = str(timezone_name or "").strip()
        if (
            not normalized_timezone
            or len(normalized_timezone) > 64
            or not re.fullmatch(r"[A-Za-z0-9_+./-]+", normalized_timezone)
        ):
            raise CreatorOperationsError("invalid_start_timezone")
        try:
            local_timezone = ZoneInfo(normalized_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise CreatorOperationsError("invalid_start_timezone") from exc
        fold_zero = value.replace(tzinfo=local_timezone, fold=0)
        fold_one = value.replace(tzinfo=local_timezone, fold=1)
        if fold_zero.utcoffset() != fold_one.utcoffset():
            zero_round_trip = (
                fold_zero.astimezone(UTC)
                .astimezone(local_timezone)
                .replace(tzinfo=None)
            )
            one_round_trip = (
                fold_one.astimezone(UTC)
                .astimezone(local_timezone)
                .replace(tzinfo=None)
            )
            if zero_round_trip == value and one_round_trip == value:
                raise CreatorOperationsError("start_at_is_ambiguous_in_timezone")
        localized = fold_zero
        utc_value = localized.astimezone(UTC)
        # Reject wall-clock values that do not exist during a DST jump.  A
        # silent normalization would schedule a creator at a different hour.
        if utc_value.astimezone(local_timezone).replace(tzinfo=None) != value:
            raise CreatorOperationsError("start_at_does_not_exist_in_timezone")
        return utc_value.replace(tzinfo=None)

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
            return canonical_publication_url(value, destination)
        except PublicationIdentityError as exc:
            raise CreatorOperationsError(exc.code) from exc

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = " ".join(str(exc).split())[:300]
        lowered = message.casefold()
        for marker in ("token", "secret", "password", "authorization", "apikey", "api_key"):
            if marker in lowered:
                return "operation_failed_redacted"
        return message or exc.__class__.__name__
