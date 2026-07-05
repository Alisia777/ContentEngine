from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_performance.performance_aggregator import CampaignPerformanceAggregator
from app.campaign_performance.types import PerformanceScoreResult


class CampaignPerformanceScorer:
    def __init__(self, db: Session):
        self.db = db

    def compute_scores(self, campaign_id: int) -> list[PerformanceScoreResult]:
        summary = CampaignPerformanceAggregator(self.db).summarize(campaign_id)
        self.db.query(models.CampaignPerformanceScore).filter(models.CampaignPerformanceScore.campaign_id == campaign_id).delete()
        rows = []
        for entity_type, group_rows in [
            ("sku", summary.by_sku),
            ("variant", summary.by_variant),
            ("destination", summary.by_destination),
            ("platform", summary.by_platform),
        ]:
            for row in group_rows:
                rows.append(self._create_score(campaign_id, entity_type, row["entity_id"], row))
        rows.extend(self._hook_scores(campaign_id))
        self.db.commit()
        return [self._result(row) for row in rows]

    def latest_scores(self, campaign_id: int) -> list[PerformanceScoreResult]:
        scores = self.db.scalars(
            select(models.CampaignPerformanceScore)
            .where(models.CampaignPerformanceScore.campaign_id == campaign_id)
            .order_by(models.CampaignPerformanceScore.entity_type, models.CampaignPerformanceScore.id)
        ).all()
        if not scores:
            return self.compute_scores(campaign_id)
        return [self._result(score) for score in scores]

    def _create_score(self, campaign_id: int, entity_type: str, entity_id: str | None, row: dict) -> models.CampaignPerformanceScore:
        score_value = self._score_value(row)
        status = "strong" if score_value >= 0.35 else "weak" if row.get("views", 0) >= 1000 and score_value < 0.08 else "neutral"
        reasons = []
        if row.get("engagement_rate") is not None:
            reasons.append(f"engagement_rate={row['engagement_rate']}")
        if row.get("ctr") is not None:
            reasons.append(f"ctr={row['ctr']}")
        if row.get("conversion_rate") is not None:
            reasons.append(f"conversion_rate={row['conversion_rate']}")
        recommendation = "scale" if status == "strong" else "regenerate_or_pause" if status == "weak" else "monitor"
        record = models.CampaignPerformanceScore(
            campaign_id=campaign_id,
            entity_type=entity_type,
            entity_id=entity_id,
            score_json={**row, "score_value": score_value},
            status=status,
            recommendation=recommendation,
            reasons_json=reasons,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _hook_scores(self, campaign_id: int) -> list[models.CampaignPerformanceScore]:
        records = []
        metrics = self.db.scalars(
            select(models.CampaignPerformanceMetric).where(
                models.CampaignPerformanceMetric.campaign_id == campaign_id,
                models.CampaignPerformanceMetric.creative_variant_id.is_not(None),
            )
        ).all()
        seen = set()
        for metric in metrics:
            variant = self.db.get(models.CreativeVariant, metric.creative_variant_id)
            if not variant or not variant.hook_text or variant.hook_text in seen:
                continue
            seen.add(variant.hook_text)
            records.append(
                self._create_score(
                    campaign_id,
                    "hook",
                    variant.hook_text[:150],
                    {
                        "entity_id": variant.hook_text[:150],
                        "views": metric.views or 0,
                        "clicks": metric.clicks or 0,
                        "orders": metric.orders or 0,
                        "revenue": metric.revenue or 0,
                        "spend": metric.spend or 0,
                        "engagement_rate": metric.engagement_rate,
                        "ctr": metric.ctr,
                        "conversion_rate": metric.conversion_rate,
                        "revenue_per_view": self._ratio(metric.revenue, metric.views),
                    },
                )
            )
        return records

    @staticmethod
    def _score_value(row: dict) -> float:
        engagement = row.get("engagement_rate") or 0
        ctr = row.get("ctr") or 0
        conversion = row.get("conversion_rate") or 0
        revenue_per_view = row.get("revenue_per_view") or 0
        return round(engagement + ctr * 2 + conversion * 2 + min(revenue_per_view, 0.2), 4)

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)

    @staticmethod
    def _result(score: models.CampaignPerformanceScore) -> PerformanceScoreResult:
        return PerformanceScoreResult(
            score_id=score.id,
            campaign_id=score.campaign_id,
            entity_type=score.entity_type,
            entity_id=score.entity_id,
            status=score.status,
            recommendation=score.recommendation,
            score=score.score_json or {},
            reasons=score.reasons_json or [],
        )
