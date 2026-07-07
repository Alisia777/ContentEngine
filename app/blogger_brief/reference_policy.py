from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.blogger_brief.errors import BloggerBriefDataError
from app.blogger_brief.types import (
    ONE_REFERENCE_ALLOWED_MODES,
    STRICT_ONE_REFERENCE_BLOCKED_MODES,
    ProductReferencePolicy,
)


LABEL_TYPES = {"label_closeup", "packaging_closeup", "label", "packaging"}
PACKSHOT_TYPES = {"packshot", "product", "unknown"}
CONTEXT_TYPES = {"lifestyle", "context", "use_case", "texture", "side_view", "back_view"}


class ProductReferencePolicyService:
    def __init__(self, db: Session):
        self.db = db

    def check(
        self,
        product_id: int,
        *,
        provider: str = "runway",
        product_identity_strict: bool = True,
    ) -> ProductReferencePolicy:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise BloggerBriefDataError(f"Product {product_id} not found.")

        readiness = ProductReferenceReadinessChecker(self.db).check(product_id, provider=provider)
        approved_assets = self._approved_assets(product_id)
        approved_count = len(approved_assets)
        approved_types = sorted({asset.asset_type for asset in approved_assets})
        primary = next((asset for asset in approved_assets if asset.is_primary_reference), None)
        primary_id = primary.id if primary else readiness.primary_reference_asset_id

        missing_types = self._missing_reference_types(approved_assets)
        warnings = list(readiness.warnings or [])
        blockers = list(readiness.blockers or [])
        if approved_count < 2 and product_identity_strict:
            blockers.append("strict_product_identity_requires_two_approved_references")
        if approved_count < 3:
            warnings.append("recommended_three_product_references_missing")
        if "label_closeup" in missing_types:
            warnings.append("label_or_packaging_closeup_missing")
        if "context_or_scale" in missing_types:
            warnings.append("scale_use_case_or_context_reference_missing")

        if approved_count >= 2 and not blockers:
            product_lock_mode = "reference_i2v"
        elif approved_count == 1:
            product_lock_mode = "packshot_overlay"
        else:
            product_lock_mode = "no_product_generation"

        strict_allowed = product_identity_strict and product_lock_mode == "reference_i2v" and not blockers
        status = "ready" if strict_allowed or (not product_identity_strict and approved_count >= 1) else "blocked"
        if approved_count == 1:
            status = "limited"
        if approved_count == 0:
            status = "blocked"

        next_actions = []
        if approved_count < 2:
            next_actions.append("add_product_references")

        mass_status = "strict_real_ready" if strict_allowed else "needs_reference_gate"
        if approved_count == 1:
            mass_status = "one_photo_limited_overlay_only"
        elif approved_count == 0:
            mass_status = "blocked_missing_references"

        return ProductReferencePolicy(
            product_id=product.id,
            sku=product.sku,
            provider=provider,
            product_identity_strict=product_identity_strict,
            status=status,
            mass_generation_safety_status=mass_status,
            approved_reference_count=approved_count,
            primary_reference_asset_id=primary_id,
            reference_asset_ids=[asset.id for asset in approved_assets[:4]],
            approved_reference_types=approved_types,
            missing_reference_types=missing_types,
            product_lock_mode=product_lock_mode,
            allowed_modes=list(ONE_REFERENCE_ALLOWED_MODES) if approved_count <= 1 else ["reference_i2v", *ONE_REFERENCE_ALLOWED_MODES],
            blocked_modes=list(STRICT_ONE_REFERENCE_BLOCKED_MODES) if approved_count <= 1 else [],
            strict_real_generation_allowed=strict_allowed,
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=next_actions,
        )

    def _approved_assets(self, product_id: int) -> list[models.ProductAsset]:
        return (
            self.db.query(models.ProductAsset)
            .filter(models.ProductAsset.product_id == product_id)
            .filter(models.ProductAsset.review_status == "approved")
            .order_by(models.ProductAsset.is_primary_reference.desc(), models.ProductAsset.id)
            .all()
        )

    @staticmethod
    def _missing_reference_types(assets: list[models.ProductAsset]) -> list[str]:
        asset_types = {asset.asset_type for asset in assets}
        missing = []
        if not asset_types.intersection(PACKSHOT_TYPES):
            missing.append("front_packshot")
        if not asset_types.intersection(LABEL_TYPES):
            missing.append("label_closeup")
        if not asset_types.intersection(CONTEXT_TYPES):
            missing.append("context_or_scale")
        return missing
