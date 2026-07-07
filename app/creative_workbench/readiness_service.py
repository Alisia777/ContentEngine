from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.creative_workbench.errors import CreativeWorkbenchDataError
from app.creative_workbench.types import WorkbenchReadiness
from app.product_strategy import OfferStrategyBuilder, ProductStrategyBuilder


class ReadinessService:
    def __init__(self, db: Session):
        self.db = db

    def for_product(
        self,
        product_id: int,
        *,
        ugc_script_id: int | None = None,
        creative_quality_score_id: int | None = None,
        prompt_pack_id: int | None = None,
        provider: str = "runway",
    ) -> WorkbenchReadiness:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise CreativeWorkbenchDataError(f"Product {product_id} not found.")

        strategy = ProductStrategyBuilder(self.db).latest_for_product(product_id)
        offer = OfferStrategyBuilder(self.db).latest_for_product(product_id)
        meaning = self._latest_meaning(product_id)
        script = self.db.get(models.UGCAdScript, ugc_script_id) if ugc_script_id else self._latest_script(product_id)
        score = self.db.get(models.CreativeQualityScore, creative_quality_score_id) if creative_quality_score_id else None
        if not score and script:
            score = self._latest_score(script.id)
        prompt_pack = self.db.get(models.PromptPack, prompt_pack_id) if prompt_pack_id else None
        policy = ProductReferencePolicyService(self.db).check(product_id, provider=provider)

        blockers: list[str] = []
        next_actions: list[str] = []
        if not strategy:
            blockers.append("product_strategy_required")
            next_actions.append("build_product_strategy_spec")
        if not offer:
            blockers.append("offer_strategy_required")
            next_actions.append("build_offer_strategy")
        if not meaning:
            blockers.append("blogger_meaning_spec_required")
            next_actions.append("build_blogger_meaning_spec")
        if not script:
            blockers.append("ugc_script_required")
            next_actions.append("build_ugc_script")
        if not score:
            blockers.append("creative_quality_score_required")
            next_actions.append("score_ugc_script")
        elif score.status != "passed":
            blockers.extend([f"creative_quality:{reason}" for reason in (score.reasons_json or ["score_below_threshold"])])
            next_actions.append("rewrite_ugc_script")
        if not policy.strict_real_generation_allowed:
            blockers.extend([f"reference_policy:{item}" for item in (policy.blockers or ["strict_real_generation_not_allowed"])])
            next_actions.append("add_product_references")
        if not prompt_pack:
            blockers.append("prompt_pack_required")
            next_actions.append("build_prompt_pack")

        blockers = list(dict.fromkeys(blockers))
        next_actions = list(dict.fromkeys(next_actions or ["review_workbench"]))
        return WorkbenchReadiness(
            product_id=product.id,
            sku=product.sku,
            product_strategy_ready=bool(strategy and strategy.status == "ready"),
            offer_strategy_ready=bool(offer and offer.status == "ready"),
            blogger_meaning_ready=bool(meaning),
            ugc_script_ready=bool(script and script.status == "ready"),
            creative_quality_passed=bool(score and score.status == "passed"),
            reference_policy_passed=bool(policy.strict_real_generation_allowed),
            prompt_pack_ready=bool(prompt_pack),
            real_smoke_allowed=not blockers,
            product_lock_mode=policy.product_lock_mode,
            reference_policy=policy.model_dump(mode="json"),
            blockers=blockers,
            warnings=list(dict.fromkeys(policy.warnings or [])),
            next_actions=next_actions,
        )

    def for_session(self, session_id: int, *, provider: str = "runway") -> WorkbenchReadiness:
        session = self.db.get(models.CreativeWorkbenchSession, session_id)
        if not session:
            raise CreativeWorkbenchDataError(f"CreativeWorkbenchSession {session_id} not found.")
        return self.for_product(
            session.product_id,
            ugc_script_id=session.ugc_script_id,
            creative_quality_score_id=session.creative_quality_score_id,
            prompt_pack_id=session.prompt_pack_id,
            provider=provider,
        )

    def _latest_meaning(self, product_id: int) -> models.BloggerMeaningSpec | None:
        return self.db.scalar(
            select(models.BloggerMeaningSpec)
            .where(models.BloggerMeaningSpec.product_id == product_id)
            .order_by(models.BloggerMeaningSpec.id.desc())
        )

    def _latest_script(self, product_id: int) -> models.UGCAdScript | None:
        return self.db.scalar(
            select(models.UGCAdScript)
            .join(models.BloggerMeaningSpec)
            .where(models.BloggerMeaningSpec.product_id == product_id)
            .order_by(models.UGCAdScript.id.desc())
        )

    def _latest_score(self, ugc_script_id: int) -> models.CreativeQualityScore | None:
        return self.db.scalar(
            select(models.CreativeQualityScore)
            .where(models.CreativeQualityScore.ugc_script_id == ugc_script_id)
            .order_by(models.CreativeQualityScore.id.desc())
        )
