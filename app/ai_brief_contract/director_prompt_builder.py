from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ai_brief_contract.errors import AIBriefContractDataError
from app.ai_brief_contract.scene_blueprint_builder import SceneBlueprintBuilder
from app.ai_brief_contract.types import DirectorPromptPackOutput, NEGATIVE_PROMPT_TERMS


class DirectorPromptBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, ai_production_brief_id: int) -> models.DirectorPromptPack:
        brief = self.db.get(models.AIProductionBrief, ai_production_brief_id)
        if not brief:
            raise AIBriefContractDataError(f"AIProductionBrief {ai_production_brief_id} not found.")
        scenes = sorted(brief.scene_blueprints, key=lambda item: item.scene_order)
        if not scenes:
            scenes = SceneBlueprintBuilder(self.db).build(brief.id)
        self.db.query(models.DirectorPromptPack).filter(
            models.DirectorPromptPack.ai_production_brief_id == brief.id
        ).delete()
        prompt_pack_id = brief.creative_quality_score.prompt_pack_id if brief.creative_quality_score else None
        provider_prompt = {
            "platform": brief.platform,
            "format": brief.format,
            "creator_persona": (brief.blogger_meaning_spec.creator_persona_json if brief.blogger_meaning_spec else {}) or {},
            "one_sentence_thesis": brief.one_sentence_thesis,
            "viewer_takeaway": brief.viewer_takeaway,
            "cta": brief.cta,
            "product_lock_mode": brief.product_lock_mode,
            "identity_constraints": brief.product_identity_rules_json or {},
            "scenes": [self._scene_prompt(scene, brief) for scene in scenes],
        }
        prompt = models.DirectorPromptPack(
            ai_production_brief_id=brief.id,
            prompt_pack_id=prompt_pack_id,
            status="ready",
            system_instruction=(
                "You are producing a realistic UGC ad from a production brief. "
                "Follow exact spoken lines, scene roles, product visibility policy, and failure conditions."
            ),
            provider_prompt_json=provider_prompt,
            negative_prompt=", ".join(NEGATIVE_PROMPT_TERMS),
            asset_instructions_json=self._asset_instructions(brief),
            overlay_instructions_json=self._overlay_instructions(brief),
            end_card_instructions_json=self._end_card_instructions(brief),
            quality_checklist_json=[
                "scene role is clear",
                "exact spoken line is present",
                "product visibility policy is followed",
                "identity and geometry are preserved",
                "proof moment is visible",
                "CTA is present",
                "human review remains required",
            ],
        )
        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        return prompt

    def latest_for_brief(self, ai_production_brief_id: int) -> models.DirectorPromptPack | None:
        return self.db.scalar(
            select(models.DirectorPromptPack)
            .where(models.DirectorPromptPack.ai_production_brief_id == ai_production_brief_id)
            .order_by(models.DirectorPromptPack.id.desc())
        )

    @staticmethod
    def as_output(prompt: models.DirectorPromptPack) -> DirectorPromptPackOutput:
        return DirectorPromptPackOutput(
            id=prompt.id,
            ai_production_brief_id=prompt.ai_production_brief_id,
            prompt_pack_id=prompt.prompt_pack_id,
            status=prompt.status,
            system_instruction=prompt.system_instruction,
            provider_prompt=prompt.provider_prompt_json or {},
            negative_prompt=prompt.negative_prompt,
            asset_instructions=prompt.asset_instructions_json or {},
            overlay_instructions=prompt.overlay_instructions_json or {},
            end_card_instructions=prompt.end_card_instructions_json or {},
            quality_checklist=prompt.quality_checklist_json or [],
        )

    @staticmethod
    def _scene_prompt(scene: models.SceneBlueprint, brief: models.AIProductionBrief) -> dict:
        return {
            "scene_order": scene.scene_order,
            "scene_role": scene.scene_role,
            "timing": {"start_second": scene.start_second, "end_second": scene.end_second},
            "creator_persona": (brief.blogger_meaning_spec.creator_persona_json if brief.blogger_meaning_spec else {}) or {},
            "exact_spoken_line": scene.spoken_line,
            "emotional_tone": "natural first-person creator, not commercial announcer",
            "visual_action": scene.visual_action,
            "product_visibility_rule": scene.product_visibility,
            "asset_overlay_instruction": DirectorPromptBuilder._visibility_instruction(brief.product_lock_mode),
            "identity_geometry_constraints": brief.product_identity_rules_json or {},
            "forbidden_changes": brief.must_avoid_json or [],
            "platform_format": f"{brief.platform} / {brief.format}",
            "cta": brief.cta,
            "caption": scene.caption_text,
            "must_show": scene.must_show_json or [],
            "must_avoid": scene.must_avoid_json or [],
        }

    @staticmethod
    def _visibility_instruction(lock_mode: str | None) -> str:
        if lock_mode == "packshot_overlay":
            return "Do not ask AI to redraw exact packaging; insert real approved packshot as overlay and end card."
        if lock_mode == "end_card_packshot":
            return "Use lifestyle/context scenes; exact product appears on real approved packshot end card."
        if lock_mode == "reference_i2v":
            return "Use approved reference image while preserving identity, geometry, scale, and label; human review required."
        return "Do not generate exact product packaging."

    @staticmethod
    def _asset_instructions(brief: models.AIProductionBrief) -> dict:
        requirements = brief.reference_requirements_json or {}
        return {
            "approved_reference_count": requirements.get("approved_reference_count", 0),
            "reference_asset_ids": requirements.get("reference_asset_ids", []),
            "primary_reference_asset_id": requirements.get("primary_reference_asset_id"),
            "human_review_required": True,
        }

    @staticmethod
    def _overlay_instructions(brief: models.AIProductionBrief) -> dict:
        return {
            "required": brief.product_lock_mode == "packshot_overlay",
            "instruction": DirectorPromptBuilder._visibility_instruction(brief.product_lock_mode),
        }

    @staticmethod
    def _end_card_instructions(brief: models.AIProductionBrief) -> dict:
        return {
            "use_real_packshot": brief.product_lock_mode in {"packshot_overlay", "end_card_packshot"},
            "cta": brief.cta,
            "do_not_generate_packaging_text": True,
        }
