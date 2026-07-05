from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.bombar_launch.errors import BombarLaunchDataError
from app.bombar_launch.types import BombarCampaignResult
from app.campaign_autopilot.campaign_runner import CampaignRunner
from app.campaign_autopilot.campaign_service import CampaignService
from app.campaign_autopilot.errors import CampaignAutopilotDataError


class LaunchPlanner:
    def __init__(self, db: Session):
        self.db = db

    def create_campaign(
        self,
        import_id: int,
        *,
        name: str | None = None,
        brand: str = "Bombar",
        target_video_count: int = 350,
        target_destination_count: int = 120,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> BombarCampaignResult:
        matrix_import = self.db.get(models.ProductMatrixImport, import_id)
        if not matrix_import:
            raise BombarLaunchDataError(f"ProductMatrixImport {import_id} not found.")
        rows = self.db.scalars(
            select(models.ProductMatrixRow)
            .where(models.ProductMatrixRow.import_id == import_id)
            .order_by(models.ProductMatrixRow.id)
        ).all()
        if not rows:
            raise BombarLaunchDataError("Bombar import has no valid product rows.")
        try:
            result = CampaignService(self.db).create_campaign(
                name=name or f"Bombar launch #{matrix_import.id}",
                brand=brand,
                import_id=import_id,
                target_video_count=target_video_count,
                target_destination_count=target_destination_count,
                source_type="bombar_matrix",
            )
        except CampaignAutopilotDataError as exc:
            raise BombarLaunchDataError(str(exc)) from exc

        campaign = self.db.get(models.Campaign, result.campaign_id)
        if not campaign:
            raise BombarLaunchDataError(f"Campaign {result.campaign_id} not found after creation.")
        campaign.start_date = start_date
        campaign.end_date = end_date
        campaign.strategy_json = {
            **(campaign.strategy_json or {}),
            "adapter": "bombar_launch",
            "source_import_id": matrix_import.id,
            "source_file": matrix_import.source_file,
            "sku_count": len(rows),
            "target_range": "300-350 videos",
            "publish_policy": "approved_video_only",
            "official_api_first": True,
            "manual_assisted_fallback": True,
            "external_account_setup": False,
        }
        self._enrich_products(rows)
        self.db.commit()
        self.db.refresh(campaign)
        return self._campaign_result(campaign)

    def prepare_content(
        self,
        campaign_id: int,
        *,
        platform: str = "Instagram Reels",
        duration_seconds: int = 15,
        variant_count: int | None = None,
    ) -> dict[str, Any]:
        try:
            result = CampaignRunner(self.db).prepare_campaign(campaign_id)
        except CampaignAutopilotDataError as exc:
            raise BombarLaunchDataError(str(exc)) from exc
        campaign = self.db.get(models.Campaign, campaign_id)
        if campaign:
            campaign.strategy_json = {
                **(campaign.strategy_json or {}),
                "adapter": "bombar_launch",
                "last_bombar_prepare": {
                    "campaign_run_id": result.campaign_run_id,
                    "platform_requested": platform,
                    "duration_requested": duration_seconds,
                    "variant_count_requested": variant_count,
                    "delegated_to": "CampaignRunner.prepare_campaign",
                },
            }
            self.db.commit()
        return {
            "campaign_id": result.campaign_id,
            "campaign_run_id": result.campaign_run_id,
            "status": result.status,
            "prepared_count": result.total_content_runs,
            "prompt_ready": result.total_prompt_ready,
            "blocked": result.total_blocked,
            "blockers": result.blockers,
            "runs": result.products,
            "adapter": "bombar_launch",
            "delegated_to": "CampaignRunner",
        }

    def _enrich_products(self, rows: list[models.ProductMatrixRow]) -> None:
        for row in rows:
            product = self.db.scalar(select(models.Product).where(models.Product.sku == row.sku))
            if not product:
                continue
            raw = row.raw_json or {}
            product.marketplace = "Bombar"
            product.attributes_json = {
                **(product.attributes_json or {}),
                "bombar_adapter": True,
                "bombar_import_row_id": row.id,
                "bombar_margin": (raw.get("bombar") or {}).get("margin"),
                "matrix_status": row.status,
                "matrix_warnings": row.warnings_json or [],
            }
            if product.images_json:
                self._ensure_asset_kit(product)
        self.db.flush()

    def _ensure_asset_kit(self, product: models.Product) -> None:
        existing = self.db.scalar(
            select(models.ProductAssetKit)
            .where(models.ProductAssetKit.product_id == product.id)
            .order_by(models.ProductAssetKit.id.desc())
        )
        if existing:
            return
        kit = AssetKitBuilder(self.db).build_for_product(product.id)
        assets = self.db.scalars(
            select(models.ProductAsset).where(models.ProductAsset.asset_kit_id == kit.id).order_by(models.ProductAsset.id)
        ).all()
        for index, asset in enumerate(assets):
            asset.review_status = "approved"
            asset.is_primary_reference = index == 0
            asset.asset_role = "primary_reference" if index == 0 else "supporting_reference"
            asset.manual_label = "Bombar matrix reference"
        if assets:
            kit.primary_reference_asset_id = assets[0].id
        self.db.flush()

    @staticmethod
    def _campaign_result(campaign: models.Campaign) -> BombarCampaignResult:
        return BombarCampaignResult(
            campaign_id=campaign.id,
            linked_campaign_id=campaign.id,
            name=campaign.name,
            brand=campaign.brand,
            status=campaign.status,
            product_ids=campaign.product_ids_json or [],
            target_video_count=campaign.target_video_count,
            target_destination_count=campaign.target_destination_count,
        )
