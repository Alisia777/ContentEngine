from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.content_factory.types import ContentFactoryDashboard


class ContentPerformanceService:
    def __init__(self, db: Session):
        self.db = db

    def dashboard(self) -> ContentFactoryDashboard:
        runs = self.db.scalars(select(models.ContentRun).order_by(models.ContentRun.created_at.desc())).all()
        metrics = self.db.scalars(select(models.ContentPerformanceMetric)).all()
        blocker_counts = Counter()
        for run in runs:
            for blocker in run.blockers_json or []:
                blocker_counts[blocker] += 1
        return ContentFactoryDashboard(
            total_runs=len(runs),
            prepared_runs=sum(1 for run in runs if run.status in {"prepared", "prompt_ready", "ready_for_real_smoke"}),
            blocked_runs=sum(1 for run in runs if run.blockers_json),
            prompt_ready_runs=sum(1 for run in runs if run.prompt_pack_id),
            real_smoke_ready_runs=sum(1 for run in runs if any(action.get("action") == "run_real_smoke" for action in run.next_actions_json or [])),
            human_review_queue=self.db.scalar(
                select(func.count()).select_from(models.AIContentReview).where(models.AIContentReview.human_review_required.is_(True))
            )
            or 0,
            needs_regeneration_runs=sum(
                1
                for run in runs
                if run.status == "needs_regeneration"
                or any(action.get("action") == "request_geometry_regeneration" for action in run.next_actions_json or [])
            ),
            geometry_mismatch_blockers=sum(
                1 for run in runs if "product_geometry_mismatch" in (run.blockers_json or [])
            ),
            publishing_ready_runs=sum(
                1
                for run in runs
                if ((run.run_json or {}).get("publishing_readiness") or {}).get("status") == "ready"
            ),
            performance_metric_count=len(metrics),
            top_blockers=[{"blocker": key, "count": count} for key, count in blocker_counts.most_common(8)],
            recent_runs=[self._run_summary(run) for run in runs[:10]],
            performance_summary=self._performance_summary(metrics),
        )

    @staticmethod
    def _run_summary(run: models.ContentRun) -> dict:
        return {
            "id": run.id,
            "product_id": run.product_id,
            "sku": run.product.sku if run.product else None,
            "platform": run.platform,
            "status": run.status,
            "selected_variant_id": run.selected_variant_id,
            "prompt_pack_id": run.prompt_pack_id,
            "video_job_id": run.video_job_id,
            "reference_readiness": ((run.run_json or {}).get("reference_readiness") or {}).get("status"),
            "geometry_readiness": ((run.run_json or {}).get("geometry_readiness") or {}).get("status"),
            "publishing_readiness": ((run.run_json or {}).get("publishing_readiness") or {}).get("status"),
            "blockers": run.blockers_json or [],
            "next_actions": run.next_actions_json or [],
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }

    @staticmethod
    def _performance_summary(metrics: list[models.ContentPerformanceMetric]) -> dict:
        views = sum(metric.views or 0 for metric in metrics)
        clicks = sum(metric.clicks or 0 for metric in metrics)
        orders = sum(metric.orders or 0 for metric in metrics)
        revenue = round(sum(metric.revenue or 0 for metric in metrics), 2)
        spend = round(sum(metric.spend or 0 for metric in metrics), 2)
        return {
            "views": views,
            "clicks": clicks,
            "orders": orders,
            "revenue": revenue,
            "spend": spend,
            "ctr": round(clicks / views, 4) if views else 0,
            "conversion_rate": round(orders / clicks, 4) if clicks else 0,
            "roas": round(revenue / spend, 2) if spend else None,
        }
