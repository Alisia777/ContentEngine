from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_performance.errors import CampaignPerformanceDataError
from app.campaign_performance.performance_aggregator import CampaignPerformanceAggregator
from app.campaign_performance.scoring import CampaignPerformanceScorer
from app.campaign_performance.types import ScalingRecommendationResult


class CampaignRecommendationEngine:
    def __init__(self, db: Session):
        self.db = db

    def generate(self, campaign_id: int) -> list[ScalingRecommendationResult]:
        self.db.query(models.CampaignScalingRecommendation).filter(
            models.CampaignScalingRecommendation.campaign_id == campaign_id,
            models.CampaignScalingRecommendation.status.in_(["proposed", "queued"]),
        ).delete()
        summary = CampaignPerformanceAggregator(self.db).summarize(campaign_id)
        CampaignPerformanceScorer(self.db).compute_scores(campaign_id)
        records: list[models.CampaignScalingRecommendation] = []
        for metric in self._metrics(campaign_id):
            records.extend(self._recommend_for_metric(metric))
        for row in summary.published_without_metrics:
            records.append(
                self._create(
                    campaign_id,
                    "import_performance_stats",
                    product_id=None,
                    sku=row.get("sku"),
                    destination_id=row.get("destination_id"),
                    priority=25,
                    impact="Close the loop for published content before scaling decisions.",
                    reasons=[f"published task {row.get('publishing_task_id')} has final URL but no metric row"],
                )
            )
        self._multi_destination_recommendations(campaign_id, records)
        self.db.commit()
        for record in records:
            self._queue_action(record)
        self.db.commit()
        return [self._result(record) for record in records]

    def list_recommendations(self, campaign_id: int) -> list[ScalingRecommendationResult]:
        rows = self.db.scalars(
            select(models.CampaignScalingRecommendation)
            .where(models.CampaignScalingRecommendation.campaign_id == campaign_id)
            .order_by(models.CampaignScalingRecommendation.priority, models.CampaignScalingRecommendation.id)
        ).all()
        if not rows:
            return self.generate(campaign_id)
        return [self._result(row) for row in rows]

    def accept(self, recommendation_id: int) -> ScalingRecommendationResult:
        recommendation = self._recommendation(recommendation_id)
        recommendation.status = "accepted"
        self._queue_action(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        return self._result(recommendation)

    def reject(self, recommendation_id: int) -> ScalingRecommendationResult:
        recommendation = self._recommendation(recommendation_id)
        recommendation.status = "rejected"
        self.db.commit()
        self.db.refresh(recommendation)
        return self._result(recommendation)

    def _recommend_for_metric(self, metric: models.CampaignPerformanceMetric) -> list[models.CampaignScalingRecommendation]:
        views = metric.views or 0
        clicks = metric.clicks or 0
        orders = metric.orders or 0
        ctr = metric.ctr or 0
        engagement = metric.engagement_rate or 0
        cpo = metric.cost_per_order or 0
        records = []
        if views >= 1000 and engagement >= 0.08:
            records.append(
                self._create(
                    metric.campaign_id,
                    "scale_variant",
                    product_id=metric.product_id,
                    sku=metric.sku,
                    creative_variant_id=metric.creative_variant_id,
                    destination_id=metric.destination_id,
                    priority=20,
                    impact="Increase distribution for a variant with strong attention.",
                    reasons=[f"views={views}", f"engagement_rate={engagement}"],
                )
            )
        if views >= 1000 and clicks <= max(5, int(views * 0.005)):
            records.append(
                self._create(
                    metric.campaign_id,
                    "regenerate_variant",
                    product_id=metric.product_id,
                    sku=metric.sku,
                    creative_variant_id=metric.creative_variant_id,
                    destination_id=metric.destination_id,
                    priority=30,
                    impact="Improve hook or CTA before scaling.",
                    reasons=[f"high_views={views}", f"low_clicks={clicks}", f"ctr={ctr}"],
                )
            )
        if clicks >= 50 and orders == 0:
            records.append(
                self._create(
                    metric.campaign_id,
                    "regenerate_variant",
                    product_id=metric.product_id,
                    sku=metric.sku,
                    creative_variant_id=metric.creative_variant_id,
                    destination_id=metric.destination_id,
                    priority=35,
                    impact="Improve offer, card, or promise after click interest.",
                    reasons=[f"clicks={clicks}", "orders=0"],
                )
            )
        if views < 100 and metric.destination_id:
            records.append(
                self._create(
                    metric.campaign_id,
                    "change_destination",
                    product_id=metric.product_id,
                    sku=metric.sku,
                    creative_variant_id=metric.creative_variant_id,
                    destination_id=metric.destination_id,
                    priority=45,
                    impact="Pause or change weak destination distribution.",
                    reasons=[f"low_views={views}"],
                )
            )
        if cpo and cpo >= 500:
            records.append(
                self._create(
                    metric.campaign_id,
                    "pause_variant",
                    product_id=metric.product_id,
                    sku=metric.sku,
                    creative_variant_id=metric.creative_variant_id,
                    destination_id=metric.destination_id,
                    priority=40,
                    impact="Reduce waste from high cost per order.",
                    reasons=[f"cost_per_order={cpo}"],
                )
            )
        return records

    def _multi_destination_recommendations(self, campaign_id: int, records: list[models.CampaignScalingRecommendation]) -> None:
        counts: dict[int, int] = {}
        for metric in self._metrics(campaign_id):
            if metric.creative_variant_id and (metric.engagement_rate or 0) >= 0.08:
                counts[metric.creative_variant_id] = counts.get(metric.creative_variant_id, 0) + 1
        for variant_id, count in counts.items():
            if count >= 2:
                records.append(
                    self._create(
                        campaign_id,
                        "increase_distribution",
                        creative_variant_id=variant_id,
                        priority=15,
                        impact="Variant is strong across multiple destinations.",
                        reasons=[f"strong_destinations={count}"],
                    )
                )

    def _create(
        self,
        campaign_id: int,
        recommendation_type: str,
        *,
        product_id: int | None = None,
        sku: str | None = None,
        creative_variant_id: int | None = None,
        destination_id: int | None = None,
        priority: int,
        impact: str,
        reasons: list[str],
    ) -> models.CampaignScalingRecommendation:
        record = models.CampaignScalingRecommendation(
            campaign_id=campaign_id,
            recommendation_type=recommendation_type,
            product_id=product_id,
            sku=sku,
            creative_variant_id=creative_variant_id,
            destination_id=destination_id,
            priority=priority,
            expected_impact=impact,
            reasons_json=reasons,
            status="proposed",
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _queue_action(self, recommendation: models.CampaignScalingRecommendation) -> None:
        action_type = self._action_type(recommendation.recommendation_type)
        if not action_type:
            return
        existing = self.db.scalar(
            select(models.CampaignActionQueueItem).where(
                models.CampaignActionQueueItem.campaign_id == recommendation.campaign_id,
                models.CampaignActionQueueItem.action_type == action_type,
                models.CampaignActionQueueItem.sku == recommendation.sku,
                models.CampaignActionQueueItem.status.in_(["open", "blocked"]),
            )
        )
        if existing:
            return
        self.db.add(
            models.CampaignActionQueueItem(
                campaign_id=recommendation.campaign_id,
                product_id=recommendation.product_id,
                sku=recommendation.sku,
                content_run_id=None,
                action_type=action_type,
                priority=recommendation.priority,
                status="open",
                reason=recommendation.expected_impact,
                blockers_json=[],
                safe_to_execute=action_type in {"create_regeneration_request", "create_more_variants_draft", "import_performance_stats"},
                requires_human=False,
            )
        )
        recommendation.status = "queued" if recommendation.status == "proposed" else recommendation.status

    @staticmethod
    def _action_type(recommendation_type: str) -> str | None:
        return {
            "regenerate_variant": "create_regeneration_request",
            "scale_variant": "create_more_variants_draft",
            "increase_distribution": "create_distribution_task_draft",
            "import_performance_stats": "import_performance_stats",
        }.get(recommendation_type)

    def _metrics(self, campaign_id: int) -> list[models.CampaignPerformanceMetric]:
        return self.db.scalars(
            select(models.CampaignPerformanceMetric)
            .where(models.CampaignPerformanceMetric.campaign_id == campaign_id)
            .order_by(models.CampaignPerformanceMetric.id)
        ).all()

    def _recommendation(self, recommendation_id: int) -> models.CampaignScalingRecommendation:
        recommendation = self.db.get(models.CampaignScalingRecommendation, recommendation_id)
        if not recommendation:
            raise CampaignPerformanceDataError(f"CampaignScalingRecommendation {recommendation_id} not found.")
        return recommendation

    @staticmethod
    def _result(record: models.CampaignScalingRecommendation) -> ScalingRecommendationResult:
        return ScalingRecommendationResult(
            recommendation_id=record.id,
            campaign_id=record.campaign_id,
            recommendation_type=record.recommendation_type,
            product_id=record.product_id,
            sku=record.sku,
            creative_variant_id=record.creative_variant_id,
            destination_id=record.destination_id,
            priority=record.priority,
            expected_impact=record.expected_impact,
            reasons=record.reasons_json or [],
            status=record.status,
        )
