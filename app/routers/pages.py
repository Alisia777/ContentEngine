from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.asset_storage import ProductAssetStorage
from app.assets.errors import AssetKitError
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.assets.reference_bundle_builder import ProviderReferenceBundleBuilder
from app.blogger_brief import (
    BloggerBriefError,
    MeaningSpecBuilder,
    ProductReferencePolicyService,
    UGCAdScriptBuilder,
)
from app.blogger_brief.prompt_enricher import PromptEnricher
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
from app.campaign_batch.safety_gates import SAFE_BATCH_ACTIONS
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
from app.creative.errors import CreativeSpecError
from app.database import get_db
from app.destination_setup import DestinationProfilePackBuilder, DestinationSetupTaskService, SetupRequirementService
from app.destination_setup.errors import DestinationSetupError
from app.destination_crm import (
    DestinationCRMActionService,
    DestinationCRMCampaignCapacityService,
    DestinationHealthService,
    DestinationReadinessService,
    DestinationWarmupService,
)
from app.destination_crm.errors import DestinationCRMError
from app.destination_connectors import ConnectionRegistry, CSVMetricsImporter, DestinationConnectorSyncService, DestinationMetricsCollector
from app.destination_connectors.errors import DestinationConnectorError
from app.destination_control_tower import DestinationControlReportService, DestinationControlTowerError, TowerService
from app.demand.errors import DemandError
from app.engine import VideoFactoryEngine
from app.factory_os import FactoryAcceptanceReportService, FactoryHealthCheck, FactoryLaunchWorkflow, FactoryRunbookService
from app.factory_os.errors import FactoryOSError
from app.intelligence.csv_imports import import_csv_text
from app.intelligence.errors import IntelligenceError
from app.intelligence.generation_runner import GeneratorRunService
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.prompt_builder import PromptPackBuilder
from app.intelligence.safety import provider_key_status
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.script_generator import GeneratorScriptService
from app.intelligence.video_generator import GeneratorVideoService
from app.launch_operations import LaunchReadinessService, LaunchReportService
from app.launch_operations.errors import LaunchOperationsError
from app.metrics_intake import (
    AttributionService,
    CSVImporter,
    ClickTracker,
    FunnelService,
    MetricsIntakeError,
    MetricsSourceRegistry,
    PlatformMetricsMatrix,
    TrackingLinkService,
)
from app.participant_portal import (
    AssignmentPortalService,
    OnboardingService,
    ParticipantMetricsService,
    ParticipantPortalError,
    ParticipantService,
    PayoutService,
    RecommendationService,
    SubmissionService,
)
from app.publishing import ManualUploadProvider, PublishingDestinationService, PublishingPackageService, PublishingScheduler
from app.publishing.errors import PublishingError
from app.training_academy import CertificationService, CurriculumService, ProgressService, QuizService, ScenarioService, TrainingAcademyError
from app.training_academy.academy_catalog import BEGINNER_TRACKS, PLATFORM_PLAYBOOKS
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
from app.ui import templates

router = APIRouter(tags=["pages"])


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


@router.get("/r/{slug}")
def tracking_redirect(slug: str, request: Request, db: Session = Depends(get_db)):
    try:
        link, _ = ClickTracker(db).record(
            slug,
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
            metadata={"path": request.url.path},
        )
    except MetricsIntakeError:
        return redirect("/metrics-intake?error=tracking_link_not_found")
    return RedirectResponse(link.target_url, status_code=307)


@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, db: Session = Depends(get_db)):
    products = db.scalars(select(models.Product).order_by(models.Product.created_at.desc())).all()
    return templates.TemplateResponse(
        "products.html",
        {"request": request, "page_title": "Products", "products": products},
    )


