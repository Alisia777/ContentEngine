from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.product_asset_contract.asset_classifier import normalize_key
from app.product_asset_contract.errors import ProductAssetContractError
from app.product_asset_contract.types import ProductAssetRequirementOutput, ProductAssetTierOutput


TIER_RANK = {f"tier_{index}": index for index in range(5)}


@dataclass(frozen=True)
class ProductProfileRequirements:
    tier_1: tuple[tuple[str, ...], ...]
    tier_2: tuple[tuple[str, ...], ...]
    tier_3: tuple[tuple[str, ...], ...]
    tier_4: tuple[tuple[str, ...], ...]

    def groups(self, tier: str) -> tuple[tuple[str, ...], ...]:
        rank = TIER_RANK[tier]
        groups: list[tuple[str, ...]] = []
        for index in range(1, rank + 1):
            groups.extend(getattr(self, f"tier_{index}"))
        return tuple(groups)


COMMON_TIER_1 = (("front_packshot",),)
COMMON_TIER_2 = (
    ("angled_wrapper", "angled_product", "back_view"),
    ("wrapper_in_hand", "wrapper_on_table", "product_in_hand", "product_on_surface", "scale_context"),
)

PROFILE_REQUIREMENTS = {
    "food_snack": ProductProfileRequirements(
        tier_1=COMMON_TIER_1,
        tier_2=COMMON_TIER_2,
        tier_3=(("whole_unwrapped_product",), ("cutaway_product",), ("wrapper_plus_product",)),
        tier_4=(("bitten_product",), ("product_in_hand",), ("product_near_mouth",), ("semi_open_wrapper",), ("opening_video_reference", "use_video_reference")),
    ),
    "cosmetic": ProductProfileRequirements(
        tier_1=COMMON_TIER_1,
        tier_2=COMMON_TIER_2,
        tier_3=(("dispenser_closeup", "detail_closeup"), ("texture_swatch", "texture_macro"), ("application_context", "application_area")),
        tier_4=(("product_in_hand",), ("application_demo",), ("application_area",), ("use_video_reference",)),
    ),
    "apparel": ProductProfileRequirements(
        tier_1=(("front_packshot", "front_view"),),
        tier_2=(("back_view", "angled_product"), ("detail_closeup",), ("on_body", "scale_context")),
        tier_3=(("on_body",), ("detail_closeup",), ("application_context", "lifestyle_reference")),
        tier_4=(("movement_reference",), ("use_video_reference",), ("on_body",)),
    ),
    "household": ProductProfileRequirements(
        tier_1=COMMON_TIER_1,
        tier_2=COMMON_TIER_2,
        tier_3=(("detail_closeup", "texture_macro"), ("application_context",), ("result_context", "product_on_surface")),
        tier_4=(("product_in_hand",), ("application_demo",), ("use_video_reference",)),
    ),
    "general": ProductProfileRequirements(
        tier_1=COMMON_TIER_1,
        tier_2=COMMON_TIER_2,
        tier_3=(("detail_closeup", "texture_macro"), ("application_context",), ("result_context", "product_on_surface")),
        tier_4=(("product_in_hand",), ("application_demo",), ("use_video_reference",)),
    ),
}

PROFILE_INTERACTION_MODES = {
    "food_snack": "taste",
    "cosmetic": "apply",
    "apparel": "try_on",
    "household": "demonstrate",
    "general": "use_case",
}

PURPOSE_TIERS = {
    "strategy": "tier_0",
    "end_card": "tier_1",
    "packshot_overlay": "tier_1",
    "marketplace_card": "tier_1",
    "identity_reveal": "tier_2",
    "wrapper_reveal": "tier_2",
    "final_ad": "tier_2",
    "publishing_candidate": "tier_2",
    "unwrapped_insert": "tier_3",
    "cutaway_proof": "tier_3",
    "texture_proof": "tier_3",
    "product_demo": "tier_3",
    "bite_scene": "tier_4",
    "opening_scene": "tier_4",
    "near_mouth": "tier_4",
    "eating_ugc": "tier_4",
    "application_demo": "tier_4",
    "try_on_demo": "tier_4",
    "operation_demo": "tier_4",
    "taste_demo": "tier_4",
    "use_case_ugc": "tier_4",
}

