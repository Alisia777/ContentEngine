from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.creative_quality.errors import CreativeQualityDataError
from app.creative_quality.rubric import REASON_TO_FIX, REQUIRED_SCENE_ROLES
from app.creative_quality.types import CreativeRewriteBuildResult


class ScriptRewriter:
    def __init__(self, db: Session):
        self.db = db

    def create_request(
        self,
        creative_quality_score_id: int,
        *,
        feedback: str | None = None,
        reason: str = "quality_score_below_threshold",
    ) -> models.CreativeRewriteRequest:
        score = self.db.get(models.CreativeQualityScore, creative_quality_score_id)
        if not score:
            raise CreativeQualityDataError(f"CreativeQualityScore {creative_quality_score_id} not found.")
        if not score.ugc_script_id:
            raise CreativeQualityDataError("CreativeQualityScore is not linked to a UGCAdScript.")

        existing = self.db.scalar(
            select(models.CreativeRewriteRequest)
            .where(models.CreativeRewriteRequest.creative_quality_score_id == score.id)
            .where(models.CreativeRewriteRequest.status.in_(("requested", "rewritten")))
            .order_by(models.CreativeRewriteRequest.id.desc())
        )
        if existing:
            return existing

        request = models.CreativeRewriteRequest(
            creative_quality_score_id=score.id,
            ugc_script_id=score.ugc_script_id,
            product_id=score.product_id,
            status="requested",
            reason=reason,
            feedback=feedback,
            required_fixes_json=score.required_fixes_json or [],
            before_script_json={
                "scene_script": (score.ugc_script.scene_script_json if score.ugc_script else []),
                "voiceover": (score.ugc_script.voiceover_json if score.ugc_script else {}),
                "captions": (score.ugc_script.captions_json if score.ugc_script else {}),
            },
            rewrite_plan_json={
                "reason_codes": score.reasons_json or [],
                "fixes": score.required_fixes_json or [],
            },
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def build(self, rewrite_request_id: int) -> CreativeRewriteBuildResult:
        request = self.db.get(models.CreativeRewriteRequest, rewrite_request_id)
        if not request:
            raise CreativeQualityDataError(f"CreativeRewriteRequest {rewrite_request_id} not found.")
        source = request.ugc_script
        if not source:
            raise CreativeQualityDataError("CreativeRewriteRequest is missing source UGCAdScript.")
        meaning = source.blogger_meaning_spec
        if not meaning:
            raise CreativeQualityDataError("Source UGCAdScript is missing BloggerMeaningSpec.")

        before_lines = [str(scene.get("spoken_line") or "") for scene in (source.scene_script_json or [])]
        new_scenes = self._rewritten_scenes(source, meaning, request)
        after_lines = [str(scene.get("spoken_line") or "") for scene in new_scenes]
        new_script = models.UGCAdScript(
            blogger_meaning_spec_id=meaning.id,
            creative_variant_id=source.creative_variant_id,
            status="ready",
            duration_seconds=source.duration_seconds,
            voiceover_json={
                "language": (source.voiceover_json or {}).get("language", "ru"),
                "style": "first-person creator language",
                "lines": after_lines,
                "avoid": ["generic ad voice", "unsupported claims", "announcer tone"],
                "rewrite_source_ugc_script_id": source.id,
            },
            captions_json={
                "style": (source.captions_json or {}).get("style", "minimal"),
                "lines": [scene.get("caption", "") for scene in new_scenes],
                "generated_on_screen_text_allowed": False,
            },
            scene_script_json=new_scenes,
        )
        self.db.add(new_script)
        self.db.flush()
        request.status = "rewritten"
        request.new_ugc_script_id = new_script.id
        request.rewrite_plan_json = {
            **(request.rewrite_plan_json or {}),
            "built_new_ugc_script_id": new_script.id,
            "safe_promise_preserved": True,
        }
        if new_script.creative_variant_id:
            self._apply_rewrite_to_variant(new_script, meaning)
        self.db.commit()
        self.db.refresh(new_script)
        self.db.refresh(request)
        return CreativeRewriteBuildResult(
            rewrite_request_id=request.id,
            source_ugc_script_id=source.id,
            new_ugc_script_id=new_script.id,
            status=request.status,
            required_fixes=request.required_fixes_json or [],
            before_lines=before_lines,
            after_lines=after_lines,
        )

    def _rewritten_scenes(
        self,
        source: models.UGCAdScript,
        meaning: models.BloggerMeaningSpec,
        request: models.CreativeRewriteRequest,
    ) -> list[dict]:
        product = self.db.get(models.Product, meaning.product_id)
        product_title = product.title if product else meaning.sku
        buyer_context = meaning.buyer_context_json or {}
        proof = meaning.proof_moment_json or {}
        cta = meaning.cta_json or {}
        role_to_scene = {scene.get("role"): deepcopy(scene) for scene in (source.scene_script_json or []) if scene.get("role")}
        starts_at = 0
        duration = max(1, source.duration_seconds // max(1, len(REQUIRED_SCENE_ROLES)))
        rewritten: list[dict] = []
        for index, role in enumerate(REQUIRED_SCENE_ROLES, start=1):
            scene = role_to_scene.get(role) or {"role": role}
            scene["scene_number"] = index
            scene["starts_at"] = starts_at
            scene["duration_seconds"] = duration if index < len(REQUIRED_SCENE_ROLES) else max(1, source.duration_seconds - starts_at)
            scene["spoken_line"] = self._line_for_role(role, product_title, buyer_context, proof, cta)
            scene["caption"] = scene.get("caption") or self._caption_for_role(role)
            scene["visual_direction"] = scene.get("visual_direction") or self._visual_for_role(role)
            scene["proof_moment"] = proof
            scene["rewrite_request_id"] = request.id
            starts_at += scene["duration_seconds"]
            rewritten.append(scene)
        return rewritten

    @staticmethod
    def _line_for_role(role: str, product_title: str, buyer_context: dict, proof: dict, cta: dict) -> str:
        if role == "hook":
            return f"I found {product_title} for the moment when I need a quick, clear snack choice."
        if role == "personal_context":
            return "I usually reach for something like this between errands or after training, when I do not want a heavy snack."
        if role == "product_reason":
            reason = buyer_context.get("objection") or "I want to understand why this one fits my routine."
            return f"That is why I look at this exact product: {reason}"
        if role == "proof_demo":
            proof_line = proof.get("proof_line") or "I show the real pack and texture/use moment without changing the packaging."
            return proof_line
        if role == "cta":
            return cta.get("spoken_line") or "Check the product card if this fits your routine."
        return "I keep this as a natural creator note, not an announcer ad."

    @staticmethod
    def _caption_for_role(role: str) -> str:
        captions = {
            "hook": "Real snack moment",
            "personal_context": "Why I picked it",
            "product_reason": "Product reason",
            "proof_demo": "Real pack + texture",
            "cta": "See product card",
        }
        return captions.get(role, "")

    @staticmethod
    def _visual_for_role(role: str) -> str:
        visuals = {
            "hook": "Sporty creator holds the exact pack in a realistic vertical frame.",
            "personal_context": "Creator speaks in a real kitchen/gym-bag routine moment.",
            "product_reason": "Creator keeps package visible and points to safe, readable product details.",
            "proof_demo": "Creator shows exact packshot, texture, or bite/use moment without redrawing packaging.",
            "cta": "Creator ends with exact packshot/end-card and low-pressure CTA.",
        }
        return visuals.get(role, "Natural creator delivery.")

    def _apply_rewrite_to_variant(self, script: models.UGCAdScript, meaning: models.BloggerMeaningSpec) -> None:
        variant = self.db.get(models.CreativeVariant, script.creative_variant_id)
        if not variant:
            return
        variant.scene_plan_json = [
            {
                "scene_number": scene["scene_number"],
                "role": scene["role"],
                "starts_at": scene["starts_at"],
                "duration_seconds": scene["duration_seconds"],
                "visual": scene["visual_direction"],
                "caption": scene["caption"],
                "voiceover": scene["spoken_line"],
                "claim_refs": ["creative_quality_rewrite", "blogger_meaning_spec", "product_reference_policy"],
                "blogger_meaning_spec_id": meaning.id,
                "ugc_script_id": script.id,
                "product_lock_mode": scene.get("product_lock_mode") or (meaning.product_lock_rules_json or {}).get("product_lock_mode"),
                "proof_moment": scene.get("proof_moment"),
            }
            for scene in script.scene_script_json
        ]
        variant.risk_flags_json = list(dict.fromkeys([*(variant.risk_flags_json or []), "creative_quality_rewritten_ugc_script"]))
