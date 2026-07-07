from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.creative_workbench.errors import CreativeWorkbenchDataError, CreativeWorkbenchGuardrailError
from app.creative_workbench.types import BriefPatch
from app.creative_workbench.workbench_service import WorkbenchService


class BriefEditorService:
    ALLOWED_FIELDS = set(BriefPatch.model_fields)
    BLOCKED_FIELDS = {
        "api_key",
        "provider_secret",
        "runway_secret",
        "token",
        "real_smoke_allowed",
        "strict_real_generation_allowed",
        "reference_policy_passed",
        "reference_status",
        "review_status",
        "product_reference_approval_status",
        "creative_quality_passed",
        "quality_score_status",
        "product_lock_mode",
        "status",
        "approved_for_smoke",
    }

    def __init__(self, db: Session):
        self.db = db

    def patch(self, session_id: int, payload: dict[str, Any]) -> models.CreativeWorkbenchSession:
        illegal = set(payload) - self.ALLOWED_FIELDS
        blocked = set(payload).intersection(self.BLOCKED_FIELDS)
        if illegal or blocked:
            raise CreativeWorkbenchGuardrailError(
                "Brief editor can only patch safe creative brief fields, not gates, secrets, or asset approvals."
            )
        session = WorkbenchService(self.db).get(session_id)
        patch = BriefPatch(**payload)
        if not session.product_strategy_spec:
            raise CreativeWorkbenchDataError("Workbench session is missing ProductStrategySpec.")
        self._patch_strategy(session.product_strategy_spec, patch)
        if session.blogger_meaning_spec:
            self._patch_meaning(session.blogger_meaning_spec, patch)
        self.db.commit()
        return WorkbenchService(self.db).refresh(session.id)

    @staticmethod
    def _patch_strategy(spec: models.ProductStrategySpec, patch: BriefPatch) -> None:
        if patch.buyer_situation is not None:
            buyer_situation = deepcopy(spec.buyer_situation_json or {})
            buyer_situation["operator_note"] = patch.buyer_situation
            buyer_situation["situation"] = patch.buyer_situation
            spec.buyer_situation_json = buyer_situation
        if patch.main_objection is not None:
            spec.main_objection = patch.main_objection
        if patch.platform_angle is not None:
            platform = deepcopy(spec.platform_strategy_json or {})
            platform["operator_angle"] = patch.platform_angle
            spec.platform_strategy_json = platform
        if patch.product_reason is not None:
            spec.product_role = patch.product_reason
        if patch.must_include is not None or patch.must_avoid is not None:
            angles = list(spec.content_angles_json or [])
            angles.append(
                {
                    "angle": "operator_brief_patch",
                    "must_include": patch.must_include or [],
                    "must_avoid": patch.must_avoid or [],
                }
            )
            spec.content_angles_json = angles

    @staticmethod
    def _patch_meaning(meaning: models.BloggerMeaningSpec, patch: BriefPatch) -> None:
        if patch.proof_moment is not None:
            proof = deepcopy(meaning.proof_moment_json or {})
            proof["operator_note"] = patch.proof_moment
            proof["proof_line"] = patch.proof_moment
            meaning.proof_moment_json = proof
        if patch.cta is not None:
            cta = deepcopy(meaning.cta_json or {})
            cta["operator_note"] = patch.cta
            cta["spoken_line"] = patch.cta
            meaning.cta_json = cta
        if patch.creator_persona is not None:
            persona = deepcopy(meaning.creator_persona_json or {})
            persona["operator_note"] = patch.creator_persona
            persona["persona"] = patch.creator_persona
            meaning.creator_persona_json = persona
        if patch.product_reason is not None:
            story = deepcopy(meaning.blogger_story_json or {})
            story["product_reason"] = patch.product_reason
            meaning.blogger_story_json = story
        if patch.must_include is not None or patch.must_avoid is not None:
            rules = deepcopy(meaning.authenticity_rules_json or {})
            rules["must_include"] = patch.must_include or rules.get("must_include") or []
            rules["must_avoid"] = patch.must_avoid or rules.get("must_avoid") or []
            meaning.authenticity_rules_json = rules
