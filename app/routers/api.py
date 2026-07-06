import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.asset_storage import ProductAssetStorage
from app.assets.asset_validator import AssetValidator
from app.assets.errors import AssetKitError
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.assets.reference_bundle_builder import ProviderReferenceBundleBuilder
from app.assets.types import ProductAssetDescriptor
from app.bombar_launch import (
    BombarMatrixImporter,
    DestinationSetupPlanner,
    DistributionAllocator,
    LaunchDashboardService,
    LaunchPlanner,
)
from app.bombar_launch.errors import BombarLaunchDataError
from app.bombar_production import BombarProductionDryRunService
from app.bombar_production.errors import BombarProductionError
from app.campaign_batch import BatchExecutor, BatchReporter, BatchSelector
from app.campaign_batch.errors import CampaignBatchDataError
from app.campaign_autopilot import CampaignDistributionPlanner, CampaignRunner, CampaignService, ProductMatrixImporter
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_execution import ActionQueueService, ExecutionReportService, ExecutionStateService
from app.campaign_execution.errors import CampaignExecutionDataError
from app.campaign_performance import (
    CampaignMetricsImporter,
    CampaignPerformanceAggregator,
    CampaignPerformanceReportService,
    CampaignPerformanceScorer,
    CampaignRecommendationEngine,
)
from app.campaign_performance.errors import CampaignPerformanceDataError
from app.content_factory import ContentPerformanceService, ContentRunOrchestrator, ContentStatsImporter
from app.content_factory.errors import ContentFactoryError
from app.creative.creative_spec_builder import CreativeSpecBuilder
from app.creative.creative_spec_validator import CreativeSpecValidator
from app.creative.errors import CreativeSpecError
from app.creative.types import CreativeSpec
from app.database import get_db
from app.demand.errors import DemandError
from app.engine import EngineRunResult, VideoFactoryEngine
from app.engine.errors import EngineError
from app.factory_os import FactoryAcceptanceReportService, FactoryHealthCheck, FactoryLaunchWorkflow, FactoryRunbookService
from app.factory_os.errors import FactoryOSError
from app.intelligence.csv_imports import import_csv_text
from app.intelligence.errors import IntelligenceError
from app.intelligence.generation_runner import GeneratorRunArtifacts, GeneratorRunService
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.prompt_builder import PromptPackBuilder
from app.intelligence.safety import provider_key_status
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.script_generator import GeneratorScriptService
from app.intelligence.video_generator import GeneratorVideoService
from app.launch_operations import (
    DestinationCapacityService,
    LaunchActionPlanner,
    LaunchReadinessService,
    LaunchReportService,
    QualityGateService,
)
from app.launch_operations.errors import LaunchOperationsError
from app.publishing import ManualUploadProvider, PublishingDestinationService, PublishingPackageService, PublishingScheduler
from app.publishing.errors import PublishingError
from app.variants.creative_variant_builder import CreativeVariantBuilder
from app.variants.errors import VariantError
from app.variants.first_frame_builder import FirstFrameBuilder
from app.variants.variant_scorer import VariantScorer
from app.variants.variant_selector import VariantSelector
from app.video_generator.errors import VideoGeneratorError
from app.video_generator.generator import VideoGenerator
from app.video_generator.real_smoke_runner import RealSmokeRunner
from app.workflows.working_video_generator import WorkingVideoGenerator
from app.services.script_engine import ScriptEngine
from app.services.video_engine import VideoEngine
from app.services.publishing_engine import PublishingEngine
from app.services.warmup_scheduler import WarmupScheduler
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api", tags=["api"])


class EngineRunRequest(BaseModel):
    product_id: int
    account_id: int | None = None


class GeneratorProductRequest(BaseModel):
    product_id: int


class GeneratorScriptBriefRequest(BaseModel):
    intelligence_pack_id: int


class GeneratorScriptRequest(BaseModel):
    script_brief_id: int
    llm_provider: str | None = None


class GeneratorPromptPackRequest(BaseModel):
    script_variant_id: int
    provider: str = "runway"
    script_brief_id: int | None = None


class GeneratorVideoJobRequest(BaseModel):
    prompt_pack_id: int
    video_provider: str | None = None


class GeneratorRealRunRequest(BaseModel):
    product_id: int
    llm_provider: str | None = None
    video_provider: str | None = None
    confirm_real_spend: bool = False
    max_scenes: int | None = None
    full_video: bool = False


class GeneratorProviderRunRequest(BaseModel):
    confirm_real_spend: bool = False


class CreativeSpecBuildRequest(BaseModel):
    product_id: int
    platform: str = "Instagram Reels"
    duration: int = 15
    format: str = "short_video"
    aspect_ratio: str = "9:16"


class AssetKitBuildRequest(BaseModel):
    product_id: int
    override_required_assets: bool = False


class AssetKitValidateRequest(BaseModel):
    require_real_generation: bool = True
    override_required_assets: bool = False


class AssetUrlAttachRequest(BaseModel):
    url: str
    asset_type: str | None = None
    manual_label: str | None = None
    is_primary_reference: bool = False


class AssetPatchRequest(BaseModel):
    asset_type: str | None = None
    asset_role: str | None = None
    is_primary_reference: bool | None = None
    manual_label: str | None = None
    review_status: str | None = None
    review_notes: str | None = None


class ProductReferenceRequest(BaseModel):
    provider: str = "runway"


class FirstFrameBuildRequest(BaseModel):
    creative_spec_id: int
    asset_kit_id: int | None = None


class CreativeVariantSetBuildRequest(BaseModel):
    creative_spec_id: int
    asset_kit_id: int | None = None
    count: int = 5


class VideoGeneratorPromptPackRequest(BaseModel):
    creative_spec_id: int
    video_provider: str | None = None


class VideoGeneratorVariantPromptPackRequest(BaseModel):
    creative_variant_id: int
    video_provider: str | None = None


class VideoGeneratorStartRequest(BaseModel):
    creative_spec_id: int | None = None
    generation_variant_id: int | None = None
    video_provider: str | None = None
    confirm_real_spend: bool = False
    max_scenes: int | None = None
    full_video: bool = False


class VideoGeneratorRegenerateSceneRequest(BaseModel):
    scene_number: int


class VariantRealSmokeRequest(BaseModel):
    provider: str = "runway"
    real_run: bool = False
    allow_real_spend: bool = False
    max_scenes: int = 1
    full_video: bool = False


class WorkingVideoPrepareRequest(BaseModel):
    product_id: int
    platform: str = "Instagram Reels"
    duration_seconds: int = 15
    variant_count: int = 5


class WorkingVideoPromptOnlyRequest(BaseModel):
    selected_variant_id: int
    video_provider: str = "runway"


class WorkingVideoRealSmokeRequest(BaseModel):
    selected_variant_id: int
    video_provider: str = "runway"
    real_run: bool = False
    allow_real_spend: bool = False
    max_scenes: int = 1


class ContentFactoryPrepareRequest(BaseModel):
    product_id: int
    platform: str = "Instagram Reels"
    duration_seconds: int = 15
    variant_count: int = 5


class ContentFactoryRealSmokeRequest(BaseModel):
    provider: str = "runway"
    real_run: bool = False
    allow_real_spend: bool = False


class CampaignCreateRequest(BaseModel):
    name: str
    brand: str = "Bombar"
    import_id: int | None = None
    product_ids: list[int] | None = None
    target_video_count: int = 350
    target_destination_count: int = 120
    source_type: str | None = None


