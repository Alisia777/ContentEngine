from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.bombar_launch.errors import BombarLaunchDataError
from app.bombar_launch.profile_pack_builder import ProfilePackBuilder
from app.bombar_launch.types import DestinationSetupPackResult


PLATFORMS = ["Instagram Reels", "TikTok", "VK Clips", "YouTube Shorts", "Telegram"]


class DestinationSetupPlanner:
    def __init__(self, db: Session):
        self.db = db
        self.profile_builder = ProfilePackBuilder()

    def generate(self, campaign_id: int) -> list[DestinationSetupPackResult]:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise BombarLaunchDataError(f"Campaign {campaign_id} not found.")
        products = self._products(campaign)
        if not products:
            raise BombarLaunchDataError("Campaign has no products.")
        existing = self.db.scalars(
            select(models.DestinationSetupPack).where(models.DestinationSetupPack.campaign_id == campaign.id)
        ).all()
        if existing:
            for pack in existing:
                self._ensure_publishing_destination(campaign, pack)
            self.db.commit()
            return [self._result(pack) for pack in existing]

        packs: list[models.DestinationSetupPack] = []
        for index in range(campaign.target_destination_count):
            product = products[index % len(products)]
            platform = PLATFORMS[index % len(PLATFORMS)]
            profile = self.profile_builder.build(product, platform=platform, index=index + 1)
            pack = models.DestinationSetupPack(
                campaign_id=campaign.id,
                product_id=product.id,
                sku=product.sku,
                destination_type="owned_media",
                platform=platform,
                suggested_name=profile["account_name"],
                suggested_handle=profile["handle_options"][0],
                bio_text=profile["bio_variants"][0],
                avatar_asset_path=self._avatar_asset(product),
                content_pillars_json=profile["content_pillars"],
                first_posts_json=profile["first_posts"],
                setup_checklist_json=profile["setup_checklist"],
                status="needs_manual_setup",
            )
            self.db.add(pack)
            self.db.flush()
            self._ensure_publishing_destination(campaign, pack)
            packs.append(pack)
        campaign.strategy_json = {
            **(campaign.strategy_json or {}),
            "adapter": "bombar_launch",
            "destination_setup": {
                "total_packs": campaign.target_destination_count,
                "modes": ["official_api_when_token_valid", "manual_assisted_upload"],
                "external_account_setup": False,
                "publish_requires_approval": True,
                "generic_destination_registry": True,
            },
        }
        self.db.commit()
        return [self._result(pack) for pack in packs]

    def _ensure_publishing_destination(self, campaign: models.Campaign, pack: models.DestinationSetupPack) -> models.PublishingDestination:
        destination = self.db.scalar(
            select(models.PublishingDestination).where(
                models.PublishingDestination.brand == campaign.brand,
                models.PublishingDestination.platform == pack.platform,
                models.PublishingDestination.handle == pack.suggested_handle,
            )
        )
        if destination:
            return destination
        destination = models.PublishingDestination(
            brand=campaign.brand,
            platform=pack.platform,
            name=pack.suggested_name,
            handle=pack.suggested_handle,
            status="draft",
            posting_mode="official_api_or_manual",
            auth_status="token_required",
            allowed_formats_json=["vertical_video"],
            daily_limit=1,
            weekly_limit=3,
            notes=(
                "Created from Bombar destination setup pack. Account must be owned/verified; "
                "no external account registration is performed by ContentEngine."
            ),
        )
        self.db.add(destination)
        self.db.flush()
        return destination

    def _products(self, campaign: models.Campaign) -> list[models.Product]:
        ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        if not ids:
            return []
        return self.db.scalars(select(models.Product).where(models.Product.id.in_(ids)).order_by(models.Product.id)).all()

    @staticmethod
    def _avatar_asset(product: models.Product) -> str | None:
        return (product.images_json or [None])[0]

    @staticmethod
    def _result(pack: models.DestinationSetupPack) -> DestinationSetupPackResult:
        return DestinationSetupPackResult(
            pack_id=pack.id,
            campaign_id=pack.campaign_id,
            sku=pack.sku,
            destination_type=pack.destination_type,
            platform=pack.platform,
            suggested_name=pack.suggested_name,
            suggested_handle=pack.suggested_handle,
            status=pack.status,
            content_pillars=pack.content_pillars_json or [],
            first_posts=pack.first_posts_json or [],
            setup_checklist=pack.setup_checklist_json or [],
        )
