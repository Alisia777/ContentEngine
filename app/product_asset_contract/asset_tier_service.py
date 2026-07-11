from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.product_asset_contract.asset_classifier import ProductAssetClassifier, normalize_key
from app.product_asset_contract.errors import ProductAssetContractError
from app.product_asset_contract.reference_requirement_service import PROFILE_REQUIREMENTS, TIER_RANK, product_profile, product_variant_key
from app.product_asset_contract.scene_permission_service import ScenePermissionService
from app.product_asset_contract.types import AssetClassification, ProductAssetTierOutput, ScenePermissionOutput


WRAPPER_TYPES = {"front_packshot", "angled_wrapper", "label_closeup", "wrapper_in_hand", "wrapper_on_table", "semi_open_wrapper"}
EDIBLE_TYPES = {"whole_unwrapped_product", "cutaway_product", "bitten_product", "product_near_mouth", "texture_macro", "wrapper_plus_product"}


class ProductAssetTierService:
    def __init__(self, db: Session):
        self.db = db
        self.classifier = ProductAssetClassifier()
        self.permission_service = ScenePermissionService()

    def evaluate(
        self,
        product_id: int,
        *,
        label_accuracy_required: bool = True,
        publishing_candidate: bool = True,
    ) -> models.ProductAssetTierSnapshot:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise ProductAssetContractError(f"Product {product_id} not found.")
        profile = product_profile(product)
        declared_variant_key = product_variant_key(product)
        assets = list(
            self.db.scalars(
                select(models.ProductAsset)
                .where(models.ProductAsset.product_id == product_id)
                .where(models.ProductAsset.review_status == "approved")
                .order_by(models.ProductAsset.id)
            )
        )
        asset_variant_keys = {
            normalize_key((asset.metadata_json or {}).get("variant_key") or (asset.metadata_json or {}).get("flavor") or (asset.metadata_json or {}).get("model_variant"))
            for asset in assets
        }
        asset_variant_keys.discard(None)
        variant_conflict = not declared_variant_key and len(asset_variant_keys) > 1
        primary_variant = next(
            (
                normalize_key((asset.metadata_json or {}).get("variant_key") or (asset.metadata_json or {}).get("flavor") or (asset.metadata_json or {}).get("model_variant"))
                for asset in assets
                if asset.is_primary_reference
            ),
            None,
        )
        variant_key = declared_variant_key or primary_variant or (next(iter(asset_variant_keys)) if len(asset_variant_keys) == 1 else None)
        classified = [self.classifier.classify(asset, expected_variant_key=variant_key) for asset in assets]
        if variant_conflict and not variant_key:
            for item in classified:
                if item.family not in {"style", "lifestyle"}:
                    item.eligible = False
                    item.variant_status = "conflict"
                    item.evidence.append("multiple_variant_keys_without_product_or_primary_variant")
        eligible_types = {item.contract_type for item in classified if item.eligible}
        current_tier = self._current_tier(profile, eligible_types)
        next_tier = f"tier_{min(4, TIER_RANK[current_tier] + 1)}"
        missing = self.missing_for_tier(profile, next_tier, eligible_types) if current_tier != "tier_4" else []
        mismatch_ids = [item.asset_id for item in classified if item.variant_status in {"mismatch", "unverified", "conflict"} and item.family not in {"style", "lifestyle"}]
        permission = self.permission_service.evaluate(
            product_profile=profile,
            current_tier=current_tier,
            classified_assets=classified,
            label_accuracy_required=label_accuracy_required,
            publishing_candidate=publishing_candidate,
        )
        blockers = []
        if current_tier == "tier_0":
            blockers.append("product_asset_contract:no_approved_front_packshot")
        if current_tier == "tier_1":
            blockers.append("product_asset_contract:one_photo_generation_blocked")
        if mismatch_ids:
            blockers.append("product_asset_contract:variant_identity_unverified_or_mismatched")
        if variant_conflict:
            blockers.append("product_asset_contract:multiple_variants_attached_to_one_product")
        snapshot = models.ProductAssetTierSnapshot(
            product_id=product.id,
            sku=product.sku,
            variant_key=variant_key,
            product_profile=profile,
            current_tier=current_tier,
            wrapper_refs_count=sum(1 for item in classified if item.eligible and item.contract_type in WRAPPER_TYPES),
            edible_refs_count=sum(1 for item in classified if item.eligible and item.contract_type in EDIBLE_TYPES),
            style_refs_count=sum(1 for item in classified if item.eligible and item.family == "style"),
            lifestyle_refs_count=sum(1 for item in classified if item.eligible and item.family == "lifestyle"),
            identity_refs_count=sum(1 for item in classified if item.eligible and item.family == "identity"),
            use_case_refs_count=sum(1 for item in classified if item.eligible and item.family in {"use_case", "proof", "interaction"}),
            classified_assets_json=[item.model_dump(mode="json") for item in classified],
            variant_mismatch_asset_ids_json=mismatch_ids,
            missing_assets_json=missing,
            allowed_scenes_json=permission.allowed_scenes,
            blocked_scenes_json=permission.blocked_scenes,
            permissions_json=permission.model_dump(mode="json"),
            blockers_json=blockers,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def latest(self, product_id: int) -> models.ProductAssetTierSnapshot | None:
        return self.db.scalar(
            select(models.ProductAssetTierSnapshot)
            .where(models.ProductAssetTierSnapshot.product_id == product_id)
            .order_by(models.ProductAssetTierSnapshot.id.desc())
        )

    @staticmethod
    def output(snapshot: models.ProductAssetTierSnapshot) -> ProductAssetTierOutput:
        return ProductAssetTierOutput(
            id=snapshot.id,
            product_id=snapshot.product_id,
            sku=snapshot.sku,
            variant_key=snapshot.variant_key,
            product_profile=snapshot.product_profile,
            current_tier=snapshot.current_tier,
            wrapper_refs_count=snapshot.wrapper_refs_count,
            edible_refs_count=snapshot.edible_refs_count,
            style_refs_count=snapshot.style_refs_count,
            lifestyle_refs_count=snapshot.lifestyle_refs_count,
            identity_refs_count=snapshot.identity_refs_count,
            use_case_refs_count=snapshot.use_case_refs_count,
            classified_assets=[AssetClassification.model_validate(item) for item in (snapshot.classified_assets_json or [])],
            variant_mismatch_asset_ids=snapshot.variant_mismatch_asset_ids_json or [],
            missing_assets=snapshot.missing_assets_json or [],
            allowed_scenes=snapshot.allowed_scenes_json or [],
            blocked_scenes=snapshot.blocked_scenes_json or [],
            permissions=ScenePermissionOutput.model_validate(snapshot.permissions_json or {}),
            blockers=snapshot.blockers_json or [],
        )

    @staticmethod
    def _current_tier(profile: str, available: set[str]) -> str:
        requirements = PROFILE_REQUIREMENTS[profile]
        current = "tier_0"
        for tier in ["tier_1", "tier_2", "tier_3", "tier_4"]:
            if ProductAssetTierService._groups_ready(requirements.groups(tier), available):
                current = tier
            else:
                break
        return current

    @staticmethod
    def missing_for_tier(profile: str, tier: str, available: set[str]) -> list[str]:
        groups = PROFILE_REQUIREMENTS[profile].groups(tier)
        return ["|".join(group) for group in groups if not available.intersection(group)]

    @staticmethod
    def _groups_ready(groups: tuple[tuple[str, ...], ...], available: set[str]) -> bool:
        return all(available.intersection(group) for group in groups)
