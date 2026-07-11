from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.one_video_acceptance.asset_audit import ProductAssetAuditor
from app.one_video_acceptance.errors import OneVideoAcceptanceDataError
from app.one_video_acceptance.types import ProductScenePolicyOutput
from app.product_asset_contract import ProductAssetTierService, ReferenceRequirementService


WRAPPER_TYPES = {"packshot", "product", "label_closeup", "packaging_closeup", "label", "packaging", "unknown"}
EDIBLE_TYPES = {"texture", "cutaway", "unwrapped", "bite", "bitten", "food", "macro", "slice", "sliced"}
STYLE_TYPES = {"style", "creator_style", "ugc_style", "moodboard", "wibes", "reels_reference"}
LIFESTYLE_TYPES = {"lifestyle", "context", "use_case", "creator", "setting", "home_setting", "coffee_context"}
WRAPPER_KEYWORDS = {
    "wrapper",
    "packshot",
    "package",
    "packaging",
    "label",
    "front",
    "оберт",
    "упаков",
    "этикет",
}
EDIBLE_KEYWORDS = {
    "edible",
    "bar cut",
    "cutaway",
    "cross section",
    "texture",
    "unwrapped",
    "bite",
    "bitten",
    "inside",
    "разрез",
    "кусочек",
    "надкус",
    "начинк",
    "текстур",
}
BITTEN_KEYWORDS = {"bitten", "bite", "надкус", "укус", "кусает"}
BAR_IN_HAND_KEYWORDS = {"bar in hand", "hand", "holding", "в руке", "держит"}
STYLE_KEYWORDS = {
    "style",
    "wibes",
    "reels",
    "ugc",
    "creator",
    "female creator",
    "sporty",
    "face-to-camera",
    "блогер",
    "девушка",
    "спорт",
    "вайб",
    "стиль",
}
LIFESTYLE_KEYWORDS = {
    "lifestyle",
    "context",
    "use case",
    "coffee",
    "table",
    "home",
    "gym",
    "plate",
    "setting",
    "кофе",
    "стол",
    "дом",
    "зал",
    "контекст",
}


