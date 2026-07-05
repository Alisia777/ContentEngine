from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.content_factory.readiness import control_loop_readiness
from app.content_factory.types import ContentNextAction


RECOMMENDATION_ACTIONS = [
    "add_product_reference",
    "add_geometry_lock",
    "run_prompt_only",
    "run_real_smoke",
    "request_regeneration",
    "request_geometry_regeneration",
    "approve_for_publishing",
    "create_publishing_package",
    "import_performance_stats",
    "scale_variant",
    "pause_variant",
]


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db

    def recommend(self, content_run: models.ContentRun) -> list[ContentNextAction]:
        actions: list[ContentNextAction] = []
        run_json = content_run.run_json or {}
        readiness = run_json.get("reference_readiness") or {}
        control_readiness = control_loop_readiness(self.db, content_run)
        geometry = control_readiness["geometry_readiness"]
        blockers = set(content_run.blockers_json or [])
        latest_review = self._latest_review(content_run.id)
        latest_metric = self._latest_metric(content_run)

        if readiness.get("status") != "ready" or any("reference:" in item for item in blockers):
            actions.append(
                ContentNextAction(
                    action="add_product_reference",
                    priority=10,
                    reason="Approved primary product reference is required before real provider smoke.",
                    payload={"product_id": content_run.product_id, "provider": "runway"},
                )
            )

        if geometry.get("status") != "ready" or "geometry_lock_missing" in blockers:
            actions.append(
                ContentNextAction(
                    action="add_geometry_lock",
                    priority=15,
                    reason="Product geometry and scale lock must be present before real provider generation.",
                    payload={
                        "content_run_id": content_run.id,
                        "creative_spec_id": content_run.creative_spec_id,
                        "missing_fields": geometry.get("missing_fields") or [],
                    },
                )
            )

        if content_run.selected_variant_id:
            actions.append(
                ContentNextAction(
                    action="run_prompt_only",
                    priority=20,
                    reason="Selected variant exists; prompt pack can be rebuilt without paid provider calls.",
                    payload={"content_run_id": content_run.id, "selected_variant_id": content_run.selected_variant_id},
                )
            )

        if (
            content_run.prompt_pack_id
            and readiness.get("status") == "ready"
            and geometry.get("status") == "ready"
            and not content_run.video_job_id
        ):
            actions.append(
                ContentNextAction(
                    action="run_real_smoke",
                    priority=30,
                    reason="Prompt pack and approved references are ready for one-scene spend-gated smoke.",
                    payload={"content_run_id": content_run.id, "provider": "runway", "max_scenes": 1},
                )
            )

        if "product_geometry_mismatch" in blockers or (latest_review and latest_review.status == "needs_regeneration"):
            actions.append(
                ContentNextAction(
                    action="request_geometry_regeneration",
                    priority=35,
                    reason="Human review or quality metadata indicates product size/proportion drift.",
                    payload={"content_run_id": content_run.id, "review_id": latest_review.id if latest_review else None},
                )
            )

        if latest_review and latest_review.status in {"needs_regeneration", "rejected"}:
            actions.append(
                ContentNextAction(
                    action="request_regeneration",
                    priority=40,
                    reason="AI review or human feedback indicates this scene should be regenerated.",
                    payload={"content_run_id": content_run.id, "review_id": latest_review.id},
                )
            )

        if content_run.video_job_id and (not latest_review or latest_review.human_review_required):
            actions.append(
                ContentNextAction(
                    action="approve_for_publishing",
                    priority=50,
                    reason="Video exists but still needs final human visual approval before publishing prep.",
                    payload={"content_run_id": content_run.id, "video_job_id": content_run.video_job_id},
                )
            )

        if content_run.video_job_id and latest_review and latest_review.status in {"approved", "human_approved"}:
            actions.append(
                ContentNextAction(
                    action="create_publishing_package",
                    priority=60,
                    reason="Human-approved video can be prepared for owned destinations.",
                    payload={"content_run_id": content_run.id, "video_job_id": content_run.video_job_id},
                )
            )

        if not latest_metric:
            actions.append(
                ContentNextAction(
                    action="import_performance_stats",
                    priority=70,
                    reason="No performance metrics are attached to this content run yet.",
                    payload={"content_run_id": content_run.id},
                )
            )
        elif self._is_scaling_candidate(latest_metric):
            actions.append(
                ContentNextAction(
                    action="scale_variant",
                    priority=80,
                    reason="Performance is above baseline; this variant is a candidate for more destinations.",
                    payload={"content_run_id": content_run.id, "metric_id": latest_metric.id},
                )
            )
        elif self._is_pause_candidate(latest_metric):
            actions.append(
                ContentNextAction(
                    action="pause_variant",
                    priority=80,
                    reason="Performance is below baseline; pause or regenerate before scaling.",
                    payload={"content_run_id": content_run.id, "metric_id": latest_metric.id},
                )
            )

        return sorted(actions, key=lambda item: item.priority)

    def action_catalog(self) -> list[str]:
        return list(RECOMMENDATION_ACTIONS)

    def _latest_review(self, content_run_id: int) -> models.AIContentReview | None:
        return self.db.scalar(
            select(models.AIContentReview)
            .where(models.AIContentReview.content_run_id == content_run_id)
            .order_by(models.AIContentReview.id.desc())
        )

    def _latest_metric(self, content_run: models.ContentRun) -> models.ContentPerformanceMetric | None:
        query = select(models.ContentPerformanceMetric).order_by(models.ContentPerformanceMetric.id.desc())
        if content_run.id:
            metric = self.db.scalar(query.where(models.ContentPerformanceMetric.content_run_id == content_run.id))
            if metric:
                return metric
        product = content_run.product
        if product:
            return self.db.scalar(query.where(models.ContentPerformanceMetric.sku == product.sku))
        return None

    @staticmethod
    def _is_scaling_candidate(metric: models.ContentPerformanceMetric) -> bool:
        ctr = metric.ctr or 0
        retention = metric.retention_rate or 0
        orders = metric.orders or 0
        return ctr >= 0.035 or retention >= 0.4 or orders >= 3

    @staticmethod
    def _is_pause_candidate(metric: models.ContentPerformanceMetric) -> bool:
        ctr = metric.ctr or 0
        retention = metric.retention_rate or 0
        orders = metric.orders or 0
        return ctr > 0 and ctr < 0.01 and retention < 0.2 and orders == 0
