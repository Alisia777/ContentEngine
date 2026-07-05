from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.errors import CampaignAutopilotDataError


class CampaignPerformanceService:
    def __init__(self, db: Session):
        self.db = db

    def summarize(self, campaign_id: int) -> dict:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignAutopilotDataError(f"Campaign {campaign_id} not found.")
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        products = self.db.scalars(select(models.Product).where(models.Product.id.in_(product_ids)) if product_ids else select(models.Product).where(False)).all()
        skus = [product.sku for product in products]
        metrics = self.db.scalars(
            select(models.ContentPerformanceMetric)
            .where(models.ContentPerformanceMetric.sku.in_(skus) if skus else False)
            .order_by(models.ContentPerformanceMetric.views.desc().nullslast())
        ).all()
        runs = self.db.scalars(
            select(models.ContentRun)
            .where(models.ContentRun.product_id.in_(product_ids) if product_ids else False)
            .order_by(models.ContentRun.id)
        ).all()
        best_metric = metrics[0] if metrics else None
        best_run = max(runs, key=lambda run: (run.run_json or {}).get("selected_variant_score", {}).get("total", 0), default=None)
        recommendations = []
        if best_metric:
            recommendations.append({"action": "scale", "reason": f"{best_metric.sku} has the strongest imported view signal."})
        if any(run.status == "blocked" for run in runs):
            recommendations.append({"action": "resolve_blockers", "reason": "Some campaign runs are blocked."})
        if any(run.prompt_pack_id and not run.video_job_id for run in runs):
            recommendations.append({"action": "human_review", "reason": "Prompt-ready runs need video output and approval before distribution."})
        return {
            "metric_count": len(metrics),
            "content_run_count": len(runs),
            "best_sku": best_metric.sku if best_metric else None,
            "best_hook": (best_run.run_json or {}).get("selected_hook") if best_run else None,
            "best_destination": None,
            "recommendations": recommendations,
        }
