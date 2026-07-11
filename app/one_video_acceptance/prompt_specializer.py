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

GENERIC_PRODUCT_NEGATIVE_TERMS = [
    "wrong SKU or product variant",
    "generic substitute product",
    "invented logo or label text",
    "changed product color, geometry or scale",
    "floating or melting product",
    "invented use or application method",
    "unsupported before-and-after result",
    "medical, guaranteed or unsafe claim",
]

PROFILE_NEGATIVE_TERMS = {
    "cosmetic": ["wrong dispenser", "invented skin result", "application on an unsupported body area", "fake texture swatch"],
    "apparel": ["wrong garment cut", "changed fabric or color", "impossible fit", "extra garment details"],
    "household": ["invented product function", "unsafe handling", "wrong scale in hand", "impossible result"],
    "general": ["invented product function", "wrong use context", "unsupported result"],
}

PROFILE_INTERACTION_INSTRUCTIONS = {
    "food_snack": "Taste or bite only when matching edible and interaction references explicitly allow it.",
    "cosmetic": "Apply only to the approved body area and match the reference application motion and amount.",
    "apparel": "Show the approved garment on-body fit and movement; never invent a different cut, fabric or color.",
    "household": "Demonstrate only the approved function and handling sequence; never invent an effect or unsafe use.",
    "general": "Show only the approved real-world use sequence and result context.",
}

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

BASE_ACCEPTANCE_CHECKLIST = [
    "no_wrong_sku_or_variant_visual_drift",
    "no_wrapper_logo_label_redesign",
    "product_appears_only_according_to_scene_policy",
    "category_appropriate_interaction_only",
    "blogger_reason_is_credible",
    "proof_moment_present",
    "cta_or_end_card_present",
    "human_review_decision_recorded",
    "no_auto_approval",
]

PROFILE_ACCEPTANCE_CHECKLISTS = {
    "food_snack": ["no_muesli_granola_visual_drift", "edible_identity_matches_exact_variant"],
    "cosmetic": ["dispenser_and_texture_match_references", "application_area_and_motion_match_references"],
    "apparel": ["garment_cut_color_and_fabric_match_references", "fit_and_movement_match_on_body_references"],
    "household": ["function_and_scale_match_references", "handling_is_reference_matched_and_safe"],
    "general": ["function_and_scale_match_references", "use_sequence_matches_approved_references"],
}

# Backward-compatible food checklist for older imports.
ACCEPTANCE_CHECKLIST = [*BASE_ACCEPTANCE_CHECKLIST, *PROFILE_ACCEPTANCE_CHECKLISTS["food_snack"]]


