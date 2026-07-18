from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app import models
from app.assets.errors import AssetKitDataError
from app.assets.image_registry import ImageRegistry, SUPPORTED_EXTENSIONS
from app.config import get_settings
from app.media_storage.backend import StorageBackend
from app.media_storage.errors import MediaArtifactError, StorageError
from app.media_storage.factory import get_storage_backends
from app.media_storage.service import MediaArtifactService


class ProductAssetStorage:
    def __init__(
        self,
        db: Session,
        *,
        backends: Mapping[str, StorageBackend] | None = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.registry = ImageRegistry()
        self.backends = dict(backends) if backends is not None else None

    def upload_file(
        self,
        product_id: int,
        *,
        filename: str,
        content: bytes,
        asset_type: str | None = None,
        manual_label: str | None = None,
        is_primary_reference: bool = False,
        created_by_user_profile_id: int | None = None,
    ) -> models.ProductAsset:
        product = self._product(product_id)
        kit = self._latest_or_create_kit(product.id)
        safe_name = self.safe_filename(filename)
        checksum = hashlib.sha256(content).hexdigest()
        artifact: models.MediaArtifact | None = None
        durable = self.settings.runtime_profile == "production" or self.backends is not None
        if durable:
            if product.organization_id is None or created_by_user_profile_id is None:
                raise AssetKitDataError(
                    "Durable product-reference upload requires an organization and attributable user."
                )
            backends, backend = self._artifact_backend()
            try:
                artifact = MediaArtifactService(self.db, backends).store_bytes(
                    organization_id=product.organization_id,
                    created_by_user_profile_id=created_by_user_profile_id,
                    backend_name=backend.name,
                    kind="product_reference",
                    content=content,
                    mime_type=mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
                    original_filename=safe_name,
                    product_id=product.id,
                    metadata={"source": "product_asset_upload"},
                )
            except (MediaArtifactError, StorageError) as exc:
                raise AssetKitDataError("Product reference could not be stored privately.") from exc
        asset = models.ProductAsset(
            product_id=product.id,
            asset_kit_id=kit.id,
            media_artifact_id=artifact.id if artifact else None,
            source_ref=f"media-artifact://{artifact.public_id}" if artifact else "pending",
            source_type="media_artifact" if artifact else "local",
            asset_type=asset_type or self.registry.classify(safe_name),
            asset_role="primary_reference" if is_primary_reference else None,
            filename=safe_name,
            extension=Path(safe_name).suffix.lower() or None,
            mime_type=mimetypes.guess_type(safe_name)[0],
            exists=artifact is not None,
            status="ready",
            is_primary_reference=is_primary_reference,
            is_safe_for_real_generation=False,
            manual_label=manual_label,
            review_status="pending",
            checksum=checksum,
            metadata_json=(
                {
                    "storage": "private_media_artifact",
                    "artifact_public_id": artifact.public_id,
                }
                if artifact
                else {"storage": "local_upload"}
            ),
            warnings_json=[],
        )
        self.db.add(asset)
        self.db.flush()
        if artifact is None:
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

    def _artifact_backend(self) -> tuple[dict[str, StorageBackend], StorageBackend]:
        backends = dict(self.backends) if self.backends is not None else get_storage_backends()
        if not backends:
            raise AssetKitDataError("Private media storage is not configured.")
        preferred = backends.get(str(self.settings.storage_backend))
        backend = preferred or (next(iter(backends.values())) if len(backends) == 1 else None)
        if backend is None:
            raise AssetKitDataError("Private media storage backend is ambiguous.")
        if self.settings.runtime_profile == "production" and backend.name == "local":
            raise AssetKitDataError("Local product-reference storage is forbidden in production.")
        return backends, backend

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
        descriptor = self.registry.describe(self.remote_asset_url(url))
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
        metadata = dict(asset.metadata_json or {})
        for key in {"variant_key", "contract_type", "shared_non_identity"}:
            if key in updates and updates[key] is not None:
                metadata[key] = updates[key]
        asset.metadata_json = metadata
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
                "media_artifact_id": asset.media_artifact_id,
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
                "metadata": asset.metadata_json,
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
    def remote_asset_url(url: str) -> str:
        value = str(url or "").strip()
        try:
            parsed = urlsplit(value)
            parsed.port
        except (TypeError, ValueError) as exc:
            raise AssetKitDataError("Product asset URL is invalid.") from exc
        if (
            parsed.scheme.casefold() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise AssetKitDataError("Product asset URL must be an HTTP(S) URL without credentials.")
        return value

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
