from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_autopilot.types import TargetAllocationResult


@dataclass
class Allocation:
    campaign_product: models.CampaignProduct
    target_video_count: int
    target_prompt_count: int
    target_real_smoke_count: int
    reasons: list[str]


class TargetAllocator:
    def __init__(self, db: Session):
        self.db = db

    def allocate(self, campaign_id: int) -> TargetAllocationResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignAutopilotDataError(f"Campaign {campaign_id} not found.")
        products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id).order_by(models.CampaignProduct.id)
        ).all()
        if not products:
            raise CampaignAutopilotDataError("Campaign has no CampaignProduct rows.")
        allocations = self._weighted(campaign, products)
        for allocation in allocations:
            item = allocation.campaign_product
            item.target_video_count = allocation.target_video_count
            item.target_prompt_count = allocation.target_prompt_count
            item.target_real_smoke_count = allocation.target_real_smoke_count
            item.next_actions_json = [{"action": "prepare_content", "reason": "Target allocated."}]
            item.status = "planned"
        campaign.strategy_json = {
            **(campaign.strategy_json or {}),
            "target_allocator": {
                "default_sku_count": 40,
                "target_video_range": "300-350",
                "target_destination_count": campaign.target_destination_count,
                "rules": [
                    "7-9 variants per SKU by default",
                    "higher priority SKU receive more targets",
                    "low stock SKU receive fewer demand-generation targets",
                    "missing references still allow prompt-only targets",
                ],
            },
        }
        self.db.commit()
        return TargetAllocationResult(
            campaign_id=campaign.id,
            total_products=len(products),
            total_target_videos=sum(item.target_video_count for item in products),
            allocations=[
                {
                    "campaign_product_id": allocation.campaign_product.id,
                    "sku": allocation.campaign_product.sku,
                    "target_video_count": allocation.target_video_count,
                    "target_prompt_count": allocation.target_prompt_count,
                    "target_real_smoke_count": allocation.target_real_smoke_count,
                    "reasons": allocation.reasons,
                }
                for allocation in allocations
            ],
        )

    def _weighted(self, campaign: models.Campaign, products: list[models.CampaignProduct]) -> list[Allocation]:
        target_total = campaign.target_video_count
        weights = []
        raw: list[tuple[models.CampaignProduct, float, list[str]]] = []
        for item in products:
            product = self.db.get(models.Product, item.product_id)
            attrs = product.attributes_json if product else {}
            priority = int(attrs.get("matrix_priority") or 1)
            stock_qty = attrs.get("stock_qty")
            photo_count = len(product.images_json or []) if product else 0
            weight = 1.0 + max(0, min(priority, 5) - 1) * 0.25
            reasons = [f"priority:{priority}"]
            if stock_qty is not None and stock_qty < 20:
                weight *= 0.55
                reasons.append("low_stock_reduced")
            if photo_count == 0:
                reasons.append("missing_reference_prompt_only")
            weights.append(weight)
            raw.append((item, weight, reasons))
        total_weight = sum(weights) or 1
        allocations: list[Allocation] = []
        fractional: list[tuple[int, float]] = []
        for index, (item, weight, reasons) in enumerate(raw):
            exact = target_total * weight / total_weight
            count = max(1, math.floor(exact))
            allocations.append(
                Allocation(
                    campaign_product=item,
                    target_video_count=count,
                    target_prompt_count=max(1, count),
                    target_real_smoke_count=0,
                    reasons=reasons,
                )
            )
            fractional.append((index, exact - count))
        current = sum(allocation.target_video_count for allocation in allocations)
        while current < target_total:
            index = max(fractional, key=lambda item: item[1])[0]
            allocations[index].target_video_count += 1
            allocations[index].target_prompt_count += 1
            current += 1
            fractional[index] = (index, 0)
        while current > target_total:
            candidates = [index for index, allocation in enumerate(allocations) if allocation.target_video_count > 1]
            if not candidates:
                break
            index = candidates[-1]
            allocations[index].target_video_count -= 1
            allocations[index].target_prompt_count = max(1, allocations[index].target_prompt_count - 1)
            current -= 1
        for allocation in allocations:
            product = self.db.get(models.Product, allocation.campaign_product.product_id)
            has_reference = bool(product and product.images_json)
            allocation.target_real_smoke_count = 1 if has_reference and allocation.target_video_count > 0 else 0
        return allocations
