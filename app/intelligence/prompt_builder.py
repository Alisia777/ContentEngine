from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.intelligence.errors import MissingGeneratorDataError
from app.intelligence.types import PromptPackOutput, PromptSceneOutput


class PromptPackBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def build_for_script(
        self,
        script_variant_id: int,
        provider: str,
        script_brief_id: int | None = None,
    ) -> models.PromptPack:
        variant = self.db.get(models.ScriptVariant, script_variant_id)
        if not variant:
            raise MissingGeneratorDataError(f"Script variant {script_variant_id} not found.")
        brief = self._brief_for_variant(variant, script_brief_id)
        prompt_output = self._output_for_variant(variant, provider)
        record = models.PromptPack(
            script_brief_id=brief.id,
            script_variant_id=variant.id,
            status="ready",
            prompt_pack_json=prompt_output.model_dump(mode="json"),
            scene_prompts_json=[scene.model_dump(mode="json") for scene in prompt_output.scene_prompts],
            negative_prompts_json=[
                {"scene_number": scene.scene_number, "negative_prompt": scene.negative_prompt}
                for scene in prompt_output.scene_prompts
            ],
            provider_payload_json={
                "provider": provider,
                "model": self.settings.runway_model if provider == "runway" else provider,
                "ratio": self.settings.video_ratio,
                "scenes": [scene.model_dump(mode="json") for scene in prompt_output.scene_prompts],
            },
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _output_for_variant(self, variant: models.ScriptVariant, provider: str) -> PromptPackOutput:
        scenes = sorted(variant.scenes, key=lambda scene: scene.scene_number)
        prompt_scenes = []
        for scene in scenes:
            duration = max(1, int(scene.time_end - scene.time_start))
            prompt_scenes.append(
                PromptSceneOutput(
                    scene_number=scene.scene_number,
                    duration_seconds=duration,
                    prompt_text=scene.video_prompt or scene.visual_description or "",
                    negative_prompt=scene.negative_prompt or "distorted product, unsupported claims, low quality",
                    reference_images=variant.script_job.product.images_json or [],
                    camera_motion="slow push-in with stable product framing",
                    style="realistic 9:16 marketplace product video",
                    safety_constraints=[
                        "do not alter product shape",
                        "do not add unsupported claims",
                        "keep labels and packaging believable",
                    ],
                )
            )
        return PromptPackOutput(
            provider=provider,
            aspect_ratio=variant.full_script_json.get("aspect_ratio", "9:16"),
            duration_seconds=variant.full_script_json.get("duration_seconds", 15),
            scene_prompts=prompt_scenes,
        )

    def _brief_for_variant(self, variant: models.ScriptVariant, script_brief_id: int | None) -> models.ScriptBrief:
        if script_brief_id:
            brief = self.db.get(models.ScriptBrief, script_brief_id)
            if brief:
                return brief
        product_id = variant.script_job.product_id
        brief = (
            self.db.query(models.ScriptBrief)
            .filter(models.ScriptBrief.product_id == product_id)
            .order_by(models.ScriptBrief.id.desc())
            .first()
        )
        if not brief:
            raise MissingGeneratorDataError("ScriptBrief is required before building a PromptPack.")
        return brief

