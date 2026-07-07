from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.product_strategy.errors import ProductStrategyDataError
from app.product_strategy.types import OfferStrategyOutput


class OfferStrategyBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, product_strategy_spec_id: int) -> models.OfferStrategy:
        spec = self.db.get(models.ProductStrategySpec, product_strategy_spec_id)
        if not spec:
            raise ProductStrategyDataError(f"ProductStrategySpec {product_strategy_spec_id} not found.")
        existing = self.db.scalar(
            select(models.OfferStrategy)
            .where(models.OfferStrategy.product_strategy_spec_id == spec.id)
            .order_by(models.OfferStrategy.id.desc())
        )
        if existing:
            return existing
        offer = self._offer_from_spec(spec)
        model = models.OfferStrategy(
            product_strategy_spec_id=spec.id,
            product_id=spec.product_id,
            sku=spec.sku,
            status="ready",
            offer_type=offer["offer_type"],
            price_message=offer["price_message"],
            discount_message=offer["discount_message"],
            value_reason=offer["value_reason"],
            competitor_response=offer["competitor_response"],
            stock_warning=offer["stock_warning"],
            cta_strategy=offer["cta_strategy"],
            warnings_json=offer["warnings"],
        )
        self.db.add(model)
        self.db.flush()
        spec.offer_strategy_json = {
            **(spec.offer_strategy_json or {}),
            "offer_strategy_id": model.id,
            **offer,
        }
        self.db.commit()
        self.db.refresh(model)
        return model

    def latest_for_product(self, product_id: int) -> models.OfferStrategy | None:
        return self.db.scalar(
            select(models.OfferStrategy)
            .where(models.OfferStrategy.product_id == product_id)
            .order_by(models.OfferStrategy.id.desc())
        )

    def as_output(self, offer: models.OfferStrategy) -> OfferStrategyOutput:
        return OfferStrategyOutput(
            id=offer.id,
            product_strategy_spec_id=offer.product_strategy_spec_id,
            product_id=offer.product_id,
            sku=offer.sku,
            status=offer.status,
            offer_type=offer.offer_type,
            price_message=offer.price_message,
            discount_message=offer.discount_message,
            value_reason=offer.value_reason,
            competitor_response=offer.competitor_response,
            stock_warning=offer.stock_warning,
            cta_strategy=offer.cta_strategy,
            warnings=offer.warnings_json or [],
        )

    @staticmethod
    def preview(spec: models.ProductStrategySpec) -> dict:
        return OfferStrategyBuilder._offer_from_spec(spec)

    @staticmethod
    def _offer_from_spec(spec: models.ProductStrategySpec) -> dict:
        warnings: list[str] = []
        performance_flags = set((spec.offer_strategy_json or {}).get("performance_flags") or [])
        market_risks = set((spec.offer_strategy_json or {}).get("market_risks") or [])
        stock_context = spec.stock_context_json or {}
        price_position = spec.price_position_json or {}
        competitor = spec.competitor_context_json or {}
        stock_risk = stock_context.get("stock_risk")
        discount_percent = price_position.get("discount_percent")

        offer_type = "routine"
        if "low_ctr" in performance_flags:
            offer_type = "novelty"
        if "low_conversion" in performance_flags:
            offer_type = "trust"
        if "high_returns" in performance_flags:
            offer_type = "problem_solution"
        if "competitor_price_pressure" in market_risks or competitor.get("pressure") == "price_pressure":
            offer_type = "comparison"
        if stock_risk == "low_stock":
            offer_type = "routine"
            warnings.append("stock_risk_no_aggressive_cta")

        price_message = "Use product value, not a pure discount claim."
        if discount_percent:
            price_message = f"Discount can be mentioned carefully: {discount_percent}%."
        if price_position.get("needs_value_explanation"):
            price_message = "Explain why the product is worth comparing beyond cheapest price."

        discount_message = "No discount-led hook unless a real discount is present."
        if discount_percent:
            discount_message = f"Real discount available: {discount_percent}%."

        value_reason = spec.product_role or "Explain the concrete routine fit and proof moment."
        competitor_response = ""
        if competitor.get("pressure") == "price_pressure":
            competitor_response = "Acknowledge cheaper alternatives indirectly and explain value, format, proof, or trust."
        stock_warning = "Soft education only; avoid urgency and aggressive CTA." if stock_risk == "low_stock" else ""
        cta_strategy = "Check the product card if this fits your routine."
        if stock_risk == "low_stock":
            cta_strategy = "Soft CTA: learn whether it fits, no hard push."
        elif offer_type == "comparison":
            cta_strategy = "Compare the product card details before choosing."
        elif offer_type == "trust":
            cta_strategy = "Open the product card for details and reviews."

        return {
            "offer_type": offer_type,
            "price_message": price_message,
            "discount_message": discount_message,
            "value_reason": value_reason,
            "competitor_response": competitor_response,
            "stock_warning": stock_warning,
            "cta_strategy": cta_strategy,
            "warnings": list(dict.fromkeys(warnings)),
        }