class CampaignDistributionPlanRequest(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None


class BombarCampaignCreateRequest(BaseModel):
    import_id: int
    name: str | None = None
    brand: str = "Bombar"
    target_video_count: int = 350
    target_destination_count: int = 120
    start_date: datetime | None = None
    end_date: datetime | None = None


class BombarCampaignPrepareRequest(BaseModel):
    platform: str = "Instagram Reels"
    duration_seconds: int = 15
    variant_count: int | None = None


class BombarDestinationPackPatchRequest(BaseModel):
    status: str | None = None
    suggested_name: str | None = None
    suggested_handle: str | None = None
    bio_text: str | None = None
    avatar_asset_path: str | None = None


class CampaignExecutionExecuteRequest(BaseModel):
    allow_paid: bool = False


class CampaignBatchRequest(BaseModel):
    action_type: str | None = None


class FactoryPromptOnlyLaunchRequest(BaseModel):
    matrix_path: str
    campaign_name: str = "Demo Launch"
    target_videos: int = 350
    target_destinations: int = 120
    brand: str = "Factory OS"
    performance_csv_path: str | None = "sample_data/campaign_performance.csv"


class BombarProductionDryRunRequest(BaseModel):
    matrix_path: str
    campaign_name: str = "Bombar Production Dry Run"
    target_videos: int = 350
    target_destinations: int = 120
    reports_dir: str = "reports"


def get_or_404(db: Session, model: type, entity_id: int):
    entity = db.get(model, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return entity


def parse_json_cell(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def generator_artifacts_response(artifacts: GeneratorRunArtifacts) -> dict:
    video_job = artifacts.video_job
    return {
        "product_id": artifacts.pack.product_id,
        "intelligence_pack_id": artifacts.pack.id,
        "script_brief_id": artifacts.brief.id,
        "script_job_id": artifacts.script_job.id,
        "script_variant_id": artifacts.variant.id,
        "prompt_pack_id": artifacts.prompt_pack.id,
        "video_job_id": video_job.id if video_job else None,
        "status": video_job.status if video_job else "prompt_pack_ready",
        "llm_provider": artifacts.script_job.llm_provider,
        "llm_model": artifacts.script_job.llm_model,
        "video_provider": video_job.provider if video_job else artifacts.prompt_pack.prompt_pack_json.get("provider"),
        "provider_status": artifacts.provider_status,
        "local_output_paths": artifacts.local_output_paths or [],
        "final_video_path": video_job.output_video_path if video_job else None,
        "report_path": artifacts.report_path,
    }


def creative_spec_response(record: models.VideoCreativeSpecRecord) -> dict:
    return {
        "id": record.id,
        "product_id": record.product_id,
        "status": record.status,
        "platform": record.platform,
        "format": record.format,
        "duration_seconds": record.duration_seconds,
        "spec": record.spec_json,
        "hook_candidates": record.hook_candidates_json,
        "validation_report": record.validation_report_json,
        "warnings": record.warnings_json,
    }


def asset_kit_response(kit: models.ProductAssetKit) -> dict:
    return {
        "id": kit.id,
        "product_id": kit.product_id,
        "status": kit.status,
        "assets": kit.assets_json,
        "required_assets": kit.required_assets_json,
        "missing_assets": kit.missing_assets_json,
        "validation_report": kit.validation_report_json,
        "warnings": kit.warnings_json,
        "real_generation_allowed": kit.real_generation_allowed,
        "primary_reference_asset_id": kit.primary_reference_asset_id,
        "provider_reference_bundle": kit.provider_reference_bundle_json,
        "real_generation_blockers": kit.real_generation_blockers_json,
        "override_required_assets": kit.override_required_assets,
    }


def asset_response(asset: models.ProductAsset) -> dict:
    return {
        "id": asset.id,
        "product_id": asset.product_id,
        "asset_kit_id": asset.asset_kit_id,
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
        "status": asset.status,
        "is_primary_reference": asset.is_primary_reference,
        "is_safe_for_real_generation": asset.is_safe_for_real_generation,
        "manual_label": asset.manual_label,
        "review_status": asset.review_status,
        "review_notes": asset.review_notes,
        "checksum": asset.checksum,
        "metadata": asset.metadata_json,
        "warnings": asset.warnings_json,
    }


def reference_bundle_response(bundle: models.ProductReferenceBundle) -> dict:
    return {
        "id": bundle.id,
        "product_id": bundle.product_id,
        "asset_kit_id": bundle.asset_kit_id,
        "status": bundle.status,
        "provider": bundle.provider,
        "primary_image_asset_id": bundle.primary_image_asset_id,
        "reference_asset_ids": bundle.reference_asset_ids_json,
        "provider_payload": bundle.provider_payload_json,
        "blockers": bundle.blockers_json,
        "warnings": bundle.warnings_json,
    }


def first_frame_response(option: models.FirstFrameOption) -> dict:
    return {
        "id": option.id,
        "creative_spec_id": option.creative_spec_id,
        "asset_kit_id": option.asset_kit_id,
        "option_number": option.option_number,
        "status": option.status,
        "option": option.option_json,
        "risk_flags": option.risk_flags_json,
    }


def variant_response(variant: models.CreativeVariant) -> dict:
    return {
        "id": variant.id,
        "creative_variant_set_id": variant.creative_variant_set_id,
        "creative_spec_id": variant.creative_spec_id,
        "first_frame_option_id": variant.first_frame_option_id,
        "variant_number": variant.variant_number,
        "status": variant.status,
        "hook_text": variant.hook_text,
        "first_frame": variant.first_frame_json,
        "scene_plan": variant.scene_plan_json,
        "scene_pacing": variant.pacing_json,
        "cta_framing": variant.cta_framing,
        "visual_style": variant.visual_style,
        "product_reveal_timing": variant.product_reveal_timing,
        "asset_refs": variant.asset_refs_json,
        "score": variant.score_json,
        "risk_flags": variant.risk_flags_json,
        "selection_reason": variant.selection_reason,
    }


def variant_set_response(variant_set: models.CreativeVariantSet) -> dict:
    return {
        "id": variant_set.id,
        "creative_spec_id": variant_set.creative_spec_id,
        "asset_kit_id": variant_set.asset_kit_id,
        "status": variant_set.status,
        "variant_count": variant_set.variant_count,
        "selected_variant_id": variant_set.selected_variant_id,
        "selection_reason": variant_set.selection_reason,
        "score_summary": variant_set.score_summary_json,
        "warnings": variant_set.warnings_json,
        "variants": [variant_response(variant) for variant in sorted(variant_set.variants, key=lambda item: item.variant_number)],
    }


def generation_variant_response(variant: models.VideoGenerationVariant) -> dict:
    video_job = variant.video_job
    return {
        "id": variant.id,
        "creative_spec_id": variant.creative_spec_id,
        "creative_variant_id": variant.creative_variant_id,
        "prompt_pack_id": variant.prompt_pack_id,
        "video_job_id": variant.video_job_id,
        "provider": variant.provider,
        "status": variant.status,
        "prompt_pack": variant.prompt_pack_json,
        "provider_payload": variant.provider_payload_json,
        "local_output_paths": variant.local_output_paths_json,
        "final_video_path": variant.final_video_path or (video_job.output_video_path if video_job else None),
        "quality_score": variant.quality_score_json,
        "provider_job_ids": [clip.provider_job_id for clip in video_job.clips if clip.provider_job_id] if video_job else [],
    }


@router.post("/publishing/destinations", response_model=schemas.PublishingDestinationRead)
def create_publishing_destination(payload: schemas.PublishingDestinationCreate, db: Session = Depends(get_db)):
    try:
        return PublishingDestinationService(db).create(
            brand=payload.brand,
            platform=payload.platform,
            name=payload.name,
            handle=payload.handle,
            url=payload.url,
            owner_name=payload.owner_name,
            status=payload.status,
            posting_mode=payload.posting_mode,
            auth_status=payload.auth_status,
            allowed_formats=payload.allowed_formats_json,
            daily_limit=payload.daily_limit,
            weekly_limit=payload.weekly_limit,
            notes=payload.notes,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing/destinations", response_model=list[schemas.PublishingDestinationRead])
def list_publishing_destinations(db: Session = Depends(get_db)):
    return PublishingDestinationService(db).list()


@router.get("/publishing/destinations/{destination_id}", response_model=schemas.PublishingDestinationRead)
def get_publishing_destination(destination_id: int, db: Session = Depends(get_db)):
    try:
        return PublishingDestinationService(db).get(destination_id)
    except PublishingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/publishing/destinations/{destination_id}", response_model=schemas.PublishingDestinationRead)
def patch_publishing_destination(
    destination_id: int,
    payload: schemas.PublishingDestinationPatch,
    db: Session = Depends(get_db),
):
    try:
        return PublishingDestinationService(db).update(destination_id, **payload.model_dump(exclude_unset=True))
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publishing/destinations/{destination_id}/readiness-check", response_model=schemas.PublishingReadinessRead)
def check_publishing_destination_readiness(destination_id: int, db: Session = Depends(get_db)):
    try:
        readiness = PublishingDestinationService(db).readiness(PublishingDestinationService(db).get(destination_id))
        return schemas.PublishingReadinessRead(
            ready=readiness.ready,
            status=readiness.status,
            blockers=readiness.blockers,
            warnings=readiness.warnings,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/publishing/destinations/import-csv")
async def import_publishing_destinations_csv(
    file: UploadFile = File(...),
    default_brand: str = "Altea",
    db: Session = Depends(get_db),
):
    text = (await file.read()).decode("utf-8-sig")
    return PublishingDestinationService(db).import_csv_text(text, default_brand=default_brand)


@router.post("/publishing/packages", response_model=schemas.PublishingPackageRead)
def create_safe_publishing_package(payload: schemas.SafePublishingPackageCreate, db: Session = Depends(get_db)):
    try:
        return PublishingPackageService(db).create_from_video(
            video_job_id=payload.video_job_id,
            platform=payload.platform,
            title=payload.title,
            description=payload.description,
            hashtags=[str(item) for item in payload.hashtags_json] if payload.hashtags_json else None,
            cta=payload.cta,
            cover_image_path=payload.cover_image_path,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing/packages", response_model=list[schemas.PublishingPackageRead])
def list_safe_publishing_packages(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingPackage).order_by(models.PublishingPackage.created_at.desc())).all()


@router.get("/publishing/packages/{package_id}", response_model=schemas.PublishingPackageRead)
def get_safe_publishing_package(package_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingPackage, package_id)


@router.post("/publishing/packages/{package_id}/approve", response_model=schemas.PublishingPackageRead)
def approve_safe_publishing_package(
    package_id: int,
    payload: schemas.PublishingPackageApprovalRequest,
    db: Session = Depends(get_db),
):
    package = get_or_404(db, models.PublishingPackage, package_id)
    try:
        return PublishingPackageService(db).approve(
            package,
            reviewer_name=payload.reviewer_name,
            manual_override=payload.manual_override,
            notes=payload.notes,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publishing/packages/{package_id}/reject", response_model=schemas.PublishingPackageRead)
def reject_safe_publishing_package(
    package_id: int,
    payload: schemas.PublishingPackageRejectRequest,
    db: Session = Depends(get_db),
):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingPackageService(db).reject(package, payload.reason, reviewer_name=payload.reviewer_name)


@router.post("/publishing/tasks/schedule", response_model=schemas.PublishingTaskRead)
def schedule_safe_publishing_task(payload: schemas.PublishingTaskScheduleRequest, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, payload.publishing_package_id)
    destination = get_or_404(db, models.PublishingDestination, payload.destination_id)
    try:
        return PublishingScheduler(db).schedule(
            package=package,
            destination=destination,
            scheduled_at=payload.scheduled_at,
            operator_name=payload.operator_name,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publishing/tasks/bulk-schedule")
def bulk_schedule_safe_publishing_tasks(payload: schemas.PublishingBulkScheduleRequest, db: Session = Depends(get_db)):
    try:
        return PublishingScheduler(db).bulk_schedule(
            package_ids=payload.publishing_package_ids,
            destination_ids=payload.destination_ids,
            start_at=payload.start_at,
            interval_minutes=payload.interval_minutes,
            operator_name=payload.operator_name,
            dry_run=payload.dry_run,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing/tasks", response_model=list[schemas.PublishingTaskRead])
def list_safe_publishing_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.scheduled_at.desc())).all()


@router.get("/publishing/tasks/{task_id}", response_model=schemas.PublishingTaskRead)
def get_safe_publishing_task(task_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingTask, task_id)


@router.post("/publishing/tasks/{task_id}/run", response_model=schemas.PublishingTaskRead)
def run_safe_publishing_task(task_id: int, db: Session = Depends(get_db)):
    return ManualUploadProvider(db).run(get_or_404(db, models.PublishingTask, task_id))


@router.post("/publishing/tasks/{task_id}/mark-manual-uploaded", response_model=schemas.PublishingTaskRead)
def mark_safe_publishing_task_uploaded(
    task_id: int,
    payload: schemas.PublishingManualUploadedRequest,
    db: Session = Depends(get_db),
):
    try:
        return ManualUploadProvider(db).mark_published(
            get_or_404(db, models.PublishingTask, task_id),
            payload.final_url,
            payload.operator_name,
        )
    except PublishingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publishing/tasks/{task_id}/cancel", response_model=schemas.PublishingTaskRead)
def cancel_safe_publishing_task(task_id: int, db: Session = Depends(get_db)):
    task = get_or_404(db, models.PublishingTask, task_id)
    task.status = "cancelled"
    db.commit()
    db.refresh(task)
    return task


@router.get("/publishing/calendar", response_model=list[schemas.PublishingTaskRead])
def safe_publishing_calendar(db: Session = Depends(get_db)):
    return PublishingScheduler(db).calendar()


@router.post("/products", response_model=schemas.ProductRead)
def create_product(payload: schemas.ProductCreate, db: Session = Depends(get_db)):
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=list[schemas.ProductRead])
def list_products(db: Session = Depends(get_db)):
    return db.scalars(select(models.Product).order_by(models.Product.created_at.desc())).all()


@router.get("/products/{product_id}", response_model=schemas.ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.Product, product_id)


@router.post("/products/import-csv", response_model=list[schemas.ProductRead])
async def import_products_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(text))
    products = []
    for row in rows:
        product = models.Product(
            sku=row["sku"],
            brand=row.get("brand") or "Unknown",
            marketplace=row.get("marketplace"),
            title=row.get("title") or row["sku"],
            description=row.get("description"),
            category=row.get("category"),
            attributes_json=parse_json_cell(row.get("attributes_json"), {}),
            benefits_json=parse_json_cell(row.get("benefits_json"), []),
            images_json=parse_json_cell(row.get("images_json"), []),
            reviews_json=parse_json_cell(row.get("reviews_json"), []),
            restrictions_json=parse_json_cell(row.get("restrictions_json"), []),
            product_url=row.get("product_url"),
        )
        db.add(product)
        products.append(product)
    db.commit()
    for product in products:
        db.refresh(product)
    return products


@router.post("/brand-guides", response_model=schemas.BrandGuideRead)
def create_brand_guide(payload: schemas.BrandGuideCreate, db: Session = Depends(get_db)):
    guide = models.BrandGuide(**payload.model_dump())
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


@router.get("/brand-guides", response_model=list[schemas.BrandGuideRead])
def list_brand_guides(db: Session = Depends(get_db)):
    return db.scalars(select(models.BrandGuide).order_by(models.BrandGuide.brand)).all()


@router.post("/creative-templates", response_model=schemas.CreativeTemplateRead)
def create_creative_template(payload: schemas.CreativeTemplateCreate, db: Session = Depends(get_db)):
    template = models.CreativeTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/creative-templates", response_model=list[schemas.CreativeTemplateRead])
def list_creative_templates(db: Session = Depends(get_db)):
    return db.scalars(select(models.CreativeTemplate).order_by(models.CreativeTemplate.name)).all()


@router.post("/reviews", response_model=schemas.ReviewRead)
def create_review(payload: schemas.ReviewCreate, db: Session = Depends(get_db)):
    review = models.Review(**payload.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.post("/engine/run-demo", response_model=EngineRunResult)
def run_engine_demo(payload: EngineRunRequest, db: Session = Depends(get_db)):
    result = VideoFactoryEngine(db).run_full_demo(payload.product_id, payload.account_id)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@router.get("/engine/status/{publishing_job_id}")
def get_engine_status(publishing_job_id: int, db: Session = Depends(get_db)):
    try:
        return VideoFactoryEngine(db).status_for_publishing_job(publishing_job_id)
    except EngineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/creative/specs/build")
def build_creative_spec(payload: CreativeSpecBuildRequest, db: Session = Depends(get_db)):
    try:
        record = CreativeSpecBuilder(db).build_for_product(
            payload.product_id,
            platform=payload.platform,
            duration_seconds=payload.duration,
            format=payload.format,
            aspect_ratio=payload.aspect_ratio,
        )
        return creative_spec_response(record)
    except (CreativeSpecError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/creative/specs/{creative_spec_id}")
def get_creative_spec(creative_spec_id: int, db: Session = Depends(get_db)):
    return creative_spec_response(get_or_404(db, models.VideoCreativeSpecRecord, creative_spec_id))


@router.post("/creative/specs/{creative_spec_id}/validate")
def validate_creative_spec(creative_spec_id: int, db: Session = Depends(get_db)):
    record = get_or_404(db, models.VideoCreativeSpecRecord, creative_spec_id)
    product = record.product
    brand_guide = db.scalar(select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id))
    spec = CreativeSpec.model_validate(record.spec_json)
    report = CreativeSpecValidator().validate(
        spec,
        forbidden_words=brand_guide.forbidden_words_json if brand_guide else [],
        forbidden_claims=brand_guide.forbidden_claims_json if brand_guide else [],
    )
    record.validation_report_json = report.model_dump(mode="json")
    record.status = "ready" if report.valid else "needs_revision"
    db.commit()
    return {"id": record.id, "validation_report": record.validation_report_json, "status": record.status}


@router.post("/creative/specs/{creative_spec_id}/hook-candidates")
def get_creative_spec_hook_candidates(creative_spec_id: int, db: Session = Depends(get_db)):
    record = get_or_404(db, models.VideoCreativeSpecRecord, creative_spec_id)
    return {"id": record.id, "hook_candidates": record.hook_candidates_json}


@router.post("/assets/kits/build")
def build_asset_kit(payload: AssetKitBuildRequest, db: Session = Depends(get_db)):
    try:
        kit = AssetKitBuilder(db).build_for_product(
            payload.product_id,
            override_required_assets=payload.override_required_assets,
        )
        return asset_kit_response(kit)
    except AssetKitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/assets/kits/{asset_kit_id}")
def get_asset_kit(asset_kit_id: int, db: Session = Depends(get_db)):
    return asset_kit_response(get_or_404(db, models.ProductAssetKit, asset_kit_id))


@router.post("/assets/kits/{asset_kit_id}/validate")
def validate_asset_kit(asset_kit_id: int, payload: AssetKitValidateRequest, db: Session = Depends(get_db)):
    kit = get_or_404(db, models.ProductAssetKit, asset_kit_id)
    assets = [ProductAssetDescriptor.model_validate(asset) for asset in kit.assets_json]
    report = AssetValidator().validate(
        assets,
        require_real_generation=payload.require_real_generation,
        override_required_assets=payload.override_required_assets,
    )
    kit.validation_report_json = report.model_dump(mode="json")
    kit.missing_assets_json = report.missing_assets
    kit.warnings_json = report.warnings
    kit.real_generation_allowed = report.real_generation_allowed or payload.override_required_assets
    kit.status = "ready" if report.valid else "needs_assets"
    db.commit()
    db.refresh(kit)
    return asset_kit_response(kit)


@router.post("/assets/products/{product_id}/upload")
async def upload_product_asset(
    product_id: int,
    file: UploadFile = File(...),
    asset_type: str | None = Form(None),
    manual_label: str | None = Form(None),
    is_primary_reference: bool = Form(False),
    db: Session = Depends(get_db),
):
    try:
        asset = ProductAssetStorage(db).upload_file(
            product_id,
            filename=file.filename or "asset",
            content=await file.read(),
            asset_type=asset_type,
            manual_label=manual_label,
            is_primary_reference=is_primary_reference,
        )
        return asset_response(asset)
    except AssetKitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assets/products/{product_id}/attach-url")
def attach_product_asset_url(product_id: int, payload: AssetUrlAttachRequest, db: Session = Depends(get_db)):
    try:
        asset = ProductAssetStorage(db).attach_url(
            product_id,
            url=payload.url,
            asset_type=payload.asset_type,
            manual_label=payload.manual_label,
            is_primary_reference=payload.is_primary_reference,
        )
        return asset_response(asset)
    except AssetKitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/assets/products/{product_id}")
def list_product_assets(product_id: int, db: Session = Depends(get_db)):
    assets = db.scalars(select(models.ProductAsset).where(models.ProductAsset.product_id == product_id).order_by(models.ProductAsset.id)).all()
    return {"product_id": product_id, "assets": [asset_response(asset) for asset in assets]}


@router.patch("/assets/{asset_id}")
def patch_product_asset(asset_id: int, payload: AssetPatchRequest, db: Session = Depends(get_db)):
    try:
        asset = ProductAssetStorage(db).update_asset(asset_id, **payload.model_dump(exclude_unset=True))
        return asset_response(asset)
    except AssetKitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assets/products/{product_id}/readiness-check")
def check_product_reference_readiness(product_id: int, payload: ProductReferenceRequest, db: Session = Depends(get_db)):
    readiness = ProductReferenceReadinessChecker(db).check(product_id, provider=payload.provider)
    return readiness.model_dump(mode="json")


@router.post("/assets/products/{product_id}/reference-bundle")
def build_product_reference_bundle(product_id: int, payload: ProductReferenceRequest, db: Session = Depends(get_db)):
    try:
        return reference_bundle_response(ProviderReferenceBundleBuilder(db).build(product_id, provider=payload.provider))
    except AssetKitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/variants/first-frames/build")
def build_first_frame_options(payload: FirstFrameBuildRequest, db: Session = Depends(get_db)):
    try:
        options = FirstFrameBuilder(db).build_options(
            payload.creative_spec_id,
            asset_kit_id=payload.asset_kit_id,
        )
        return {"creative_spec_id": payload.creative_spec_id, "options": [first_frame_response(option) for option in options]}
    except (VariantError, AssetKitError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/variants/first-frames/{first_frame_option_id}")
def get_first_frame_option(first_frame_option_id: int, db: Session = Depends(get_db)):
    return first_frame_response(get_or_404(db, models.FirstFrameOption, first_frame_option_id))


@router.post("/variants/sets/build")
def build_creative_variant_set(payload: CreativeVariantSetBuildRequest, db: Session = Depends(get_db)):
    try:
        variant_set = CreativeVariantBuilder(db).build_set(
            payload.creative_spec_id,
            count=payload.count,
            asset_kit_id=payload.asset_kit_id,
        )
        return variant_set_response(variant_set)
    except (VariantError, AssetKitError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/variants/sets/{variant_set_id}")
def get_creative_variant_set(variant_set_id: int, db: Session = Depends(get_db)):
    return variant_set_response(get_or_404(db, models.CreativeVariantSet, variant_set_id))


@router.post("/variants/sets/{variant_set_id}/score")
def score_creative_variant_set(variant_set_id: int, db: Session = Depends(get_db)):
    try:
        return variant_set_response(VariantScorer(db).score_set(variant_set_id))
    except VariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/variants/sets/{variant_set_id}/select-best")
def select_best_creative_variant(variant_set_id: int, db: Session = Depends(get_db)):
    try:
        return variant_set_response(VariantSelector(db).select_best(variant_set_id))
    except VariantError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/prompt-packs/from-spec")
def build_video_generator_prompt_pack(payload: VideoGeneratorPromptPackRequest, db: Session = Depends(get_db)):
    try:
        variant = VideoGenerator(db).build_prompt_pack_from_spec(
            payload.creative_spec_id,
            provider=payload.video_provider,
        )
        return generation_variant_response(variant)
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/prompt-packs/from-variant")
def build_video_generator_prompt_pack_from_variant(payload: VideoGeneratorVariantPromptPackRequest, db: Session = Depends(get_db)):
    try:
        variant = VideoGenerator(db).build_prompt_pack_from_variant(
            payload.creative_variant_id,
            provider=payload.video_provider,
        )
        return generation_variant_response(variant)
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/start")
def start_video_generator(payload: VideoGeneratorStartRequest, db: Session = Depends(get_db)):
    try:
        generator = VideoGenerator(db)
        generation_variant_id = payload.generation_variant_id
        if generation_variant_id is None:
            if payload.creative_spec_id is None:
                raise HTTPException(status_code=400, detail="creative_spec_id or generation_variant_id is required")
            generation_variant_id = generator.build_prompt_pack_from_spec(
                payload.creative_spec_id,
                provider=payload.video_provider,
            ).id
        variant = generator.start_generation(
            generation_variant_id,
            provider=payload.video_provider,
            confirm_real_spend=payload.confirm_real_spend,
            max_scenes=payload.max_scenes,
            full_video=payload.full_video,
        )
        return generation_variant_response(variant)
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/video-generator/jobs/{generation_variant_id}")
def get_video_generator_job(generation_variant_id: int, db: Session = Depends(get_db)):
    return generation_variant_response(get_or_404(db, models.VideoGenerationVariant, generation_variant_id))


@router.post("/video-generator/jobs/{generation_variant_id}/poll")
def poll_video_generator_job(generation_variant_id: int, db: Session = Depends(get_db)):
    try:
        return VideoGenerator(db).poll(generation_variant_id)
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/jobs/{generation_variant_id}/download")
def download_video_generator_job(generation_variant_id: int, db: Session = Depends(get_db)):
    try:
        return generation_variant_response(VideoGenerator(db).download(generation_variant_id))
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/jobs/{generation_variant_id}/assemble")
def assemble_video_generator_job(generation_variant_id: int, db: Session = Depends(get_db)):
    try:
        return generation_variant_response(VideoGenerator(db).assemble(generation_variant_id))
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/jobs/{generation_variant_id}/score")
def score_video_generator_job(generation_variant_id: int, db: Session = Depends(get_db)):
    try:
        review = VideoGenerator(db).score(generation_variant_id)
        return {
            "id": review.id,
            "score": review.score,
            "status": review.status,
            "review": review.review_json,
            "warnings": review.warnings_json,
        }
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/jobs/{generation_variant_id}/regenerate-scene")
def regenerate_video_generator_scene(
    generation_variant_id: int,
    payload: VideoGeneratorRegenerateSceneRequest,
    db: Session = Depends(get_db),
):
    try:
        return {"scene": VideoGenerator(db).regenerate_scene(generation_variant_id, payload.scene_number)}
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/variants/{creative_variant_id}/real-smoke")
def run_variant_real_smoke(
    creative_variant_id: int,
    payload: VariantRealSmokeRequest,
    db: Session = Depends(get_db),
):
    if not payload.real_run:
        raise HTTPException(status_code=400, detail="Real smoke requires explicit real_run=true.")
    try:
        return RealSmokeRunner(db).run_from_variant(
            creative_variant_id,
            provider=payload.provider,
            max_scenes=payload.max_scenes,
            full_video=payload.full_video,
            allow_real_spend=payload.allow_real_spend,
        ).model_dump(mode="json")
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/video-generator/real-smoke/{video_job_id}")
def get_variant_real_smoke(video_job_id: int, db: Session = Depends(get_db)):
    try:
        return RealSmokeRunner(db).output_for_video_job(video_job_id).model_dump(mode="json")
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/real-smoke/{video_job_id}/poll")
def poll_variant_real_smoke(video_job_id: int, db: Session = Depends(get_db)):
    try:
        return RealSmokeRunner(db).poll(video_job_id).model_dump(mode="json")
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/real-smoke/{video_job_id}/download")
def download_variant_real_smoke(video_job_id: int, db: Session = Depends(get_db)):
    try:
        return RealSmokeRunner(db).download(video_job_id).model_dump(mode="json")
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/video-generator/real-smoke/{video_job_id}/score")
def score_variant_real_smoke(video_job_id: int, db: Session = Depends(get_db)):
    try:
        return RealSmokeRunner(db).score(video_job_id).model_dump(mode="json")
    except (VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/working-video/prepare")
def prepare_working_video(payload: WorkingVideoPrepareRequest, db: Session = Depends(get_db)):
    try:
        return WorkingVideoGenerator(db).prepare(
            payload.product_id,
            payload.platform,
            payload.duration_seconds,
            payload.variant_count,
        ).model_dump(mode="json")
    except (DemandError, CreativeSpecError, VariantError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/working-video/prompt-only")
def working_video_prompt_only(payload: WorkingVideoPromptOnlyRequest, db: Session = Depends(get_db)):
    try:
        return WorkingVideoGenerator(db).run_prompt_only(
            payload.selected_variant_id,
            provider=payload.video_provider,
        ).model_dump(mode="json")
    except (DemandError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/working-video/real-smoke")
def working_video_real_smoke(payload: WorkingVideoRealSmokeRequest, db: Session = Depends(get_db)):
    if not payload.real_run:
        raise HTTPException(status_code=400, detail="Working video real smoke requires explicit real_run=true.")
    try:
        return WorkingVideoGenerator(db).run_real_smoke(
            payload.selected_variant_id,
            provider=payload.video_provider,
            allow_real_spend=payload.allow_real_spend,
            max_scenes=payload.max_scenes,
        ).model_dump(mode="json")
    except (DemandError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/working-video/status/{selected_variant_id}")
def working_video_status(selected_variant_id: int, db: Session = Depends(get_db)):
    try:
        return WorkingVideoGenerator(db).status(selected_variant_id).model_dump(mode="json")
    except (DemandError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/content-factory/runs/prepare")
def prepare_content_factory_run(payload: ContentFactoryPrepareRequest, db: Session = Depends(get_db)):
    try:
        return ContentRunOrchestrator(db).prepare_content_run(
            payload.product_id,
            payload.platform,
            payload.duration_seconds,
            payload.variant_count,
        ).model_dump(mode="json")
    except (ContentFactoryError, DemandError, CreativeSpecError, VariantError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/content-factory/runs/{content_run_id}/prompt-only")
def content_factory_prompt_only(content_run_id: int, db: Session = Depends(get_db)):
    try:
        return ContentRunOrchestrator(db).run_prompt_only(content_run_id).model_dump(mode="json")
    except (ContentFactoryError, DemandError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/content-factory/runs/{content_run_id}/real-smoke")
def content_factory_real_smoke(
    content_run_id: int,
    payload: ContentFactoryRealSmokeRequest,
    db: Session = Depends(get_db),
):
    if not payload.real_run:
        raise HTTPException(status_code=400, detail="Content factory real smoke requires explicit real_run=true.")
    try:
        return ContentRunOrchestrator(db).run_real_smoke(
            content_run_id,
            provider=payload.provider,
            allow_real_spend=payload.allow_real_spend,
        ).model_dump(mode="json")
    except (ContentFactoryError, DemandError, VideoGeneratorError, IntelligenceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/content-factory/runs/{content_run_id}/review")
def review_content_factory_run(content_run_id: int, db: Session = Depends(get_db)):
    try:
        return ContentRunOrchestrator(db).review(content_run_id).model_dump(mode="json")
    except ContentFactoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/content-factory/runs/{content_run_id}")
def get_content_factory_run(content_run_id: int, db: Session = Depends(get_db)):
    try:
        return ContentRunOrchestrator(db).get(content_run_id).model_dump(mode="json")
    except ContentFactoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/content-factory/dashboard")
def get_content_factory_dashboard(db: Session = Depends(get_db)):
    return ContentPerformanceService(db).dashboard().model_dump(mode="json")


@router.get("/content-factory/runs/{content_run_id}/recommendations")
def get_content_factory_recommendations(content_run_id: int, db: Session = Depends(get_db)):
    try:
        return {
            "content_run_id": content_run_id,
            "recommendations": [
                item.model_dump(mode="json")
                for item in ContentRunOrchestrator(db).recommend_next_action(content_run_id)
            ],
        }
    except ContentFactoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/content-factory/stats/import-csv")
async def import_content_factory_stats_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8-sig")
    return ContentStatsImporter(db).import_csv_text(text).model_dump(mode="json")


@router.post("/campaigns/import-matrix")
async def import_campaign_product_matrix(file: UploadFile = File(...), db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8-sig")
    return ProductMatrixImporter(db).import_csv_text(text, source_file=file.filename or "product_matrix.csv").model_dump(mode="json")


@router.get("/campaigns/imports/{import_id}")
def get_campaign_product_matrix_import(import_id: int, db: Session = Depends(get_db)):
    matrix_import = get_or_404(db, models.ProductMatrixImport, import_id)
    rows = db.scalars(
        select(models.ProductMatrixRow)
        .where(models.ProductMatrixRow.import_id == import_id)
        .order_by(models.ProductMatrixRow.id)
    ).all()
    return {
        "id": matrix_import.id,
        "source_file": matrix_import.source_file,
        "status": matrix_import.status,
        "imported_count": matrix_import.imported_count,
        "error_count": matrix_import.error_count,
        "warnings": matrix_import.warnings_json or [],
        "errors": matrix_import.errors_json or [],
        "rows": [
            {
                "id": row.id,
                "sku": row.sku,
                "product_name": row.product_name,
                "category": row.category,
                "price": row.price,
                "stock_qty": row.stock_qty,
                "product_url": row.product_url,
                "photo_urls": row.photo_urls_json or [],
                "priority": row.priority,
                "status": row.status,
                "warnings": row.warnings_json or [],
            }
            for row in rows
        ],
    }


@router.post("/bombar/import-matrix")
async def import_bombar_matrix(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    filename = file.filename or "bombar_matrix.csv"
    try:
        importer = BombarMatrixImporter(db)
        if filename.lower().endswith(".xlsx"):
            return importer.import_xlsx_bytes(data, source_file=filename).model_dump(mode="json")
        return importer.import_csv_text(data.decode("utf-8-sig"), source_file=filename).model_dump(mode="json")
    except BombarLaunchDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bombar/imports/{import_id}")
def get_bombar_import(import_id: int, db: Session = Depends(get_db)):
    product_import = get_or_404(db, models.ProductMatrixImport, import_id)
    rows = db.scalars(
        select(models.ProductMatrixRow)
        .where(models.ProductMatrixRow.import_id == import_id)
        .order_by(models.ProductMatrixRow.id)
    ).all()
    return {
        "id": product_import.id,
        "source_file": product_import.source_file,
        "status": product_import.status,
        "imported_count": product_import.imported_count,
        "warnings": product_import.warnings_json or [],
        "errors": product_import.errors_json or [],
        "rows": [
            {
                "id": row.id,
                "sku": row.sku,
                "product_name": row.product_name,
                "category": row.category,
                "price": row.price,
                "margin": ((row.raw_json or {}).get("bombar") or {}).get("margin"),
                "stock_qty": row.stock_qty,
                "product_url": row.product_url,
                "photo_urls": row.photo_urls_json or [],
                "status": row.status,
                "warnings": row.warnings_json or [],
            }
            for row in rows
        ],
    }


@router.post("/campaigns")
def create_campaign(payload: CampaignCreateRequest, db: Session = Depends(get_db)):
    try:
        return CampaignService(db).create_campaign(
            name=payload.name,
            brand=payload.brand,
            import_id=payload.import_id,
            product_ids=payload.product_ids,
            target_video_count=payload.target_video_count,
            target_destination_count=payload.target_destination_count,
            source_type=payload.source_type,
        ).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return [item.model_dump(mode="json") for item in CampaignService(db).list_campaigns()]


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignService(db).get(campaign_id).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaigns/{campaign_id}/prepare")
def prepare_campaign(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignRunner(db).prepare_campaign(campaign_id).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/campaigns/{campaign_id}/run-prompt-only")
def run_campaign_prompt_only(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignRunner(db).run_prompt_only_for_ready_items(campaign_id).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}/state")
def get_campaign_state(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignRunner(db).inspect_campaign(campaign_id).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}/report")
def get_campaign_report(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignRunner(db).generate_campaign_report(campaign_id).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaigns/{campaign_id}/distribution-plan")
def generate_campaign_distribution_plan(
    campaign_id: int,
    payload: CampaignDistributionPlanRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = payload or CampaignDistributionPlanRequest()
    try:
        return CampaignDistributionPlanner(db).generate_plan(
            campaign_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
        ).model_dump(mode="json")
    except CampaignAutopilotDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}/distribution-plan")
def get_campaign_distribution_plan(campaign_id: int, db: Session = Depends(get_db)):
    plan = CampaignDistributionPlanner(db).latest_plan(campaign_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Campaign distribution plan not found")
    return plan


@router.get("/campaign-execution/{campaign_id}/snapshot")
def get_campaign_execution_snapshot(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return ExecutionStateService(db).latest_snapshot(campaign_id).model_dump(mode="json")
    except CampaignExecutionDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-execution/{campaign_id}/refresh")
def refresh_campaign_execution(campaign_id: int, db: Session = Depends(get_db)):
    try:
        snapshot = ExecutionStateService(db).refresh_snapshot(campaign_id)
        actions = ActionQueueService(db).refresh_actions(campaign_id)
        return {
            "snapshot": snapshot.model_dump(mode="json"),
            "actions": [item.model_dump(mode="json") for item in actions],
        }
    except CampaignExecutionDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/campaign-execution/{campaign_id}/actions")
def list_campaign_execution_actions(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return [item.model_dump(mode="json") for item in ActionQueueService(db).list_actions(campaign_id)]
    except CampaignExecutionDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-execution/actions/{action_id}/execute")
def execute_campaign_execution_action(
    action_id: int,
    payload: CampaignExecutionExecuteRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = payload or CampaignExecutionExecuteRequest()
    try:
        return ActionQueueService(db).execute(action_id, allow_paid=payload.allow_paid).model_dump(mode="json")
    except CampaignExecutionDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-execution/actions/{action_id}/resolve")
def resolve_campaign_execution_action(action_id: int, db: Session = Depends(get_db)):
    try:
        return ActionQueueService(db).resolve(action_id).model_dump(mode="json")
    except CampaignExecutionDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-execution/{campaign_id}/report")
def get_campaign_execution_report(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return ExecutionReportService(db).build_report(campaign_id).model_dump(mode="json")
    except CampaignExecutionDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-batch/{campaign_id}/dry-run")
def dry_run_campaign_batch(
    campaign_id: int,
    payload: CampaignBatchRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = payload or CampaignBatchRequest()
    try:
        return BatchExecutor(db).dry_run(campaign_id, action_type=payload.action_type).model_dump(mode="json")
    except CampaignBatchDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-batch/{campaign_id}/execute")
def execute_campaign_batch(
    campaign_id: int,
    payload: CampaignBatchRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = payload or CampaignBatchRequest()
    try:
        return BatchExecutor(db).execute(campaign_id, action_type=payload.action_type).model_dump(mode="json")
    except CampaignBatchDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-batch/{campaign_id}/preview")
def preview_campaign_batch(campaign_id: int, action_type: str | None = None, db: Session = Depends(get_db)):
    try:
        return BatchSelector(db).select_safe_actions(campaign_id, action_type=action_type).model_dump(mode="json")
    except CampaignBatchDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-batch/runs/{batch_run_id}")
def get_campaign_batch_run(batch_run_id: int, db: Session = Depends(get_db)):
    try:
        return BatchExecutor(db).get_run(batch_run_id).model_dump(mode="json")
    except CampaignBatchDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-batch/runs/{batch_run_id}/report")
def get_campaign_batch_report(batch_run_id: int, db: Session = Depends(get_db)):
    try:
        return BatchReporter(db).build_report(batch_run_id).model_dump(mode="json")
    except CampaignBatchDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-performance/{campaign_id}/import-csv")
async def import_campaign_performance_csv(
    campaign_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        csv_text = (await file.read()).decode("utf-8-sig")
        return CampaignMetricsImporter(db).import_csv_text(
            campaign_id,
            csv_text,
            source_file=file.filename or "campaign_performance.csv",
        ).model_dump(mode="json")
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-performance/{campaign_id}/summary")
def get_campaign_performance_summary(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignPerformanceAggregator(db).summarize(campaign_id).model_dump(mode="json")
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-performance/{campaign_id}/scores")
def get_campaign_performance_scores(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return [item.model_dump(mode="json") for item in CampaignPerformanceScorer(db).latest_scores(campaign_id)]
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-performance/{campaign_id}/recommendations")
def get_campaign_performance_recommendations(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return [item.model_dump(mode="json") for item in CampaignRecommendationEngine(db).list_recommendations(campaign_id)]
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-performance/recommendations/{recommendation_id}/accept")
def accept_campaign_performance_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignRecommendationEngine(db).accept(recommendation_id).model_dump(mode="json")
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaign-performance/recommendations/{recommendation_id}/reject")
def reject_campaign_performance_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignRecommendationEngine(db).reject(recommendation_id).model_dump(mode="json")
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/campaign-performance/{campaign_id}/report")
def get_campaign_performance_report(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return CampaignPerformanceReportService(db).build_report(campaign_id).model_dump(mode="json")
    except CampaignPerformanceDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/factory-os/health")
def get_factory_os_health(db: Session = Depends(get_db)):
    return FactoryHealthCheck(db).run().model_dump(mode="json")


@router.post("/factory-os/prompt-only-launch")
def run_factory_prompt_only_launch(payload: FactoryPromptOnlyLaunchRequest, db: Session = Depends(get_db)):
    try:
        return FactoryLaunchWorkflow(db).run_prompt_only_launch(
            payload.matrix_path,
            payload.campaign_name,
            payload.target_videos,
            payload.target_destinations,
            brand=payload.brand,
            performance_csv_path=payload.performance_csv_path,
        ).model_dump(mode="json")
    except FactoryOSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/factory-os/campaigns/{campaign_id}/acceptance-report")
def get_factory_acceptance_report(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return FactoryAcceptanceReportService(db).build(campaign_id).model_dump(mode="json")
    except FactoryOSError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/factory-os/campaigns/{campaign_id}/runbook")
def get_factory_runbook(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return FactoryRunbookService(db).build(campaign_id).model_dump(mode="json")
    except FactoryOSError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/bombar-production-dry-run")
def run_bombar_production_dry_run(payload: BombarProductionDryRunRequest, db: Session = Depends(get_db)):
    try:
        return BombarProductionDryRunService(db, reports_dir=payload.reports_dir).run(
            payload.matrix_path,
            target_videos=payload.target_videos,
            target_destinations=payload.target_destinations,
            campaign_name=payload.campaign_name,
        ).model_dump(mode="json")
    except BombarProductionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bombar-production-dry-run/{campaign_id}/report")
def get_bombar_production_dry_run_report(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return BombarProductionDryRunService(db).build_report(campaign_id).model_dump(mode="json")
    except BombarProductionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/launch-operations/campaigns/{campaign_id}/readiness")
def get_launch_readiness(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return LaunchReadinessService(db).latest_or_refresh(campaign_id).model_dump(mode="json")
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/launch-operations/campaigns/{campaign_id}/refresh")
def refresh_launch_readiness(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return LaunchReadinessService(db).refresh(campaign_id).model_dump(mode="json")
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/launch-operations/campaigns/{campaign_id}/quality-gates")
def get_launch_quality_gates(campaign_id: int, db: Session = Depends(get_db)):
    try:
        gates = QualityGateService(db).list_latest(campaign_id)
        return [gate.model_dump(mode="json") for gate in gates]
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/launch-operations/campaigns/{campaign_id}/destination-capacity")
def get_launch_destination_capacity(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return DestinationCapacityService(db).latest_or_refresh(campaign_id).model_dump(mode="json")
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/launch-operations/campaigns/{campaign_id}/action-plan")
def get_launch_action_plan(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return LaunchActionPlanner(db).latest_or_refresh(campaign_id).model_dump(mode="json")
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/launch-operations/campaigns/{campaign_id}/report")
def get_launch_report(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return LaunchReportService(db).build(campaign_id).model_dump(mode="json")
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/launch-operations/campaigns/{campaign_id}/export-runbook")
def export_launch_runbook(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return LaunchReportService(db).export_runbook(campaign_id).model_dump(mode="json")
    except LaunchOperationsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/bombar/campaigns")
def create_bombar_campaign(payload: BombarCampaignCreateRequest, db: Session = Depends(get_db)):
    try:
        return LaunchPlanner(db).create_campaign(
            payload.import_id,
            name=payload.name,
            brand=payload.brand,
            target_video_count=payload.target_video_count,
            target_destination_count=payload.target_destination_count,
            start_date=payload.start_date,
            end_date=payload.end_date,
        ).model_dump(mode="json")
    except BombarLaunchDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bombar/campaigns")
def list_bombar_campaigns(db: Session = Depends(get_db)):
    campaigns = db.scalars(
        select(models.Campaign)
        .where(models.Campaign.source_type == "bombar_matrix")
        .order_by(models.Campaign.id.desc())
    ).all()
    return [
        {
            "id": campaign.id,
            "linked_campaign_id": campaign.id,
            "name": campaign.name,
            "brand": campaign.brand,
            "status": campaign.status,
            "product_count": len(campaign.product_ids_json or []),
            "target_video_count": campaign.target_video_count,
            "target_destination_count": campaign.target_destination_count,
        }
        for campaign in campaigns
    ]


@router.get("/bombar/campaigns/{campaign_id}")
def get_bombar_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = get_or_404(db, models.Campaign, campaign_id)
    return {
        "id": campaign.id,
        "linked_campaign_id": campaign.id,
        "name": campaign.name,
        "brand": campaign.brand,
        "status": campaign.status,
        "product_ids": campaign.product_ids_json or [],
        "target_video_count": campaign.target_video_count,
        "target_destination_count": campaign.target_destination_count,
        "strategy": campaign.strategy_json or {},
    }


@router.post("/bombar/campaigns/{campaign_id}/prepare-content")
def prepare_bombar_content(
    campaign_id: int,
    payload: BombarCampaignPrepareRequest | None = None,
    db: Session = Depends(get_db),
):
    payload = payload or BombarCampaignPrepareRequest()
    try:
        return LaunchPlanner(db).prepare_content(
            campaign_id,
            platform=payload.platform,
            duration_seconds=payload.duration_seconds,
            variant_count=payload.variant_count,
        )
    except BombarLaunchDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bombar/campaigns/{campaign_id}/generate-destination-packs")
def generate_bombar_destination_packs(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return [item.model_dump(mode="json") for item in DestinationSetupPlanner(db).generate(campaign_id)]
    except BombarLaunchDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/bombar/campaigns/{campaign_id}/generate-distribution-plan")
def generate_bombar_distribution_plan(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return DistributionAllocator(db).generate_plan(campaign_id).model_dump(mode="json")
    except BombarLaunchDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bombar/campaigns/{campaign_id}/dashboard")
def get_bombar_dashboard(campaign_id: int, db: Session = Depends(get_db)):
    try:
        return LaunchDashboardService(db).dashboard(campaign_id).model_dump(mode="json")
    except BombarLaunchDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/bombar/destination-packs")
def list_bombar_destination_packs(campaign_id: int | None = None, db: Session = Depends(get_db)):
    query = select(models.DestinationSetupPack).order_by(models.DestinationSetupPack.id.desc())
    if campaign_id is not None:
        query = query.where(models.DestinationSetupPack.campaign_id == campaign_id)
    packs = db.scalars(query).all()
    return [
        {
            "id": pack.id,
            "campaign_id": pack.campaign_id,
            "product_id": pack.product_id,
            "sku": pack.sku,
            "platform": pack.platform,
            "suggested_name": pack.suggested_name,
            "suggested_handle": pack.suggested_handle,
            "status": pack.status,
            "content_pillars": pack.content_pillars_json or [],
            "first_posts": pack.first_posts_json or [],
            "setup_checklist": pack.setup_checklist_json or [],
        }
        for pack in packs
    ]


@router.patch("/bombar/destination-packs/{pack_id}")
def patch_bombar_destination_pack(
    pack_id: int,
    payload: BombarDestinationPackPatchRequest,
    db: Session = Depends(get_db),
):
    pack = get_or_404(db, models.DestinationSetupPack, pack_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pack, field, value)
    db.commit()
    db.refresh(pack)
    return {"id": pack.id, "status": pack.status, "suggested_handle": pack.suggested_handle}


@router.post("/bombar/publishing-tasks/{task_id}/mark-done")
def mark_bombar_publishing_task_done(
    task_id: int,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
):
    task = get_or_404(db, models.PublishingTask, task_id)
    task.status = "done"
    task.final_url = payload.get("final_url")
    task.raw_response_json = {**(task.raw_response_json or {}), "bombar_manual_upload": payload.get("stats", {})}
    db.commit()
    db.refresh(task)
    return {"id": task.id, "status": task.status, "final_url": task.final_url, "stats": task.raw_response_json}


@router.post("/generator/intelligence/build")
def build_generator_intelligence(payload: GeneratorProductRequest, db: Session = Depends(get_db)):
    try:
        record = CreativeIntelligenceBuilder(db).build_for_product(payload.product_id)
        return {"id": record.id, "status": record.status, "pack": record.pack_json, "warnings": record.warnings_json}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/intelligence/{intelligence_pack_id}")
def get_generator_intelligence(intelligence_pack_id: int, db: Session = Depends(get_db)):
    record = get_or_404(db, models.CreativeIntelligencePackRecord, intelligence_pack_id)
    return {"id": record.id, "status": record.status, "pack": record.pack_json, "warnings": record.warnings_json}


@router.post("/generator/script-briefs")
def create_generator_script_brief(payload: GeneratorScriptBriefRequest, db: Session = Depends(get_db)):
    try:
        brief = ScriptBriefBuilder(db).build_from_record(payload.intelligence_pack_id)
        return {"id": brief.id, "status": brief.status, "brief": brief.brief_json}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/script-briefs/{script_brief_id}")
def get_generator_script_brief(script_brief_id: int, db: Session = Depends(get_db)):
    brief = get_or_404(db, models.ScriptBrief, script_brief_id)
    return {"id": brief.id, "status": brief.status, "brief": brief.brief_json}


@router.post("/generator/scripts/generate")
def generate_generator_script(payload: GeneratorScriptRequest, db: Session = Depends(get_db)):
    try:
        script_job = GeneratorScriptService(db).generate_from_brief(payload.script_brief_id, payload.llm_provider)
        variant = sorted(script_job.variants, key=lambda item: item.variant_number)[0]
        return {
            "script_job_id": script_job.id,
            "script_variant_id": variant.id,
            "status": script_job.status,
            "llm_provider": script_job.llm_provider,
            "script": script_job.output_script_json,
        }
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/scripts/{script_job_id}")
def get_generator_script(script_job_id: int, db: Session = Depends(get_db)):
    script_job = get_or_404(db, models.ScriptJob, script_job_id)
    return {
        "script_job_id": script_job.id,
        "status": script_job.status,
        "llm_provider": script_job.llm_provider,
        "script": script_job.output_script_json,
        "validation": script_job.validation_report_json,
    }


@router.post("/generator/prompt-packs")
def create_generator_prompt_pack(payload: GeneratorPromptPackRequest, db: Session = Depends(get_db)):
    try:
        prompt_pack = PromptPackBuilder(db).build_for_script(
            payload.script_variant_id,
            payload.provider,
            payload.script_brief_id,
        )
        return {
            "id": prompt_pack.id,
            "status": prompt_pack.status,
            "prompt_pack": prompt_pack.prompt_pack_json,
            "provider_payload": prompt_pack.provider_payload_json,
        }
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/prompt-packs/{prompt_pack_id}")
def get_generator_prompt_pack(prompt_pack_id: int, db: Session = Depends(get_db)):
    prompt_pack = get_or_404(db, models.PromptPack, prompt_pack_id)
    return {
        "id": prompt_pack.id,
        "status": prompt_pack.status,
        "prompt_pack": prompt_pack.prompt_pack_json,
        "provider_payload": prompt_pack.provider_payload_json,
    }


@router.post("/generator/video-jobs")
def create_generator_video_job(payload: GeneratorVideoJobRequest, db: Session = Depends(get_db)):
    try:
        video_job = GeneratorVideoService(db).create_video_job_from_prompt_pack(
            payload.prompt_pack_id,
            payload.video_provider,
        )
        return {"id": video_job.id, "status": video_job.status, "provider": video_job.provider}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/run-real")
def run_generator_real(payload: GeneratorRealRunRequest, db: Session = Depends(get_db)):
    try:
        artifacts = GeneratorRunService(db).run_real(
            product_id=payload.product_id,
            llm_provider=payload.llm_provider,
            video_provider=payload.video_provider,
            confirm_real_spend=payload.confirm_real_spend,
            max_scenes=payload.max_scenes,
            full_video=payload.full_video,
        )
        return generator_artifacts_response(artifacts)
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/provider-key-status")
def get_generator_provider_key_status():
    return provider_key_status()


@router.post("/generator/video-jobs/{video_job_id}/run")
def run_generator_video_job(
    video_job_id: int,
    payload: GeneratorProviderRunRequest | None = None,
    db: Session = Depends(get_db),
):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        video_job = GeneratorVideoService(db).start_provider_jobs(
            video_job,
            explicit_real_run=payload.confirm_real_spend if payload else False,
        )
        return {
            "id": video_job.id,
            "status": video_job.status,
            "provider": video_job.provider,
            "provider_job_ids": [clip.provider_job_id for clip in video_job.clips if clip.provider_job_id],
        }
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/video-jobs/{video_job_id}/status")
def get_generator_video_status(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        return GeneratorVideoService(db).status(video_job)
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/video-jobs/{video_job_id}/provider-status")
def get_generator_video_provider_status(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        return GeneratorVideoService(db).provider_status(video_job)
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/video-jobs/{video_job_id}/poll")
def poll_generator_video_provider(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        return GeneratorVideoService(db).poll_until_complete(video_job)
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/video-jobs/{video_job_id}/download")
def download_generator_video_outputs(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        return {"paths": GeneratorVideoService(db).download_outputs(video_job)}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/video-jobs/{video_job_id}/assemble")
def assemble_generator_video(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        video_job = GeneratorVideoService(db).assemble(video_job)
        return {"id": video_job.id, "status": video_job.status, "output_video_path": video_job.output_video_path}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/import/{kind}")
async def import_generator_csv(kind: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if kind not in {"product_metrics", "creative_performance", "review_insights", "market_signals"}:
        raise HTTPException(status_code=404, detail="Unknown generator import type")
    text = (await file.read()).decode("utf-8-sig")
    return {"kind": kind, "imported": import_csv_text(db, kind, text)}


@router.post("/script-jobs/generate", response_model=schemas.ScriptJobRead)
def generate_script_job(payload: schemas.ScriptGenerateRequest, db: Session = Depends(get_db)):
    try:
        return ScriptEngine(db).generate(payload.product_id, payload.template_id, payload.brand_guide_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/script-jobs/{script_job_id}", response_model=schemas.ScriptJobRead)
def get_script_job(script_job_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.ScriptJob, script_job_id)


@router.post("/script-jobs/{script_job_id}/validate")
def validate_script_job(script_job_id: int, db: Session = Depends(get_db)):
    script_job = get_or_404(db, models.ScriptJob, script_job_id)
    return ScriptEngine(db).validate(script_job)


@router.post("/script-variants/{variant_id}/approve", response_model=schemas.ScriptVariantRead)
def approve_script_variant(variant_id: int, db: Session = Depends(get_db)):
    variant = get_or_404(db, models.ScriptVariant, variant_id)
    return ScriptEngine(db).approve_variant(variant)


@router.post("/script-variants/{variant_id}/reject", response_model=schemas.ScriptVariantRead)
def reject_script_variant(variant_id: int, reason: str = "Needs revision", db: Session = Depends(get_db)):
    variant = get_or_404(db, models.ScriptVariant, variant_id)
    return ScriptEngine(db).reject_variant(variant, rejection_reason=reason)


@router.post("/video-jobs", response_model=schemas.VideoJobRead)
def create_video_job(payload: schemas.VideoJobCreate, db: Session = Depends(get_db)):
    try:
        return VideoEngine(db).create_job(payload.script_variant_id, payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/video-jobs", response_model=list[schemas.VideoJobRead])
def list_video_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(models.VideoJob).order_by(models.VideoJob.created_at.desc())).all()


@router.get("/video-jobs/{video_job_id}", response_model=schemas.VideoJobRead)
def get_video_job(video_job_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.VideoJob, video_job_id)


@router.post("/video-jobs/{video_job_id}/run", response_model=schemas.VideoJobRead)
def run_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).run(video_job)


@router.post("/video-jobs/{video_job_id}/assemble", response_model=schemas.VideoJobRead)
def assemble_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).assemble(video_job)


@router.post("/video-clips/{clip_id}/regenerate", response_model=schemas.VideoClipRead)
def regenerate_video_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = get_or_404(db, models.VideoClip, clip_id)
    return VideoEngine(db).regenerate_clip(clip)


@router.post("/video-jobs/{video_job_id}/approve", response_model=schemas.VideoJobRead)
def approve_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).approve_video(video_job)


@router.post("/video-jobs/{video_job_id}/reject", response_model=schemas.VideoJobRead)
def reject_video_job(video_job_id: int, reason: str = "Needs revision", db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).reject_video(video_job, reason)


@router.post("/publishing-packages", response_model=schemas.PublishingPackageRead)
def create_publishing_package(payload: schemas.PublishingPackageCreate, db: Session = Depends(get_db)):
    try:
        return PublishingEngine(db).create_package(payload.video_job_id, payload.target_platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing-packages", response_model=list[schemas.PublishingPackageRead])
def list_publishing_packages(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingPackage).order_by(models.PublishingPackage.created_at.desc())).all()


@router.get("/publishing-packages/{package_id}", response_model=schemas.PublishingPackageRead)
def get_publishing_package(package_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingPackage, package_id)


@router.post("/publishing-packages/{package_id}/generate-metadata", response_model=schemas.PublishingPackageRead)
def generate_publishing_metadata(package_id: int, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingEngine(db).regenerate_metadata(package)


@router.post("/publishing-packages/{package_id}/approve", response_model=schemas.PublishingPackageRead)
def approve_publishing_package(package_id: int, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingEngine(db).approve(package)


@router.post("/publishing-packages/{package_id}/reject", response_model=schemas.PublishingPackageRead)
def reject_publishing_package(package_id: int, reason: str = "Needs revision", db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingEngine(db).reject(package, reason)


@router.get("/publishing-calendar", response_model=list[schemas.PublishingJobRead])
def publishing_calendar(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingJob).order_by(models.PublishingJob.scheduled_at)).all()


@router.post("/publishing-jobs/schedule", response_model=schemas.PublishingJobRead)
def schedule_publishing_job(payload: schemas.PublishingScheduleRequest, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, payload.publishing_package_id)
    account = get_or_404(db, models.PublishingAccount, payload.account_id)
    try:
        return WarmupScheduler(db).schedule(
            package,
            account,
            payload.scheduled_at,
            payload.provider,
            payload.manual_override,
            payload.operator_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing-jobs", response_model=list[schemas.PublishingJobRead])
def list_publishing_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingJob).order_by(models.PublishingJob.scheduled_at.desc())).all()


@router.get("/publishing-jobs/{job_id}", response_model=schemas.PublishingJobRead)
def get_publishing_job(job_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingJob, job_id)


@router.post("/publishing-jobs/{job_id}/run", response_model=schemas.PublishingJobRead)
def run_publishing_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).run_job(job)


@router.post("/publishing-jobs/{job_id}/mark-manual-uploaded", response_model=schemas.PublishingJobRead)
def mark_manual_uploaded(job_id: int, payload: schemas.ManualUploadRequest, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).mark_manual_uploaded(job, payload.provider_post_url, payload.operator_name)


@router.post("/publishing-jobs/{job_id}/cancel", response_model=schemas.PublishingJobRead)
def cancel_publishing_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).cancel(job)


@router.post("/publishing-jobs/{job_id}/retry", response_model=schemas.PublishingJobRead)
def retry_publishing_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).retry(job)


@router.post("/publishing-jobs/{job_id}/collect-analytics", response_model=schemas.PublishAnalyticsRead)
def collect_job_analytics(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return AnalyticsService(db).collect_for_job(job)


@router.get("/publishing-jobs/{job_id}/analytics", response_model=list[schemas.PublishAnalyticsRead])
def get_job_analytics(job_id: int, db: Session = Depends(get_db)):
    get_or_404(db, models.PublishingJob, job_id)
    return db.scalars(
        select(models.PublishAnalytics)
        .where(models.PublishAnalytics.publishing_job_id == job_id)
        .order_by(models.PublishAnalytics.collected_at.desc())
    ).all()


@router.get("/analytics/by-product/{product_id}", response_model=list[schemas.PublishAnalyticsRead])
def get_analytics_by_product(product_id: int, db: Session = Depends(get_db)):
    get_or_404(db, models.Product, product_id)
    return AnalyticsService(db).by_product(product_id)


@router.get("/analytics/by-account/{account_id}", response_model=list[schemas.PublishAnalyticsRead])
def get_analytics_by_account(account_id: int, db: Session = Depends(get_db)):
    get_or_404(db, models.PublishingAccount, account_id)
    return AnalyticsService(db).by_account(account_id)


@router.post("/exports")
def create_export(payload: schemas.ExportCreate, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, payload.video_job_id)
    export = models.ExportPackage(
        video_job_id=video_job.id,
        destination=payload.destination,
        video_file=video_job.output_video_path,
        preview_file=video_job.preview_path,
        title=video_job.script_variant.hook,
        description=video_job.script_variant.key_message,
        tags_json=[video_job.script_variant.creative_angle],
        metadata_json={"source": "qharisma_video_factory", "provider": video_job.provider},
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return {
        "id": export.id,
        "destination": export.destination,
        "video_file": export.video_file,
        "preview_file": export.preview_file,
    }


@router.post("/publishing-accounts", response_model=schemas.PublishingAccountRead)
def create_publishing_account(payload: schemas.PublishingAccountCreate, db: Session = Depends(get_db)):
    account = models.PublishingAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/publishing-accounts", response_model=list[schemas.PublishingAccountRead])
def list_publishing_accounts(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()


@router.get("/publishing-accounts/{account_id}", response_model=schemas.PublishingAccountRead)
def get_publishing_account(account_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingAccount, account_id)


@router.patch("/publishing-accounts/{account_id}", response_model=schemas.PublishingAccountRead)
def patch_publishing_account(account_id: int, payload: schemas.PublishingAccountPatch, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.post("/publishing-accounts/{account_id}/pause", response_model=schemas.PublishingAccountRead)
def pause_publishing_account(account_id: int, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    account.warmup_status = "paused"
    db.commit()
    db.refresh(account)
    return account


@router.post("/publishing-accounts/{account_id}/resume", response_model=schemas.PublishingAccountRead)
def resume_publishing_account(account_id: int, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    account.warmup_status = "warming" if account.warmup_phase != "phase_4_active_distribution" else "active"
    db.commit()
    db.refresh(account)
    return account


@router.post("/warmup-plans", response_model=schemas.WarmupPlanRead)
def create_warmup_plan(payload: schemas.WarmupPlanCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"rules"})
    plan = models.WarmupPlan(**data)
    db.add(plan)
    db.flush()
    for rule_payload in payload.rules:
        db.add(models.WarmupRule(warmup_plan_id=plan.id, **rule_payload.model_dump()))
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/warmup-plans", response_model=list[schemas.WarmupPlanRead])
def list_warmup_plans(db: Session = Depends(get_db)):
    return db.scalars(select(models.WarmupPlan).order_by(models.WarmupPlan.name)).all()


@router.get("/warmup-plans/{plan_id}", response_model=schemas.WarmupPlanRead)
def get_warmup_plan(plan_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.WarmupPlan, plan_id)


@router.post("/warmup-plans/{plan_id}/apply-to-account", response_model=schemas.WarmupPlanRead)
def apply_warmup_plan(plan_id: int, account_id: int, db: Session = Depends(get_db)):
    plan = get_or_404(db, models.WarmupPlan, plan_id)
    account = get_or_404(db, models.PublishingAccount, account_id)
    plan.account_id = account.id
    account.warmup_phase = plan.current_phase
    account.warmup_status = "warming"
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/publishing-accounts/{account_id}/warmup-status")
def get_warmup_status(account_id: int, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    plan = db.scalar(select(models.WarmupPlan).where(models.WarmupPlan.account_id == account.id))
    return {
        "account_id": account.id,
        "warmup_status": account.warmup_status,
        "warmup_phase": account.warmup_phase,
        "daily_publish_limit": account.daily_publish_limit,
        "weekly_publish_limit": account.weekly_publish_limit,
        "active_plan": plan.name if plan else None,
        "checked_at": datetime.now(UTC).isoformat(),
    }
