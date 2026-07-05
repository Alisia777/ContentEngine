from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app import models
from app.creative.product_geometry import (
    GEOMETRY_LOCK_PROMPT_LINES,
    geometry_lock_prompt_text,
    geometry_negative_prompt,
)
from app.video_generator.errors import VideoGeneratorDataError


class SceneRegenerator:
    def __init__(self, db: Session):
        self.db = db

    def regenerate_scene(
        self,
        generation_variant: models.VideoGenerationVariant,
        scene_number: int,
        *,
        reason: str | None = None,
        feedback: str | None = None,
        regeneration_request_id: int | None = None,
    ) -> dict:
        prompt_pack = deepcopy(generation_variant.prompt_pack_json or {})
        scene_prompts = deepcopy(prompt_pack.get("scene_prompts") or [])
        changed = None
        for scene in scene_prompts:
            if scene.get("scene_number") == scene_number:
                scene["prompt_text"] = self._regeneration_prompt(scene.get("prompt_text", ""), reason, feedback)
                scene["negative_prompt"] = self._regeneration_negative_prompt(scene.get("negative_prompt"), reason)
                scene["safety_constraints"] = self._regeneration_safety_constraints(
                    scene.get("safety_constraints") or [], reason
                )
                scene["regeneration_reason"] = reason or "scene_prompt_refresh"
                scene["regeneration_feedback"] = feedback
                scene["regenerated_at"] = datetime.now(UTC).isoformat()
                changed = scene
                break
        if not changed:
            raise VideoGeneratorDataError(f"Scene {scene_number} not found in prompt pack.")
        prompt_pack["scene_prompts"] = scene_prompts
        generation_variant.prompt_pack_json = prompt_pack
        flag_modified(generation_variant, "prompt_pack_json")
        generation_variant.regeneration_log_json = list(generation_variant.regeneration_log_json or []) + [
            {
                "scene_number": scene_number,
                "reason": reason or "scene_prompt_refresh",
                "feedback": feedback,
                "regeneration_request_id": regeneration_request_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
        if generation_variant.prompt_pack:
            generation_variant.prompt_pack.prompt_pack_json = prompt_pack
            generation_variant.prompt_pack.scene_prompts_json = scene_prompts
            flag_modified(generation_variant.prompt_pack, "prompt_pack_json")
            flag_modified(generation_variant.prompt_pack, "scene_prompts_json")
            generation_variant.prompt_pack.provider_payload_json = {
                **(generation_variant.prompt_pack.provider_payload_json or {}),
                "scenes": scene_prompts,
            }
            flag_modified(generation_variant.prompt_pack, "provider_payload_json")
        if generation_variant.script_variant:
            for scene in generation_variant.script_variant.scenes:
                if scene.scene_number == scene_number:
                    scene.video_prompt = changed["prompt_text"]
        self.db.commit()
        return changed

    @staticmethod
    def _regeneration_prompt(existing_prompt: str, reason: str | None, feedback: str | None) -> str:
        additions = [
            "Regeneration pass: keep the same claim refs, preserve product accuracy, vary only staging and pacing.",
        ]
        if reason == "product_geometry_mismatch":
            additions.extend(
                [
                    "Geometry correction: product size/proportions drifted in human review.",
                    geometry_lock_prompt_text(),
                ]
            )
        if feedback:
            additions.append(f"Human feedback: {feedback}")
        return f"{existing_prompt} {' '.join(additions)}".strip()

    @staticmethod
    def _regeneration_negative_prompt(existing_negative_prompt: str | None, reason: str | None) -> str:
        if reason == "product_geometry_mismatch":
            return geometry_negative_prompt(existing_negative_prompt)
        return existing_negative_prompt or "distorted product, unsupported claims, low quality"

    @staticmethod
    def _regeneration_safety_constraints(existing_constraints: list[str], reason: str | None) -> list[str]:
        constraints = list(existing_constraints)
        if reason == "product_geometry_mismatch":
            constraints.extend(GEOMETRY_LOCK_PROMPT_LINES)
        return list(dict.fromkeys(constraints))
