from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_autopilot.types import CampaignDistributionPlanResult


APPROVED_PACKAGE_STATUSES = {"approved", "ready", "scheduled", "published"}
AVAILABLE_DESTINATION_STATUSES = {"ready", "active", "draft"}


class CampaignDistributionPlanner:
    def __init__(self, db: Session):
        self.db = db

    def generate_plan(
        self,
        campaign_id: int,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> CampaignDistributionPlanResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignAutopilotDataError(f"Campaign {campaign_id} not found.")
        start = (start_date or datetime.now(UTC)).replace(tzinfo=None)
        end = (end_date or (start + timedelta(days=14))).replace(tzinfo=None)
        days = max(1, (end.date() - start.date()).days + 1)
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        packages = self._approved_packages(product_ids)
        destinations = self._available_destinations(campaign.brand)
        blockers: list[str] = []
        warnings: list[str] = []
        if len(destinations) < campaign.target_destination_count:
            blockers.append("destination_capacity_below_target")
        if len(packages) < campaign.target_video_count:
            blockers.append("not_enough_approved_packages")
        if not packages:
            blockers.append("approved_packages_required")
        if not destinations:
            blockers.append("available_destinations_required")
        destination_capacity = self._destination_capacity(destinations, days)
        total_slots = sum(destination_capacity.values())
        if total_slots < min(campaign.target_video_count, len(packages)):
            blockers.append("destination_capacity_insufficient")
        assignments = []
        scheduled_slots = 0
        if packages and destinations:
            assignments, scheduled_slots = self._schedule(
                campaign=campaign,
                packages=packages,
                destinations=destinations,
                capacity=destination_capacity,
                start=start,
                target_slots=min(campaign.target_video_count, len(packages), total_slots),
            )
        if scheduled_slots < campaign.target_video_count:
            warnings.append("distribution_plan_has_unfilled_slots")
        plan_json = {
            "campaign_id": campaign.id,
            "date_range": {"start": start.isoformat(), "end": end.isoformat()},
            "approved_package_count": len(packages),
            "available_destination_count": len(destinations),
            "target_video_count": campaign.target_video_count,
            "target_destination_count": campaign.target_destination_count,
            "assignments": assignments,
            "rules": [
                "approved packages only",
                "destination daily and weekly limits respected",
                "SKU coverage preferred through sorted package order",
            ],
        }
        record = models.CampaignDistributionPlan(
            campaign_id=campaign.id,
            status="blocked" if blockers else "planned",
            target_destination_count=campaign.target_destination_count,
            destination_ids_json=[destination.id for destination in destinations],
            publishing_package_ids_json=[package.id for package in packages],
            total_slots=total_slots,
            scheduled_slots=scheduled_slots,
            blockers_json=list(dict.fromkeys(blockers)),
            warnings_json=list(dict.fromkeys(warnings)),
            plan_json=plan_json,
        )
        self.db.add(record)
        campaign.summary_json = {
            **(campaign.summary_json or {}),
            "latest_distribution": {
                "status": record.status,
                "scheduled_slots": scheduled_slots,
                "blockers": record.blockers_json,
            },
        }
        self.db.flush()
        plan_json["plan_id"] = record.id
        record.plan_json = plan_json
        self.db.commit()
        self.db.refresh(record)
        return self._result(record)

    def latest_plan(self, campaign_id: int) -> dict[str, Any] | None:
        plan = self.db.scalar(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == campaign_id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        )
        if not plan:
            return None
        return self._result(plan).model_dump(mode="json")

    def _approved_packages(self, product_ids: list[int]) -> list[models.PublishingPackage]:
        if not product_ids:
            return []
        return self.db.scalars(
            select(models.PublishingPackage)
            .where(
                models.PublishingPackage.product_id.in_(product_ids),
                models.PublishingPackage.review_status == "approved",
                models.PublishingPackage.status.in_(APPROVED_PACKAGE_STATUSES),
            )
            .order_by(models.PublishingPackage.product_id, models.PublishingPackage.id)
        ).all()

    def _available_destinations(self, brand: str) -> list[models.PublishingDestination]:
        return self.db.scalars(
            select(models.PublishingDestination)
            .where(
                models.PublishingDestination.brand == brand,
                models.PublishingDestination.status.in_(AVAILABLE_DESTINATION_STATUSES),
            )
            .order_by(models.PublishingDestination.platform, models.PublishingDestination.id)
        ).all()

    @staticmethod
    def _destination_capacity(destinations: list[models.PublishingDestination], days: int) -> dict[int, int]:
        weeks = max(1, math.ceil(days / 7))
        return {
            destination.id: min(max(1, destination.daily_limit) * days, max(1, destination.weekly_limit) * weeks)
            for destination in destinations
        }

    def _schedule(
        self,
        *,
        campaign: models.Campaign,
        packages: list[models.PublishingPackage],
        destinations: list[models.PublishingDestination],
        capacity: dict[int, int],
        start: datetime,
        target_slots: int,
    ) -> tuple[list[dict[str, Any]], int]:
        assignments = []
        usage = {destination.id: 0 for destination in destinations}
        day_usage: dict[tuple[int, int], int] = {}
        scheduled = 0
        package_index = 0
        while scheduled < target_slots and package_index < len(packages):
            package = packages[package_index]
            destination = self._next_destination(destinations, capacity, usage)
            if not destination:
                break
            scheduled_at = self._next_time_for_destination(destination, start, day_usage, usage[destination.id])
            task = self._create_task(package, destination, scheduled_at)
            assignments.append(
                {
                    "publishing_task_id": task.id,
                    "publishing_package_id": package.id,
                    "product_id": package.product_id,
                    "sku": package.product.sku if package.product else None,
                    "destination_id": destination.id,
                    "platform": destination.platform,
                    "scheduled_at": scheduled_at.isoformat(),
                }
            )
            usage[destination.id] += 1
            day_key = (destination.id, (scheduled_at.date() - start.date()).days)
            day_usage[day_key] = day_usage.get(day_key, 0) + 1
            scheduled += 1
            package_index += 1
        return assignments, scheduled

    @staticmethod
    def _next_destination(
        destinations: list[models.PublishingDestination],
        capacity: dict[int, int],
        usage: dict[int, int],
    ) -> models.PublishingDestination | None:
        candidates = sorted(destinations, key=lambda destination: usage[destination.id])
        for destination in candidates:
            if usage[destination.id] < capacity[destination.id]:
                return destination
        return None

    @staticmethod
    def _next_time_for_destination(
        destination: models.PublishingDestination,
        start: datetime,
        day_usage: dict[tuple[int, int], int],
        destination_usage: int,
    ) -> datetime:
        day = 0
        while day_usage.get((destination.id, day), 0) >= max(1, destination.daily_limit):
            day += 1
        hour = 10 + (destination_usage % 6) * 2
        return start.replace(hour=min(hour, 20), minute=0, second=0, microsecond=0) + timedelta(days=day)

    def _create_task(
        self,
        package: models.PublishingPackage,
        destination: models.PublishingDestination,
        scheduled_at: datetime,
    ) -> models.PublishingTask:
        existing = self.db.scalar(
            select(models.PublishingTask).where(
                models.PublishingTask.publishing_package_id == package.id,
                models.PublishingTask.destination_id == destination.id,
            )
        )
        if existing:
            return existing
        task = models.PublishingTask(
            publishing_package_id=package.id,
            destination_id=destination.id,
            platform=destination.platform,
            status="scheduled",
            scheduled_at=scheduled_at,
            raw_response_json={"source": "campaign_autopilot", "approved_package_only": True},
        )
        self.db.add(task)
        self.db.flush()
        return task

    @staticmethod
    def _result(plan: models.CampaignDistributionPlan) -> CampaignDistributionPlanResult:
        return CampaignDistributionPlanResult(
            plan_id=plan.id,
            campaign_id=plan.campaign_id,
            status=plan.status,
            target_destination_count=plan.target_destination_count,
            total_slots=plan.total_slots,
            scheduled_slots=plan.scheduled_slots,
            blockers=plan.blockers_json or [],
            warnings=plan.warnings_json or [],
            plan=plan.plan_json or {},
        )