PURPOSE_PROFILE_COMPATIBILITY = {
    "bite_scene": {"food_snack"},
    "opening_scene": {"food_snack"},
    "near_mouth": {"food_snack"},
    "eating_ugc": {"food_snack"},
    "taste_demo": {"food_snack"},
    "application_demo": {"cosmetic"},
    "try_on_demo": {"apparel"},
    "operation_demo": {"household", "general"},
}


def product_profile(product: models.Product) -> str:
    attributes = product.attributes_json or {}
    explicit = str(
        attributes.get("product_profile")
        or attributes.get("asset_profile")
        or attributes.get("category_profile")
        or ""
    ).strip().lower()
    if explicit in PROFILE_REQUIREMENTS:
        return explicit
    text = " ".join(str(value or "") for value in [product.category, product.title, product.description]).lower()
    if any(
        token in text
        for token in [
            "bombbar",
            "bomb bar",
            "snack",
            "food",
            "nutrition",
            "protein bar",
            "energy bar",
            "drink",
            "beverage",
            "cookie",
            "dessert",
            "ice cream",
            "батон",
            "еда",
            "напит",
            "десерт",
            "печенье",
            "шоколад",
        ]
    ):
        return "food_snack"
    if any(token in text for token in ["cosmetic", "skincare", "serum", "cream", "beauty", "shampoo", "космет", "сыворот", "крем", "уход"]):
        return "cosmetic"
    if any(token in text for token in ["apparel", "clothing", "dress", "shirt", "fashion", "одеж", "плать", "футбол"]):
        return "apparel"
    if any(token in text for token in ["household", "appliance", "cleaning", "home", "быт", "уборк", "дом"]):
        return "household"
    return "general"


def product_variant_key(product: models.Product) -> str | None:
    attributes = product.attributes_json or {}
    explicit = attributes.get("variant_key")
    if explicit:
        return normalize_key(str(explicit))
    for key in ["flavor", "taste", "colour", "color", "model_variant"]:
        if attributes.get(key):
            return normalize_key(str(attributes[key]))
    return None


class ReferenceRequirementService:
    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, tier: ProductAssetTierOutput, *, purpose: str = "final_ad") -> models.ProductAssetRequirement:
        required_tier = PURPOSE_TIERS.get(purpose)
        if not required_tier:
            raise ProductAssetContractError(f"Unsupported product asset purpose: {purpose}")
        profile = PROFILE_REQUIREMENTS[tier.product_profile]
        groups = profile.groups(required_tier)
        available = {item.contract_type for item in tier.classified_assets if item.eligible}
        missing_groups = [group for group in groups if not available.intersection(group)]
        required = ["|".join(group) for group in groups]
        missing = ["|".join(group) for group in missing_groups]
        compatible_profiles = PURPOSE_PROFILE_COMPATIBILITY.get(purpose)
        profile_incompatible = bool(compatible_profiles and tier.product_profile not in compatible_profiles)
        ready = TIER_RANK[tier.current_tier] >= TIER_RANK[required_tier] and not missing and not profile_incompatible
        status = "ready" if ready else "blocked" if profile_incompatible else "needs_assets"
        record = models.ProductAssetRequirement(
            product_id=tier.product_id,
            sku=tier.sku,
            variant_key=tier.variant_key,
            product_profile=tier.product_profile,
            required_tier=required_tier,
            purpose=purpose,
            required_asset_types_json=required,
            missing_asset_types_json=missing,
            status=status,
            requirement_json={
                "current_tier": tier.current_tier,
                "end_card_required": purpose in {"final_ad", "publishing_candidate", "end_card"},
                "human_review_required": True,
                "profile_incompatible": profile_incompatible,
                "variant_key": tier.variant_key,
                "interaction_mode": PROFILE_INTERACTION_MODES[tier.product_profile],
            },
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    @staticmethod
    def output(record: models.ProductAssetRequirement, *, permission: dict | None = None) -> ProductAssetRequirementOutput:
        facts = record.requirement_json or {}
        return ProductAssetRequirementOutput(
            id=record.id,
            product_id=record.product_id,
            sku=record.sku,
            variant_key=record.variant_key,
            product_profile=record.product_profile,
            required_tier=record.required_tier,
            purpose=record.purpose,
            required_asset_types=record.required_asset_types_json or [],
            missing_asset_types=record.missing_asset_types_json or [],
            status=record.status,
            current_tier=facts.get("current_tier", "tier_0"),
            end_card_required=bool(facts.get("end_card_required")),
            human_review_required=bool(facts.get("human_review_required", True)),
            permission=permission or {},
        )
