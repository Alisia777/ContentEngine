from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models


class BlockerService:
    def __init__(self, db: Session):
        self.db = db

    def campaign_blockers(self, campaign: models.Campaign, campaign_state: dict[str, Any]) -> list[dict[str, Any]]:
        blockers = Counter()
        for item in campaign_state.get("blockers_by_type", []):
            blocker = item.get("blocker")
            count = int(item.get("count") or 0)
            if blocker:
                blockers[blocker] += count
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        if campaign_state.get("missing_references", 0):
            blockers["missing_references"] += int(campaign_state["missing_references"])
        if campaign_state.get("missing_geometry_lock", 0):
            blockers["missing_geometry_lock"] += int(campaign_state["missing_geometry_lock"])
        if campaign_state.get("needs_human_review", 0):
            blockers["human_review_required"] += int(campaign_state["needs_human_review"])
        if product_ids:
            approved_packages = self._approved_packages(product_ids)
            if not approved_packages:
                blockers["no_approved_video"] += len(product_ids)
            destinations = self._available_destinations(campaign.brand)
            if not destinations:
                blockers["no_destinations"] += 1
            if not self._has_stats(product_ids):
                blockers["no_stats"] += 1
        latest_plan = self._latest_plan(campaign.id)
        if latest_plan and latest_plan.blockers_json:
            for blocker in latest_plan.blockers_json:
                blockers[blocker] += 1
        elif product_ids:
            blockers["no_distribution_plan"] += 1
        return [{"blocker": blocker, "count": count} for blocker, count in blockers.most_common()]

    def publishing_package_ready_count(self, product_ids: list[int]) -> int:
        return len(self._approved_packages(product_ids))

    def distribution_task_ready_count(self, campaign_id: int) -> int:
        latest_plan = self._latest_plan(campaign_id)
        if not latest_plan:
            return 0
        destination_ids = latest_plan.destination_ids_json or []
        package_ids = latest_plan.publishing_package_ids_json or []
        if not destination_ids or not package_ids:
            return 0
        return self.db.scalar(
            select(func.count())
            .select_from(models.PublishingTask)
            .where(
                models.PublishingTask.destination_id.in_(destination_ids),
                models.PublishingTask.publishing_package_id.in_(package_ids),
                models.PublishingTask.status.in_(["planned", "scheduled", "draft"]),
            )
        ) or 0

    def _approved_packages(self, product_ids: list[int]) -> list[models.PublishingPackage]:
        if not product_ids:
            return []
        return self.db.scalars(
            select(models.PublishingPackage)
            .where(
                models.PublishingPackage.product_id.in_(product_ids),
                models.PublishingPackage.review_status == "approved",
                models.PublishingPackage.status.in_(["approved", "ready", "scheduled", "published"]),
            )
            .order_by(models.PublishingPackage.id)
        ).all()

    def _available_destinations(self, brand: str) -> list[models.PublishingDestination]:
        return self.db.scalars(
            select(models.PublishingDestination)
            .where(
                models.PublishingDestination.brand == brand,
                models.PublishingDestination.status.in_(["ready", "active", "draft"]),
            )
            .order_by(models.PublishingDestination.id)
        ).all()

    def _has_stats(self, product_ids: list[int]) -> bool:
        if not product_ids:
            return False
        metric = self.db.scalar(
            select(models.ContentPerformanceMetric)
            .where(models.ContentPerformanceMetric.product_id.in_(product_ids))
            .order_by(models.ContentPerformanceMetric.id.desc())
        )
        return metric is not None

    def _latest_plan(self, campaign_id: int) -> models.CampaignDistributionPlan | None:
        return self.db.scalar(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == campaign_id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        )
