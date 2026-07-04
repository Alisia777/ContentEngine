from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.creative.types import CreativeSpec
from app.variants.errors import VariantDataError
from app.variants.types import FirstFrameOptionOutput


class FirstFrameBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_options(
        self,
        creative_spec_id: int,
        *,
        asset_kit_id: int | None = None,
    ) -> list[models.FirstFrameOption]:
        spec_record = self.db.get(models.VideoCreativeSpecRecord, creative_spec_id)
        if not spec_record:
            raise VariantDataError(f"VideoCreativeSpecRecord {creative_spec_id} not found.")
        asset_kit = self._asset_kit(spec_record.product_id, asset_kit_id)
        spec = CreativeSpec.model_validate(spec_record.spec_json)
        outputs = self._outputs(spec, asset_kit)
        records = []
        for index, output in enumerate(outputs, start=1):
            record = models.FirstFrameOption(
                creative_spec_id=spec_record.id,
                asset_kit_id=asset_kit.id if asset_kit else None,
                option_number=index,
                status="needs_review" if output.risk_flags else "ready",
                hook_text=output.hook_text,
                visual_concept=output.visual_concept,
                text_overlay=output.text_overlay,
                product_placement=output.product_placement,
                camera_motion=output.camera_motion,
                composition=output.composition,
                product_visible_by_second=output.product_visible_by_second,
                required_assets_json=output.required_assets,
                risk_flags_json=output.risk_flags,
                option_json=output.model_dump(mode="json"),
            )
            self.db.add(record)
            records.append(record)
        self.db.commit()
        for record in records:
            self.db.refresh(record)
        return records

    def _asset_kit(self, product_id: int, asset_kit_id: int | None) -> models.ProductAssetKit | None:
        if asset_kit_id:
            return self.db.get(models.ProductAssetKit, asset_kit_id)
        return (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        ) or AssetKitBuilder(self.db).build_for_product(product_id)

    def _outputs(self, spec: CreativeSpec, asset_kit: models.ProductAssetKit | None) -> list[FirstFrameOptionOutput]:
        missing_assets = set(asset_kit.missing_assets_json if asset_kit else ["packshot", "label_closeup", "lifestyle"])
        kit_asset_types = {asset.get("asset_type") for asset in (asset_kit.assets_json if asset_kit else [])}
        hooks = spec.hook_candidates[:3] or [spec.selected_hook]
        concepts = [
            (
                "packshot_stop_scroll",
                "packshot",
                f"Open on {spec.product_title} filling the center third with the hook already visible.",
                "Product front-facing in the first frame, large enough to verify shape and packaging.",
            ),
            (
                "label_proof",
                "label_closeup",
                f"Start with a readable product detail, then widen to the full {spec.product_title}.",
                "Label or product detail appears beside a full product silhouette.",
            ),
            (
                "lifestyle_use_case",
                "lifestyle",
                f"Show the product in a realistic use context tied to {spec.creative_objective}.",
                "Product is in hand or on surface, not hidden by props.",
            ),
        ]
        options = []
        for index, (concept_key, required_asset, visual, placement) in enumerate(concepts):
            hook = hooks[index % len(hooks)]
            risks = []
            if required_asset in missing_assets:
                risks.append(f"missing_{required_asset}")
            if "packshot" not in kit_asset_types:
                risks.append("packshot_missing_for_product_accuracy")
            overlay = self._short_overlay(hook.hook_text)
            if len(overlay) > 64:
                risks.append("overlay_may_be_hard_to_read")
            options.append(
                FirstFrameOptionOutput(
                    hook_text=hook.hook_text,
                    visual_concept=visual,
                    text_overlay=overlay,
                    product_placement=placement,
                    camera_motion="fast settle into slow push-in" if index == 0 else "stable product-first reveal",
                    composition="vertical 9:16, product visible before text animation, overlay clear of packaging",
                    required_assets=[required_asset],
                    risk_flags=list(dict.fromkeys(risks)),
                    product_visible_by_second=1.0,
                    source_flags=hook.source_flags,
                )
            )
        return options

    @staticmethod
    def _short_overlay(text: str) -> str:
        words = text.split()
        overlay = " ".join(words[:9])
        return overlay if len(overlay) <= 72 else overlay[:69].rstrip() + "..."