class ProductUsePromptSpecializer:
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
        flavor_lock = self.identity_lock_instruction(
            flavor_identity,
            food_profile=policy.product_profile == "food_snack",
        )
        product_negative_terms = self.product_negative_terms(product, policy, flavor_negative_terms)
        quality_checklist = self.acceptance_checklist(policy)
        scene_prompts = []
        for scene in scenes:
            negative_prompt = self.merge_negative_prompt(scene.negative_prompt, product_negative_terms)
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
                    "must_avoid": list(dict.fromkeys([*scene.must_avoid, *product_negative_terms])),
                }
            )
        return {
            "provider": provider,
            "platform": platform,
            "aspect_ratio": "9:16",
            "duration_seconds": sum(scene.duration_seconds for scene in scenes),
            "product_title": product.title,
            "sku": product.sku,
            "creator_profile": self.creator_profile(product, policy),
            "product_flavor_identity": flavor_identity if policy.product_profile == "food_snack" else {},
            "product_variant_identity": flavor_identity,
            "product_scene_policy": policy.model_dump(mode="json"),
            "interaction_mode": policy.interaction_mode,
            "scene_prompts": scene_prompts,
            "negative_prompt": self.merge_negative_prompt("", product_negative_terms),
            "product_specific_negative_terms": product_negative_terms,
            "quality_checklist": quality_checklist,
            "notes": [
                "Prompt-only path must not call a paid provider.",
                "Real run remains behind QVF_GENERATION_MODE, QVF_ALLOW_REAL_SPEND and provider key gates.",
                "Metadata checks do not claim visual product identity verification.",
            ],
        }

    def scene_prompt(self, product: models.Product, policy: ProductScenePolicyOutput, scene: OneVideoScene) -> str:
        if policy.product_profile != "food_snack":
            policy_line = (
                f"Use the exact approved {policy.interaction_mode} video/reference as an insert; do not redraw the SKU."
                if policy.interaction_scene_allowed and not policy.provider_generated_product_allowed
                else (
                    "Reference-guided interaction is allowed only where the Product Asset Contract explicitly permits it."
                    if policy.interaction_scene_allowed
                    else "Use approved static packshot/use-case inserts only; do not invent product handling or application."
                )
            )
            return (
                f"9:16 realistic Russian blogger UGC Reel for exact SKU {product.sku}: {product.title}. "
                f"Creator: {self.creator_profile(product, policy)} "
                f"Scene role: {scene.role}. Timing: {scene.starts_at}-{scene.starts_at + scene.duration_seconds}s. "
                f"Action: {scene.visual}. Spoken line: {scene.spoken_line}. Caption: {scene.caption}. "
                f"Product visibility: {scene.product_visibility}. {policy_line} "
                "Preserve exact variant, label, color, geometry and scale. "
                f"{PROFILE_INTERACTION_INSTRUCTIONS[policy.product_profile]}"
            )
        policy_line = (
            "Use closed wrapper, approved cutaway insert, packshot overlay and end card only."
            if not policy.edible_kit_ready
            else (
                "Use exact approved bite/use inserts; the provider must not redraw wrapper, filling or bite texture."
                if not policy.provider_generated_product_allowed
                else "Bite/texture shots are allowed only when matching approved edible references exactly."
            )
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
        return ", ".join(list(dict.fromkeys([*terms, *GENERIC_PRODUCT_NEGATIVE_TERMS, *(additional_terms or [])])))

    @staticmethod
    def creator_profile(product: models.Product, policy: ProductScenePolicyOutput) -> str:
        attributes = product.attributes_json or {}
        if attributes.get("creator_persona"):
            return str(attributes["creator_persona"])
        if policy.product_profile == "food_snack":
            return "Russian-speaking sporty woman, 25-30, natural UGC tone, looks like a real buyer, not a studio ad."
        return "Russian-speaking creator aged 25-35, natural first-person UGC tone, credible real product user."

    @staticmethod
    def product_negative_terms(
        product: models.Product,
        policy: ProductScenePolicyOutput,
        identity_terms: list[str],
    ) -> list[str]:
        normalized = f"{product.brand} {product.sku} {product.title}".lower()
        terms = [*GENERIC_PRODUCT_NEGATIVE_TERMS, *PROFILE_NEGATIVE_TERMS.get(policy.product_profile, []), *identity_terms]
        if "bombbar" in normalized or "bomb bar" in normalized:
            terms.extend(BOMBBAR_NEGATIVE_TERMS)
        return list(dict.fromkeys(terms))

    @staticmethod
    def acceptance_checklist(policy: ProductScenePolicyOutput) -> list[str]:
        return list(
            dict.fromkeys(
                [*BASE_ACCEPTANCE_CHECKLIST, *PROFILE_ACCEPTANCE_CHECKLISTS.get(policy.product_profile, [])]
            )
        )

    @staticmethod
    def flavor_identity(product: models.Product) -> dict[str, Any]:
        attributes = product.attributes_json or {}
        normalized = f"{product.sku} {product.title} {attributes.get('flavor', '')}".lower()
        if "mango" in normalized and "kunafa" in normalized:
            return {key: list(value) if isinstance(value, list) else value for key, value in MANGO_KUNAFA_FLAVOR_IDENTITY.items()}
        return {
            "target_variant": product.title,
            "variant_key": attributes.get("variant_key") or attributes.get("flavor") or attributes.get("color") or attributes.get("model_variant"),
            "required_visuals": list(attributes.get("visual_identity") or []),
            "excluded_variants": list(attributes.get("excluded_variants") or []),
            "negative_terms": list(attributes.get("variant_negative_terms") or []),
        }

    @staticmethod
    def identity_lock_instruction(flavor_identity: dict[str, Any], *, food_profile: bool) -> str:
        required = flavor_identity.get("required_visuals") or []
        excluded = flavor_identity.get("excluded_variants") or []
        if not required and not excluded:
            return ""
        label = "Flavor identity lock" if food_profile else "Variant identity lock"
        appearance = "edible appearance" if food_profile else "visual identity"
        return (
            f"{label}: show only {flavor_identity['target_variant']}. "
            f"Required {appearance}: {', '.join(required)}. "
            f"Never substitute or mix: {'; '.join(excluded)}."
        )

    @staticmethod
    def flavor_lock_instruction(flavor_identity: dict[str, Any]) -> str:
        return ProductUsePromptSpecializer.identity_lock_instruction(flavor_identity, food_profile=True)

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
                "product_variant_identity": prompt_preview.get("product_variant_identity"),
                "product_asset_contract": (plan.product_scene_policy_json or {}).get("asset_contract"),
                "product_specific_negative_terms": prompt_preview.get("product_specific_negative_terms") or [],
                "generic_product_negative_terms": GENERIC_PRODUCT_NEGATIVE_TERMS,
                "acceptance_checklist": prompt_preview.get("quality_checklist") or BASE_ACCEPTANCE_CHECKLIST,
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
                "product_variant_identity": prompt_preview.get("product_variant_identity"),
                "product_asset_contract": (plan.product_scene_policy_json or {}).get("asset_contract"),
                "scenes": specialized_scenes or provider_payload.get("scenes") or [],
                "negative_prompt": plan.negative_prompt,
                "quality_checklist": prompt_preview.get("quality_checklist") or BASE_ACCEPTANCE_CHECKLIST,
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


# Backward-compatible name for existing routes and scripts.
BombbarPromptSpecializer = ProductUsePromptSpecializer
