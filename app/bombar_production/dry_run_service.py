from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.bombar_production.errors import BombarProductionDataError
from app.bombar_production.matrix_validator import BombarMatrixValidator
from app.bombar_production.report_exporter import BombarProductionReportExporter
from app.bombar_production.types import (
    BombarMatrixRowValidation,
    BombarMatrixValidationResult,
    BombarProductionDryRunResult,
    BombarSkuReadiness,
)
from app.factory_os import FactoryAcceptanceReportService, FactoryLaunchWorkflow
from app.factory_os.types import FactoryAcceptanceReport, FactoryLaunchResult


BLOCKING_CONTENT_PREFIXES = (
    "missing_reference",
    "approved_product_reference",
    "product_identity",
    "geometry",
)


class BombarProductionDryRunService:
    def __init__(self, db: Session, *, reports_dir: str | Path = "reports"):
        self.db = db
        self.reports_dir = Path(reports_dir)
        self.validator = BombarMatrixValidator()
        self.exporter = BombarProductionReportExporter()

    def run(
        self,
        matrix_path: str | Path,
        *,
        target_videos: int = 350,
        target_destinations: int = 120,
        campaign_name: str | None = None,
        reports_dir: str | Path | None = None,
    ) -> BombarProductionDryRunResult:
        validation = self.validator.validate_path(matrix_path)
        self._require_importable(validation)
        with TemporaryDirectory(prefix="bombar_dry_run_") as temp_dir:
            factory_csv = self.validator.write_factory_csv(validation, Path(temp_dir) / "bombar_factory_matrix.csv")
            launch = FactoryLaunchWorkflow(self.db).run_prompt_only_launch(
                factory_csv,
                campaign_name or "Bombar Production Dry Run",
                target_videos,
                target_destinations,
                brand="Bombar",
                performance_csv_path=None,
            )
            self._mark_campaign(launch, validation)
            report = self.build_report(launch.campaign_id, validation=validation, launch_result=launch)
        report_paths = self.exporter.export(report, reports_dir or self.reports_dir)
        report.report_paths = report_paths
        self._save_report_paths(report.campaign_id, report_paths)
        report.status = "production_dry_run_ready"
        return report

    def build_report(
        self,
        campaign_id: int,
        *,
        validation: BombarMatrixValidationResult | None = None,
        launch_result: FactoryLaunchResult | None = None,
    ) -> BombarProductionDryRunResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise BombarProductionDataError(f"Campaign {campaign_id} not found.")
        validation = validation or self._validation_from_campaign(campaign)
        factory_report = launch_result.acceptance_report if launch_result else FactoryAcceptanceReportService(self.db).build(campaign_id)
        import_id = launch_result.import_id if launch_result else self._source_import_id(campaign)
        readiness = self._sku_readiness(campaign, validation, import_id)
        blockers_by_sku = {row.sku: row.blockers for row in readiness if row.blockers}
        distribution_blockers = self._distribution_blockers(factory_report, campaign)
        next_actions = self._campaign_next_actions(readiness, factory_report, distribution_blockers)
        ready_sku_count = sum(1 for row in readiness if row.status in {"prompt_ready", "publishing_ready"})
        return BombarProductionDryRunResult(
            campaign_id=campaign.id,
            import_id=import_id,
            imported_sku_count=len(readiness),
            ready_sku_count=ready_sku_count,
            blocked_sku_count=len(readiness) - ready_sku_count,
            prompt_pack_count=sum(row.prompt_pack_count for row in readiness),
            missing_references_count=sum(1 for row in readiness if not row.has_reference),
            missing_photo_count=sum(1 for row in readiness if not row.has_photo),
            missing_price_count=sum(1 for row in readiness if not row.has_price),
            missing_stock_count=sum(1 for row in readiness if not row.has_stock),
            approved_package_count=sum(row.approved_package_count for row in readiness),
            distribution_blockers=distribution_blockers,
            next_actions=next_actions,
            report_paths=(campaign.strategy_json or {}).get("bombar_production_report_paths", {}),
            paid_calls_made=factory_report.paid_calls_made,
            safe_mode={
                "paid_provider_calls": False,
                "auto_publish": False,
                "external_account_registration": False,
                "approval_gates_bypassed": False,
            },
            blockers_by_sku=blockers_by_sku,
            sku_readiness=readiness,
            validation=validation,
            factory_steps=launch_result.steps if launch_result else [],
            factory_acceptance_report=factory_report,
        )

    def _require_importable(self, validation: BombarMatrixValidationResult) -> None:
        missing_headers = [error for error in validation.errors if error.startswith("missing_header:")]
        if missing_headers:
            raise BombarProductionDataError("Bombar matrix is missing required headers: " + ", ".join(missing_headers))
        if validation.valid_row_count == 0:
            raise BombarProductionDataError("Bombar matrix has no valid SKU rows to import.")

    def _mark_campaign(self, launch: FactoryLaunchResult, validation: BombarMatrixValidationResult) -> None:
        campaign = self.db.get(models.Campaign, launch.campaign_id)
        if not campaign:
            return
        campaign.source_type = "bombar_production_dry_run"
        campaign.strategy_json = {
            **(campaign.strategy_json or {}),
            "adapter": "bombar_production_dry_run",
            "source_matrix_path": validation.source_file,
            "source_import_id": launch.import_id,
            "bombar_production_validation": validation.model_dump(mode="json"),
            "paid_provider_calls_in_dry_run": False,
            "auto_publish_in_dry_run": False,
        }
        self.db.commit()

    def _save_report_paths(self, campaign_id: int, report_paths: dict[str, str]) -> None:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            return
        campaign.strategy_json = {
            **(campaign.strategy_json or {}),
            "bombar_production_report_paths": report_paths,
        }
        self.db.commit()

    def _validation_from_campaign(self, campaign: models.Campaign) -> BombarMatrixValidationResult | None:
        payload = (campaign.strategy_json or {}).get("bombar_production_validation")
        if not payload:
            return None
        return BombarMatrixValidationResult.model_validate(payload)

    def _source_import_id(self, campaign: models.Campaign) -> int | None:
        value = (campaign.strategy_json or {}).get("source_import_id")
        return int(value) if value else None

    def _sku_readiness(
        self,
        campaign: models.Campaign,
        validation: BombarMatrixValidationResult | None,
        import_id: int | None,
    ) -> list[BombarSkuReadiness]:
        campaign_products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id).order_by(models.CampaignProduct.id)
        ).all()
        product_ids = [item.product_id for item in campaign_products]
        products = {
            product.id: product
            for product in self.db.scalars(
                select(models.Product).where(models.Product.id.in_(product_ids) if product_ids else False)
            ).all()
        }
        rows_by_sku = self._matrix_rows_by_sku(import_id)
        validation_by_sku = {row.sku: row for row in (validation.rows if validation else []) if row.sku}
        content_runs = self._content_runs(campaign_products, product_ids)
        runs_by_product: dict[int, list[models.ContentRun]] = defaultdict(list)
        for run in content_runs:
            runs_by_product[run.product_id].append(run)
        packages = self._approved_packages(product_ids)
        packages_by_product: dict[int, list[models.PublishingPackage]] = defaultdict(list)
        for package in packages:
            packages_by_product[package.product_id].append(package)

        readiness = []
        for item in campaign_products:
            product = products.get(item.product_id)
            matrix_row = rows_by_sku.get(item.sku)
            validation_row = validation_by_sku.get(item.sku)
            runs = runs_by_product.get(item.product_id, [])
            has_photo = self._has_matrix_photo(matrix_row, validation_row, product)
            has_reference = self._has_reference(product)
            has_price = self._has_price(matrix_row, validation_row, product)
            has_stock = self._has_stock(matrix_row, validation_row, product)
            blockers = self._sku_blockers(item, runs, has_photo, has_reference, has_price, has_stock, validation_row)
            prompt_pack_count = len({run.prompt_pack_id for run in runs if run.prompt_pack_id})
            approved_package_count = len(packages_by_product.get(item.product_id, []))
            next_actions = self._sku_next_actions(blockers, prompt_pack_count, approved_package_count)
            readiness.append(
                BombarSkuReadiness(
                    sku=item.sku,
                    product_name=product.title if product else (matrix_row.product_name if matrix_row else None),
                    product_id=item.product_id,
                    status=self._sku_status(blockers, prompt_pack_count, approved_package_count),
                    has_photo=has_photo,
                    has_reference=has_reference,
                    has_price=has_price,
                    has_stock=has_stock,
                    content_run_count=len(runs),
                    prompt_pack_count=prompt_pack_count,
                    approved_package_count=approved_package_count,
                    blockers=blockers,
                    next_actions=next_actions,
                )
            )
        return readiness

    def _matrix_rows_by_sku(self, import_id: int | None) -> dict[str, models.ProductMatrixRow]:
        if not import_id:
            return {}
        rows = self.db.scalars(
            select(models.ProductMatrixRow).where(models.ProductMatrixRow.import_id == import_id).order_by(models.ProductMatrixRow.id)
        ).all()
        return {row.sku: row for row in rows}

    def _content_runs(self, campaign_products: list[models.CampaignProduct], product_ids: list[int]) -> list[models.ContentRun]:
        run_ids = {int(run_id) for item in campaign_products for run_id in (item.content_run_ids_json or [])}
        if run_ids:
            return self.db.scalars(select(models.ContentRun).where(models.ContentRun.id.in_(run_ids))).all()
        if not product_ids:
            return []
        return self.db.scalars(select(models.ContentRun).where(models.ContentRun.product_id.in_(product_ids))).all()

    def _approved_packages(self, product_ids: list[int]) -> list[models.PublishingPackage]:
        if not product_ids:
            return []
        return self.db.scalars(
            select(models.PublishingPackage).where(
                models.PublishingPackage.product_id.in_(product_ids),
                models.PublishingPackage.review_status == "approved",
                models.PublishingPackage.status.in_(["approved", "ready", "scheduled", "published"]),
            )
        ).all()

    @staticmethod
    def _has_matrix_photo(
        matrix_row: models.ProductMatrixRow | None,
        validation_row: BombarMatrixRowValidation | None,
        product: models.Product | None,
    ) -> bool:
        if validation_row:
            return validation_row.has_photo
        if matrix_row:
            return bool(matrix_row.photo_urls_json)
        return bool(product and product.images_json)

    @staticmethod
    def _has_reference(product: models.Product | None) -> bool:
        return bool(product and product.images_json)

    @staticmethod
    def _has_price(
        matrix_row: models.ProductMatrixRow | None,
        validation_row: BombarMatrixRowValidation | None,
        product: models.Product | None,
    ) -> bool:
        if validation_row:
            return validation_row.has_price
        if matrix_row:
            return matrix_row.price is not None
        return bool(product and (product.attributes_json or {}).get("price") is not None)

    @staticmethod
    def _has_stock(
        matrix_row: models.ProductMatrixRow | None,
        validation_row: BombarMatrixRowValidation | None,
        product: models.Product | None,
    ) -> bool:
        if validation_row:
            return validation_row.has_stock
        if matrix_row:
            return matrix_row.stock_qty is not None
        return bool(product and (product.attributes_json or {}).get("stock_qty") is not None)

    def _sku_blockers(
        self,
        item: models.CampaignProduct,
        runs: list[models.ContentRun],
        has_photo: bool,
        has_reference: bool,
        has_price: bool,
        has_stock: bool,
        validation_row: BombarMatrixRowValidation | None,
    ) -> list[dict[str, Any]]:
        blockers = []
        if validation_row:
            blockers.extend({"source": "matrix_validation", "blocker": error} for error in validation_row.errors)
        if not has_photo:
            blockers.append({"source": "matrix_validation", "blocker": "missing_photo"})
        if not has_reference:
            blockers.append({"source": "product_reference", "blocker": "missing_reference"})
        if not has_price:
            blockers.append({"source": "matrix_validation", "blocker": "missing_price"})
        if not has_stock:
            blockers.append({"source": "matrix_validation", "blocker": "missing_stock"})
        if not runs:
            blockers.append({"source": "content_readiness", "blocker": "missing_content_run"})
        for blocker in item.blockers_json or []:
            if self._is_production_blocker(blocker):
                blockers.append({"source": "campaign_product", "blocker": blocker})
        for run in runs:
            for blocker in run.blockers_json or []:
                if self._is_production_blocker(blocker):
                    blockers.append({"source": "content_run", "blocker": blocker})
        if runs and not any(run.prompt_pack_id for run in runs):
            blockers.append({"source": "content_readiness", "blocker": "missing_prompt_pack"})
        return self._dedupe_blockers(blockers)

    @staticmethod
    def _is_production_blocker(blocker: str) -> bool:
        return any(prefix in blocker for prefix in BLOCKING_CONTENT_PREFIXES)

    @staticmethod
    def _dedupe_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped = []
        seen = set()
        for blocker in blockers:
            key = (blocker.get("source"), blocker.get("blocker"))
            if key not in seen:
                seen.add(key)
                deduped.append(blocker)
        return deduped

    @staticmethod
    def _sku_next_actions(blockers: list[dict[str, Any]], prompt_pack_count: int, approved_package_count: int) -> list[dict[str, Any]]:
        blocker_names = {blocker.get("blocker", "") for blocker in blockers}
        actions = []
        if any("missing_photo" in blocker or "missing_reference" in blocker for blocker in blocker_names):
            actions.append({"action": "attach_product_reference", "reason": "Add approved product packshot/reference before real video."})
        if "missing_price" in blocker_names:
            actions.append({"action": "fill_price", "reason": "Price is required for production readiness."})
        if "missing_stock" in blocker_names:
            actions.append({"action": "fill_stock", "reason": "Stock is required before scaling."})
        if prompt_pack_count == 0:
            actions.append({"action": "rerun_prompt_only", "reason": "PromptPack is missing."})
        if not approved_package_count:
            actions.append({"action": "human_review_required", "reason": "Only approved videos/packages can be distributed."})
        return actions

    @staticmethod
    def _sku_status(blockers: list[dict[str, Any]], prompt_pack_count: int, approved_package_count: int) -> str:
        if blockers:
            return "blocked"
        if approved_package_count:
            return "publishing_ready"
        if prompt_pack_count:
            return "prompt_ready"
        return "blocked"

    def _distribution_blockers(self, factory_report: FactoryAcceptanceReport, campaign: models.Campaign) -> list[dict[str, Any]]:
        blockers = [
            blocker
            for blocker in factory_report.blockers
            if (blocker.get("source") == "distribution_plan" or "destination" in str(blocker.get("blocker", "")))
        ]
        available_destinations = self.db.scalars(
            select(models.PublishingDestination).where(
                models.PublishingDestination.brand == campaign.brand,
                models.PublishingDestination.status.in_(["draft", "ready", "active"]),
            )
        ).all()
        if len(available_destinations) < campaign.target_destination_count:
            blockers.append(
                {
                    "source": "destination_capacity",
                    "blocker": "destination_capacity_below_target",
                    "available_destinations": len(available_destinations),
                    "target_destinations": campaign.target_destination_count,
                }
            )
        return self._dedupe_blockers(blockers)

    @staticmethod
    def _campaign_next_actions(
        readiness: list[BombarSkuReadiness],
        factory_report: FactoryAcceptanceReport,
        distribution_blockers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions = [
            {
                "scope": "campaign",
                "action": "keep_paid_calls_disabled",
                "reason": "Production dry run must not call paid video providers.",
                "count": 1,
            }
        ]
        missing_refs = sum(1 for row in readiness if not row.has_reference)
        missing_price = sum(1 for row in readiness if not row.has_price)
        missing_stock = sum(1 for row in readiness if not row.has_stock)
        blocked = sum(1 for row in readiness if row.status == "blocked")
        if missing_refs:
            actions.append({"scope": "sku", "action": "attach_product_references", "reason": "SKU lacks product photo/reference.", "count": missing_refs})
        if missing_price:
            actions.append({"scope": "sku", "action": "fill_prices", "reason": "SKU lacks matrix price.", "count": missing_price})
        if missing_stock:
            actions.append({"scope": "sku", "action": "fill_stock", "reason": "SKU lacks stock quantity.", "count": missing_stock})
        if blocked:
            actions.append({"scope": "sku", "action": "resolve_sku_blockers", "reason": "SKU cannot proceed to production yet.", "count": blocked})
        if factory_report.publishing_packages_approved == 0:
            actions.append({"scope": "campaign", "action": "manual_review_and_approve_videos", "reason": "Distribution requires approved packages only.", "count": 1})
        if distribution_blockers:
            actions.append({"scope": "campaign", "action": "prepare_owned_destinations", "reason": "Destination capacity is below target.", "count": len(distribution_blockers)})
        return actions
