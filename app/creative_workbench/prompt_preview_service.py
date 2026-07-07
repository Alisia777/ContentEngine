from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.creative_workbench.errors import CreativeWorkbenchDataError
from app.creative_workbench.types import PromptPreviewOutput, PromptPreviewScene


class PromptPreviewService:
    def __init__(self, db: Session):
        self.db = db

    def preview(self, session_id: int) -> PromptPreviewOutput:
        session = self.db.get(models.CreativeWorkbenchSession, session_id)
        if not session:
            raise CreativeWorkbenchDataError(f"CreativeWorkbenchSession {session_id} not found.")
        prompt_pack = session.prompt_pack
        script = session.ugc_script
        meaning = session.blogger_meaning_spec
        policy = ((meaning.product_lock_rules_json or {}).get("policy") if meaning else {}) or {}
        product_lock_mode = (
            policy.get("product_lock_mode")
            or ((meaning.product_lock_rules_json or {}).get("product_lock_mode") if meaning else None)
            or (session.summary_json or {}).get("product_lock_mode")
        )
        reference_count = int(policy.get("approved_reference_count") or 0)
        identity_constraints = self._identity_constraints(meaning, product_lock_mode)
        geometry_constraints = self._geometry_constraints(prompt_pack, meaning)
        scene_prompts = self._scene_prompt_rows(prompt_pack)
        script_scenes = script.scene_script_json if script else []
        scenes: list[PromptPreviewScene] = []
        for index, prompt in enumerate(scene_prompts):
            script_scene = script_scenes[index] if index < len(script_scenes) else {}
            scenes.append(
                PromptPreviewScene(
                    scene_number=prompt.get("scene_number") or script_scene.get("scene_number") or index + 1,
                    scene_role=script_scene.get("role") or prompt.get("scene_role"),
                    duration_seconds=prompt.get("duration_seconds") or script_scene.get("duration_seconds"),
                    scene_prompt=prompt.get("prompt_text") or prompt.get("scene_prompt") or prompt.get("prompt") or "",
                    negative_prompt=prompt.get("negative_prompt") or self._negative_prompt(prompt_pack, index),
                    product_lock_mode=product_lock_mode,
                    reference_count=reference_count,
                    reference_images=prompt.get("reference_images") or [],
                    identity_constraints=identity_constraints,
                    geometry_constraints=geometry_constraints,
                    blogger_persona=(meaning.creator_persona_json if meaning else {}) or {},
                    spoken_line=script_scene.get("spoken_line"),
                    caption=script_scene.get("caption"),
                )
            )
        if not scenes and script:
            for scene in script.scene_script_json or []:
                scenes.append(
                    PromptPreviewScene(
                        scene_number=scene.get("scene_number"),
                        scene_role=scene.get("role"),
                        duration_seconds=scene.get("duration_seconds"),
                        scene_prompt=scene.get("visual_direction") or "",
                        negative_prompt=self._negative_prompt(prompt_pack, 0),
                        product_lock_mode=product_lock_mode,
                        reference_count=reference_count,
                        identity_constraints=identity_constraints,
                        geometry_constraints=geometry_constraints,
                        blogger_persona=(meaning.creator_persona_json if meaning else {}) or {},
                        spoken_line=scene.get("spoken_line"),
                        caption=scene.get("caption"),
                    )
                )
        return PromptPreviewOutput(
            session_id=session.id,
            prompt_pack_id=prompt_pack.id if prompt_pack else None,
            product_lock_mode=product_lock_mode,
            reference_count=reference_count,
            negative_prompt=self._negative_prompt(prompt_pack, 0),
            identity_constraints=identity_constraints,
            geometry_constraints=geometry_constraints,
            scenes=scenes,
        )

    @staticmethod
    def _scene_prompt_rows(prompt_pack: models.PromptPack | None) -> list[dict[str, Any]]:
        if not prompt_pack:
            return []
        rows = prompt_pack.scene_prompts_json or []
        if rows:
            return rows
        pack = prompt_pack.prompt_pack_json or {}
        return pack.get("scene_prompts") or pack.get("scenes") or []

    @staticmethod
    def _negative_prompt(prompt_pack: models.PromptPack | None, index: int) -> str | None:
        if not prompt_pack:
            return None
        negatives = prompt_pack.negative_prompts_json or []
        if negatives:
            item = negatives[index] if index < len(negatives) else negatives[0]
            if isinstance(item, dict):
                return item.get("negative_prompt") or item.get("prompt_text")
            return str(item)
        provider = prompt_pack.provider_payload_json or {}
        return provider.get("negative_prompt")

    @staticmethod
    def _identity_constraints(meaning: models.BloggerMeaningSpec | None, product_lock_mode: str | None) -> list[str]:
        rules = meaning.product_lock_rules_json if meaning else {}
        constraints = list(rules.get("identity_constraints") or [])
        if product_lock_mode:
            constraints.append(f"product_lock_mode:{product_lock_mode}")
        constraints.extend(["do_not_redraw_packaging_text", "preserve_logo_label_color_and_proportions"])
        return list(dict.fromkeys(str(item) for item in constraints if item))

    @staticmethod
    def _geometry_constraints(prompt_pack: models.PromptPack | None, meaning: models.BloggerMeaningSpec | None) -> dict[str, Any]:
        provider = prompt_pack.provider_payload_json if prompt_pack else {}
        rules = meaning.product_lock_rules_json if meaning else {}
        return {
            "provider_payload_geometry": provider.get("product_geometry_rules") or provider.get("geometry_constraints") or {},
            "product_lock_rules": rules.get("geometry_constraints") or rules.get("product_geometry_rules") or {},
        }
