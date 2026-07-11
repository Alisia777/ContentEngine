from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from threading import RLock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.generation_costs.errors import (
    GenerationCostConflictError,
    GenerationCostOwnershipError,
    GenerationCostValidationError,
)
from app.generation_costs.types import GenerationCostAggregate, GenerationCostRecordResult
from app.intelligence.safety import is_real_video_provider


ENTRY_KINDS = {"estimated", "actual"}
ENTRY_STATUSES = {"pending", "confirmed", "voided"}
COST_SOURCES = {
    "internal_estimate",
    "provider_api",
    "provider_webhook",
    "invoice_import",
    "manual_reconciliation",
}
GENERATED_VIDEO_STATUSES = {
    "generated",
    "completed",
    "video_generated",
    "video_approved",
    "approved",
    "provider_succeeded",
    "succeeded",
    "success",
    "done",
}
APPROVED_VIDEO_STATUSES = {"video_approved", "approved"}
PASS_STATUSES = {"pass", "passed", "approved", "ok"}
UNSAFE_PROVIDER_MARKERS = {
    "mock",
    "stub",
    "fake",
    "test",
    "sandbox",
    "demo",
    "dummy",
    "fixture",
    "placeholder",
    "simulation",
    "simulated",
    "synthetic",
}
SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
SAFE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_LEDGER_LOCK = RLock()