@router.post("/products/create")
def create_product_form(
    sku: str = Form(...),
    brand: str = Form(...),
    title: str = Form(...),
    marketplace: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    product_url: str = Form(""),
    db: Session = Depends(get_db),
):
    db.add(
        models.Product(
            sku=sku,
            brand=brand,
            title=title,
            marketplace=marketplace or None,
            description=description or None,
            category=category or None,
            product_url=product_url or None,
            attributes_json={},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
    )
    db.commit()
    return redirect("/products")


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail_page(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if not product:
        return redirect("/products")
    return templates.TemplateResponse(
        "product_detail.html",
        {"request": request, "page_title": product.title, "product": product},
    )


@router.get("/scripts", response_class=HTMLResponse)
def scripts_page(request: Request, db: Session = Depends(get_db)):
    script_jobs = db.scalars(select(models.ScriptJob).order_by(models.ScriptJob.created_at.desc())).all()
    return templates.TemplateResponse(
        "scripts.html",
        {"request": request, "page_title": "Scripts", "script_jobs": script_jobs},
    )


@router.get("/scripts/new", response_class=HTMLResponse)
def script_form_page(request: Request, db: Session = Depends(get_db)):
    selected_product_id = request.query_params.get("product_id")
    products = db.scalars(select(models.Product).order_by(models.Product.title)).all()
    brand_guides = db.scalars(select(models.BrandGuide).order_by(models.BrandGuide.brand)).all()
    creative_templates = db.scalars(select(models.CreativeTemplate).order_by(models.CreativeTemplate.name)).all()
    return templates.TemplateResponse(
        "script_form.html",
        {
            "request": request,
            "page_title": "Create Script",
            "products": products,
            "brand_guides": brand_guides,
            "creative_templates": creative_templates,
            "selected_product_id": int(selected_product_id) if selected_product_id else None,
        },
    )


@router.post("/scripts/generate")
def generate_script_form(
    product_id: int = Form(...),
    template_id: int = Form(...),
    brand_guide_id: int = Form(...),
    db: Session = Depends(get_db),
):
    script_job = ScriptEngine(db).generate(product_id, template_id, brand_guide_id)
    return redirect(f"/scripts/{script_job.id}")


@router.get("/scripts/{script_job_id}", response_class=HTMLResponse)
def script_detail_page(script_job_id: int, request: Request, db: Session = Depends(get_db)):
    script_job = db.get(models.ScriptJob, script_job_id)
    if not script_job:
        return redirect("/scripts")
    return templates.TemplateResponse(
        "script_detail.html",
        {"request": request, "page_title": "Script Review", "script_job": script_job},
    )


@router.post("/script-variants/{variant_id}/approve-ui")
def approve_script_variant_ui(variant_id: int, db: Session = Depends(get_db)):
    variant = db.get(models.ScriptVariant, variant_id)
    if variant:
        ScriptEngine(db).approve_variant(variant)
        return redirect(f"/scripts/{variant.script_job_id}")
    return redirect("/scripts")


@router.post("/script-variants/{variant_id}/reject-ui")
def reject_script_variant_ui(
    variant_id: int,
    rejection_reason: str = Form("Needs revision"),
    db: Session = Depends(get_db),
):
    variant = db.get(models.ScriptVariant, variant_id)
    if variant:
        ScriptEngine(db).reject_variant(variant, rejection_reason=rejection_reason)
        return redirect(f"/scripts/{variant.script_job_id}")
    return redirect("/scripts")


@router.get("/videos", response_class=HTMLResponse)
def videos_page(request: Request, db: Session = Depends(get_db)):
    video_jobs = db.scalars(select(models.VideoJob).order_by(models.VideoJob.created_at.desc())).all()
    return templates.TemplateResponse(
        "videos.html",
        {"request": request, "page_title": "Videos", "video_jobs": video_jobs},
    )


@router.get("/videos/new", response_class=HTMLResponse)
def video_form_page(request: Request, db: Session = Depends(get_db)):
    selected_variant_id = request.query_params.get("variant_id")
    variants = db.scalars(
        select(models.ScriptVariant)
        .where(models.ScriptVariant.status == "script_approved")
        .order_by(models.ScriptVariant.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        "video_form.html",
        {
            "request": request,
            "page_title": "Video Generation",
            "variants": variants,
            "selected_variant_id": int(selected_variant_id) if selected_variant_id else None,
        },
    )


@router.post("/videos/create")
def create_video_form(
    script_variant_id: int = Form(...),
    provider: str = Form("mock"),
    db: Session = Depends(get_db),
):
    video_job = VideoEngine(db).create_job(script_variant_id, provider)
    return redirect(f"/videos/{video_job.id}")


@router.get("/videos/{video_job_id}", response_class=HTMLResponse)
def video_detail_page(video_job_id: int, request: Request, db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if not video_job:
        return redirect("/videos")
    return templates.TemplateResponse(
        "video_detail.html",
        {"request": request, "page_title": "Video Review", "video_job": video_job},
    )


@router.post("/videos/{video_job_id}/run-ui")
def run_video_ui(video_job_id: int, db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if video_job:
        VideoEngine(db).run(video_job)
    return redirect(f"/videos/{video_job_id}")


@router.post("/videos/{video_job_id}/approve-ui")
def approve_video_ui(video_job_id: int, db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if video_job:
        VideoEngine(db).approve_video(video_job)
    return redirect(f"/videos/{video_job_id}")


@router.post("/videos/{video_job_id}/reject-ui")
def reject_video_ui(video_job_id: int, reason: str = Form("Needs revision"), db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if video_job:
        VideoEngine(db).reject_video(video_job, reason)
    return redirect(f"/videos/{video_job_id}")


@router.get("/generator", response_class=HTMLResponse)
def generator_page(request: Request, db: Session = Depends(get_db)):
    products = db.scalars(select(models.Product).order_by(models.Product.title)).all()
    return templates.TemplateResponse(
        "generator.html",
        {
            "request": request,
            "page_title": "Generator",
            "products": products,
            "result": None,
            "error": None,
            "provider_status": provider_key_status(),
        },
    )


@router.post("/generator/run", response_class=HTMLResponse)
def run_generator_page(
    request: Request,
    product_id: int = Form(...),
    llm_provider: str = Form("mock"),
    video_provider: str = Form("mock"),
    action: str = Form("prompt_only"),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(models.Product).order_by(models.Product.title)).all()
    result = None
    error = None
    try:
        runner = GeneratorRunService(db)
        if action == "prompt_only":
            artifacts = runner.build_prompt_pack_only(
                product_id=product_id,
                llm_provider=llm_provider,
                video_provider=video_provider,
            )
        else:
            artifacts = runner.run_real(
                product_id=product_id,
                llm_provider=llm_provider,
                video_provider=video_provider,
                confirm_real_spend=True,
                max_scenes=1 if action == "real_smoke" else None,
                full_video=action == "full_real",
            )
        result = {
            "pack": artifacts.pack,
            "brief": artifacts.brief,
            "script_job": artifacts.script_job,
            "variant": artifacts.variant,
            "prompt_pack": artifacts.prompt_pack,
            "video_job": artifacts.video_job,
            "provider_status": artifacts.provider_status,
            "local_output_paths": artifacts.local_output_paths or [],
            "report_path": artifacts.report_path,
        }
    except IntelligenceError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "generator.html",
        {
            "request": request,
            "page_title": "Generator",
            "products": products,
            "result": result,
            "error": error,
            "provider_status": provider_key_status(),
            "selected_product_id": product_id,
            "selected_llm_provider": llm_provider,
            "selected_video_provider": video_provider,
            "action": action,
        },
    )


@router.post("/generator/import/{kind}")
async def import_generator_csv_ui(
    kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if kind in {"product_metrics", "creative_performance", "review_insights", "market_signals"}:
        text = (await file.read()).decode("utf-8-sig")
        import_csv_text(db, kind, text)
    return redirect("/generator")


@router.get("/working-video-generator", response_class=HTMLResponse)
def working_video_generator_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "working_video_generator.html",
        {
            "request": request,
            "page_title": "Working Video Generator",
            "result": None,
            "real_smoke": None,
            "error": None,
            **working_video_context(db),
        },
    )


@router.post("/working-video-generator/run", response_class=HTMLResponse)
def run_working_video_generator_page(
    request: Request,
    product_id: int = Form(0),
    platform: str = Form("Instagram Reels"),
    duration: int = Form(15),
    variant_count: int = Form(5),
    selected_variant_id: str = Form(""),
    video_provider: str = Form("runway"),
    action: str = Form("prepare"),
    db: Session = Depends(get_db),
):
    result = None
    real_smoke = None
    error = None
    try:
        runner = WorkingVideoGenerator(db)
        if action == "prepare":
            result = runner.prepare(product_id, platform, duration, variant_count).model_dump(mode="json")
        else:
            variant_id = int(selected_variant_id)
            if action == "prompt_only":
                result = runner.run_prompt_only(variant_id, provider=video_provider).model_dump(mode="json")
            elif action == "real_smoke":
                real_smoke = runner.run_real_smoke(
                    variant_id,
                    provider=video_provider,
                    allow_real_spend=True,
                    max_scenes=1,
                ).model_dump(mode="json")
                result = runner.status(variant_id).model_dump(mode="json")
    except (DemandError, CreativeSpecError, VariantError, VideoGeneratorError, IntelligenceError, ValueError) as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "working_video_generator.html",
        {
            "request": request,
            "page_title": "Working Video Generator",
            "result": result,
            "real_smoke": real_smoke,
            "error": error,
            "selected_product_id": product_id,
            "selected_platform": platform,
            "selected_duration": duration,
            "selected_variant_count": variant_count,
            "selected_variant_id": int(selected_variant_id) if selected_variant_id else None,
            "selected_video_provider": video_provider,
            **working_video_context(db),
        },
    )


def working_video_context(db: Session) -> dict:
    status = provider_key_status()
    return {
        "products": db.scalars(select(models.Product).order_by(models.Product.title)).all(),
        "selected_variants": db.scalars(
            select(models.CreativeVariant)
            .where(models.CreativeVariant.status == "selected")
            .order_by(models.CreativeVariant.created_at.desc())
            .limit(20)
        ).all(),
        "demand_hypotheses": db.scalars(
            select(models.DemandHypothesisRecord).order_by(models.DemandHypothesisRecord.created_at.desc()).limit(10)
        ).all(),
        "provider_status": status,
        "real_smoke_gate_ready": (
            status["generation_mode"] == "real"
            and status["allow_real_spend"]
            and status["runway_api_secret_configured"]
        ),
    }


@router.get("/ugc-video-strategy", response_class=HTMLResponse)
def ugc_video_strategy_page(request: Request, product_id: int | None = None, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "ugc_video_strategy.html",
        {
            "request": request,
            "page_title": "UGC Video Strategy",
            "result": ugc_video_strategy_result(db, product_id) if product_id else None,
            "error": request.query_params.get("error"),
            **ugc_video_strategy_context(db),
        },
    )


@router.post("/ugc-video-strategy/run", response_class=HTMLResponse)
def run_ugc_video_strategy_page(
    request: Request,
    product_id: int = Form(0),
    platform: str = Form("Instagram Reels"),
    duration_seconds: int = Form(8),
    creative_variant_id: str = Form(""),
    ugc_script_id: str = Form(""),
    action: str = Form("check"),
    db: Session = Depends(get_db),
):
    result = None
    error = None
    try:
        if action == "check":
            result = ugc_video_strategy_result(db, product_id)
        elif action == "build_spec":
            spec = MeaningSpecBuilder(db).build(product_id, platform=platform, duration_seconds=duration_seconds)
            result = ugc_video_strategy_result(db, product_id, meaning_spec_id=spec.id)
        elif action == "build_script":
            spec = latest_blogger_meaning_spec(db, product_id) or MeaningSpecBuilder(db).build(
                product_id,
                platform=platform,
                duration_seconds=duration_seconds,
            )
            script = UGCAdScriptBuilder(db).build(
                spec.id,
                creative_variant_id=int(creative_variant_id) if creative_variant_id else None,
                duration_seconds=duration_seconds,
            )
            result = ugc_video_strategy_result(db, product_id, meaning_spec_id=spec.id, ugc_script_id=script.id)
        elif action == "prompt_only":
            script_id = int(ugc_script_id) if ugc_script_id else (latest_ugc_script(db, product_id).id if latest_ugc_script(db, product_id) else 0)
            generation = PromptEnricher(db).build_prompt_pack_from_script(script_id, provider="runway")
            result = ugc_video_strategy_result(db, product_id, ugc_script_id=script_id)
            result["prompt_pack_id"] = generation.prompt_pack_id
            result["generation_variant_id"] = generation.id
    except (BloggerBriefError, VideoGeneratorError, IntelligenceError, ValueError) as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "ugc_video_strategy.html",
        {
            "request": request,
            "page_title": "UGC Video Strategy",
            "result": result,
            "error": error,
            "selected_product_id": product_id,
            "selected_platform": platform,
            "selected_duration_seconds": duration_seconds,
            "selected_creative_variant_id": int(creative_variant_id) if creative_variant_id else None,
            "selected_ugc_script_id": int(ugc_script_id) if ugc_script_id else None,
            **ugc_video_strategy_context(db),
        },
    )


def ugc_video_strategy_context(db: Session) -> dict:
    return {
        "products": db.scalars(select(models.Product).order_by(models.Product.title)).all(),
        "selected_variants": db.scalars(
            select(models.CreativeVariant)
            .where(models.CreativeVariant.status == "selected")
            .order_by(models.CreativeVariant.created_at.desc())
            .limit(20)
        ).all(),
        "meaning_specs": db.scalars(select(models.BloggerMeaningSpec).order_by(models.BloggerMeaningSpec.created_at.desc()).limit(20)).all(),
        "ugc_scripts": db.scalars(select(models.UGCAdScript).order_by(models.UGCAdScript.created_at.desc()).limit(20)).all(),
    }


def ugc_video_strategy_result(
    db: Session,
    product_id: int,
    *,
    meaning_spec_id: int | None = None,
    ugc_script_id: int | None = None,
) -> dict:
    product = db.get(models.Product, product_id)
    policy = ProductReferencePolicyService(db).check(product_id).model_dump(mode="json")
    readiness = ProductReferenceReadinessChecker(db).check(product_id, provider="runway").model_dump(mode="json")
    meaning_spec = db.get(models.BloggerMeaningSpec, meaning_spec_id) if meaning_spec_id else latest_blogger_meaning_spec(db, product_id)
    script = db.get(models.UGCAdScript, ugc_script_id) if ugc_script_id else latest_ugc_script(db, product_id)
    return {
        "product": product,
        "reference_policy": policy,
        "reference_readiness": readiness,
        "meaning_spec": meaning_spec,
        "ugc_script": script,
        "mass_generation_safety_status": policy.get("mass_generation_safety_status"),
        "next_actions": policy.get("next_actions") or [],
    }


def latest_blogger_meaning_spec(db: Session, product_id: int) -> models.BloggerMeaningSpec | None:
    return db.scalar(
        select(models.BloggerMeaningSpec)
        .where(models.BloggerMeaningSpec.product_id == product_id)
        .order_by(models.BloggerMeaningSpec.id.desc())
    )


def latest_ugc_script(db: Session, product_id: int) -> models.UGCAdScript | None:
    return db.scalar(
        select(models.UGCAdScript)
        .join(models.BloggerMeaningSpec)
        .where(models.BloggerMeaningSpec.product_id == product_id)
        .order_by(models.UGCAdScript.id.desc())
    )


@router.get("/content-factory", response_class=HTMLResponse)
def content_factory_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "content_factory.html",
        {
            "request": request,
            "page_title": "AI Content Factory",
            "result": None,
            "error": request.query_params.get("error"),
            **content_factory_context(db),
        },
    )


@router.post("/content-factory/run", response_class=HTMLResponse)
def run_content_factory_page(
    request: Request,
    product_id: int = Form(0),
    platform: str = Form("Instagram Reels"),
    duration: int = Form(15),
    variant_count: int = Form(5),
    content_run_id: str = Form(""),
    action: str = Form("prepare"),
    db: Session = Depends(get_db),
):
    result = None
    error = None
    try:
        orchestrator = ContentRunOrchestrator(db)
        if action == "prepare":
            result = orchestrator.prepare_content_run(product_id, platform, duration, variant_count).model_dump(mode="json")
        elif action == "prompt_only":
            result = orchestrator.run_prompt_only(int(content_run_id)).model_dump(mode="json")
        elif action == "review":
            result = orchestrator.review(int(content_run_id)).model_dump(mode="json")
    except (ContentFactoryError, DemandError, CreativeSpecError, VariantError, VideoGeneratorError, IntelligenceError, ValueError) as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "content_factory.html",
        {
            "request": request,
            "page_title": "AI Content Factory",
            "result": result,
            "error": error,
            "selected_product_id": product_id,
            "selected_platform": platform,
            "selected_duration": duration,
            "selected_variant_count": variant_count,
            "selected_content_run_id": int(content_run_id) if content_run_id else None,
            **content_factory_context(db),
        },
    )


@router.post("/content-factory/stats/import")
async def import_content_factory_stats_ui(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    text = (await file.read()).decode("utf-8-sig")
    result = ContentStatsImporter(db).import_csv_text(text)
    if result.error_count:
        return redirect(f"/content-factory?error=Imported {result.imported_count} rows with {result.error_count} errors")
    return redirect("/content-factory")


def content_factory_context(db: Session) -> dict:
    dashboard = ContentPerformanceService(db).dashboard().model_dump(mode="json")
    runs = db.scalars(select(models.ContentRun).order_by(models.ContentRun.created_at.desc()).limit(20)).all()
    return {
        "products": db.scalars(select(models.Product).order_by(models.Product.title)).all(),
        "content_runs": runs,
        "ai_reviews": db.scalars(select(models.AIContentReview).order_by(models.AIContentReview.created_at.desc()).limit(20)).all(),
        "performance_metrics": db.scalars(
            select(models.ContentPerformanceMetric).order_by(models.ContentPerformanceMetric.created_at.desc()).limit(20)
        ).all(),
        "dashboard": dashboard,
    }


@router.get("/video-generator", response_class=HTMLResponse)
def video_generator_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "video_generator.html",
        {
            "request": request,
            "page_title": "Video Generator",
            "provider_status": provider_key_status(),
            "result": None,
            "error": None,
            **video_generator_context(db),
        },
    )


@router.post("/video-generator/run", response_class=HTMLResponse)
def run_video_generator_page(
    request: Request,
    product_id: int = Form(0),
    platform: str = Form("Instagram Reels"),
    duration: int = Form(15),
    asset_kit_id: str = Form(""),
    asset_id: str = Form(""),
    asset_type: str = Form(""),
    asset_role: str = Form(""),
    asset_url: str = Form(""),
    manual_label: str = Form(""),
    review_status: str = Form(""),
    review_notes: str = Form(""),
    is_primary_reference: bool = Form(False),
    upload_file: UploadFile | None = File(None),
    creative_spec_id: str = Form(""),
    variant_set_id: str = Form(""),
    creative_variant_id: str = Form(""),
    generation_variant_id: str = Form(""),
    variant_count: int = Form(5),
    video_provider: str = Form("mock"),
    action: str = Form("build_spec"),
    scene_number: int = Form(1),
    db: Session = Depends(get_db),
):
    result = {}
    error = None
    try:
        generator = VideoGenerator(db)
        spec = None
        variant = None
        asset_kit = None
        asset = None
        readiness = None
        reference_bundle = None
        first_frame_options = None
        variant_set = None
        if action == "build_spec":
            spec = CreativeSpecBuilder(db).build_for_product(product_id, platform=platform, duration_seconds=duration)
        elif action == "build_asset_kit":
            asset_kit = AssetKitBuilder(db).build_for_product(product_id)
        elif action == "upload_asset":
            if not upload_file:
                raise ValueError("Upload file is required.")
            asset = ProductAssetStorage(db).upload_file(
                product_id,
                filename=upload_file.filename or "asset",
                content=upload_file.file.read(),
                asset_type=asset_type or None,
                manual_label=manual_label or None,
                is_primary_reference=is_primary_reference,
            )
        elif action == "attach_asset_url":
            asset = ProductAssetStorage(db).attach_url(
                product_id,
                url=asset_url,
                asset_type=asset_type or None,
                manual_label=manual_label or None,
                is_primary_reference=is_primary_reference,
            )
        elif action == "patch_asset":
            asset = ProductAssetStorage(db).update_asset(
                int(asset_id),
                asset_type=asset_type or None,
                asset_role=asset_role or None,
                is_primary_reference=is_primary_reference,
                manual_label=manual_label or None,
                review_status=review_status or None,
                review_notes=review_notes or None,
            )
        elif action == "readiness_check":
            readiness = ProductReferenceReadinessChecker(db).check(product_id, provider=video_provider)
        elif action == "reference_bundle":
            reference_bundle = ProviderReferenceBundleBuilder(db).build(product_id, provider=video_provider)
        else:
            spec_id = int(creative_spec_id) if creative_spec_id else None
            kit_id = int(asset_kit_id) if asset_kit_id else None
            set_id = int(variant_set_id) if variant_set_id else None
            source_creative_variant_id = int(creative_variant_id) if creative_variant_id else None
            variant_id = int(generation_variant_id) if generation_variant_id else None
            if not spec_id and variant_id:
                variant = db.get(models.VideoGenerationVariant, variant_id)
                spec_id = variant.creative_spec_id if variant else None
            if action == "build_first_frames":
                first_frame_options = FirstFrameBuilder(db).build_options(spec_id, asset_kit_id=kit_id)
            elif action == "build_variants":
                variant_set = CreativeVariantBuilder(db).build_set(spec_id, asset_kit_id=kit_id, count=variant_count)
            elif action == "score_variant_set":
                variant_set = VariantScorer(db).score_set(set_id)
            elif action == "select_best_variant":
                variant_set = VariantSelector(db).select_best(set_id)
            elif action == "build_prompts_from_variant":
                variant = generator.build_prompt_pack_from_variant(source_creative_variant_id, provider=video_provider)
            elif action == "build_prompts":
                variant = generator.build_prompt_pack_from_spec(spec_id, provider=video_provider)
            elif action == "real_smoke_from_variant":
                if source_creative_variant_id is None:
                    raise ValueError("Creative Variant is required for selected-variant real smoke.")
                result["real_smoke"] = RealSmokeRunner(db).run_from_variant(
                    source_creative_variant_id,
                    provider=video_provider,
                    max_scenes=1,
                    full_video=False,
                    allow_real_spend=True,
                ).model_dump(mode="json")
            elif action == "real_smoke":
                if variant_id is None:
                    variant_id = generator.build_prompt_pack_from_spec(spec_id, provider=video_provider).id
                variant = generator.start_generation(
                    variant_id,
                    provider=video_provider,
                    confirm_real_spend=True,
                    max_scenes=1,
                    full_video=False,
                )
            elif action == "poll":
                result["provider_status"] = generator.poll(variant_id)
                variant = db.get(models.VideoGenerationVariant, variant_id)
            elif action == "download":
                variant = generator.download(variant_id)
            elif action == "assemble":
                variant = generator.assemble(variant_id)
            elif action == "score":
                result["quality_review"] = generator.score(variant_id)
                variant = db.get(models.VideoGenerationVariant, variant_id)
            elif action == "regenerate_scene":
                result["regenerated_scene"] = generator.regenerate_scene(variant_id, scene_number)
                variant = db.get(models.VideoGenerationVariant, variant_id)
            spec = db.get(models.VideoCreativeSpecRecord, spec_id) if spec_id else spec
            asset_kit = db.get(models.ProductAssetKit, kit_id) if kit_id else asset_kit
        result["spec"] = spec
        result["variant"] = variant
        result["asset_kit"] = asset_kit
        result["asset"] = asset
        result["readiness"] = readiness.model_dump(mode="json") if readiness else None
        result["reference_bundle"] = reference_bundle
        result["first_frame_options"] = first_frame_options
        result["variant_set"] = variant_set
    except (AssetKitError, CreativeSpecError, VariantError, VideoGeneratorError, IntelligenceError, ValueError) as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "video_generator.html",
        {
            "request": request,
            "page_title": "Video Generator",
            "provider_status": provider_key_status(),
            "result": result,
            "error": error,
            "selected_product_id": product_id,
            "selected_platform": platform,
            "selected_duration": duration,
            "selected_video_provider": video_provider,
            "selected_asset_kit_id": int(asset_kit_id) if asset_kit_id else None,
            "selected_asset_id": int(asset_id) if asset_id else None,
            "selected_variant_set_id": int(variant_set_id) if variant_set_id else None,
            "selected_creative_variant_id": int(creative_variant_id) if creative_variant_id else None,
            **video_generator_context(db),
        },
    )


def video_generator_context(db: Session) -> dict:
    creative_variants = db.scalars(select(models.CreativeVariant).order_by(models.CreativeVariant.created_at.desc()).limit(20)).all()
    provider_status = provider_key_status()
    eligible_variant_ids = []
    for creative_variant in creative_variants:
        variant_set = creative_variant.variant_set
        asset_kit = variant_set.asset_kit if variant_set else None
        selected = creative_variant.status == "selected" or (variant_set and variant_set.selected_variant_id == creative_variant.id)
        if selected and asset_kit and asset_kit.real_generation_allowed:
            eligible_variant_ids.append(creative_variant.id)
    real_smoke_spend_gate_enabled = (
        provider_status["generation_mode"] == "real"
        and provider_status["allow_real_spend"]
        and provider_status["runway_api_secret_configured"]
    )
    return {
        "products": db.scalars(select(models.Product).order_by(models.Product.title)).all(),
        "specs": db.scalars(select(models.VideoCreativeSpecRecord).order_by(models.VideoCreativeSpecRecord.created_at.desc()).limit(10)).all(),
        "asset_kits": db.scalars(select(models.ProductAssetKit).order_by(models.ProductAssetKit.created_at.desc()).limit(10)).all(),
        "first_frames": db.scalars(select(models.FirstFrameOption).order_by(models.FirstFrameOption.created_at.desc()).limit(10)).all(),
        "variant_sets": db.scalars(select(models.CreativeVariantSet).order_by(models.CreativeVariantSet.created_at.desc()).limit(10)).all(),
        "creative_variants": creative_variants,
        "variants": db.scalars(select(models.VideoGenerationVariant).order_by(models.VideoGenerationVariant.created_at.desc()).limit(10)).all(),
        "product_assets": db.scalars(select(models.ProductAsset).order_by(models.ProductAsset.created_at.desc()).limit(20)).all(),
        "reference_bundles": db.scalars(select(models.ProductReferenceBundle).order_by(models.ProductReferenceBundle.created_at.desc()).limit(10)).all(),
        "real_smoke_eligible_variant_ids": eligible_variant_ids,
        "real_smoke_spend_gate_enabled": real_smoke_spend_gate_enabled,
        "real_smoke_ui_enabled": real_smoke_spend_gate_enabled and bool(eligible_variant_ids),
    }


@router.get("/publishing", response_class=HTMLResponse)
def publishing_page(request: Request, db: Session = Depends(get_db)):
    default_time = (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).replace(microsecond=0).isoformat(
        timespec="minutes"
    )
    return templates.TemplateResponse(
        "publishing.html",
        {
            "request": request,
            "page_title": "Publishing",
            "error": request.query_params.get("error"),
            "default_time": default_time,
            "destinations": db.scalars(select(models.PublishingDestination).order_by(models.PublishingDestination.platform)).all(),
            "packages": db.scalars(select(models.PublishingPackage).order_by(models.PublishingPackage.created_at.desc())).all(),
            "tasks": db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.scheduled_at.desc())).all(),
            "video_jobs": db.scalars(
                select(models.VideoJob)
                .where(models.VideoJob.output_video_path.is_not(None))
                .order_by(models.VideoJob.created_at.desc())
                .limit(20)
            ).all(),
        },
    )


