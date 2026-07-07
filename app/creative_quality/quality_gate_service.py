from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.creative_quality.errors import CreativeQualityDataError
from app.creative_quality.rubric import REQUIRED_SCENE_ROLES
from app.creative_quality.script_rewriter import ScriptRewriter
from app.creative_quality.types import CreativeQualityGateStatus
from app.creative_quality.ugc_quality_scorer import UGCQualityScorer


class CreativeQualityGateService:
    def __init__(self, db: Session):
        self.db = db
        self.scorer = UGCQualityScorer(db)

    def gate(
        self,
        product_id: int,
        *,
        ugc_script_id: int | None = None,
        creative_variant_id: int | None = None,
        prompt_pack_id: int | None = None,
        provider: str = "runway",
    ) -> CreativeQualityGateStatus:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise CreativeQualityDataError(f"Product {product_id} not found.")
        script = self._script(product_id, ugc_script_id=ugc_script_id, creative_variant_id=creative_variant_id)
        policy = ProductReferencePolicyService(self.db).check(product_id, provider=provider)

        blockers: list[str] = []
        warnings = list(policy.warnings or [])
        rewrite_request_id = None
        score = None
        if not policy.strict_real_generation_allowed:
            blockers.extend([f"reference_policy:{item}" for item in (policy.blockers or ["strict_real_generation_not_allowed"])])
        if not policy.product_lock_mode:
            blockers.append("product_lock_missing")

        if not script:
            blockers.append("ugc_script_required")
        else:
            score = self.scorer.latest_for_script(script.id)
            if not score:
                score = self.scorer.score_script(script.id, prompt_pack_id=prompt_pack_id)
            elif prompt_pack_id and score.prompt_pack_id != prompt_pack_id:
                score.prompt_pack_id = prompt_pack_id
                self.db.commit()
                self.db.refresh(score)
            missing_roles = self._missing_roles(script)
            if missing_roles:
                blockers.append("incomplete_scene_roles:" + ",".join(missing_roles))
            if score.status != "passed":
                blockers.extend([f"creative_quality:{reason}" for reason in (score.reasons_json or ["score_below_threshold"])])
                rewrite_request_id = ScriptRewriter(self.db).create_request(score.id).id
            elif missing_roles:
                rewrite_request_id = ScriptRewriter(self.db).create_request(
                    score.id,
                    reason="incomplete_scene_roles",
                    feedback="Complete required UGC scene roles before real smoke.",
                ).id

        real_smoke_allowed = not blockers and score is not None and score.status == "passed"
        status = "passed" if real_smoke_allowed else "blocked"
        next_action = "run_limited_real_smoke" if real_smoke_allowed else self._next_action(blockers)
        quality_output = self.scorer.as_output(score).model_dump(mode="json") if score else None
        return CreativeQualityGateStatus(
            product_id=product.id,
            sku=product.sku,
            ugc_script_id=script.id if script else None,
            quality_score_id=score.id if score else None,
            status=status,
            real_smoke_allowed=real_smoke_allowed,
            next_action=next_action,
            blockers=list(dict.fromkeys(blockers)),
            warnings=warnings,
            reference_policy=policy.model_dump(mode="json"),
            creative_quality_score=quality_output,
            rewrite_request_id=rewrite_request_id,
        )

    def latest_script_for_variant(self, creative_variant_id: int) -> models.UGCAdScript | None:
        return self.db.scalar(
            select(models.UGCAdScript)
            .where(models.UGCAdScript.creative_variant_id == creative_variant_id)
            .order_by(models.UGCAdScript.id.desc())
        )

    def latest_script_for_product(self, product_id: int) -> models.UGCAdScript | None:
        return self.db.scalar(
            select(models.UGCAdScript)
            .join(models.BloggerMeaningSpec)
            .where(models.BloggerMeaningSpec.product_id == product_id)
            .order_by(models.UGCAdScript.id.desc())
        )

    def _script(
        self,
        product_id: int,
        *,
        ugc_script_id: int | None,
        creative_variant_id: int | None,
    ) -> models.UGCAdScript | None:
        if ugc_script_id:
            script = self.db.get(models.UGCAdScript, ugc_script_id)
            if not script:
                raise CreativeQualityDataError(f"UGCAdScript {ugc_script_id} not found.")
            return script
        if creative_variant_id:
            script = self.latest_script_for_variant(creative_variant_id)
            if script:
                return script
        return self.latest_script_for_product(product_id)

    @staticmethod
    def _missing_roles(script: models.UGCAdScript) -> list[str]:
        roles = {scene.get("role") for scene in (script.scene_script_json or []) if scene.get("role")}
        return [role for role in REQUIRED_SCENE_ROLES if role not in roles]

    @staticmethod
    def _next_action(blockers: list[str]) -> str:
        blocker_text = " ".join(blockers)
        if "reference_policy" in blocker_text or "product_lock_missing" in blocker_text:
            return "add_product_references"
        if "creative_quality" in blocker_text or "incomplete_scene_roles" in blocker_text or "ugc_script_required" in blocker_text:
            return "rewrite_ugc_script"
        return "review_gate_blockers"
