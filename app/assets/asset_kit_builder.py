from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.assets.asset_validator import AssetValidator
from app.assets.errors import AssetKitDataError
from app.assets.image_registry import ImageRegistry


class AssetKitBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.registry = ImageRegistry()
        self.validator = AssetValidator()

    def build_for_product(
        self,
        product_id: int,
        *,
        override_required_assets: bool = False,
    ) -> models.ProductAssetKit:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise AssetKitDataError(f"Product {product_id} not found.")
        descriptors = [
            self.registry.describe(reference)
            for reference in (product.images_json or [])
            if reference
        ]
        validation = self.validator.validate(
            descriptors,
            require_real_generation=True,
            override_required_assets=override_required_assets,
        )
        kit = models.ProductAssetKit(
            product_id=product.id,
            status="ready" if validation.valid else "needs_assets",
            assets_json=[asset.model_dump(mode="json") for asset in descriptors],
            required_assets_json=["packshot", "label_closeup", "lifestyle"],
            missing_assets_json=validation.missing_assets,
            validation_report_json=validation.model_dump(mode="json"),
            warnings_json=validation.warnings,
            real_generation_allowed=validation.real_generation_allowed or override_required_assets,
            override_required_assets=override_required_assets,
        )
        self.db.add(kit)
        self.db.flush()
        for descriptor in descriptors:
            self.db.add(
                models.ProductAsset(
                    product_id=product.id,
                    asset_kit_id=kit.id,
                    source_ref=descriptor.source_ref,
                    source_type=descriptor.source_type,
                    asset_type=descriptor.asset_type,
                    asset_role=None,
                    filename=descriptor.filename,
                    extension=descriptor.extension,
                    mime_type=descriptor.mime_type,
                    width=descriptor.width,
                    height=descriptor.height,
                    exists=descriptor.exists,
                    status="ready",
                    is_primary_reference=False,
                    is_safe_for_real_generation=False,
                    review_status="pending",
                    metadata_json=descriptor.metadata,
                    warnings_json=descriptor.warnings,
                )
            )
        self.db.commit()
        self.db.refresh(kit)
        return kit
