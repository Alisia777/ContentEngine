from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.creative_quality.ugc_quality_scorer import UGCQualityScorer
from app.creative_workbench.errors import CreativeWorkbenchDataError, CreativeWorkbenchGuardrailError
from app.creative_workbench.prompt_preview_service import PromptPreviewService
from app.creative_workbench.readiness_service import ReadinessService
from app.creative_workbench.types import BriefApprovalOutput, WorkbenchReadiness, WorkbenchSessionOutput
from app.product_strategy import OfferStrategyBuilder, ProductStrategyBuilder


class WorkbenchService:
    def __init__(self, db: Session):
        self.db = db
        self.strategy_builder = ProductStrategyBuilder(db)
        self.offer_builder = OfferStrategyBuilder(db)
        self.scorer = UGCQualityScorer(db)

    def build(
        self,
        product_id: int,
        *,
        platform: str = "Instagram Reels",
        ugc_script_id: int | None = None,
        prompt_pack_id: int | None = None,
    ) -> models.CreativeWorkbenchSession:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise CreativeWorkbenchDataError(f"Product {product_id} not found.")
        strategy = self.strategy_builder.latest_for_product(product_id) or self.strategy_builder.build(product_id, platform=platform)
        offer = self.offer_builder.latest_for_product(product_id) or self.offer_builder.build(strategy.id)
        script = self.db.get(models.UGCAdScript, ugc_script_id) if ugc_script_id else self._latest_script(product_id)
        meaning = script.blogger_meaning_spec if script else self._latest_meaning(product_id)
        prompt_pack = self.db.get(models.PromptPack, prompt_pack_id) if prompt_pack_id else self._latest_prompt_pack(product_id, script)
        score = self._latest_score(script.id) if script else None
        if script and not score:
            score = self.scorer.score_script(script.id, prompt_pack_id=prompt_pack.id if prompt_pack else None)
        elif score and prompt_pack and score.prompt_pack_id != prompt_pack.id:
            score.prompt_pack_id = prompt_pack.id
            self.db.commit()
            self.db.refresh(score)

        readiness = ReadinessService(self.db).for_product(
            product_id,
            ugc_script_id=script.id if script else None,
            creative_quality_score_id=score.id if score else None,
            prompt_pack_id=prompt_pack.id if prompt_pack else None,
        )
        session = models.CreativeWorkbenchSession(
            product_id=product.id,
            sku=product.sku,
            product_strategy_spec_id=strategy.id if strategy else None,
            offer_strategy_id=offer.id if offer else None,
            blogger_meaning_spec_id=meaning.id if meaning else None,
            ugc_script_id=script.id if script else None,
            creative_quality_score_id=score.id if score else None,
            prompt_pack_id=prompt_pack.id if prompt_pack else None,
            status=self._status_from_readiness(readiness, score),
            blockers_json=readiness.blockers,
            next_actions_json=readiness.next_actions,
        )
        self.db.add(session)
        self.db.flush()
        session.summary_json = self._summary(session, readiness)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get(self, session_id: int) -> models.CreativeWorkbenchSession:
        session = self.db.get(models.CreativeWorkbenchSession, session_id)
        if not session:
            raise CreativeWorkbenchDataError(f"CreativeWorkbenchSession {session_id} not found.")
        return session

    def refresh(self, session_id: int) -> models.CreativeWorkbenchSession:
        session = self.get(session_id)
        score = self._latest_score(session.ugc_script_id) if session.ugc_script_id else None
        if score:
            session.creative_quality_score_id = score.id
        readiness = ReadinessService(self.db).for_session(session.id)
        session.status = self._status_from_readiness(readiness, score or session.creative_quality_score)
        session.blockers_json = readiness.blockers
        session.next_actions_json = readiness.next_actions
        session.summary_json = self._summary(session, readiness)
        self.db.commit()
        self.db.refresh(session)
        return session

    def score(self, session_id: int) -> models.CreativeQualityScore:
        session = self.get(session_id)
        if not session.ugc_script_id:
            raise CreativeWorkbenchDataError("Workbench session is missing UGCAdScript.")
        score = self.scorer.score_script(session.ugc_script_id, prompt_pack_id=session.prompt_pack_id)
        session.creative_quality_score_id = score.id
        self.db.commit()
        self.refresh(session.id)
        return score

    def approve_for_smoke(
        self,
        session_id: int,
        *,
        reviewer_name: str,
        notes: str | None = None,
    ) -> BriefApprovalOutput:
        session = self.refresh(session_id)
        readiness = ReadinessService(self.db).for_session(session.id)
        if not readiness.real_smoke_allowed:
            raise CreativeWorkbenchGuardrailError("Cannot approve for smoke until all readiness gates pass.")
        approval = models.CreativeBriefApproval(
            workbench_session_id=session.id,
            reviewer_name=reviewer_name,
            status="approved",
            notes=notes,
            approved_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(approval)
        session.status = "approved_for_smoke"
        self.db.commit()
        self.db.refresh(approval)
        self.db.refresh(session)
        return BriefApprovalOutput(
            session_id=session.id,
            approval_id=approval.id,
            reviewer_name=approval.reviewer_name,
            status=approval.status,
            notes=approval.notes,
            approved_at=approval.approved_at.isoformat() if approval.approved_at else None,
        )

    def as_output(self, session: models.CreativeWorkbenchSession) -> WorkbenchSessionOutput:
        readiness = ReadinessService(self.db).for_session(session.id)
        prompt_preview = PromptPreviewService(self.db).preview(session.id).model_dump(mode="json")
        strategy_scorecard = self._strategy_scorecard(session.product_strategy_spec)
        output = WorkbenchSessionOutput(
            id=session.id,
            product_id=session.product_id,
            sku=session.sku,
            status=session.status,
            product_strategy_spec_id=session.product_strategy_spec_id,
            offer_strategy_id=session.offer_strategy_id,
            blogger_meaning_spec_id=session.blogger_meaning_spec_id,
            ugc_script_id=session.ugc_script_id,
            creative_quality_score_id=session.creative_quality_score_id,
            prompt_pack_id=session.prompt_pack_id,
            strategy_scorecard=strategy_scorecard,
            offer_logic=self._offer_logic(session.offer_strategy),
            ugc_script_preview=self._ugc_script_preview(session.ugc_script),
            scene_intent_table=self._scene_intent_table(session.blogger_meaning_spec, session.ugc_script),
            creative_quality_breakdown=self._creative_quality_breakdown(session.creative_quality_score),
            prompt_preview=prompt_preview,
            real_smoke_readiness=readiness,
            blockers=readiness.blockers,
            next_actions=readiness.next_actions,
            approvals=[self._approval_row(item) for item in session.approvals],
            summary=session.summary_json or {},
        )
        return output

    def _summary(self, session: models.CreativeWorkbenchSession, readiness: WorkbenchReadiness) -> dict[str, Any]:
        return {
            "status": session.status,
            "product_lock_mode": readiness.product_lock_mode,
            "real_smoke_allowed": readiness.real_smoke_allowed,
            "blocker_count": len(readiness.blockers),
            "next_action": readiness.next_actions[0] if readiness.next_actions else None,
        }

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

    def _latest_score(self, ugc_script_id: int | None) -> models.CreativeQualityScore | None:
        if not ugc_script_id:
            return None
        return self.db.scalar(
            select(models.CreativeQualityScore)
            .where(models.CreativeQualityScore.ugc_script_id == ugc_script_id)
            .order_by(models.CreativeQualityScore.id.desc())
        )

    def _latest_prompt_pack(self, product_id: int, script: models.UGCAdScript | None) -> models.PromptPack | None:
        if script and script.creative_variant_id:
            generation_variant = self.db.scalar(
                select(models.VideoGenerationVariant)
                .where(models.VideoGenerationVariant.creative_variant_id == script.creative_variant_id)
                .where(models.VideoGenerationVariant.prompt_pack_id.is_not(None))
                .order_by(models.VideoGenerationVariant.id.desc())
            )
            if generation_variant and generation_variant.prompt_pack:
                return generation_variant.prompt_pack
        generation_variant = self.db.scalar(
            select(models.VideoGenerationVariant)
            .join(models.VideoCreativeSpecRecord)
            .where(models.VideoCreativeSpecRecord.product_id == product_id)
            .where(models.VideoGenerationVariant.prompt_pack_id.is_not(None))
            .order_by(models.VideoGenerationVariant.id.desc())
        )
        return generation_variant.prompt_pack if generation_variant else None

    @staticmethod
    def _status_from_readiness(
        readiness: WorkbenchReadiness,
        score: models.CreativeQualityScore | None,
    ) -> str:
        if readiness.real_smoke_allowed:
            return "ready"
        if score and score.status in {"needs_rewrite", "blocked"}:
            return "needs_rewrite"
        if readiness.blockers:
            return "blocked"
        return "draft"

    @staticmethod
    def _strategy_scorecard(spec: models.ProductStrategySpec | None) -> dict[str, Any]:
        if not spec:
            return {"status": "needs_data", "items": []}
        fields = {
            "buyer_segment": spec.buyer_segment_json,
            "buyer_situation": spec.buyer_situation_json,
            "purchase_trigger": spec.purchase_trigger,
            "main_pain": spec.main_pain,
            "main_objection": spec.main_objection,
            "product_role": spec.product_role,
            "offer_strategy": spec.offer_strategy_json,
            "proof_required": spec.proof_required_json,
            "platform_strategy": spec.platform_strategy_json,
        }
        return {
            "status": "ready" if all(bool(value) for value in fields.values()) else "needs_data",
            "items": [
                {"key": key, "label": key.replace("_", " "), "present": bool(value), "value": value}
                for key, value in fields.items()
            ],
            "warnings": spec.warnings_json or [],
        }

    @staticmethod
    def _offer_logic(offer: models.OfferStrategy | None) -> dict[str, Any]:
        if not offer:
            return {"status": "missing"}
        return {
            "status": offer.status,
            "offer_type": offer.offer_type,
            "price_message": offer.price_message,
            "discount_message": offer.discount_message,
            "value_reason": offer.value_reason,
            "competitor_response": offer.competitor_response,
            "stock_warning": offer.stock_warning,
            "cta_strategy": offer.cta_strategy,
            "warnings": offer.warnings_json or [],
        }

    @staticmethod
    def _ugc_script_preview(script: models.UGCAdScript | None) -> dict[str, Any]:
        if not script:
            return {"status": "missing", "scenes": []}
        return {
            "id": script.id,
            "status": script.status,
            "duration_seconds": script.duration_seconds,
            "voiceover": script.voiceover_json or {},
            "captions": script.captions_json or {},
            "scenes": script.scene_script_json or [],
        }

    @staticmethod
    def _scene_intent_table(
        meaning: models.BloggerMeaningSpec | None,
        script: models.UGCAdScript | None,
    ) -> list[dict[str, Any]]:
        intents = meaning.scene_intent_json if meaning else []
        script_scenes = script.scene_script_json if script else []
        rows = []
        max_rows = max(len(intents), len(script_scenes))
        for index in range(max_rows):
            intent = intents[index] if index < len(intents) else {}
            scene = script_scenes[index] if index < len(script_scenes) else {}
            rows.append(
                {
                    "scene_number": scene.get("scene_number") or intent.get("scene_number") or index + 1,
                    "role": scene.get("role") or intent.get("role"),
                    "intent": intent.get("intent") or intent.get("goal") or intent,
                    "spoken_line": scene.get("spoken_line"),
                    "caption": scene.get("caption"),
                    "proof_moment": scene.get("proof_moment") or (meaning.proof_moment_json if meaning else {}),
                }
            )
        return rows

    def _creative_quality_breakdown(self, score: models.CreativeQualityScore | None) -> dict[str, Any]:
        if not score:
            return {"status": "missing", "total_score": None, "breakdown": [], "reasons": [], "required_fixes": []}
        output = self.scorer.as_output(score)
        return output.model_dump(mode="json")

    @staticmethod
    def _approval_row(approval: models.CreativeBriefApproval) -> dict[str, Any]:
        return {
            "id": approval.id,
            "reviewer_name": approval.reviewer_name,
            "status": approval.status,
            "notes": approval.notes,
            "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
        }
