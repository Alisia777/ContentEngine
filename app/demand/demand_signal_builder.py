from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.demand.errors import DemandDataError
from app.demand.types import DemandSignalSet
from app.intelligence.metrics import coalesce_rate
from app.intelligence.scoring import score_intelligence
from app.intelligence.source_mapping import product_facts


class DemandSignalBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, product_id: int) -> DemandSignalSet:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise DemandDataError(f"Product {product_id} not found.")
        metrics = self.db.scalars(
            select(models.ProductMetricSnapshot)
            .where(models.ProductMetricSnapshot.sku == product.sku)
            .order_by(models.ProductMetricSnapshot.period_end.desc(), models.ProductMetricSnapshot.id.desc())
        ).all()
        latest_metric = metrics[0] if metrics else None
        previous_metric = metrics[1] if len(metrics) > 1 else None
        creative_rows = self.db.scalars(
            select(models.CreativePerformanceSnapshot)
            .where(models.CreativePerformanceSnapshot.sku == product.sku)
            .order_by(models.CreativePerformanceSnapshot.posted_at.desc().nullslast(), models.CreativePerformanceSnapshot.id.desc())
            .limit(10)
        ).all()
        review = self.db.scalar(
            select(models.ProductReviewInsight)
            .where(models.ProductReviewInsight.sku == product.sku)
            .order_by(models.ProductReviewInsight.id.desc())
        )
        market_signals = self.db.scalars(
            select(models.MarketSignal).where(models.MarketSignal.sku == product.sku).order_by(models.MarketSignal.id.desc())
        ).all()
        _, allowed_claims = product_facts(product)
        score = score_intelligence(latest_metric, market_signals)
        missing_data = []
        if not latest_metric:
            missing_data.append("no marketplace performance data")
        if not creative_rows:
            missing_data.append("no creative performance data")
        if not review:
            missing_data.append("no recent review insights")
        if not market_signals:
            missing_data.append("no market signals")
        if not any(row.retention_rate is not None for row in creative_rows):
            missing_data.append("no retention data")
        performance_flags = list(score["performance_flags"])
        market_risks = list(score["market_risks"])
        if not latest_metric and not creative_rows and not review and "no_strong_data" not in performance_flags:
            performance_flags.append("no_strong_data")
        return DemandSignalSet(
            product_id=product.id,
            sku=product.sku,
            product_title=product.title,
            performance_flags=list(dict.fromkeys(performance_flags)),
            market_risks=market_risks,
            stock_risk=score["stock_risk"],
            price_positioning=score["price_positioning"],
            buyer_objections=review.buyer_objections_json if review else [],
            buyer_language=review.buyer_language_json if review else [],
            allowed_claims=allowed_claims,
            missing_data=list(dict.fromkeys(missing_data)),
            warnings=list(score["warnings"]),
            source_map={
                "product": product.id,
                "latest_metric": latest_metric.id if latest_metric else None,
                "previous_metric": previous_metric.id if previous_metric else None,
                "creative_performance": [row.id for row in creative_rows],
                "review_insight": review.id if review else None,
                "market_signals": [row.id for row in market_signals],
            },
            metrics_summary=self._metrics_summary(latest_metric),
        )

    @staticmethod
    def _metrics_summary(metric: models.ProductMetricSnapshot | None) -> dict:
        if not metric:
            return {}
        return {
            "ctr": coalesce_rate(metric.ctr, metric.clicks, metric.views),
            "conversion_rate": coalesce_rate(metric.conversion_rate, metric.orders, metric.clicks),
            "returns_rate": metric.returns_rate,
            "stock_qty": metric.stock_qty,
            "days_of_stock": metric.days_of_stock,
            "avg_price": metric.avg_price,
        }
