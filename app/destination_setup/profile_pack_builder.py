from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_setup.account_checklist_builder import OFFICIAL_API_PLATFORMS
from app.destination_setup.errors import DestinationSetupDataError
from app.destination_setup.types import DestinationProfilePackResult


class DestinationProfilePackBuilder:
    def __init__(self, db: Session):
        self.db = db

    def generate_for_campaign(self, campaign_id: int) -> list[DestinationProfilePackResult]:
        campaign = self._campaign(campaign_id)
        requirements = self.db.scalars(
            select(models.DestinationSetupRequirement)
            .where(models.DestinationSetupRequirement.campaign_id == campaign.id)
            .order_by(models.DestinationSetupRequirement.id)
        ).all()
        if not requirements:
            raise DestinationSetupDataError("Create destination setup requirements before profile packs.")
        results: list[DestinationProfilePackResult] = []
        for requirement in requirements:
            results.extend(self.generate_for_requirement(requirement.id))
        return results

    def generate_for_requirement(self, requirement_id: int) -> list[DestinationProfilePackResult]:
        requirement = self.db.get(models.DestinationSetupRequirement, requirement_id)
        if not requirement:
            raise DestinationSetupDataError(f"Destination setup requirement {requirement_id} not found.")
        campaign = self._campaign(requirement.campaign_id)
        products = self._products(campaign)
        if not products:
            raise DestinationSetupDataError("Campaign has no products for destination profile packs.")
        existing = self.db.scalars(
            select(models.DestinationProfilePack)
            .where(
                models.DestinationProfilePack.campaign_id == campaign.id,
                models.DestinationProfilePack.platform == requirement.platform,
            )
            .order_by(models.DestinationProfilePack.id)
        ).all()
        target_count = max(0, requirement.required_count)
        for index in range(len(existing) + 1, target_count + 1):
            product = products[(index - 1) % len(products)]
            pack = self._build_pack(campaign, product, requirement.platform, index)
            self.db.add(pack)
            existing.append(pack)
        self.db.commit()
        for pack in existing:
            self.db.refresh(pack)
        return [self._result(pack) for pack in existing]

    def get(self, profile_pack_id: int) -> DestinationProfilePackResult:
        pack = self.db.get(models.DestinationProfilePack, profile_pack_id)
        if not pack:
            raise DestinationSetupDataError(f"Destination profile pack {profile_pack_id} not found.")
        return self._result(pack)

    def list(self, campaign_id: int | None = None) -> list[DestinationProfilePackResult]:
        query = select(models.DestinationProfilePack).order_by(models.DestinationProfilePack.id.desc())
        if campaign_id is not None:
            query = query.where(models.DestinationProfilePack.campaign_id == campaign_id)
        packs = self.db.scalars(query).all()
        return [self._result(pack) for pack in packs]

    def _build_pack(self, campaign: models.Campaign, product: models.Product, platform: str, index: int) -> models.DestinationProfilePack:
        focus = self._focus(product)
        handle = self._handle(campaign.brand, focus, index)
        title = product.title or product.sku
        sku_focus = [{"product_id": product.id, "sku": product.sku, "title": title, "priority": index}]
        return models.DestinationProfilePack(
            campaign_id=campaign.id,
            platform=platform,
            sku_focus_json=sku_focus,
            theme=f"{focus.title()} product education",
            suggested_name=f"{campaign.brand} {focus.title()} #{index}",
            suggested_handle=handle,
            bio_text=(
                f"{title}: product-first videos, source-backed usage context, "
                "human review before publishing."
            ),
            avatar_prompt=(
                f"Clean square avatar for {campaign.brand} {focus}, product-safe, readable at small size, "
                "no medical promises."
            ),
            avatar_asset_path=self._avatar_asset(product),
            content_pillars_json=[
                "product_reference_first",
                "routine_context",
                "objection_handling",
                "safe_claims_only",
                "manual_review_required",
            ],
            first_posts_json=self._first_posts(product, platform),
            posting_rules_json=self._posting_rules(platform),
            status="draft",
        )

    def _products(self, campaign: models.Campaign) -> list[models.Product]:
        ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        if not ids:
            return []
        return self.db.scalars(select(models.Product).where(models.Product.id.in_(ids)).order_by(models.Product.id)).all()

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationSetupDataError(f"Campaign {campaign_id} not found.")
        return campaign

    @staticmethod
    def _first_posts(product: models.Product, platform: str) -> list[dict[str, Any]]:
        angles = [
            ("hook", "Open with the product in frame and one buyer problem."),
            ("texture", "Show texture, package details, and safe sensory context."),
            ("usage", "Explain where this SKU fits in a routine."),
            ("expectations", "Set realistic timing and consistency expectations."),
            ("safety", "Show restrictions, patch test, or careful-use note."),
            ("comparison", "Compare use case against a generic alternative without attacking brands."),
            ("faq", "Answer one common product-card question."),
            ("bundle", "Pair with approved complementary care or SPF context."),
            ("cta", "Use approved CTA and official product link."),
        ]
        return [
            {
                "slot": index,
                "sku": product.sku,
                "platform": platform,
                "angle": angle,
                "title": f"{product.title}: {description}",
                "status": "planned",
            }
            for index, (angle, description) in enumerate(angles, start=1)
        ]

    @staticmethod
    def _posting_rules(platform: str) -> list[dict[str, Any]]:
        rules = [
            {"rule": "publish_only_approved_video", "required": True},
            {"rule": "capture_final_url_after_manual_upload", "required": True},
            {"rule": "no_medical_or_guaranteed_claims", "required": True},
            {"rule": "respect_daily_and_weekly_limits", "required": True},
        ]
        if platform in OFFICIAL_API_PLATFORMS:
            rules.append({"rule": "official_api_first_when_token_valid", "required": True})
        else:
            rules.append({"rule": "manual_assisted_upload", "required": True})
        return rules

    @staticmethod
    def _avatar_asset(product: models.Product) -> str | None:
        return (product.images_json or [None])[0]

    @staticmethod
    def _focus(product: models.Product) -> str:
        value = product.category or product.title or product.sku
        words = [word for word in re.split(r"\W+", value.lower()) if len(word) > 2]
        return " ".join(words[:2]) or "launch"

    @staticmethod
    def _handle(brand: str, focus: str, index: int) -> str:
        base = re.sub(r"[^\w]+", "_", f"{brand}_{focus}_{index}".lower()).strip("_")
        return f"@{base[:29]}"

    @staticmethod
    def _result(pack: models.DestinationProfilePack) -> DestinationProfilePackResult:
        return DestinationProfilePackResult(
            id=pack.id,
            campaign_id=pack.campaign_id,
            platform=pack.platform,
            sku_focus=pack.sku_focus_json or [],
            theme=pack.theme,
            suggested_name=pack.suggested_name,
            suggested_handle=pack.suggested_handle,
            bio_text=pack.bio_text,
            avatar_prompt=pack.avatar_prompt,
            avatar_asset_path=pack.avatar_asset_path,
            content_pillars=pack.content_pillars_json or [],
            first_posts=pack.first_posts_json or [],
            posting_rules=pack.posting_rules_json or [],
            status=pack.status,
            created_at=pack.created_at,
            updated_at=pack.updated_at,
        )
