from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app import models
from app.one_video_acceptance.types import AssetAuditItem, ProductAssetAuditOutput


class ProductAssetAuditor:
    def build(
        self,
        product: models.Product,
        approved_assets: list[models.ProductAsset],
        *,
        allowed_scene_types: list[str],
        blocked_scene_types: list[str],
    ) -> ProductAssetAuditOutput:
        wrapper_items = [
            self._item("front_packshot", "front packshot", approved_assets, self._front_packshot, next_action="add_front_packshot"),
            self._item("angled_wrapper", "angled wrapper", approved_assets, self._angled_wrapper, next_action="add_angled_wrapper_reference"),
            self._item("wrapper_in_hand", "wrapper in hand", approved_assets, self._wrapper_in_hand, next_action="add_wrapper_in_hand_reference"),
            self._item("semi_open_wrapper", "semi-open wrapper", approved_assets, self._semi_open_wrapper, next_action="add_semi_open_wrapper_reference"),
            self._wrapper_with_edible_item(approved_assets),
        ]
        edible_items = [
            self._item("whole_unwrapped_bar", "whole unwrapped bar", approved_assets, self._whole_unwrapped_bar, next_action="add_whole_unwrapped_bar_reference"),
            self._item("cutaway", "cutaway", approved_assets, self._cutaway, next_action="add_cutaway_reference"),
            self._item("bitten_bar", "bitten bar", approved_assets, self._bitten_bar, next_action="add_bitten_bar_reference"),
            self._item("bar_in_hand", "bar in hand", approved_assets, self._bar_in_hand, next_action="add_bar_in_hand_reference"),
            self._item("bar_near_mouth", "bar near mouth", approved_assets, self._bar_near_mouth, next_action="add_bar_near_mouth_reference"),
            self._texture_macro_item(approved_assets),
        ]
        style_items = [
            self._item("creator_at_table", "creator at table", approved_assets, self._creator_at_table, next_action="add_creator_at_table_style_reference"),
            self._item("home_setting", "home setting", approved_assets, self._home_setting, next_action="add_home_setting_style_reference"),
        ]
        lifestyle_items = [
            self._item("coffee_table_context", "coffee/table context", approved_assets, self._coffee_table_context, next_action="add_coffee_table_context_reference"),
        ]
        missing = [
            item.next_action
            for item in [*wrapper_items, *edible_items, *style_items, *lifestyle_items]
            if item.status in {"no", "partial"} and item.next_action
        ]
        return ProductAssetAuditOutput(
            product_id=product.id,
            sku=product.sku,
            wrapper_refs=wrapper_items,
            edible_refs=edible_items,
            style_refs=style_items,
            lifestyle_refs=lifestyle_items,
            allowed_scenes=allowed_scene_types,
            blocked_scenes=blocked_scene_types,
            missing_refs=list(dict.fromkeys(missing)),
            decision=self._decision(blocked_scene_types),
        )

    def _item(
        self,
        key: str,
        label: str,
        assets: list[models.ProductAsset],
        predicate: Callable[[models.ProductAsset], bool],
        *,
        next_action: str,
        partial: bool = False,
    ) -> AssetAuditItem:
        matches = [asset for asset in assets if predicate(asset)]
        status = "yes" if matches else "partial" if partial else "no"
        return AssetAuditItem(
            key=key,
            label=label,
            status=status,
            asset_ids=[asset.id for asset in matches],
            evidence=[self._asset_label(asset) for asset in matches],
            next_action=None if status == "yes" else next_action,
        )

    def _wrapper_with_edible_item(self, assets: list[models.ProductAsset]) -> AssetAuditItem:
        matches = [asset for asset in assets if self._wrapper(asset) and (self._cutaway(asset) or self._whole_unwrapped_bar(asset))]
        partial = not matches and any(self._wrapper(asset) for asset in assets) and any(self._cutaway(asset) or self._whole_unwrapped_bar(asset) for asset in assets)
        item = self._item(
            "wrapper_plus_edible_product",
            "wrapper + edible product",
            assets,
            lambda asset: asset in matches,
            next_action="add_wrapper_plus_edible_product_reference",
            partial=partial,
        )
        if partial:
            item.evidence = ["wrapper and edible refs exist separately, but not together"]
        return item

    def _texture_macro_item(self, assets: list[models.ProductAsset]) -> AssetAuditItem:
        matches = [asset for asset in assets if self._texture_macro(asset)]
        partial = not matches and any(self._cutaway(asset) for asset in assets)
        item = self._item("texture_macro", "texture macro", assets, lambda asset: asset in matches, next_action="add_texture_macro_reference", partial=partial)
        if partial:
            item.evidence = ["cutaway exists, but no dedicated texture macro reference"]
        return item

    @staticmethod
    def _decision(blocked_scene_types: list[str]) -> str:
        if "bite_scene" in blocked_scene_types or "texture_macro" in blocked_scene_types:
            return "safe_prompt_only_or_overlay_until_edible_refs_ready"
        if blocked_scene_types:
            return "limited_real_smoke_with_policy_blocks"
        return "eligible_for_limited_real_smoke_after_spend_gates"

    def _front_packshot(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type == "packshot" or self._has_any(asset, {"front packshot", "front", "фронт"})

    def _angled_wrapper(self, asset: models.ProductAsset) -> bool:
        return self._wrapper(asset) and self._has_any(asset, {"angle", "angled", "45", "side", "profile", "под углом", "бок"})

    def _wrapper_in_hand(self, asset: models.ProductAsset) -> bool:
        return self._wrapper(asset) and self._has_any(asset, {"in hand", "hand", "holding", "в руке", "держит"})

    def _semi_open_wrapper(self, asset: models.ProductAsset) -> bool:
        return self._wrapper(asset) and self._has_any(asset, {"semi-open", "partially open", "opened", "open wrapper", "полуоткры", "открыт"})

    def _whole_unwrapped_bar(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type == "unwrapped" or self._has_any(asset, {"whole unwrapped", "unwrapped bar", "bare bar", "без упаковки", "целый батончик"})

    def _cutaway(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in {"cutaway", "slice", "sliced"} or self._has_any(asset, {"cutaway", "cross section", "sliced", "inside filling", "разрез", "начинка"})

    def _bitten_bar(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in {"bite", "bitten"} or self._has_any(asset, {"bitten", "bite mark", "надкус", "укус"})

    def _bar_in_hand(self, asset: models.ProductAsset) -> bool:
        return self._has_any(asset, {"bar in hand", "unwrapped in hand", "в руке", "держит батончик"})

    def _bar_near_mouth(self, asset: models.ProductAsset) -> bool:
        return self._has_any(asset, {"near mouth", "at mouth", "mouth", "у рта", "возле рта"})

    def _texture_macro(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in {"texture", "macro"} or self._has_any(asset, {"texture macro", "macro", "close texture", "макро", "текстура крупно"})

    def _creator_at_table(self, asset: models.ProductAsset) -> bool:
        return self._has_any(asset, {"creator at table", "female creator", "blogger", "ugc creator", "девушка", "блогер"}) and self._has_any(asset, {"table", "coffee", "стол", "кофе"})

    def _home_setting(self, asset: models.ProductAsset) -> bool:
        return self._has_any(asset, {"home", "home setting", "kitchen", "living room", "дом", "кухня"})

    def _coffee_table_context(self, asset: models.ProductAsset) -> bool:
        return self._has_any(asset, {"coffee", "table", "plate", "cup", "кофе", "стол", "чашка", "тарелка"})

    def _wrapper(self, asset: models.ProductAsset) -> bool:
        return asset.asset_type in {"packshot", "product", "label_closeup", "packaging_closeup", "label", "packaging"} or self._has_any(
            asset,
            {"wrapper", "packshot", "package", "packaging", "label", "оберт", "упаков", "этикет"},
        )

    @staticmethod
    def _asset_label(asset: models.ProductAsset) -> str:
        return str(asset.manual_label or asset.filename or asset.source_ref or f"asset:{asset.id}")

    def _has_any(self, asset: models.ProductAsset, keywords: set[str]) -> bool:
        text = self._asset_text(asset)
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _asset_text(asset: models.ProductAsset) -> str:
        values: list[Any] = [
            asset.asset_type,
            asset.asset_role,
            asset.manual_label,
            asset.filename,
            asset.source_ref,
            asset.review_notes,
            asset.metadata_json,
        ]
        return " ".join(str(value or "") for value in values).lower()