class ProductScenePolicyService:
    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        product_id: int,
        *,
        provider: str = "runway",
        label_accuracy_required: bool = True,
    ) -> ProductScenePolicyOutput:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise OneVideoAcceptanceDataError(f"Product {product_id} not found.")

        contract_service = ProductAssetTierService(self.db)
        contract = contract_service.output(
            contract_service.evaluate(
                product_id,
                label_accuracy_required=label_accuracy_required,
                publishing_candidate=True,
            )
        )
        requirement_service = ReferenceRequirementService(self.db)
        requirement_record = requirement_service.evaluate(contract, purpose="final_ad")
        requirement = requirement_service.output(
            requirement_record,
            permission=contract.permissions.model_dump(mode="json"),
        )

        readiness = ProductReferenceReadinessChecker(self.db).check(product_id, provider=provider)
        reference_policy = ProductReferencePolicyService(self.db).check(
            product_id,
            provider=provider,
            product_identity_strict=True,
        )
        approved_assets = self._approved_assets(product_id)
        is_food = contract.product_profile == "food_snack"
        wrapper_assets = [asset for asset in approved_assets if is_food and self._is_wrapper_ref(asset)]
        edible_assets = [asset for asset in approved_assets if is_food and self._is_edible_ref(asset)]
        style_assets = [asset for asset in approved_assets if self._is_style_ref(asset)]
        lifestyle_assets = [asset for asset in approved_assets if self._is_lifestyle_ref(asset)]
        has_bitten = is_food and any(self._has_keywords(asset, BITTEN_KEYWORDS) for asset in approved_assets)
        has_bar_in_hand = is_food and any(self._has_keywords(asset, BAR_IN_HAND_KEYWORDS) for asset in approved_assets)
        approved_identity_ids = [
            item.asset_id
            for item in contract.classified_assets
            if item.eligible and item.family in {"identity", "geometry", "handling"}
        ]
        approved_use_case_ids = [
            item.asset_id
            for item in contract.classified_assets
            if item.eligible and item.family in {"handling", "use_case", "proof", "interaction"}
        ]

        wrapper_count = len(wrapper_assets)
        edible_count = len(edible_assets)
        style_count = len(style_assets)
        lifestyle_count = len(lifestyle_assets)
        wrapper_scene_allowed = contract.permissions.wrapper_scene_allowed
        wrapper_closeup_allowed = contract.permissions.wrapper_closeup_allowed
        unwrapped_product_allowed = contract.permissions.unwrapped_product_allowed
        bite_scene_allowed = contract.permissions.bite_scene_allowed
        texture_macro_allowed = contract.permissions.texture_macro_allowed
        packshot_overlay_required = contract.permissions.packshot_overlay_required
        end_card_required = contract.permissions.end_card_required
        edible_kit_ready = is_food and contract.current_tier == "tier_4"

        blocked_scene_types: list[str] = []
        blockers: list[str] = []
        warnings: list[str] = list(readiness.warnings or []) + list(reference_policy.warnings or [])
        next_actions: list[str] = list(reference_policy.next_actions or [])

        if is_food:
            if wrapper_count < 2:
                blocked_scene_types.append("wrapper_closeup")
                warnings.append("wrapper_closeup_requires_two_approved_wrapper_refs")
                next_actions.append("add_second_wrapper_or_label_reference")
            if edible_count < 3:
                blocked_scene_types.extend(["bite_scene", "texture_macro", "ai_generated_unwrapped_product"])
                warnings.append("edible_scene_requires_three_approved_edible_refs")
                next_actions.append("add_edible_cutaway_texture_and_use_case_refs")
            if not has_bitten:
                blocked_scene_types.append("bite_or_chew_closeup")
                warnings.append("bitten_bar_reference_missing")
                next_actions.append("add_bitten_bar_reference")
            if not has_bar_in_hand:
                blocked_scene_types.append("unwrapped_bar_in_hand")
                warnings.append("bar_in_hand_reference_missing")
                next_actions.append("add_bar_in_hand_reference")
        elif not contract.permissions.interaction_scene_allowed:
            warnings.append(f"{contract.permissions.interaction_mode}_scene_requires_tier_4_use_references")
            next_actions.append(f"add_{contract.permissions.interaction_mode}_references")
        if label_accuracy_required:
            warnings.append("label_accuracy_requires_packshot_overlay_or_end_card")
        if requirement.status != "ready":
            blockers.append(f"product_asset_contract:requires_{requirement.required_tier}_for_final_ad")
            for missing in requirement.missing_asset_types:
                blockers.append(f"product_asset_contract:missing:{missing}")
            next_actions.append("complete_product_asset_contract_before_real_generation")
        if contract.variant_mismatch_asset_ids:
            blockers.append("product_asset_contract:mixed_or_unverified_variant_references")
            next_actions.append("tag_each_identity_asset_with_exact_variant_key")
        if readiness.blockers:
            blockers.extend(f"reference_readiness:{item}" for item in readiness.blockers)
        if reference_policy.blockers:
            blockers.extend(f"reference_policy:{item}" for item in reference_policy.blockers)

        allowed_scene_types = ["creator_talking_head", "reaction_shot", "no_product_generation_lifestyle"]
        if contract.current_tier != "tier_0":
            allowed_scene_types.extend(["packshot_overlay", "end_card"])
        if wrapper_scene_allowed:
            allowed_scene_types.extend(["closed_wrapper_in_hand", "wrapper_reveal"])
        if contract.permissions.cutaway_proof_allowed:
            allowed_scene_types.append("approved_cutaway_insert")
        if wrapper_closeup_allowed:
            allowed_scene_types.append("wrapper_closeup")
        if unwrapped_product_allowed:
            allowed_scene_types.append("unwrapped_bar_in_hand")
        if bite_scene_allowed:
            allowed_scene_types.append("bite_scene")
        if texture_macro_allowed:
            allowed_scene_types.append("texture_macro")
        if contract.permissions.application_scene_allowed:
            allowed_scene_types.append("application_demo")
        if contract.permissions.try_on_scene_allowed:
            allowed_scene_types.append("try_on_demo")
        if contract.permissions.demonstration_scene_allowed:
            allowed_scene_types.append("operation_demo")

        blocked_scene_types = list(dict.fromkeys([*blocked_scene_types, *contract.blocked_scenes]))
        allowed_scene_types = list(dict.fromkeys([*allowed_scene_types, *contract.allowed_scenes]))
        asset_audit = (
            ProductAssetAuditor().build(
                product,
                approved_assets,
                allowed_scene_types=allowed_scene_types,
                blocked_scene_types=blocked_scene_types,
            )
            if is_food
            else None
        )

        return ProductScenePolicyOutput(
            product_id=product.id,
            sku=product.sku,
            provider=provider,
            product_profile=contract.product_profile,
            variant_key=contract.variant_key,
            interaction_mode=contract.permissions.interaction_mode,
            current_asset_tier=contract.current_tier,
            required_asset_tier=requirement.required_tier,
            wrapper_reference_count=wrapper_count,
            edible_reference_count=edible_count,
            style_reference_count=style_count,
            lifestyle_reference_count=lifestyle_count,
            has_bitten_bar_reference=has_bitten,
            has_bar_in_hand_reference=has_bar_in_hand,
            label_accuracy_required=label_accuracy_required,
            wrapper_scene_allowed=wrapper_scene_allowed,
            wrapper_closeup_allowed=wrapper_closeup_allowed,
            unwrapped_product_allowed=unwrapped_product_allowed,
            bite_scene_allowed=bite_scene_allowed,
            texture_macro_allowed=texture_macro_allowed,
            opening_scene_allowed=contract.permissions.opening_scene_allowed,
            cutaway_proof_allowed=contract.permissions.cutaway_proof_allowed,
            near_mouth_allowed=contract.permissions.near_mouth_allowed,
            use_case_scene_allowed=contract.permissions.use_case_scene_allowed,
            interaction_scene_allowed=contract.permissions.interaction_scene_allowed,
            application_scene_allowed=contract.permissions.application_scene_allowed,
            try_on_scene_allowed=contract.permissions.try_on_scene_allowed,
            demonstration_scene_allowed=contract.permissions.demonstration_scene_allowed,
            tasting_scene_allowed=contract.permissions.tasting_scene_allowed,
            provider_generated_packaging_allowed=contract.permissions.provider_generated_packaging_allowed,
            provider_generated_product_allowed=contract.permissions.provider_generated_product_allowed,
            packshot_overlay_required=packshot_overlay_required,
            end_card_required=end_card_required,
            edible_kit_ready=edible_kit_ready,
            approved_wrapper_asset_ids=[asset.id for asset in wrapper_assets],
            approved_edible_asset_ids=[asset.id for asset in edible_assets],
            approved_style_asset_ids=[asset.id for asset in style_assets],
            approved_lifestyle_asset_ids=[asset.id for asset in lifestyle_assets],
            approved_identity_asset_ids=approved_identity_ids,
            approved_use_case_asset_ids=approved_use_case_ids,
            asset_audit=asset_audit,
            blocked_scene_types=blocked_scene_types,
            allowed_scene_types=allowed_scene_types,
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=list(dict.fromkeys(next_actions)),
            reference_readiness=readiness.model_dump(mode="json"),
            reference_policy=reference_policy.model_dump(mode="json"),
            asset_contract={
                "tier": contract.model_dump(mode="json"),
                "requirement": requirement.model_dump(mode="json"),
            },
        )

    def _approved_assets(self, product_id: int) -> list[models.ProductAsset]:
        return (
            self.db.query(models.ProductAsset)
            .filter(models.ProductAsset.product_id == product_id)
            .filter(models.ProductAsset.review_status == "approved")
            .order_by(models.ProductAsset.is_primary_reference.desc(), models.ProductAsset.id)
            .all()
        )

    def _is_wrapper_ref(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in WRAPPER_TYPES or self._has_keywords(asset, WRAPPER_KEYWORDS)

    def _is_edible_ref(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in EDIBLE_TYPES or self._has_keywords(asset, EDIBLE_KEYWORDS)

    def _is_style_ref(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in STYLE_TYPES or self._has_keywords(asset, STYLE_KEYWORDS)

    def _is_lifestyle_ref(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in LIFESTYLE_TYPES or self._has_keywords(asset, LIFESTYLE_KEYWORDS)

    @staticmethod
    def _has_keywords(asset: models.ProductAsset, keywords: set[str]) -> bool:
        text = " ".join(
            str(value or "")
            for value in [
                asset.asset_type,
                asset.asset_role,
                asset.manual_label,
                asset.filename,
                asset.source_ref,
                asset.review_notes,
                asset.metadata_json,
            ]
        ).lower()
        return any(keyword in text for keyword in keywords)
