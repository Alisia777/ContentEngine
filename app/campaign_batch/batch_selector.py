from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_batch.errors import CampaignBatchDataError
from app.campaign_batch.safety_gates import BatchSafetyGate
from app.campaign_batch.types import BatchActionPreview, BatchSelectionResult
from app.campaign_execution import ActionQueueService


class BatchSelector:
    def __init__(self, db: Session):
        self.db = db
        self.gate = BatchSafetyGate()

    def select_safe_actions(self, campaign_id: int, action_type: str | None = None) -> BatchSelectionResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignBatchDataError(f"Campaign {campaign_id} not found.")
        ActionQueueService(self.db).refresh_actions(campaign_id)
        query = (
            select(models.CampaignActionQueueItem)
            .where(
                models.CampaignActionQueueItem.campaign_id == campaign_id,
                models.CampaignActionQueueItem.status == "open",
            )
            .order_by(models.CampaignActionQueueItem.priority, models.CampaignActionQueueItem.id)
        )
        if action_type:
            query = query.where(models.CampaignActionQueueItem.action_type == action_type)
        selected: list[BatchActionPreview] = []
        skipped: list[BatchActionPreview] = []
        for action in self.db.scalars(query).all():
            allowed, reason = self.gate.assess(action)
            preview = self._preview(action, skip_reason=reason)
            if allowed:
                selected.append(preview)
            else:
                skipped.append(preview)
        return BatchSelectionResult(
            campaign_id=campaign_id,
            action_type=action_type,
            selected_actions=selected,
            skipped_actions=skipped,
            safe_action_count=len(selected),
            skipped_count=len(skipped),
        )

    @staticmethod
    def _preview(action: models.CampaignActionQueueItem, *, skip_reason: str | None) -> BatchActionPreview:
        return BatchActionPreview(
            action_id=action.id,
            campaign_id=action.campaign_id,
            product_id=action.product_id,
            sku=action.sku,
            content_run_id=action.content_run_id,
            action_type=action.action_type,
            status=action.status,
            safe_to_execute=action.safe_to_execute,
            reason=action.reason,
            blockers=action.blockers_json or [],
            skip_reason=skip_reason,
        )
