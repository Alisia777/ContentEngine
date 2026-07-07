from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.blogger_brief.blogger_persona_builder import BloggerPersonaBuilder
from app.blogger_brief.errors import BloggerBriefDataError
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.blogger_brief.scene_intent_builder import SceneIntentBuilder
from app.product_strategy import OfferStrategyBuilder, ProductStrategyBuilder


class MeaningSpecBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.personas = BloggerPersonaBuilder()
        self.reference_policy = ProductReferencePolicyService(db)
        self.scene_intents = SceneIntentBuilder()

    def build(
        self,
        product_id: int,
        *,
        platform: str = "Instagram Reels",
        duration_seconds: int = 8,
        demand_hypothesis_id: int | None = None,
        creative_spec_id: int | None = None,
        provider: str = "runway",
        product_identity_strict: bool = True,
    ) -> models.BloggerMeaningSpec:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise BloggerBriefDataError(f"Product {product_id} not found.")
        demand = self._demand(product_id, demand_hypothesis_id)
        creative_spec = self._creative_spec(product_id, creative_spec_id)
        strategy = ProductStrategyBuilder(self.db).latest_for_product(product_id)
        offer = OfferStrategyBuilder(self.db).latest_for_product(product_id)
        policy = self.reference_policy.check(
            product_id,
            provider=provider,
            product_identity_strict=product_identity_strict,
        )

        persona = self.personas.build(product, platform=platform)
        buyer_context = self._buyer_context(product, demand, strategy)
        proof_moment = self._proof_moment(product, policy.product_lock_mode, strategy)
        cta = self._cta(platform, offer, strategy)
        scene_intent = self.scene_intents.build(
            buyer_context=buyer_context,
            proof_moment=proof_moment,
            cta=cta,
            duration_seconds=duration_seconds,
        )
        warnings = list(dict.fromkeys(policy.warnings + ["human_review_required_for_real_provider_output"]))
        spec = models.BloggerMeaningSpec(
            product_id=product.id,
            sku=product.sku,
            demand_hypothesis_id=demand.id if demand else None,
            creative_spec_id=creative_spec.id if creative_spec else None,
            creator_persona_json=persona,
            buyer_context_json=buyer_context,
            blogger_story_json={
                "why_showing_product": "The creator frames the product as a personal find for a concrete routine moment.",
                "story_arc": "personal find -> buyer situation -> product reason -> proof/use-case -> natural CTA",
                "language": "first-person creator language",
                "product_strategy_spec_id": strategy.id if strategy else None,
                "offer_strategy_id": offer.id if offer else None,
            },
            authenticity_rules_json={
                "voice": "first person",
                "avoid": ["generic announcer copy", "fake authority", "unsupported claims", "visual identity verification claims"],
                "must_show": ["real product reference", "specific use case", "manual review before publishing"],
            },
            scene_intent_json=scene_intent,
            hook_options_json=self._hooks(product, buyer_context),
            proof_moment_json=proof_moment,
            cta_json=cta,
            product_lock_rules_json={
                "policy": policy.model_dump(mode="json"),
                "product_identity_strict": product_identity_strict,
                "product_lock_mode": policy.product_lock_mode,
                "do_not_generate_packaging": policy.product_lock_mode in {"packshot_overlay", "end_card_packshot"},
            },
            warnings_json=warnings,
        )
        self.db.add(spec)
        self.db.commit()
        self.db.refresh(spec)
        return spec

    def _demand(self, product_id: int, demand_hypothesis_id: int | None) -> models.DemandHypothesisRecord | None:
        if demand_hypothesis_id:
            demand = self.db.get(models.DemandHypothesisRecord, demand_hypothesis_id)
            if not demand:
                raise BloggerBriefDataError(f"DemandHypothesisRecord {demand_hypothesis_id} not found.")
            return demand
        return self.db.scalar(
            select(models.DemandHypothesisRecord)
            .where(models.DemandHypothesisRecord.product_id == product_id)
            .order_by(models.DemandHypothesisRecord.id.desc())
        )

    def _creative_spec(self, product_id: int, creative_spec_id: int | None) -> models.VideoCreativeSpecRecord | None:
        if creative_spec_id:
            spec = self.db.get(models.VideoCreativeSpecRecord, creative_spec_id)
            if not spec:
                raise BloggerBriefDataError(f"VideoCreativeSpecRecord {creative_spec_id} not found.")
            return spec
        return self.db.scalar(
            select(models.VideoCreativeSpecRecord)
            .where(models.VideoCreativeSpecRecord.product_id == product_id)
            .order_by(models.VideoCreativeSpecRecord.id.desc())
        )

    @staticmethod
    def _buyer_context(
        product: models.Product,
        demand: models.DemandHypothesisRecord | None,
        strategy: models.ProductStrategySpec | None,
    ) -> dict:
        hypothesis = demand.hypothesis_json if demand else {}
        strategy_situation = strategy.buyer_situation_json if strategy else {}
        return {
            "buyer_situation": strategy_situation.get("desire") or hypothesis.get("buyer_need") or f"Buyer is considering {product.title}.",
            "trigger_situation": strategy_situation.get("situation")
            or hypothesis.get("trigger_situation")
            or "A quick routine moment where the product needs to be easy to understand.",
            "pain_or_desire": strategy_situation.get("pain") or hypothesis.get("pain_point") or "The ad must explain why this product is useful now.",
            "objection": strategy_situation.get("objection") or hypothesis.get("objection") or "Why this product instead of another option?",
            "safe_promise": hypothesis.get("safe_promise") or "Clear product fit without unsupported claims.",
            "source_refs": hypothesis.get("source_refs") or ["product_field:description"],
            "product_strategy_spec_id": strategy.id if strategy else None,
            "offer_strategy": (strategy.offer_strategy_json if strategy else {}),
        }

    @staticmethod
    def _proof_moment(product: models.Product, product_lock_mode: str, strategy: models.ProductStrategySpec | None) -> dict:
        proof_required = strategy.proof_required_json if strategy else []
        proof_line = "I show the real pack, then the texture/use moment without changing the packaging."
        if proof_required:
            proof_line = str(proof_required[0].get("proof") if isinstance(proof_required[0], dict) else proof_required[0])
        return {
            "proof_type": "reference-backed product use case",
            "proof_line": proof_line,
            "product_lock_mode": product_lock_mode,
            "asset_requirement": "Use exact packshot or approved references for package identity.",
            "product_title": product.title,
            "proof_required": proof_required,
            "product_strategy_spec_id": strategy.id if strategy else None,
        }

    @staticmethod
    def _cta(platform: str, offer: models.OfferStrategy | None, strategy: models.ProductStrategySpec | None) -> dict:
        platform_rules = ((strategy.platform_strategy_json or {}).get("selected") if strategy else {}) or {}
        return {
            "platform": platform,
            "spoken_line": (offer.cta_strategy if offer else None) or "Check the product card if this fits your snack routine.",
            "caption": platform_rules.get("cta") or "See product card",
            "style": "natural, low-pressure, creator-led",
            "offer_strategy_id": offer.id if offer else None,
            "offer_type": offer.offer_type if offer else None,
            "platform_rules": platform_rules,
        }

    @staticmethod
    def _hooks(product: models.Product, buyer_context: dict) -> list[dict]:
        return [
            {
                "hook": f"I found {product.brand} for this exact routine moment.",
                "type": "personal_find",
            },
            {
                "hook": buyer_context["pain_or_desire"],
                "type": "buyer_context",
            },
        ]
