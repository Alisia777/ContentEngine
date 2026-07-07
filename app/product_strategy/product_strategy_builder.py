from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.product_strategy.competitor_context_builder import CompetitorContextBuilder
from app.product_strategy.errors import ProductStrategyDataError
from app.product_strategy.offer_strategy_builder import OfferStrategyBuilder
from app.product_strategy.platform_strategy_builder import PlatformStrategyBuilder
from app.product_strategy.proof_requirement_builder import ProofRequirementBuilder
from app.product_strategy.types import ProductStrategySpecOutput, ProductStrategyStatus


class ProductStrategyBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(
        self,
        product_id: int,
        *,
        platform: str = "Instagram Reels",
        demand_hypothesis_id: int | None = None,
    ) -> models.ProductStrategySpec:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise ProductStrategyDataError(f"Product {product_id} not found.")
        from app.demand.demand_hypothesis_builder import DemandHypothesisBuilder
        from app.demand.demand_signal_builder import DemandSignalBuilder

        demand = self._demand(product_id, demand_hypothesis_id) or DemandHypothesisBuilder(self.db).build_for_product(product_id)
        signals = DemandSignalBuilder(self.db).build(product_id)
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id.desc())
        )
        review = self._review(product.sku)
        competitor_context, price_position = CompetitorContextBuilder(self.db).build(product, signals.metrics_summary)
        stock_context = self._stock_context(signals.metrics_summary, signals.stock_risk)
        proof_required = ProofRequirementBuilder().build(product, demand, self._review_summary(review))
        buyer_segment = self._buyer_segment(product, demand, signals)
        buyer_situation = self._buyer_situation(demand, signals)
        content_angles = self._content_angles(demand, signals, competitor_context, stock_context)
        offer_preview = self._offer_preview(
            performance_flags=signals.performance_flags,
            market_risks=signals.market_risks,
            product_role=self._product_role(product, demand),
            competitor_context=competitor_context,
            price_position=price_position,
            stock_context=stock_context,
        )
        platform_strategy = PlatformStrategyBuilder().build(primary_platform=platform, offer_type=offer_preview["offer_type"])
        warnings = list(dict.fromkeys(signals.warnings + self._warnings(signals, competitor_context, stock_context)))

        spec = models.ProductStrategySpec(
            product_id=product.id,
            sku=product.sku,
            status="ready",
            buyer_segment_json=buyer_segment,
            buyer_situation_json=buyer_situation,
            purchase_trigger=(demand.hypothesis_json or {}).get("trigger_situation"),
            main_pain=(demand.hypothesis_json or {}).get("pain_point"),
            main_desire=(demand.hypothesis_json or {}).get("buyer_need"),
            main_objection=(demand.hypothesis_json or {}).get("objection"),
            product_role=self._product_role(product, demand),
            category_alternative=self._category_alternative(product),
            competitor_context_json=competitor_context,
            price_position_json=price_position,
            stock_context_json=stock_context,
            offer_strategy_json=offer_preview,
            proof_required_json=proof_required,
            safe_claims_json=self._safe_claims(demand),
            forbidden_claims_json=self._forbidden_claims(product, brand_guide),
            platform_strategy_json=platform_strategy,
            content_angles_json=content_angles,
            warnings_json=warnings,
        )
        self.db.add(spec)
        self.db.commit()
        self.db.refresh(spec)
        return spec

    def latest_for_product(self, product_id: int) -> models.ProductStrategySpec | None:
        return self.db.scalar(
            select(models.ProductStrategySpec)
            .where(models.ProductStrategySpec.product_id == product_id)
            .order_by(models.ProductStrategySpec.id.desc())
        )

    def status(self, product_id: int) -> ProductStrategyStatus:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise ProductStrategyDataError(f"Product {product_id} not found.")
        spec = self.latest_for_product(product_id)
        offer = OfferStrategyBuilder(self.db).latest_for_product(product_id)
        blockers = []
        next_actions = []
        if not spec:
            blockers.append("product_strategy_required")
            next_actions.append("build_product_strategy_spec")
        if spec and not offer:
            blockers.append("offer_strategy_required")
            next_actions.append("build_offer_strategy")
        return ProductStrategyStatus(
            product_id=product.id,
            sku=product.sku,
            status="ready" if not blockers else "blocked",
            product_strategy_spec_id=spec.id if spec else None,
            offer_strategy_id=offer.id if offer else None,
            blockers=blockers,
            warnings=(spec.warnings_json if spec else []),
            next_actions=next_actions,
        )

    def as_output(self, spec: models.ProductStrategySpec) -> ProductStrategySpecOutput:
        return ProductStrategySpecOutput(
            id=spec.id,
            product_id=spec.product_id,
            sku=spec.sku,
            status=spec.status,
            buyer_segment=spec.buyer_segment_json or {},
            buyer_situation=spec.buyer_situation_json or {},
            purchase_trigger=spec.purchase_trigger,
            main_pain=spec.main_pain,
            main_desire=spec.main_desire,
            main_objection=spec.main_objection,
            product_role=spec.product_role,
            category_alternative=spec.category_alternative,
            competitor_context=spec.competitor_context_json or {},
            price_position=spec.price_position_json or {},
            stock_context=spec.stock_context_json or {},
            offer_strategy=spec.offer_strategy_json or {},
            proof_required=spec.proof_required_json or [],
            safe_claims=spec.safe_claims_json or [],
            forbidden_claims=spec.forbidden_claims_json or [],
            platform_strategy=spec.platform_strategy_json or {},
            content_angles=spec.content_angles_json or [],
            warnings=spec.warnings_json or [],
        )

    def _demand(self, product_id: int, demand_hypothesis_id: int | None) -> models.DemandHypothesisRecord | None:
        if demand_hypothesis_id:
            demand = self.db.get(models.DemandHypothesisRecord, demand_hypothesis_id)
            if not demand:
                raise ProductStrategyDataError(f"DemandHypothesisRecord {demand_hypothesis_id} not found.")
            return demand
        return self.db.scalar(
            select(models.DemandHypothesisRecord)
            .where(models.DemandHypothesisRecord.product_id == product_id)
            .order_by(models.DemandHypothesisRecord.id.desc())
        )

    def _review(self, sku: str) -> models.ProductReviewInsight | None:
        return self.db.scalar(
            select(models.ProductReviewInsight)
            .where(models.ProductReviewInsight.sku == sku)
            .order_by(models.ProductReviewInsight.id.desc())
        )

    @staticmethod
    def _buyer_segment(product: models.Product, demand: models.DemandHypothesisRecord, signals) -> dict:
        hypothesis = demand.hypothesis_json or {}
        return {
            "segment": "routine-driven buyer",
            "category": product.category,
            "language": signals.buyer_language[:5],
            "need_type": hypothesis.get("need_type") or demand.need_type,
            "why_relevant": hypothesis.get("buyer_need"),
        }

    @staticmethod
    def _buyer_situation(demand: models.DemandHypothesisRecord, signals) -> dict:
        hypothesis = demand.hypothesis_json or {}
        return {
            "situation": hypothesis.get("trigger_situation"),
            "pain": hypothesis.get("pain_point"),
            "desire": hypothesis.get("buyer_need"),
            "objection": hypothesis.get("objection"),
            "stock_risk": signals.stock_risk,
            "performance_flags": signals.performance_flags,
            "market_risks": signals.market_risks,
        }

    @staticmethod
    def _product_role(product: models.Product, demand: models.DemandHypothesisRecord) -> str:
        hypothesis = demand.hypothesis_json or {}
        safe_promise = hypothesis.get("safe_promise") or f"show realistic fit for {product.title}"
        return f"{product.title} acts as the concrete proof for: {safe_promise}"

    @staticmethod
    def _category_alternative(product: models.Product) -> str:
        category = product.category or "category alternative"
        if "bar" in product.title.lower() or "snack" in category.lower():
            return "ordinary chocolate bar, dessert, or random snack"
        if "beauty" in category.lower() or "skin" in product.title.lower():
            return "generic beauty product without routine proof"
        return f"another {category} option"

    @staticmethod
    def _stock_context(metrics_summary: dict, stock_risk: str | None) -> dict:
        return {
            "stock_qty": metrics_summary.get("stock_qty"),
            "days_of_stock": metrics_summary.get("days_of_stock"),
            "stock_risk": stock_risk,
            "aggressive_cta_allowed": stock_risk != "low_stock",
        }

    @staticmethod
    def _review_summary(review: models.ProductReviewInsight | None) -> dict:
        if not review:
            return {}
        return {
            "positive_themes": review.positive_themes_json or [],
            "negative_themes": review.negative_themes_json or [],
            "buyer_objections": review.buyer_objections_json or [],
            "buyer_language": review.buyer_language_json or [],
        }

    @staticmethod
    def _safe_claims(demand: models.DemandHypothesisRecord) -> list[str]:
        hypothesis = demand.hypothesis_json or {}
        claims = [hypothesis.get("safe_promise")]
        claims.extend(hypothesis.get("proof_required") or [])
        return list(dict.fromkeys(item for item in claims if item))

    @staticmethod
    def _forbidden_claims(product: models.Product, brand_guide: models.BrandGuide | None) -> list[str]:
        blocked = ["medical treatment", "guaranteed result", "visual identity verified by AI"]
        blocked.extend(str(item) for item in (product.restrictions_json or []))
        if brand_guide:
            blocked.extend(str(item) for item in (brand_guide.forbidden_claims_json or []))
        return list(dict.fromkeys(item for item in blocked if item))

    @staticmethod
    def _content_angles(demand: models.DemandHypothesisRecord, signals, competitor_context: dict, stock_context: dict) -> list[dict]:
        hypothesis = demand.hypothesis_json or {}
        angles = [
            {
                "angle": hypothesis.get("need_type") or demand.need_type,
                "why": hypothesis.get("reasoning") or "Demand rule selected this need.",
            }
        ]
        if "low_ctr" in signals.performance_flags:
            angles.append({"angle": "stop_scroll_awareness", "why": "CTR is weak, so the first frame must give a reason to care."})
        if "low_conversion" in signals.performance_flags:
            angles.append({"angle": "trust_and_proof", "why": "Conversion is weak, so the ad should answer doubt."})
        if competitor_context.get("pressure") == "price_pressure":
            angles.append({"angle": "comparison_value", "why": "Competitor price pressure needs value explanation."})
        if stock_context.get("stock_risk") == "low_stock":
            angles.append({"angle": "soft_education", "why": "Stock risk blocks aggressive demand push."})
        return angles

    @staticmethod
    def _offer_preview(
        *,
        performance_flags: list[str],
        market_risks: list[str],
        product_role: str,
        competitor_context: dict,
        price_position: dict,
        stock_context: dict,
    ) -> dict:
        pseudo_spec = type(
            "OfferPreview",
            (),
            {
                "offer_strategy_json": {"performance_flags": performance_flags, "market_risks": market_risks},
                "stock_context_json": stock_context,
                "price_position_json": price_position,
                "competitor_context_json": competitor_context,
                "product_role": product_role,
            },
        )
        return OfferStrategyBuilder.preview(pseudo_spec)

    @staticmethod
    def _warnings(signals, competitor_context: dict, stock_context: dict) -> list[str]:
        warnings = []
        if "no marketplace performance data" in signals.missing_data:
            warnings.append("strategy_has_limited_marketplace_data")
        if competitor_context.get("pressure") == "price_pressure":
            warnings.append("competitor_price_pressure_requires_value_reason")
        if stock_context.get("stock_risk") == "low_stock":
            warnings.append("stock_risk_blocks_aggressive_cta")
        return warnings
