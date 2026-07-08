from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.one_video_acceptance.errors import OneVideoAcceptanceDataError
from app.one_video_acceptance.types import ProductScenePolicyOutput


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

        readiness = ProductReferenceReadinessChecker(self.db).check(product_id, provider=provider)
        reference_policy = ProductReferencePolicyService(self.db).check(
            product_id,
            provider=provider,
            product_identity_strict=True,
        )
        approved_assets = self._approved_assets(product_id)
        wrapper_assets = [asset for asset in approved_assets if self._is_wrapper_ref(asset)]
        edible_assets = [asset for asset in approved_assets if self._is_edible_ref(asset)]
        style_assets = [asset for asset in approved_assets if self._is_style_ref(asset)]
        lifestyle_assets = [asset for asset in approved_assets if self._is_lifestyle_ref(asset)]
        has_bitten = any(self._has_keywords(asset, BITTEN_KEYWORDS) for asset in approved_assets)
        has_bar_in_hand = any(self._has_keywords(asset, BAR_IN_HAND_KEYWORDS) for asset in approved_assets)

        wrapper_count = len(wrapper_assets)
        edible_count = len(edible_assets)
        style_count = len(style_assets)
        lifestyle_count = len(lifestyle_assets)
        wrapper_scene_allowed = wrapper_count >= 1
        wrapper_closeup_allowed = wrapper_count >= 2
        unwrapped_product_allowed = edible_count >= 3 and has_bar_in_hand
        bite_scene_allowed = edible_count >= 3 and has_bitten
        texture_macro_allowed = edible_count >= 3
        packshot_overlay_required = label_accuracy_required or wrapper_count < 2
        end_card_required = label_accuracy_required
        edible_kit_ready = edible_count >= 3 and has_bitten and has_bar_in_hand

        blocked_scene_types: list[str] = []
        blockers: list[str] = []
        warnings: list[str] = list(readiness.warnings or []) + list(reference_policy.warnings or [])
        next_actions: list[str] = list(reference_policy.next_actions or [])

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
        if label_accuracy_required:
            warnings.append("label_accuracy_requires_packshot_overlay_or_end_card")
        if readiness.blockers:
            blockers.extend(f"reference_readiness:{item}" for item in readiness.blockers)
        if reference_policy.blockers:
            blockers.extend(f"reference_policy:{item}" for item in reference_policy.blockers)

        allowed_scene_types = [
            "creator_talking_head",
            "closed_wrapper_in_hand",
            "wrapper_reveal",
            "approved_cutaway_insert",
            "packshot_overlay",
            "end_card",
            "reaction_shot",
        ]
        if wrapper_closeup_allowed:
            allowed_scene_types.append("wrapper_closeup")
        if unwrapped_product_allowed:
            allowed_scene_types.append("unwrapped_bar_in_hand")
        if bite_scene_allowed:
            allowed_scene_types.append("bite_scene")
        if texture_macro_allowed:
            allowed_scene_types.append("texture_macro")

        return ProductScenePolicyOutput(
            product_id=product.id,
            sku=product.sku,
            provider=provider,
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
            packshot_overlay_required=packshot_overlay_required,
            end_card_required=end_card_required,
            edible_kit_ready=edible_kit_ready,
            approved_wrapper_asset_ids=[asset.id for asset in wrapper_assets],
            approved_edible_asset_ids=[asset.id for asset in edible_assets],
            approved_style_asset_ids=[asset.id for asset in style_assets],
            approved_lifestyle_asset_ids=[asset.id for asset in lifestyle_assets],
            blocked_scene_types=list(dict.fromkeys(blocked_scene_types)),
            allowed_scene_types=list(dict.fromkeys(allowed_scene_types)),
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=list(dict.fromkeys(next_actions)),
            reference_readiness=readiness.model_dump(mode="json"),
            reference_policy=reference_policy.model_dump(mode="json"),
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
