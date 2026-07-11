from __future__ import annotations

from app.product_asset_contract.reference_requirement_service import PROFILE_INTERACTION_MODES, TIER_RANK
from app.product_asset_contract.types import AssetClassification, ScenePermissionOutput


class ScenePermissionService:
    def evaluate(
        self,
        *,
        product_profile: str,
        current_tier: str,
        classified_assets: list[AssetClassification],
        label_accuracy_required: bool = True,
        publishing_candidate: bool = True,
    ) -> ScenePermissionOutput:
        rank = TIER_RANK[current_tier]
        types = {item.contract_type for item in classified_assets if item.eligible}
        is_food = product_profile == "food_snack"
        interaction_mode = PROFILE_INTERACTION_MODES[product_profile]
        wrapper_scene = is_food and rank >= 2
        wrapper_closeup = wrapper_scene and bool(types.intersection({"angled_wrapper", "label_closeup", "front_packshot"}))
        opening = is_food and rank >= 4 and "semi_open_wrapper" in types and bool(types.intersection({"opening_video_reference", "use_video_reference"}))
        unwrapped = is_food and rank >= 3 and "whole_unwrapped_product" in types
        cutaway = is_food and rank >= 3 and "cutaway_product" in types
        bite = is_food and rank >= 4 and "bitten_product" in types and "product_near_mouth" in types
        near_mouth = is_food and rank >= 4 and "product_near_mouth" in types
        texture = rank >= 3 and bool(types.intersection({"texture_macro", "texture_swatch", "cutaway_product", "detail_closeup"}))
        use_case = rank >= 3
        application = rank >= 4 and product_profile == "cosmetic"
        try_on = rank >= 4 and product_profile == "apparel"
        demonstration = rank >= 4 and product_profile in {"household", "general"}
        tasting = bite
        interaction = application or try_on or demonstration or tasting
        provider_packaging = wrapper_scene and not label_accuracy_required
        provider_product = rank >= 4 and not label_accuracy_required
        packshot_overlay = label_accuracy_required or not provider_packaging
        end_card = publishing_candidate or label_accuracy_required

        allowed = ["creator_talking_head", "strategy", "no_product_generation_lifestyle"]
        if rank >= 1:
            allowed.extend(["packshot_overlay", "end_card"])
        if rank >= 2:
            allowed.extend(["identity_reveal", "reference_safe_product_context"])
        if wrapper_scene:
            allowed.append("closed_wrapper_reveal")
        if wrapper_closeup:
            allowed.append("wrapper_closeup")
        if rank >= 3:
            allowed.extend(["product_use_insert", "proof_insert"])
        if unwrapped:
            allowed.append("unwrapped_product")
        if cutaway:
            allowed.append("cutaway_proof")
        if texture:
            allowed.append("texture_macro")
        if opening:
            allowed.append("opening_scene")
        if bite:
            allowed.append("bite_scene")
        if near_mouth:
            allowed.append("near_mouth_scene")
        if application:
            allowed.append("application_demo")
        if try_on:
            allowed.append("try_on_demo")
        if demonstration:
            allowed.append("operation_demo")
        if tasting:
            allowed.append("taste_demo")
        if rank >= 4:
            allowed.append("ugc_use_reaction")

        all_sensitive = {
            "closed_wrapper_reveal",
            "wrapper_closeup",
            "opening_scene",
            "unwrapped_product",
            "cutaway_proof",
            "bite_scene",
            "near_mouth_scene",
            "texture_macro",
            "product_use_insert",
            "proof_insert",
            "application_demo",
            "try_on_demo",
            "operation_demo",
            "taste_demo",
            "ugc_use_reaction",
        }
        blocked = sorted(all_sensitive.difference(allowed))
        reasons = []
        if rank == 0:
            reasons.append("no_approved_product_identity_reference")
        if rank == 1:
            reasons.append("front_packshot_alone_does_not_unlock_provider_generated_product_scenes")
        if is_food and rank < 3:
            reasons.append("edible_refs_missing_no_unwrapped_bite_or_macro")
        if is_food and "bitten_product" not in types:
            reasons.append("bitten_product_missing_no_bite_closeup")
        if is_food and "product_near_mouth" not in types:
            reasons.append("product_near_mouth_missing")
        if is_food and "semi_open_wrapper" not in types:
            reasons.append("semi_open_wrapper_missing_no_opening_scene")
        if label_accuracy_required:
            reasons.append("label_accuracy_requires_packshot_overlay_or_end_card")
        return ScenePermissionOutput(
            product_profile=product_profile,
            current_tier=current_tier,
            interaction_mode=interaction_mode,
            wrapper_scene_allowed=wrapper_scene,
            wrapper_closeup_allowed=wrapper_closeup,
            opening_scene_allowed=opening,
            unwrapped_product_allowed=unwrapped,
            cutaway_proof_allowed=cutaway,
            bite_scene_allowed=bite,
            near_mouth_allowed=near_mouth,
            texture_macro_allowed=texture,
            use_case_scene_allowed=use_case,
            interaction_scene_allowed=interaction,
            application_scene_allowed=application,
            try_on_scene_allowed=try_on,
            demonstration_scene_allowed=demonstration,
            tasting_scene_allowed=tasting,
            packshot_overlay_required=packshot_overlay,
            end_card_required=end_card,
            provider_generated_packaging_allowed=provider_packaging,
            provider_generated_product_allowed=provider_product,
            product_compositor_ready=rank >= 1,
            compositor_mode="packshot_overlay" if rank >= 1 else "blocked",
            allowed_scenes=list(dict.fromkeys(allowed)),
            blocked_scenes=blocked,
            reasons=list(dict.fromkeys(reasons)),
        )
