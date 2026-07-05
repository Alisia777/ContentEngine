from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_autopilot.target_allocator import TargetAllocator
from app.campaign_autopilot.types import CampaignResult


class CampaignService:
    def __init__(self, db: Session):
        self.db = db

    def create_campaign(
        self,
        *,
        name: str,
        brand: str,
        import_id: int | None = None,
        product_ids: list[int] | None = None,
        target_video_count: int = 350,
        target_destination_count: int = 120,
        source_type: str | None = None,
    ) -> CampaignResult:
        if import_id is None and not product_ids:
            raise CampaignAutopilotDataError("Campaign requires import_id or product_ids.")
        self._ensure_brand_context(brand)
        products = self._products_from_import(import_id, brand) if import_id is not None else self._products_by_ids(product_ids or [])
        if not products:
            raise CampaignAutopilotDataError("Campaign has no valid products.")
        campaign = models.Campaign(
            name=name,
            brand=brand,
            status="draft",
            source_type=source_type or ("csv" if import_id is not None else "manual_selection"),
            product_ids_json=[product.id for product in products],
            target_video_count=target_video_count,
            target_destination_count=target_destination_count,
            strategy_json={
                "source_import_id": import_id,
                "default_videos_per_sku": "7-9",
                "safe_execution": True,
                "paid_provider_calls_in_prepare": False,
                "publish_policy": "approved_packages_only",
            },
            summary_json={},
        )
        self.db.add(campaign)
        self.db.flush()
        for product in products:
            self.db.add(
                models.CampaignProduct(
                    campaign_id=campaign.id,
                    product_id=product.id,
                    sku=product.sku,
                    status="planned",
                    blockers_json=[],
                    next_actions_json=[{"action": "allocate_targets", "reason": "Campaign created."}],
                )
            )
        self.db.commit()
        TargetAllocator(self.db).allocate(campaign.id)
        self.db.refresh(campaign)
        return self._result(campaign)

    def list_campaigns(self) -> list[CampaignResult]:
        campaigns = self.db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
        return [self._result(campaign) for campaign in campaigns]

    def get(self, campaign_id: int) -> CampaignResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignAutopilotDataError(f"Campaign {campaign_id} not found.")
        return self._result(campaign)

    def _products_from_import(self, import_id: int, brand: str) -> list[models.Product]:
        matrix_import = self.db.get(models.ProductMatrixImport, import_id)
        if not matrix_import:
            raise CampaignAutopilotDataError(f"ProductMatrixImport {import_id} not found.")
        rows = self.db.scalars(
            select(models.ProductMatrixRow).where(models.ProductMatrixRow.import_id == import_id).order_by(models.ProductMatrixRow.id)
        ).all()
        products = [self._create_or_update_product(row, brand) for row in rows]
        self.db.commit()
        return products

    def _products_by_ids(self, product_ids: list[int]) -> list[models.Product]:
        if not product_ids:
            return []
        return self.db.scalars(select(models.Product).where(models.Product.id.in_(product_ids)).order_by(models.Product.id)).all()

    def _create_or_update_product(self, row: models.ProductMatrixRow, brand: str) -> models.Product:
        product = self.db.scalar(select(models.Product).where(models.Product.sku == row.sku))
        attrs = {
            "product_matrix_row_id": row.id,
            "price": row.price,
            "stock_qty": row.stock_qty,
            "matrix_priority": row.priority,
            "matrix_warnings": row.warnings_json or [],
        }
        benefits = [
            f"Product matrix lists {row.product_name} in {row.category or 'catalog'}.",
            "Use source-backed product facts and approved references only.",
        ]
        if product:
            product.brand = brand
            product.marketplace = "Product Matrix"
            product.title = row.product_name
            product.category = row.category
            product.product_url = row.product_url
            product.images_json = row.photo_urls_json or []
            product.attributes_json = {**(product.attributes_json or {}), **attrs}
            product.benefits_json = benefits
        else:
            product = models.Product(
                sku=row.sku,
                brand=brand,
                marketplace="Product Matrix",
                title=row.product_name,
                description=f"Campaign product card for {row.product_name}.",
                category=row.category,
                attributes_json=attrs,
                benefits_json=benefits,
                images_json=row.photo_urls_json or [],
                reviews_json=[],
                restrictions_json=["medical treatment", "guaranteed result"],
                product_url=row.product_url,
            )
            self.db.add(product)
        self.db.flush()
        self._ensure_seed_signals(product, row)
        return product

    def _ensure_seed_signals(self, product: models.Product, row: models.ProductMatrixRow) -> None:
        today = date.today()
        if not self.db.scalar(select(models.ProductMetricSnapshot).where(models.ProductMetricSnapshot.sku == product.sku)):
            stock_qty = row.stock_qty if row.stock_qty is not None else 0
            self.db.add(
                models.ProductMetricSnapshot(
                    sku=product.sku,
                    marketplace="Product Matrix",
                    period_start=today,
                    period_end=today,
                    views=1000,
                    clicks=25,
                    orders=2,
                    revenue=(row.price or 0) * 2,
                    conversion_rate=0.08,
                    ctr=0.025,
                    avg_price=row.price,
                    stock_qty=stock_qty,
                    days_of_stock=max(1, min(30, stock_qty // 3)) if stock_qty else None,
                    returns_rate=0.02,
                    rating=4.5,
                    reviews_count=1,
                    raw_json={"source": "product_matrix", "row_id": row.id},
                )
            )
        if not self.db.scalar(select(models.CreativePerformanceSnapshot).where(models.CreativePerformanceSnapshot.sku == product.sku)):
            self.db.add(
                models.CreativePerformanceSnapshot(
                    sku=product.sku,
                    platform="Instagram Reels",
                    creative_angle="campaign_launch",
                    hook_text=f"Show {product.title} clearly in the first frame",
                    views=0,
                    clicks=0,
                    ctr=0.0,
                    orders=0,
                    retention_rate=0.4,
                    raw_json={"source": "campaign_autopilot_seed"},
                )
            )
        if not self.db.scalar(select(models.ProductReviewInsight).where(models.ProductReviewInsight.sku == product.sku)):
            self.db.add(
                models.ProductReviewInsight(
                    sku=product.sku,
                    marketplace="Product Matrix",
                    period_start=today,
                    period_end=today,
                    positive_themes_json=["clear product reference", "source-backed facts"],
                    negative_themes_json=["needs review before publishing"],
                    buyer_objections_json=["how does this fit my routine?"],
                    buyer_language_json=["show the product", "explain usage", "avoid overpromising"],
                    source_review_count=1,
                    raw_json={"source": "campaign_autopilot_seed"},
                )
            )
        if not self.db.scalar(select(models.MarketSignal).where(models.MarketSignal.sku == product.sku)):
            self.db.add(
                models.MarketSignal(
                    sku=product.sku,
                    marketplace="Product Matrix",
                    signal_type="launch_baseline",
                    signal_strength="low",
                    notes="Use source-backed launch education.",
                    raw_json={"source": "campaign_autopilot_seed"},
                )
            )
        self.db.flush()

    def _ensure_brand_context(self, brand: str) -> None:
        if not self.db.scalar(select(models.BrandGuide).where(models.BrandGuide.brand == brand)):
            self.db.add(
                models.BrandGuide(
                    brand=brand,
                    tone_of_voice="Clear, practical, and careful with claims.",
                    visual_style="Product-first vertical video with readable product details.",
                    forbidden_words_json=["cure", "heal", "guaranteed"],
                    forbidden_claims_json=["medical treatment", "guaranteed result"],
                    required_disclaimers_json=["AI-assisted creative requires human review."],
                    allowed_cta_json=["Open the product card", "Check the official product page"],
                )
            )
        if not self.db.scalar(select(models.CreativeTemplate).where(models.CreativeTemplate.name == "Campaign autopilot short video")):
            self.db.add(
                models.CreativeTemplate(
                    name="Campaign autopilot short video",
                    description="Product-first prompt-only campaign preparation template.",
                    format="short_video",
                    duration_seconds=15,
                    aspect_ratio="9:16",
                    structure_json=["hook", "product_reference", "usage_context", "cta"],
                    hook_formula="Show the product in the first frame and name the buyer context.",
                    cta="Open the product card",
                    platform_fit_json=["Instagram Reels", "TikTok", "VK Clips", "YouTube Shorts"],
                )
            )
        self.db.flush()

    @staticmethod
    def _result(campaign: models.Campaign) -> CampaignResult:
        return CampaignResult(
            campaign_id=campaign.id,
            name=campaign.name,
            brand=campaign.brand,
            status=campaign.status,
            source_type=campaign.source_type,
            product_ids=campaign.product_ids_json or [],
            target_video_count=campaign.target_video_count,
            target_destination_count=campaign.target_destination_count,
            strategy=campaign.strategy_json or {},
        )
