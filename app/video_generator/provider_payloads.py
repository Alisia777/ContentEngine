from __future__ import annotations

from app.creative.product_geometry import (
    GEOMETRY_LOCK_PROMPT_LINES,
    geometry_lock_prompt_text,
    geometry_negative_prompt,
)
from app.creative.types import CreativeSpec
from app.video_generator.types import SpecPromptPack, SpecPromptScene


def build_provider_prompt_pack(spec: CreativeSpec, provider: str, creative_spec_id: int) -> SpecPromptPack:
    warnings = []
    if not spec.reference_images:
        warnings.append("No reference images supplied; do not hallucinate packaging.")
    scenes = []
    product_accuracy_rules = list(dict.fromkeys(spec.product_display_rules + GEOMETRY_LOCK_PROMPT_LINES))
    for scene in spec.scene_plan:
        first_frame_requirements = {}
        if scene.scene_number == 1:
            first_frame_requirements = spec.first_frame_spec.model_dump(mode="json")
        scenes.append(
            SpecPromptScene(
                scene_number=scene.scene_number,
                scene_role=scene.role,
                duration_seconds=scene.duration_seconds,
                prompt_text=(
                    f"Scene role: {scene.role}. {scene.visual} Caption: {scene.caption}. "
                    f"Voiceover: {scene.voiceover}. Product rules: {'; '.join(spec.product_display_rules)} "
                    f"Product geometry lock: {geometry_lock_prompt_text()}"
                ),
                negative_prompt=geometry_negative_prompt(
                    "distorted product, changed packaging, fake labels, unsupported claims, "
                    "medical claims, unreadable text, low quality"
                ),
                reference_images=spec.reference_images,
                first_frame_requirements=first_frame_requirements,
                camera_motion=scene.camera_motion,
                composition=scene.composition,
                lighting=scene.lighting,
                product_accuracy_rules=product_accuracy_rules,
                product_geometry_rules=spec.product_geometry_rules,
                product_scale_rules=spec.product_scale_rules,
                product_visibility_rules=spec.product_visibility_rules,
                caption_text=scene.caption,
                voiceover_text=scene.voiceover,
                provider_params={
                    "provider": provider,
                    "aspect_ratio": spec.aspect_ratio,
                    "scene_role": scene.role,
                    "claim_refs": scene.claim_refs,
                    "product_geometry_rules": spec.product_geometry_rules,
                    "product_scale_rules": spec.product_scale_rules,
                    "product_visibility_rules": spec.product_visibility_rules,
                },
            )
        )
    return SpecPromptPack(
        provider=provider,
        creative_spec_id=creative_spec_id,
        aspect_ratio=spec.aspect_ratio,
        duration_seconds=spec.duration_seconds,
        scene_prompts=scenes,
        provider_params={
            "provider": provider,
            "format": spec.format,
            "platform": spec.platform,
            "product_geometry_spec": spec.product_geometry_spec.model_dump(mode="json"),
            "product_geometry_rules": spec.product_geometry_rules,
            "product_scale_rules": spec.product_scale_rules,
            "product_visibility_rules": spec.product_visibility_rules,
        },
        warnings=warnings,
    )