@router.post("/publishing/destinations/create")
def create_publishing_destination_ui(
    brand: str = Form("Altea"),
    platform: str = Form(...),
    name: str = Form(...),
    handle: str = Form(""),
    url: str = Form(""),
    owner_name: str = Form(""),
    posting_mode: str = Form("manual"),
    daily_limit: int = Form(1),
    weekly_limit: int = Form(3),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        PublishingDestinationService(db).create(
            brand=brand,
            platform=platform,
            name=name,
            handle=handle or None,
            url=url or None,
            owner_name=owner_name or None,
            posting_mode=posting_mode,
            daily_limit=daily_limit,
            weekly_limit=weekly_limit,
            notes=notes or None,
        )
    except PublishingError as exc:
        return redirect(f"/publishing?error={str(exc)}")
    return redirect("/publishing")


@router.post("/publishing/destinations/import")
async def import_publishing_destinations_ui(
    file: UploadFile = File(...),
    default_brand: str = Form("Altea"),
    db: Session = Depends(get_db),
):
    text = (await file.read()).decode("utf-8-sig")
    result = PublishingDestinationService(db).import_csv_text(text, default_brand=default_brand)
    if result["error_count"]:
        return redirect(f"/publishing?error=Imported {result['created_count']} destinations with {result['error_count']} errors")
    return redirect("/publishing")


@router.post("/publishing/packages/create")
def create_safe_publishing_package_ui(
    video_job_id: int = Form(...),
    platform: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    hashtags: str = Form(""),
    cta: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        PublishingPackageService(db).create_from_video(
            video_job_id=video_job_id,
            platform=platform,
            title=title or None,
            description=description or None,
            hashtags=[item.strip() for item in hashtags.split() if item.strip()] or None,
            cta=cta or None,
        )
    except PublishingError as exc:
        return redirect(f"/publishing?error={str(exc)}")
    return redirect("/publishing")


@router.post("/publishing/packages/{package_id}/approve")
def approve_safe_publishing_package_ui(
    package_id: int,
    reviewer_name: str = Form("operator"),
    manual_override: bool = Form(False),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    package = db.get(models.PublishingPackage, package_id)
    if not package:
        return redirect("/publishing")
    try:
        PublishingPackageService(db).approve(
            package,
            reviewer_name=reviewer_name,
            manual_override=manual_override,
            notes=notes or None,
        )
    except PublishingError as exc:
        return redirect(f"/publishing?error={str(exc)}")
    return redirect("/publishing")


@router.post("/publishing/tasks/schedule")
def schedule_safe_publishing_task_ui(
    publishing_package_id: int = Form(...),
    destination_id: int = Form(...),
    scheduled_at: str = Form(...),
    operator_name: str = Form(""),
    db: Session = Depends(get_db),
):
    package = db.get(models.PublishingPackage, publishing_package_id)
    destination = db.get(models.PublishingDestination, destination_id)
    if not package or not destination:
        return redirect("/publishing")
    try:
        PublishingScheduler(db).schedule(
            package=package,
            destination=destination,
            scheduled_at=datetime.fromisoformat(scheduled_at),
            operator_name=operator_name or None,
        )
    except PublishingError as exc:
        return redirect(f"/publishing?error={str(exc)}")
    return redirect("/publishing")


@router.post("/publishing/tasks/bulk-schedule")
def bulk_schedule_safe_publishing_tasks_ui(
    publishing_package_ids: str = Form(...),
    destination_ids: str = Form(...),
    start_at: str = Form(...),
    interval_minutes: int = Form(60),
    operator_name: str = Form(""),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    try:
        result = PublishingScheduler(db).bulk_schedule(
            package_ids=_parse_int_list(publishing_package_ids),
            destination_ids=_parse_int_list(destination_ids),
            start_at=datetime.fromisoformat(start_at),
            interval_minutes=interval_minutes,
            operator_name=operator_name or None,
            dry_run=dry_run,
        )
        if result["error_count"]:
            return redirect(
                f"/publishing?error=Bulk schedule planned {result['planned_count']} tasks with {result['error_count']} blocked items"
            )
    except (PublishingError, ValueError) as exc:
        return redirect(f"/publishing?error={str(exc)}")
    return redirect("/publishing")


@router.get("/publishing/tasks/{task_id}", response_class=HTMLResponse)
def safe_publishing_task_page(task_id: int, request: Request, db: Session = Depends(get_db)):
    task = db.get(models.PublishingTask, task_id)
    if not task:
        return redirect("/publishing")
    tracking_link = db.scalar(
        select(models.TrackingLink)
        .where(models.TrackingLink.publishing_task_id == task.id)
        .order_by(models.TrackingLink.id.desc())
    )
    warnings = []
    if not task.final_url:
        warnings.append("final_url_missing")
    if not tracking_link:
        warnings.append("tracking_link_missing")
    return templates.TemplateResponse(
        "publishing_task.html",
        {
            "request": request,
            "page_title": "Publishing Task",
            "task": task,
            "tracking_link": tracking_link,
            "warnings": warnings,
            "error": request.query_params.get("error"),
        },
    )


@router.post("/publishing/tasks/{task_id}/run")
def run_safe_publishing_task_ui(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.PublishingTask, task_id)
    if task:
        ManualUploadProvider(db).run(task)
    return redirect(f"/publishing/tasks/{task_id}")


@router.post("/publishing/tasks/{task_id}/mark-manual-uploaded")
def mark_safe_publishing_task_uploaded_ui(
    task_id: int,
    final_url: str = Form(...),
    operator_name: str = Form("operator"),
    db: Session = Depends(get_db),
):
    task = db.get(models.PublishingTask, task_id)
    if task:
        try:
            ManualUploadProvider(db).mark_published(task, final_url, operator_name)
        except PublishingError as exc:
            return redirect(f"/publishing/tasks/{task_id}?error={exc}")
    return redirect(f"/publishing/tasks/{task_id}")


def _parse_int_list(value: str) -> list[int]:
    normalized = value.replace("\n", ",").replace(";", ",").replace(" ", ",")
    return [int(item) for item in normalized.split(",") if item.strip()]


@router.get("/engine", response_class=HTMLResponse)
def engine_page(request: Request, db: Session = Depends(get_db)):
    products = db.scalars(select(models.Product).order_by(models.Product.title)).all()
    accounts = db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()
    return templates.TemplateResponse(
        "engine.html",
        {
            "request": request,
            "page_title": "Engine",
            "products": products,
            "accounts": accounts,
            "result": None,
        },
    )


@router.post("/engine/run", response_class=HTMLResponse)
def run_engine_page(
    request: Request,
    product_id: int = Form(...),
    account_id: str = Form(""),
    db: Session = Depends(get_db),
):
    selected_account_id = int(account_id) if account_id else None
    result = VideoFactoryEngine(db).run_full_demo(product_id, selected_account_id)
    products = db.scalars(select(models.Product).order_by(models.Product.title)).all()
    accounts = db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()
    return templates.TemplateResponse(
        "engine.html",
        {
            "request": request,
            "page_title": "Engine",
            "products": products,
            "accounts": accounts,
            "result": result,
            "selected_product_id": product_id,
            "selected_account_id": selected_account_id,
        },
    )


@router.get("/publishing-packages", response_class=HTMLResponse)
def publishing_packages_page(request: Request, db: Session = Depends(get_db)):
    packages = db.scalars(select(models.PublishingPackage).order_by(models.PublishingPackage.created_at.desc())).all()
    return templates.TemplateResponse(
        "publishing_packages.html",
        {"request": request, "page_title": "Publishing Packages", "packages": packages},
    )


@router.get("/publishing-packages/new", response_class=HTMLResponse)
def publishing_package_form_page(request: Request, db: Session = Depends(get_db)):
    selected_video_job_id = request.query_params.get("video_job_id")
    video_jobs = db.scalars(
        select(models.VideoJob)
        .where(models.VideoJob.status == "video_approved")
        .order_by(models.VideoJob.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        "publishing_package_form.html",
        {
            "request": request,
            "page_title": "Create Publishing Package",
            "video_jobs": video_jobs,
            "selected_video_job_id": int(selected_video_job_id) if selected_video_job_id else None,
        },
    )


@router.post("/publishing-packages/create")
def create_publishing_package_form(
    video_job_id: int = Form(...),
    target_platform: str = Form(...),
    db: Session = Depends(get_db),
):
    package = PublishingEngine(db).create_package(video_job_id, target_platform)
    return redirect(f"/publishing-packages/{package.id}")


@router.get("/publishing-packages/{package_id}", response_class=HTMLResponse)
def publishing_package_detail_page(package_id: int, request: Request, db: Session = Depends(get_db)):
    package = db.get(models.PublishingPackage, package_id)
    if not package:
        return redirect("/publishing-packages")
    accounts = db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()
    default_time = (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).replace(microsecond=0).isoformat(
        timespec="minutes"
    )
    return templates.TemplateResponse(
        "publishing_package_detail.html",
        {
            "request": request,
            "page_title": "Publishing Package",
            "package": package,
            "accounts": accounts,
            "default_time": default_time,
        },
    )


@router.post("/publishing-packages/{package_id}/approve-ui")
def approve_publishing_package_ui(package_id: int, db: Session = Depends(get_db)):
    package = db.get(models.PublishingPackage, package_id)
    if package:
        PublishingEngine(db).approve(package)
    return redirect(f"/publishing-packages/{package_id}")


@router.post("/publishing-packages/{package_id}/reject-ui")
def reject_publishing_package_ui(
    package_id: int,
    reason: str = Form("Needs revision"),
    db: Session = Depends(get_db),
):
    package = db.get(models.PublishingPackage, package_id)
    if package:
        PublishingEngine(db).reject(package, reason)
    return redirect(f"/publishing-packages/{package_id}")


@router.post("/publishing-jobs/schedule-ui")
def schedule_publishing_job_ui(
    publishing_package_id: int = Form(...),
    account_id: int = Form(...),
    scheduled_at: str = Form(...),
    provider: str = Form("mock"),
    manual_override: bool = Form(False),
    db: Session = Depends(get_db),
):
    package = db.get(models.PublishingPackage, publishing_package_id)
    account = db.get(models.PublishingAccount, account_id)
    if not package or not account:
        return redirect("/publishing-calendar")
    try:
        job = WarmupScheduler(db).schedule(
            package,
            account,
            datetime.fromisoformat(scheduled_at),
            provider,
            manual_override,
            "admin" if manual_override else None,
        )
        return redirect(f"/publishing-jobs/{job.id}")
    except ValueError:
        return redirect(f"/publishing-packages/{publishing_package_id}")


@router.get("/publishing-calendar", response_class=HTMLResponse)
def publishing_calendar_page(request: Request, db: Session = Depends(get_db)):
    jobs = db.scalars(select(models.PublishingJob).order_by(models.PublishingJob.scheduled_at)).all()
    return templates.TemplateResponse(
        "publishing_calendar.html",
        {"request": request, "page_title": "Publishing Calendar", "jobs": jobs},
    )


@router.get("/publishing-jobs/{job_id}", response_class=HTMLResponse)
def publishing_job_detail_page(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if not job:
        return redirect("/publishing-calendar")
    return templates.TemplateResponse(
        "publishing_job_detail.html",
        {"request": request, "page_title": "Publishing Job", "job": job},
    )


@router.post("/publishing-jobs/{job_id}/run-ui")
def run_publishing_job_ui(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if job:
        UploadService(db).run_job(job)
    return redirect(f"/publishing-jobs/{job_id}")


@router.post("/publishing-jobs/{job_id}/collect-analytics-ui")
def collect_analytics_ui(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if job:
        AnalyticsService(db).collect_for_job(job)
    return redirect(f"/publishing-jobs/{job_id}")


@router.get("/manual-upload/{job_id}", response_class=HTMLResponse)
def manual_upload_page(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if not job:
        return redirect("/publishing-calendar")
    return templates.TemplateResponse(
        "manual_upload.html",
        {"request": request, "page_title": "Manual Upload", "job": job},
    )


@router.post("/manual-upload/{job_id}/complete")
def complete_manual_upload(
    job_id: int,
    provider_post_url: str = Form(...),
    operator_name: str = Form("operator"),
    db: Session = Depends(get_db),
):
    job = db.get(models.PublishingJob, job_id)
    if job:
        UploadService(db).mark_manual_uploaded(job, provider_post_url, operator_name)
    return redirect(f"/publishing-jobs/{job_id}")


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    analytics = db.scalars(select(models.PublishAnalytics).order_by(models.PublishAnalytics.collected_at.desc())).all()
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request, "page_title": "Analytics", "analytics": analytics},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    brand_guides = db.scalars(select(models.BrandGuide).order_by(models.BrandGuide.brand)).all()
    templates_ = db.scalars(select(models.CreativeTemplate).order_by(models.CreativeTemplate.name)).all()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page_title": "Settings",
            "brand_guides": brand_guides,
            "creative_templates": templates_,
        },
    )


@router.get("/publishing-accounts", response_class=HTMLResponse)
def accounts_page(request: Request, db: Session = Depends(get_db)):
    accounts = db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()
    return templates.TemplateResponse(
        "accounts.html",
        {"request": request, "page_title": "Publishing Accounts", "accounts": accounts},
    )


@router.get("/warmup-plans", response_class=HTMLResponse)
def warmup_plans_page(request: Request, db: Session = Depends(get_db)):
    plans = db.scalars(select(models.WarmupPlan).order_by(models.WarmupPlan.name)).all()
    return templates.TemplateResponse(
        "warmup_plans.html",
        {"request": request, "page_title": "Warm-up Plans", "plans": plans},
    )


@router.get("/campaign-autopilot", response_class=HTMLResponse)
def campaign_autopilot_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    imports = db.scalars(select(models.ProductMatrixImport).order_by(models.ProductMatrixImport.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    matrix_rows = []
    campaign_products = []
    state = None
    report = None
    distribution_plan = None
    if selected_campaign:
        source_import_id = (selected_campaign.strategy_json or {}).get("source_import_id")
        if source_import_id:
            matrix_rows = db.scalars(
                select(models.ProductMatrixRow)
                .where(models.ProductMatrixRow.import_id == source_import_id)
                .order_by(models.ProductMatrixRow.id)
            ).all()
        campaign_products = db.scalars(
            select(models.CampaignProduct)
            .where(models.CampaignProduct.campaign_id == selected_campaign.id)
            .order_by(models.CampaignProduct.id)
        ).all()
        try:
            runner = CampaignRunner(db)
            state = runner.inspect_campaign(selected_campaign.id)
            report = runner.generate_campaign_report(selected_campaign.id)
            distribution_plan = CampaignDistributionPlanner(db).latest_plan(selected_campaign.id)
        except CampaignAutopilotDataError:
            state = None
    return templates.TemplateResponse(
        "campaign_autopilot.html",
        {
            "request": request,
            "page_title": "Campaign Autopilot",
            "campaigns": campaigns,
            "imports": imports,
            "selected_campaign": selected_campaign,
            "matrix_rows": matrix_rows,
            "campaign_products": campaign_products,
            "state": state,
            "report": report,
            "distribution_plan": distribution_plan,
        },
    )


@router.get("/bombar-launch", response_class=HTMLResponse)
def bombar_launch_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(
        select(models.Campaign)
        .where(models.Campaign.source_type == "bombar_matrix")
        .order_by(models.Campaign.id.desc())
    ).all()
    imports = db.scalars(select(models.ProductMatrixImport).order_by(models.ProductMatrixImport.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    rows = []
    dashboard = None
    destination_packs = []
    distribution_plans = []
    publishing_tasks = []
    if selected_campaign:
        source_import_id = (selected_campaign.strategy_json or {}).get("source_import_id")
        if source_import_id:
            rows = db.scalars(
                select(models.ProductMatrixRow)
                .where(models.ProductMatrixRow.import_id == source_import_id)
                .order_by(models.ProductMatrixRow.id)
            ).all()
        try:
            dashboard = LaunchDashboardService(db).dashboard(selected_campaign.id)
        except BombarLaunchDataError:
            dashboard = None
        destination_packs = db.scalars(
            select(models.DestinationSetupPack)
            .where(models.DestinationSetupPack.campaign_id == selected_campaign.id)
            .order_by(models.DestinationSetupPack.id)
        ).all()
        distribution_plans = db.scalars(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == selected_campaign.id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        ).all()
        latest_plan = distribution_plans[0] if distribution_plans else None
        if latest_plan:
            destination_ids = latest_plan.destination_ids_json or []
            package_ids = latest_plan.publishing_package_ids_json or []
            if destination_ids and package_ids:
                publishing_tasks = db.scalars(
                    select(models.PublishingTask)
                    .where(
                        models.PublishingTask.destination_id.in_(destination_ids),
                        models.PublishingTask.publishing_package_id.in_(package_ids),
                    )
                    .order_by(models.PublishingTask.id.desc())
                ).all()
    return templates.TemplateResponse(
        "bombar_launch.html",
        {
            "request": request,
            "page_title": "Bombar Launch Autopilot",
            "campaigns": campaigns,
            "imports": imports,
            "selected_campaign": selected_campaign,
            "rows": rows,
            "dashboard": dashboard,
            "destination_packs": destination_packs,
            "distribution_plans": distribution_plans,
            "publishing_tasks": publishing_tasks,
        },
    )


@router.get("/bombar-production-dry-run", response_class=HTMLResponse)
def bombar_production_dry_run_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(
        select(models.Campaign)
        .where(models.Campaign.source_type == "bombar_production_dry_run")
        .order_by(models.Campaign.id.desc())
    ).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    report = None
    if selected_campaign:
        try:
            report = BombarProductionDryRunService(db).build_report(selected_campaign.id)
        except BombarProductionError:
            report = None
    return templates.TemplateResponse(
        "bombar_production_dry_run.html",
        {
            "request": request,
            "page_title": "Bombar Production Dry Run",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "report": report,
        },
    )


@router.post("/bombar-production-dry-run")
def bombar_production_dry_run_submit(
    matrix_path: str = Form("sample_data/bombar_matrix.csv"),
    campaign_name: str = Form("Bombar Production Dry Run"),
    target_videos: int = Form(350),
    target_destinations: int = Form(120),
    reports_dir: str = Form("reports"),
    db: Session = Depends(get_db),
):
    result = BombarProductionDryRunService(db, reports_dir=reports_dir).run(
        matrix_path,
        target_videos=target_videos,
        target_destinations=target_destinations,
        campaign_name=campaign_name,
    )
    return redirect(f"/bombar-production-dry-run?campaign_id={result.campaign_id}")


@router.get("/launch-operations", response_class=HTMLResponse)
def launch_operations_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    report = None
    if selected_campaign:
        try:
            report = LaunchReportService(db).build(selected_campaign.id)
        except LaunchOperationsError:
            report = None
    return templates.TemplateResponse(
        "launch_operations.html",
        {
            "request": request,
            "page_title": "Launch Operations",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "report": report,
        },
    )


@router.post("/launch-operations/{campaign_id}/refresh")
def launch_operations_refresh(campaign_id: int, db: Session = Depends(get_db)):
    LaunchReadinessService(db).refresh(campaign_id)
    return redirect(f"/launch-operations?campaign_id={campaign_id}")


@router.post("/launch-operations/{campaign_id}/export-runbook")
def launch_operations_export_runbook(campaign_id: int, db: Session = Depends(get_db)):
    LaunchReportService(db).export_runbook(campaign_id)
    return redirect(f"/launch-operations?campaign_id={campaign_id}")


@router.get("/destination-setup", response_class=HTMLResponse)
def destination_setup_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    requirements = []
    profile_packs = []
    tasks = []
    error = request.query_params.get("error")
    if selected_campaign:
        try:
            requirements = SetupRequirementService(db).list(selected_campaign.id)
            profile_packs = DestinationProfilePackBuilder(db).list(selected_campaign.id)
            tasks = DestinationSetupTaskService(db).list(campaign_id=selected_campaign.id)
        except DestinationSetupError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        "destination_setup.html",
        {
            "request": request,
            "page_title": "Destination Setup Factory",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "requirements": requirements,
            "profile_packs": profile_packs,
            "tasks": tasks,
            "error": error,
        },
    )


@router.post("/destination-setup/{campaign_id}/requirements")
def destination_setup_requirements_ui(
    campaign_id: int,
    platform: str = Form("Instagram Reels"),
    db: Session = Depends(get_db),
):
    try:
        SetupRequirementService(db).refresh(campaign_id, platform=platform)
    except DestinationSetupError as exc:
        return redirect(f"/destination-setup?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-setup?campaign_id={campaign_id}")


@router.post("/destination-setup/{campaign_id}/profile-packs")
def destination_setup_profile_packs_ui(campaign_id: int, db: Session = Depends(get_db)):
    try:
        if not SetupRequirementService(db).list(campaign_id):
            SetupRequirementService(db).refresh(campaign_id)
        DestinationProfilePackBuilder(db).generate_for_campaign(campaign_id)
    except DestinationSetupError as exc:
        return redirect(f"/destination-setup?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-setup?campaign_id={campaign_id}")


@router.post("/destination-setup/{campaign_id}/tasks")
def destination_setup_tasks_ui(
    campaign_id: int,
    owner_name: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        DestinationSetupTaskService(db).create_tasks_for_campaign(campaign_id, owner_name=owner_name or None)
    except DestinationSetupError as exc:
        return redirect(f"/destination-setup?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-setup?campaign_id={campaign_id}")


@router.post("/destination-setup/profile-packs/{profile_pack_id}/create-task")
def destination_setup_profile_pack_task_ui(profile_pack_id: int, db: Session = Depends(get_db)):
    try:
        task = DestinationSetupTaskService(db).create_task(profile_pack_id)
    except DestinationSetupError as exc:
        return redirect(f"/destination-setup?error={exc}")
    return redirect(f"/destination-setup?campaign_id={task.campaign_id}")


@router.post("/destination-setup/tasks/{task_id}/complete")
def destination_setup_complete_task_ui(
    task_id: int,
    campaign_id: int = Form(...),
    final_account_url: str = Form(""),
    final_handle: str = Form(""),
    owner_name: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        DestinationSetupTaskService(db).mark_complete(
            task_id,
            url=final_account_url or None,
            handle=final_handle or None,
            owner_name=owner_name or None,
            notes=notes or None,
        )
    except DestinationSetupError as exc:
        return redirect(f"/destination-setup?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-setup?campaign_id={campaign_id}")


@router.post("/destination-setup/tasks/{task_id}/create-destination")
def destination_setup_create_destination_ui(
    task_id: int,
    campaign_id: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        DestinationSetupTaskService(db).create_destination(task_id)
    except DestinationSetupError as exc:
        return redirect(f"/destination-setup?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-setup?campaign_id={campaign_id}")


@router.get("/destination-crm", response_class=HTMLResponse)
def destination_crm_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    overview = {"total": 0, "active": 0, "ready": 0, "manual_ready": 0, "api_ready": 0, "paused": 0, "blocked": 0}
    readiness = []
    capacity = None
    health = []
    actions = []
    error = request.query_params.get("error")
    try:
        overview = DestinationCRMActionService(db).overview()
        readiness = DestinationReadinessService(db).list_latest(campaign_id=selected_campaign.id if selected_campaign else None)
        if selected_campaign:
            capacity = DestinationCRMCampaignCapacityService(db).calculate(selected_campaign.id)
            health = DestinationHealthService(db).refresh_campaign(selected_campaign.id)
            actions = DestinationCRMActionService(db).list_actions(campaign_id=selected_campaign.id)
    except DestinationCRMError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "destination_crm.html",
        {
            "request": request,
            "page_title": "Destination Readiness CRM",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "overview": overview,
            "readiness": readiness,
            "capacity": capacity,
            "health": health,
            "actions": actions,
            "error": error,
        },
    )


@router.post("/destination-crm/destinations/{destination_id}/refresh")
def destination_crm_refresh_ui(destination_id: int, campaign_id: int | None = Form(None), db: Session = Depends(get_db)):
    try:
        DestinationReadinessService(db).refresh(destination_id, campaign_id=campaign_id)
    except DestinationCRMError as exc:
        return redirect(f"/destination-crm?error={exc}")
    return redirect(f"/destination-crm?campaign_id={campaign_id}" if campaign_id else "/destination-crm")


@router.post("/destination-crm/destinations/{destination_id}/warmup")
def destination_crm_warmup_ui(
    destination_id: int,
    campaign_id: int | None = Form(None),
    current_phase: str = Form("phase_1_soft_start"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        DestinationWarmupService(db).create_or_update(destination_id, current_phase=current_phase, notes=notes or None)
        DestinationReadinessService(db).refresh(destination_id, campaign_id=campaign_id)
    except DestinationCRMError as exc:
        return redirect(f"/destination-crm?error={exc}")
    return redirect(f"/destination-crm?campaign_id={campaign_id}" if campaign_id else "/destination-crm")


@router.get("/destination-connectors", response_class=HTMLResponse)
def destination_connectors_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    destinations = db.scalars(select(models.PublishingDestination).order_by(models.PublishingDestination.platform, models.PublishingDestination.id)).all()
    registry = ConnectionRegistry(db)
    metrics_service = DestinationMetricsCollector(db)
    overview = registry.overview()
    connections = [registry.view(connection) for connection in registry.list()]
    syncs = db.scalars(select(models.DestinationMetricSync).order_by(models.DestinationMetricSync.id.desc()).limit(10)).all()
    metrics = db.scalars(select(models.DestinationPostMetric).order_by(models.DestinationPostMetric.id.desc()).limit(20)).all()
    summary = metrics_service.campaign_summary(selected_campaign.id) if selected_campaign else None
    return templates.TemplateResponse(
        "destination_connectors.html",
        {
            "request": request,
            "page_title": "Destination Connectors",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "destinations": destinations,
            "overview": overview,
            "connections": connections,
            "syncs": syncs,
            "metrics": metrics,
            "summary": summary,
            "error": request.query_params.get("error"),
            "notice": request.query_params.get("notice"),
        },
    )


@router.post("/destination-connectors/connections")
def destination_connectors_create_ui(
    destination_id: int = Form(...),
    connection_type: str = Form("manual"),
    credential_ref: str = Form(""),
    campaign_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        ConnectionRegistry(db).create(destination_id, connection_type, credential_ref=credential_ref or None)
    except DestinationConnectorError as exc:
        return redirect(f"/destination-connectors?error={exc}")
    return redirect(f"/destination-connectors?campaign_id={campaign_id}" if campaign_id else "/destination-connectors")


@router.post("/destination-connectors/connections/{connection_id}/check")
def destination_connectors_check_ui(connection_id: int, campaign_id: int | None = Form(None), db: Session = Depends(get_db)):
    try:
        ConnectionRegistry(db).check(connection_id)
    except DestinationConnectorError as exc:
        return redirect(f"/destination-connectors?error={exc}")
    return redirect(f"/destination-connectors?campaign_id={campaign_id}" if campaign_id else "/destination-connectors")


@router.post("/destination-connectors/connections/{connection_id}/sync")
def destination_connectors_sync_ui(
    connection_id: int,
    campaign_id: int | None = Form(None),
    period_start: str = Form(""),
    period_end: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        result = DestinationConnectorSyncService(db).sync(
            connection_id,
            period_start=datetime.fromisoformat(period_start).date() if period_start else None,
            period_end=datetime.fromisoformat(period_end).date() if period_end else None,
        )
    except DestinationConnectorError as exc:
        return redirect(f"/destination-connectors?error={exc}")
    target = f"/destination-connectors?notice=sync_{result.sync_id}_{result.status}"
    if campaign_id:
        target += f"&campaign_id={campaign_id}"
    return redirect(target)


@router.post("/destination-connectors/import-csv")
async def destination_connectors_import_csv_ui(
    file: UploadFile = File(...),
    campaign_id: int | None = Form(None),
    connection_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        text = (await file.read()).decode("utf-8-sig")
        connection = ConnectionRegistry(db).get(connection_id) if connection_id else None
        result = CSVMetricsImporter(db).import_csv_text(
            text,
            connection=connection,
            campaign_id=campaign_id,
            source_file=file.filename or "destination_metrics.csv",
        )
    except DestinationConnectorError as exc:
        return redirect(f"/destination-connectors?error={exc}")
    target = f"/destination-connectors?notice=import_{result.sync_id}_{result.status}"
    if campaign_id:
        target += f"&campaign_id={campaign_id}"
    return redirect(target)


@router.get("/destination-control-tower", response_class=HTMLResponse)
def destination_control_tower_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    snapshot = None
    rows = []
    report = None
    error = request.query_params.get("error")
    notice = request.query_params.get("notice")
    if selected_campaign:
        try:
            service = TowerService(db)
            snapshot = service.latest_or_refresh(selected_campaign.id)
            rows = service.rows(selected_campaign.id)
            report = DestinationControlReportService(db).build(selected_campaign.id)
        except DestinationControlTowerError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        "destination_control_tower.html",
        {
            "request": request,
            "page_title": "Destination Control Tower",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "snapshot": snapshot,
            "rows": rows,
            "report": report,
            "error": error,
            "notice": notice,
        },
    )


@router.post("/destination-control-tower/{campaign_id}/refresh")
def destination_control_tower_refresh_ui(campaign_id: int, db: Session = Depends(get_db)):
    try:
        snapshot = TowerService(db).refresh(campaign_id)
    except DestinationControlTowerError as exc:
        return redirect(f"/destination-control-tower?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-control-tower?campaign_id={campaign_id}&notice=snapshot_{snapshot.snapshot_id}_refreshed")


@router.post("/destination-control-tower/rows/{row_id}/action")
def destination_control_tower_action_ui(row_id: int, campaign_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        result = TowerService(db).apply_action(row_id)
    except DestinationControlTowerError as exc:
        return redirect(f"/destination-control-tower?campaign_id={campaign_id}&error={exc}")
    return redirect(f"/destination-control-tower?campaign_id={campaign_id}&notice={result['action']}_{result['status']}")


@router.get("/metrics-intake", response_class=HTMLResponse)
def metrics_intake_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign_id = campaign_id or (campaigns[0].id if campaigns else None)
    sources = MetricsSourceRegistry(db).list()
    links = TrackingLinkService(db).list(campaign_id=selected_campaign_id)
    batches = db.scalars(select(models.MetricsIntakeBatch).order_by(models.MetricsIntakeBatch.id.desc()).limit(20)).all()
    tasks = db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.id.desc()).limit(50)).all()
    funnel = FunnelService(db).campaign_funnel(selected_campaign_id) if selected_campaign_id else None
    unmatched = FunnelService(db).unmatched_rows(selected_campaign_id)
    platform_matrix = PlatformMetricsMatrix.all_configs()
    return templates.TemplateResponse(
        "metrics_intake.html",
        {
            "request": request,
            "page_title": "Metrics Intake",
            "campaigns": campaigns,
            "selected_campaign_id": selected_campaign_id,
            "sources": sources,
            "links": links,
            "batches": batches,
            "tasks": tasks,
            "funnel": funnel,
            "unmatched": unmatched,
            "platform_matrix": platform_matrix,
        },
    )


@router.post("/metrics-intake/sources")
def metrics_intake_create_source(
    name: str = Form(...),
    source_type: str = Form("manual_csv"),
    platform: str = Form("facebook"),
    connection_id: int | None = Form(None),
    credential_ref: str | None = Form(None),
    campaign_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    settings = {"credential_ref": credential_ref} if credential_ref else {}
    try:
        MetricsSourceRegistry(db).create(
            name=name,
            source_type=source_type,
            platform=platform,
            connection_id=connection_id,
            settings_json=settings,
        )
    except MetricsIntakeError as exc:
        return redirect(f"/metrics-intake?campaign_id={campaign_id or ''}&error={exc}")
    return redirect(f"/metrics-intake?campaign_id={campaign_id}" if campaign_id else "/metrics-intake")


@router.post("/metrics-intake/tracking-links")
def metrics_intake_create_tracking_link(
    publishing_task_id: int = Form(...),
    target_url: str | None = Form(None),
    campaign_id: int | None = Form(None),
    participant_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        TrackingLinkService(db).create_for_task(
            publishing_task_id,
            target_url=target_url,
            campaign_id=campaign_id,
            participant_id=participant_id,
        )
    except MetricsIntakeError as exc:
        return redirect(f"/metrics-intake?campaign_id={campaign_id or ''}&error={exc}")
    return redirect(f"/metrics-intake?campaign_id={campaign_id}" if campaign_id else "/metrics-intake")


@router.post("/metrics-intake/import-csv")
def metrics_intake_import_csv(
    csv_text: str = Form(...),
    source_id: int | None = Form(None),
    campaign_id: int | None = Form(None),
    source_type: str = Form("manual_csv"),
    db: Session = Depends(get_db),
):
    try:
        CSVImporter(db).import_csv_text(csv_text, source_id=source_id, campaign_id=campaign_id, source_type=source_type)
    except MetricsIntakeError as exc:
        return redirect(f"/metrics-intake?campaign_id={campaign_id or ''}&error={exc}")
    return redirect(f"/metrics-intake?campaign_id={campaign_id}" if campaign_id else "/metrics-intake")


@router.post("/metrics-intake/batches/{batch_id}/attribute")
def metrics_intake_attribute_batch(batch_id: int, campaign_id: int | None = Form(None), db: Session = Depends(get_db)):
    try:
        AttributionService(db).attribute_batch(batch_id)
    except MetricsIntakeError as exc:
        return redirect(f"/metrics-intake?campaign_id={campaign_id or ''}&error={exc}")
    return redirect(f"/metrics-intake?campaign_id={campaign_id}" if campaign_id else "/metrics-intake")


@router.get("/participant-portal", response_class=HTMLResponse)
def participant_portal_page(request: Request, participant_id: int | None = None, db: Session = Depends(get_db)):
    participants = ParticipantService(db).list()
    selected_participant = ParticipantService(db).get(participant_id) if participant_id else (participants[0] if participants else None)
    destinations = db.scalars(select(models.PublishingDestination).order_by(models.PublishingDestination.platform, models.PublishingDestination.id)).all()
    content_runs = db.scalars(select(models.ContentRun).order_by(models.ContentRun.id.desc()).limit(25)).all()
    publishing_tasks = db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.id.desc()).limit(25)).all()
    payout_rules = db.scalars(select(models.PayoutRule).order_by(models.PayoutRule.id)).all()
    links = []
    assignments = []
    submissions = []
    stats = None
    payout_summary = {"entries": [], "totals": {}, "total": 0}
    recommendations = []
    setup_steps = []
    training_progress = None
    platform_readiness = {}
    error = request.query_params.get("error")
    notice = request.query_params.get("notice")
    if selected_participant:
        try:
            links = OnboardingService(db).destinations(selected_participant.id)
            assignments = AssignmentPortalService(db).list_assignments(selected_participant.id)
            submissions = db.scalars(
                select(models.ParticipantSubmission)
                .where(models.ParticipantSubmission.participant_id == selected_participant.id)
                .order_by(models.ParticipantSubmission.id.desc())
            ).all()
            stats = ParticipantMetricsService(db).dashboard_stats(selected_participant.id)
            payout_summary = PayoutService(db).summary(selected_participant.id)
            recommendations = RecommendationService(db).recommendations(selected_participant.id)
            setup_steps = OnboardingService(db).setup_steps(selected_participant.id)
            curriculum = CurriculumService(db)
            if not curriculum.list_courses():
                curriculum.seed_defaults()
            training_progress = ProgressService(db).progress(selected_participant.id).model_dump(mode="json")
            cert_service = CertificationService(db)
            platform_readiness = {
                link.destination_id: cert_service.platform_readiness(selected_participant.id, link.destination.platform)
                for link in links
            }
        except ParticipantPortalError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        "participant_portal.html",
        {
            "request": request,
            "page_title": "Participant Portal",
            "participants": participants,
            "selected_participant": selected_participant,
            "destinations": destinations,
            "content_runs": content_runs,
            "publishing_tasks": publishing_tasks,
            "payout_rules": payout_rules,
            "links": links,
            "assignments": assignments,
            "submissions": submissions,
            "stats": stats,
            "payout_summary": payout_summary,
            "recommendations": recommendations,
            "setup_steps": setup_steps,
            "training_progress": training_progress,
            "platform_readiness": platform_readiness,
            "error": error,
            "notice": notice,
        },
    )


@router.post("/participant-portal/participants")
def participant_portal_create_participant(
    display_name: str = Form(...),
    role: str = Form("creator"),
    email: str = Form(""),
    telegram_handle: str = Form(""),
    platforms: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        participant = ParticipantService(db).create(
            display_name=display_name,
            role=role,
            email=email or None,
            telegram_handle=telegram_handle or None,
            platforms=[item.strip() for item in platforms.split(",") if item.strip()],
            notes=notes or None,
        )
    except ParticipantPortalError as exc:
        return redirect(f"/participant-portal?error={exc}")
    return redirect(f"/participant-portal?participant_id={participant.id}")


@router.post("/participant-portal/participants/{participant_id}/link-destination")
def participant_portal_link_destination(
    participant_id: int,
    destination_id: int = Form(...),
    relationship_type: str = Form("creator"),
    db: Session = Depends(get_db),
):
    try:
        OnboardingService(db).link_destination(participant_id, destination_id, relationship_type=relationship_type)
    except ParticipantPortalError as exc:
        return redirect(f"/participant-portal?participant_id={participant_id}&error={exc}")
    return redirect(f"/participant-portal?participant_id={participant_id}")


@router.post("/participant-portal/assignments")
def participant_portal_create_assignment(
    participant_id: int = Form(...),
    assignment_type: str = Form("create_video"),
    campaign_id: str = Form(""),
    content_run_id: str = Form(""),
    creative_variant_id: str = Form(""),
    publishing_task_id: str = Form(""),
    payout_rule_id: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        AssignmentPortalService(db).create_assignment(
            participant_id=participant_id,
            assignment_type=assignment_type,
            campaign_id=int(campaign_id) if campaign_id else None,
            content_run_id=int(content_run_id) if content_run_id else None,
            creative_variant_id=int(creative_variant_id) if creative_variant_id else None,
            publishing_task_id=int(publishing_task_id) if publishing_task_id else None,
            payout_rule_id=int(payout_rule_id) if payout_rule_id else None,
        )
    except (ParticipantPortalError, ValueError) as exc:
        return redirect(f"/participant-portal?participant_id={participant_id}&error={exc}")
    return redirect(f"/participant-portal?participant_id={participant_id}")


@router.post("/participant-portal/submissions")
def participant_portal_submit(
    participant_id: int = Form(...),
    assignment_id: int = Form(...),
    external_url: str = Form(""),
    file_path: str = Form(""),
    final_post_url: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        SubmissionService(db).submit(
            assignment_id=assignment_id,
            external_url=external_url or None,
            file_path=file_path or None,
            final_post_url=final_post_url or None,
        )
    except ParticipantPortalError as exc:
        return redirect(f"/participant-portal?participant_id={participant_id}&error={exc}")
    return redirect(f"/participant-portal?participant_id={participant_id}")


@router.post("/participant-portal/submissions/{submission_id}/review")
def participant_portal_review_submission(
    submission_id: int,
    participant_id: int = Form(...),
    review_status: str = Form("approved"),
    review_notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        SubmissionService(db).review(submission_id, review_status=review_status, review_notes=review_notes or None)
    except ParticipantPortalError as exc:
        return redirect(f"/participant-portal?participant_id={participant_id}&error={exc}")
    return redirect(f"/participant-portal?participant_id={participant_id}")


@router.post("/participant-portal/payout-rules")
def participant_portal_create_payout_rule(
    participant_id: int | None = Form(None),
    name: str = Form(...),
    payout_type: str = Form("per_video"),
    amount_fixed: float | None = Form(None),
    currency: str = Form("RUB"),
    percent_revenue: float | None = Form(None),
    db: Session = Depends(get_db),
):
    PayoutService(db).create_rule(
        name=name,
        payout_type=payout_type,
        amount_fixed=amount_fixed,
        currency=currency,
        percent_revenue=percent_revenue,
    )
    return redirect(f"/participant-portal?participant_id={participant_id}" if participant_id else "/participant-portal")


@router.post("/participant-portal/assignments/{assignment_id}/calculate-payout")
def participant_portal_calculate_payout(assignment_id: int, participant_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        PayoutService(db).calculate_for_assignment(assignment_id)
    except ParticipantPortalError as exc:
        return redirect(f"/participant-portal?participant_id={participant_id}&error={exc}")
    return redirect(f"/participant-portal?participant_id={participant_id}")


@router.post("/participant-portal/payouts/{payout_id}/mark-paid")
def participant_portal_mark_paid(payout_id: int, participant_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        PayoutService(db).mark_paid(payout_id)
    except ParticipantPortalError as exc:
        return redirect(f"/participant-portal?participant_id={participant_id}&error={exc}")
    return redirect(f"/participant-portal?participant_id={participant_id}")


@router.get("/training-academy", response_class=HTMLResponse)
def training_academy_page(
    request: Request,
    participant_id: int | None = None,
    course_id: int | None = None,
    db: Session = Depends(get_db),
):
    curriculum = CurriculumService(db)
    if not curriculum.list_courses():
        curriculum.seed_defaults()
    courses = curriculum.list_courses()
    selected_course = curriculum.get_course(course_id) if course_id else (courses[0] if courses else None)
    participants = ParticipantService(db).list()
    selected_participant = ParticipantService(db).get(participant_id) if participant_id else (participants[0] if participants else None)
    progress = None
    if selected_participant:
        progress = ProgressService(db).progress(selected_participant.id).model_dump(mode="json")
    return templates.TemplateResponse(
        "training_academy.html",
        {
            "request": request,
            "page_title": "Training Academy",
            "courses": courses,
            "selected_course": selected_course,
            "selected_course_payload": curriculum.course_payload(selected_course) if selected_course else None,
            "participants": participants,
            "selected_participant": selected_participant,
            "progress": progress,
            "beginner_tracks": BEGINNER_TRACKS,
            "platform_playbooks": PLATFORM_PLAYBOOKS,
            "scenarios": ScenarioService().list_scenarios(),
            "error": request.query_params.get("error"),
            "notice": request.query_params.get("notice"),
        },
    )


@router.post("/training-academy/courses/{course_id}/start")
def training_academy_start_course(course_id: int, participant_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        attempt = ProgressService(db).start_course(participant_id=participant_id, course_id=course_id)
    except TrainingAcademyError as exc:
        return redirect(f"/training-academy?participant_id={participant_id}&course_id={course_id}&error={exc}")
    return redirect(f"/training-academy?participant_id={participant_id}&course_id={course_id}&notice=started_attempt_{attempt.id}")


@router.post("/training-academy/quizzes/{quiz_id}/submit")
async def training_academy_submit_quiz(quiz_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    participant_id = int(str(form.get("participant_id") or "0"))
    course_id = int(str(form.get("course_id") or "0"))
    answers = {key.removeprefix("answer_"): value for key, value in form.items() if key.startswith("answer_")}
    try:
        result = QuizService(db).submit(participant_id=participant_id, quiz_id=quiz_id, answers=answers)
    except TrainingAcademyError as exc:
        return redirect(f"/training-academy?participant_id={participant_id}&course_id={course_id}&error={exc}")
    status = "certified" if result.passed else "failed"
    return redirect(
        f"/training-academy?participant_id={participant_id}&course_id={course_id}&notice=quiz_{status}_score_{result.score:.2f}"
    )


@router.post("/campaign-autopilot/import-matrix")
async def campaign_autopilot_import_matrix(file: UploadFile = File(...), db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8-sig")
    result = ProductMatrixImporter(db).import_csv_text(text, source_file=file.filename or "product_matrix.csv")
    return redirect(f"/campaign-autopilot?import_id={result.import_id}")


@router.post("/campaign-autopilot/campaigns/create")
def campaign_autopilot_create_campaign(
    import_id: int = Form(...),
    name: str = Form("Campaign Wave 1"),
    brand: str = Form("Bombar"),
    target_video_count: int = Form(350),
    target_destination_count: int = Form(120),
    db: Session = Depends(get_db),
):
    result = CampaignService(db).create_campaign(
        name=name,
        brand=brand,
        import_id=import_id,
        target_video_count=target_video_count,
        target_destination_count=target_destination_count,
        source_type="csv",
    )
    return redirect(f"/campaign-autopilot?campaign_id={result.campaign_id}")


@router.post("/campaign-autopilot/campaigns/{campaign_id}/prepare")
def campaign_autopilot_prepare(campaign_id: int, db: Session = Depends(get_db)):
    CampaignRunner(db).prepare_campaign(campaign_id)
    return redirect(f"/campaign-autopilot?campaign_id={campaign_id}")


@router.post("/campaign-autopilot/campaigns/{campaign_id}/prompt-only")
def campaign_autopilot_prompt_only(campaign_id: int, db: Session = Depends(get_db)):
    CampaignRunner(db).run_prompt_only_for_ready_items(campaign_id)
    return redirect(f"/campaign-autopilot?campaign_id={campaign_id}")


@router.post("/campaign-autopilot/campaigns/{campaign_id}/distribution-plan")
def campaign_autopilot_distribution_plan(campaign_id: int, db: Session = Depends(get_db)):
    CampaignDistributionPlanner(db).generate_plan(campaign_id)
    return redirect(f"/campaign-autopilot?campaign_id={campaign_id}")


@router.get("/campaign-execution", response_class=HTMLResponse)
def campaign_execution_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    snapshot = None
    actions = []
    report = None
    campaign_products = []
    if selected_campaign:
        campaign_products = db.scalars(
            select(models.CampaignProduct)
            .where(models.CampaignProduct.campaign_id == selected_campaign.id)
            .order_by(models.CampaignProduct.id)
        ).all()
        try:
            snapshot = ExecutionStateService(db).latest_snapshot(selected_campaign.id)
            actions = ActionQueueService(db).refresh_actions(selected_campaign.id)
            report = ExecutionReportService(db).build_report(selected_campaign.id)
        except CampaignExecutionDataError:
            snapshot = None
    return templates.TemplateResponse(
        "campaign_execution.html",
        {
            "request": request,
            "page_title": "Campaign Execution",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "snapshot": snapshot,
            "actions": actions,
            "report": report,
            "campaign_products": campaign_products,
        },
    )


@router.post("/campaign-execution/{campaign_id}/refresh")
def campaign_execution_refresh(campaign_id: int, db: Session = Depends(get_db)):
    ExecutionStateService(db).refresh_snapshot(campaign_id)
    ActionQueueService(db).refresh_actions(campaign_id)
    return redirect(f"/campaign-execution?campaign_id={campaign_id}")


@router.post("/campaign-execution/actions/{action_id}/execute")
def campaign_execution_execute(action_id: int, db: Session = Depends(get_db)):
    action = db.get(models.CampaignActionQueueItem, action_id)
    campaign_id = action.campaign_id if action else None
    if action:
        ActionQueueService(db).execute(action_id)
    return redirect(f"/campaign-execution?campaign_id={campaign_id}" if campaign_id else "/campaign-execution")


@router.post("/campaign-execution/actions/{action_id}/resolve")
def campaign_execution_resolve(action_id: int, db: Session = Depends(get_db)):
    action = db.get(models.CampaignActionQueueItem, action_id)
    campaign_id = action.campaign_id if action else None
    if action:
        ActionQueueService(db).resolve(action_id)
    return redirect(f"/campaign-execution?campaign_id={campaign_id}" if campaign_id else "/campaign-execution")


@router.get("/campaign-batch", response_class=HTMLResponse)
def campaign_batch_page(
    request: Request,
    campaign_id: int | None = None,
    action_type: str | None = None,
    batch_run_id: int | None = None,
    db: Session = Depends(get_db),
):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    selection = None
    latest_runs = []
    report = None
    if selected_campaign:
        try:
            selection = BatchSelector(db).select_safe_actions(selected_campaign.id, action_type=action_type or None)
        except CampaignBatchDataError:
            selection = None
        latest_runs = db.scalars(
            select(models.CampaignBatchRun)
            .where(models.CampaignBatchRun.campaign_id == selected_campaign.id)
            .order_by(models.CampaignBatchRun.id.desc())
        ).all()
    if batch_run_id:
        try:
            report = BatchReporter(db).build_report(batch_run_id)
        except CampaignBatchDataError:
            report = None
    elif latest_runs:
        report = BatchReporter(db).build_report(latest_runs[0].id)
    return templates.TemplateResponse(
        "campaign_batch.html",
        {
            "request": request,
            "page_title": "Campaign Batch",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "action_type": action_type or "",
            "action_types": sorted(SAFE_BATCH_ACTIONS),
            "selection": selection,
            "latest_runs": latest_runs[:10],
            "report": report,
        },
    )


@router.post("/campaign-batch/{campaign_id}/dry-run")
def campaign_batch_dry_run(
    campaign_id: int,
    action_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    result = BatchExecutor(db).dry_run(campaign_id, action_type=action_type or None)
    action_query = f"&action_type={action_type}" if action_type else ""
    return redirect(f"/campaign-batch?campaign_id={campaign_id}{action_query}&batch_run_id={result.batch_run_id}")


@router.post("/campaign-batch/{campaign_id}/execute")
def campaign_batch_execute(
    campaign_id: int,
    action_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    result = BatchExecutor(db).execute(campaign_id, action_type=action_type or None)
    action_query = f"&action_type={action_type}" if action_type else ""
    return redirect(f"/campaign-batch?campaign_id={campaign_id}{action_query}&batch_run_id={result.batch_run_id}")


@router.get("/campaign-performance", response_class=HTMLResponse)
def campaign_performance_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    summary = None
    scores = []
    recommendations = []
    report = None
    imports = []
    if selected_campaign:
        try:
            summary = CampaignPerformanceAggregator(db).summarize(selected_campaign.id)
            scores = CampaignPerformanceScorer(db).latest_scores(selected_campaign.id)
            recommendations = CampaignRecommendationEngine(db).list_recommendations(selected_campaign.id)
            report = CampaignPerformanceReportService(db).build_report(selected_campaign.id)
            imports = db.scalars(
                select(models.CampaignPerformanceImport)
                .where(models.CampaignPerformanceImport.campaign_id == selected_campaign.id)
                .order_by(models.CampaignPerformanceImport.id.desc())
            ).all()
        except CampaignPerformanceDataError:
            summary = None
    return templates.TemplateResponse(
        "campaign_performance.html",
        {
            "request": request,
            "page_title": "Campaign Performance",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "summary": summary,
            "scores": scores,
            "recommendations": recommendations,
            "report": report,
            "imports": imports[:10],
        },
    )


@router.post("/campaign-performance/{campaign_id}/import-csv")
async def campaign_performance_import_csv(campaign_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    csv_text = (await file.read()).decode("utf-8-sig")
    CampaignMetricsImporter(db).import_csv_text(campaign_id, csv_text, source_file=file.filename or "campaign_performance.csv")
    return redirect(f"/campaign-performance?campaign_id={campaign_id}")


@router.post("/campaign-performance/{campaign_id}/generate-recommendations")
def campaign_performance_generate_recommendations(campaign_id: int, db: Session = Depends(get_db)):
    CampaignRecommendationEngine(db).generate(campaign_id)
    return redirect(f"/campaign-performance?campaign_id={campaign_id}")


@router.post("/campaign-performance/recommendations/{recommendation_id}/accept")
def campaign_performance_accept_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    result = CampaignRecommendationEngine(db).accept(recommendation_id)
    return redirect(f"/campaign-performance?campaign_id={result.campaign_id}")


@router.post("/campaign-performance/recommendations/{recommendation_id}/reject")
def campaign_performance_reject_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    result = CampaignRecommendationEngine(db).reject(recommendation_id)
    return redirect(f"/campaign-performance?campaign_id={result.campaign_id}")


@router.get("/factory-os", response_class=HTMLResponse)
def factory_os_page(request: Request, campaign_id: int | None = None, db: Session = Depends(get_db)):
    campaigns = db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all()
    selected_campaign = db.get(models.Campaign, campaign_id) if campaign_id else (campaigns[0] if campaigns else None)
    health = FactoryHealthCheck(db).run()
    report = None
    runbook = None
    if selected_campaign:
        try:
            report = FactoryAcceptanceReportService(db).build(selected_campaign.id)
            runbook = FactoryRunbookService(db).build(selected_campaign.id)
        except FactoryOSError:
            report = None
            runbook = None
    return templates.TemplateResponse(
        "factory_os.html",
        {
            "request": request,
            "page_title": "Factory OS",
            "campaigns": campaigns,
            "selected_campaign": selected_campaign,
            "health": health,
            "report": report,
            "runbook": runbook,
        },
    )


@router.post("/factory-os/prompt-only-launch")
def factory_os_prompt_only_launch(
    matrix_path: str = Form("sample_data/product_matrix.csv"),
    campaign_name: str = Form("Demo Launch"),
    brand: str = Form("Factory OS"),
    target_videos: int = Form(350),
    target_destinations: int = Form(120),
    performance_csv_path: str = Form("sample_data/campaign_performance.csv"),
    db: Session = Depends(get_db),
):
    result = FactoryLaunchWorkflow(db).run_prompt_only_launch(
        matrix_path,
        campaign_name,
        target_videos,
        target_destinations,
        brand=brand,
        performance_csv_path=performance_csv_path or None,
    )
    return redirect(f"/factory-os?campaign_id={result.campaign_id}")


@router.post("/bombar-launch/import-matrix")
async def bombar_launch_import_matrix(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read()
    filename = file.filename or "bombar_matrix.csv"
    importer = BombarMatrixImporter(db)
    if filename.lower().endswith(".xlsx"):
        result = importer.import_xlsx_bytes(data, source_file=filename)
    else:
        result = importer.import_csv_text(data.decode("utf-8-sig"), source_file=filename)
    return redirect(f"/bombar-launch?import_id={result.import_id}")


@router.post("/bombar-launch/campaigns/create")
def bombar_launch_create_campaign(
    import_id: int = Form(...),
    name: str = Form(""),
    brand: str = Form("Bombar"),
    target_video_count: int = Form(350),
    target_destination_count: int = Form(120),
    db: Session = Depends(get_db),
):
    result = LaunchPlanner(db).create_campaign(
        import_id,
        name=name or None,
        brand=brand,
        target_video_count=target_video_count,
        target_destination_count=target_destination_count,
    )
    return redirect(f"/bombar-launch?campaign_id={result.campaign_id}")


@router.post("/bombar-launch/campaigns/{campaign_id}/prepare-content")
def bombar_launch_prepare_content(campaign_id: int, db: Session = Depends(get_db)):
    LaunchPlanner(db).prepare_content(campaign_id)
    return redirect(f"/bombar-launch?campaign_id={campaign_id}")


@router.post("/bombar-launch/campaigns/{campaign_id}/destination-packs")
def bombar_launch_destination_packs(campaign_id: int, db: Session = Depends(get_db)):
    DestinationSetupPlanner(db).generate(campaign_id)
    return redirect(f"/bombar-launch?campaign_id={campaign_id}")


@router.post("/bombar-launch/campaigns/{campaign_id}/distribution-plan")
def bombar_launch_distribution_plan(campaign_id: int, db: Session = Depends(get_db)):
    DistributionAllocator(db).generate_plan(campaign_id)
    return redirect(f"/bombar-launch?campaign_id={campaign_id}")


@router.get("/ui-counts")
def ui_counts(db: Session = Depends(get_db)):
    return {
        "products": db.scalar(select(func.count()).select_from(models.Product)),
        "brand_guides": db.scalar(select(func.count()).select_from(models.BrandGuide)),
        "creative_templates": db.scalar(select(func.count()).select_from(models.CreativeTemplate)),
        "accounts": db.scalar(select(func.count()).select_from(models.PublishingAccount)),
    }
