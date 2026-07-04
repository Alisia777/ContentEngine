from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app import models
from app.assets.image_registry import SECRET_QUERY_KEYS, SUPPORTED_EXTENSIONS
from app.assets.types import ProductReferenceReadiness


REFERENCE_TYPES = {"packshot", "product", "label_closeup", "lifestyle", "unknown"}


class ProductReferenceReadinessChecker:
    def __init__(self, db: Session):
        self.db = db

    def check(self, product_id: int, *, provider: str = "runway") -> ProductReferenceReadiness:
        kit = self._latest_kit(product_id)
        assets = self._assets(product_id, kit.id if kit else None)
        blockers: list[str] = []
        warnings: list[str] = []
        usable = [asset for asset in assets if self._is_usable(asset, blockers, warnings)]
        approved = [asset for asset in usable if asset.review_status == "approved"]
        primary = next((asset for asset in approved if asset.is_primary_reference), None)
        if not primary:
            blockers.append("missing_approved_primary_reference")
        if primary and primary.asset_type not in {"packshot", "product", "unknown"}:
            warnings.append("Primary reference is not a packshot/general product image.")
        asset_types = {asset.asset_type for asset in approved}
        if "label_closeup" not in asset_types:
            warnings.append("Missing approved label closeup asset.")
        if "lifestyle" not in asset_types:
            warnings.append("Missing approved lifestyle asset.")
        if provider != "runway":
            warnings.append(f"Provider reference support is not confirmed for {provider}; bundle is kept for prompt accuracy.")
        reference_assets = approved[:4]
        status = "ready" if not blockers else "blocked"
        bundle = {
            "provider": provider,
            "status": status,
            "primary_reference_asset_id": primary.id if primary else None,
            "reference_asset_ids": [asset.id for asset in reference_assets],
            "reference_images": [self._public_ref(asset) for asset in reference_assets],
            "notes": ["Internal provider-ready reference bundle; adapter field names must be confirmed before paid use."],
        }
        readiness = ProductReferenceReadiness(
            status=status,
            real_generation_allowed=not blockers,
            primary_reference_asset_id=primary.id if primary else None,
            reference_asset_ids=[asset.id for asset in reference_assets],
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            provider_reference_bundle=bundle,
        )
        if kit:
            kit.primary_reference_asset_id = readiness.primary_reference_asset_id
            kit.provider_reference_bundle_json = readiness.provider_reference_bundle
            kit.real_generation_allowed = readiness.real_generation_allowed
            kit.real_generation_blockers_json = readiness.blockers
            kit.warnings_json = readiness.warnings
            kit.status = "ready" if readiness.real_generation_allowed else "needs_assets"
            for asset in assets:
                asset.is_safe_for_real_generation = asset.id in readiness.reference_asset_ids
            self.db.commit()
        return readiness

    def _latest_kit(self, product_id: int) -> models.ProductAssetKit | None:
        return (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        )

    def _assets(self, product_id: int, asset_kit_id: int | None) -> list[models.ProductAsset]:
        query = self.db.query(models.ProductAsset).filter(models.ProductAsset.product_id == product_id)
        if asset_kit_id:
            query = query.filter(models.ProductAsset.asset_kit_id == asset_kit_id)
        return query.order_by(models.ProductAsset.id).all()

    def _is_usable(self, asset: models.ProductAsset, blockers: list[str], warnings: list[str]) -> bool:
        if asset.review_status == "rejected":
            return False
        if asset.asset_type not in REFERENCE_TYPES:
            return False
        if asset.extension and asset.extension.lower() not in SUPPORTED_EXTENSIONS:
            self._risk(asset, f"unsupported_file_type:{asset.id}", blockers, warnings)
            return False
        if asset.source_type == "local" and (not asset.exists or not Path(asset.source_ref).exists()):
            self._risk(asset, f"missing_local_asset:{asset.id}", blockers, warnings)
            return False
        if not asset.source_ref:
            self._risk(asset, f"missing_asset_source:{asset.id}", blockers, warnings)
            return False
        return True

    @staticmethod
    def _risk(asset: models.ProductAsset, message: str, blockers: list[str], warnings: list[str]) -> None:
        if asset.is_primary_reference:
            blockers.append(message)
        else:
            warnings.append(message)

    @staticmethod
    def _public_ref(asset: models.ProductAsset) -> str:
        parsed = urlparse(asset.source_ref)
        if parsed.scheme not in {"http", "https"}:
            return asset.source_ref
        if any(key.lower() in SECRET_QUERY_KEYS for key in [part.split("=", 1)[0] for part in parsed.query.split("&") if part]):
            return parsed._replace(query="", fragment="").geturl()
        return parsed._replace(fragment="").geturl()
