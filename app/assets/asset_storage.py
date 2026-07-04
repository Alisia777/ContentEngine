from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.assets.errors import AssetKitDataError
from app.assets.image_registry import ImageRegistry, SUPPORTED_EXTENSIONS
from app.config import get_settings


class ProductAssetStorage:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.registry = ImageRegistry()

    def upload_file(
        self,
        product_id: int,
        *,
        filename: str,
        content: bytes,
        asset_type: str | None = None,
        manual_label: str | None = None,
        is_primary_reference: bool = False,
    ) -> models.ProductAsset:
        product = self._product(product_id)
        kit = self._latest_or_create_kit(product.id)
        safe_name = self.safe_filename(filename)
        checksum = hashlib.sha256(content).hexdigest()
        asset = models.ProductAsset(
            product_id=product.id,
            asset_kit_id=kit.id,
            source_ref="pending",
            source_type="local",
            asset_type=asset_type or self.registry.classify(safe_name),
            asset_role="primary_reference" if is_primary_reference else None,
            filename=safe_name,
            extension=Path(safe_name).suffix.lower() or None,
            mime_type=mimetypes.guess_type(safe_name)[0],
            exists=False,
            status="ready",
            is_primary_reference=is_primary_reference,
            is_safe_for_real_generation=False,
            manual_label=manual_label,
            review_status="pending",
            checksum=checksum,
            metadata_json={"storage": "local_upload"},
            warnings_json=[],
        )
        self.db.add(asset)
        self.db.flush()
        target_dir = self.settings.media_root / "products" / str(product.id) / "assets"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{asset.id}_{safe_name}"
        target_path.write_bytes(content)
        asset.source_ref = target_path.as_posix()
        asset.exists = target_path.exists()
        self._mark_primary(asset)
        self._sync_kit(kit)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def attach_url(
        self,
        product_id: int,
        *,
        url: str,
        asset_type: str | None = None,
        manual_label: str | None = None,
        is_primary_reference: bool = False,
    ) -> models.ProductAsset:
        product = self._product(product_id)
        kit = self._latest_or_create_kit(product.id)
        descriptor = self.registry.describe(url)
        asset = models.ProductAsset(
            product_id=product.id,
            asset_kit_id=kit.id,
            source_ref=descriptor.source_ref,
            source_type="url",
            asset_type=asset_type or descriptor.asset_type,
            asset_role="primary_reference" if is_primary_reference else None,
            filename=descriptor.filename,
            extension=descriptor.extension,
            mime_type=descriptor.mime_type,
            width=descriptor.width,
            height=descriptor.height,
            exists=True,
            status="ready",
            is_primary_reference=is_primary_reference,
            is_safe_for_real_generation=False,
            manual_label=manual_label,
            review_status="pending",
            metadata_json=descriptor.metadata,
            warnings_json=descriptor.warnings,
        )
        self.db.add(asset)
        self.db.flush()
        self._mark_primary(asset)
        self._sync_kit(kit)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def update_asset(self, asset_id: int, **updates) -> models.ProductAsset:
        asset = self.db.get(models.ProductAsset, asset_id)
        if not asset:
            raise AssetKitDataError(f"ProductAsset {asset_id} not found.")
        allowed = {
            "asset_type",
            "asset_role",
            "is_primary_reference",
            "manual_label",
            "review_status",
            "review_notes",
        }
        for key, value in updates.items():
            if key in allowed and value is not None:
                setattr(asset, key, value)
        if asset.is_primary_reference:
            asset.asset_role = asset.asset_role or "primary_reference"
            self._mark_primary(asset)
        self._sync_kit(asset.asset_kit)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def _product(self, product_id: int) -> models.Product:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise AssetKitDataError(f"Product {product_id} not found.")
        return product

    def _latest_or_create_kit(self, product_id: int) -> models.ProductAssetKit:
        kit = (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        )
        if kit:
            return kit
        kit = models.ProductAssetKit(
            product_id=product_id,
            status="needs_assets",
            required_assets_json=["packshot", "label_closeup", "lifestyle"],
            missing_assets_json=["packshot", "label_closeup", "lifestyle"],
            validation_report_json={},
            warnings_json=[],
            real_generation_allowed=False,
            real_generation_blockers_json=["missing_primary_reference"],
        )
        self.db.add(kit)
        self.db.flush()
        return kit

    def _mark_primary(self, asset: models.ProductAsset) -> None:
        if not asset.is_primary_reference:
            return
        for other in self.db.query(models.ProductAsset).filter(models.ProductAsset.product_id == asset.product_id):
            if other.id != asset.id:
                other.is_primary_reference = False
        asset.asset_kit.primary_reference_asset_id = asset.id

    @staticmethod
    def _sync_kit(kit: models.ProductAssetKit) -> None:
        assets = sorted(kit.assets, key=lambda item: item.id)
        kit.assets_json = [
            {
                "id": asset.id,
                "source_ref": asset.source_ref,
                "source_type": asset.source_type,
                "asset_type": asset.asset_type,
                "asset_role": asset.asset_role,
                "filename": asset.filename,
                "extension": asset.extension,
                "mime_type": asset.mime_type,
                "width": asset.width,
                "height": asset.height,
                "exists": asset.exists,
                "is_primary_reference": asset.is_primary_reference,
                "is_safe_for_real_generation": asset.is_safe_for_real_generation,
                "manual_label": asset.manual_label,
                "review_status": asset.review_status,
                "checksum": asset.checksum,
                "warnings": asset.warnings_json,
            }
            for asset in assets
        ]
        asset_types = {asset.asset_type for asset in assets}
        kit.missing_assets_json = [
            required for required in ["packshot", "label_closeup", "lifestyle"] if required not in asset_types
        ]
        kit.primary_reference_asset_id = next((asset.id for asset in assets if asset.is_primary_reference), None)

    @staticmethod
    def safe_filename(filename: str) -> str:
        name = Path(filename or "asset").name
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
        if not name:
            name = "asset"
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            return name
        return name[:180]
