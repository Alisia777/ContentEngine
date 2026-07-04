from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.demand.demand_signal_builder import DemandSignalBuilder
from app.demand.demand_validator import DemandValidator, UNSAFE_PROMISE_TERMS
from app.demand.errors import DemandDataError
from app.demand.scoring import select_demand_rule
from app.demand.types import DemandHypothesis, DemandSignalSet


class DemandHypothesisBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_for_product(self, product_id: int) -> models.DemandHypothesisRecord:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise DemandDataError(f"Product {product_id} not found.")
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        )
        signals = DemandSignalBuilder(self.db).build(product_id)
        rule = select_demand_rule(signals.flags)
        claim, claim_refs = self._safe_claim(signals, brand_guide)
        source_refs = list(dict.fromkeys(claim_refs + self._evidence_refs(signals)))
        missing_data = list(signals.missing_data)
        if not claim_refs:
            missing_data.append("missing_source_backed_product_claim")
        objection = signals.buyer_objections[0] if signals.buyer_objections else rule.default_objection
        unsafe_blocked = self._blocked_promises(product, brand_guide)
        hypothesis = DemandHypothesis(
            product_id=product.id,
            sku=product.sku,
            product_title=product.title,
            need_type=rule.need_type,
            buyer_need=rule.buyer_need,
            trigger_situation=rule.trigger_situation,
            pain_point=rule.pain_point,
            objection=objection,
            safe_promise=claim,
            unsafe_promises_blocked=unsafe_blocked,
            proof_required=[claim] if claim_refs else [],
            recommended_hook_types=rule.recommended_hook_types,
            recommended_first_frame=rule.recommended_first_frame,
            source_refs=source_refs,
            missing_data=list(dict.fromkeys(missing_data)),
            performance_flags=signals.performance_flags,
            market_risks=signals.market_risks,
            stock_risk=signals.stock_risk,
            buyer_language=signals.buyer_language,
            reasoning=self._reasoning(rule.rule_key, signals),
            source_map={
                **signals.source_map,
                "allowed_claim_refs": claim_refs,
                "demand_rule": rule.rule_key,
            },
        )
        validation = DemandValidator().validate(
            hypothesis,
            forbidden_claims=brand_guide.forbidden_claims_json if brand_guide else [],
        )
        hypothesis.validation_status = validation.status
        hypothesis.real_video_eligible = validation.real_video_eligible
        record = models.DemandHypothesisRecord(
            product_id=product.id,
            sku=product.sku,
            status=validation.status,
            need_type=hypothesis.need_type,
            buyer_need=hypothesis.buyer_need,
            hypothesis_json=hypothesis.model_dump(mode="json"),
            signals_json=signals.model_dump(mode="json"),
            validation_report_json=validation.model_dump(mode="json"),
            source_summary_json=hypothesis.source_map,
            warnings_json=list(dict.fromkeys(signals.warnings + validation.warnings)),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    @staticmethod
    def _safe_claim(signals: DemandSignalSet, brand_guide: models.BrandGuide | None) -> tuple[str, list[str]]:
        forbidden = " ".join((brand_guide.forbidden_claims_json if brand_guide else []) or []).lower()
        for claim in signals.allowed_claims:
            text = claim.claim.strip()
            lowered = text.lower()
            if not text:
                continue
            if any(term in lowered for term in UNSAFE_PROMISE_TERMS):
                continue
            if forbidden and lowered in forbidden:
                continue
            return text, [f"{claim.source_type}:{claim.source_key}"]
        return f"Show how {signals.product_title} fits a realistic use case.", []

    @staticmethod
    def _evidence_refs(signals: DemandSignalSet) -> list[str]:
        refs = [f"product:{signals.product_id}"]
        if signals.source_map.get("latest_metric"):
            refs.append(f"product_metric_snapshot:{signals.source_map['latest_metric']}")
        if signals.source_map.get("review_insight"):
            refs.append(f"product_review_insight:{signals.source_map['review_insight']}")
        refs.extend(f"market_signal:{item}" for item in signals.source_map.get("market_signals") or [])
        refs.extend(f"creative_performance_snapshot:{item}" for item in signals.source_map.get("creative_performance") or [])
        return refs

    @staticmethod
    def _blocked_promises(product: models.Product, brand_guide: models.BrandGuide | None) -> list[str]:
        blocked = ["medical treatment", "guaranteed result", "cure", "heal"]
        blocked.extend(str(item) for item in (product.restrictions_json or []))
        if brand_guide:
            blocked.extend(str(item) for item in (brand_guide.forbidden_claims_json or []))
        return list(dict.fromkeys(item for item in blocked if item))

    @staticmethod
    def _reasoning(rule_key: str, signals: DemandSignalSet) -> str:
        flags = ", ".join(signals.flags) or "no strong signal"
        if rule_key == "low_ctr":
            return f"CTR signal points to weak awareness. Flags: {flags}."
        if rule_key == "low_conversion":
            return f"Conversion signal points to trust and clarity friction. Flags: {flags}."
        if rule_key == "high_returns":
            return f"Return signal points to expectation-setting. Flags: {flags}."
        if rule_key == "competitor_price_pressure":
            return f"Market signal points to value comparison. Flags: {flags}."
        if rule_key == "stock_risk":
            return f"Stock risk requires soft education instead of aggressive demand generation. Flags: {flags}."
        return f"Data is limited, so the safest path is a simple source-backed use-case introduction. Flags: {flags}."
