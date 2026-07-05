from __future__ import annotations

from sqlalchemy.orm import Session

from app.campaign_performance.performance_aggregator import CampaignPerformanceAggregator
from app.campaign_performance.recommendation_engine import CampaignRecommendationEngine
from app.campaign_performance.scoring import CampaignPerformanceScorer
from app.campaign_performance.types import CampaignPerformanceReport


class CampaignPerformanceReportService:
    def __init__(self, db: Session):
        self.db = db

    def build_report(self, campaign_id: int) -> CampaignPerformanceReport:
        summary = CampaignPerformanceAggregator(self.db).summarize(campaign_id)
        scores = CampaignPerformanceScorer(self.db).latest_scores(campaign_id)
        recommendations = CampaignRecommendationEngine(self.db).list_recommendations(campaign_id)
        return CampaignPerformanceReport(
            campaign_id=campaign_id,
            summary=summary,
            scores=scores,
            recommendations=recommendations,
            summary_csv=self._summary_csv(summary.model_dump(mode="json")),
        )

    @staticmethod
    def _summary_csv(summary: dict) -> str:
        keys = [
            "campaign_id",
            "metric_count",
            "total_views",
            "total_clicks",
            "total_orders",
            "total_revenue",
            "total_spend",
            "avg_ctr",
            "avg_conversion_rate",
            "avg_engagement_rate",
        ]
        return ",".join(keys) + "\n" + ",".join(str(summary.get(key, "")) for key in keys)
