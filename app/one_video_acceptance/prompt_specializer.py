from __future__ import annotations

from typing import Any

from app import models
from app.one_video_acceptance.types import OneVideoScene, ProductScenePolicyOutput


BOMBBAR_NEGATIVE_TERMS = [
    "generic muesli bar",
    "granola bar",
    "cereal bar",
    "oat cluster",
    "loose oats",
    "random nuts replacing filling",
    "generic protein bar packaging",
    "redesigned wrapper",
    "changed Bombbar logo",
    "fake label text",
    "unreadable wrapper",
    "wrong wrapper color",
    "deformed wrapper in hand",
    "floating wrapper",
    "product melts into hand",
    "oversized snack bar",
    "tiny snack bar",
    "AI-generated bite texture without references",
    "chewing close-up when bite references are missing",
    "medical or weight-loss claims",
]

MANGO_KUNAFA_FLAVOR_IDENTITY = {
    "target_variant": "Bombbar Pro Dubai Mango & Kunafa",
    "required_visuals": [
        "milk-chocolate shell",
        "pale cream souffle body",
        "bright yellow mango center",
        "thin caramel-kunafa top layer",
    ],
    "excluded_variants": [
        "Raspberry, pistachio and kunafa variant with pink interior and green center",
        "Hazelnut variant with brown center and visible hazelnut pieces",
    ],
    "negative_terms": [
        "raspberry pistachio flavor variant",
        "pink raspberry interior",
        "green pistachio center",
        "hazelnut flavor variant",
        "brown hazelnut center",
        "visible hazelnut pieces replacing mango filling",
        "mixing Bombbar flavor variants",
        "yellow mango center changed to green or brown",
    ],
}

ACCEPTANCE_CHECKLIST = [
    "no_muesli_granola_visual_drift",
    "no_wrapper_logo_label_redesign",
    "product_appears_only_according_to_scene_policy",
    "proof_moment_present",
    "cta_or_end_card_present",
    "human_review_decision_recorded",
    "no_auto_approval",
]


