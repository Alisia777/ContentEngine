from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.assets.errors import AssetKitDataError
from app.assets.readiness_checker import ProductReferenceReadinessChecker


class ProviderReferenceBundleBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, product_id: int, *, provider: str = "runway") -> models.ProductReferenceBundle:
        kit = (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        )
        if not kit:
            raise AssetKitDataError(f"Product {product_id} has no asset kit.")
        readiness = ProductReferenceReadinessChecker(self.db).check(product_id, provider=provider)
        provider_payload = {
            "provider": provider,
            "reference_bundle_version": "internal_v1",
            "primary_image_asset_id": readiness.primary_reference_asset_id,
            "reference_asset_ids": readiness.reference_asset_ids,
            "reference_images": readiness.provider_reference_bundle.get("reference_images", []),
            "adapter_todo": "Confirm exact provider reference-image request fields before paid use.",
        }
        bundle = models.ProductReferenceBundle(
            product_id=product_id,
            asset_kit_id=kit.id,
            status=readiness.status,
            provider=provider,
            primary_image_asset_id=readiness.primary_reference_asset_id,
            reference_asset_ids_json=readiness.reference_asset_ids,
            provider_payload_json=provider_payload,
            blockers_json=readiness.blockers,
            warnings_json=readiness.warnings,
        )
        self.db.add(bundle)
        kit.provider_reference_bundle_json = {
            "id": None,
            **provider_payload,
            "status": readiness.status,
            "blockers": readiness.blockers,
            "warnings": readiness.warnings,
        }
        kit.real_generation_allowed = readiness.real_generation_allowed
        kit.real_generation_blockers_json = readiness.blockers
        kit.primary_reference_asset_id = readiness.primary_reference_asset_id
        self.db.flush()
        kit.provider_reference_bundle_json = {
            **kit.provider_reference_bundle_json,
            "id": bundle.id,
        }
        self.db.commit()
        self.db.refresh(bundle)
        return bundle
