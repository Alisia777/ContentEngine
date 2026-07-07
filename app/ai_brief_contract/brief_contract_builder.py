from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ai_brief_contract.errors import AIBriefContractDataError
from app.ai_brief_contract.markdown_renderer import MarkdownRenderer
from app.blogger_brief import MeaningSpecBuilder, ProductReferencePolicyService, UGCAdScriptBuilder
from app.creative_quality import UGCQualityScorer
from app.product_strategy import OfferStrategyBuilder, ProductStrategyBuilder


class AIProductionBriefBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(
        self,
        product_id: int,
        *,
        platform: str = "Instagram Reels",
        ugc_script_id: int | None = None,
    ) -> models.AIProductionBrief:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise AIBriefContractDataError(f"Product {product_id} not found.")
        strategy = ProductStrategyBuilder(self.db).latest_for_product(product_id) or ProductStrategyBuilder(self.db).build(
            product_id,
            platform=platform,
        )
        offer = OfferStrategyBuilder(self.db).latest_for_product(product_id) or OfferStrategyBuilder(self.db).build(strategy.id)
        script = self.db.get(models.UGCAdScript, ugc_script_id) if ugc_script_id else self._latest_script(product_id)
        if not script:
            meaning = MeaningSpecBuilder(self.db).build(product_id, duration_seconds=15, provider="runway")
            script = UGCAdScriptBuilder(self.db).build(meaning.id, duration_seconds=15)
        meaning = script.blogger_meaning_spec
        score = UGCQualityScorer(self.db).latest_for_script(script.id) or UGCQualityScorer(self.db).score_script(script.id)
        policy = ProductReferencePolicyService(self.db).check(product_id, provider="runway")

        proof_moment = (meaning.proof_moment_json or {}).get("proof_line") or self._proof_required(strategy)
        cta = offer.cta_strategy or (meaning.cta_json or {}).get("spoken_line") or "Check the product card if this fits your routine."
        must_say = [scene.get("spoken_line") for scene in (script.scene_script_json or []) if scene.get("spoken_line")]
        must_show = self._must_show(strategy, meaning, policy.product_lock_mode)
        must_avoid = self._must_avoid(strategy, policy.product_lock_mode)
        failure_conditions = [
            "packaging is redrawn or changed",
            "label text is invented or unreadable",
            "logo, color, proportions, or product scale drift",
            "no proof moment",
            "no personal creator context",
            "generic ad voice or commercial announcer tone",
            "unsupported or medical claim appears",
        ]
        thesis = self._thesis(product, strategy, offer)
        brief_json = {
            "product_title": product.title,
            "offer_type": offer.offer_type,
            "product_role": strategy.product_role,
            "creator_persona": meaning.creator_persona_json or {},
            "scene_roles": [scene.get("role") for scene in (script.scene_script_json or [])],
            "quality_score_id": score.id,
            "quality_status": score.status,
        }
        brief = models.AIProductionBrief(
            product_id=product.id,
            sku=product.sku,
            product_strategy_spec_id=strategy.id,
            offer_strategy_id=offer.id,
            blogger_meaning_spec_id=meaning.id,
            ugc_script_id=script.id,
            creative_quality_score_id=score.id,
            status="draft",
            platform=platform,
            format="short_video",
            one_sentence_thesis=thesis,
            viewer_takeaway=self._viewer_takeaway(strategy, offer),
            buyer_situation=(strategy.buyer_situation_json or {}).get("situation") or (meaning.buyer_context_json or {}).get("buyer_situation"),
            main_objection=strategy.main_objection,
            reason_to_believe=offer.value_reason or strategy.product_role,
            proof_moment=proof_moment,
            cta=cta,
            must_show_json=must_show,
            must_say_json=must_say,
            must_avoid_json=must_avoid,
            product_identity_rules_json=self._identity_rules(policy.product_lock_mode),
            product_lock_mode=policy.product_lock_mode,
            reference_requirements_json=policy.model_dump(mode="json"),
            scene_count=5,
            duration_seconds=15,
            failure_conditions_json=failure_conditions,
            brief_json=brief_json,
            warnings_json=list(dict.fromkeys([*(strategy.warnings_json or []), *(policy.warnings or [])])),
        )
        self.db.add(brief)
        self.db.flush()
        brief.brief_markdown = MarkdownRenderer().render(brief)
        self.db.commit()
        self.db.refresh(brief)
        return brief

    def latest_for_product(self, product_id: int) -> models.AIProductionBrief | None:
        return self.db.scalar(
            select(models.AIProductionBrief)
            .where(models.AIProductionBrief.product_id == product_id)
            .order_by(models.AIProductionBrief.id.desc())
        )

    def as_output(self, brief: models.AIProductionBrief):
        from app.ai_brief_contract.types import AIProductionBriefOutput

        return AIProductionBriefOutput(
            id=brief.id,
            product_id=brief.product_id,
            sku=brief.sku,
            status=brief.status,
            platform=brief.platform,
            format=brief.format,
            one_sentence_thesis=brief.one_sentence_thesis,
            viewer_takeaway=brief.viewer_takeaway,
            buyer_situation=brief.buyer_situation,
            main_objection=brief.main_objection,
            reason_to_believe=brief.reason_to_believe,
            proof_moment=brief.proof_moment,
            cta=brief.cta,
            product_lock_mode=brief.product_lock_mode,
            reference_requirements=brief.reference_requirements_json or {},
            must_show=brief.must_show_json or [],
            must_say=brief.must_say_json or [],
            must_avoid=brief.must_avoid_json or [],
            failure_conditions=brief.failure_conditions_json or [],
            scene_count=brief.scene_count,
            duration_seconds=brief.duration_seconds,
            brief=brief.brief_json or {},
            brief_markdown=brief.brief_markdown,
            warnings=brief.warnings_json or [],
        )

    def _latest_script(self, product_id: int) -> models.UGCAdScript | None:
        return self.db.scalar(
            select(models.UGCAdScript)
            .join(models.BloggerMeaningSpec)
            .where(models.BloggerMeaningSpec.product_id == product_id)
            .order_by(models.UGCAdScript.id.desc())
        )

    @staticmethod
    def _thesis(product: models.Product, strategy: models.ProductStrategySpec, offer: models.OfferStrategy) -> str:
        offer_type = offer.offer_type or "value"
        return f"{product.title} is positioned as a {offer_type} choice for the buyer situation: {strategy.product_role}"

    @staticmethod
    def _viewer_takeaway(strategy: models.ProductStrategySpec, offer: models.OfferStrategy) -> str:
        return f"In the first 3 seconds, the viewer should understand the situation and why this product is worth {offer.offer_type} consideration."

    @staticmethod
    def _proof_required(strategy: models.ProductStrategySpec) -> str:
        proof = strategy.proof_required_json or []
        if proof:
            first = proof[0]
            if isinstance(first, dict):
                return first.get("proof") or first.get("scene_use") or str(first)
            return str(first)
        return "Show real product context without changing packaging."

    @staticmethod
    def _must_show(strategy: models.ProductStrategySpec, meaning: models.BloggerMeaningSpec, lock_mode: str) -> list[str]:
        items = [
            "creator personal context",
            "clear product reason",
            "proof/use-case demo",
            "low-pressure CTA",
            f"product visibility policy:{lock_mode}",
        ]
        for proof in strategy.proof_required_json or []:
            items.append(str(proof.get("scene_use") or proof.get("proof") or proof) if isinstance(proof, dict) else str(proof))
        if meaning.proof_moment_json:
            items.append(str(meaning.proof_moment_json.get("proof_line") or meaning.proof_moment_json))
        return list(dict.fromkeys(item for item in items if item))

    @staticmethod
    def _must_avoid(strategy: models.ProductStrategySpec, lock_mode: str) -> list[str]:
        items = [
            "fake label",
            "distorted text",
            "changed packaging",
            "wrong logo",
            "invented brand text",
            "unreadable label",
            "different product",
            "warped package",
            "wrong proportions",
            "scale mismatch",
            "generic ad voice",
            "commercial announcer tone",
            "unsupported claims",
            f"do not bypass product lock mode:{lock_mode}",
        ]
        items.extend(strategy.forbidden_claims_json or [])
        return list(dict.fromkeys(item for item in items if item))

    @staticmethod
    def _identity_rules(lock_mode: str) -> dict:
        return {
            "product_lock_mode": lock_mode,
            "preserve": ["logo", "label", "colors", "packaging proportions", "product scale"],
            "human_review_required": True,
            "visual_identity_verification": "not_claimed",
        }
