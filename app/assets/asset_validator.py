from __future__ import annotations

from app.assets.image_registry import SUPPORTED_EXTENSIONS
from app.assets.types import AssetValidationReport, ProductAssetDescriptor


class AssetValidator:
    def validate(
        self,
        assets: list[ProductAssetDescriptor],
        *,
        require_real_generation: bool = False,
        override_required_assets: bool = False,
    ) -> AssetValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        asset_types = {asset.asset_type for asset in assets}
        missing_assets = [
            required for required in ["packshot", "label_closeup", "lifestyle"] if required not in asset_types
        ]
        for asset in assets:
            if not asset.source_ref:
                errors.append("Asset source is empty.")
            if asset.source_type == "local" and not asset.exists:
                errors.append(f"Local asset does not exist: {asset.source_ref}")
            if asset.extension and asset.extension.lower() not in SUPPORTED_EXTENSIONS:
                errors.append(f"Unsupported image extension: {asset.source_ref}")
            if not asset.extension:
                warnings.append(f"Asset extension is unknown: {asset.source_ref}")
            warnings.extend(asset.warnings)
        if not assets:
            warnings.append("No product reference images available.")
        for missing in missing_assets:
            warnings.append(f"Missing {missing} asset.")
        if require_real_generation and not override_required_assets:
            if "packshot" in missing_assets:
                errors.append("Real provider generation requires a packshot unless override is passed.")
            if not any(asset.exists and asset.extension in SUPPORTED_EXTENSIONS for asset in assets):
                errors.append("Real provider generation requires at least one usable product image.")
        return AssetValidationReport(
            valid=not errors,
            errors=list(dict.fromkeys(errors)),
            warnings=list(dict.fromkeys(warnings)),
            real_generation_allowed=not errors and bool(assets) and "packshot" not in missing_assets,
            missing_assets=missing_assets,
        )
