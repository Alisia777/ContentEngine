from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.intelligence.errors import MissingGeneratorDataError
from app.intelligence.scoring import score_intelligence
from app.intelligence.source_mapping import product_facts
from app.intelligence.types import ContentLearning, CreativeIntelligencePack


class CreativeIntelligenceBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_for_product(self, product_id: int) -> models.CreativeIntelligencePackRecord:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise MissingGeneratorDataError(f"Product {product_id} not found.")

        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        )
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

        facts, allowed_claims = product_facts(product)
        score = score_intelligence(latest_metric, market_signals)
        missing_data = []
        warnings = list(score["warnings"])
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
        if brand_guide:
            warnings.extend(brand_guide.forbidden_claims_json or [])

        pack = CreativeIntelligencePack(
            sku=product.sku,
            product_id=product.id,
            product_title=product.title,
            product_facts=facts,
            allowed_claims=allowed_claims,
            missing_data=missing_data,
            performance_flags=score["performance_flags"],
            buyer_objections=review.buyer_objections_json if review else [],
            buyer_language=review.buyer_language_json if review else [],
            content_learnings=[
                ContentLearning(
                    platform=row.platform,
                    creative_angle=row.creative_angle,
                    hook_text=row.hook_text,
                    ctr=row.ctr,
                    retention_rate=row.retention_rate,
                    orders=row.orders,
                )
                for row in creative_rows
            ],
            market_risks=score["market_risks"],
            stock_risk=score["stock_risk"],
            price_positioning=score["price_positioning"],
            recommended_objective=score["recommended_objective"],
            recommended_creative_angles=score["recommended_creative_angles"],
            recommended_video_formats=["9:16_short", "captioned_scene_sequence"],
            source_map={
                "product": product.id,
                "brand_guide": brand_guide.id if brand_guide else None,
                "latest_metric": latest_metric.id if latest_metric else None,
                "previous_metric": previous_metric.id if previous_metric else None,
                "creative_performance": [row.id for row in creative_rows],
                "review_insight": review.id if review else None,
                "market_signals": [row.id for row in market_signals],
            },
            warnings=warnings,
            reasoning_summary=self._reasoning(score, missing_data),
        )
        record = models.CreativeIntelligencePackRecord(
            product_id=product.id,
            sku=product.sku,
            status="ready",
            pack_json=pack.model_dump(mode="json"),
            source_summary_json=pack.source_map,
            warnings_json=pack.warnings,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    @staticmethod
    def _reasoning(score: dict, missing_data: list[str]) -> str:
        if "low_conversion" in score["performance_flags"]:
            return "CTR is acceptable while conversion is weak, so the script should explain value and handle objections."
        if "low_ctr" in score["performance_flags"]:
            return "CTR is below threshold, so the first frame, hook, and curiosity gap need stronger treatment."
        if "high_returns" in score["performance_flags"]:
            return "Return risk is elevated, so the script should set expectations and explain use clearly."
        if missing_data:
            return "Performance data is incomplete, so the generator should use conservative source-backed messaging."
        return "Available data supports a balanced product explanation with source-backed claims."

