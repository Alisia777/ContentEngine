from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_crm.errors import DestinationCRMDataError
from app.destination_crm.types import DestinationReadinessResult
from app.destination_crm.warmup_service import DestinationWarmupService


READY_TASK_STATUSES = {"draft", "scheduled", "ready", "published", "done", "manual_uploaded"}
ALLOWED_POSTING_MODES = {"manual", "api", "telegram_bot"}
API_READY_STATUSES = {"token_valid", "api_ready"}
MANUAL_READY_STATUSES = {"manual_only", "not_configured", "needs_review"}


class DestinationReadinessService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(self, destination_id: int, *, campaign_id: int | None = None) -> DestinationReadinessResult:
        destination = self._destination(destination_id)
        campaign = self._campaign(campaign_id) if campaign_id is not None else self._infer_campaign(destination)
        warmup_phase, warmup_daily, warmup_weekly = DestinationWarmupService(self.db).phase_limits(destination.id)
        used_today, used_this_week = self._usage(destination.id)
        effective_daily = min(max(0, destination.daily_limit), warmup_daily)
        effective_weekly = min(max(0, destination.weekly_limit), warmup_weekly)
        remaining_daily = max(0, effective_daily - used_today)
        remaining_weekly = max(0, effective_weekly - used_this_week)
        active = destination.status == "active"
        manual_ready = self._manual_ready(destination, active)
        api_ready = self._api_ready(destination, active)
        blockers, warnings = self._blockers(destination, active, manual_ready, api_ready, effective_daily, effective_weekly)
        if remaining_daily == 0:
            blockers.append({"blocker": "no_remaining_daily_capacity", "source": "destination_crm"})
        if remaining_weekly == 0:
            blockers.append({"blocker": "no_remaining_weekly_capacity", "source": "destination_crm"})
        next_actions = self._next_actions(destination, blockers, warnings)
        snapshot = models.DestinationReadinessSnapshot(
            destination_id=destination.id,
            campaign_id=campaign.id if campaign else None,
            status="ready" if not blockers else "blocked",
            platform=destination.platform,
            posting_mode=destination.posting_mode,
            auth_status=destination.auth_status,
            active=active,
            manual_ready=manual_ready,
            api_ready=api_ready,
            warmup_phase=warmup_phase,
            daily_limit=effective_daily,
            weekly_limit=effective_weekly,
            used_today=used_today,
            used_this_week=used_this_week,
            remaining_daily_capacity=remaining_daily,
            remaining_weekly_capacity=remaining_weekly,
            blockers_json=blockers,
            warnings_json=warnings,
            next_actions_json=next_actions,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return self._result(snapshot)

    def latest_or_refresh(self, destination_id: int, *, campaign_id: int | None = None) -> DestinationReadinessResult:
        snapshot = self.db.scalar(
            select(models.DestinationReadinessSnapshot)
            .where(models.DestinationReadinessSnapshot.destination_id == destination_id)
            .order_by(models.DestinationReadinessSnapshot.id.desc())
        )
        if not snapshot:
            return self.refresh(destination_id, campaign_id=campaign_id)
        return self._result(snapshot)

    def list_latest(self, *, campaign_id: int | None = None) -> list[DestinationReadinessResult]:
        destinations = self._destinations_for_campaign(campaign_id)
        return [self.latest_or_refresh(destination.id, campaign_id=campaign_id) for destination in destinations]

    def _destinations_for_campaign(self, campaign_id: int | None) -> list[models.PublishingDestination]:
        if campaign_id is None:
            return self.db.scalars(select(models.PublishingDestination).order_by(models.PublishingDestination.id)).all()
        campaign = self._campaign(campaign_id)
        return self.db.scalars(
            select(models.PublishingDestination)
            .where(models.PublishingDestination.brand == campaign.brand)
            .order_by(models.PublishingDestination.id)
        ).all()

    def _destination(self, destination_id: int) -> models.PublishingDestination:
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise DestinationCRMDataError(f"Destination {destination_id} not found.")
        return destination

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationCRMDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _infer_campaign(self, destination: models.PublishingDestination) -> models.Campaign | None:
        return self.db.scalar(
            select(models.Campaign).where(models.Campaign.brand == destination.brand).order_by(models.Campaign.id.desc())
        )

    def _usage(self, destination_id: int) -> tuple[int, int]:
        now = datetime.now(UTC).replace(tzinfo=None)
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_week = start_today - timedelta(days=start_today.weekday())
        tasks = self.db.scalars(
            select(models.PublishingTask)
            .where(
                models.PublishingTask.destination_id == destination_id,
                models.PublishingTask.status.in_(READY_TASK_STATUSES),
                models.PublishingTask.scheduled_at >= start_week,
            )
        ).all()
        used_today = sum(1 for task in tasks if task.scheduled_at >= start_today)
        return used_today, len(tasks)

    @staticmethod
    def _manual_ready(destination: models.PublishingDestination, active: bool) -> bool:
        if not active or destination.posting_mode not in {"manual", "telegram_bot"}:
            return False
        return bool(destination.handle or destination.url) and destination.auth_status in MANUAL_READY_STATUSES | API_READY_STATUSES

    @staticmethod
    def _api_ready(destination: models.PublishingDestination, active: bool) -> bool:
        if not active or destination.posting_mode != "api":
            return False
        return destination.auth_status in API_READY_STATUSES

    @staticmethod
    def _blockers(
        destination: models.PublishingDestination,
        active: bool,
        manual_ready: bool,
        api_ready: bool,
        daily_limit: int,
        weekly_limit: int,
    ) -> tuple[list[dict], list[dict]]:
        blockers = []
        warnings = []
        if not active:
            blockers.append({"blocker": "destination_not_active", "status": destination.status, "source": "destination_crm"})
        if destination.status in {"paused", "disabled"}:
            blockers.append({"blocker": f"destination_{destination.status}", "source": "destination_crm"})
        if destination.posting_mode not in ALLOWED_POSTING_MODES:
            blockers.append({"blocker": "posting_mode_not_allowed", "posting_mode": destination.posting_mode})
        if destination.posting_mode == "manual" and not manual_ready:
            blockers.append({"blocker": "manual_destination_needs_handle_or_url", "source": "destination_crm"})
        if destination.posting_mode == "telegram_bot" and not manual_ready:
            blockers.append({"blocker": "telegram_destination_needs_handle_or_url", "source": "destination_crm"})
        if destination.posting_mode == "api" and not api_ready:
            blockers.append({"blocker": "api_destination_requires_token_valid", "auth_status": destination.auth_status})
        if daily_limit <= 0:
            blockers.append({"blocker": "daily_capacity_zero", "source": "destination_crm"})
        if weekly_limit <= 0:
            blockers.append({"blocker": "weekly_capacity_zero", "source": "destination_crm"})
        if destination.posting_mode == "manual":
            warnings.append({"warning": "manual_upload_requires_operator_final_url", "source": "destination_crm"})
        return blockers, warnings

    @staticmethod
    def _next_actions(destination: models.PublishingDestination, blockers: list[dict], warnings: list[dict]) -> list[dict]:
        actions = []
        for blocker in blockers:
            name = blocker.get("blocker")
            if name == "api_destination_requires_token_valid":
                actions.append({"action": "connect_official_api_token", "reason": name, "requires_human": True})
            elif name in {"manual_destination_needs_handle_or_url", "telegram_destination_needs_handle_or_url"}:
                actions.append({"action": "complete_destination_profile", "reason": name, "requires_human": True})
            elif name in {"daily_capacity_zero", "weekly_capacity_zero", "no_remaining_daily_capacity", "no_remaining_weekly_capacity"}:
                actions.append({"action": "review_warmup_or_limits", "reason": name, "requires_human": True})
            elif name == "destination_not_active":
                actions.append({"action": "activate_or_replace_destination", "reason": destination.status, "requires_human": True})
        if not blockers and warnings:
            actions.append({"action": "ready_for_manual_assisted_upload", "reason": "destination_ready_with_warnings", "requires_human": True})
        return actions

    @staticmethod
    def _result(snapshot: models.DestinationReadinessSnapshot) -> DestinationReadinessResult:
        return DestinationReadinessResult(
            snapshot_id=snapshot.id,
            destination_id=snapshot.destination_id,
            campaign_id=snapshot.campaign_id,
            status=snapshot.status,
            platform=snapshot.platform,
            posting_mode=snapshot.posting_mode,
            auth_status=snapshot.auth_status,
            active=snapshot.active,
            manual_ready=snapshot.manual_ready,
            api_ready=snapshot.api_ready,
            warmup_phase=snapshot.warmup_phase,
            daily_limit=snapshot.daily_limit,
            weekly_limit=snapshot.weekly_limit,
            used_today=snapshot.used_today,
            used_this_week=snapshot.used_this_week,
            remaining_daily_capacity=snapshot.remaining_daily_capacity,
            remaining_weekly_capacity=snapshot.remaining_weekly_capacity,
            blockers=snapshot.blockers_json or [],
            warnings=snapshot.warnings_json or [],
            next_actions=snapshot.next_actions_json or [],
            generated_at=snapshot.created_at,
        )