class GenerationCostLedgerService:
    """Append-only cost accounting for real video-provider jobs.

    This service records accounting facts only. It never calls a provider,
    initiates a charge, sends money, or changes a payout/billing record.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        organization_id: int,
        video_job_id: int,
        amount_minor: int,
        currency: str,
        entry_kind: str,
        status: str,
        source: str,
        idempotency_key: str,
        provider_job_id: str | None = None,
        external_reference: str | None = None,
        recorded_by_user_profile_id: int | None = None,
        occurred_at: datetime | None = None,
        supersedes_entry_id: int | None = None,
    ) -> GenerationCostRecordResult:
        with _LEDGER_LOCK:
            return self._record_locked(
                organization_id=organization_id,
                video_job_id=video_job_id,
                amount_minor=amount_minor,
                currency=currency,
                entry_kind=entry_kind,
                status=status,
                source=source,
                idempotency_key=idempotency_key,
                provider_job_id=provider_job_id,
                external_reference=external_reference,
                recorded_by_user_profile_id=recorded_by_user_profile_id,
                occurred_at=occurred_at,
                supersedes_entry_id=supersedes_entry_id,
            )

    def aggregate(
        self,
        *,
        organization_id: int,
        currency: str | None = None,
    ) -> list[GenerationCostAggregate]:
        organization_id = self._positive_id(organization_id, "organization_id")
        currency = self._currency(currency) if currency is not None else None
        organization = self.db.get(models.Organization, organization_id)
        if not organization:
            raise GenerationCostOwnershipError("Organization does not exist.")

        statement = (
            select(models.GenerationCostLedgerEntry)
            .where(models.GenerationCostLedgerEntry.organization_id == organization_id)
            .order_by(models.GenerationCostLedgerEntry.id)
        )
        if currency:
            statement = statement.where(models.GenerationCostLedgerEntry.currency == currency)
        entries = list(self.db.scalars(statement).all())
        superseded_ids = {entry.supersedes_entry_id for entry in entries if entry.supersedes_entry_id is not None}
        effective = [entry for entry in entries if entry.id not in superseded_ids and entry.status != "voided"]

        video_jobs = list(
            self.db.scalars(
                select(models.VideoJob).where(models.VideoJob.organization_id == organization_id)
            ).all()
        )
        real_jobs = [job for job in video_jobs if self._is_real_provider(job.provider)]
        generated_ids = {job.id for job in real_jobs if self._is_generated(job)}
        approved_ids = self._approved_video_job_ids(real_jobs)

        recognized_by_currency: dict[str, dict[tuple[int, str], models.GenerationCostLedgerEntry]] = {}
        grouped: dict[str, list[models.GenerationCostLedgerEntry]] = {}
        for entry in effective:
            grouped.setdefault(entry.currency, []).append(entry)

        for code, rows in grouped.items():
            self._assert_unambiguous_scopes(rows)
            units: dict[tuple[int, str], list[models.GenerationCostLedgerEntry]] = {}
            for entry in rows:
                units.setdefault((entry.video_job_id, entry.cost_unit_key), []).append(entry)
            recognized: dict[tuple[int, str], models.GenerationCostLedgerEntry] = {}
            for unit, unit_rows in units.items():
                confirmed_actual = next(
                    (
                        row
                        for row in unit_rows
                        if row.entry_kind == "actual" and row.status == "confirmed"
                    ),
                    None,
                )
                estimate = next((row for row in unit_rows if row.entry_kind == "estimated"), None)
                if confirmed_actual or estimate:
                    recognized[unit] = confirmed_actual or estimate  # type: ignore[assignment]
            recognized_by_currency[code] = recognized

        all_priced_job_ids = {
            entry.video_job_id
            for recognized in recognized_by_currency.values()
            for entry in recognized.values()
        }
        unpriced_generated = generated_ids - all_priced_job_ids
        unpriced_approved = approved_ids - all_priced_job_ids

        results: list[GenerationCostAggregate] = []
        for code in sorted(grouped):
            rows = grouped[code]
            recognized = recognized_by_currency[code]
            recognized_rows = list(recognized.values())
            priced_ids = {entry.video_job_id for entry in recognized_rows}
            segment_generated = generated_ids & priced_ids
            segment_approved = approved_ids & priced_ids
            recognized_total = sum(entry.amount_minor for entry in recognized_rows)
            results.append(
                GenerationCostAggregate(
                    organization_id=organization_id,
                    currency=code,
                    effective_entry_count=len(rows),
                    estimated_cost_minor=sum(
                        entry.amount_minor for entry in rows if entry.entry_kind == "estimated"
                    ),
                    confirmed_actual_cost_minor=sum(
                        entry.amount_minor
                        for entry in rows
                        if entry.entry_kind == "actual" and entry.status == "confirmed"
                    ),
                    pending_actual_cost_minor=sum(
                        entry.amount_minor
                        for entry in rows
                        if entry.entry_kind == "actual" and entry.status == "pending"
                    ),
                    recognized_cost_minor=recognized_total,
                    priced_video_count=len(priced_ids),
                    generated_video_count=len(segment_generated),
                    approved_video_count=len(segment_approved),
                    organization_generated_video_count=len(generated_ids),
                    organization_approved_video_count=len(approved_ids),
                    unpriced_generated_video_count=len(unpriced_generated),
                    unpriced_approved_video_count=len(unpriced_approved),
                    cost_per_generated_video_minor=self._average(
                        recognized_total,
                        len(segment_generated),
                    ),
                    cost_per_approved_video_minor=self._average(
                        recognized_total,
                        len(segment_approved),
                    ),
                )
            )
        return results

    def _record_locked(
        self,
        *,
        organization_id: int,
        video_job_id: int,
        amount_minor: int,
        currency: str,
        entry_kind: str,
        status: str,
        source: str,
        idempotency_key: str,
        provider_job_id: str | None,
        external_reference: str | None,
        recorded_by_user_profile_id: int | None,
        occurred_at: datetime | None,
        supersedes_entry_id: int | None,
    ) -> GenerationCostRecordResult:
        occurred_at_was_supplied = occurred_at is not None
        organization_id = self._positive_id(organization_id, "organization_id")
        video_job_id = self._positive_id(video_job_id, "video_job_id")
        amount_minor = self._amount_minor(amount_minor)
        currency = self._currency(currency)
        entry_kind = str(entry_kind or "").strip().lower()
        status = str(status or "").strip().lower()
        source = str(source or "").strip().lower()
        idempotency_key = self._safe_key(idempotency_key, "idempotency_key")
        provider_job_id = str(provider_job_id or "").strip() or None
        external_reference = str(external_reference or "").strip() or None
        occurred_at = self._occurred_at(occurred_at)
        supersedes_entry_id = (
            self._positive_id(supersedes_entry_id, "supersedes_entry_id")
            if supersedes_entry_id is not None
            else None
        )

        if entry_kind not in ENTRY_KINDS:
            raise GenerationCostValidationError("entry_kind must be estimated or actual.")
        if status not in ENTRY_STATUSES:
            raise GenerationCostValidationError("status must be pending, confirmed, or voided.")
        if source not in COST_SOURCES:
            raise GenerationCostValidationError("source is not supported.")
        if source == "internal_estimate" and entry_kind != "estimated":
            raise GenerationCostValidationError("internal_estimate can record estimates only.")
        if status == "voided" and (supersedes_entry_id is None or amount_minor != 0):
            raise GenerationCostValidationError("A void record must supersede one entry and have zero amount.")
        if provider_job_id and len(provider_job_id) > 160:
            raise GenerationCostValidationError("provider_job_id is too long.")
        if external_reference and not SAFE_REFERENCE_RE.fullmatch(external_reference):
            raise GenerationCostValidationError("external_reference has an invalid format.")

        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job or video_job.organization_id != organization_id:
            raise GenerationCostOwnershipError("Video job is not owned by this organization.")
        if not self._is_real_provider(video_job.provider):
            raise GenerationCostValidationError("Mock, test, or placeholder generation cannot create cost entries.")
        if provider_job_id and not self._provider_job_belongs_to_video_job(video_job, provider_job_id):
            raise GenerationCostOwnershipError("Provider job is not explicitly linked to this video job.")
        if provider_job_id and self._looks_synthetic_reference(provider_job_id):
            raise GenerationCostValidationError("Synthetic provider job identifiers cannot create cost entries.")

        if recorded_by_user_profile_id is not None:
            recorded_by_user_profile_id = self._positive_id(
                recorded_by_user_profile_id,
                "recorded_by_user_profile_id",
            )
            self._require_active_member(organization_id, recorded_by_user_profile_id)
        elif source == "manual_reconciliation":
            raise GenerationCostValidationError("manual_reconciliation requires an organization member actor.")

        cost_scope = "provider_job" if provider_job_id else "video_job"
        cost_unit_key = f"provider:{provider_job_id}" if provider_job_id else f"video:{video_job_id}"
        provider = str(video_job.provider).strip().lower()
        request_values = {
            "organization_id": organization_id,
            "video_job_id": video_job_id,
            "provider_job_id": provider_job_id,
            "provider": provider,
            "cost_scope": cost_scope,
            "cost_unit_key": cost_unit_key,
            "amount_minor": amount_minor,
            "currency": currency,
            "entry_kind": entry_kind,
            "status": status,
            "source": source,
            "external_reference": external_reference,
            "recorded_by_user_profile_id": recorded_by_user_profile_id,
            "supersedes_entry_id": supersedes_entry_id,
        }
        if occurred_at_was_supplied:
            request_values["occurred_at"] = occurred_at

        replay = self.db.scalar(
            select(models.GenerationCostLedgerEntry).where(
                models.GenerationCostLedgerEntry.idempotency_key == idempotency_key
            )
        )
        if replay:
            if self._matches_request(replay, **request_values):
                return GenerationCostRecordResult(entry=replay, created=False)
            raise GenerationCostConflictError("Idempotency key was already used for another cost fact.")

        effective = self._effective_entries(
            organization_id=organization_id,
            video_job_id=video_job_id,
            currency=currency,
        )
        nonvoid_scopes = {entry.cost_scope for entry in effective if entry.status != "voided"}
        if nonvoid_scopes and cost_scope not in nonvoid_scopes:
            raise GenerationCostConflictError(
                "Provider-job and video-job cost scopes cannot be mixed for one video and currency."
            )

        unit_entries = [
            entry
            for entry in effective
            if entry.entry_kind == entry_kind and entry.cost_unit_key == cost_unit_key
        ]
        revision = 1
        if supersedes_entry_id is None:
            if unit_entries:
                raise GenerationCostConflictError(
                    "An active cost fact already exists; append a correction with supersedes_entry_id."
                )
        else:
            predecessor = self.db.get(models.GenerationCostLedgerEntry, supersedes_entry_id)
            if not predecessor or predecessor not in unit_entries:
                raise GenerationCostConflictError(
                    "supersedes_entry_id must reference the active fact for the same owned cost unit."
                )
            revision = predecessor.revision + 1

        entry = models.GenerationCostLedgerEntry(
            organization_id=organization_id,
            video_job_id=video_job_id,
            provider_job_id=provider_job_id,
            provider=provider,
            cost_scope=cost_scope,
            cost_unit_key=cost_unit_key,
            revision=revision,
            amount_minor=amount_minor,
            currency=currency,
            entry_kind=entry_kind,
            status=status,
            source=source,
            external_reference=external_reference,
            idempotency_key=idempotency_key,
            supersedes_entry_id=supersedes_entry_id,
            recorded_by_user_profile_id=recorded_by_user_profile_id,
            occurred_at=occurred_at,
        )
        self.db.add(entry)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            concurrent = self.db.scalar(
                select(models.GenerationCostLedgerEntry).where(
                    models.GenerationCostLedgerEntry.idempotency_key == idempotency_key
                )
            )
            if concurrent and self._matches_request(concurrent, **request_values):
                return GenerationCostRecordResult(entry=concurrent, created=False)
            raise GenerationCostConflictError("Generation cost history conflicts with an existing fact.") from exc
        self.db.refresh(entry)
        return GenerationCostRecordResult(entry=entry, created=True)

    def _effective_entries(
        self,
        *,
        organization_id: int,
        video_job_id: int,
        currency: str,
    ) -> list[models.GenerationCostLedgerEntry]:
        entries = list(
            self.db.scalars(
                select(models.GenerationCostLedgerEntry)
                .where(
                    models.GenerationCostLedgerEntry.organization_id == organization_id,
                    models.GenerationCostLedgerEntry.video_job_id == video_job_id,
                    models.GenerationCostLedgerEntry.currency == currency,
                )
                .order_by(models.GenerationCostLedgerEntry.id)
            ).all()
        )
        superseded_ids = {entry.supersedes_entry_id for entry in entries if entry.supersedes_entry_id is not None}
        return [entry for entry in entries if entry.id not in superseded_ids]

    def _provider_job_belongs_to_video_job(self, video_job: models.VideoJob, provider_job_id: str) -> bool:
        clip_id = self.db.scalar(
            select(models.VideoClip.id).where(
                models.VideoClip.video_job_id == video_job.id,
                models.VideoClip.provider_job_id == provider_job_id,
            )
        )
        if clip_id:
            return True
        if video_job.source_product_ugc_draft_id:
            draft_provider_job_id = self.db.scalar(
                select(models.ProductUGCRecipeDraft.provider_task_id).where(
                    models.ProductUGCRecipeDraft.id == video_job.source_product_ugc_draft_id
                )
            )
            return str(draft_provider_job_id or "") == provider_job_id
        return False

    def _require_active_member(self, organization_id: int, user_profile_id: int) -> None:
        profile = self.db.get(models.UserProfile, user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        if not profile or not profile.is_active or profile.status != "active" or not membership:
            raise GenerationCostOwnershipError("Actor is not an active member of this organization.")

    def _approved_video_job_ids(self, real_jobs: list[models.VideoJob]) -> set[int]:
        candidate_ids = {
            job.id
            for job in real_jobs
            if self._is_generated(job) and str(job.status or "").strip().lower() in APPROVED_VIDEO_STATUSES
        }
        if not candidate_ids:
            return set()
        acceptances = list(
            self.db.scalars(
                select(models.VideoOutputAcceptance)
                .where(models.VideoOutputAcceptance.video_job_id.in_(candidate_ids))
                .order_by(models.VideoOutputAcceptance.video_job_id, models.VideoOutputAcceptance.id.desc())
            ).all()
        )
        latest: dict[int, models.VideoOutputAcceptance] = {}
        for acceptance in acceptances:
            latest.setdefault(acceptance.video_job_id, acceptance)
        return {
            job_id
            for job_id, acceptance in latest.items()
            if self._acceptance_is_approved(acceptance)
        }

    @staticmethod
    def _acceptance_is_approved(acceptance: models.VideoOutputAcceptance) -> bool:
        dimensions = (
            acceptance.product_identity_status,
            acceptance.packaging_status,
            acceptance.geometry_status,
            acceptance.blogger_authenticity_status,
            acceptance.scene_match_status,
            acceptance.proof_moment_status,
            acceptance.cta_status,
        )
        return (
            acceptance.status == "approved"
            and acceptance.publishing_readiness == "ready"
            and not (acceptance.blockers_json or [])
            and bool(str(acceptance.reviewer_notes or "").strip())
            and all(str(value or "").strip().lower() in PASS_STATUSES for value in dimensions)
        )

    @staticmethod
    def _assert_unambiguous_scopes(entries: list[models.GenerationCostLedgerEntry]) -> None:
        scopes_by_video: dict[int, set[str]] = {}
        for entry in entries:
            scopes_by_video.setdefault(entry.video_job_id, set()).add(entry.cost_scope)
        if any(len(scopes) > 1 for scopes in scopes_by_video.values()):
            raise GenerationCostConflictError(
                "Cost ledger has mixed scopes for one video; aggregate is blocked pending reconciliation."
            )

    @staticmethod
    def _is_generated(video_job: models.VideoJob) -> bool:
        status = str(video_job.status or "").strip().lower()
        output_path = str(video_job.output_video_path or "").strip().lower()
        unsafe_output = (
            not output_path
            or output_path.startswith(("mock:", "placeholder:", "synthetic:"))
            or output_path.endswith(".txt")
        )
        return status in GENERATED_VIDEO_STATUSES and not unsafe_output

    @staticmethod
    def _is_real_provider(provider: str | None) -> bool:
        normalized = str(provider or "").strip().lower()
        tokens = {token for token in re.split(r"[^a-z0-9]+", normalized) if token}
        return bool(
            normalized
            and is_real_video_provider(normalized)
            and not tokens.intersection(UNSAFE_PROVIDER_MARKERS)
        )

    @staticmethod
    def _looks_synthetic_reference(value: str) -> bool:
        normalized = str(value or "").strip().lower()
        tokens = {token for token in re.split(r"[^a-z0-9]+", normalized) if token}
        return bool(tokens.intersection(UNSAFE_PROVIDER_MARKERS))

    @staticmethod
    def _matches_request(entry: models.GenerationCostLedgerEntry, **values) -> bool:
        return all(getattr(entry, field) == value for field, value in values.items())

    @staticmethod
    def _average(total_minor: int, count: int) -> Decimal | None:
        if count <= 0:
            return None
        return (Decimal(total_minor) / Decimal(count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _positive_id(value: int, field: str) -> int:
        if isinstance(value, bool):
            raise GenerationCostValidationError(f"{field} must be a positive integer.")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise GenerationCostValidationError(f"{field} must be a positive integer.") from exc
        if normalized <= 0:
            raise GenerationCostValidationError(f"{field} must be a positive integer.")
        return normalized

    @staticmethod
    def _amount_minor(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise GenerationCostValidationError("amount_minor must be a non-negative integer.")
        return value

    @staticmethod
    def _currency(value: str) -> str:
        normalized = str(value or "").strip().upper()
        if not CURRENCY_RE.fullmatch(normalized):
            raise GenerationCostValidationError("currency must be a three-letter ISO-style code.")
        return normalized

    @staticmethod
    def _safe_key(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not SAFE_KEY_RE.fullmatch(normalized):
            raise GenerationCostValidationError(f"{field} has an invalid format.")
        return normalized

    @staticmethod
    def _occurred_at(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(UTC).replace(tzinfo=None)
        if value.tzinfo is None or value.utcoffset() is None:
            raise GenerationCostValidationError("occurred_at must include a timezone.")
        normalized = value.astimezone(UTC).replace(tzinfo=None)
        if normalized > datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5):
            raise GenerationCostValidationError("occurred_at cannot be in the future.")
        return normalized
