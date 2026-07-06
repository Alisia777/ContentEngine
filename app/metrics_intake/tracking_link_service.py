from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.errors import MetricsIntakeDataError


class TrackingLinkService:
    def __init__(self, db: Session, *, public_base_url: str = "https://our-domain.com"):
        self.db = db
        self.public_base_url = public_base_url.rstrip("/")

    def create_for_task(
        self,
        publishing_task_id: int,
        *,
        target_url: str | None = None,
        campaign_id: int | None = None,
        participant_id: int | None = None,
        slug: str | None = None,
    ) -> models.TrackingLink:
        task = self.db.get(models.PublishingTask, publishing_task_id)
        if not task:
            raise MetricsIntakeDataError(f"Publishing task {publishing_task_id} not found.")
        target = (target_url or task.final_url or "").strip()
        if not target:
            raise MetricsIntakeDataError("Tracking link target_url is required when publishing task has no final_url.")
        metadata = self._task_metadata(task, campaign_id=campaign_id, participant_id=participant_id)
        link = models.TrackingLink(
            slug=slug or self._unique_slug(task),
            target_url=target,
            campaign_id=metadata["campaign_id"],
            publishing_task_id=task.id,
            destination_id=task.destination_id,
            product_id=metadata["product_id"],
            sku=metadata["sku"],
            creative_variant_id=metadata["creative_variant_id"],
            participant_id=metadata["participant_id"],
            status="active",
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def create_for_campaign(self, campaign_id: int) -> list[models.TrackingLink]:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise MetricsIntakeDataError(f"Campaign {campaign_id} not found.")
        product_ids = set(campaign.product_ids_json or [])
        tasks = self.db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.id)).all()
        created: list[models.TrackingLink] = []
        for task in tasks:
            package = task.publishing_package
            if product_ids and (not package or package.product_id not in product_ids):
                continue
            existing = self.db.scalar(select(models.TrackingLink).where(models.TrackingLink.publishing_task_id == task.id))
            if existing:
                created.append(existing)
                continue
            if not task.final_url:
                continue
            created.append(self.create_for_task(task.id, campaign_id=campaign_id))
        return created

    def list(self, *, campaign_id: int | None = None, publishing_task_id: int | None = None) -> list[models.TrackingLink]:
        query = select(models.TrackingLink).order_by(models.TrackingLink.id.desc())
        if campaign_id:
            query = query.where(models.TrackingLink.campaign_id == campaign_id)
        if publishing_task_id:
            query = query.where(models.TrackingLink.publishing_task_id == publishing_task_id)
        return self.db.scalars(query).all()

    def redirect_url(self, link: models.TrackingLink) -> str:
        return f"{self.public_base_url}/r/{link.slug}"

    def get_by_slug(self, slug: str) -> models.TrackingLink:
        link = self.db.scalar(select(models.TrackingLink).where(models.TrackingLink.slug == slug))
        if not link:
            raise MetricsIntakeDataError(f"Tracking link {slug} not found.")
        if link.status != "active":
            raise MetricsIntakeDataError(f"Tracking link {slug} is not active.")
        return link

    def _task_metadata(
        self,
        task: models.PublishingTask,
        *,
        campaign_id: int | None,
        participant_id: int | None,
    ) -> dict[str, Any]:
        package = task.publishing_package
        product = package.product if package else None
        assignment = self.db.scalar(
            select(models.ParticipantAssignment)
            .where(models.ParticipantAssignment.publishing_task_id == task.id)
            .order_by(models.ParticipantAssignment.id.desc())
        )
        inferred_campaign_id = campaign_id or (assignment.campaign_id if assignment else None)
        if not inferred_campaign_id and product:
            campaign = self.db.scalar(
                select(models.Campaign)
                .where(models.Campaign.product_ids_json.contains([product.id]))
                .order_by(models.Campaign.id.desc())
            )
            inferred_campaign_id = campaign.id if campaign else None
        return {
            "campaign_id": inferred_campaign_id,
            "product_id": product.id if product else None,
            "sku": product.sku if product else None,
            "creative_variant_id": package.creative_variant_id if package else None,
            "participant_id": participant_id or (assignment.participant_id if assignment else None),
        }

    def _unique_slug(self, task: models.PublishingTask) -> str:
        prefix = f"pt{task.id}"
        for _ in range(12):
            slug = f"{prefix}-{secrets.token_urlsafe(4).lower().replace('_', '').replace('-', '')[:6]}"
            existing = self.db.scalar(select(models.TrackingLink).where(models.TrackingLink.slug == slug))
            if not existing:
                return slug
        raise MetricsIntakeDataError("Could not generate a unique tracking slug.")
