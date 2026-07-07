from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


class CompetitorContextBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, product: models.Product, metrics_summary: dict) -> tuple[dict, dict]:
        signals = self.db.scalars(
            select(models.MarketSignal)
            .where(models.MarketSignal.sku == product.sku)
            .order_by(models.MarketSignal.id.desc())
        ).all()
        competitor_prices = [signal.competitor_price for signal in signals if signal.competitor_price is not None]
        avg_price = metrics_summary.get("avg_price")
        cheapest_competitor = min(competitor_prices) if competitor_prices else None
        pressure = bool(cheapest_competitor is not None and avg_price is not None and cheapest_competitor < avg_price)
        competitor_context = {
            "has_competitor_signals": bool(signals),
            "pressure": "price_pressure" if pressure else "none",
            "competitor_count": len(signals),
            "cheapest_competitor_price": cheapest_competitor,
            "signals": [
                {
                    "id": signal.id,
                    "brand": signal.competitor_brand,
                    "price": signal.competitor_price,
                    "rating": signal.competitor_rating,
                    "reviews_count": signal.competitor_reviews_count,
                    "signal_type": signal.signal_type,
                    "strength": signal.signal_strength,
                }
                for signal in signals[:5]
            ],
        }
        price_position = {
            "avg_price": avg_price,
            "discount_percent": metrics_summary.get("discount_percent"),
            "competitor_price": cheapest_competitor,
            "position": "premium_vs_competitor" if pressure else "neutral_or_unknown",
            "needs_value_explanation": pressure,
        }
        return competitor_context, price_position
