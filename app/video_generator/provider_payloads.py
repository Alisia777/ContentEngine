from __future__ import annotations

from app.creative.types import CreativeSpec
from app.video_generator.types import SpecPromptPack, SpecPromptScene


def build_provider_prompt_pack(spec: CreativeSpec, provider: str, creative_spec_id: int) -> SpecPromptPack:
    warnings = []
    if not spec.reference_images:
        warnings.append("No reference images supplied; do not hallucinate packaging.")
    scenes = []
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
                    f"Voiceover: {scene.voiceover}. Product rules: {'; '.join(spec.product_display_rules)}"
                ),
                negative_prompt=(
                    "distorted product, changed packaging, fake labels, unsupported claims, "
                    "medical claims, unreadable text, low quality"
                ),
                reference_images=spec.reference_images,
                first_frame_requirements=first_frame_requirements,
                camera_motion=scene.camera_motion,
                composition=scene.composition,
                lighting=scene.lighting,
                product_accuracy_rules=spec.product_display_rules,
                caption_text=scene.caption,
                voiceover_text=scene.voiceover,
                provider_params={
                    "provider": provider,
                    "aspect_ratio": spec.aspect_ratio,
                    "scene_role": scene.role,
                    "claim_refs": scene.claim_refs,
                },
            )
        )
    return SpecPromptPack(
        provider=provider,
        creative_spec_id=creative_spec_id,
        aspect_ratio=spec.aspect_ratio,
        duration_seconds=spec.duration_seconds,
        scene_prompts=scenes,
        provider_params={"provider": provider, "format": spec.format, "platform": spec.platform},
        warnings=warnings,
    )