class BombbarPromptSpecializer:
    def build_scene_prompts(
        self,
        *,
        product: models.Product,
        policy: ProductScenePolicyOutput,
        scenes: list[OneVideoScene],
        platform: str,
        provider: str = "runway",
    ) -> dict[str, Any]:
        flavor_identity = self.flavor_identity(product)
        flavor_negative_terms = flavor_identity.get("negative_terms", [])
        flavor_lock = self.flavor_lock_instruction(flavor_identity)
        scene_prompts = []
        for scene in scenes:
            negative_prompt = self.merge_negative_prompt(scene.negative_prompt, flavor_negative_terms)
            prompt_text = scene.provider_prompt_text or self.scene_prompt(product, policy, scene)
            if flavor_lock:
                prompt_text = f"{prompt_text} {flavor_lock}"
            scene_prompts.append(
                {
                    "scene_number": scene.scene_number,
                    "role": scene.role,
                    "duration_seconds": scene.duration_seconds,
                    "prompt_text": prompt_text,
                    "negative_prompt": negative_prompt,
                    "reference_policy": policy.model_dump(mode="json"),
                    "camera_motion": scene.camera_motion,
                    "safety_constraints": scene.safety_constraints,
                    "must_avoid": list(dict.fromkeys([*scene.must_avoid, *BOMBBAR_NEGATIVE_TERMS, *flavor_negative_terms])),
                }
            )
        return {
            "provider": provider,
            "platform": platform,
            "aspect_ratio": "9:16",
            "duration_seconds": sum(scene.duration_seconds for scene in scenes),
            "product_title": product.title,
            "sku": product.sku,
            "creator_profile": "Russian-speaking sporty woman, 25-30, natural UGC tone, looks like a real buyer, not a studio ad.",
            "product_flavor_identity": flavor_identity,
            "product_scene_policy": policy.model_dump(mode="json"),
            "scene_prompts": scene_prompts,
            "negative_prompt": self.merge_negative_prompt("", flavor_negative_terms),
            "quality_checklist": ACCEPTANCE_CHECKLIST,
            "notes": [
                "Prompt-only path must not call a paid provider.",
                "Real run remains behind QVF_GENERATION_MODE, QVF_ALLOW_REAL_SPEND and provider key gates.",
                "Metadata checks do not claim visual product identity verification.",
            ],
        }

    def scene_prompt(self, product: models.Product, policy: ProductScenePolicyOutput, scene: OneVideoScene) -> str:
        policy_line = (
            "Use closed wrapper, approved cutaway insert, packshot overlay and end card only."
            if not policy.edible_kit_ready
            else "Bite/texture shots are allowed only when matching approved edible references exactly."
        )
        return (
            f"9:16 realistic Russian UGC Reel for {product.title}. "
            "A sporty woman aged 25-30 presents the product in a natural everyday setting, "
            "speaking directly to camera in Russian. "
            f"Scene role: {scene.role}. Timing: {scene.starts_at}-{scene.starts_at + scene.duration_seconds}s. "
            f"Action: {scene.visual}. Spoken line: {scene.spoken_line}. Caption: {scene.caption}. "
            f"Product visibility: {scene.product_visibility}. {policy_line} "
            "Keep the wrapper proportions, colors, logo and label locked to approved references. "
            "Do not invent edible texture unless the scene policy allows it."
        )

    @staticmethod
    def merge_negative_prompt(existing: str | None, additional_terms: list[str] | None = None) -> str:
        terms = [item.strip() for item in (existing or "").split(",") if item.strip()]
        return ", ".join(list(dict.fromkeys([*terms, *BOMBBAR_NEGATIVE_TERMS, *(additional_terms or [])])))

    @staticmethod
    def flavor_identity(product: models.Product) -> dict[str, Any]:
        normalized = f"{product.sku} {product.title}".lower()
        if "mango" in normalized and "kunafa" in normalized:
            return {key: list(value) if isinstance(value, list) else value for key, value in MANGO_KUNAFA_FLAVOR_IDENTITY.items()}
        return {
            "target_variant": product.title,
            "required_visuals": [],
            "excluded_variants": [],
            "negative_terms": [],
        }

    @staticmethod
    def flavor_lock_instruction(flavor_identity: dict[str, Any]) -> str:
        required = flavor_identity.get("required_visuals") or []
        excluded = flavor_identity.get("excluded_variants") or []
        if not required and not excluded:
            return ""
        return (
            f"Flavor identity lock: show only {flavor_identity['target_variant']}. "
            f"Required edible appearance: {', '.join(required)}. "
            f"Never substitute or mix: {'; '.join(excluded)}."
        )

    def apply_to_generation_variant(
        self,
        plan: models.OneVideoRenderPlan,
        generation_variant: models.VideoGenerationVariant,
    ) -> models.VideoGenerationVariant:
        prompt_pack_json = dict(generation_variant.prompt_pack_json or {})
        prompt_preview = dict(plan.prompt_preview_json or {})
        specialized_scenes = prompt_preview.get("scene_prompts") or []
        prompt_pack_json.update(
            {
                "one_video_render_plan_id": plan.id,
                "product_scene_policy": plan.product_scene_policy_json,
                "asset_audit": (plan.product_scene_policy_json or {}).get("asset_audit"),
                "mvp_scorecard": (plan.prompt_preview_json or {}).get("mvp_scorecard"),
                "product_flavor_identity": prompt_preview.get("product_flavor_identity"),
                "bombbar_prompt_negative_terms": BOMBBAR_NEGATIVE_TERMS,
                "acceptance_checklist": ACCEPTANCE_CHECKLIST,
                "scene_prompts": specialized_scenes or prompt_pack_json.get("scene_prompts") or [],
                "warnings": list(dict.fromkeys((prompt_pack_json.get("warnings") or []) + (plan.warnings_json or []))),
                "blockers": list(dict.fromkeys((prompt_pack_json.get("blockers") or []) + (plan.blockers_json or []))),
            }
        )
        generation_variant.prompt_pack_json = prompt_pack_json
        provider_payload = dict(generation_variant.provider_payload_json or {})
        provider_payload.update(
            {
                "one_video_render_plan_id": plan.id,
                "product_scene_policy": plan.product_scene_policy_json,
                "asset_audit": (plan.product_scene_policy_json or {}).get("asset_audit"),
                "mvp_scorecard": (plan.prompt_preview_json or {}).get("mvp_scorecard"),
                "product_flavor_identity": prompt_preview.get("product_flavor_identity"),
                "scenes": specialized_scenes or provider_payload.get("scenes") or [],
                "negative_prompt": plan.negative_prompt,
                "quality_checklist": ACCEPTANCE_CHECKLIST,
            }
        )
        generation_variant.provider_payload_json = provider_payload
        if generation_variant.prompt_pack:
            generation_variant.prompt_pack.prompt_pack_json = prompt_pack_json
            generation_variant.prompt_pack.scene_prompts_json = specialized_scenes or generation_variant.prompt_pack.scene_prompts_json
            generation_variant.prompt_pack.negative_prompts_json = [
                {
                    "scene_number": scene.get("scene_number"),
                    "negative_prompt": scene.get("negative_prompt") or plan.negative_prompt,
                }
                for scene in (specialized_scenes or [])
            ]
            generation_variant.prompt_pack.provider_payload_json = provider_payload
        return generation_variant
