from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ai_brief_contract.errors import AIBriefContractDataError
from app.ai_brief_contract.types import BriefQualityCheckOutput
from app.creative_quality.rubric import GENERIC_AD_PHRASES


class BriefQualityChecker:
    def __init__(self, db: Session):
        self.db = db

    def check(self, ai_production_brief_id: int) -> models.BriefQualityCheck:
        brief = self.db.get(models.AIProductionBrief, ai_production_brief_id)
        if not brief:
            raise AIBriefContractDataError(f"AIProductionBrief {ai_production_brief_id} not found.")
        missing = []
        for key in [
            "one_sentence_thesis",
            "viewer_takeaway",
            "buyer_situation",
            "proof_moment",
            "product_lock_mode",
            "failure_conditions_json",
        ]:
            value = getattr(brief, key)
            if not value:
                missing.append(key)
        if not brief.scene_blueprints:
            missing.append("scene_blueprint")
        if not brief.cta:
            missing.append("cta")

        weak_points = []
        text = self._brief_text(brief)
        if any(phrase in text for phrase in GENERIC_AD_PHRASES):
            weak_points.append("generic_ad_language")
        if any(not scene.product_visibility for scene in brief.scene_blueprints):
            weak_points.append("product_visibility_unclear")

        failure_risks = []
        policy = brief.reference_requirements_json or {}
        if not policy.get("strict_real_generation_allowed"):
            failure_risks.append("reference_policy_not_passed")
        if brief.product_lock_mode == "packshot_overlay" and not any("overlay" in (scene.product_visibility or "") for scene in brief.scene_blueprints):
            failure_risks.append("overlay_policy_missing")

        required_fixes = [*missing, *weak_points, *failure_risks]
        score = max(0, 100 - 10 * len(missing) - 8 * len(weak_points) - 8 * len(failure_risks))
        status = "passed" if not required_fixes else "blocked"
        check = models.BriefQualityCheck(
            ai_production_brief_id=brief.id,
            status=status,
            score=score,
            missing_fields_json=missing,
            weak_points_json=weak_points,
            failure_risks_json=failure_risks,
            required_fixes_json=required_fixes,
        )
        self.db.add(check)
        brief.status = "ready" if status == "passed" else "blocked"
        self.db.commit()
        self.db.refresh(check)
        return check

    def latest_for_brief(self, ai_production_brief_id: int) -> models.BriefQualityCheck | None:
        return self.db.scalar(
            select(models.BriefQualityCheck)
            .where(models.BriefQualityCheck.ai_production_brief_id == ai_production_brief_id)
            .order_by(models.BriefQualityCheck.id.desc())
        )

    @staticmethod
    def as_output(check: models.BriefQualityCheck) -> BriefQualityCheckOutput:
        return BriefQualityCheckOutput(
            id=check.id,
            ai_production_brief_id=check.ai_production_brief_id,
            status=check.status,
            score=check.score,
            missing_fields=check.missing_fields_json or [],
            weak_points=check.weak_points_json or [],
            failure_risks=check.failure_risks_json or [],
            required_fixes=check.required_fixes_json or [],
        )

    @staticmethod
    def _brief_text(brief: models.AIProductionBrief) -> str:
        scenes = " ".join(scene.spoken_line or "" for scene in brief.scene_blueprints)
        return " ".join(
            [
                brief.one_sentence_thesis or "",
                brief.viewer_takeaway or "",
                brief.reason_to_believe or "",
                brief.proof_moment or "",
                brief.cta or "",
                scenes,
            ]
        ).lower()
