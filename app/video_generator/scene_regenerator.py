from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app import models
from app.video_generator.errors import VideoGeneratorDataError


class SceneRegenerator:
    def __init__(self, db: Session):
        self.db = db

    def regenerate_scene(self, generation_variant: models.VideoGenerationVariant, scene_number: int) -> dict:
        prompt_pack = deepcopy(generation_variant.prompt_pack_json or {})
        scene_prompts = deepcopy(prompt_pack.get("scene_prompts") or [])
        changed = None
        for scene in scene_prompts:
            if scene.get("scene_number") == scene_number:
                scene["prompt_text"] = (
                    scene.get("prompt_text", "")
                    + " Regeneration pass: keep the same claim refs, preserve product accuracy, vary only staging and pacing."
                )
                scene["regenerated_at"] = datetime.now(UTC).isoformat()
                changed = scene
                break
        if not changed:
            raise VideoGeneratorDataError(f"Scene {scene_number} not found in prompt pack.")
        prompt_pack["scene_prompts"] = scene_prompts
        generation_variant.prompt_pack_json = prompt_pack
        flag_modified(generation_variant, "prompt_pack_json")
        generation_variant.regeneration_log_json = list(generation_variant.regeneration_log_json or []) + [
            {"scene_number": scene_number, "created_at": datetime.now(UTC).isoformat()}
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
