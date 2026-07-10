from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"

import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.ai_brief_contract import AIProductionBriefBuilder, BriefQualityChecker, DirectorPromptBuilder, MarkdownRenderer, SceneBlueprintBuilder
from app.ai_brief_contract.types import NEGATIVE_PROMPT_TERMS
from app.output_acceptance import AcceptanceReviewService, FrameExtractor, OutputQualityChecker, RegenerationFeedbackBuilder
from app.one_video_acceptance import OneVideoAcceptanceService, ProductScenePolicyService
from app.smoke_readiness import ReadinessReportService, RecoveryService
from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.asset_storage import ProductAssetStorage
from app.assets.asset_validator import AssetValidator
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.assets.reference_bundle_builder import ProviderReferenceBundleBuilder
from app.assets.types import ProductAssetDescriptor
from app.bombar_launch import (
    BombarMatrixImporter,
    DestinationSetupPlanner,
    DistributionAllocator,
    LaunchDashboardService,
    LaunchPlanner,
    ProfilePackBuilder,
)
from app.bombar_production import BombarMatrixValidator, BombarProductionDryRunService
from app.blogger_brief import MeaningSpecBuilder, ProductReferencePolicyService, UGCAdScriptBuilder
from app.blogger_brief.prompt_enricher import PromptEnricher
from app.blogger_brief.types import PACKAGING_DRIFT_NEGATIVE_TERMS
from app.campaign_autopilot import (
    CampaignDistributionPlanner,
    CampaignRunner,
    CampaignService,
    ProductMatrixImporter,
    TargetAllocator,
)
from app.campaign_batch import BatchExecutor, BatchReporter
from app.campaign_execution import ActionQueueService, ExecutionReportService, ExecutionStateService
from app.campaign_performance import (
    CampaignMetricsImporter,
    CampaignPerformanceAggregator,
    CampaignPerformanceReportService,
    CampaignPerformanceScorer,
    CampaignRecommendationEngine,
)
from app.config import get_settings
from app.control_room import ControlRoomSnapshotService
from app.content_factory import ContentPerformanceService, ContentRunOrchestrator, ContentStatsImporter
from app.creative.creative_spec_builder import CreativeSpecBuilder
from app.creative.creative_spec_validator import CreativeSpecValidator
from app.creative.hook_strategy import HookStrategySelector
from app.creative.product_geometry import GEOMETRY_LOCK_PROMPT_LINES, GEOMETRY_NEGATIVE_TERMS
from app.creative.types import CreativeSpec
from app.creative_quality import CreativeQualityGateService, ScriptRewriter, UGCQualityScorer
from app.creative_workbench import (
    BriefEditorService,
    CreativeWorkbenchGuardrailError,
    PromptPreviewService,
    ReadinessService,
    RewriteWorkflowService,
    WorkbenchService,
)
from app.database import Base, SessionLocal, engine
from app.destination_setup import DestinationProfilePackBuilder, DestinationSetupTaskService, SetupRequirementService
from app.destination_setup.errors import DestinationSetupDataError
from app.destination_crm import (
    DestinationCRMCampaignCapacityService,
    DestinationHealthService,
    DestinationReadinessService,
    DestinationWarmupService,
)
from app.destination_connectors import (
    ConnectionRegistry,
    CSVMetricsImporter,
    DestinationConnectorSyncService,
    DestinationMetricsCollector,
    TelegramConnector,
    YouTubeAnalyticsConnector,
)
from app.destination_control_tower import DestinationControlReportService, TowerService
from app.engine_audit import EngineAuditReportService, EngineAuditScorecardService
from app.participant_portal import (
    AssignmentPortalService,
    OnboardingService,
    ParticipantMetricsService,
    ParticipantService,
    PayoutService,
    RecommendationService,
    SubmissionService,
)
from app.demand.demand_hypothesis_builder import DemandHypothesisBuilder
from app.demand.demand_validator import DemandValidator
from app.demand.types import DemandHypothesis
from app.engine import VideoFactoryEngine
from app.factory_os import FactoryAcceptanceReportService, FactoryHealthCheck, FactoryLaunchWorkflow, FactoryRunbookService
from app.intelligence.errors import ClaimValidationError, ProviderConfigurationError
from app.intelligence.generation_runner import GeneratorRunService
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.prompt_builder import PromptPackBuilder
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.script_generator import GeneratorScriptService
from app.intelligence.types import (
    AllowedClaim,
    CreativeIntelligencePack,
    GeneratedSceneOutput,
    GeneratedScriptOutput,
    PromptPackOutput,
    PromptSceneOutput,
    ProviderVideoJob,
    ProviderVideoStatus,
    ScriptBriefOutput,
)
from app.intelligence.validators import validate_script_claim_refs
from app.launch_operations import DestinationCapacityService, LaunchActionPlanner, LaunchReadinessService, LaunchReportService, QualityGateService
from app.main import app
from app.metrics_intake import (
    AttributionService,
    CSVImporter,
    FunnelService,
    MetricsIntakeDataError,
    MetricsSourceRegistry,
    OfficialConnectorGateway,
    PlatformMetricsMatrix,
    TrackingLinkService,
)
from app.publishing import ManualUploadProvider, MockUploadProvider
from app.publishing.errors import PublishingError
from app.participant_portal.errors import ParticipantPortalDataError
from app.product_strategy import OfferStrategyBuilder, ProductStrategyBuilder
from app.providers.openai_llm import OpenAILLMProvider
from app.providers.runway_video import RunwayVideoProvider
from app.services.video_assembly import VideoAssemblyService
from app.training_academy import CertificationService, CurriculumService, ProgressService, QuizService, ScenarioService
from app.training_academy.academy_catalog import BEGINNER_TRACKS, COURSE_BADGE_BY_CODE
from app.training_academy.errors import TrainingAcademyDataError
from app.ugc import UGCRealismService
from app.variants.creative_variant_builder import CreativeVariantBuilder
from app.variants.first_frame_builder import FirstFrameBuilder
from app.variants.variant_scorer import VariantScorer
from app.variants.variant_selector import VariantSelector
from app.video_generator.generator import VideoGenerator
from app.video_generator.regeneration_requests import RegenerationRequestService
from app.video_generator.real_smoke_runner import RealSmokeRunner
from app.workflows.working_video_generator import WorkingVideoGenerator


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def client() -> TestClient:
    reset_db()
    return TestClient(app)


def create_product(
    api: TestClient,
    title: str = "Altea Test Bottle",
    benefits: list[str] | None = None,
    images: list[str] | None = None,
) -> int:
    response = api.post(
        "/api/products",
        json={
            "sku": f"SKU-{abs(hash(title)) % 100000}",
            "brand": "Altea",
            "marketplace": "Ozon",
            "title": title,
            "description": "Reusable bottle for everyday routines.",
            "category": "Home",
            "attributes_json": {"capacity": "600 ml"},
            "benefits_json": benefits or ["keeps drinks at hand"],
            "images_json": images or [],
            "reviews_json": [],
            "restrictions_json": [],
            "product_url": "https://example.com/product",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_guide(api: TestClient, forbidden_words: list[str] | None = None) -> int:
    response = api.post(
        "/api/brand-guides",
        json={
            "brand": "Altea",
            "tone_of_voice": "Clear and safe.",
            "visual_style": "Clean product shots.",
            "forbidden_words_json": forbidden_words or ["cure"],
            "forbidden_claims_json": ["medical treatment"],
            "required_disclaimers_json": ["AI-assisted creative"],
            "allowed_cta_json": ["Learn more in the product card"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_template(api: TestClient) -> int:
    response = api.post(
        "/api/creative-templates",
        json={
            "name": f"problem_solution_{datetime.now(UTC).timestamp()}",
            "description": "Problem, benefit, usage, CTA.",
            "format": "short_video",
            "duration_seconds": 15,
            "aspect_ratio": "9:16",
            "structure_json": ["hook", "benefit", "usage", "cta"],
            "hook_formula": "Name the buyer problem.",
            "cta": "Learn more in the product card",
            "platform_fit_json": ["Instagram Reels", "TikTok"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_account(api: TestClient, daily_limit: int = 1, weekly_limit: int = 3) -> int:
    response = api.post(
        "/api/publishing-accounts",
        json={
            "brand": "Altea",
            "platform": "Instagram Reels",
            "account_name": "Altea Instagram",
            "account_handle": "@altea",
            "owner_name": "Content Ops",
            "auth_status": "mock_ready",
            "warmup_status": "warming",
            "warmup_phase": "phase_1_soft_start",
            "daily_publish_limit": daily_limit,
            "weekly_publish_limit": weekly_limit,
            "allowed_formats_json": ["vertical_video"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_warmup_plan(api: TestClient) -> int:
    response = api.post(
        "/api/warmup-plans",
        json={
            "name": "test_conservative",
            "status": "active",
            "current_phase": "phase_1_soft_start",
            "rules_json": ["phase_1_soft_start"],
            "rules": [
                {
                    "phase": "phase_1_soft_start",
                    "day_from": 1,
                    "day_to": 7,
                    "max_posts_per_day": 1,
                    "max_posts_per_week": 3,
                    "allowed_content_types_json": ["vertical_video"],
                    "requires_manual_approval": True,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def product_sku(api: TestClient, product_id: int) -> str:
    return api.get(f"/api/products/{product_id}").json()["sku"]


def add_generator_snapshots(
    sku: str,
    ctr: float = 0.035,
    conversion_rate: float = 0.02,
    stock_qty: int = 80,
    days_of_stock: float = 20,
    returns_rate: float = 0.04,
    competitor_price: float | None = None,
) -> None:
    with SessionLocal() as db:
        db.add(
            models.ProductMetricSnapshot(
                sku=sku,
                marketplace="Ozon",
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                views=10000,
                clicks=max(1, int(10000 * ctr)),
                orders=max(1, int(10000 * ctr * conversion_rate)),
                revenue=12000,
                conversion_rate=conversion_rate,
                ctr=ctr,
                avg_price=1500,
                ad_spend=4000,
                ad_orders=0,
                ad_revenue=0,
                stock_qty=stock_qty,
                days_of_stock=days_of_stock,
                returns_rate=returns_rate,
                rating=4.5,
                reviews_count=120,
                raw_json={},
            )
        )
        db.add(
            models.CreativePerformanceSnapshot(
                sku=sku,
                platform="Instagram Reels",
                creative_angle="trust_builder",
                hook_text="Why shoppers choose it",
                posted_at=datetime.now(UTC).replace(tzinfo=None),
                views=3000,
                clicks=120,
                ctr=0.04,
                orders=5,
                retention_rate=0.41,
                raw_json={},
            )
        )
        db.add(
            models.ProductReviewInsight(
                sku=sku,
                marketplace="Ozon",
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                positive_themes_json=["easy to use"],
                negative_themes_json=["difference from analogs unclear"],
                buyer_objections_json=["why is it better than cheaper options?"],
                buyer_language_json=["daily routine", "not sticky"],
                source_review_count=120,
                raw_json={},
            )
        )
        if competitor_price is not None:
            db.add(
                models.MarketSignal(
                    sku=sku,
                    marketplace="Ozon",
                    competitor_brand="Competitor",
                    competitor_price=competitor_price,
                    competitor_rating=4.6,
                    competitor_reviews_count=240,
                    signal_type="price_pressure",
                    signal_strength="medium",
                    notes="Competitor is cheaper.",
                    raw_json={},
                )
            )
        db.commit()


def prepare_generator_product(api: TestClient, title: str = "Sprint 03 Product") -> int:
    product_id = create_product(api, title=title)
    create_guide(api)
    create_template(api)
    add_generator_snapshots(product_sku(api, product_id))
    return product_id


def build_creative_spec_fixture(
    api: TestClient,
    title: str = "Creative Spec Product",
    duration: int = 15,
    images: list[str] | None = None,
    ctr: float = 0.035,
    conversion_rate: float = 0.02,
) -> tuple[int, int, CreativeSpec]:
    product_id = create_product(api, title=title, images=images)
    create_guide(api)
    create_template(api)
    add_generator_snapshots(product_sku(api, product_id), ctr=ctr, conversion_rate=conversion_rate)
    with SessionLocal() as db:
        record = CreativeSpecBuilder(db).build_for_product(
            product_id,
            platform="Instagram Reels",
            duration_seconds=duration,
        )
    return product_id, record.id, CreativeSpec.model_validate(record.spec_json)


def build_variant_set_fixture(
    api: TestClient,
    title: str = "Variant Product",
    images: list[str] | None = None,
    count: int = 5,
    ctr: float = 0.035,
    conversion_rate: float = 0.02,
) -> tuple[int, int, int, int]:
    product_id, spec_id, _ = build_creative_spec_fixture(
        api,
        title=title,
        images=images
        or [
            "https://example.com/packshot_front.jpg",
            "https://example.com/label_closeup.png",
            "https://example.com/lifestyle_use.jpg",
        ],
        ctr=ctr,
        conversion_rate=conversion_rate,
    )
    with SessionLocal() as db:
        kit = AssetKitBuilder(db).build_for_product(product_id)
        variant_set = CreativeVariantBuilder(db).build_set(spec_id, count=count, asset_kit_id=kit.id)
        VariantScorer(db).score_set(variant_set.id)
        variant_set = VariantSelector(db).select_best(variant_set.id)
        selected_variant_id = variant_set.selected_variant_id or variant_set.variants[0].id
    return product_id, spec_id, variant_set.id, selected_variant_id


def enable_real_smoke_env(monkeypatch, *, allow_spend: str = "true", runway_key: str | None = "test-runway-key") -> None:
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", allow_spend)
    monkeypatch.setenv("QVF_VIDEO_PROVIDER", "runway")
    if runway_key is None:
        monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)
    else:
        monkeypatch.setenv("RUNWAYML_API_SECRET", runway_key)
    get_settings.cache_clear()


def prepare_ready_variant(
    api: TestClient,
    title: str = "Ready Real Smoke Variant",
    *,
    url: str = "https://example.com/packshot.png",
) -> tuple[int, int, int, int]:
    product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title=title)
    with SessionLocal() as db:
        attach_approved_tier_2_contract(db, product_id, primary_url=url)
        bundle = ProviderReferenceBundleBuilder(db).build(product_id, provider="runway")
    return product_id, spec_id, selected_variant_id, bundle.id


def attach_approved_reference_pair(
    db: Session,
    product_id: int,
    *,
    primary_url: str = "https://example.com/packshot.png",
) -> tuple[models.ProductAsset, models.ProductAsset]:
    storage = ProductAssetStorage(db)
    primary = storage.attach_url(
        product_id,
        url=primary_url,
        asset_type="packshot",
        is_primary_reference=True,
    )
    storage.update_asset(
        primary.id,
        review_status="approved",
        is_primary_reference=True,
        contract_type="front_packshot",
    )
    label = storage.attach_url(
        product_id,
        url="https://example.com/label_closeup.png",
        asset_type="label_closeup",
        manual_label="label closeup",
    )
    storage.update_asset(label.id, review_status="approved", asset_type="label_closeup", contract_type="label_closeup")
    return primary, label


def attach_approved_tier_2_contract(
    db: Session,
    product_id: int,
    *,
    primary_url: str = "https://example.com/packshot.png",
) -> tuple[models.ProductAsset, models.ProductAsset, models.ProductAsset]:
    storage = ProductAssetStorage(db)
    primary = storage.attach_url(product_id, url=primary_url, asset_type="packshot", is_primary_reference=True)
    storage.update_asset(
        primary.id,
        review_status="approved",
        is_primary_reference=True,
        contract_type="front_packshot",
    )
    angle = storage.attach_url(
        product_id,
        url="https://example.com/angled_product.png",
        asset_type="product",
        manual_label="angled product",
    )
    storage.update_asset(angle.id, review_status="approved", contract_type="angled_product")
    scale = storage.attach_url(
        product_id,
        url="https://example.com/product_in_hand.png",
        asset_type="product",
        manual_label="product in hand scale context",
    )
    storage.update_asset(scale.id, review_status="approved", contract_type="product_in_hand")
    return primary, angle, scale


def create_manual_ugc_script(
    db: Session,
    product_id: int,
    *,
    creative_spec_id: int | None = None,
    creative_variant_id: int | None = None,
    scenes: list[dict] | None = None,
    with_product_strategy: bool = True,
    platform: str = "Instagram Reels",
) -> models.UGCAdScript:
    if with_product_strategy:
        strategy = ProductStrategyBuilder(db).latest_for_product(product_id) or ProductStrategyBuilder(db).build(
            product_id,
            platform=platform,
        )
        OfferStrategyBuilder(db).build(strategy.id)
    meaning = MeaningSpecBuilder(db).build(product_id, creative_spec_id=creative_spec_id, duration_seconds=8)
    scene_script = scenes or [
        {
            "scene_number": 1,
            "role": "hook",
            "starts_at": 0,
            "duration_seconds": 1,
            "spoken_line": "I tried this after training when I wanted dessert without a heavy snack.",
            "caption": "After training",
            "visual_direction": "Sporty creator holds the exact pack.",
            "proof_moment": meaning.proof_moment_json,
            "product_lock_mode": (meaning.product_lock_rules_json or {}).get("product_lock_mode"),
        },
        {
            "scene_number": 2,
            "role": "personal_context",
            "starts_at": 1,
            "duration_seconds": 2,
            "spoken_line": "I keep it in my gym bag because I need something quick between errands.",
            "caption": "Real routine",
            "visual_direction": "Creator speaks naturally in a gym or kitchen routine.",
            "proof_moment": meaning.proof_moment_json,
            "product_lock_mode": (meaning.product_lock_rules_json or {}).get("product_lock_mode"),
        },
        {
            "scene_number": 3,
            "role": "product_reason",
            "starts_at": 3,
            "duration_seconds": 2,
            "spoken_line": "That is why this exact product fits my routine: compact pack, clear flavour, and easy portion.",
            "caption": "Why this one",
            "visual_direction": "Package stays visible and readable.",
            "proof_moment": meaning.proof_moment_json,
            "product_lock_mode": (meaning.product_lock_rules_json or {}).get("product_lock_mode"),
        },
        {
            "scene_number": 4,
            "role": "proof_demo",
            "starts_at": 5,
            "duration_seconds": 2,
            "spoken_line": "I show the real pack, open it, and try one unwrapped bite so the texture is visible.",
            "caption": "Texture check",
            "visual_direction": "Exact packshot plus separate unwrapped product piece.",
            "proof_moment": meaning.proof_moment_json,
            "product_lock_mode": (meaning.product_lock_rules_json or {}).get("product_lock_mode"),
        },
        {
            "scene_number": 5,
            "role": "cta",
            "starts_at": 7,
            "duration_seconds": 1,
            "spoken_line": "Check the product card if this snack fits your routine.",
            "caption": "See product card",
            "visual_direction": "End on exact product packshot.",
            "proof_moment": meaning.proof_moment_json,
            "product_lock_mode": (meaning.product_lock_rules_json or {}).get("product_lock_mode"),
        },
    ]
    script = models.UGCAdScript(
        blogger_meaning_spec_id=meaning.id,
        creative_variant_id=creative_variant_id,
        status="ready",
        duration_seconds=8,
        voiceover_json={
            "language": "ru",
            "style": "first-person creator language",
            "lines": [scene.get("spoken_line", "") for scene in scene_script],
        },
        captions_json={"style": "minimal", "lines": [scene.get("caption", "") for scene in scene_script]},
        scene_script_json=scene_script,
    )
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def generic_ad_scenes() -> list[dict]:
    return [
        {"scene_number": 1, "role": "hook", "spoken_line": "Buy now, best product.", "caption": "", "visual_direction": ""},
        {"scene_number": 2, "role": "personal_context", "spoken_line": "This is good.", "caption": "", "visual_direction": ""},
        {"scene_number": 3, "role": "product_reason", "spoken_line": "Great offer for everyone.", "caption": "", "visual_direction": ""},
        {"scene_number": 4, "role": "proof_demo", "spoken_line": "Look at this item.", "caption": "", "visual_direction": ""},
        {"scene_number": 5, "role": "cta", "spoken_line": "Order now.", "caption": "", "visual_direction": ""},
    ]


def prepare_workbench_fixture(
    api: TestClient,
    *,
    title: str = "Creative Workbench Product",
    scenes: list[dict] | None = None,
    with_references: bool = True,
    with_prompt_pack: bool = True,
) -> tuple[int, int, int, int | None]:
    product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title=title)
    with SessionLocal() as db:
        if with_references:
            attach_approved_reference_pair(db, product_id)
        script = create_manual_ugc_script(
            db,
            product_id,
            creative_spec_id=spec_id,
            creative_variant_id=selected_variant_id,
            scenes=scenes,
        )
        prompt_pack_id = None
        if with_prompt_pack:
            generation = PromptEnricher(db).build_prompt_pack_from_script(script.id, provider="runway")
            prompt_pack_id = generation.prompt_pack_id
        UGCQualityScorer(db).score_script(script.id, prompt_pack_id=prompt_pack_id)
        session = WorkbenchService(db).build(product_id, ugc_script_id=script.id, prompt_pack_id=prompt_pack_id)
    return product_id, session.id, script.id, prompt_pack_id


def prepare_ai_brief_fixture(
    api: TestClient,
    *,
    title: str = "AI Brief Contract Product",
    scenes: list[dict] | None = None,
    with_blueprint: bool = True,
    with_director_prompt: bool = True,
    with_quality_check: bool = False,
) -> tuple[int, int, int]:
    product_id, _, script_id, _ = prepare_workbench_fixture(api, title=title, scenes=scenes)
    with SessionLocal() as db:
        brief = AIProductionBriefBuilder(db).build(product_id, ugc_script_id=script_id)
        if with_blueprint:
            SceneBlueprintBuilder(db).build(brief.id)
        if with_director_prompt:
            DirectorPromptBuilder(db).build(brief.id)
        if with_quality_check:
            BriefQualityChecker(db).check(brief.id)
    return product_id, brief.id, script_id


def prepare_output_acceptance_fixture(
    api: TestClient,
    *,
    title: str = "Output Acceptance Product",
    with_frames: bool = True,
) -> tuple[int, int, int]:
    product_id, brief_id, script_id = prepare_ai_brief_fixture(api, title=title, with_quality_check=True)
    video_job_id = approve_script_and_create_video(api)
    run = api.post(f"/api/video-jobs/{video_job_id}/run")
    assert run.status_code == 200, run.text
    with SessionLocal() as db:
        script = db.get(models.UGCAdScript, script_id)
        creative_spec_id = script.blogger_meaning_spec.creative_spec_id
        video_job = db.get(models.VideoJob, video_job_id)
        generation_variant = models.VideoGenerationVariant(
            creative_spec_id=creative_spec_id,
            script_variant_id=video_job.script_variant_id,
            video_job_id=video_job.id,
            provider="mock",
            status="generated",
            prompt_pack_json={
                "scene_prompts": [
                    {"scene_number": 1, "scene_role": "hook", "prompt": "Hook scene"},
                    {"scene_number": 2, "scene_role": "personal_context", "prompt": "Context scene"},
                ]
            },
            provider_payload_json={},
            local_output_paths_json=[video_job.output_video_path],
            final_video_path=video_job.output_video_path,
        )
        db.add(generation_variant)
        db.commit()
        if with_frames:
            FrameExtractor(db).extract(video_job_id)
    return product_id, brief_id, video_job_id


def prepare_working_video_product(
    api: TestClient,
    title: str = "Working Video Product",
    *,
    images: list[str] | None = None,
    ctr: float = 0.035,
    conversion_rate: float = 0.02,
    returns_rate: float = 0.04,
    stock_qty: int = 80,
    days_of_stock: float = 20,
    competitor_price: float | None = None,
    with_signals: bool = True,
) -> int:
    product_id = create_product(
        api,
        title=title,
        images=images
        or [
            "https://example.com/packshot_front.jpg",
            "https://example.com/label_closeup.png",
            "https://example.com/lifestyle_use.jpg",
        ],
    )
    create_guide(api)
    create_template(api)
    if with_signals:
        add_generator_snapshots(
            product_sku(api, product_id),
            ctr=ctr,
            conversion_rate=conversion_rate,
            stock_qty=stock_qty,
            days_of_stock=days_of_stock,
            returns_rate=returns_rate,
            competitor_price=competitor_price,
        )
    return product_id


def install_fake_runway_provider(monkeypatch) -> list[int]:
    scene_counts: list[int] = []

    class FakeRunwayProvider:
        provider_name = "runway"

        def create_generation(self, prompt_pack: PromptPackOutput) -> ProviderVideoJob:
            scene_counts.append(len(prompt_pack.scene_prompts))
            return ProviderVideoJob(
                provider="runway",
                provider_job_id=f"fake-runway-job-{len(scene_counts)}",
                status="succeeded",
                raw_response={
                    "id": f"fake-runway-job-{len(scene_counts)}",
                    "status": "succeeded",
                    "request_token": "fake-provider-secret",
                },
            )

        def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
            return ProviderVideoStatus(
                provider_job_id=provider_job_id,
                status="succeeded",
                raw_response={
                    "id": provider_job_id,
                    "status": "succeeded",
                    "output": ["https://cdn.example.com/out.mp4?token=raw-secret&signature=abc123&_jwt=signed-url-secret"],
                },
            )

        def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]:
            target_dir.mkdir(parents=True, exist_ok=True)
            path = target_dir / f"{provider_job_id}.mp4"
            path.write_text("fake provider video bytes", encoding="utf-8")
            return [path]

    monkeypatch.setattr("app.intelligence.video_generator.RunwayVideoProvider", FakeRunwayProvider)
    return scene_counts


def create_script(api: TestClient, title: str = "Altea Test Bottle", forbidden_words: list[str] | None = None) -> int:
    product_id = create_product(api, title=title)
    guide_id = create_guide(api, forbidden_words=forbidden_words)
    template_id = create_template(api)
    response = api.post(
        "/api/script-jobs/generate",
        json={"product_id": product_id, "template_id": template_id, "brand_guide_id": guide_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def approve_script_and_create_video(api: TestClient) -> int:
    script_id = create_script(api)
    script = api.get(f"/api/script-jobs/{script_id}").json()
    variant_id = script["id"]
    # The generated script job always creates variant ID 1 in a fresh database.
    approve = api.post("/api/script-variants/1/approve")
    assert approve.status_code == 200, approve.text
    response = api.post("/api/video-jobs", json={"script_variant_id": 1, "provider": "mock"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_approved_package(api: TestClient) -> tuple[int, int]:
    video_job_id = approve_script_and_create_video(api)
    run = api.post(f"/api/video-jobs/{video_job_id}/run")
    assert run.status_code == 200, run.text
    approved = api.post(f"/api/video-jobs/{video_job_id}/approve")
    assert approved.status_code == 200, approved.text
    package = api.post("/api/publishing-packages", json={"video_job_id": video_job_id, "target_platform": "Instagram Reels"})
    assert package.status_code == 200, package.text
    package_id = package.json()["id"]
    approved_package = api.post(f"/api/publishing-packages/{package_id}/approve")
    assert approved_package.status_code == 200, approved_package.text
    account_id = create_account(api)
    create_warmup_plan(api)
    return package_id, account_id


def create_safe_approved_package_and_destination(
    api: TestClient,
    *,
    title: str = "Altea Test Bottle",
    daily_limit: int = 1,
) -> tuple[int, int]:
    script_id = create_script(api, title=title)
    with SessionLocal() as db:
        variant_id = db.query(models.ScriptVariant).filter_by(script_job_id=script_id).one().id
    approved = api.post(f"/api/script-variants/{variant_id}/approve")
    assert approved.status_code == 200, approved.text
    response = api.post("/api/video-jobs", json={"script_variant_id": variant_id, "provider": "mock"})
    assert response.status_code == 200, response.text
    video_job_id = response.json()["id"]
    run = api.post(f"/api/video-jobs/{video_job_id}/run")
    assert run.status_code == 200, run.text
    approved_video = api.post(f"/api/video-jobs/{video_job_id}/approve")
    assert approved_video.status_code == 200, approved_video.text
    package = api.post("/api/publishing/packages", json={"video_job_id": video_job_id, "platform": "telegram"})
    assert package.status_code == 200, package.text
    package_id = package.json()["id"]
    approval = api.post(f"/api/publishing/packages/{package_id}/approve", json={"reviewer_name": "ops"})
    assert approval.status_code == 200, approval.text
    destination = api.post(
        "/api/publishing/destinations",
        json={
            "brand": "Altea",
            "platform": "telegram",
            "name": "Altea Telegram",
            "posting_mode": "manual",
            "daily_limit": daily_limit,
            "weekly_limit": 3,
        },
    )
    assert destination.status_code == 200, destination.text
    return package_id, destination.json()["id"]


def test_product_creation():
    with client() as api:
        product_id = create_product(api)
        response = api.get(f"/api/products/{product_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Altea Test Bottle"


def test_script_generation():
    with client() as api:
        script_id = create_script(api)
        script = api.get(f"/api/script-jobs/{script_id}").json()
        assert script["status"] == "script_generated"
        assert script["validation_report_json"]["valid"] is True
        assert script["output_script_json"]["scenes"][0]["video_prompt"]


def test_forbidden_claim_validation():
    with client() as api:
        script_id = create_script(api, title="Miracle Bottle", forbidden_words=["miracle"])
        report = api.post(f"/api/script-jobs/{script_id}/validate")
        assert report.status_code == 200
        assert report.json()["valid"] is False
        assert "Forbidden" in report.json()["errors"][0]


def test_video_job_creation():
    with client() as api:
        video_job_id = approve_script_and_create_video(api)
        response = api.get(f"/api/video-jobs/{video_job_id}")
        assert response.json()["status"] == "video_generation_queued"


def test_mock_video_assembly_path_creation():
    with client() as api:
        video_job_id = approve_script_and_create_video(api)
        response = api.post(f"/api/video-jobs/{video_job_id}/run")
        assert response.status_code == 200
        output_path = Path(response.json()["output_video_path"])
        assert output_path.exists()


def test_publishing_package_generation():
    with client() as api:
        video_job_id = approve_script_and_create_video(api)
        api.post(f"/api/video-jobs/{video_job_id}/run")
        api.post(f"/api/video-jobs/{video_job_id}/approve")
        response = api.post("/api/publishing-packages", json={"video_job_id": video_job_id, "target_platform": "Instagram Reels"})
        assert response.status_code == 200
        assert response.json()["utm_url"].endswith("utm_source=instagram_reels&utm_medium=social_video&utm_campaign=qharisma_video_factory")


def test_warmup_scheduler_allows_valid_schedule():
    with client() as api:
        package_id, account_id = create_approved_package(api)
        response = api.post(
            "/api/publishing-jobs/schedule",
            json={
                "publishing_package_id": package_id,
                "account_id": account_id,
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
                "provider": "mock",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "scheduled"


def test_warmup_scheduler_blocks_over_limit_posts():
    with client() as api:
        package_id, account_id = create_approved_package(api)
        scheduled_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        first = api.post(
            "/api/publishing-jobs/schedule",
            json={
                "publishing_package_id": package_id,
                "account_id": account_id,
                "scheduled_at": scheduled_at.isoformat(),
                "provider": "mock",
            },
        )
        assert first.status_code == 200, first.text
        blocked = api.post(
            "/api/publishing-jobs/schedule",
            json={
                "publishing_package_id": package_id,
                "account_id": account_id,
                "scheduled_at": (scheduled_at + timedelta(hours=1)).isoformat(),
                "provider": "mock",
            },
        )
        assert blocked.status_code == 400
        assert "Daily warm-up limit reached" in blocked.json()["detail"]


def test_mock_upload_provider_publishing():
    with client() as api:
        package_id, account_id = create_approved_package(api)
        schedule = api.post(
            "/api/publishing-jobs/schedule",
            json={
                "publishing_package_id": package_id,
                "account_id": account_id,
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
                "provider": "mock",
            },
        )
        job_id = schedule.json()["id"]
        published = api.post(f"/api/publishing-jobs/{job_id}/run")
        assert published.status_code == 200
        assert published.json()["status"] == "published"
        assert published.json()["provider_post_url"].startswith("https://mock.social/posts/")


def test_manual_upload_status_update():
    with client() as api:
        package_id, account_id = create_approved_package(api)
        schedule = api.post(
            "/api/publishing-jobs/schedule",
            json={
                "publishing_package_id": package_id,
                "account_id": account_id,
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
                "provider": "manual",
                "manual_override": True,
            },
        )
        job_id = schedule.json()["id"]
        manual = api.post(f"/api/publishing-jobs/{job_id}/run")
        assert manual.json()["status"] == "manual_upload_required"
        done = api.post(
            f"/api/publishing-jobs/{job_id}/mark-manual-uploaded",
            json={"provider_post_url": "https://example.com/post/manual-1", "operator_name": "ops"},
        )
        assert done.status_code == 200
        assert done.json()["status"] == "published_manual"


def test_create_publishing_destination():
    with client() as api:
        response = api.post(
            "/api/publishing/destinations",
            json={
                "brand": "Altea",
                "platform": "telegram",
                "name": "Altea Telegram",
                "posting_mode": "manual",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "Altea Telegram"
        assert payload["auth_status"] == "manual_only"
        assert payload["status"] == "active"


def test_destination_readiness_manual_mode_ready():
    with client() as api:
        destination = api.post(
            "/api/publishing/destinations",
            json={"brand": "Altea", "platform": "telegram", "name": "Altea Telegram", "posting_mode": "manual"},
        )

        response = api.post(f"/api/publishing/destinations/{destination.json()['id']}/readiness-check")

        assert response.status_code == 200, response.text
        assert response.json()["ready"] is True
        assert response.json()["blockers"] == []


def test_bulk_import_publishing_destinations():
    csv_text = (
        "brand,platform,name,handle,posting_mode,daily_limit,weekly_limit\n"
        "Altea,telegram,Altea Telegram,@altea,manual,1,3\n"
        "Altea,youtube,Altea YouTube,@altea_video,manual,2,6\n"
    )
    with client() as api:
        response = api.post(
            "/api/publishing/destinations/import-csv",
            files={"file": ("destinations.csv", csv_text, "text/csv")},
        )

        assert response.status_code == 200, response.text
        assert response.json()["created_count"] == 2
        assert response.json()["error_count"] == 0
        assert len(response.json()["destination_ids"]) == 2


def test_api_mode_destination_requires_token_valid():
    with client() as api:
        destination = api.post(
            "/api/publishing/destinations",
            json={
                "brand": "Altea",
                "platform": "youtube",
                "name": "Altea YouTube",
                "posting_mode": "api",
                "auth_status": "not_configured",
            },
        )

        response = api.post(f"/api/publishing/destinations/{destination.json()['id']}/readiness-check")

        assert response.status_code == 200, response.text
        assert response.json()["ready"] is False
        assert "API posting requires configured valid platform credentials." in response.json()["blockers"]


def test_create_publishing_package_from_video_artifact():
    with client() as api:
        video_job_id = approve_script_and_create_video(api)
        api.post(f"/api/video-jobs/{video_job_id}/run")
        api.post(f"/api/video-jobs/{video_job_id}/approve")

        response = api.post("/api/publishing/packages", json={"video_job_id": video_job_id, "platform": "telegram"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["video_job_id"] == video_job_id
        assert payload["video_file_path"]
        assert payload["review_status"] == "approved"
        assert payload["status"] == "ready"


def test_package_requires_approval_before_schedule():
    with client() as api:
        video_job_id = approve_script_and_create_video(api)
        api.post(f"/api/video-jobs/{video_job_id}/run")
        api.post(f"/api/video-jobs/{video_job_id}/approve")
        package = api.post("/api/publishing/packages", json={"video_job_id": video_job_id, "platform": "telegram"})
        destination = api.post(
            "/api/publishing/destinations",
            json={"brand": "Altea", "platform": "telegram", "name": "Altea Telegram", "posting_mode": "manual"},
        )

        blocked = api.post(
            "/api/publishing/tasks/schedule",
            json={
                "publishing_package_id": package.json()["id"],
                "destination_id": destination.json()["id"],
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
            },
        )

        assert blocked.status_code == 400
        assert "must be approved" in blocked.json()["detail"]


def test_unapproved_quality_review_blocks_auto_package_approval(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Publishing Review Gate Variant")
        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)

        package = api.post("/api/publishing/packages", json={"video_job_id": output.video_job_id, "platform": "telegram"})
        assert package.status_code == 200, package.text
        assert package.json()["review_status"] == "needs_review"

        blocked = api.post(f"/api/publishing/packages/{package.json()['id']}/approve", json={"reviewer_name": "ops"})

        assert blocked.status_code == 400
        assert "QualityReview is not approved" in blocked.json()["detail"]


def test_scheduler_blocks_inactive_destination():
    with client() as api:
        package_id, destination_id = create_safe_approved_package_and_destination(api)
        patch = api.patch(f"/api/publishing/destinations/{destination_id}", json={"status": "paused"})
        assert patch.status_code == 200, patch.text

        blocked = api.post(
            "/api/publishing/tasks/schedule",
            json={
                "publishing_package_id": package_id,
                "destination_id": destination_id,
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
            },
        )

        assert blocked.status_code == 400
        assert "Destination must be active" in blocked.json()["detail"]


def test_scheduler_blocks_daily_limit():
    with client() as api:
        package_id, destination_id = create_safe_approved_package_and_destination(api, daily_limit=1)
        scheduled_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        first = api.post(
            "/api/publishing/tasks/schedule",
            json={
                "publishing_package_id": package_id,
                "destination_id": destination_id,
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        assert first.status_code == 200, first.text
        second = api.post(
            "/api/publishing/tasks/schedule",
            json={
                "publishing_package_id": package_id,
                "destination_id": destination_id,
                "scheduled_at": (scheduled_at + timedelta(hours=1)).isoformat(),
            },
        )

        assert second.status_code == 400
        assert "Daily publishing limit reached" in second.json()["detail"]


def test_bulk_schedule_distributes_approved_packages_only():
    with client() as api:
        package_id_1, destination_id_1 = create_safe_approved_package_and_destination(api, title="Bulk Package One")
        package_id_2, destination_id_2 = create_safe_approved_package_and_destination(api, title="Bulk Package Two")

        response = api.post(
            "/api/publishing/tasks/bulk-schedule",
            json={
                "publishing_package_ids": [package_id_1, package_id_2],
                "destination_ids": [destination_id_1, destination_id_2],
                "start_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
                "interval_minutes": 90,
                "operator_name": "ops",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["created_count"] == 2
        assert payload["error_count"] == 0
        assert len(payload["task_ids"]) == 2


def test_bulk_schedule_blocks_unapproved_package():
    with client() as api:
        video_job_id = approve_script_and_create_video(api)
        api.post(f"/api/video-jobs/{video_job_id}/run")
        api.post(f"/api/video-jobs/{video_job_id}/approve")
        package = api.post("/api/publishing/packages", json={"video_job_id": video_job_id, "platform": "telegram"})
        destination = api.post(
            "/api/publishing/destinations",
            json={"brand": "Altea", "platform": "telegram", "name": "Altea Telegram", "posting_mode": "manual"},
        )

        response = api.post(
            "/api/publishing/tasks/bulk-schedule",
            json={
                "publishing_package_ids": [package.json()["id"]],
                "destination_ids": [destination.json()["id"]],
                "start_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
                "interval_minutes": 90,
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["created_count"] == 0
        assert response.json()["error_count"] == 1
        assert "PublishingPackage must be approved" in response.json()["errors"][0]["error"]


def test_manual_upload_task_created():
    with client() as api:
        package_id, destination_id = create_safe_approved_package_and_destination(api)
        schedule = api.post(
            "/api/publishing/tasks/schedule",
            json={
                "publishing_package_id": package_id,
                "destination_id": destination_id,
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
            },
        )
        task_id = schedule.json()["id"]

        task = api.post(f"/api/publishing/tasks/{task_id}/run")

        assert task.status_code == 200, task.text
        assert task.json()["status"] == "manual_upload_required"
        assert task.json()["raw_response_json"]["manual_upload"]["video_file_path"]


def test_mark_manual_upload_published_stores_final_url():
    with client() as api:
        package_id, destination_id = create_safe_approved_package_and_destination(api)
        schedule = api.post(
            "/api/publishing/tasks/schedule",
            json={
                "publishing_package_id": package_id,
                "destination_id": destination_id,
                "scheduled_at": (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
            },
        )
        task_id = schedule.json()["id"]
        api.post(f"/api/publishing/tasks/{task_id}/run")

        response = api.post(
            f"/api/publishing/tasks/{task_id}/mark-manual-uploaded",
            json={"final_url": "https://example.com/post", "operator_name": "ops"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "published_manual"
        assert response.json()["final_url"] == "https://example.com/post"


def test_mock_upload_provider_returns_fake_url():
    result = MockUploadProvider().upload({"id": 123})

    assert result["status"] == "published_api"
    assert result["final_url"].startswith("https://mock.social/posts/")


def test_publishing_ui_renders():
    with client() as api:
        response = api.get("/publishing")

        assert response.status_code == 200, response.text
        assert "Publishing" in response.text
        assert "Destinations" in response.text
        assert "Manual Upload" in response.text


def test_engine_full_demo_pipeline():
    with client() as api:
        product_id = create_product(api, title="Engine Demo Product")
        create_guide(api)
        create_template(api)
        create_account(api)
        create_warmup_plan(api)

        with SessionLocal() as db:
            result = VideoFactoryEngine(db).run_full_demo(product_id)

        assert result.status == "completed"
        assert result.script_job_id is not None
        assert result.script_variant_id is not None
        assert result.video_job_id is not None
        assert result.publishing_package_id is not None
        assert result.publishing_job_id is not None
        assert result.analytics_id is not None
        assert [step.step_name for step in result.steps] == [
            "generate_script",
            "approve_script_variant",
            "generate_video",
            "approve_video",
            "create_publishing_package",
            "approve_publishing_package",
            "schedule_publishing",
            "run_upload",
            "collect_analytics",
        ]


def test_engine_creates_script_video_package_job_analytics():
    with client() as api:
        product_id = create_product(api, title="Engine Entity Product")
        create_guide(api)
        create_template(api)
        create_account(api)
        create_warmup_plan(api)

        with SessionLocal() as db:
            result = VideoFactoryEngine(db).run_full_demo(product_id)
            script_job = db.get(models.ScriptJob, result.script_job_id)
            video_job = db.get(models.VideoJob, result.video_job_id)
            package = db.get(models.PublishingPackage, result.publishing_package_id)
            publishing_job = db.get(models.PublishingJob, result.publishing_job_id)
            analytics = db.get(models.PublishAnalytics, result.analytics_id)

        assert script_job is not None
        assert video_job is not None
        assert package is not None
        assert publishing_job is not None
        assert analytics is not None
        assert publishing_job.status == "published"
        assert publishing_job.provider_post_url.startswith("https://mock.social/posts/")
        assert analytics.views > 0


def test_engine_blocks_when_no_product():
    with client():
        with SessionLocal() as db:
            result = VideoFactoryEngine(db).run_full_demo(product_id=999)

        assert result.status == "failed"
        assert result.errors
        assert "Product 999 not found" in result.errors[0]


def test_engine_api_run_demo():
    with client() as api:
        product_id = create_product(api, title="Engine API Product")
        create_guide(api)
        create_template(api)
        account_id = create_account(api)
        create_warmup_plan(api)

        response = api.post("/api/engine/run-demo", json={"product_id": product_id, "account_id": account_id})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["publishing_job_id"] is not None
        assert payload["analytics_id"] is not None
        status = api.get(f"/api/engine/status/{payload['publishing_job_id']}")
        assert status.status_code == 200
        assert status.json()["provider_post_url"].startswith("https://mock.social/posts/")


def test_intelligence_pack_uses_metrics_and_reviews():
    with client() as api:
        product_id = create_product(api, title="Generator Review Product")
        create_guide(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku, ctr=0.035, conversion_rate=0.02)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)

        pack = record.pack_json
        assert "low_conversion" in pack["performance_flags"]
        assert "why is it better than cheaper options?" in pack["buyer_objections"]
        assert pack["source_map"]["latest_metric"] is not None


def test_low_ctr_recommends_hook_angle():
    with client() as api:
        product_id = create_product(api, title="Low CTR Product")
        create_guide(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku, ctr=0.01, conversion_rate=0.08)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)

        assert record.pack_json["recommended_objective"] == "improve_clickability"
        assert "strong_hook" in record.pack_json["recommended_creative_angles"]


def test_low_conversion_recommends_objection_handling():
    with client() as api:
        product_id = create_product(api, title="Low Conversion Product")
        create_guide(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku, ctr=0.04, conversion_rate=0.01)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)

        assert record.pack_json["recommended_objective"] == "improve_conversion"
        assert "objection_handling" in record.pack_json["recommended_creative_angles"]


def test_stock_risk_blocks_aggressive_push():
    with client() as api:
        product_id = create_product(api, title="Low Stock Product")
        create_guide(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku, stock_qty=5, days_of_stock=5)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)
            brief = ScriptBriefBuilder(db).build_from_record(record.id)

        assert "stock_risk" in record.pack_json["performance_flags"]
        assert "aggressive demand generation" in brief.brief_json["must_avoid"]


def test_script_brief_contains_allowed_claim_source_refs():
    with client() as api:
        product_id = create_product(api, title="Source Ref Product", benefits=["keeps essentials visible"])
        create_guide(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)
            brief = ScriptBriefBuilder(db).build_from_record(record.id)

        assert brief.allowed_claims_json
        assert brief.allowed_claims_json[0]["source_type"] == "product_field"
        assert brief.allowed_claims_json[0]["source_key"] == "description"


def test_llm_provider_missing_key_fails_in_openai_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY is missing"):
        OpenAILLMProvider()


def test_prompt_pack_contains_provider_ready_scene_prompts():
    with client() as api:
        product_id = create_product(api, title="Prompt Pack Product")
        create_guide(api)
        create_template(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku)

        with SessionLocal() as db:
            pack = CreativeIntelligenceBuilder(db).build_for_product(product_id)
            brief = ScriptBriefBuilder(db).build_from_record(pack.id)
            script_job = GeneratorScriptService(db).generate_from_brief(brief.id, "mock")
            variant = sorted(script_job.variants, key=lambda item: item.variant_number)[0]
            prompt_pack = PromptPackBuilder(db).build_for_script(variant.id, "runway", brief.id)

        assert prompt_pack.prompt_pack_json["provider"] == "runway"
        assert prompt_pack.scene_prompts_json
        assert prompt_pack.scene_prompts_json[0]["prompt_text"]
        assert prompt_pack.provider_payload_json["ratio"] == "720:1280"


def test_generator_api_builds_intelligence_and_prompt_pack():
    with client() as api:
        product_id = create_product(api, title="Generator API Product")
        create_guide(api)
        create_template(api)
        sku = product_sku(api, product_id)
        add_generator_snapshots(sku)

        intelligence = api.post("/api/generator/intelligence/build", json={"product_id": product_id})
        assert intelligence.status_code == 200, intelligence.text
        brief = api.post("/api/generator/script-briefs", json={"intelligence_pack_id": intelligence.json()["id"]})
        assert brief.status_code == 200, brief.text
        script = api.post("/api/generator/scripts/generate", json={"script_brief_id": brief.json()["id"], "llm_provider": "mock"})
        assert script.status_code == 200, script.text
        prompt_pack = api.post(
            "/api/generator/prompt-packs",
            json={
                "script_variant_id": script.json()["script_variant_id"],
                "script_brief_id": brief.json()["id"],
                "provider": "runway",
            },
        )
        assert prompt_pack.status_code == 200, prompt_pack.text
        assert prompt_pack.json()["prompt_pack"]["scene_prompts"]


def test_real_video_provider_missing_key_fails_in_runway_mode(monkeypatch):
    monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)
    with pytest.raises(ProviderConfigurationError, match="RUNWAYML_API_SECRET is missing"):
        RunwayVideoProvider()


def test_openai_network_error_fails_clearly(monkeypatch):
    def raise_connect_error(*args, **kwargs):
        raise httpx.ConnectError("TLS handshake failed")

    monkeypatch.setattr("app.providers.openai_llm.httpx.post", raise_connect_error)
    brief = ScriptBriefOutput(
        sku="SKU-OPENAI-NETWORK",
        product_title="Network Test Product",
        objective="improve_conversion",
        creative_angle="trust_builder",
        reasoning_summary="Use only source-backed claims.",
    )

    with pytest.raises(ProviderConfigurationError, match="OpenAI structured script request failed"):
        OpenAILLMProvider(api_key="test-key").generate_script(brief)


def test_openai_structured_output_schema_is_strict():
    schema = OpenAILLMProvider._strict_json_schema(GeneratedScriptOutput.model_json_schema())

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    for definition in schema["$defs"].values():
        if "properties" in definition:
            assert definition["additionalProperties"] is False
            assert set(definition["required"]) == set(definition["properties"])


def test_claim_refs_accept_source_type_source_key_format():
    brief = ScriptBriefOutput(
        sku="SKU-CLAIM-REF",
        product_title="Claim Ref Product",
        objective="improve_conversion",
        creative_angle="trust_builder",
        reasoning_summary="Use source-backed claims.",
        allowed_claims=[
            AllowedClaim(claim="keeps essentials visible", source_type="product_field", source_key="description")
        ],
    )
    script = GeneratedScriptOutput(
        creative_angle="trust_builder",
        hook="Proof first",
        key_message="keeps essentials visible",
        final_cta="Open the product card",
        scenes=[
            GeneratedSceneOutput(
                scene_number=1,
                time_start=0,
                time_end=5,
                visual_description="Show the product clearly.",
                voiceover="keeps essentials visible",
                caption="Visible essentials",
                claim_refs=["product_field:description"],
                video_prompt="Realistic product video",
                negative_prompt="distorted product",
            )
        ],
    )

    assert validate_script_claim_refs(script, brief)["valid"] is True


def test_claim_refs_reject_wrong_source_type_prefix():
    brief = ScriptBriefOutput(
        sku="SKU-CLAIM-REF-REJECT",
        product_title="Claim Ref Reject Product",
        objective="improve_conversion",
        creative_angle="trust_builder",
        reasoning_summary="Use source-backed claims.",
        allowed_claims=[
            AllowedClaim(claim="keeps essentials visible", source_type="product_field", source_key="description")
        ],
    )
    script = GeneratedScriptOutput(
        creative_angle="trust_builder",
        hook="Proof first",
        key_message="keeps essentials visible",
        final_cta="Open the product card",
        scenes=[
            GeneratedSceneOutput(
                scene_number=1,
                time_start=0,
                time_end=5,
                visual_description="Show the product clearly.",
                voiceover="keeps essentials visible",
                caption="Visible essentials",
                claim_refs=["review:description"],
                video_prompt="Realistic product video",
                negative_prompt="distorted product",
            )
        ],
    )

    with pytest.raises(ClaimValidationError):
        validate_script_claim_refs(script, brief)


def test_runway_network_error_fails_clearly(monkeypatch):
    def raise_connect_error(*args, **kwargs):
        raise httpx.ConnectError("TLS handshake failed")

    monkeypatch.setattr("app.providers.runway_video.httpx.post", raise_connect_error)
    prompt_pack = PromptPackOutput(
        provider="runway",
        aspect_ratio="9:16",
        duration_seconds=5,
        scene_prompts=[
            PromptSceneOutput(
                scene_number=1,
                duration_seconds=5,
                prompt_text="Realistic product video",
                negative_prompt="distorted product",
            )
        ],
    )

    with pytest.raises(ProviderConfigurationError, match="Runway generation request failed"):
        RunwayVideoProvider(api_secret="test-key").create_generation(prompt_pack)


def test_real_run_requires_allow_spend_true(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "false")
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_generator_product(api, title="Spend Gate Product")

        response = api.post(
            "/api/generator/run-real",
            json={
                "product_id": product_id,
                "llm_provider": "mock",
                "video_provider": "runway",
                "confirm_real_spend": True,
            },
        )

        assert response.status_code == 400
        assert "QVF_ALLOW_REAL_SPEND=true" in response.json()["detail"]


def test_real_run_openai_missing_key_fails_clearly(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_generator_product(api, title="Missing OpenAI Product")

        response = api.post(
            "/api/generator/run-real",
            json={
                "product_id": product_id,
                "llm_provider": "openai",
                "video_provider": "mock",
                "confirm_real_spend": True,
            },
        )

        assert response.status_code == 400
        assert "OPENAI_API_KEY is missing" in response.json()["detail"]


def test_real_run_runway_missing_key_fails_clearly(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_generator_product(api, title="Missing Runway Product")

        response = api.post(
            "/api/generator/run-real",
            json={
                "product_id": product_id,
                "llm_provider": "mock",
                "video_provider": "runway",
                "confirm_real_spend": True,
            },
        )

        assert response.status_code == 400
        assert "RUNWAYML_API_SECRET is missing" in response.json()["detail"]


def test_real_run_preflights_runway_before_openai(monkeypatch):
    def fail_if_openai_is_instantiated(*args, **kwargs):
        raise AssertionError("OpenAI should not be called when Runway preflight fails.")

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)
    monkeypatch.setattr("app.intelligence.script_generator.OpenAILLMProvider", fail_if_openai_is_instantiated)
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_generator_product(api, title="Runway Preflight Product")

        response = api.post(
            "/api/generator/run-real",
            json={
                "product_id": product_id,
                "llm_provider": "openai",
                "video_provider": "runway",
                "confirm_real_spend": True,
            },
        )

        assert response.status_code == 400
        assert "RUNWAYML_API_SECRET is missing" in response.json()["detail"]
        with SessionLocal() as db:
            assert db.query(models.ScriptJob).count() == 0


def test_prompt_only_never_calls_video_provider(monkeypatch):
    def fail_if_instantiated(*args, **kwargs):
        raise AssertionError("Video provider should not be called in prompt-only mode.")

    monkeypatch.setattr("app.intelligence.video_generator.RunwayVideoProvider", fail_if_instantiated)
    with client() as api:
        product_id = prepare_generator_product(api, title="Prompt Only Product")

        with SessionLocal() as db:
            artifacts = GeneratorRunService(db).build_prompt_pack_only(
                product_id=product_id,
                llm_provider="mock",
                video_provider="runway",
            )

        assert artifacts.prompt_pack.prompt_pack_json["provider"] == "runway"
        assert artifacts.video_job is None


def test_real_run_limited_to_one_scene_by_default(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_generator_product(api, title="One Scene Product")

        response = api.post(
            "/api/generator/run-real",
            json={"product_id": product_id, "llm_provider": "mock", "video_provider": "mock"},
        )

        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            video_job = db.get(models.VideoJob, response.json()["video_job_id"])
            assert len(video_job.clips) == 1


def test_generation_report_created_for_mock_real_mode(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_generator_product(api, title="Report Product")

        response = api.post(
            "/api/generator/run-real",
            json={"product_id": product_id, "llm_provider": "mock", "video_provider": "mock"},
        )

        assert response.status_code == 200, response.text
        report_path = Path(response.json()["report_path"])
        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["product_id"] == product_id
        assert report["video_job_id"] == response.json()["video_job_id"]
        assert report["video_provider"] == "mock"
        assert report["provider_job_ids"]
        assert report["local_output_paths"]
        assert report["final_video_path"]


def test_generator_ui_shows_provider_key_status_without_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "runway-test-secret-value")
    get_settings.cache_clear()
    with client() as api:
        response = api.get("/generator")

        assert response.status_code == 200
        assert "OpenAI key" in response.text
        assert "Runway key" in response.text
        assert "configured" in response.text
        assert "sk-test-secret-value" not in response.text
        assert "runway-test-secret-value" not in response.text


def test_video_generator_ui_renders_creative_tz_and_generate_blocks():
    with client() as api:
        response = api.get("/video-generator")

        assert response.status_code == 200
        assert "Creative TZ" in response.text
        assert "Generate Video" in response.text


def test_hook_strategy_low_ctr_selects_curiosity_and_benefit_first():
    with client() as api:
        product_id = create_product(api, title="Low CTR Hook Product")
        create_guide(api)
        add_generator_snapshots(product_sku(api, product_id), ctr=0.01, conversion_rate=0.08)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)

        pack = CreativeIntelligencePack.model_validate(record.pack_json)
        hook_types = [candidate.hook_type for candidate in HookStrategySelector().select(pack)]
        assert "curiosity_gap" in hook_types
        assert "benefit_first_frame" in hook_types
        assert len(hook_types) == 3


def test_hook_strategy_low_conversion_selects_objection_handling():
    with client() as api:
        product_id = create_product(api, title="Low Conversion Hook Product")
        create_guide(api)
        add_generator_snapshots(product_sku(api, product_id), ctr=0.04, conversion_rate=0.01)

        with SessionLocal() as db:
            record = CreativeIntelligenceBuilder(db).build_for_product(product_id)

        pack = CreativeIntelligencePack.model_validate(record.pack_json)
        hook_types = [candidate.hook_type for candidate in HookStrategySelector().select(pack)]
        assert hook_types[0] == "objection_handling"


def test_creative_spec_has_first_frame_and_product_rules():
    with client() as api:
        _, _, spec = build_creative_spec_fixture(api, title="First Frame Spec Product")

        assert spec.first_frame_spec.product_visible_by_second <= 1.5
        assert spec.first_frame_spec.visual_hook
        assert spec.first_frame_spec.text_overlay
        assert any("first frame" in rule.lower() for rule in spec.product_display_rules)
        assert any("hallucinate packaging" in rule.lower() for rule in spec.product_display_rules)


def test_product_geometry_rules_added_to_creative_spec():
    with client() as api:
        _, _, spec = build_creative_spec_fixture(api, title="Geometry Spec Product")

        assert spec.product_geometry_spec.geometry_lock_enabled is True
        assert spec.product_geometry_spec.preserve_silhouette is True
        assert spec.product_geometry_spec.preserve_height_width_ratio is True
        assert spec.product_geometry_rules["preserve_reference_silhouette"] is True
        assert spec.product_geometry_rules["preserve_cap_size_and_position"] is True
        assert spec.product_scale_rules["product_should_occupy_percent_of_frame"] == "25-40%"
        assert spec.product_scale_rules["product_scale_relative_to_hand"] == "natural cosmetic bottle scale"
        assert spec.product_visibility_rules["product_face_label_visible"] is True


def test_creative_spec_claims_have_source_refs():
    with client() as api:
        _, _, spec = build_creative_spec_fixture(api, title="Claim Ref Spec Product")

        assert spec.allowed_claim_refs
        allowed_refs = set(spec.allowed_claim_refs)
        for scene in spec.scene_plan:
            if scene.role != "cta":
                assert scene.claim_refs
                assert set(scene.claim_refs).issubset(allowed_refs)


def test_creative_spec_validation_blocks_missing_captions():
    with client() as api:
        _, _, spec = build_creative_spec_fixture(api, title="Missing Caption Spec Product")
        broken_scene = spec.scene_plan[0].model_copy(update={"caption": ""})
        broken = spec.model_copy(update={"scene_plan": [broken_scene, *spec.scene_plan[1:]]})

        report = CreativeSpecValidator().validate(broken)

        assert report.valid is False
        assert any("missing caption" in error.lower() for error in report.errors)


def test_creative_spec_duration_matches_scene_sum():
    with client() as api:
        _, _, spec = build_creative_spec_fixture(api, title="Duration Spec Product", duration=15)

        assert sum(scene.duration_seconds for scene in spec.scene_plan) == spec.duration_seconds


def test_prompt_pack_from_spec_contains_first_frame_requirements():
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Prompt First Frame Product")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_spec(spec_id, provider="runway")

        first_scene = variant.prompt_pack_json["scene_prompts"][0]
        assert first_scene["first_frame_requirements"]["product_visible_by_second"] <= 1.5
        assert first_scene["caption_text"]
        assert first_scene["product_accuracy_rules"]


def test_prompt_pack_contains_geometry_lock_constraints():
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Geometry Prompt Product")

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        prompt_pack = generation_variant.prompt_pack_json
        first_scene = prompt_pack["scene_prompts"][0]
        for line in GEOMETRY_LOCK_PROMPT_LINES:
            assert line in first_scene["prompt_text"]
            assert line in first_scene["safety_constraints"]
        assert prompt_pack["product_geometry_rules"]["preserve_reference_silhouette"] is True
        assert prompt_pack["product_scale_rules"]["product_scale_relative_to_hand"] == "natural cosmetic bottle scale"
        assert prompt_pack["product_visibility_rules"]["avoid_occluding_cap_or_label"] is True


def test_negative_prompt_blocks_size_and_proportion_drift():
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Geometry Negative Product")

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        negative_prompt = generation_variant.prompt_pack_json["scene_prompts"][0]["negative_prompt"]
        for term in GEOMETRY_NEGATIVE_TERMS:
            assert term in negative_prompt


def test_prompt_pack_includes_reference_image_warning_when_missing():
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Missing Reference Product")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_spec(spec_id, provider="runway")

        assert "No reference images supplied" in variant.prompt_pack_json["warnings"][0]
        assert all(scene["reference_images"] == [] for scene in variant.prompt_pack_json["scene_prompts"])


def test_video_generator_prompt_only_does_not_call_provider(monkeypatch):
    def fail_if_instantiated(*args, **kwargs):
        raise AssertionError("Video provider should not be called when only building prompts from a creative spec.")

    monkeypatch.setattr("app.intelligence.video_generator.RunwayVideoProvider", fail_if_instantiated)
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Spec Prompt Only Product")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_spec(spec_id, provider="runway")

        assert variant.status == "prompt_pack_ready"
        assert variant.video_job_id is None


def test_video_quality_score_is_metadata_based_and_honest():
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Metadata Quality Product")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_spec(spec_id, provider="mock")
            review = VideoGenerator(db).score(variant.id)

        assert review.status == "metadata_scored"
        assert any("No computer vision" in note for note in review.review_json["notes"])
        assert all(check["check_type"] == "metadata" for check in review.review_json["checks"])


def test_regenerate_scene_creates_new_prompt_for_one_scene_only():
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Regenerate Scene Product")

        with SessionLocal() as db:
            generator = VideoGenerator(db)
            variant = generator.build_prompt_pack_from_spec(spec_id, provider="mock")
            before = {
                scene["scene_number"]: scene["prompt_text"]
                for scene in variant.prompt_pack_json["scene_prompts"]
            }
            changed = generator.regenerate_scene(variant.id, 2)
            db.refresh(variant)
            after = {
                scene["scene_number"]: scene["prompt_text"]
                for scene in variant.prompt_pack_json["scene_prompts"]
            }

        assert "Regeneration pass" in changed["prompt_text"]
        assert after[2] != before[2]
        assert after[1] == before[1]
        assert after[3] == before[3]
        assert after[4] == before[4]


def test_regeneration_request_accepts_product_geometry_mismatch():
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Geometry Request Product")

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_spec(spec_id, provider="mock")
            video_job = models.VideoJob(
                script_variant_id=generation_variant.script_variant_id,
                provider="mock",
                status="needs_human_review",
            )
            db.add(video_job)
            db.flush()
            generation_variant.video_job_id = video_job.id
            db.commit()
            request = RegenerationRequestService(db).create(
                video_job_id=video_job.id,
                scene_number=1,
                reason="product_geometry_mismatch",
                feedback="Product size/proportions drifted; preserve exact bottle silhouette.",
            )

        assert request.reason == "product_geometry_mismatch"
        assert request.status == "requested"
        assert request.video_generation_variant_id == generation_variant.id


def test_regeneration_prompt_includes_geometry_corrections():
    with client() as api:
        _, spec_id, _ = build_creative_spec_fixture(api, title="Geometry Regeneration Product")

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_spec(spec_id, provider="mock")
            video_job = models.VideoJob(
                script_variant_id=generation_variant.script_variant_id,
                provider="mock",
                status="needs_human_review",
            )
            db.add(video_job)
            db.flush()
            generation_variant.video_job_id = video_job.id
            db.commit()
            service = RegenerationRequestService(db)
            request = service.create(
                video_job_id=video_job.id,
                scene_number=1,
                reason="product_geometry_mismatch",
                feedback=(
                    "Product size/proportions drifted; preserve exact bottle silhouette, "
                    "height-width ratio, cap/dropper size and label area."
                ),
            )
            request = service.build_prompt_only(request.id)
            changed_scene = request.prompt_only_output_json["scene_prompt"]
            db.refresh(generation_variant)

        assert request.status == "prompt_ready"
        assert "Geometry correction" in changed_scene["prompt_text"]
        assert "Keep the product the same size and proportions as the primary reference image." in changed_scene["prompt_text"]
        assert "Preserve height-to-width ratio." in changed_scene["prompt_text"]
        assert "changed product size" in changed_scene["negative_prompt"]
        assert "wrong proportions" in changed_scene["negative_prompt"]
        assert generation_variant.status == "prompt_pack_ready"


def test_video_generator_api_build_spec_and_prompt_pack():
    with client() as api:
        product_id = prepare_generator_product(api, title="Video Generator API Product")

        spec_response = api.post(
            "/api/creative/specs/build",
            json={"product_id": product_id, "platform": "Instagram Reels", "duration": 15},
        )
        assert spec_response.status_code == 200, spec_response.text
        assert spec_response.json()["status"] == "ready"

        prompt_response = api.post(
            "/api/video-generator/prompt-packs/from-spec",
            json={"creative_spec_id": spec_response.json()["id"], "video_provider": "mock"},
        )
        assert prompt_response.status_code == 200, prompt_response.text
        assert prompt_response.json()["status"] == "prompt_pack_ready"
        assert prompt_response.json()["prompt_pack"]["scene_prompts"][0]["first_frame_requirements"]


def test_asset_kit_builds_from_product_images_json():
    with client() as api:
        product_id = create_product(
            api,
            title="Asset Kit Product",
            images=[
                "https://example.com/packshot_front.jpg",
                "https://example.com/label_closeup.png",
                "https://example.com/lifestyle_use.jpg",
            ],
        )

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id)

        assert kit.status == "ready"
        assert len(kit.assets_json) == 3
        assert {asset["asset_type"] for asset in kit.assets_json} >= {"packshot", "label_closeup", "lifestyle"}
        assert kit.real_generation_allowed is True


def test_asset_kit_warns_when_no_reference_images():
    with client() as api:
        product_id = create_product(api, title="No Reference Product")

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id)

        assert kit.status == "needs_assets"
        assert "No product reference images available." in kit.warnings_json
        assert "packshot" in kit.missing_assets_json


def test_asset_validator_blocks_real_generation_without_required_packshot():
    report = AssetValidator().validate(
        [
            ProductAssetDescriptor(
                source_ref="https://example.com/lifestyle_use.jpg",
                source_type="url",
                asset_type="lifestyle",
                filename="lifestyle_use.jpg",
                extension=".jpg",
                mime_type="image/jpeg",
                exists=True,
            )
        ],
        require_real_generation=True,
    )

    assert report.valid is False
    assert any("packshot" in error.lower() for error in report.errors)
    assert report.real_generation_allowed is False


def test_first_frame_builder_creates_three_options():
    with client() as api:
        product_id, spec_id, _ = build_creative_spec_fixture(
            api,
            title="First Frame Options Product",
            images=["https://example.com/packshot_front.jpg"],
        )

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id, override_required_assets=True)
            options = FirstFrameBuilder(db).build_options(spec_id, asset_kit_id=kit.id)

        assert len(options) == 3
        assert all(option.hook_text for option in options)
        assert all(option.required_assets_json for option in options)


def test_first_frame_option_has_product_visible_by_second():
    with client() as api:
        product_id, spec_id, _ = build_creative_spec_fixture(
            api,
            title="Visible First Second Product",
            images=["https://example.com/packshot_front.jpg"],
        )

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id, override_required_assets=True)
            option = FirstFrameBuilder(db).build_options(spec_id, asset_kit_id=kit.id)[0]

        assert option.product_visible_by_second <= 1.0
        assert option.option_json["product_visible_by_second"] <= 1.0


def test_variant_builder_creates_multiple_variants():
    with client() as api:
        product_id, spec_id, _ = build_creative_spec_fixture(
            api,
            title="Multiple Variant Product",
            images=[
                "https://example.com/packshot_front.jpg",
                "https://example.com/label_closeup.png",
                "https://example.com/lifestyle_use.jpg",
            ],
        )

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id)
            variant_set = CreativeVariantBuilder(db).build_set(spec_id, count=5, asset_kit_id=kit.id)
            variant_count = len(variant_set.variants)
            pacing_names = {variant.pacing_json["name"] for variant in variant_set.variants}

        assert variant_set.variant_count == 5
        assert variant_count == 5
        assert len(pacing_names) > 1


def test_variant_scorer_penalizes_missing_assets():
    with client() as api:
        product_id, spec_id, _ = build_creative_spec_fixture(api, title="Missing Assets Variant Product")

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id)
            variant_set = CreativeVariantBuilder(db).build_set(spec_id, count=2, asset_kit_id=kit.id)
            VariantScorer(db).score_set(variant_set.id)
            variant = sorted(variant_set.variants, key=lambda item: item.variant_number)[0]

        assert variant.score_json["dimensions"]["asset_readiness"] < 0.5
        assert "missing_product_reference_assets" in variant.risk_flags_json


def test_variant_scorer_boosts_matching_low_ctr_hook():
    with client() as api:
        product_id, spec_id, _ = build_creative_spec_fixture(
            api,
            title="Low CTR Variant Product",
            images=[
                "https://example.com/packshot_front.jpg",
                "https://example.com/label_closeup.png",
                "https://example.com/lifestyle_use.jpg",
            ],
            ctr=0.01,
            conversion_rate=0.08,
        )

        with SessionLocal() as db:
            kit = AssetKitBuilder(db).build_for_product(product_id)
            variant_set = CreativeVariantBuilder(db).build_set(spec_id, count=3, asset_kit_id=kit.id)
            VariantScorer(db).score_set(variant_set.id)
            variant = sorted(variant_set.variants, key=lambda item: item.variant_number)[0]

        assert "low_ctr" in variant.first_frame_json["source_flags"]
        assert variant.score_json["dimensions"]["hook_strength"] >= 0.9


def test_variant_selector_selects_highest_safe_score():
    with client() as api:
        _, _, variant_set_id, selected_variant_id = build_variant_set_fixture(api, title="Selected Variant Product")

        with SessionLocal() as db:
            variant_set = db.get(models.CreativeVariantSet, variant_set_id)
            selected = db.get(models.CreativeVariant, selected_variant_id)

        assert variant_set.status == "selected"
        assert variant_set.selected_variant_id == selected_variant_id
        assert selected.status == "selected"
        assert selected.score_json["safe"] is True


def test_prompt_pack_from_variant_contains_first_frame_and_assets():
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Variant Prompt Product")

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        prompt_pack = generation_variant.prompt_pack_json
        assert prompt_pack["creative_variant_id"] == selected_variant_id
        assert prompt_pack["selected_first_frame"]["text_overlay"]
        assert prompt_pack["asset_references"]
        assert prompt_pack["product_accuracy_rules"]
        assert "distorted product" in prompt_pack["scene_prompts"][0]["negative_prompt"]


def test_generate_from_variant_prompt_only_never_calls_provider(monkeypatch):
    def fail_if_instantiated(*args, **kwargs):
        raise AssertionError("Video provider should not be called when building prompts from a creative variant.")

    monkeypatch.setattr("app.intelligence.video_generator.RunwayVideoProvider", fail_if_instantiated)
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Variant Prompt Only Product")

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        assert generation_variant.status == "prompt_pack_ready"
        assert generation_variant.video_job_id is None


def test_video_generator_ui_shows_asset_kit_and_variants():
    with client() as api:
        response = api.get("/video-generator")

        assert response.status_code == 200
        assert "Asset Kit" in response.text
        assert "First Frame Options" in response.text
        assert "Creative Variants" in response.text


def test_upload_product_asset_creates_asset_record_and_file():
    with client() as api:
        product_id = create_product(api, title="Upload Asset Product")

        response = api.post(
            f"/api/assets/products/{product_id}/upload",
            data={"asset_type": "packshot", "manual_label": "front packshot", "is_primary_reference": "true"},
            files={"file": ("packshot.png", b"fake-png-bytes", "image/png")},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["asset_type"] == "packshot"
        assert payload["is_primary_reference"] is True
        assert payload["checksum"]
        assert Path(payload["source_ref"]).exists()


def test_attach_url_asset_creates_url_asset():
    with client() as api:
        product_id = create_product(api, title="URL Asset Product")

        response = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={
                "url": "https://example.com/packshot.png",
                "asset_type": "packshot",
                "manual_label": "front packshot",
                "is_primary_reference": True,
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["source_type"] == "url"
        assert payload["source_ref"] == "https://example.com/packshot.png"
        assert payload["is_primary_reference"] is True


def test_patch_asset_sets_primary_reference_and_review_status():
    with client() as api:
        product_id = create_product(api, title="Patch Asset Product")
        attached = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={"url": "https://example.com/product.png", "asset_type": "unknown"},
        ).json()

        response = api.patch(
            f"/api/assets/{attached['id']}",
            json={
                "asset_type": "packshot",
                "asset_role": "primary_reference",
                "is_primary_reference": True,
                "manual_label": "front approved packshot",
                "review_status": "approved",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["asset_type"] == "packshot"
        assert payload["is_primary_reference"] is True
        assert payload["review_status"] == "approved"


def test_readiness_blocks_without_primary_reference():
    with client() as api:
        product_id = create_product(api, title="Blocked Reference Product")
        api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={"url": "https://example.com/packshot.png", "asset_type": "packshot"},
        )

        response = api.post(f"/api/assets/products/{product_id}/readiness-check", json={"provider": "runway"})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "blocked"
        assert "missing_approved_primary_reference" in response.json()["blockers"]


def test_readiness_allows_approved_primary_packshot():
    with client() as api:
        product_id = create_product(api, title="Ready Reference Product")
        asset = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={
                "url": "https://example.com/packshot.png",
                "asset_type": "packshot",
                "is_primary_reference": True,
            },
        ).json()
        api.patch(f"/api/assets/{asset['id']}", json={"review_status": "approved", "is_primary_reference": True})

        response = api.post(f"/api/assets/products/{product_id}/readiness-check", json={"provider": "runway"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "ready"
        assert payload["real_generation_allowed"] is True
        assert payload["primary_reference_asset_id"] == asset["id"]


def test_rejected_asset_not_used_for_reference_bundle():
    with client() as api:
        product_id = create_product(api, title="Rejected Reference Product")
        asset = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={
                "url": "https://example.com/packshot.png",
                "asset_type": "packshot",
                "is_primary_reference": True,
            },
        ).json()
        api.patch(f"/api/assets/{asset['id']}", json={"review_status": "rejected", "is_primary_reference": True})

        response = api.post(f"/api/assets/products/{product_id}/reference-bundle", json={"provider": "runway"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "blocked"
        assert payload["reference_asset_ids"] == []


def test_reference_bundle_contains_only_approved_assets():
    with client() as api:
        product_id = create_product(api, title="Approved Bundle Product")
        primary = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={
                "url": "https://example.com/packshot.png",
                "asset_type": "packshot",
                "is_primary_reference": True,
            },
        ).json()
        pending = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={"url": "https://example.com/label.png", "asset_type": "label_closeup"},
        ).json()
        api.patch(f"/api/assets/{primary['id']}", json={"review_status": "approved", "is_primary_reference": True})

        response = api.post(f"/api/assets/products/{product_id}/reference-bundle", json={"provider": "runway"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert primary["id"] in payload["reference_asset_ids"]
        assert pending["id"] not in payload["reference_asset_ids"]


def test_prompt_pack_from_variant_includes_reference_bundle_when_ready():
    with client() as api:
        product_id, _, _, selected_variant_id = build_variant_set_fixture(api, title="Ready Variant Bundle Product")
        with SessionLocal() as db:
            storage = ProductAssetStorage(db)
            asset = storage.attach_url(
                product_id,
                url="https://example.com/packshot.png",
                asset_type="packshot",
                is_primary_reference=True,
            )
            storage.update_asset(asset.id, review_status="approved", is_primary_reference=True)
            generation_variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        prompt_pack = generation_variant.prompt_pack_json
        assert prompt_pack["reference_readiness_status"] == "ready"
        assert prompt_pack["reference_bundle_id"]
        assert prompt_pack["reference_images"] == ["https://example.com/packshot.png"]
        assert prompt_pack["primary_reference_asset"] == asset.id
        assert prompt_pack["product_lock_mode"] == "packshot_overlay"
        assert prompt_pack["product_reference_policy"]["strict_real_generation_allowed"] is False


def test_prompt_pack_from_variant_warns_when_reference_bundle_missing():
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Missing Bundle Variant Product", images=[])

        with SessionLocal() as db:
            generation_variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        assert generation_variant.prompt_pack_json["reference_readiness_status"] in {"blocked", "missing"}
        assert any("missing_approved_primary_reference" in warning or "No provider reference bundle" in warning for warning in generation_variant.prompt_pack_json["warnings"])


def test_video_generator_ui_uploads_and_shows_asset_readiness():
    with client() as api:
        product_id = create_product(api, title="UI Reference Product")

        upload = api.post(
            "/video-generator/run",
            data={
                "action": "upload_asset",
                "product_id": str(product_id),
                "asset_type": "packshot",
                "is_primary_reference": "true",
            },
            files={"upload_file": ("packshot.png", b"fake-png-bytes", "image/png")},
        )
        readiness = api.post(
            "/video-generator/run",
            data={"action": "readiness_check", "product_id": str(product_id), "video_provider": "runway"},
        )

        assert upload.status_code == 200
        assert "Asset Result" in upload.text
        assert readiness.status_code == 200
        assert "Reference Readiness" in readiness.text


def test_no_secrets_or_signed_urls_in_reference_bundle_report():
    with client() as api:
        product_id = create_product(api, title="Secret URL Product")
        asset = api.post(
            f"/api/assets/products/{product_id}/attach-url",
            json={
                "url": "https://example.com/packshot.png?token=secret&signature=abc123",
                "asset_type": "packshot",
                "is_primary_reference": True,
            },
        ).json()
        api.patch(f"/api/assets/{asset['id']}", json={"review_status": "approved", "is_primary_reference": True})

        response = api.post(f"/api/assets/products/{product_id}/reference-bundle", json={"provider": "runway"})
        serialized = json.dumps(response.json(), sort_keys=True)

        assert response.status_code == 200, response.text
        assert "token=secret" not in serialized
        assert "signature=abc123" not in serialized
        assert response.json()["provider_payload"]["reference_images"] == ["https://example.com/packshot.png"]


def test_reference_policy_blocks_strict_real_video_with_one_photo(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    with client() as api:
        product_id, _, _, selected_variant_id = build_variant_set_fixture(api, title="One Photo Strict Block Product")
        with SessionLocal() as db:
            storage = ProductAssetStorage(db)
            asset = storage.attach_url(
                product_id,
                url="https://example.com/packshot.png",
                asset_type="packshot",
                is_primary_reference=True,
            )
            storage.update_asset(asset.id, review_status="approved", is_primary_reference=True)
            policy = ProductReferencePolicyService(db).check(product_id)

            with pytest.raises(ProviderConfigurationError, match="Product reference readiness must be ready before real smoke"):
                RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)

        assert policy.product_lock_mode == "packshot_overlay"
        assert policy.strict_real_generation_allowed is False
        assert "strict_product_identity_requires_two_approved_references" in policy.blockers
        assert policy.next_actions == ["add_product_references"]


def test_reference_policy_allows_packshot_overlay_with_one_photo():
    with client() as api:
        product_id, _, _, selected_variant_id = build_variant_set_fixture(api, title="One Photo Overlay Product")
        with SessionLocal() as db:
            storage = ProductAssetStorage(db)
            asset = storage.attach_url(
                product_id,
                url="https://example.com/packshot.png",
                asset_type="packshot",
                is_primary_reference=True,
            )
            storage.update_asset(asset.id, review_status="approved", is_primary_reference=True)
            generation = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        assert generation.prompt_pack_json["product_lock_mode"] == "packshot_overlay"
        assert "packshot_overlay" in generation.prompt_pack_json["product_reference_policy"]["allowed_modes"]
        assert generation.video_job_id is None


def test_reference_policy_requires_tier_2_identity_and_scale_refs_for_strict_product_generation():
    with client() as api:
        product_id = create_product(api, title="Two Reference Product")
        with SessionLocal() as db:
            primary, angle, scale = attach_approved_tier_2_contract(db, product_id)
            policy = ProductReferencePolicyService(db).check(product_id)
            lifestyle = ProductAssetStorage(db).attach_url(
                product_id,
                url="https://example.com/context.png",
                asset_type="lifestyle",
            )
            ProductAssetStorage(db).update_asset(lifestyle.id, review_status="approved", asset_type="lifestyle")
            full_policy = ProductReferencePolicyService(db).check(product_id)

        assert policy.strict_real_generation_allowed is True
        assert policy.approved_reference_count == 3
        assert primary.id in policy.reference_asset_ids
        assert angle.id in policy.reference_asset_ids
        assert scale.id in policy.reference_asset_ids
        assert "recommended_three_product_references_missing" not in policy.warnings
        assert full_policy.approved_reference_count == 4
        assert "context_or_scale" not in full_policy.missing_reference_types


def test_blogger_meaning_spec_contains_persona_context_and_proof():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Bombbar Pro Dubai Mango Snack")
        with SessionLocal() as db:
            spec = MeaningSpecBuilder(db).build(product_id, platform="Instagram Reels", duration_seconds=8)

        assert spec.creator_persona_json["persona"] == "sporty UGC creator"
        assert spec.buyer_context_json["buyer_situation"]
        assert spec.proof_moment_json["proof_line"]
        assert spec.product_lock_rules_json["product_lock_mode"] in {"reference_i2v", "packshot_overlay", "no_product_generation"}


def test_ugc_script_uses_first_person_blogger_language():
    with client() as api:
        product_id = prepare_working_video_product(api, title="First Person Script Product")
        with SessionLocal() as db:
            meaning = MeaningSpecBuilder(db).build(product_id, duration_seconds=8)
            script = UGCAdScriptBuilder(db).build(meaning.id, duration_seconds=8)

        lines = " ".join(script.voiceover_json["lines"])
        assert "I " in lines
        assert script.voiceover_json["style"] == "first-person creator language"
        assert "generic ad voice" in script.voiceover_json["avoid"]


def test_ugc_script_without_variant_uses_latest_selected_variant_for_prompt_pack():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Default Variant UGC Script Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            meaning = MeaningSpecBuilder(db).build(product_id, creative_spec_id=spec_id, duration_seconds=8)
            script = UGCAdScriptBuilder(db).build(meaning.id, duration_seconds=8)
            generation = PromptEnricher(db).build_prompt_pack_from_script(script.id, provider="runway")

        assert script.creative_variant_id == selected_variant_id
        assert generation.prompt_pack_json["ugc_script_id"] == script.id
        assert generation.video_job_id is None


def test_scene_intent_has_hook_context_reason_proof_cta():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Scene Intent Product")
        with SessionLocal() as db:
            meaning = MeaningSpecBuilder(db).build(product_id, duration_seconds=8)

        roles = [scene["role"] for scene in meaning.scene_intent_json]
        assert roles == ["hook", "personal_context", "product_reason", "proof_demo", "cta"]


def test_prompt_enricher_includes_blogger_persona_and_scene_role():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Bombbar Protein UGC Enriched Prompt Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            meaning = MeaningSpecBuilder(db).build(product_id, creative_spec_id=spec_id, duration_seconds=8)
            script = UGCAdScriptBuilder(db).build(meaning.id, creative_variant_id=selected_variant_id, duration_seconds=8)
            generation = PromptEnricher(db).build_prompt_pack_from_script(script.id, provider="runway")

        first_scene = generation.prompt_pack_json["scene_prompts"][0]
        assert "Creator persona: sporty UGC creator" in first_scene["prompt_text"]
        assert "scene role: hook" in first_scene["prompt_text"]
        assert generation.prompt_pack_json["blogger_meaning_spec_id"] == meaning.id
        assert generation.prompt_pack_json["ugc_script_id"] == script.id


def test_prompt_enricher_requires_packshot_overlay_for_strict_identity_with_one_photo():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="UGC One Ref Overlay Prompt Product")
        with SessionLocal() as db:
            storage = ProductAssetStorage(db)
            asset = storage.attach_url(
                product_id,
                url="https://example.com/packshot.png",
                asset_type="packshot",
                is_primary_reference=True,
            )
            storage.update_asset(asset.id, review_status="approved", is_primary_reference=True)
            meaning = MeaningSpecBuilder(db).build(product_id, creative_spec_id=spec_id, duration_seconds=8)
            script = UGCAdScriptBuilder(db).build(meaning.id, creative_variant_id=selected_variant_id, duration_seconds=8)
            generation = PromptEnricher(db).build_prompt_pack_from_script(script.id, provider="runway")

        first_scene = generation.prompt_pack_json["scene_prompts"][0]
        assert generation.prompt_pack_json["product_lock_mode"] == "packshot_overlay"
        assert "do not generate packaging" in " ".join(first_scene["safety_constraints"])
        assert "Do not generate or redraw packaging" in first_scene["prompt_text"]


def test_mass_generation_marks_missing_references_as_blocker():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Mass Missing References Product", images=[])
        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)

        assert result.reference_policy["mass_generation_safety_status"] == "blocked_missing_references"
        assert "add_product_references" in {action.action for action in result.next_actions}
        assert any(blocker.startswith("reference_policy:") for blocker in result.blockers)


def test_prompt_contains_packaging_and_geometry_negative_terms():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Packaging Drift Prompt Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            meaning = MeaningSpecBuilder(db).build(product_id, creative_spec_id=spec_id, duration_seconds=8)
            script = UGCAdScriptBuilder(db).build(meaning.id, creative_variant_id=selected_variant_id, duration_seconds=8)
            generation = PromptEnricher(db).build_prompt_pack_from_script(script.id, provider="runway")

        negative_prompt = generation.prompt_pack_json["scene_prompts"][0]["negative_prompt"]
        for term in PACKAGING_DRIFT_NEGATIVE_TERMS:
            assert term in negative_prompt


def test_ugc_video_strategy_ui_and_api_show_reference_policy():
    with client() as api:
        product_id = create_product(api, title="UGC Strategy UI Product")

        policy_response = api.get(f"/api/video-generator/products/{product_id}/reference-policy")
        page = api.get(f"/ugc-video-strategy?product_id={product_id}")

        spec_response = api.post(
            "/api/blogger-brief/specs/build",
            json={"product_id": product_id, "platform": "Instagram Reels", "duration_seconds": 8},
        )
        script_response = api.post(
            "/api/blogger-brief/scripts/build",
            json={"blogger_meaning_spec_id": spec_response.json()["id"], "duration_seconds": 8},
        )

        assert policy_response.status_code == 200
        assert policy_response.json()["next_actions"] == ["add_product_references"]
        assert page.status_code == 200
        assert "UGC Video Strategy" in page.text
        assert "Reference Policy" in page.text
        assert spec_response.status_code == 200
        assert spec_response.json()["product_lock_rules"]["product_lock_mode"] == "no_product_generation"
        assert script_response.status_code == 200
        assert script_response.json()["status"] == "ready"


def test_product_strategy_spec_contains_buyer_situation_objection_offer():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Strategy Snack Product")
        with SessionLocal() as db:
            spec = ProductStrategyBuilder(db).build(product_id, platform="Instagram Reels")
            offer = OfferStrategyBuilder(db).build(spec.id)

        assert spec.buyer_situation_json["situation"]
        assert spec.main_objection
        assert spec.offer_strategy_json["offer_type"]
        assert spec.proof_required_json
        assert offer.product_strategy_spec_id == spec.id


def test_offer_strategy_handles_competitor_price_pressure():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Strategy Competitor Product", competitor_price=100)
        with SessionLocal() as db:
            spec = ProductStrategyBuilder(db).build(product_id, platform="Instagram Reels")
            offer = OfferStrategyBuilder(db).build(spec.id)

        assert spec.competitor_context_json["pressure"] == "price_pressure"
        assert offer.offer_type == "comparison"
        assert "value" in (offer.competitor_response or "").lower()


def test_offer_strategy_blocks_aggressive_cta_on_stock_risk():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Strategy Stock Product", stock_qty=3, days_of_stock=3)
        with SessionLocal() as db:
            spec = ProductStrategyBuilder(db).build(product_id, platform="Instagram Reels")
            offer = OfferStrategyBuilder(db).build(spec.id)

        assert spec.stock_context_json["stock_risk"] == "low_stock"
        assert spec.stock_context_json["aggressive_cta_allowed"] is False
        assert "stock_risk_no_aggressive_cta" in offer.warnings_json
        assert "urgent" not in (offer.cta_strategy or "").lower()


def test_platform_strategy_differs_for_reels_tiktok_youtube_marketplace():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Strategy Platform Product")
        with SessionLocal() as db:
            reels = ProductStrategyBuilder(db).build(product_id, platform="Instagram Reels")
            tiktok = ProductStrategyBuilder(db).build(product_id, platform="TikTok")
            youtube = ProductStrategyBuilder(db).build(product_id, platform="YouTube Shorts")
            marketplace = ProductStrategyBuilder(db).build(product_id, platform="Marketplace card video")

        assert reels.platform_strategy_json["selected"]["hook_style"] != tiktok.platform_strategy_json["selected"]["hook_style"]
        assert youtube.platform_strategy_json["selected"]["pacing"] != tiktok.platform_strategy_json["selected"]["pacing"]
        assert "product clarity" in marketplace.platform_strategy_json["selected"]["hook_style"]


def test_product_strategy_api_builds_spec_offer_and_status():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Strategy API Product")

        spec_response = api.post(
            "/api/product-strategy/specs/build",
            json={"product_id": product_id, "platform": "TikTok"},
        )
        spec_id = spec_response.json()["id"]
        offer_response = api.post(
            "/api/product-strategy/offers/build",
            json={"product_strategy_spec_id": spec_id},
        )
        status_response = api.get(f"/api/product-strategy/products/{product_id}/strategy-status")

        assert spec_response.status_code == 200
        assert spec_response.json()["platform_strategy"]["primary_platform"] == "TikTok"
        assert spec_response.json()["buyer_situation"]["situation"]
        assert offer_response.status_code == 200
        assert offer_response.json()["product_strategy_spec_id"] == spec_id
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "ready"
        assert status_response.json()["offer_strategy_id"] == offer_response.json()["id"]


def test_product_strategy_cli_builds_spec_and_offer():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Strategy CLI Product")

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    spec_result = subprocess.run(
        [
            sys.executable,
            "scripts/build_product_strategy_spec.py",
            "--product-id",
            str(product_id),
            "--platform",
            "Instagram Reels",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert spec_result.returncode == 0
    assert "Product Strategy Spec ID:" in spec_result.stdout
    spec_id = int(
        next(line for line in spec_result.stdout.splitlines() if line.startswith("Product Strategy Spec ID:")).split(":")[-1].strip()
    )

    offer_result = subprocess.run(
        [
            sys.executable,
            "scripts/build_offer_strategy.py",
            "--product-strategy-spec-id",
            str(spec_id),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert offer_result.returncode == 0
    assert "Offer Strategy ID:" in offer_result.stdout
    assert f"Product Strategy Spec ID: {spec_id}" in offer_result.stdout


def test_ugc_quality_score_passes_good_blogger_script():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Good UGC Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
            )
            score = UGCQualityScorer(db).score_script(script.id)

        assert score.status == "passed"
        assert score.total_score >= 75
        assert "generic_ad_voice" not in score.reasons_json


def test_ugc_quality_score_passes_russian_blogger_script():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(
            api,
            title="Quality Russian UGC Product",
            conversion_rate=0.05,
        )
        scenes = [
            {
                "scene_number": 1,
                "role": "hook",
                "spoken_line": "Я беру этот батончик после тренировки, когда хочется сладкого без тяжелого перекуса.",
                "caption": "После тренировки",
                "visual_direction": "Спортивная девушка держит точную упаковку.",
            },
            {
                "scene_number": 2,
                "role": "personal_context",
                "spoken_line": "Мне удобно держать его в сумке между залом и делами.",
                "caption": "В моей рутине",
                "visual_direction": "Натуральная речь в раздевалке или кухне.",
            },
            {
                "scene_number": 3,
                "role": "product_reason",
                "spoken_line": "Поэтому выбираю именно этот формат: он подходит для быстрого перекуса и легко помещается в сумку.",
                "caption": "Почему этот",
                "visual_direction": "Упаковка читаемая, без перерисовки.",
            },
            {
                "scene_number": 4,
                "role": "proof_demo",
                "spoken_line": "Покажу реальную упаковку, открою батончик и пробую кусочек, чтобы была видна текстура.",
                "caption": "Пробую текстуру",
                "visual_direction": "Отдельный распакованный кусочек рядом с точной упаковкой.",
            },
            {
                "scene_number": 5,
                "role": "cta",
                "spoken_line": "Открой карточку товара и посмотри, подходит ли он под твою рутину.",
                "caption": "Смотри карточку",
                "visual_direction": "Финальный кадр на точную упаковку.",
            },
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=scenes,
            )
            score = UGCQualityScorer(db).score_script(script.id)

        assert score.status == "passed"
        assert "generic_ad_voice" not in score.reasons_json
        assert "offer_mismatch" not in score.reasons_json


def test_ugc_quality_score_flags_generic_ad_voice():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Generic Voice Product")
        generic_scenes = [
            {"scene_number": 1, "role": "hook", "spoken_line": "Buy now, this is the best product.", "caption": "", "visual_direction": ""},
            {"scene_number": 2, "role": "personal_context", "spoken_line": "This snack is useful.", "caption": "", "visual_direction": ""},
            {"scene_number": 3, "role": "product_reason", "spoken_line": "Great offer for everyone.", "caption": "", "visual_direction": ""},
            {"scene_number": 4, "role": "proof_demo", "spoken_line": "Look at this item.", "caption": "", "visual_direction": ""},
            {"scene_number": 5, "role": "cta", "spoken_line": "Order now.", "caption": "", "visual_direction": ""},
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=generic_scenes,
            )
            score = UGCQualityScorer(db).score_script(script.id)

        assert "generic_ad_voice" in score.reasons_json
        assert score.status == "needs_rewrite"


def test_ugc_quality_score_flags_missing_personal_context():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Missing Context Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            base_script = create_manual_ugc_script(db, product_id, creative_spec_id=spec_id, creative_variant_id=selected_variant_id)
            base_script.scene_script_json = [scene for scene in base_script.scene_script_json if scene["role"] != "personal_context"]
            db.commit()
            score = UGCQualityScorer(db).score_script(base_script.id)

        assert "no_personal_context" in score.reasons_json
        assert "incomplete_scene_roles" in score.reasons_json


def test_ugc_quality_score_flags_missing_product_reason():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Missing Reason Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(db, product_id, creative_spec_id=spec_id, creative_variant_id=selected_variant_id)
            script.scene_script_json = [scene for scene in script.scene_script_json if scene["role"] != "product_reason"]
            db.commit()
            score = UGCQualityScorer(db).score_script(script.id)

        assert "missing_product_reason" in score.reasons_json
        assert "incomplete_scene_roles" in score.reasons_json


def test_ugc_quality_score_flags_missing_proof_moment():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Missing Proof Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(db, product_id, creative_spec_id=spec_id, creative_variant_id=selected_variant_id)
            script.scene_script_json = [scene for scene in script.scene_script_json if scene["role"] != "proof_demo"]
            db.commit()
            score = UGCQualityScorer(db).score_script(script.id)

        assert "missing_proof_moment" in score.reasons_json
        assert score.status == "needs_rewrite"


def test_ugc_quality_score_flags_weak_hook():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Weak Hook Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(db, product_id, creative_spec_id=spec_id, creative_variant_id=selected_variant_id)
            scenes = list(script.scene_script_json)
            scenes[0] = {**scenes[0], "spoken_line": "Nice."}
            script.scene_script_json = scenes
            db.commit()
            score = UGCQualityScorer(db).score_script(script.id)

        assert "weak_hook" in score.reasons_json


def test_ugc_quality_score_flags_offer_mismatch():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(
            api,
            title="Quality Offer Mismatch Product",
            conversion_rate=0.08,
        )
        add_generator_snapshots(product_sku(api, product_id), competitor_price=100)
        scenes = [
            {
                "scene_number": 1,
                "role": "hook",
                "spoken_line": "I tried this after training when I wanted a quick snack in my routine.",
                "caption": "",
                "visual_direction": "",
            },
            {
                "scene_number": 2,
                "role": "personal_context",
                "spoken_line": "I keep it nearby between errands and gym days.",
                "caption": "",
                "visual_direction": "",
            },
            {
                "scene_number": 3,
                "role": "product_reason",
                "spoken_line": "Because the format is easy to carry and the portion is clear.",
                "caption": "",
                "visual_direction": "",
            },
            {
                "scene_number": 4,
                "role": "proof_demo",
                "spoken_line": "I show the real pack and the texture in one bite.",
                "caption": "",
                "visual_direction": "",
            },
            {
                "scene_number": 5,
                "role": "cta",
                "spoken_line": "Check the product card if this fits your snack routine.",
                "caption": "",
                "visual_direction": "",
            },
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            strategy = ProductStrategyBuilder(db).build(product_id, platform="Instagram Reels")
            offer = OfferStrategyBuilder(db).build(strategy.id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=scenes,
            )
            score = UGCQualityScorer(db).score_script(script.id)

        assert offer.offer_type == "comparison"
        assert "offer_mismatch" in score.reasons_json


def test_ugc_quality_gate_blocks_real_smoke_below_threshold():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Gate Block Product")
        generic_scenes = [
            {"scene_number": 1, "role": "hook", "spoken_line": "Buy now, best product.", "caption": "", "visual_direction": ""},
            {"scene_number": 2, "role": "personal_context", "spoken_line": "This is good.", "caption": "", "visual_direction": ""},
            {"scene_number": 3, "role": "product_reason", "spoken_line": "Great offer for everyone.", "caption": "", "visual_direction": ""},
            {"scene_number": 4, "role": "proof_demo", "spoken_line": "Look.", "caption": "", "visual_direction": ""},
            {"scene_number": 5, "role": "cta", "spoken_line": "Order now.", "caption": "", "visual_direction": ""},
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=generic_scenes,
            )
            gate = CreativeQualityGateService(db).gate(product_id, ugc_script_id=script.id, creative_variant_id=selected_variant_id)

        assert gate.real_smoke_allowed is False
        assert gate.next_action == "rewrite_ugc_script"
        assert gate.rewrite_request_id is not None
        assert any(blocker.startswith("creative_quality:") for blocker in gate.blockers)


def test_quality_gate_blocks_real_smoke_without_product_strategy(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Gate Missing Strategy Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                with_product_strategy=False,
            )
            with pytest.raises(ProviderConfigurationError, match="Creative quality gate blocks real smoke"):
                RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)


def test_ugc_quality_gate_passes_script_above_threshold():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Gate Pass Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
            )
            gate = CreativeQualityGateService(db).gate(product_id, ugc_script_id=script.id, creative_variant_id=selected_variant_id)

        assert gate.real_smoke_allowed is True
        assert gate.status == "passed"
        assert gate.next_action == "run_limited_real_smoke"


def test_rewrite_request_created_for_needs_rewrite():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Rewrite Request Product")
        generic_scenes = [
            {"scene_number": 1, "role": "hook", "spoken_line": "Buy now, best product.", "caption": "", "visual_direction": ""},
            {"scene_number": 2, "role": "personal_context", "spoken_line": "This is good.", "caption": "", "visual_direction": ""},
            {"scene_number": 3, "role": "product_reason", "spoken_line": "Great offer for everyone.", "caption": "", "visual_direction": ""},
            {"scene_number": 4, "role": "proof_demo", "spoken_line": "Look at this item.", "caption": "", "visual_direction": ""},
            {"scene_number": 5, "role": "cta", "spoken_line": "Order now.", "caption": "", "visual_direction": ""},
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=generic_scenes,
            )
            score = UGCQualityScorer(db).score_script(script.id)
            request = ScriptRewriter(db).create_request(score.id, feedback="Make it feel like a sporty creator.")

        assert score.status == "needs_rewrite"
        assert request.status == "requested"
        assert request.ugc_script_id == script.id
        assert request.required_fixes_json


def test_script_rewriter_adds_personal_context_and_proof():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality Rewrite Build Product")
        generic_scenes = [
            {"scene_number": 1, "role": "hook", "spoken_line": "Buy now, best product.", "caption": "", "visual_direction": ""},
            {"scene_number": 2, "role": "cta", "spoken_line": "Order now.", "caption": "", "visual_direction": ""},
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=generic_scenes,
            )
            score = UGCQualityScorer(db).score_script(script.id)
            request = ScriptRewriter(db).create_request(score.id)
            result = ScriptRewriter(db).build(request.id)
            rewritten = db.get(models.UGCAdScript, result.new_ugc_script_id)

        roles = [scene["role"] for scene in rewritten.scene_script_json]
        lines = " ".join(scene["spoken_line"] for scene in rewritten.scene_script_json)
        assert "personal_context" in roles
        assert "proof_demo" in roles
        assert "I " in lines
        assert result.new_ugc_script_id != script.id


def test_creative_quality_ui_renders_score_breakdown():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality UI Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
            )
            score = UGCQualityScorer(db).score_script(script.id)

        response = api.get(f"/creative-quality?product_id={product_id}")

        assert response.status_code == 200
        assert "Creative Quality" in response.text
        assert "Score Breakdown" in response.text
        assert "Hook strength" in response.text
        assert str(score.id) in response.text


def test_product_strategy_ui_renders_strategy_and_quality_score():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Product Strategy UI Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
            )
            score = UGCQualityScorer(db).score_script(script.id)

        response = api.get(f"/product-strategy?product_id={product_id}")

        assert response.status_code == 200
        assert "Product Strategy" in response.text
        assert "Buyer situation" in response.text
        assert "Offer Strategy" in response.text
        assert str(score.product_strategy_spec_id) in response.text


def test_creative_quality_api_scores_rewrites_and_reports_gate_status():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality API Product")
        generic_scenes = [
            {"scene_number": 1, "role": "hook", "spoken_line": "Buy now, best product.", "caption": "", "visual_direction": ""},
            {"scene_number": 2, "role": "personal_context", "spoken_line": "This is good.", "caption": "", "visual_direction": ""},
            {"scene_number": 3, "role": "product_reason", "spoken_line": "Great offer for everyone.", "caption": "", "visual_direction": ""},
            {"scene_number": 4, "role": "proof_demo", "spoken_line": "Look at this item.", "caption": "", "visual_direction": ""},
            {"scene_number": 5, "role": "cta", "spoken_line": "Order now.", "caption": "", "visual_direction": ""},
        ]
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
                scenes=generic_scenes,
            )

        score_response = api.post("/api/creative-quality/score", json={"ugc_script_id": script.id})
        score_id = score_response.json()["id"]
        rewrite_response = api.post(
            f"/api/creative-quality/scores/{score_id}/rewrite-request",
            json={"feedback": "Make it creator-led."},
        )
        build_response = api.post(f"/api/creative-quality/rewrite-requests/{rewrite_response.json()['id']}/build")
        gate_response = api.get(
            f"/api/creative-quality/products/{product_id}/gate-status",
            params={"ugc_script_id": script.id, "creative_variant_id": selected_variant_id},
        )

        assert score_response.status_code == 200
        assert score_response.json()["status"] == "needs_rewrite"
        assert rewrite_response.status_code == 200
        assert build_response.status_code == 200
        assert build_response.json()["new_ugc_script_id"] != script.id
        assert gate_response.status_code == 200
        assert gate_response.json()["next_action"] == "rewrite_ugc_script"


def test_creative_quality_cli_scores_script():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="Quality CLI Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            script = create_manual_ugc_script(
                db,
                product_id,
                creative_spec_id=spec_id,
                creative_variant_id=selected_variant_id,
            )

        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/score_ugc_script.py", "--ugc-script-id", str(script.id)],
            cwd=root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "Total Score:" in result.stdout
        assert "Status: passed" in result.stdout


def test_creative_workbench_builds_session_from_product():
    with client() as api:
        product_id, session_id, script_id, prompt_pack_id = prepare_workbench_fixture(api, title="Workbench Build Product")

        with SessionLocal() as db:
            session = db.get(models.CreativeWorkbenchSession, session_id)
            output = WorkbenchService(db).as_output(session)

        assert session.product_id == product_id
        assert session.ugc_script_id == script_id
        assert session.prompt_pack_id == prompt_pack_id
        assert output.product_strategy_spec_id
        assert output.offer_strategy_id
        assert output.real_smoke_readiness.prompt_pack_ready is True


def test_workbench_shows_strategy_offer_ugc_score_and_prompt():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(api, title="Workbench Full View Product")

        with SessionLocal() as db:
            output = WorkbenchService(db).as_output(db.get(models.CreativeWorkbenchSession, session_id))

        assert output.strategy_scorecard["items"]
        assert output.offer_logic["offer_type"]
        assert output.ugc_script_preview["scenes"]
        assert output.creative_quality_breakdown["total_score"] >= 80
        assert output.prompt_preview["scenes"]


def test_workbench_blocks_real_smoke_when_quality_below_threshold():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(
            api,
            title="Workbench Low Quality Product",
            scenes=generic_ad_scenes(),
        )

        with SessionLocal() as db:
            readiness = ReadinessService(db).for_session(session_id)

        assert readiness.real_smoke_allowed is False
        assert any(blocker.startswith("creative_quality:") for blocker in readiness.blockers)


def test_workbench_blocks_real_smoke_when_reference_policy_fails():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(
            api,
            title="Workbench Missing References Product",
            with_references=False,
        )

        with SessionLocal() as db:
            readiness = ReadinessService(db).for_session(session_id)

        assert readiness.reference_policy_passed is False
        assert readiness.real_smoke_allowed is False
        assert any(blocker.startswith("reference_policy:") for blocker in readiness.blockers)


def test_brief_editor_updates_safe_fields():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(api, title="Workbench Brief Patch Product")

        with SessionLocal() as db:
            session = BriefEditorService(db).patch(
                session_id,
                {
                    "buyer_situation": "Sporty creator needs a quick snack after training.",
                    "main_objection": "Needs proof that it is not just candy.",
                    "proof_moment": "Show the exact pack and one unwrapped bite.",
                    "cta": "Open the product card and compare details.",
                    "creator_persona": "Sporty woman, 25-30, calm first-person delivery.",
                    "must_avoid": ["do not eat wrapper"],
                },
            )
            assert session.product_strategy_spec.main_objection == "Needs proof that it is not just candy."
            assert session.blogger_meaning_spec.proof_moment_json["proof_line"] == "Show the exact pack and one unwrapped bite."
            assert session.blogger_meaning_spec.cta_json["spoken_line"] == "Open the product card and compare details."
            assert "do not eat wrapper" in session.blogger_meaning_spec.authenticity_rules_json["must_avoid"]


def test_brief_editor_does_not_bypass_gates():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(api, title="Workbench Guardrail Product")

        with SessionLocal() as db:
            with pytest.raises(CreativeWorkbenchGuardrailError):
                BriefEditorService(db).patch(
                    session_id,
                    {"real_smoke_allowed": True, "product_reference_approval_status": "approved"},
                )
            session = db.get(models.CreativeWorkbenchSession, session_id)

        assert session.status != "approved_for_smoke"


def test_prompt_preview_contains_scene_prompt_negative_prompt_and_lock_mode():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(api, title="Workbench Prompt Preview Product")

        with SessionLocal() as db:
            preview = PromptPreviewService(db).preview(session_id)

        assert preview.prompt_pack_id
        assert preview.product_lock_mode == "reference_i2v"
        assert preview.negative_prompt
        assert preview.scenes[0].scene_prompt
        assert preview.scenes[0].identity_constraints


def test_rewrite_workflow_creates_before_after_script():
    with client() as api:
        _, session_id, script_id, _ = prepare_workbench_fixture(
            api,
            title="Workbench Rewrite Product",
            scenes=generic_ad_scenes(),
        )

        with SessionLocal() as db:
            result = RewriteWorkflowService(db).rewrite(session_id, feedback="Make this feel like a real sporty creator.")

        assert result.source_ugc_script_id == script_id
        assert result.new_ugc_script_id != script_id
        assert result.before_lines != result.after_lines
        assert result.new_score["ugc_script_id"] == result.new_ugc_script_id


def test_workbench_approval_requires_passed_readiness():
    with client() as api:
        _, blocked_session_id, _, _ = prepare_workbench_fixture(
            api,
            title="Workbench Blocked Approval Product",
            scenes=generic_ad_scenes(),
        )
        _, ready_session_id, _, _ = prepare_workbench_fixture(api, title="Workbench Ready Approval Product")

        with SessionLocal() as db:
            with pytest.raises(CreativeWorkbenchGuardrailError):
                WorkbenchService(db).approve_for_smoke(blocked_session_id, reviewer_name="Operator")
            approval = WorkbenchService(db).approve_for_smoke(ready_session_id, reviewer_name="Operator")
            ready_session = db.get(models.CreativeWorkbenchSession, ready_session_id)

        assert approval.status == "approved"
        assert ready_session.status == "approved_for_smoke"


def test_creative_workbench_ui_renders_all_sections():
    with client() as api:
        _, session_id, _, _ = prepare_workbench_fixture(api, title="Workbench UI Product")

        response = api.get(f"/creative-workbench?session_id={session_id}")

        assert response.status_code == 200
        assert "Creative Quality Workbench" in response.text
        assert "Product Strategy" in response.text
        assert "Offer Logic" in response.text
        assert "UGC Script" in response.text
        assert "Quality Score" in response.text
        assert "Prompt Preview" in response.text
        assert "Rewrite" in response.text
        assert "Real Smoke Readiness" in response.text


def test_ai_production_brief_contains_thesis_takeaway_proof_and_cta():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Thesis Product", with_blueprint=False, with_director_prompt=False)

        with SessionLocal() as db:
            brief = db.get(models.AIProductionBrief, brief_id)

        assert brief.one_sentence_thesis
        assert brief.viewer_takeaway
        assert brief.proof_moment
        assert brief.cta
        assert brief.reason_to_believe


def test_ai_production_brief_contains_must_show_and_must_avoid():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Musts Product", with_blueprint=False, with_director_prompt=False)

        with SessionLocal() as db:
            brief = db.get(models.AIProductionBrief, brief_id)

        assert "proof/use-case demo" in brief.must_show_json
        assert "fake label" in brief.must_avoid_json
        assert "changed packaging" in brief.must_avoid_json
        assert brief.failure_conditions_json


def test_scene_blueprint_has_required_timeline_roles():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Timeline Product", with_blueprint=True, with_director_prompt=False)

        with SessionLocal() as db:
            scenes = SceneBlueprintBuilder(db).latest_for_brief(brief_id)

        assert [scene.scene_role for scene in scenes] == ["hook", "personal_context", "product_reason", "proof_demo", "cta"]
        assert [(scene.start_second, scene.end_second) for scene in scenes] == [(0, 2), (2, 5), (5, 8), (8, 12), (12, 15)]


def test_scene_blueprint_defines_product_visibility_per_scene():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Visibility Product", with_blueprint=True, with_director_prompt=False)

        with SessionLocal() as db:
            scenes = SceneBlueprintBuilder(db).latest_for_brief(brief_id)

        assert all(scene.product_visibility for scene in scenes)
        assert any("reference image" in scene.product_visibility for scene in scenes)


def test_director_prompt_pack_contains_scene_role_spoken_line_and_asset_rules():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Director Product")

        with SessionLocal() as db:
            prompt = DirectorPromptBuilder(db).latest_for_brief(brief_id)

        first_scene = prompt.provider_prompt_json["scenes"][0]
        assert first_scene["scene_role"] == "hook"
        assert first_scene["exact_spoken_line"]
        assert first_scene["asset_overlay_instruction"]
        assert first_scene["identity_geometry_constraints"]["human_review_required"] is True
        for term in NEGATIVE_PROMPT_TERMS:
            assert term in prompt.negative_prompt


def test_director_prompt_pack_blocks_ai_packaging_generation_in_overlay_mode():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(api, title="AI Brief Overlay Product")
        with SessionLocal() as db:
            storage = ProductAssetStorage(db)
            asset = storage.attach_url(product_id, url="https://example.com/packshot.png", asset_type="packshot", is_primary_reference=True)
            storage.update_asset(asset.id, review_status="approved", is_primary_reference=True)
            script = create_manual_ugc_script(db, product_id, creative_spec_id=spec_id, creative_variant_id=selected_variant_id)
            UGCQualityScorer(db).score_script(script.id)
            brief = AIProductionBriefBuilder(db).build(product_id, ugc_script_id=script.id)
            SceneBlueprintBuilder(db).build(brief.id)
            prompt = DirectorPromptBuilder(db).build(brief.id)

        assert brief.product_lock_mode == "packshot_overlay"
        assert "Do not ask AI to redraw exact packaging" in prompt.overlay_instructions_json["instruction"]
        assert "Do not ask AI to redraw exact packaging" in prompt.provider_prompt_json["scenes"][0]["asset_overlay_instruction"]


def test_brief_quality_checker_blocks_missing_proof_moment():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Missing Proof Product", with_director_prompt=False)

        with SessionLocal() as db:
            brief = db.get(models.AIProductionBrief, brief_id)
            brief.proof_moment = None
            db.commit()
            check = BriefQualityChecker(db).check(brief.id)

        assert check.status == "blocked"
        assert "proof_moment" in check.missing_fields_json


def test_brief_quality_checker_blocks_generic_ad_language():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(
            api,
            title="AI Brief Generic Language Product",
            scenes=generic_ad_scenes(),
            with_director_prompt=False,
        )

        with SessionLocal() as db:
            check = BriefQualityChecker(db).check(brief_id)

        assert check.status == "blocked"
        assert "generic_ad_language" in check.weak_points_json


def test_brief_markdown_export_contains_full_tz():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief Markdown Product", with_blueprint=True, with_director_prompt=False)

        with SessionLocal() as db:
            brief = db.get(models.AIProductionBrief, brief_id)
            markdown = MarkdownRenderer().render(brief)

        assert "Final Brief Contract" in markdown
        assert "Scene Blueprint" in markdown
        assert "Failure Conditions" in markdown
        assert "Product lock mode" in markdown


def test_ai_brief_studio_ui_renders_contract_blueprint_prompt_and_quality():
    with client() as api:
        _, brief_id, _ = prepare_ai_brief_fixture(api, title="AI Brief UI Product", with_quality_check=True)

        response = api.get(f"/ai-brief-studio?ai_production_brief_id={brief_id}")

        assert response.status_code == 200
        assert "AI Brief Studio" in response.text
        assert "Final Brief Contract" in response.text
        assert "Scene Blueprint" in response.text
        assert "Director Prompt Preview" in response.text
        assert "Brief Quality Check" in response.text
        assert "Export Markdown" in response.text


def test_frame_extractor_creates_contact_sheet_from_fixture_video():
    with client() as api:
        _, _, video_job_id = prepare_output_acceptance_fixture(api, title="Output Frames Product", with_frames=False)

        with SessionLocal() as db:
            result = FrameExtractor(db).extract(video_job_id)

        assert result.status == "created"
        assert result.frame_paths_json
        assert Path(result.contact_sheet_path).exists()


def test_output_acceptance_blocks_missing_contact_sheet():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Output Missing Sheet Product", with_frames=False)

        with SessionLocal() as db:
            acceptance = AcceptanceReviewService(db).review(
                video_job_id=video_job_id,
                ai_production_brief_id=brief_id,
                decision="approve",
                product_identity_status="pass",
                packaging_status="pass",
                geometry_status="pass",
                blogger_authenticity_status="pass",
                scene_match_status="pass",
                proof_moment_status="pass",
                cta_status="pass",
            )

        assert acceptance.status == "blocked"
        assert "contact_sheet_missing" in acceptance.blockers_json
        assert "extract_frames_before_review" in acceptance.required_fixes_json


def test_output_quality_checker_requires_human_review_for_identity():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Output Identity Review Product")

        with SessionLocal() as db:
            video_job = db.get(models.VideoJob, video_job_id)
            brief = db.get(models.AIProductionBrief, brief_id)
            frame_result = FrameExtractor(db).latest_for_video_job(video_job_id)
            result = OutputQualityChecker().check(
                video_job=video_job,
                brief=brief,
                frame_result=frame_result,
                decision="approve",
                product_identity_status="needs_review",
                packaging_status="pass",
                geometry_status="pass",
                blogger_authenticity_status="pass",
                scene_match_status="pass",
                proof_moment_status="pass",
                cta_status="pass",
            )

        assert result.status == "needs_regeneration"
        assert "human_review_required_for_product_identity" in result.blockers
        assert result.publishing_readiness == "blocked"


def test_output_acceptance_flags_packaging_drift():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Output Packaging Drift Product")

        with SessionLocal() as db:
            acceptance = AcceptanceReviewService(db).review(
                video_job_id=video_job_id,
                ai_production_brief_id=brief_id,
                decision="needs_regeneration",
                product_identity_status="pass",
                packaging_status="drift",
                geometry_status="pass",
                blogger_authenticity_status="pass",
                scene_match_status="pass",
                proof_moment_status="pass",
                cta_status="pass",
            )

        assert acceptance.status == "needs_regeneration"
        assert "packaging_drift" in acceptance.blockers_json
        assert "regenerate_or_switch_to_packshot_overlay" in acceptance.required_fixes_json


def test_output_acceptance_flags_missing_proof_moment():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Output Missing Proof Product")

        with SessionLocal() as db:
            acceptance = AcceptanceReviewService(db).review(
                video_job_id=video_job_id,
                ai_production_brief_id=brief_id,
                decision="needs_regeneration",
                product_identity_status="pass",
                packaging_status="pass",
                geometry_status="pass",
                blogger_authenticity_status="pass",
                scene_match_status="pass",
                proof_moment_status="missing",
                cta_status="pass",
            )

        assert acceptance.status == "needs_regeneration"
        assert "missing_proof_moment" in acceptance.blockers_json
        assert "add_visible_proof_moment" in acceptance.required_fixes_json


def test_output_acceptance_creates_regeneration_request():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Output Regeneration Product")

        with SessionLocal() as db:
            acceptance = AcceptanceReviewService(db).review(
                video_job_id=video_job_id,
                ai_production_brief_id=brief_id,
                decision="needs_regeneration",
                product_identity_status="pass",
                packaging_status="drift",
                geometry_status="pass",
                blogger_authenticity_status="pass",
                scene_match_status="pass",
                proof_moment_status="pass",
                cta_status="pass",
                reviewer_notes="Label drifted in product closeup.",
            )
            request = RegenerationFeedbackBuilder(db).request(
                acceptance.id,
                reason="product_identity_mismatch",
                scene_number=1,
            )

        assert request.video_job_id == video_job_id
        assert request.reason == "product_identity_mismatch"
        assert "Output acceptance" in request.feedback


def test_output_acceptance_ui_renders_contact_sheet_and_checklist():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Output UI Product")
        response = api.post(
            f"/api/output-acceptance/video-jobs/{video_job_id}/review",
            json={
                "ai_production_brief_id": brief_id,
                "decision": "approve",
                "product_identity_status": "pass",
                "packaging_status": "pass",
                "geometry_status": "pass",
                "blogger_authenticity_status": "pass",
                "scene_match_status": "pass",
                "proof_moment_status": "pass",
                "cta_status": "pass",
            },
        )
        assert response.status_code == 200, response.text

        page = api.get(f"/output-acceptance?video_job_id={video_job_id}")

        assert page.status_code == 200
        assert "Output Acceptance" in page.text
        assert "Video Artifact" in page.text
        assert "Contact Sheet" in page.text
        assert "AIProductionBrief Summary" in page.text
        assert "Scene Blueprint Checklist" in page.text
        assert "Product Identity Checklist" in page.text
        assert "Blogger Authenticity Checklist" in page.text
        assert "Decision: approve / needs_regeneration / reject" in page.text


def test_variant_real_smoke_requires_real_generation_mode(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "mock")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway-key")
    get_settings.cache_clear()
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Mode Gate Variant")

        with SessionLocal() as db:
            with pytest.raises(ProviderConfigurationError, match="QVF_GENERATION_MODE=real"):
                RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)


def test_variant_real_smoke_requires_allow_spend_true(monkeypatch):
    enable_real_smoke_env(monkeypatch, allow_spend="false")
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Spend Gate Variant")

        with SessionLocal() as db:
            with pytest.raises(ProviderConfigurationError, match="QVF_ALLOW_REAL_SPEND=true"):
                RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)


def test_variant_real_smoke_requires_runway_key(monkeypatch):
    enable_real_smoke_env(monkeypatch, runway_key=None)
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Missing Key Variant")

        with SessionLocal() as db:
            with pytest.raises(ProviderConfigurationError, match="RUNWAYML_API_SECRET is missing"):
                RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)


def test_variant_real_smoke_requires_reference_readiness_ready(monkeypatch):
    enable_real_smoke_env(monkeypatch)

    def fail_if_instantiated(*args, **kwargs):
        raise AssertionError("Runway provider should not be created before reference readiness passes.")

    monkeypatch.setattr("app.intelligence.video_generator.RunwayVideoProvider", fail_if_instantiated)
    with client() as api:
        _, _, _, selected_variant_id = build_variant_set_fixture(api, title="Reference Gate Variant")

        with SessionLocal() as db:
            with pytest.raises(ProviderConfigurationError, match="Product reference readiness must be ready"):
                RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)


def test_variant_real_smoke_defaults_to_one_scene(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    scene_counts = install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Default One Scene Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            video_job = db.get(models.VideoJob, output.video_job_id)
            clip_count = len(video_job.clips)

        assert scene_counts == [1]
        assert clip_count == 1
        assert output.provider_job_ids == ["fake-runway-job-1"]


def test_variant_real_smoke_refuses_full_video_without_explicit_flag(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    scene_counts = install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="No Full Video Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(
                selected_variant_id,
                max_scenes=4,
                full_video=False,
                allow_real_spend=True,
            )
            video_job = db.get(models.VideoJob, output.video_job_id)
            clip_count = len(video_job.clips)

        assert scene_counts == [1]
        assert clip_count == 1


def test_variant_real_smoke_prompt_pack_contains_reference_bundle(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, bundle_id = prepare_ready_variant(api, title="Prompt Reference Bundle Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            generation_variant = db.query(models.VideoGenerationVariant).filter_by(video_job_id=output.video_job_id).one()

        assert output.reference_bundle_id
        assert generation_variant.prompt_pack_json["reference_bundle_id"] >= bundle_id
        assert generation_variant.prompt_pack_json["reference_images"][0] == "https://example.com/packshot.png"
        assert len(generation_variant.prompt_pack_json["reference_images"]) >= 2
        assert generation_variant.prompt_pack_json["product_lock_mode"] == "reference_i2v"
        assert generation_variant.prompt_pack_json["provider_reference_bundle"]["reference_asset_ids"]


def test_variant_real_smoke_generation_report_has_no_secrets(monkeypatch):
    enable_real_smoke_env(monkeypatch, runway_key="runway-test-secret-value")
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(
            api,
            title="Secret Report Variant",
            url="https://example.com/packshot.png?token=secret&signature=abc123",
        )

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)

        report_text = Path(output.generation_report_path).read_text(encoding="utf-8")
        report = json.loads(report_text)

        assert report["run_type"] == "real_one_scene_smoke"
        assert "runway-test-secret-value" not in report_text
        assert "fake-provider-secret" not in report_text
        assert "raw-secret" not in report_text
        assert "token=" not in report_text
        assert "signature=abc123" not in report_text
        assert "_jwt=" not in report_text
        assert "signed-url-secret" not in report_text
        assert report["provider_job_ids"] == ["fake-runway-job-1"]


def test_video_assembly_copies_single_clip_when_ffmpeg_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(VideoAssemblyService, "ffmpeg_path", property(lambda self: None))
    source = tmp_path / "provider_clip.mp4"
    source.write_bytes(b"real provider video bytes")

    output_path, preview_path = VideoAssemblyService().assemble(
        123,
        [source.as_posix()],
        "Open the product card",
        ["Product visible in the first frame"],
    )

    assert Path(output_path).read_bytes() == source.read_bytes()
    assert Path(preview_path).exists()


def test_variant_real_smoke_creates_quality_review_needs_human_review(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Quality Review Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            review = db.get(models.VideoQualityReview, output.quality_review_id)

        assert review.status == "needs_human_review"
        assert review.review_json["status"] == "needs_human_review"
        assert review.review_json["score"] > 0
        assert output.quality_score == review.score
        assert any(check["key"] == "generation_report_exists" and check["passed"] for check in review.review_json["checks"])


def test_geometry_lock_does_not_auto_approve_video(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Geometry Review Guard Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            review = db.get(models.VideoQualityReview, output.quality_review_id)
            generation_variant = db.query(models.VideoGenerationVariant).filter_by(video_job_id=output.video_job_id).one()

        assert review.status == "needs_human_review"
        assert review.review_json["status"] == "needs_human_review"
        assert review.status != "approved"
        assert generation_variant.prompt_pack_json["product_geometry_rules"]["preserve_reference_silhouette"] is True
        assert "Keep the product the same size and proportions as the primary reference image." in generation_variant.prompt_pack_json["scene_prompts"][0]["prompt_text"]


def test_variant_real_smoke_cli_safe_failure_without_spend_gate():
    env = os.environ.copy()
    env["QVF_GENERATION_MODE"] = "real"
    env["QVF_ALLOW_REAL_SPEND"] = "false"
    env.pop("RUNWAYML_API_SECRET", None)
    root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_variant_real_smoke.py",
            "--creative-variant-id",
            "1",
            "--video-provider",
            "runway",
            "--real-run",
            "--max-scenes",
            "1",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "QVF_ALLOW_REAL_SPEND=true" in result.stderr


def test_video_generator_ui_shows_real_smoke_eligibility(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="UI Real Smoke Variant")

        response = api.get("/video-generator")

        assert response.status_code == 200
        assert "Real Smoke Eligibility" in response.text
        assert "Run real one-scene smoke from selected variant" in response.text
        assert str(selected_variant_id) in response.text
        assert "Runway key" in response.text
        assert "test-runway-key" not in response.text


def test_demand_generator_low_ctr_selects_awareness_need():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Low CTR Demand Product", ctr=0.01, conversion_rate=0.08)

        with SessionLocal() as db:
            record = DemandHypothesisBuilder(db).build_for_product(product_id)

        hypothesis = record.hypothesis_json
        assert hypothesis["need_type"] == "awareness_need"
        assert "low_ctr" in hypothesis["performance_flags"]
        assert "curiosity_gap" in hypothesis["recommended_hook_types"]
        assert hypothesis["source_refs"]


def test_demand_generator_low_conversion_selects_trust_need():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Low Conversion Demand Product", ctr=0.04, conversion_rate=0.01)

        with SessionLocal() as db:
            record = DemandHypothesisBuilder(db).build_for_product(product_id)

        hypothesis = record.hypothesis_json
        assert hypothesis["need_type"] == "trust_and_clarity_need"
        assert "low_conversion" in hypothesis["performance_flags"]
        assert "objection_handling" in hypothesis["recommended_hook_types"]


def test_demand_generator_high_returns_selects_expectation_need():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Returns Demand Product", conversion_rate=0.08, returns_rate=0.12)

        with SessionLocal() as db:
            record = DemandHypothesisBuilder(db).build_for_product(product_id)

        hypothesis = record.hypothesis_json
        assert hypothesis["need_type"] == "expectation_setting_need"
        assert "high_returns" in hypothesis["performance_flags"]
        assert "expectation_setting" in hypothesis["recommended_hook_types"]


def test_demand_generator_competitor_price_pressure_selects_value_need():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Price Pressure Demand Product", conversion_rate=0.08, competitor_price=100)

        with SessionLocal() as db:
            record = DemandHypothesisBuilder(db).build_for_product(product_id)

        hypothesis = record.hypothesis_json
        assert hypothesis["need_type"] == "comparison_value_need"
        assert "competitor_price_pressure" in hypothesis["market_risks"]
        assert "comparison" in hypothesis["recommended_hook_types"]


def test_demand_generator_stock_risk_blocks_aggressive_direction():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Stock Risk Demand Product", conversion_rate=0.08, stock_qty=3, days_of_stock=3)

        with SessionLocal() as db:
            record = DemandHypothesisBuilder(db).build_for_product(product_id)

        hypothesis = record.hypothesis_json
        assert hypothesis["need_type"] == "soft_education_need"
        assert hypothesis["stock_risk"] == "low_stock"
        assert "no_aggressive_promo" in hypothesis["recommended_hook_types"]
        assert "buy now" not in json.dumps(hypothesis).lower()


def test_demand_generator_no_strong_data_uses_simple_intro():
    with client() as api:
        product_id = prepare_working_video_product(api, title="No Data Demand Product", with_signals=False)

        with SessionLocal() as db:
            record = DemandHypothesisBuilder(db).build_for_product(product_id)

        hypothesis = record.hypothesis_json
        assert hypothesis["need_type"] == "simple_use_case_introduction"
        assert "no_strong_data" in hypothesis["performance_flags"]
        assert "use_case_demo" in hypothesis["recommended_hook_types"]


def test_demand_validator_blocks_unsafe_promises_and_missing_proof():
    hypothesis = DemandHypothesis(
        product_id=1,
        sku="SKU-DEMAND-VALIDATOR",
        product_title="Validator Product",
        need_type="trust_and_clarity_need",
        buyer_need="Need proof.",
        trigger_situation="Buyer hesitates.",
        pain_point="Unclear proof.",
        objection="will it work?",
        safe_promise="Guaranteed medical treatment result",
        unsafe_promises_blocked=[],
        proof_required=[],
        recommended_hook_types=["trust_builder"],
        recommended_first_frame="Show the product.",
        source_refs=[],
        reasoning="Test",
    )

    report = DemandValidator().validate(hypothesis, forbidden_claims=["medical treatment"])

    assert report.valid is False
    assert report.status == "blocked"
    assert "missing_source_backed_proof" in report.missing_data
    assert report.real_video_eligible is False


def test_demand_validator_marks_blocked_references_real_ineligible():
    hypothesis = DemandHypothesis(
        product_id=1,
        sku="SKU-DEMAND-REFS",
        product_title="Reference Product",
        need_type="awareness_need",
        buyer_need="Need awareness.",
        trigger_situation="Buyer scrolls.",
        pain_point="Too generic.",
        objection="why this?",
        safe_promise="Source-backed product fit",
        proof_required=["Source-backed product fit"],
        recommended_hook_types=["curiosity_gap"],
        recommended_first_frame="Show the product.",
        source_refs=["product_field:description"],
        reasoning="Test",
    )

    report = DemandValidator().validate(
        hypothesis,
        reference_readiness_status="blocked",
        reference_blockers=["missing_approved_primary_reference"],
    )

    assert report.valid is True
    assert report.status == "ready"
    assert report.real_video_eligible is False
    assert "missing_approved_primary_reference" in report.blockers


def test_creative_spec_builder_builds_from_demand_hypothesis():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Demand Spec Product", ctr=0.01, conversion_rate=0.08)

        with SessionLocal() as db:
            demand = DemandHypothesisBuilder(db).build_for_product(product_id)
            spec = CreativeSpecBuilder(db).build_from_demand(
                demand.id,
                platform="Instagram Reels",
                duration_seconds=15,
            )

        assert spec.status == "ready"
        assert spec.spec_json["source_map"]["demand_hypothesis_id"] == demand.id
        assert spec.spec_json["hook_type"] in {"curiosity_gap", "benefit_first_frame", "contradiction"}


def test_working_video_prepare_returns_selected_variant_prompt_pack_without_paid_call(monkeypatch):
    def fail_if_provider_created(*args, **kwargs):
        raise AssertionError("prepare() must not instantiate a video provider.")

    monkeypatch.setattr("app.intelligence.video_generator.RunwayVideoProvider", fail_if_provider_created)
    with client() as api:
        product_id = prepare_working_video_product(api, title="Working Prepare Product")

        with SessionLocal() as db:
            result = WorkingVideoGenerator(db).prepare(product_id, "Instagram Reels", 15, 5)

        assert result.buyer_need
        assert result.selected_variant_id
        assert result.prompt_pack_id
        assert result.prompt_pack["creative_variant_id"] == result.selected_variant_id
        assert result.real_smoke_eligible is False
        assert any(blocker.startswith("reference:") for blocker in result.real_smoke_blockers)
        assert "spend_gate:QVF_GENERATION_MODE=real" in result.real_smoke_blockers


def test_working_video_prompt_only_from_selected_variant():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Working Prompt Product")

        with SessionLocal() as db:
            prepared = WorkingVideoGenerator(db).prepare(product_id, "Instagram Reels", 15, 5)
            prompt_only = WorkingVideoGenerator(db).run_prompt_only(prepared.selected_variant_id)

        assert prompt_only.prompt_pack_id
        assert prompt_only.selected_variant_id == prepared.selected_variant_id
        assert prompt_only.prompt_pack["reference_readiness_status"] in {"blocked", "ready"}


def test_ugc_realism_contract_feeds_variant_prompt_and_assignment():
    with client() as api:
        product_id, spec_id, _, selected_variant_id = build_variant_set_fixture(
            api,
            title="Bombbar Pro Dubai Mango & Kunafa 45 g",
            count=3,
        )

        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Sport UGC Creator", role="creator")
            content_run = models.ContentRun(
                product_id=product_id,
                platform="Instagram Reels",
                duration_seconds=8,
                creative_spec_id=spec_id,
                selected_variant_id=selected_variant_id,
                status="prompt_ready",
            )
            db.add(content_run)
            db.commit()
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                product_id=product_id,
                content_run_id=content_run.id,
                creative_variant_id=selected_variant_id,
            )

            variant = UGCRealismService(db).apply_to_variant(selected_variant_id, duration_seconds=8)
            scene = variant.scene_plan_json[0]
            generation = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")
            prompt_scene = generation.prompt_pack_json["scene_prompts"][0]
            db.refresh(assignment)

        assert scene["duration_seconds"] == 8
        assert scene["caption"] == ""
        assert len(scene["provider_prompt_text"]) <= 1000
        assert "Sporty athletic adult woman presenter age 25-30" in scene["provider_prompt_text"]
        assert "never from wrapper or package" in scene["provider_prompt_text"]
        assert "no on-screen text" in scene["provider_prompt_text"]
        assert "bottle" not in scene["provider_prompt_text"].lower()
        assert prompt_scene["prompt_text"] == scene["provider_prompt_text"]
        assert prompt_scene["duration_seconds"] == 8
        assert "biting wrapper" in prompt_scene["negative_prompt"]
        assert "on-screen text" in prompt_scene["negative_prompt"]
        assert assignment.brief_json["ugc_realism_contract"]["presenter"] == "sporty athletic woman, 25-30, fitness lifestyle"
        assert "no wrapper biting" in assignment.brief_json["corrections"]


def test_runway_provider_uses_prompt_image_for_local_reference(monkeypatch, tmp_path):
    image = tmp_path / "packshot.png"
    image.write_bytes(b"not-a-real-png-but-local-reference")
    captured = {}

    class FakeResponse:
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "runway-task-1", "status": "queued"}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["payload"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.providers.runway_video.httpx.post", fake_post)
    prompt_pack = PromptPackOutput(
        provider="runway",
        aspect_ratio="9:16",
        duration_seconds=8,
        scene_prompts=[
            PromptSceneOutput(
                scene_number=1,
                duration_seconds=8,
                prompt_text="x" * 1200,
                negative_prompt="distorted product",
                reference_images=[str(image)],
            )
        ],
    )

    job = RunwayVideoProvider(api_secret="test-key").create_generation(prompt_pack)

    assert captured["url"].endswith("/image_to_video")
    assert captured["payload"]["promptImage"].startswith("data:image/png;base64,")
    assert len(captured["payload"]["promptText"]) == 1000
    assert captured["payload"]["duration"] == 8
    assert job.provider_job_id == "runway-task-1"
    assert job.raw_response["prompt_image_used"] is True


def test_working_video_real_smoke_reuses_sprint_07_gates(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "mock")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "false")
    monkeypatch.delenv("RUNWAYML_API_SECRET", raising=False)
    get_settings.cache_clear()
    with client() as api:
        product_id = prepare_working_video_product(api, title="Working Real Smoke Gate Product")

        with SessionLocal() as db:
            prepared = WorkingVideoGenerator(db).prepare(product_id, "Instagram Reels", 15, 5)
            with pytest.raises(ProviderConfigurationError, match="QVF_GENERATION_MODE=real"):
                WorkingVideoGenerator(db).run_real_smoke(
                    prepared.selected_variant_id,
                    provider="runway",
                    allow_real_spend=True,
                )


def test_working_video_api_prepare_and_status():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Working API Product")

        response = api.post(
            "/api/working-video/prepare",
            json={"product_id": product_id, "platform": "Instagram Reels", "duration_seconds": 15, "variant_count": 5},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        status = api.get(f"/api/working-video/status/{payload['selected_variant_id']}")

        assert payload["buyer_need"]
        assert payload["selected_variant_id"]
        assert payload["prompt_pack_id"]
        assert status.status_code == 200, status.text
        assert status.json()["selected_variant_id"] == payload["selected_variant_id"]


def test_working_video_ui_shows_primary_guided_page():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Working UI Product")

        response = api.post(
            "/working-video-generator/run",
            data={
                "action": "prepare",
                "product_id": str(product_id),
                "platform": "Instagram Reels",
                "duration": "15",
                "variant_count": "5",
            },
        )

        assert response.status_code == 200, response.text
        assert "Working Video Generator" in response.text
        assert "buyer_need" in response.text
        assert "safe_promise" in response.text
        assert "selected_variant_id" in response.text
        assert "prompt_pack_id" in response.text
        assert "real_smoke_eligible" in response.text
        assert "missing references / spend gate blockers" in response.text
        assert "Prompt Pack" in response.text
        assert "Run real one-scene smoke" in response.text


def test_prepare_content_run_creates_demand_spec_variant_prompt_pack():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Prepare Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)
            content_run = db.get(models.ContentRun, result.id)
            assignment_count = db.query(models.ContentAssignment).filter_by(content_run_id=result.id).count()

        assert result.demand_hypothesis_id
        assert result.creative_spec_id
        assert result.selected_variant_id
        assert result.generation_variant_id
        assert result.prompt_pack_id
        assert result.ai_review_id
        assert content_run is not None
        assert assignment_count >= 5


def test_prepare_content_run_does_not_call_paid_provider(monkeypatch):
    def fail_if_video_job_is_created(*args, **kwargs):
        raise AssertionError("prepare_content_run must not create or start paid video jobs.")

    monkeypatch.setattr(
        "app.video_generator.generator.GeneratorVideoService.create_video_job_from_prompt_pack",
        fail_if_video_job_is_created,
    )
    monkeypatch.setattr(
        "app.workflows.working_video_generator.RealSmokeRunner.run_from_variant",
        fail_if_video_job_is_created,
    )
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory No Provider Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)

        assert result.prompt_pack_id
        assert result.video_job_id is None


def test_content_run_review_requires_human_when_visual_identity_unverified():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Review Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)
            review = db.get(models.AIContentReview, result.ai_review_id)

        assert review.status == "needs_human_review"
        assert review.human_review_required is True
        assert any("No computer vision" in note for note in review.review_json["notes"])
        assert all(check["check_type"] == "metadata" for check in review.review_json["checks"])


def test_content_run_recommendation_add_reference_when_missing():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Missing Reference Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)

        actions = {action.action for action in result.next_actions}
        assert "add_product_reference" in actions
        assert "add_product_references" in actions
        assert any(blocker.startswith("reference:") for blocker in result.blockers)


def test_content_run_recommendation_real_smoke_when_ready():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Ready Reference Product")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id)
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)

        actions = {action.action for action in result.next_actions}
        assert "run_real_smoke" in actions
        assert "add_product_reference" not in actions
        assert "add_product_references" not in actions
        assert result.run["reference_readiness"]["status"] == "ready"
        assert result.run["reference_policy"]["strict_real_generation_allowed"] is True


def test_content_run_prompt_only_never_calls_video_provider(monkeypatch):
    def fail_if_video_job_is_created(*args, **kwargs):
        raise AssertionError("content prompt-only must not create or start video jobs.")

    monkeypatch.setattr(
        "app.video_generator.generator.GeneratorVideoService.create_video_job_from_prompt_pack",
        fail_if_video_job_is_created,
    )
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Prompt Only Product")

        with SessionLocal() as db:
            orchestrator = ContentRunOrchestrator(db)
            prepared = orchestrator.prepare_content_run(product_id, "Instagram Reels", 15, 5)
            prompt_only = orchestrator.run_prompt_only(prepared.id)

        assert prompt_only.status == "prompt_ready"
        assert prompt_only.prompt_pack_id
        assert prompt_only.video_job_id is None


def test_content_stats_import_csv():
    csv_text = (
        "content_run_id,product_id,sku,platform,metric_date,impressions,views,clicks,orders,revenue,spend,retention_rate\n"
        ",,SKU-FACTORY,Instagram Reels,2026-07-05,1000,800,40,4,12000,3000,0.41\n"
    )
    with client():
        with SessionLocal() as db:
            result = ContentStatsImporter(db).import_csv_text(csv_text)
            metric = db.query(models.ContentPerformanceMetric).one()

        assert result.imported_count == 1
        assert result.error_count == 0
        assert metric.platform == "Instagram Reels"
        assert metric.ctr == 0.04
        assert metric.conversion_rate == 0.1


def test_content_factory_dashboard_counts_runs_and_blockers():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Dashboard Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)
            ContentStatsImporter(db).import_csv_text(
                "content_run_id,product_id,sku,platform,metric_date,views,clicks,orders\n"
                f"{result.id},{product_id},{result.sku},Instagram Reels,2026-07-05,1000,20,1\n"
            )
            dashboard = ContentPerformanceService(db).dashboard()

        assert dashboard.total_runs == 1
        assert dashboard.prompt_ready_runs == 1
        assert dashboard.human_review_queue >= 1
        assert dashboard.performance_metric_count == 1
        assert dashboard.top_blockers


def test_content_factory_ui_renders_main_workspace():
    with client() as api:
        response = api.get("/content-factory")

        assert response.status_code == 200
        assert "AI Content Factory" in response.text
        assert "Factory Overview" in response.text
        assert "Run Builder" in response.text
        assert "AI Review Queue" in response.text
        assert "Performance" in response.text


def test_content_factory_api_prepare_dashboard_and_recommendations():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory API Product")

        prepare_response = api.post(
            "/api/content-factory/runs/prepare",
            json={"product_id": product_id, "platform": "Instagram Reels", "duration_seconds": 15, "variant_count": 5},
        )
        assert prepare_response.status_code == 200, prepare_response.text
        content_run_id = prepare_response.json()["id"]

        recommendations = api.get(f"/api/content-factory/runs/{content_run_id}/recommendations")
        dashboard = api.get("/api/content-factory/dashboard")

        assert recommendations.status_code == 200, recommendations.text
        assert dashboard.status_code == 200, dashboard.text
        assert recommendations.json()["recommendations"]
        assert dashboard.json()["total_runs"] == 1


def test_content_run_ai_review_checks_geometry_lock():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Geometry Review Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)
            review = db.get(models.AIContentReview, result.ai_review_id)

        check_keys = {check["key"] for check in review.review_json["checks"]}
        assert "product_geometry_rules_present" in check_keys
        assert "product_scale_rules_present" in check_keys
        assert "negative_prompt_blocks_size_proportion_drift" in check_keys
        assert result.geometry_readiness["status"] == "ready"
        assert result.geometry_readiness["negative_prompt_blocks_geometry_drift"] is True


def test_content_run_recommends_add_geometry_lock_when_missing():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Missing Geometry Product")

        with SessionLocal() as db:
            orchestrator = ContentRunOrchestrator(db)
            result = orchestrator.prepare_content_run(product_id, "Instagram Reels", 15, 5)
            content_run = db.get(models.ContentRun, result.id)
            run_json = dict(content_run.run_json)
            prompt_pack = dict(run_json["prompt_pack"])
            prompt_pack.pop("product_geometry_spec", None)
            prompt_pack.pop("product_geometry_rules", None)
            prompt_pack.pop("product_scale_rules", None)
            prompt_pack["scene_prompts"] = [
                {**scene, "negative_prompt": "distorted product"}
                for scene in prompt_pack.get("scene_prompts", [])
            ]
            run_json["prompt_pack"] = prompt_pack
            content_run.run_json = run_json
            db.commit()
            reviewed = orchestrator.review(result.id)

        actions = {action.action for action in reviewed.next_actions}
        assert "geometry_lock_missing" in reviewed.blockers
        assert "add_geometry_lock" in actions
        assert reviewed.geometry_readiness["status"] == "blocked"


def test_content_run_recommends_geometry_regeneration_on_product_geometry_mismatch():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Geometry Mismatch Product")

        with SessionLocal() as db:
            orchestrator = ContentRunOrchestrator(db)
            result = orchestrator.prepare_content_run(product_id, "Instagram Reels", 15, 5)
            content_run = db.get(models.ContentRun, result.id)
            generation_variant = db.get(models.VideoGenerationVariant, result.generation_variant_id)
            video_job = models.VideoJob(
                script_variant_id=generation_variant.script_variant_id,
                provider="mock",
                status="needs_human_review",
            )
            db.add(video_job)
            db.flush()
            generation_variant.video_job_id = video_job.id
            content_run.video_job_id = video_job.id
            db.commit()
            RegenerationRequestService(db).create(
                video_job_id=video_job.id,
                scene_number=1,
                reason="product_geometry_mismatch",
                feedback="Product size/proportions drifted; preserve exact bottle silhouette.",
            )
            reviewed = orchestrator.review(result.id)

        actions = {action.action for action in reviewed.next_actions}
        assert reviewed.status == "needs_regeneration"
        assert "product_geometry_mismatch" in reviewed.blockers
        assert "request_geometry_regeneration" in actions


def test_content_factory_dashboard_counts_geometry_blockers():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory Geometry Dashboard Product")

        with SessionLocal() as db:
            orchestrator = ContentRunOrchestrator(db)
            result = orchestrator.prepare_content_run(product_id, "Instagram Reels", 15, 5)
            content_run = db.get(models.ContentRun, result.id)
            generation_variant = db.get(models.VideoGenerationVariant, result.generation_variant_id)
            video_job = models.VideoJob(
                script_variant_id=generation_variant.script_variant_id,
                provider="mock",
                status="needs_human_review",
            )
            db.add(video_job)
            db.flush()
            generation_variant.video_job_id = video_job.id
            content_run.video_job_id = video_job.id
            db.commit()
            RegenerationRequestService(db).create(
                video_job_id=video_job.id,
                scene_number=1,
                reason="product_geometry_mismatch",
                feedback="Product scale mismatch after generation.",
            )
            orchestrator.review(result.id)
            dashboard = ContentPerformanceService(db).dashboard()

        assert dashboard.needs_regeneration_runs == 1
        assert dashboard.geometry_mismatch_blockers == 1


def test_content_factory_ui_shows_geometry_readiness_and_next_actions():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory UI Geometry Product")
        response = api.post(
            "/content-factory/run",
            data={
                "action": "prepare",
                "product_id": str(product_id),
                "platform": "Instagram Reels",
                "duration": "15",
                "variant_count": "5",
            },
        )

        assert response.status_code == 200, response.text
        assert "buyer_need" in response.text
        assert "safe_promise" in response.text
        assert "Reference readiness" in response.text
        assert "Geometry readiness" in response.text
        assert "product identity blockers" in response.text
        assert "geometry/scale blockers" in response.text
        assert "Next action" in response.text


def test_prepare_content_run_prints_geometry_status():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory CLI Geometry Product")
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/prepare_content_run.py",
                "--product-id",
                str(product_id),
                "--platform",
                "Instagram Reels",
                "--duration",
                "15",
                "--variant-count",
                "5",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, result.stderr
        assert "Buyer Need:" in result.stdout
        assert "Safe Promise:" in result.stdout
        assert "Reference Readiness:" in result.stdout
        assert "Geometry Readiness:" in result.stdout
        assert "Human Review Required:" in result.stdout


def test_content_run_does_not_auto_approve_visual_identity():
    with client() as api:
        product_id = prepare_working_video_product(api, title="Factory No Auto Approval Product")

        with SessionLocal() as db:
            result = ContentRunOrchestrator(db).prepare_content_run(product_id, "Instagram Reels", 15, 5)
            review = db.get(models.AIContentReview, result.ai_review_id)

        assert result.human_review_required is True
        assert review.status not in {"approved", "human_approved"}
        assert result.publishing_readiness["status"] != "ready"
        assert any("No computer vision" in note for note in review.review_json["notes"])


def campaign_matrix_csv(row_count: int = 3, *, with_photos: bool = True) -> str:
    rows = ["sku,product_name,category,price,stock_qty,product_url,photo_1,photo_2,photo_3,priority"]
    for index in range(1, row_count + 1):
        photo = f"https://example.com/product_{index}.png" if with_photos else ""
        priority = 5 if index <= 5 else 1
        stock = 8 if index % 10 == 0 else 80 + index
        rows.append(
            ",".join(
                [
                    f"CAMP-{index:03d}",
                    f"Campaign Product {index}",
                    "Skincare",
                    str(500 + index),
                    str(stock),
                    f"https://example.com/campaign/{index}",
                    photo,
                    "",
                    "",
                    str(priority),
                ]
            )
        )
    return "\n".join(rows) + "\n"


def campaign_fixture(
    row_count: int = 3,
    *,
    target_videos: int = 12,
    target_destinations: int = 4,
    with_photos: bool = True,
) -> int:
    with SessionLocal() as db:
        imported = ProductMatrixImporter(db).import_csv_text(campaign_matrix_csv(row_count, with_photos=with_photos))
        campaign = CampaignService(db).create_campaign(
            name="Campaign Autopilot Test",
            brand="Bombar",
            import_id=imported.import_id,
            target_video_count=target_videos,
            target_destination_count=target_destinations,
            source_type="csv",
        )
        return campaign.campaign_id


def bombar_csv(row_count: int = 3, *, with_photos: bool = True) -> str:
    rows = ["sku,product_name,category,price,margin,stock_qty,product_url,photo_1,photo_2,photo_3"]
    for index in range(1, row_count + 1):
        photo = f"https://example.com/packshot_{index}.png" if with_photos else ""
        rows.append(
            ",".join(
                [
                    f"BOMBAR-{index:03d}",
                    f"Bombar Product {index}",
                    "Skincare",
                    str(700 + index),
                    "0.42",
                    str(80 + index),
                    f"https://example.com/products/{index}",
                    photo,
                    "",
                    "",
                ]
            )
        )
    return "\n".join(rows) + "\n"


def bombar_xlsx_bytes(rows: list[list[str]]) -> bytes:
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row):
            column = chr(ord("A") + col_index)
            cells.append(f'<c r="{column}{row_index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def create_bombar_campaign_fixture(
    row_count: int = 3,
    *,
    target_videos: int = 12,
    target_destinations: int = 4,
    with_photos: bool = True,
) -> int:
    with SessionLocal() as db:
        imported = BombarMatrixImporter(db).import_csv_text(bombar_csv(row_count, with_photos=with_photos))
        campaign = LaunchPlanner(db).create_campaign(
            imported.import_id,
            name="Bombar Test Campaign",
            target_video_count=target_videos,
            target_destination_count=target_destinations,
        )
        return campaign.campaign_id


def add_campaign_destination(db, brand: str = "Bombar", daily_limit: int = 1, weekly_limit: int = 3) -> int:
    destination = models.PublishingDestination(
        brand=brand,
        platform="Instagram Reels",
        name=f"{brand} Reels",
        handle=f"@{brand.lower()}",
        status="ready",
        posting_mode="manual",
        auth_status="manual_only",
        daily_limit=daily_limit,
        weekly_limit=weekly_limit,
        allowed_formats_json=["vertical_video"],
    )
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return destination.id


def add_approved_campaign_package(db, product: models.Product) -> int:
    template = db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
    guide = db.scalar(select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id))
    script_job = models.ScriptJob(
        product_id=product.id,
        template_id=template.id,
        brand_guide_id=guide.id,
        status="script_approved",
        input_payload_json={},
        output_script_json={},
        validation_report_json={},
    )
    db.add(script_job)
    db.flush()
    variant = models.ScriptVariant(
        script_job_id=script_job.id,
        variant_number=1,
        creative_angle="campaign",
        hook="Campaign hook",
        key_message="Campaign message",
        final_cta="Open product card",
        full_script_json={},
        status="script_approved",
    )
    db.add(variant)
    db.flush()
    video_job = models.VideoJob(
        script_variant_id=variant.id,
        provider="mock",
        status="approved",
        output_video_path=f"media/mock/{product.sku}.mp4",
    )
    db.add(video_job)
    db.flush()
    package = models.PublishingPackage(
        video_job_id=video_job.id,
        product_id=product.id,
        brand=product.brand,
        target_platform="Instagram Reels",
        title=f"{product.title} launch",
        description="Approved campaign package.",
        hashtags_json=["#campaign"],
        cta="Open product card",
        product_url=product.product_url,
        video_file_path=video_job.output_video_path,
        review_status="approved",
        status="approved",
        metadata_json={"source": "test"},
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    return package.id


def add_batch_action(
    db,
    campaign_id: int,
    action_type: str = "run_prompt_only",
    *,
    safe: bool = True,
    requires_human: bool = False,
    blockers: list[str] | None = None,
) -> int:
    action = models.CampaignActionQueueItem(
        campaign_id=campaign_id,
        action_type=action_type,
        priority=5,
        status="open",
        reason="test batch action",
        blockers_json=blockers or [],
        safe_to_execute=safe,
        requires_human=requires_human,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action.id


def add_campaign_published_task(db, campaign_id: int, final_url: str = "https://example.com/post/perf") -> tuple[models.Product, models.PublishingTask]:
    campaign = db.get(models.Campaign, campaign_id)
    product = db.get(models.Product, campaign.product_ids_json[0])
    package_id = add_approved_campaign_package(db, product)
    destination_id = add_campaign_destination(db, brand=campaign.brand)
    task = models.PublishingTask(
        publishing_package_id=package_id,
        destination_id=destination_id,
        platform="Instagram Reels",
        status="published_manual",
        scheduled_at=datetime.now(UTC).replace(tzinfo=None),
        final_url=final_url,
        operator_name="ops",
        raw_response_json={"source": "test"},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return product, task


def performance_csv(rows: list[dict]) -> str:
    columns = [
        "campaign_id",
        "sku",
        "platform",
        "posted_url",
        "destination_name",
        "creative_variant_id",
        "period_start",
        "period_end",
        "views",
        "likes",
        "comments",
        "shares",
        "saves",
        "clicks",
        "orders",
        "revenue",
        "spend",
        "watch_time_seconds",
        "retention_rate",
    ]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row.get(column, "")) for column in columns))
    return "\n".join(lines) + "\n"


def destination_metrics_csv(rows: list[dict]) -> str:
    columns = [
        "campaign_id",
        "destination_name",
        "platform",
        "posted_url",
        "sku",
        "period_start",
        "period_end",
        "views",
        "likes",
        "comments",
        "shares",
        "saves",
        "clicks",
        "orders",
        "revenue",
        "spend",
        "watch_time_seconds",
        "retention_rate",
    ]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row.get(column, "")) for column in columns))
    return "\n".join(lines) + "\n"


def metrics_intake_csv(rows: list[dict]) -> str:
    columns = [
        "platform",
        "destination_handle",
        "posted_url",
        "tracking_slug",
        "publishing_task_id",
        "sku",
        "period_start",
        "period_end",
        "views",
        "reach",
        "impressions",
        "likes",
        "comments",
        "shares",
        "saves",
        "clicks",
        "orders",
        "revenue",
        "spend",
    ]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row.get(column, "")) for column in columns))
    return "\n".join(lines) + "\n"


def test_import_product_matrix_csv():
    with client():
        with SessionLocal() as db:
            result = ProductMatrixImporter(db).import_csv_text(campaign_matrix_csv(2), source_file="matrix.csv")
            rows = db.scalars(select(models.ProductMatrixRow).order_by(models.ProductMatrixRow.id)).all()

        assert result.status == "imported"
        assert result.imported_count == 2
        assert rows[0].sku == "CAMP-001"


def test_matrix_import_missing_photos_warns_not_fails():
    with client():
        with SessionLocal() as db:
            result = ProductMatrixImporter(db).import_csv_text(campaign_matrix_csv(1, with_photos=False))
            row = db.scalar(select(models.ProductMatrixRow))

        assert result.imported_count == 1
        assert result.error_count == 0
        assert "missing_photo" in row.warnings_json
        assert any("missing_photo" in warning for warning in result.warnings)


def test_create_campaign_from_import():
    with client():
        campaign_id = campaign_fixture(row_count=3, target_videos=21, target_destinations=6)
        with SessionLocal() as db:
            campaign = db.get(models.Campaign, campaign_id)
            products = db.scalars(select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign_id)).all()

        assert campaign.source_type == "csv"
        assert len(campaign.product_ids_json) == 3
        assert len(products) == 3
        assert sum(item.target_video_count for item in products) == 21


def test_target_allocator_40_sku_350_videos():
    with client():
        campaign_id = campaign_fixture(row_count=40, target_videos=350, target_destinations=120)
        with SessionLocal() as db:
            allocation = TargetAllocator(db).allocate(campaign_id)
            campaign_products = db.scalars(select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign_id)).all()

        assert allocation.total_products == 40
        assert allocation.total_target_videos == 350
        assert max(item.target_video_count for item in campaign_products) >= 9
        assert min(item.target_video_count for item in campaign_products) >= 1


def test_campaign_prepare_creates_campaign_products():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=8, target_destinations=3)
        with SessionLocal() as db:
            result = CampaignRunner(db).prepare_campaign(campaign_id)
            campaign_product = db.scalar(select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign_id))

        assert result.total_products == 1
        assert campaign_product.content_run_ids_json
        assert result.total_content_runs >= 1


def test_campaign_prepare_calls_content_autopilot_without_paid_provider(monkeypatch):
    def fail_paid(*args, **kwargs):
        raise AssertionError("Campaign prepare must not call paid real smoke.")

    monkeypatch.setattr("app.content_factory.content_run_orchestrator.ContentRunOrchestrator.run_real_smoke", fail_paid)
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            result = CampaignRunner(db).prepare_campaign(campaign_id)
            runs = db.scalars(select(models.ContentRun)).all()

        assert result.total_content_runs >= 1
        assert runs
        assert all(run.video_job_id is None for run in runs)


def test_campaign_state_counts_blockers_and_ready_items():
    with client():
        campaign_id = campaign_fixture(row_count=2, target_videos=6, target_destinations=2, with_photos=False)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            state = CampaignRunner(db).inspect_campaign(campaign_id)

        assert state.sku_coverage["total_sku"] == 2
        assert state.prompt_ready_count >= 1
        assert state.blocked_count >= 1
        assert state.next_actions_by_sku


def test_campaign_prompt_only_runs_only_safe_actions(monkeypatch):
    def fail_paid(*args, **kwargs):
        raise AssertionError("Prompt-only campaign action must not call paid real smoke.")

    monkeypatch.setattr("app.content_factory.content_run_orchestrator.ContentRunOrchestrator.run_real_smoke", fail_paid)
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            result = CampaignRunner(db).run_prompt_only_for_ready_items(campaign_id)

        assert result.status == "prompt_only_complete"
        assert result.total_prompt_ready >= 1


def test_campaign_distribution_plan_requires_approved_packages():
    with client():
        campaign_id = campaign_fixture(row_count=2, target_videos=6, target_destinations=2)
        with SessionLocal() as db:
            add_campaign_destination(db)
            plan = CampaignDistributionPlanner(db).generate_plan(campaign_id)

        assert plan.status == "blocked"
        assert "approved_packages_required" in plan.blockers
        assert "not_enough_approved_packages" in plan.blockers


def test_campaign_distribution_plan_respects_destination_limits():
    with client():
        campaign_id = campaign_fixture(row_count=2, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            campaign = db.get(models.Campaign, campaign_id)
            product_ids = campaign.product_ids_json
            products = db.scalars(select(models.Product).where(models.Product.id.in_(product_ids)).order_by(models.Product.id)).all()
            for product in products:
                add_approved_campaign_package(db, product)
            add_campaign_destination(db, daily_limit=1, weekly_limit=2)
            plan = CampaignDistributionPlanner(db).generate_plan(campaign_id)
            tasks = db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.id)).all()

        assert plan.scheduled_slots == 2
        assert plan.status in {"blocked", "planned"}
        assert len(tasks) == 2
        assert tasks[0].scheduled_at.date() != tasks[1].scheduled_at.date()


def test_campaign_ui_renders_setup_state_and_actions():
    with client() as api:
        campaign_id = campaign_fixture(row_count=2, target_videos=6, target_destinations=2)
        response = api.get(f"/campaign-autopilot?campaign_id={campaign_id}")

        assert response.status_code == 200, response.text
        assert "Campaign Setup" in response.text
        assert "Product Matrix" in response.text
        assert "Campaign State" in response.text
        assert "SKU Action Table" in response.text
        assert "Distribution Plan" in response.text
        assert "Performance" in response.text


def test_campaign_report_outputs_summary():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            report = CampaignRunner(db).generate_campaign_report(campaign_id)

        assert report.campaign_id == campaign_id
        assert report.state.sku_coverage["total_sku"] == 1
        assert "content_run_count" in report.performance


def test_execution_snapshot_counts_campaign_state():
    with client():
        campaign_id = campaign_fixture(row_count=2, target_videos=6, target_destinations=2, with_photos=False)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            snapshot = ExecutionStateService(db).refresh_snapshot(campaign_id)

        blocker_names = {item["blocker"] for item in snapshot.blockers}
        assert snapshot.total_sku == 2
        assert snapshot.prompt_ready_count >= 1
        assert snapshot.blocked_sku >= 1
        assert "missing_references" in blocker_names


def test_execution_queue_deduplicates_actions():
    with client():
        campaign_id = campaign_fixture(row_count=2, target_videos=6, target_destinations=2, with_photos=False)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            service = ActionQueueService(db)
            first = service.refresh_actions(campaign_id)
            second = service.refresh_actions(campaign_id)

        keys = [(item.sku, item.content_run_id, item.action_type) for item in second]
        assert len(second) == len(first)
        assert len(keys) == len(set(keys))


def test_execution_blocks_paid_action_without_gate():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            action = models.CampaignActionQueueItem(
                campaign_id=campaign_id,
                action_type="run_real_smoke",
                priority=1,
                status="open",
                blockers_json=["paid_provider_gate"],
                safe_to_execute=False,
                requires_human=False,
            )
            db.add(action)
            db.commit()
            result = ActionQueueService(db).execute(action.id)

        assert result.executed is False
        assert result.status == "blocked"
        assert "paid_action_requires_gate" in result.artifacts["blockers"]


def test_execution_blocks_publishing_unapproved_video():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            action = models.CampaignActionQueueItem(
                campaign_id=campaign_id,
                action_type="schedule_distribution",
                priority=1,
                status="open",
                blockers_json=[],
                safe_to_execute=True,
                requires_human=False,
            )
            db.add(action)
            db.commit()
            result = ActionQueueService(db).execute(action.id)

        assert result.executed is False
        assert result.status == "blocked"
        assert "approved_video_required" in result.artifacts["blockers"]


def test_execution_action_queue_contains_missing_reference():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2, with_photos=False)
        with SessionLocal() as db:
            actions = ActionQueueService(db).refresh_actions(campaign_id)

        assert any(action.action_type == "add_reference" for action in actions)


def test_execution_action_queue_contains_human_review():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            actions = ActionQueueService(db).refresh_actions(campaign_id)

        assert any(action.action_type == "human_review" for action in actions)


def test_execution_report_exports_summary():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            CampaignRunner(db).prepare_campaign(campaign_id)
            report = ExecutionReportService(db).build_report(campaign_id)

        assert report.summary["total_sku"] == 1
        assert "open_action_count" in report.summary
        assert "total_sku" in report.summary_csv
        assert "open_action_count" in report.summary_csv


def test_campaign_execution_ui_renders():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        response = api.get(f"/campaign-execution?campaign_id={campaign_id}")

        assert response.status_code == 200, response.text
        assert "Execution Control Center" in response.text
        assert "Action Queue" in response.text
        assert "SKU Table" in response.text
        assert "Summary JSON" in response.text
        assert "Summary CSV" in response.text


def test_batch_dry_run_selects_safe_actions():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            action_id = add_batch_action(db, campaign_id, "run_prompt_only")
            result = BatchExecutor(db).dry_run(campaign_id, action_type="run_prompt_only")
            item = db.scalar(select(models.CampaignBatchItem).where(models.CampaignBatchItem.batch_run_id == result.batch_run_id))

        assert result.status == "dry_run"
        assert result.selected_action_ids == [action_id]
        assert result.total_selected == 1
        assert result.total_executed == 0
        assert item.status == "would_execute"


def test_batch_executor_blocks_paid_actions():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_batch_action(db, campaign_id, "run_real_smoke", blockers=["paid_provider_gate"])
            result = BatchExecutor(db).execute(campaign_id, action_type="run_real_smoke")

        assert result.status == "blocked"
        assert result.total_selected == 0
        assert result.total_skipped == 1
        assert any("unsafe_action:run_real_smoke" in warning for warning in result.warnings)


def test_batch_executor_blocks_publishing_approval():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_batch_action(db, campaign_id, "approve_publishing_package")
            result = BatchExecutor(db).execute(campaign_id, action_type="approve_publishing_package")

        assert result.status == "blocked"
        assert result.total_selected == 0
        assert result.total_skipped == 1
        assert any("unsafe_action:approve_publishing_package" in warning for warning in result.warnings)


def test_batch_executor_runs_prompt_only_actions():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            action_id = add_batch_action(db, campaign_id, "run_prompt_only")
            result = BatchExecutor(db).execute(campaign_id, action_type="run_prompt_only")
            action = db.get(models.CampaignActionQueueItem, action_id)

        assert result.status == "completed"
        assert result.total_executed == 1
        assert action.status == "done"


def test_batch_executor_creates_result_log():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_batch_action(db, campaign_id, "run_prompt_only")
            result = BatchExecutor(db).execute(campaign_id, action_type="run_prompt_only")
            batch = db.get(models.CampaignBatchRun, result.batch_run_id)
            items = db.scalars(select(models.CampaignBatchItem).where(models.CampaignBatchItem.batch_run_id == result.batch_run_id)).all()

        assert batch.total_executed == 1
        assert batch.results_json
        assert len(items) == 1
        assert items[0].status == "done"


def test_batch_report_exports_summary():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_batch_action(db, campaign_id, "run_prompt_only")
            result = BatchExecutor(db).dry_run(campaign_id, action_type="run_prompt_only")
            report = BatchReporter(db).build_report(result.batch_run_id)

        assert report.summary["batch_run_id"] == result.batch_run_id
        assert "total_selected" in report.summary_csv
        assert "batch_run_id" in report.summary_csv


def test_campaign_execution_snapshot_updates_after_batch():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_batch_action(db, campaign_id, "run_prompt_only")
            BatchExecutor(db).execute(campaign_id, action_type="run_prompt_only")
            snapshot = db.scalar(
                select(models.CampaignExecutionSnapshot)
                .where(models.CampaignExecutionSnapshot.campaign_id == campaign_id)
                .order_by(models.CampaignExecutionSnapshot.id.desc())
            )

        assert snapshot is not None
        assert snapshot.total_sku == 1


def test_campaign_batch_ui_renders():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_batch_action(db, campaign_id, "run_prompt_only")
        response = api.get(f"/campaign-batch?campaign_id={campaign_id}&action_type=run_prompt_only")

        assert response.status_code == 200, response.text
        assert "Campaign Batch Executor" in response.text
        assert "Safe Actions" in response.text
        assert "Dry Run" in response.text
        assert "Execute Safe Batch" in response.text


def test_import_campaign_performance_csv():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            result = CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv(
                    [
                        {
                            "sku": product.sku,
                            "platform": "Instagram Reels",
                            "posted_url": task.final_url,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-05",
                            "views": 2000,
                            "likes": 140,
                            "comments": 20,
                            "shares": 20,
                            "saves": 20,
                            "clicks": 120,
                            "orders": 12,
                            "revenue": 18000,
                            "spend": 2400,
                        }
                    ]
                ),
            )
            metric = db.scalar(select(models.CampaignPerformanceMetric))

        assert result.imported_count == 1
        assert result.error_count == 0
        assert metric.sku == product.sku
        assert metric.ctr == 0.06
        assert metric.engagement_rate == 0.1


def test_import_performance_missing_metrics_warns_not_fails():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product = db.get(models.Product, db.get(models.Campaign, campaign_id).product_ids_json[0])
            result = CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv([{"sku": product.sku, "platform": "Instagram Reels", "posted_url": "https://example.com/post/missing"}]),
            )

        assert result.imported_count == 1
        assert result.error_count == 0
        assert any("missing_views" in warning for warning in result.warnings)
        assert any("posted_url_not_matched_to_task" in warning for warning in result.warnings)


def test_performance_links_metric_to_publishing_task_by_url():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/link-me")
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv(
                    [
                        {
                            "sku": product.sku,
                            "platform": "Instagram Reels",
                            "posted_url": task.final_url,
                            "views": 100,
                            "clicks": 5,
                            "orders": 1,
                        }
                    ]
                ),
            )
            metric = db.scalar(select(models.CampaignPerformanceMetric))

        assert metric.publishing_task_id == task.id
        assert metric.destination_id == task.destination_id


def test_performance_scores_sku_variant_destination():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv(
                    [
                        {
                            "sku": product.sku,
                            "platform": "Instagram Reels",
                            "posted_url": task.final_url,
                            "creative_variant_id": 777,
                            "views": 1500,
                            "likes": 100,
                            "comments": 10,
                            "shares": 10,
                            "saves": 10,
                            "clicks": 90,
                            "orders": 9,
                        }
                    ]
                ),
            )
            scores = CampaignPerformanceScorer(db).compute_scores(campaign_id)

        entity_types = {score.entity_type for score in scores}
        assert {"sku", "variant", "destination", "platform"}.issubset(entity_types)


def test_recommendation_scale_variant_for_high_engagement():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv(
                    [
                        {
                            "sku": product.sku,
                            "platform": "Instagram Reels",
                            "posted_url": task.final_url,
                            "creative_variant_id": 1,
                            "views": 2000,
                            "likes": 150,
                            "comments": 20,
                            "shares": 20,
                            "saves": 20,
                            "clicks": 80,
                            "orders": 8,
                        }
                    ]
                ),
            )
            recommendations = CampaignRecommendationEngine(db).generate(campaign_id)

        assert any(item.recommendation_type == "scale_variant" for item in recommendations)


def test_recommendation_regenerate_for_high_views_low_clicks():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv([{"sku": product.sku, "platform": "Instagram Reels", "posted_url": task.final_url, "views": 2000, "clicks": 2, "orders": 0}]),
            )
            recommendations = CampaignRecommendationEngine(db).generate(campaign_id)

        assert any(item.recommendation_type == "regenerate_variant" for item in recommendations)


def test_recommendation_pause_destination_for_low_views():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv([{"sku": product.sku, "platform": "Instagram Reels", "posted_url": task.final_url, "views": 40, "clicks": 1, "orders": 0}]),
            )
            recommendations = CampaignRecommendationEngine(db).generate(campaign_id)

        assert any(item.recommendation_type == "change_destination" for item in recommendations)


def test_recommendation_import_stats_when_published_without_metrics():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/no-stats")
            recommendations = CampaignRecommendationEngine(db).generate(campaign_id)

        assert any(item.recommendation_type == "import_performance_stats" for item in recommendations)


def test_performance_recommendations_create_action_queue_items():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv([{"sku": product.sku, "platform": "Instagram Reels", "posted_url": task.final_url, "views": 2000, "clicks": 2, "orders": 0}]),
            )
            CampaignRecommendationEngine(db).generate(campaign_id)
            actions = db.scalars(select(models.CampaignActionQueueItem).where(models.CampaignActionQueueItem.campaign_id == campaign_id)).all()

        assert any(action.action_type == "create_regeneration_request" for action in actions)
        assert all(action.action_type != "run_real_smoke" for action in actions)


def test_campaign_performance_ui_renders_summary_and_recommendations():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv([{"sku": product.sku, "platform": "Instagram Reels", "posted_url": task.final_url, "views": 2000, "clicks": 2, "orders": 0}]),
            )
            CampaignRecommendationEngine(db).generate(campaign_id)
        response = api.get(f"/campaign-performance?campaign_id={campaign_id}")

        assert response.status_code == 200, response.text
        assert "Performance Loop" in response.text
        assert "Campaign Summary" in response.text
        assert "Recommendations" in response.text


def test_campaign_performance_report_exports():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            CampaignMetricsImporter(db).import_csv_text(
                campaign_id,
                performance_csv([{"sku": product.sku, "platform": "Instagram Reels", "posted_url": task.final_url, "views": 40, "clicks": 1, "orders": 0}]),
            )
            report = CampaignPerformanceReportService(db).build_report(campaign_id)

        assert report.summary.metric_count == 1
        assert "metric_count" in report.summary_csv
        assert report.recommendations


def run_factory_launch(db, *, target_videos: int = 8, target_destinations: int = 2):
    return FactoryLaunchWorkflow(db).run_prompt_only_launch(
        Path("sample_data/product_matrix.csv"),
        "Factory OS Test Launch",
        target_videos,
        target_destinations,
        brand="Factory OS",
        performance_csv_path=Path("sample_data/campaign_performance.csv"),
    )


def test_factory_health_check_reports_modules():
    with client():
        with SessionLocal() as db:
            health = FactoryHealthCheck(db).run()

    names = {item["name"] for item in health.checks}
    assert health.overall_status == "ready"
    assert {"db", "media_dir", "campaign_autopilot", "batch_executor", "performance_loop"}.issubset(names)
    assert "runway_api_secret_configured" in health.provider_keys


def test_factory_prompt_only_launch_imports_matrix_and_creates_campaign():
    with client():
        with SessionLocal() as db:
            result = run_factory_launch(db)
            campaign = db.get(models.Campaign, result.campaign_id)

    assert result.import_id
    assert campaign is not None
    assert campaign.source_type == "factory_os_prompt_only"
    assert result.acceptance_report.total_sku == 4


def test_factory_prompt_only_launch_runs_safe_batch_only():
    with client():
        with SessionLocal() as db:
            result = run_factory_launch(db)
            batch_items = db.scalars(select(models.CampaignBatchItem)).all()

    assert any(step["step"] == "dry_run_safe_batch" for step in result.steps)
    assert all(item.action_type not in {"run_real_smoke", "publish", "schedule_live_publishing"} for item in batch_items)


def test_factory_prompt_only_launch_makes_no_paid_calls():
    with client():
        with SessionLocal() as db:
            result = run_factory_launch(db)

    assert result.acceptance_report.paid_calls_made == 0


def test_factory_acceptance_report_contains_campaign_metrics():
    with client():
        with SessionLocal() as db:
            result = run_factory_launch(db)
            report = FactoryAcceptanceReportService(db).build(result.campaign_id)

    assert report.content_runs_created >= 1
    assert report.prompt_packs_created >= 1
    assert report.performance_metrics_imported == 3
    assert report.recommendations_generated >= 1


def test_factory_acceptance_report_lists_blockers_and_next_actions():
    with client():
        with SessionLocal() as db:
            result = run_factory_launch(db, target_destinations=120)
            report = FactoryAcceptanceReportService(db).build(result.campaign_id)

    blocker_names = {item.get("blocker") for item in report.blockers}
    assert "destination_capacity_below_target" in blocker_names
    assert report.next_manual_actions


def test_factory_os_ui_renders_health_and_launch():
    with client() as api:
        response = api.get("/factory-os")

    assert response.status_code == 200, response.text
    assert "System Health" in response.text
    assert "Prompt-only Launch" in response.text


def test_factory_runbook_outputs_next_manual_steps():
    with client():
        with SessionLocal() as db:
            result = run_factory_launch(db)
            runbook = FactoryRunbookService(db).build(result.campaign_id)

    steps = {item["step"] for item in runbook.next_manual_steps}
    assert "keep_paid_and_publishing_gates_closed" in steps
    assert any("factory_acceptance_report.py" in command for command in runbook.commands)


def test_campaign_no_external_account_registration_logic_exists():
    root = Path(__file__).resolve().parents[1] / "app" / "campaign_autopilot"
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in root.glob("*.py"))
    banned_terms = [
        "mass registration",
        "register_account",
        "temp_email",
        "captcha",
        "bypass",
        "fake engagement",
    ]

    for term in banned_terms:
        assert term not in source


def test_bombar_import_maps_to_product_matrix_import():
    with client():
        with SessionLocal() as db:
            result = BombarMatrixImporter(db).import_csv_text(bombar_csv(2), source_file="bombar.csv")
            matrix_import = db.get(models.ProductMatrixImport, result.import_id)
            rows = db.scalars(select(models.ProductMatrixRow).order_by(models.ProductMatrixRow.id)).all()

        assert result.status == "imported"
        assert matrix_import is not None
        assert matrix_import.source_file == "bombar.csv"
        assert len(rows) == 2
        assert rows[0].sku == "BOMBAR-001"
        assert rows[0].raw_json["source_adapter"] == "bombar_launch"
        assert rows[0].raw_json["bombar"]["margin"] == 0.42


def test_bombar_matrix_import_xlsx_maps_to_product_matrix_import():
    with client():
        rows = [
            ["sku", "product_name", "category", "price", "margin", "stock_qty", "product_url", "photo_1"],
            ["BOMBAR-XLSX-1", "XLSX Product", "Skincare", "799", "0.4", "40", "https://example.com/p", "https://example.com/packshot.png"],
        ]
        with SessionLocal() as db:
            result = BombarMatrixImporter(db).import_xlsx_bytes(bombar_xlsx_bytes(rows), source_file="bombar.xlsx")
            row = db.scalar(select(models.ProductMatrixRow))

        assert result.status == "imported"
        assert result.imported_count == 1
        assert result.errors == []
        assert row.raw_json["source_adapter"] == "bombar_launch"


def test_bombar_import_missing_photos_creates_generic_warning():
    with client():
        with SessionLocal() as db:
            result = BombarMatrixImporter(db).import_csv_text(bombar_csv(1, with_photos=False))
            row = db.scalar(select(models.ProductMatrixRow))

        assert result.imported_count == 1
        assert any("missing_photo" in warning for warning in result.warnings)
        assert row.status == "imported_with_warnings"
        assert "missing_photo" in row.warnings_json


def test_bombar_campaign_uses_campaign_autopilot_core():
    with client():
        campaign_id = create_bombar_campaign_fixture(row_count=40, target_videos=350, target_destinations=120)
        with SessionLocal() as db:
            campaign = db.get(models.Campaign, campaign_id)
            campaign_products = db.scalars(
                select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign_id)
            ).all()

        assert campaign is not None
        assert campaign.source_type == "bombar_matrix"
        assert campaign.strategy_json["adapter"] == "bombar_launch"
        assert len(campaign.product_ids_json) == 40
        assert len(campaign_products) == 40
        assert campaign.target_video_count == 350
        assert campaign.target_destination_count == 120


def test_bombar_prepare_content_calls_campaign_runner(monkeypatch):
    called = {}
    original = CampaignRunner.prepare_campaign

    def spy(self, campaign_id):
        called["campaign_id"] = campaign_id
        return original(self, campaign_id)

    monkeypatch.setattr("app.bombar_launch.launch_planner.CampaignRunner.prepare_campaign", spy)
    with client():
        campaign_id = create_bombar_campaign_fixture(row_count=1, target_videos=8, target_destinations=3)
        with SessionLocal() as db:
            result = LaunchPlanner(db).prepare_content(campaign_id, variant_count=3)
            campaign_run = db.get(models.CampaignRun, result["campaign_run_id"])

        assert called["campaign_id"] == campaign_id
        assert result["delegated_to"] == "CampaignRunner"
        assert result["prepared_count"] >= 1
        assert campaign_run is not None


def test_destination_setup_pack_generates_generic_destinations():
    with client():
        campaign_id = create_bombar_campaign_fixture(row_count=2, target_videos=8, target_destinations=5)
        with SessionLocal() as db:
            packs = DestinationSetupPlanner(db).generate(campaign_id)
            pack = db.get(models.DestinationSetupPack, packs[0].pack_id)
            destinations = db.scalars(select(models.PublishingDestination).order_by(models.PublishingDestination.id)).all()
            accounts = db.scalars(select(models.PublishingAccount)).all()

        assert len(packs) == 5
        assert pack.campaign_id == campaign_id
        assert pack.suggested_name
        assert pack.setup_checklist_json
        assert len(destinations) == 5
        assert all(destination.status == "draft" for destination in destinations)
        assert accounts == []


def test_profile_pack_builder_creates_first_posts_plan():
    with client() as api:
        product_id = create_product(api, title="Bombar Profile Product")
        with SessionLocal() as db:
            product = db.get(models.Product, product_id)
            profile = ProfilePackBuilder().build(product, platform="Instagram Reels", index=1)

        assert profile["handle_options"]
        assert len(profile["first_posts"]) == 9
        assert profile["posting_rules"]
        assert profile["link_cta_strategy"]["primary_cta"]


def test_bombar_distribution_plan_uses_generic_campaign_distribution_plan():
    with client():
        campaign_id = create_bombar_campaign_fixture(row_count=3, target_videos=10, target_destinations=4)
        with SessionLocal() as db:
            plan = DistributionAllocator(db).generate_plan(campaign_id)
            generic_plan = db.get(models.CampaignDistributionPlan, plan.plan_id)
            legacy_model_exists = hasattr(models, "LaunchDistributionPlan")

        assert generic_plan is not None
        assert plan.plan["delegated_to"] == "CampaignDistributionPlanner"
        assert plan.total_video_targets == 10
        assert plan.total_destinations == 4
        assert "approved_packages_required" in plan.blockers
        assert legacy_model_exists is False


def test_bombar_launch_dashboard_links_campaign_state():
    with client() as api:
        campaign_id = create_bombar_campaign_fixture(row_count=2, target_videos=6, target_destinations=3)
        with SessionLocal() as db:
            LaunchPlanner(db).prepare_content(campaign_id)
            DestinationSetupPlanner(db).generate(campaign_id)
            dashboard = LaunchDashboardService(db).dashboard(campaign_id)
        response = api.get(f"/bombar-launch?campaign_id={campaign_id}")

        assert dashboard.linked_campaign_id == campaign_id
        assert dashboard.campaign_state["campaign_id"] == campaign_id
        assert dashboard.campaign_report["campaign_id"] == campaign_id
        assert response.status_code == 200, response.text
        assert "Linked Campaign ID" in response.text
        assert "Launch Dashboard" in response.text


def test_no_duplicate_campaign_core_models_created_by_bombar():
    assert not hasattr(models, "LaunchCampaign")
    assert not hasattr(models, "LaunchDistributionPlan")
    assert not hasattr(models, "LaunchTask")
    assert not hasattr(models, "BombarProductImport")
    assert not hasattr(models, "BombarProductRow")
    assert hasattr(models, "Campaign")
    assert hasattr(models, "ProductMatrixImport")
    assert hasattr(models, "CampaignDistributionPlan")


def test_bombar_adapter_does_not_create_external_accounts():
    root = Path(__file__).resolve().parents[1] / "app" / "bombar_launch"
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in root.glob("*.py"))
    banned_terms = [
        "proxy",
        "anti_detect",
        "anti-detect",
        "temp_email",
        "captcha",
        "register_account",
        "mass_registration",
        "fake engagement",
    ]

    for term in banned_terms:
        assert term not in source


def test_bombar_production_dry_run_validates_matrix(tmp_path):
    matrix = tmp_path / "bombar_matrix.csv"
    matrix.write_text(
        "\n".join(
            [
                "sku,product_name,category,price,margin,stock_qty,product_url,photo_1,photo_2,photo_3",
                "BOMBAR-OK,Ready Product,Skincare,790,0.42,50,https://example.com/p,https://example.com/p.png,,",
                "BOMBAR-GAPS,Gap Product,Skincare,,0.42,,https://example.com/g,,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    validation = BombarMatrixValidator().validate_path(matrix)

    assert validation.row_count == 2
    assert validation.valid_row_count == 2
    assert validation.missing_photo_count == 1
    assert validation.missing_price_count == 1
    assert validation.missing_stock_count == 1
    assert "row_3:missing_photo" in validation.warnings

    xlsx = tmp_path / "bombar_matrix.xlsx"
    xlsx.write_bytes(
        bombar_xlsx_bytes(
            [
                ["sku", "product_name", "category", "price", "margin", "stock_qty", "product_url", "photo_1"],
                ["BOMBAR-XLSX", "XLSX Product", "Skincare", "790", "0.42", "50", "https://example.com/x", "https://example.com/x.png"],
            ]
        )
    )
    xlsx_validation = BombarMatrixValidator().validate_path(xlsx)
    assert xlsx_validation.row_count == 1
    assert xlsx_validation.valid_row_count == 1


def test_bombar_production_dry_run_outputs_blockers(tmp_path):
    matrix = tmp_path / "bombar_missing_refs.csv"
    matrix.write_text(bombar_csv(2, with_photos=False), encoding="utf-8")

    with client():
        with SessionLocal() as db:
            result = BombarProductionDryRunService(db, reports_dir=tmp_path / "reports").run(
                matrix,
                target_videos=4,
                target_destinations=2,
            )

    assert result.imported_sku_count == 2
    assert result.blocked_sku_count == 2
    assert result.missing_references_count == 2
    assert "BOMBAR-001" in result.blockers_by_sku
    assert any(item["blocker"] == "missing_reference" for item in result.blockers_by_sku["BOMBAR-001"])


def test_bombar_production_dry_run_makes_no_paid_calls(tmp_path):
    matrix = tmp_path / "bombar_ready.csv"
    matrix.write_text(bombar_csv(1), encoding="utf-8")

    with client():
        with SessionLocal() as db:
            result = BombarProductionDryRunService(db, reports_dir=tmp_path / "reports").run(
                matrix,
                target_videos=2,
                target_destinations=1,
            )
            batch_items = db.scalars(select(models.CampaignBatchItem)).all()

    assert result.paid_calls_made == 0
    assert result.safe_mode["paid_provider_calls"] is False
    assert all(item.action_type != "run_real_smoke" or item.status != "done" for item in batch_items)


def test_bombar_production_report_exports_csv_json(tmp_path):
    matrix = tmp_path / "bombar_ready.csv"
    matrix.write_text(bombar_csv(1), encoding="utf-8")

    with client():
        with SessionLocal() as db:
            result = BombarProductionDryRunService(db, reports_dir=tmp_path / "reports").run(
                matrix,
                target_videos=2,
                target_destinations=1,
            )

    paths = {key: Path(value) for key, value in result.report_paths.items()}
    assert paths["json"].exists()
    assert paths["readiness_csv"].exists()
    assert paths["blockers_csv"].exists()
    assert paths["next_actions_csv"].exists()
    assert paths["xlsx"].exists()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["campaign_id"] == result.campaign_id
    assert payload["paid_calls_made"] == 0
    assert "sku,status,product_name" in paths["readiness_csv"].read_text(encoding="utf-8")


def test_bombar_dry_run_ui_renders():
    with client() as api:
        response = api.get("/bombar-production-dry-run")

    assert response.status_code == 200, response.text
    assert "Production Dry Run" in response.text
    assert "Run Dry Run" in response.text


def add_launch_video_fixture(
    db,
    campaign_id: int,
    *,
    review_status: str = "approved",
    review_json: dict | None = None,
    create_package: bool = False,
    package_approved: bool = True,
) -> tuple[models.Product, models.ContentRun, models.VideoJob, models.VideoQualityReview]:
    campaign_product = db.scalar(select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign_id))
    product = db.get(models.Product, campaign_product.product_id)
    template = db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
    guide = db.scalar(select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id))
    script_job = models.ScriptJob(
        product_id=product.id,
        template_id=template.id,
        brand_guide_id=guide.id,
        status="script_approved",
        input_payload_json={},
        output_script_json={},
        validation_report_json={},
    )
    db.add(script_job)
    db.flush()
    script_variant = models.ScriptVariant(
        script_job_id=script_job.id,
        variant_number=1,
        creative_angle="launch_ops",
        hook="Launch ops hook",
        key_message="Launch ops message",
        final_cta="Open product card",
        full_script_json={},
        status="script_approved",
    )
    db.add(script_variant)
    db.flush()
    pack = models.CreativeIntelligencePackRecord(
        product_id=product.id,
        sku=product.sku,
        status="ready",
        pack_json={},
        source_summary_json={},
        warnings_json=[],
    )
    db.add(pack)
    db.flush()
    brief = models.ScriptBrief(
        product_id=product.id,
        intelligence_pack_id=pack.id,
        status="ready",
        objective="launch_ops",
        creative_angle="campaign",
        target_audience="operator",
        brief_json={},
        allowed_claims_json=[],
        missing_data_json=[],
        safety_warnings_json=[],
    )
    db.add(brief)
    db.flush()
    spec = models.VideoCreativeSpecRecord(
        product_id=product.id,
        intelligence_pack_id=pack.id,
        script_brief_id=brief.id,
        platform="Instagram Reels",
        status="ready",
        spec_json={"geometry_lock": "ready"},
        hook_candidates_json=[],
        validation_report_json={},
        warnings_json=[],
    )
    db.add(spec)
    db.flush()
    video_job = models.VideoJob(
        script_variant_id=script_variant.id,
        provider="mock",
        status="approved" if review_status == "approved" else "needs_human_review",
        output_video_path=f"media/mock/{product.sku}-launch.mp4",
    )
    db.add(video_job)
    db.flush()
    generation_variant = models.VideoGenerationVariant(
        creative_spec_id=spec.id,
        script_variant_id=script_variant.id,
        video_job_id=video_job.id,
        provider="mock",
        status="generated",
        prompt_pack_json={},
        provider_payload_json={},
    )
    db.add(generation_variant)
    db.flush()
    content_run = models.ContentRun(
        product_id=product.id,
        platform="Instagram Reels",
        duration_seconds=15,
        variant_count=1,
        status="real_smoke_created",
        creative_spec_id=spec.id,
        generation_variant_id=generation_variant.id,
        video_job_id=video_job.id,
        run_json={"geometry_scale_blockers": []},
        blockers_json=[],
        next_actions_json=[],
        warnings_json=[],
    )
    db.add(content_run)
    db.flush()
    campaign_product.content_run_ids_json = list(dict.fromkeys([*(campaign_product.content_run_ids_json or []), content_run.id]))
    review_payload = {
        "human_visual_status": "approved" if review_status == "approved" else "needs_review",
        "product_identity_status": "ready",
        "geometry_status": "ready",
        **(review_json or {}),
    }
    review = models.VideoQualityReview(
        creative_spec_id=spec.id,
        video_generation_variant_id=generation_variant.id,
        video_job_id=video_job.id,
        status=review_status,
        score=0.9 if review_status == "approved" else 0.4,
        review_json=review_payload,
        warnings_json=[],
    )
    db.add(review)
    if create_package:
        package = models.PublishingPackage(
            video_job_id=video_job.id,
            creative_variant_id=None,
            product_id=product.id,
            brand=product.brand,
            target_platform="Instagram Reels",
            title=f"{product.title} package",
            description="Launch ops package.",
            hashtags_json=["#launch"],
            cta="Open product card",
            product_url=product.product_url,
            video_file_path=video_job.output_video_path,
            review_status="approved" if package_approved else "needs_review",
            status="approved" if package_approved else "draft",
            metadata_json={},
        )
        db.add(package)
    db.commit()
    return product, content_run, video_job, review


def add_launch_destination(db, *, brand: str = "Bombar", status: str = "active", posting_mode: str = "manual", auth_status: str = "manual_only", daily_limit: int = 1, weekly_limit: int = 3):
    destination = models.PublishingDestination(
        brand=brand,
        platform="Instagram Reels",
        name=f"{brand} {posting_mode} destination",
        handle=f"@{brand.lower()}_{posting_mode}",
        status=status,
        posting_mode=posting_mode,
        auth_status=auth_status,
        daily_limit=daily_limit,
        weekly_limit=weekly_limit,
        allowed_formats_json=["vertical_video"],
    )
    db.add(destination)
    db.commit()
    return destination


def test_launch_readiness_aggregates_campaign_quality_and_destinations():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=3, target_destinations=1)
        with SessionLocal() as db:
            add_launch_video_fixture(db, campaign_id, create_package=True)
            add_launch_destination(db, weekly_limit=5)
            result = LaunchReadinessService(db).refresh(campaign_id)

    assert result.total_sku == 1
    assert result.target_videos == 3
    assert result.real_video_count == 1
    assert result.approved_video_count == 1
    assert result.destination_active_count == 1
    assert result.destination_capacity_total == 5


def test_quality_gate_blocks_needs_human_review_video():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            add_launch_video_fixture(db, campaign_id, review_status="needs_human_review")
            gates = QualityGateService(db).refresh(campaign_id)

    assert gates[0].publishing_allowed is False
    assert any(blocker["blocker"] == "needs_human_review" for blocker in gates[0].blockers)


def test_quality_gate_blocks_geometry_mismatch():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            add_launch_video_fixture(db, campaign_id, review_json={"geometry_status": "mismatch"})
            gates = QualityGateService(db).refresh(campaign_id)

    assert gates[0].publishing_allowed is False
    assert any(blocker["blocker"] == "product_geometry_mismatch" for blocker in gates[0].blockers)


def test_quality_gate_allows_approved_video_for_package():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            add_launch_video_fixture(db, campaign_id)
            gates = QualityGateService(db).refresh(campaign_id)

    assert gates[0].publishing_allowed is True
    assert gates[0].status == "allowed"


def test_destination_capacity_counts_active_destinations():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=2)
        with SessionLocal() as db:
            add_launch_destination(db, status="active", posting_mode="manual", auth_status="manual_only", weekly_limit=3)
            add_launch_destination(db, status="active", posting_mode="api", auth_status="token_valid", weekly_limit=4)
            add_launch_destination(db, status="paused", posting_mode="manual", auth_status="manual_only", weekly_limit=10)
            capacity = DestinationCapacityService(db).refresh(campaign_id)

    assert capacity.total_destinations == 3
    assert capacity.active_destinations == 2
    assert capacity.manual_destinations == 1
    assert capacity.api_ready_destinations == 1
    assert capacity.weekly_capacity == 7


def test_destination_capacity_flags_capacity_gap():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=10, target_destinations=3)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=2)
            capacity = DestinationCapacityService(db).refresh(campaign_id)

    assert capacity.capacity_gap == 8
    assert {blocker["blocker"] for blocker in capacity.blockers} >= {"destination_gap", "capacity_gap"}


def test_action_plan_groups_safe_human_paid_publishing_actions():
    with client():
        campaign_id = campaign_fixture(row_count=2, target_videos=3, target_destinations=1)
        with SessionLocal() as db:
            add_launch_video_fixture(db, campaign_id, review_status="needs_human_review", create_package=True)
            add_launch_destination(db, weekly_limit=5)
            gates = QualityGateService(db).refresh(campaign_id)
            capacity = DestinationCapacityService(db).refresh(campaign_id)
            plan = LaunchActionPlanner(db).refresh(campaign_id, quality_gates=gates, capacity=capacity)

    action_types = {action["action_type"] for action in plan.actions}
    assert {"safe", "human", "paid", "publishing"}.issubset(action_types)
    assert plan.human_action_count >= 1
    assert plan.publishing_action_count >= 1


def test_action_plan_recommends_add_destinations_when_capacity_gap():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=10, target_destinations=5)
        with SessionLocal() as db:
            gates = QualityGateService(db).refresh(campaign_id)
            capacity = DestinationCapacityService(db).refresh(campaign_id)
            plan = LaunchActionPlanner(db).refresh(campaign_id, quality_gates=gates, capacity=capacity)

    assert any(action["action"] == "add_destinations" for action in plan.actions)


def test_action_plan_recommends_regeneration_when_quality_failed():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            product, content_run, video_job, review = add_launch_video_fixture(db, campaign_id, review_status="needs_regeneration")
            generation_variant = db.get(models.VideoGenerationVariant, content_run.generation_variant_id)
            db.add(
                models.SceneRegenerationRequest(
                    video_job_id=video_job.id,
                    video_generation_variant_id=generation_variant.id,
                    creative_spec_id=generation_variant.creative_spec_id,
                    scene_number=1,
                    reason="product_geometry_mismatch",
                    feedback="Regenerate scene.",
                    status="requested",
                    request_json={},
                    prompt_only_output_json={},
                )
            )
            db.commit()
            gates = QualityGateService(db).refresh(campaign_id)
            capacity = DestinationCapacityService(db).refresh(campaign_id)
            plan = LaunchActionPlanner(db).refresh(campaign_id, quality_gates=gates, capacity=capacity)

    assert any(action["action"] == "create_regeneration_requests" for action in plan.actions)


def test_launch_runbook_exports_actions(tmp_path):
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            export = LaunchReportService(db, reports_dir=tmp_path).export_runbook(campaign_id)

    assert Path(export.report_paths["json"]).exists()
    assert Path(export.report_paths["csv"]).exists()
    assert export.action_count >= 1


def test_launch_operations_ui_renders():
    with client() as api:
        response = api.get("/launch-operations")

    assert response.status_code == 200, response.text
    assert "Launch Operations" in response.text
    assert "Quality x Scale x Accounts" in response.text


def test_launch_operations_does_not_auto_publish():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            add_launch_video_fixture(db, campaign_id, create_package=True)
            add_launch_destination(db)
            before = db.query(models.PublishingTask).count()
            LaunchReadinessService(db).refresh(campaign_id)
            after = db.query(models.PublishingTask).count()
            jobs = db.scalars(select(models.PublishingJob)).all()

    assert before == after == 0
    assert jobs == []


def test_destination_setup_requirement_from_capacity_gap():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=10, target_destinations=3)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=2)
            requirement = SetupRequirementService(db).refresh(campaign_id)

    assert requirement.platform == "Instagram Reels"
    assert requirement.existing_ready_count == 1
    assert requirement.capacity_gap == 8
    assert requirement.required_count == 3
    assert requirement.status == "open"


def test_profile_pack_builder_creates_name_bio_first_posts():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            requirement = SetupRequirementService(db).refresh(campaign_id)
            packs = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)

    assert len(packs) == 1
    assert packs[0].suggested_name
    assert packs[0].suggested_handle.startswith("@")
    assert "human review" in (packs[0].bio_text or "")
    assert len(packs[0].first_posts) == 9
    assert packs[0].content_pillars


def test_setup_task_created_from_profile_pack():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            requirement = SetupRequirementService(db).refresh(campaign_id)
            pack = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)[0]
            task = DestinationSetupTaskService(db).create_task(pack.id, owner_name="Ops")

    assert task.status == "needs_manual_setup"
    assert task.owner_name == "Ops"
    assert any(item["key"] == "no_external_registration" for item in task.checklist)


def test_setup_task_mark_complete_requires_url_or_handle():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            requirement = SetupRequirementService(db).refresh(campaign_id)
            pack = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)[0]
            task = DestinationSetupTaskService(db).create_task(pack.id)
            with pytest.raises(DestinationSetupDataError):
                DestinationSetupTaskService(db).mark_complete(task.id)


def test_create_internal_destination_from_completed_task():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            requirement = SetupRequirementService(db).refresh(campaign_id)
            pack = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)[0]
            task = DestinationSetupTaskService(db).create_task(pack.id)
            completed = DestinationSetupTaskService(db).mark_complete(
                task.id,
                url="https://example.com/account",
                handle="@example",
            )
            destination = DestinationSetupTaskService(db).create_destination(completed.id)

    assert destination.status == "active"
    assert destination.posting_mode == "manual"
    assert destination.auth_status == "manual_only"
    assert destination.handle == "@example"


def test_instagram_destination_requires_manual_setup():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            requirement = SetupRequirementService(db).refresh(campaign_id, platform="Instagram Reels")
            pack = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)[0]
            task = DestinationSetupTaskService(db).create_task(pack.id)

    assert task.platform == "Instagram Reels"
    assert task.status == "needs_manual_setup"
    assert any(item["key"] == "official_api" for item in task.checklist)


def test_destination_setup_does_not_auto_register_external_account():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            before_destinations = db.query(models.PublishingDestination).count()
            requirement = SetupRequirementService(db).refresh(campaign_id)
            packs = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)
            DestinationSetupTaskService(db).create_task(packs[0].id)
            after_destinations = db.query(models.PublishingDestination).count()
            publishing_tasks = db.scalars(select(models.PublishingTask)).all()
            publishing_jobs = db.scalars(select(models.PublishingJob)).all()

    assert before_destinations == after_destinations == 0
    assert publishing_tasks == []
    assert publishing_jobs == []


def test_destination_setup_ui_renders():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        with SessionLocal() as db:
            requirement = SetupRequirementService(db).refresh(campaign_id)
            pack = DestinationProfilePackBuilder(db).generate_for_requirement(requirement.id)[0]
            DestinationSetupTaskService(db).create_task(pack.id)
        response = api.get(f"/destination-setup?campaign_id={campaign_id}")

    assert response.status_code == 200, response.text
    assert "Destination Setup Factory" in response.text
    assert "Capacity Gap to Owned Destinations" in response.text
    assert "Create Internal Destination" in response.text


def test_destination_setup_api_flow_creates_destination():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=1, target_destinations=1)
        requirement_response = api.post(f"/api/destination-setup/campaigns/{campaign_id}/requirements", json={})
        assert requirement_response.status_code == 200, requirement_response.text
        pack_response = api.post(f"/api/destination-setup/campaigns/{campaign_id}/profile-packs", json={})
        assert pack_response.status_code == 200, pack_response.text
        pack_id = pack_response.json()[0]["id"]
        task_response = api.post(f"/api/destination-setup/profile-packs/{pack_id}/create-task", json={"owner_name": "Ops"})
        assert task_response.status_code == 200, task_response.text
        task_id = task_response.json()["id"]
        complete_response = api.post(
            f"/api/destination-setup/tasks/{task_id}/mark-complete",
            json={"url": "https://example.com/account", "handle": "@example", "owner_name": "Ops"},
        )
        assert complete_response.status_code == 200, complete_response.text
        destination_response = api.post(f"/api/destination-setup/tasks/{task_id}/create-destination")

    assert destination_response.status_code == 200, destination_response.text
    assert destination_response.json()["status"] == "active"
    assert destination_response.json()["posting_mode"] == "manual"


def test_destination_readiness_active_manual_ready():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            destination = add_launch_destination(db, weekly_limit=3)
            result = DestinationReadinessService(db).refresh(destination.id, campaign_id=campaign_id)

    assert result.status == "ready"
    assert result.manual_ready is True
    assert result.remaining_weekly_capacity == 3


def test_destination_readiness_api_requires_token_valid():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            destination = add_launch_destination(db, posting_mode="api", auth_status="token_expired", weekly_limit=3)
            blocked = DestinationReadinessService(db).refresh(destination.id, campaign_id=campaign_id)
            destination.auth_status = "token_valid"
            db.commit()
            ready = DestinationReadinessService(db).refresh(destination.id, campaign_id=campaign_id)

    assert blocked.status == "blocked"
    assert any(blocker["blocker"] == "api_destination_requires_token_valid" for blocker in blocked.blockers)
    assert ready.status == "ready"
    assert ready.api_ready is True


def test_destination_readiness_paused_not_ready():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            destination = add_launch_destination(db, status="paused", weekly_limit=3)
            result = DestinationReadinessService(db).refresh(destination.id, campaign_id=campaign_id)

    assert result.status == "blocked"
    assert any(blocker["blocker"] == "destination_not_active" for blocker in result.blockers)


def test_warmup_phase_reduces_capacity():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=6, target_destinations=1)
        with SessionLocal() as db:
            destination = add_launch_destination(db, daily_limit=3, weekly_limit=10)
            DestinationWarmupService(db).create_or_update(destination.id, current_phase="phase_1_soft_start")
            result = DestinationReadinessService(db).refresh(destination.id, campaign_id=campaign_id)

    assert result.warmup_phase == "phase_1_soft_start"
    assert result.daily_limit == 1
    assert result.weekly_limit == 7


def test_campaign_capacity_counts_ready_destinations():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=5, target_destinations=2)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=3)
            add_launch_destination(db, weekly_limit=2)
            capacity = DestinationCRMCampaignCapacityService(db).calculate(campaign_id)

    assert capacity.ready_destinations == 2
    assert capacity.manual_ready_destinations == 2
    assert capacity.available_weekly_capacity == 5
    assert capacity.capacity_gap == 0


def test_campaign_capacity_flags_gap():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=10, target_destinations=2)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=2)
            capacity = DestinationCRMCampaignCapacityService(db).calculate(campaign_id)

    assert capacity.capacity_gap == 8
    assert any(blocker["blocker"] == "capacity_gap" for blocker in capacity.blockers)


def test_destination_health_uses_recent_tasks():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=4, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id)
            db.add(
                models.CampaignPerformanceMetric(
                    campaign_id=campaign_id,
                    product_id=product.id,
                    sku=product.sku,
                    publishing_task_id=task.id,
                    destination_id=task.destination_id,
                    platform=task.platform,
                    posted_url=task.final_url,
                    views=1000,
                    engagement_rate=0.12,
                    raw_json={},
                )
            )
            db.add(
                models.PublishingTask(
                    publishing_package_id=task.publishing_package_id,
                    destination_id=task.destination_id,
                    platform=task.platform,
                    status="failed",
                    scheduled_at=datetime.now(UTC).replace(tzinfo=None),
                    error_message="manual upload failed",
                    raw_response_json={},
                )
            )
            db.commit()
            health = DestinationHealthService(db).refresh(task.destination_id)

    assert health.recent_task_count == 2
    assert health.failed_task_count == 1
    assert health.avg_views == 1000
    assert health.avg_engagement_rate == 0.12
    assert any(blocker["blocker"] == "failed_publishing_tasks" for blocker in health.blockers)


def test_destination_crm_ui_renders_readiness_and_capacity():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=3)
        response = api.get(f"/destination-crm?campaign_id={campaign_id}")

    assert response.status_code == 200, response.text
    assert "Destination Readiness CRM" in response.text
    assert "Capacity by Campaign" in response.text


def test_create_manual_destination_connection():
    with client():
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            connection = ConnectionRegistry(db).create(destination_id, "manual")
            audit = db.scalar(select(models.DestinationConnectionAudit))

    assert connection.destination_id == destination_id
    assert connection.connection_type == "manual"
    assert connection.status == "connected"
    assert connection.auth_status == "manual_only"
    assert audit.event_type == "connection_created"


def test_connection_stores_credential_ref_not_secret(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN_REF", "super-secret-value")
    with client():
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            connection = ConnectionRegistry(db).create(destination_id, "telegram_bot", credential_ref="SECRET_TOKEN_REF")
            audit = db.scalar(select(models.DestinationConnectionAudit))

    assert connection.credential_ref == "SECRET_TOKEN_REF"
    assert "super-secret-value" not in json.dumps(audit.sanitized_payload_json)


def test_connection_check_reports_missing_credential(monkeypatch):
    monkeypatch.delenv("MISSING_TELEGRAM_TOKEN_REF", raising=False)
    with client():
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            connection = ConnectionRegistry(db).create(destination_id, "telegram_bot", credential_ref="MISSING_TELEGRAM_TOKEN_REF")
            result = ConnectionRegistry(db).check(connection.id)

    assert result.status == "needs_auth"
    assert result.credential_configured is False
    assert any(blocker["blocker"] == "destination_connection_needs_auth" for blocker in result.blockers)


def test_connection_ui_never_renders_secret(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN_REF", "super-secret-value")
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            ConnectionRegistry(db).create(destination_id, "telegram_bot", credential_ref="SECRET_TOKEN_REF")
        response = api.get(f"/destination-connectors?campaign_id={campaign_id}")

    assert response.status_code == 200, response.text
    assert "Destination Connectors" in response.text
    assert "configured" in response.text
    assert "super-secret-value" not in response.text
    assert "SECRET_TOKEN_REF" not in response.text


def test_csv_metrics_import_maps_posted_url_to_task():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/destination-map")
            result = CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 1200,
                            "likes": 80,
                            "comments": 12,
                            "shares": 4,
                            "saves": 8,
                            "clicks": 30,
                            "orders": 3,
                            "revenue": 4500,
                            "spend": 700,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            metric = db.scalar(select(models.DestinationPostMetric))
            performance_metric = db.scalar(select(models.CampaignPerformanceMetric))

    assert result.imported_count == 1
    assert metric.publishing_task_id == task.id
    assert metric.destination_id == task.destination_id
    assert performance_metric.publishing_task_id == task.id
    assert performance_metric.views == 1200


def test_csv_metrics_import_unmatched_url_warns_not_fails():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product = db.get(models.Product, db.get(models.Campaign, campaign_id).product_ids_json[0])
            result = CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": "Unknown",
                            "platform": "Instagram Reels",
                            "posted_url": "https://example.com/post/unmatched",
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 100,
                            "clicks": 2,
                            "orders": 0,
                        }
                    ]
                )
            )
            metric = db.scalar(select(models.DestinationPostMetric))

    assert result.status == "partial"
    assert result.imported_count == 1
    assert metric.publishing_task_id is None
    assert any("posted_url_not_matched_to_task" in warning for warning in result.warnings)


def test_metrics_import_idempotent_by_url_period():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/idempotent")
            csv_text = destination_metrics_csv(
                [
                    {
                        "campaign_id": campaign_id,
                        "destination_name": task.destination.name,
                        "platform": task.platform,
                        "posted_url": task.final_url,
                        "sku": product.sku,
                        "period_start": "2026-07-01",
                        "period_end": "2026-07-07",
                        "views": 200,
                        "clicks": 4,
                        "orders": 1,
                    }
                ]
            )
            first = CSVMetricsImporter(db).import_csv_text(csv_text, campaign_id=campaign_id)
            second = CSVMetricsImporter(db).import_csv_text(csv_text, campaign_id=campaign_id)
            metric_count = db.query(models.DestinationPostMetric).count()
            performance_count = db.query(models.CampaignPerformanceMetric).count()

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_count == 1
    assert metric_count == 1
    assert performance_count == 1


def test_telegram_connector_uses_mock_client_in_tests(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    with client():
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            connection = ConnectionRegistry(db).create(destination_id, "telegram_bot", credential_ref="TELEGRAM_BOT_TOKEN")
            result = TelegramConnector().check(connection)

    assert result.status == "connected"
    assert result.auth_status == "bot_ready"
    assert result.credential_configured is True


def test_youtube_connector_requires_oauth_ref():
    with client():
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            connection = ConnectionRegistry(db).create(destination_id, "youtube_oauth")
            result = YouTubeAnalyticsConnector().check(connection)

    assert result.status == "needs_auth"
    assert result.credential_configured is False


def test_sync_destination_metrics_creates_destination_post_metrics():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/sync")
            connection = ConnectionRegistry(db).create(
                task.destination_id,
                "manual",
                settings_json={
                    "mock_metrics": [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "views": 500,
                            "clicks": 10,
                            "orders": 2,
                        }
                    ]
                },
            )
            result = DestinationConnectorSyncService(db).sync(connection.id, period_start=date(2026, 7, 1), period_end=date(2026, 7, 7))
            metric = db.scalar(select(models.DestinationPostMetric))

    assert result.imported_count == 1
    assert metric.connection_id == connection.id
    assert metric.publishing_task_id == task.id
    assert metric.views == 500


def test_metrics_flow_updates_campaign_performance():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/performance-flow")
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 900,
                            "clicks": 45,
                            "orders": 5,
                            "revenue": 7500,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            summary = DestinationMetricsCollector(db).campaign_summary(campaign_id)
            performance = CampaignPerformanceAggregator(db).summarize(campaign_id)

    assert summary.total_views == 900
    assert performance.total_views == 900
    assert performance.total_orders == 5


def test_destination_connectors_ui_renders_connections_and_metrics():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/ui")
            ConnectionRegistry(db).create(task.destination_id, "manual")
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 321,
                            "clicks": 8,
                            "orders": 1,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
        response = api.get(f"/destination-connectors?campaign_id={campaign_id}")

    assert response.status_code == 200, response.text
    assert "Destination Connectors" in response.text
    assert "Campaign Metrics Summary" in response.text
    assert "https://example.com/post/ui" in response.text


def test_no_scraping_or_unofficial_login_paths_exist():
    package_dir = Path("app/destination_connectors")
    banned = ["selenium", "playwright", "anti_detect", "temp_mail", "register_account"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in package_dir.glob("*.py"))

    for marker in banned:
        assert marker not in text


def test_destination_control_tower_aggregates_setup_readiness_connections_metrics():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/tower-ok")
            task.destination.status = "active"
            db.commit()
            ConnectionRegistry(db).create(task.destination_id, "manual")
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 1200,
                            "clicks": 30,
                            "orders": 3,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            snapshot = TowerService(db).refresh(campaign_id)
            rows = TowerService(db).rows(campaign_id)

    assert snapshot.total_destinations == 1
    assert snapshot.ready_count == 1
    assert snapshot.connected_count == 1
    assert snapshot.metrics_synced_count == 1
    assert rows[0].connection_status == "connected"
    assert rows[0].metrics_status == "synced"


def test_destination_control_row_marks_no_metrics_when_published_without_stats():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/tower-no-metrics")
            task.destination.status = "active"
            db.commit()
            ConnectionRegistry(db).create(task.destination_id, "manual")
            TowerService(db).refresh(campaign_id)
            row = TowerService(db).rows(campaign_id)[0]

    assert row.publishing_status == "published"
    assert row.metrics_status == "no_metrics"
    assert row.next_action == "import_metrics"


def test_destination_control_row_marks_low_performance():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/tower-weak")
            task.destination.status = "active"
            db.commit()
            ConnectionRegistry(db).create(task.destination_id, "manual")
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 2500,
                            "clicks": 1,
                            "orders": 0,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            CampaignPerformanceScorer(db).compute_scores(campaign_id)
            snapshot = TowerService(db).refresh(campaign_id)
            row = TowerService(db).rows(campaign_id)[0]

    assert snapshot.low_performance_count == 1
    assert row.performance_status == "weak"
    assert row.next_action == "investigate_low_performance"


def test_destination_control_next_action_import_metrics():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/tower-import")
            task.destination.status = "active"
            db.commit()
            ConnectionRegistry(db).create(task.destination_id, "manual")
            TowerService(db).refresh(campaign_id)
            row = TowerService(db).rows(campaign_id)[0]

    assert row.metrics_status == "no_metrics"
    assert row.next_action == "import_metrics"


def test_destination_control_next_action_refresh_readiness():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            destination = add_launch_destination(db, weekly_limit=3)
            destination.handle = None
            db.commit()
            TowerService(db).refresh(campaign_id)
            row = TowerService(db).rows(campaign_id)[0]

    assert row.readiness_status == "blocked"
    assert row.next_action == "refresh_readiness"


def test_destination_control_snapshot_counts_capacity_gap():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=10, target_destinations=1)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=2)
            snapshot = TowerService(db).refresh(campaign_id)

    assert snapshot.capacity_gap == 8
    assert any(blocker["blocker"] == "capacity_gap" for blocker in snapshot.blockers)


def test_destination_control_ui_renders_overview_and_rows():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            destination = add_launch_destination(db, weekly_limit=3)
            ConnectionRegistry(db).create(destination.id, "manual")
            TowerService(db).refresh(campaign_id)
        response = api.get(f"/destination-control-tower?campaign_id={campaign_id}")

    assert response.status_code == 200, response.text
    assert "Destination Control Tower" in response.text
    assert "Destination Table" in response.text
    assert "Action Queue" in response.text


def test_destination_control_report_exports():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            add_launch_destination(db, weekly_limit=3)
            TowerService(db).refresh(campaign_id)
            report = DestinationControlReportService(db).build(campaign_id)

    assert report.snapshot.campaign_id == campaign_id
    assert "Destination Control Tower Campaign" in report.markdown
    assert "| Platform | Destination | Readiness |" in report.markdown


def test_create_participant_profile():
    with client():
        with SessionLocal() as db:
            participant = ParticipantService(db).create(
                display_name="Creator One",
                role="creator",
                platforms=["reels", "shorts"],
            )

    assert participant.id
    assert participant.role == "creator"
    assert participant.platforms_json == ["reels", "shorts"]


def test_link_participant_to_destination():
    with client():
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Partner One", role="partner")
            destination_id = add_campaign_destination(db)
            link = OnboardingService(db).link_destination(participant.id, destination_id, relationship_type="owner")

    assert link.participant_id == participant.id
    assert link.destination_id == destination_id
    assert link.relationship_type == "owner"


def test_assignment_brief_contains_video_tz():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Creator Brief", role="creator")
            product, content_run, _, _ = add_launch_video_fixture(db, campaign_id, create_package=True)
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                content_run_id=content_run.id,
                assignment_type="create_video",
            )

    assert assignment.brief_json["sku"] == product.sku
    assert "buyer_need" in assignment.brief_json
    assert "safe_promise" in assignment.brief_json
    assert "first_frame_logic" in assignment.brief_json
    assert "must_avoid" in assignment.brief_json
    assert "review_checklist" in assignment.brief_json


def test_participant_submission_from_external_url():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Submitter", role="creator")
            _, content_run, _, _ = add_launch_video_fixture(db, campaign_id, create_package=True)
            assignment = AssignmentPortalService(db).create_assignment(participant_id=participant.id, campaign_id=campaign_id, content_run_id=content_run.id)
            submission = SubmissionService(db).submit(assignment_id=assignment.id, external_url="https://example.com/video.mp4")
            assignment_status = db.get(models.ParticipantAssignment, assignment.id).status

    assert submission.external_url == "https://example.com/video.mp4"
    assert submission.review_status == "needs_review"
    assert assignment_status == "submitted"


def test_participant_metrics_aggregate_from_destination_post_metrics():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Metrics Owner", role="partner")
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/participant-metrics")
            OnboardingService(db).link_destination(participant.id, task.destination_id, relationship_type="owner")
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 1500,
                            "clicks": 45,
                            "orders": 4,
                            "revenue": 6000,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            stats = ParticipantMetricsService(db).refresh(participant.id, campaign_id=campaign_id)

    assert stats.views_total == 1500
    assert stats.clicks_total == 45
    assert stats.orders_total == 4
    assert stats.revenue_total == 6000


def test_participant_dashboard_shows_channels_stats_and_recommendations():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Dashboard User", role="creator")
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/dashboard")
            OnboardingService(db).link_destination(participant.id, task.destination_id, relationship_type="creator")
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                assignment_type="publish_video",
            )
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "views": 900,
                            "clicks": 20,
                            "orders": 1,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            stats = ParticipantMetricsService(db).dashboard_stats(participant.id, campaign_id=campaign_id)
            recommendations = RecommendationService(db).recommendations(participant.id)

    assert stats["views_total"] == 900
    assert stats["assignments_total"] == 1
    assert any(item["action"] in {"submit_video", "scale_channel", "monitor"} for item in recommendations)


def test_payout_rule_per_published_post_creates_ledger_entry():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Paid Creator", role="creator")
            rule = PayoutService(db).create_rule(name="Post fixed", payout_type="per_published_post", amount_fixed=1200)
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/payout-fixed")
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                payout_rule_id=rule.id,
                assignment_type="publish_video",
            )
            entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 1200
    assert entry.status == "pending"
    assert entry.reason == "per_published_post"


def test_payout_rule_cpa_uses_orders_metric():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="CPA Creator", role="partner")
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/payout-cpa")
            OnboardingService(db).link_destination(participant.id, task.destination_id, relationship_type="partner")
            rule = PayoutService(db).create_rule(name="CPA", payout_type="cpa", amount_fixed=300)
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                payout_rule_id=rule.id,
                assignment_type="publish_video",
            )
            CSVMetricsImporter(db).import_csv_text(
                destination_metrics_csv(
                    [
                        {
                            "campaign_id": campaign_id,
                            "destination_name": task.destination.name,
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "views": 800,
                            "clicks": 50,
                            "orders": 3,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 900
    assert entry.reason == "orders_metric_cpa"


def test_payout_mark_paid_is_manual_only():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Manual Pay", role="creator")
            rule = PayoutService(db).create_rule(name="Fixed", payout_type="per_video", amount_fixed=500)
            assignment = AssignmentPortalService(db).create_assignment(participant_id=participant.id, campaign_id=campaign_id, payout_rule_id=rule.id)
            entry = PayoutService(db).calculate_for_assignment(assignment.id)
            paid = PayoutService(db).mark_paid(entry.id)

    assert paid.status == "paid"
    assert paid.amount == 500


def test_participant_portal_ui_renders_briefs_channels_stats_payouts():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="UI Participant", role="creator", platforms=["reels"])
            destination_id = add_campaign_destination(db)
            OnboardingService(db).link_destination(participant.id, destination_id)
            _, content_run, _, _ = add_launch_video_fixture(db, campaign_id, create_package=True)
            AssignmentPortalService(db).create_assignment(participant_id=participant.id, campaign_id=campaign_id, content_run_id=content_run.id)
        response = api.get(f"/participant-portal?participant_id={participant.id}")

    assert response.status_code == 200, response.text
    assert "Participant Portal" in response.text
    assert "My Briefs / Assignments" in response.text
    assert "My Channels" in response.text
    assert "My Payouts" in response.text


def test_no_raw_payment_or_secret_values_rendered():
    with client() as api:
        with SessionLocal() as db:
            participant = ParticipantService(db).create(
                display_name="Secret Check",
                role="creator",
                notes="bank_secret_token_should_not_render",
            )
        response = api.get(f"/participant-portal?participant_id={participant.id}")

    assert response.status_code == 200
    assert "bank_secret_token_should_not_render" not in response.text
    assert "card_number" not in response.text


def test_create_tracking_link_for_publishing_task():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://market.example/p/track")
            link = TrackingLinkService(db).create_for_task(task.id, campaign_id=campaign_id)

    assert link.publishing_task_id == task.id
    assert link.campaign_id == campaign_id
    assert link.sku == product.sku
    assert link.slug.startswith(f"pt{task.id}-")


def test_tracking_redirect_records_click():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://market.example/p/click")
            link = TrackingLinkService(db).create_for_task(task.id, campaign_id=campaign_id)
            slug = link.slug
        response = api.get(f"/r/{slug}", follow_redirects=False, headers={"user-agent": "test-browser/raw"})
        with SessionLocal() as db:
            click = db.scalar(select(models.TrackingClick))

    assert response.status_code == 307
    assert response.headers["location"] == "https://market.example/p/click"
    assert click.tracking_link_id == link.id
    assert click.user_agent_hash
    assert click.user_agent_hash != "test-browser/raw"


def test_metrics_csv_import_facebook_rows():
    with client():
        with SessionLocal() as db:
            source = MetricsSourceRegistry(db).create(name="FB manual", source_type="manual_csv", platform="facebook")
            result = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": "facebook",
                            "destination_handle": "@account",
                            "posted_url": "https://facebook.com/post/1",
                            "sku": "SKU001",
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 12000,
                            "reach": 9000,
                            "impressions": 15000,
                        }
                    ]
                ),
                source_id=source.id,
                source_type="manual_csv",
            )

    assert result.imported_count == 1
    assert result.source_type == "manual_csv"
    assert result.warning_count == 0


@pytest.mark.parametrize(
    ("platform", "source_type", "expected_platform"),
    [
        ("facebook", "manual_csv", "facebook"),
        ("instagram", "manual_csv", "instagram"),
        ("youtube", "manual_csv", "youtube"),
        ("tiktok", "manual_csv", "tiktok"),
        ("telegram", "manual_csv", "telegram"),
        ("vk", "manual_csv", "vk"),
        ("ozon", "marketplace_csv", "ozon"),
        ("wb", "marketplace_csv", "wb"),
        ("partner", "partner_report", "partner"),
    ],
)
def test_platform_metrics_csv_paths_normalize_schema(platform: str, source_type: str, expected_platform: str):
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url=f"https://example.com/{platform}/post")
            row = {
                "platform": platform,
                "destination_handle": task.destination.handle,
                "posted_url": task.final_url if platform not in {"ozon", "wb"} else "",
                "tracking_slug": "",
                "sku": product.sku,
                "period_start": "2026-07-01",
                "period_end": "2026-07-07",
                "views": 900 if platform not in {"ozon", "wb"} else "",
                "reach": 700 if platform not in {"ozon", "wb"} else "",
                "impressions": 1000 if platform not in {"ozon", "wb"} else "",
                "likes": 40 if platform not in {"ozon", "wb"} else "",
                "comments": 5 if platform not in {"ozon", "wb"} else "",
                "shares": 3 if platform not in {"ozon", "wb"} else "",
                "saves": 2 if platform not in {"ozon", "wb"} else "",
                "clicks": 30,
                "orders": 2,
                "revenue": 3000,
            }
            batch = CSVImporter(db).import_csv_text(metrics_intake_csv([row]), campaign_id=campaign_id, source_type=source_type)
            stored_batch = db.get(models.MetricsIntakeBatch, batch.batch_id)

    normalized = stored_batch.rows_json[0]
    assert normalized["platform"] == expected_platform
    assert normalized["source_type"] == source_type
    assert "match_confidence" in normalized
    assert "warnings" in normalized


def test_platform_metrics_matrix_lists_all_required_platforms():
    platforms = {config.platform for config in PlatformMetricsMatrix.all_configs()}

    assert {"facebook", "instagram", "youtube", "tiktok", "telegram", "vk", "ozon", "wb", "partner"}.issubset(platforms)
    assert PlatformMetricsMatrix.config("youtube_shorts").official_connector_types == ["youtube_oauth", "youtube_analytics"]


def test_official_connector_gateway_is_gated_by_auth_status():
    with client():
        with SessionLocal() as db:
            destination_id = add_campaign_destination(db)
            destination = db.get(models.PublishingDestination, destination_id)
            destination.platform = "facebook"
            db.add(
                models.DestinationConnection(
                    destination_id=destination_id,
                    platform="facebook",
                    connection_type="meta_oauth",
                    status="connected",
                    auth_status="needs_auth",
                    credential_ref="META_FACEBOOK_TOKEN_REF",
                )
            )
            db.commit()
            readiness = OfficialConnectorGateway(db).readiness(destination_id)

    assert readiness["ready"] is False
    assert "oauth_or_token_not_valid" in readiness["blockers"]
    assert "manual_csv" in readiness["fallbacks"]


def test_metrics_import_matches_by_final_url():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://facebook.com/post/final-url")
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": task.platform,
                            "destination_handle": task.destination.handle,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 1000,
                            "clicks": 50,
                            "orders": 5,
                            "revenue": 7500,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            result = AttributionService(db).attribute_batch(batch.batch_id)
            metric = db.scalar(select(models.DestinationPostMetric))
            snapshot = db.scalar(select(models.FunnelSnapshot))

    assert result.matched_count == 1
    assert metric.publishing_task_id == task.id
    assert metric.destination_id == task.destination_id
    assert snapshot.clicks == 50


def test_metrics_import_matches_by_tracking_slug():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://market.example/p/slug")
            link = TrackingLinkService(db).create_for_task(task.id, campaign_id=campaign_id)
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": task.platform,
                            "tracking_slug": link.slug,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 2000,
                            "clicks": 120,
                            "orders": 6,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            result = AttributionService(db).attribute_batch(batch.batch_id)
            metric = db.scalar(select(models.DestinationPostMetric))

    assert result.matched_count == 1
    assert metric.publishing_task_id == task.id
    assert metric.posted_url == task.final_url
    assert metric.clicks == 120


def test_metrics_import_unmatched_row_warns_not_fails():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": "facebook",
                            "posted_url": "https://facebook.com/post/not-known",
                            "sku": "UNKNOWN-SKU",
                            "views": 10,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            result = AttributionService(db).attribute_batch(batch.batch_id)

    assert result.status == "unmatched"
    assert result.unmatched_count == 1
    assert result.warning_count >= 1


def test_funnel_snapshot_computes_ctr_and_conversion():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://facebook.com/post/funnel")
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "views": 100,
                            "clicks": 5,
                            "orders": 1,
                            "revenue": 250,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            AttributionService(db).attribute_batch(batch.batch_id)
            snapshot = db.scalar(select(models.FunnelSnapshot))

    assert snapshot.ctr == 0.05
    assert snapshot.conversion_rate == 0.2
    assert snapshot.revenue_per_click == 50
    assert snapshot.revenue_per_view == 2.5


def test_funnel_metrics_feed_campaign_performance():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://facebook.com/post/performance-feed")
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "views": 500,
                            "clicks": 25,
                            "orders": 2,
                            "revenue": 3200,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            AttributionService(db).attribute_batch(batch.batch_id)
            metric = db.scalar(select(models.CampaignPerformanceMetric))

    assert metric.campaign_id == campaign_id
    assert metric.publishing_task_id == task.id
    assert metric.views == 500
    assert metric.ctr == 0.05


def test_participant_dashboard_uses_funnel_metrics():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Funnel Owner", role="partner")
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://facebook.com/post/participant-funnel")
            OnboardingService(db).link_destination(participant.id, task.destination_id, relationship_type="owner")
            AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                assignment_type="publish_video",
            )
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "views": 700,
                            "clicks": 35,
                            "orders": 3,
                            "revenue": 4500,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            AttributionService(db).attribute_batch(batch.batch_id)
            stats = ParticipantMetricsService(db).dashboard_stats(participant.id, campaign_id=campaign_id)

    assert stats["views_total"] == 700
    assert stats["clicks_total"] == 35
    assert stats["orders_total"] == 3


def test_payout_ledger_uses_metrics_intake_orders():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Metrics CPA", role="partner")
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://facebook.com/post/metrics-payout")
            OnboardingService(db).link_destination(participant.id, task.destination_id, relationship_type="owner")
            rule = PayoutService(db).create_rule(name="Metrics intake CPA", payout_type="cpa", amount_fixed=250)
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                payout_rule_id=rule.id,
                assignment_type="publish_video",
            )
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": task.platform,
                            "posted_url": task.final_url,
                            "sku": product.sku,
                            "period_start": "2026-07-01",
                            "period_end": "2026-07-07",
                            "views": 1000,
                            "clicks": 60,
                            "orders": 4,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            AttributionService(db).attribute_batch(batch.batch_id)
            entry = PayoutService(db).calculate_for_assignment(assignment.id)

    assert entry.amount == 1000
    assert entry.reason == "orders_metric_cpa"


def test_no_raw_tokens_or_unofficial_login_paths():
    with client():
        with SessionLocal() as db:
            source = MetricsSourceRegistry(db).create(
                name="Meta official",
                source_type="official_api",
                platform="facebook",
                settings_json={"credential_ref": "META_FACEBOOK_TOKEN_REF"},
            )
            with pytest.raises(MetricsIntakeDataError):
                MetricsSourceRegistry(db).create(
                    name="Unsafe",
                    source_type="official_api",
                    platform="facebook",
                    settings_json={"access_token": "raw-token"},
                )

    payload = json.dumps(source.settings_json)
    assert "raw-token" not in payload
    assert "password" not in payload
    assert "cookie" not in payload


def test_metrics_intake_ui_renders():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        response = api.get(f"/metrics-intake?campaign_id={campaign_id}")

    assert response.status_code == 200, response.text
    assert "Metrics Intake" in response.text
    assert "Sources" in response.text
    assert "Tracking Links" in response.text
    assert "CSV Imports" in response.text
    assert "Unmatched Rows" in response.text


def test_publishing_task_requires_final_url_for_published_status():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/final-required")
            with pytest.raises(PublishingError):
                ManualUploadProvider(db).mark_published(task, "", "operator")


def test_payout_requires_final_url_for_published_post_rule():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Traceable Pay", role="creator")
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/remove-final")
            task.final_url = None
            db.commit()
            rule = PayoutService(db).create_rule(name="Published post guarded", payout_type="per_published_post", amount_fixed=700)
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                payout_rule_id=rule.id,
                assignment_type="publish_video",
            )
            with pytest.raises(ParticipantPortalDataError):
                PayoutService(db).calculate_for_assignment(assignment.id)


def test_metrics_import_requires_posted_url_or_tracking_slug():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            product, task = add_campaign_published_task(db, campaign_id, final_url="https://facebook.com/post/traceable")
            batch = CSVImporter(db).import_csv_text(
                metrics_intake_csv(
                    [
                        {
                            "platform": "facebook",
                            "destination_handle": task.destination.handle,
                            "sku": product.sku,
                            "views": 100,
                            "clicks": 10,
                        }
                    ]
                ),
                campaign_id=campaign_id,
            )
            result = AttributionService(db).attribute_batch(batch.batch_id)

    assert result.status == "unmatched"
    assert result.unmatched_count == 1
    assert result.unmatched_rows[0]["warning"] == "missing_posted_url_or_tracking_slug"


def test_assignment_detail_shows_publish_checklist():
    with client() as api:
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Checklist User", role="publisher")
            _, task = add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/checklist")
            assignment = AssignmentPortalService(db).create_assignment(
                participant_id=participant.id,
                campaign_id=campaign_id,
                publishing_task_id=task.id,
                assignment_type="publish_video",
            )
        response = api.get(f"/participant-portal?participant_id={participant.id}")

    assert response.status_code == 200
    assert "Publish checklist" in response.text
    assert "tracking_link_used_in_post" in response.text
    assert assignment.id


def test_participant_portal_shows_how_to_work_block():
    with client() as api:
        response = api.get("/participant-portal")

    assert response.status_code == 200
    assert "How to work" in response.text
    assert "Use the tracking_link in the post" in response.text


def test_metrics_intake_shows_csv_help():
    with client() as api:
        response = api.get("/metrics-intake")

    assert response.status_code == 200
    assert "Required identity" in response.text
    assert "Normalized columns" in response.text


def test_human_operating_rules_docs_exist():
    docs = [
        "docs/HUMAN_OPERATING_RULES.md",
        "docs/PUBLISHING_RULES_FOR_PARTICIPANTS.md",
        "docs/METRICS_SUBMISSION_RULES.md",
        "docs/PAYOUT_RULES_FOR_PARTICIPANTS.md",
    ]

    for doc in docs:
        assert Path(doc).exists()


def test_training_courses_seeded():
    with client():
        with SessionLocal() as db:
            courses = CurriculumService(db).seed_defaults()

    assert {
        "creator_basics",
        "publisher_basics",
        "metrics_basics",
        "payout_basics",
        "reviewer_basics",
    }.issubset({course.code for course in courses})


def test_training_course_has_lessons_and_quiz():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            course = CurriculumService(db).get_course_by_code("publisher_basics")
            lesson_count = len(course.lessons)
            quiz_count = len(course.quizzes)
            has_question = any(question["id"] == "publish_needs_review" for question in course.quizzes[0].questions_json)

    assert lesson_count > 0
    assert quiz_count > 0
    assert has_question


def test_participant_can_start_course():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Training Starter", role="publisher")
            course = CurriculumService(db).get_course_by_code("publisher_basics")
            attempt = ProgressService(db).start_course(participant_id=participant.id, course_id=course.id)

    assert attempt.status == "started"
    assert attempt.participant_id == participant.id
    assert attempt.course_id == course.id


def test_quiz_pass_creates_certification():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Certified Publisher", role="publisher")
            quiz = QuizService(db).get_for_course_code("publisher_basics")
            result = QuizService(db).submit(
                participant_id=participant.id,
                quiz_id=quiz.id,
                answers={
                    "publish_needs_review": "no",
                    "post_link": "tracking_link",
                    "post_back_reference": "final_url",
                },
            )
            certified = CertificationService(db).has_certification(participant.id, "publisher_basics")

    assert result.passed is True
    assert result.certification_id is not None
    assert certified is True


def test_quiz_fail_does_not_certify():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Needs Training", role="publisher")
            quiz = QuizService(db).get_for_course_code("publisher_basics")
            result = QuizService(db).submit(
                participant_id=participant.id,
                quiz_id=quiz.id,
                answers={
                    "publish_needs_review": "yes",
                    "post_link": "direct_product_url",
                    "post_back_reference": "caption",
                },
            )
            certified = CertificationService(db).has_certification(participant.id, "publisher_basics")

    assert result.passed is False
    assert result.certification_id is None
    assert certified is False


def test_publisher_gate_requires_training_when_enabled():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Gate Publisher", role="publisher")
            advisory = CertificationService(db).evaluate_gate(participant.id, "publishing", strict=False)
            with pytest.raises(TrainingAcademyDataError):
                CertificationService(db).evaluate_gate(participant.id, "publishing", strict=True)
            quiz = QuizService(db).get_for_course_code("publisher_basics")
            QuizService(db).submit(
                participant_id=participant.id,
                quiz_id=quiz.id,
                answers={
                    "publish_needs_review": "no",
                    "post_link": "tracking_link",
                    "post_back_reference": "publishing_task",
                },
            )
            passed = CertificationService(db).evaluate_gate(participant.id, "publishing", strict=True)

    assert advisory["status"] == "advisory"
    assert passed["status"] == "passed"


def test_metrics_gate_requires_training_when_enabled():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Metrics Trainee", role="operator")
            with pytest.raises(TrainingAcademyDataError):
                CertificationService(db).evaluate_gate(participant.id, "metrics_submission", strict=True)
            quiz = QuizService(db).get_for_course_code("metrics_basics")
            result = QuizService(db).submit(
                participant_id=participant.id,
                quiz_id=quiz.id,
                answers={
                    "missing_traceability": "unmatched warning",
                    "tracking_vs_final_url": "tracking_link",
                },
            )
            gate = CertificationService(db).evaluate_gate(participant.id, "metrics_submission", strict=True)

    assert result.passed is True
    assert gate["course_code"] == "metrics_basics"
    assert gate["status"] == "passed"


def test_training_academy_ui_renders():
    with client() as api:
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Academy UI", role="creator")
        response = api.get(f"/training-academy?participant_id={participant.id}")

    assert response.status_code == 200, response.text
    assert "Training Academy" in response.text
    assert "Course Catalog" in response.text
    assert "Quiz / Certification Test" in response.text
    assert "Creator Basics" in response.text


def test_training_api_flow_does_not_expose_answers():
    with client() as api:
        participant_response = api.post("/api/participant-portal/participants", json={"display_name": "API Trainee", "role": "publisher"})
        assert participant_response.status_code == 200, participant_response.text
        participant_id = participant_response.json()["id"]
        courses_response = api.get("/api/training/courses")
        assert courses_response.status_code == 200, courses_response.text
        assert "correct_answers" not in courses_response.text
        publisher_course = next(course for course in courses_response.json() if course["code"] == "publisher_basics")
        start_response = api.post(f"/api/training/courses/{publisher_course['id']}/start", json={"participant_id": participant_id})
        assert start_response.status_code == 200, start_response.text
        quiz_id = publisher_course["quizzes"][0]["id"]
        quiz_response = api.post(
            f"/api/training/quizzes/{quiz_id}/submit",
            json={
                "participant_id": participant_id,
                "answers": {
                    "publish_needs_review": "no",
                    "post_link": "tracking_link",
                    "post_back_reference": "final_url",
                },
            },
        )
        progress_response = api.get(f"/api/training/participants/{participant_id}/progress")

    assert quiz_response.status_code == 200, quiz_response.text
    assert quiz_response.json()["passed"] is True
    assert progress_response.status_code == 200, progress_response.text
    assert any(cert["course_code"] == "publisher_basics" for cert in progress_response.json()["certifications"])


def test_participant_portal_links_training():
    with client() as api:
        response = api.get("/participant-portal")

    assert response.status_code == 200, response.text
    assert "/training-academy" in response.text
    assert "role courses, quizzes and certifications" in response.text


def test_beginner_tracks_seeded():
    track_titles = {track["title"] for track in BEGINNER_TRACKS}

    assert "Publisher / Placement Operator" in track_titles
    assert "Metrics Operator" in track_titles
    assert "Reviewer Assistant" in track_titles
    assert "Creator / Editor" in track_titles
    assert "Channel / Destination Owner" in track_titles


def test_publisher_track_explains_final_url_tracking_link_payout():
    publisher_track = next(track for track in BEGINNER_TRACKS if track["code"] == "publisher_operator_track")
    serialized = json.dumps(publisher_track)

    assert "tracking_link" in serialized
    assert "final_url" in serialized
    assert "payout" in serialized.lower()


def test_metrics_operator_track_explains_csv_and_unmatched_rows():
    metrics_track = next(track for track in BEGINNER_TRACKS if track["code"] == "metrics_operator_track")
    serialized = json.dumps(metrics_track)

    assert "CSV" in serialized or "csv" in serialized
    assert "unmatched" in serialized
    assert "posted_url" in serialized


def test_reviewer_track_blocks_approving_identity_drift():
    reviewer_track = next(track for track in BEGINNER_TRACKS if track["code"] == "reviewer_assistant_track")
    serialized = json.dumps(reviewer_track)

    assert "distorted product" in serialized
    assert "regenerate" in serialized
    assert "approves distorted product" in serialized


def test_creator_track_explains_brief_and_product_constraints():
    creator_track = next(track for track in BEGINNER_TRACKS if track["code"] == "creator_editor_track")
    serialized = json.dumps(creator_track)

    assert "brief" in serialized.lower()
    assert "product identity" in serialized
    assert "geometry" in serialized


def test_channel_owner_track_explains_readiness_capacity_stats():
    owner_track = next(track for track in BEGINNER_TRACKS if track["code"] == "destination_owner_track")
    serialized = json.dumps(owner_track)

    assert "readiness" in serialized
    assert "capacity" in serialized
    assert "stats" in serialized


def test_training_platform_playbooks_seeded():
    with client():
        with SessionLocal() as db:
            courses = CurriculumService(db).seed_defaults()
            codes = {course.code for course in courses}

    assert {
        "instagram_reels_playbook",
        "facebook_playbook",
        "youtube_shorts_playbook",
        "tiktok_playbook",
        "telegram_playbook",
        "vk_playbook",
        "marketplace_metrics_playbook",
        "partner_slot_playbook",
    }.issubset(codes)


def test_instagram_playbook_has_tracking_final_url_stats_lessons():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            course = CurriculumService(db).get_course_by_code("instagram_reels_playbook")
            payload = CurriculumService(db).course_payload(course, include_answers=True)
            serialized = json.dumps(payload)

    assert "tracking_link" in serialized
    assert "final_url" in serialized
    assert "views" in serialized
    assert "reach" in serialized


def test_youtube_playbook_mentions_oauth_or_csv_fallback():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            course = CurriculumService(db).get_course_by_code("youtube_shorts_playbook")
            payload = CurriculumService(db).course_payload(course, include_answers=True)
            serialized = json.dumps(payload).lower()

    assert "oauth" in serialized
    assert "csv" in serialized
    assert "watch_time" in serialized


def test_tiktok_playbook_blocks_unofficial_scraping():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            course = CurriculumService(db).get_course_by_code("tiktok_playbook")
            payload = CurriculumService(db).course_payload(course, include_answers=True)
            serialized = json.dumps(payload).lower()

    assert "unofficial" in serialized
    assert "scraping" in serialized
    assert "no" in serialized


def test_marketplace_playbook_explains_orders_revenue_source():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            course = CurriculumService(db).get_course_by_code("marketplace_metrics_playbook")
            payload = CurriculumService(db).course_payload(course, include_answers=True)
            serialized = json.dumps(payload).lower()

    assert "orders" in serialized
    assert "revenue" in serialized
    assert "source of truth" in serialized


def test_platform_certification_badges_created():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Badge User", role="publisher")
            quiz = QuizService(db).get_for_course_code("instagram_reels_playbook")
            result = QuizService(db).submit(
                participant_id=participant.id,
                quiz_id=quiz.id,
                answers={"instagram_link": "tracking_link", "instagram_final_url": "final_url"},
            )
            badges = CertificationService(db).certified_badges(participant.id)

    assert result.passed is True
    assert "instagram_reels_certified" in badges
    assert COURSE_BADGE_BY_CODE["instagram_reels_playbook"] == "instagram_reels_certified"


def test_strict_gate_blocks_assignment_without_platform_certification():
    with client():
        with SessionLocal() as db:
            CurriculumService(db).seed_defaults()
            participant = ParticipantService(db).create(display_name="Strict Platform", role="publisher")
            with pytest.raises(TrainingAcademyDataError):
                CertificationService(db).platform_readiness(participant.id, "Instagram Reels", strict=True)
            quiz = QuizService(db).get_for_course_code("instagram_reels_playbook")
            QuizService(db).submit(
                participant_id=participant.id,
                quiz_id=quiz.id,
                answers={"instagram_link": "tracking_link", "instagram_final_url": "final_url"},
            )
            readiness = CertificationService(db).platform_readiness(participant.id, "Instagram Reels", strict=True)

    assert readiness["status"] == "ready"
    assert readiness["badge"] == "instagram_reels_certified"


def test_zero_experience_start_page_renders():
    with client() as api:
        response = api.get("/training-academy")

    assert response.status_code == 200, response.text
    assert "I Have Zero Experience" in response.text
    assert "How to Earn" in response.text
    assert "Scenario Simulator" in response.text


def test_earning_lesson_requires_assignment_final_url_metrics():
    with client() as api:
        response = api.get("/training-academy")

    assert response.status_code == 200, response.text
    assert "assignment" in response.text
    assert "final_url" in response.text
    assert "metrics" in response.text


def test_scenario_publish_approved_reel_passes_with_final_url():
    result = ScenarioService().evaluate(
        "publish_approved_reel",
        {
            "video_status": "approved",
            "link_used": "tracking_link",
            "destination": "assigned",
            "final_url": "provided",
        },
    )

    assert result["passed"] is True
    assert result["status"] == "passed"


def test_scenario_publish_without_final_url_fails():
    result = ScenarioService().evaluate(
        "publish_approved_reel",
        {
            "video_status": "approved",
            "link_used": "tracking_link",
            "destination": "assigned",
        },
    )

    assert result["passed"] is False
    assert any(failure["field"] == "final_url" for failure in result["failures"])


def test_participant_portal_shows_how_to_earn_block():
    with client() as api:
        response = api.get("/participant-portal")

    assert response.status_code == 200, response.text
    assert "How to earn" in response.text
    assert "Payout is blocked" in response.text


def test_participant_portal_warns_missing_platform_training():
    with client() as api:
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Platform Missing", role="publisher")
            destination = models.PublishingDestination(
                brand="Altea",
                platform="Instagram Reels",
                name="Altea IG",
                handle="@altea",
                status="active",
                posting_mode="manual",
                auth_status="manual_only",
            )
            db.add(destination)
            db.commit()
            db.refresh(destination)
            OnboardingService(db).link_destination(participant.id, destination.id, relationship_type="publisher")
        response = api.get(f"/participant-portal?participant_id={participant.id}")

    assert response.status_code == 200, response.text
    assert "training_recommended" in response.text
    assert "instagram_reels_playbook" in response.text


def test_metrics_intake_shows_platform_csv_examples():
    with client() as api:
        response = api.get("/metrics-intake")

    assert response.status_code == 200, response.text
    assert "facebook_metrics.csv" in response.text
    assert "youtube_shorts_metrics.csv" in response.text
    assert "marketplace_conversion.csv" in response.text
    assert "Common mistakes" in response.text


def test_engine_audit_scores_all_dimensions():
    reset_db()
    with SessionLocal() as db:
        report = EngineAuditScorecardService(db).run()
        output = EngineAuditScorecardService(db).output(report)

    assert output.status in {"strong", "ok", "weak", "blocked"}
    assert output.score_scale == "1_to_10"
    assert len(output.dimensions) == 9
    assert {dimension.key for dimension in output.dimensions} == {
        "interface",
        "video_quality",
        "brief_quality",
        "asset_readiness",
        "creator_clarity",
        "training",
        "metrics",
        "destinations",
        "production",
    }
    assert all(1 <= dimension.score <= 10 for dimension in output.dimensions)
    assert {dimension.status for dimension in output.dimensions} <= {"strong", "ok", "weak", "blocked"}
    assert all(dimension.reasons for dimension in output.dimensions)
    assert all(dimension.required_fixes for dimension in output.dimensions)
    assert all(dimension.next_action for dimension in output.dimensions)
    assert len(output.road_to_10) == 9
    assert output.blockers


def test_engine_audit_report_writer_persists_json(tmp_path):
    reset_db()
    with SessionLocal() as db:
        run = EngineAuditScorecardService(db).run()
        path = EngineAuditReportService(db).write(run.id, output_dir=tmp_path)

    report_path = Path(path)
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["id"] == run.id
    assert payload["overall_score"] == run.total_score
    assert len(payload["dimensions"]) == 9


def test_engine_audit_flags_missing_real_output_acceptance():
    reset_db()
    with SessionLocal() as db:
        run = EngineAuditScorecardService(db).run()
        output = EngineAuditScorecardService(db).output(run)

    video_quality = next(item for item in output.dimensions if item.key == "video_quality")
    assert video_quality.status in {"blocked", "weak"}
    assert "latest_output_acceptance_missing" in video_quality.reasons
    assert "Run one prompt-only accepted plan" in video_quality.required_fixes[0]


def test_engine_audit_scores_ai_brief_quality_from_v23_models():
    with client() as api:
        prepare_ai_brief_fixture(api, with_quality_check=True)
        with SessionLocal() as db:
            run = EngineAuditScorecardService(db).run()
            output = EngineAuditScorecardService(db).output(run)

    brief_quality = next(item for item in output.dimensions if item.key == "brief_quality")
    assert brief_quality.score >= 8
    assert brief_quality.evidence["ai_production_briefs"] >= 1
    assert brief_quality.evidence["scene_blueprints"] >= 1
    assert brief_quality.evidence["director_prompt_packs"] >= 1
    assert brief_quality.evidence["brief_quality_checks"] >= 1


def test_engine_audit_scores_asset_readiness_from_one_video_plan():
    with client() as api:
        product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
            OneVideoAcceptanceService(db).build_plan(product_id, platform="Instagram Reels")
            run = EngineAuditScorecardService(db).run()
            output = EngineAuditScorecardService(db).output(run)

    asset = next(item for item in output.dimensions if item.key == "asset_readiness")
    assert asset.evidence["wrapper_refs_count"] >= 2
    assert asset.evidence["one_video_plans"] >= 1
    assert asset.evidence["scene_permissions"]["bite_scene_allowed"] is False
    assert "edible_reference_count_below_3" in asset.reasons


def test_engine_audit_flags_low_interface_without_control_room():
    reset_db()
    with SessionLocal() as db:
        run = EngineAuditScorecardService(db).run()
        output = EngineAuditScorecardService(db).output(run)

    interface = next(item for item in output.dimensions if item.key == "interface")
    assert interface.evidence["control_room_exists"] is True
    assert interface.score < 10
    assert "many_specialized_pages_still_need_single_entrypoint" in interface.reasons


def test_engine_audit_recommends_paid_smoke_when_prompt_only_ready():
    with client() as api:
        product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
            service = OneVideoAcceptanceService(db)
            plan = service.build_plan(product_id, platform="Instagram Reels")
            service.prompt_only(plan.id, provider="runway")
            run = EngineAuditScorecardService(db).run()
            output = EngineAuditScorecardService(db).output(run)

    production = next(item for item in output.dimensions if item.key == "production")
    assert production.evidence["one_video_acceptance_status"]["prompt_only_ready"] >= 1
    assert production.evidence["paid_smoke_status"] == "pending"
    assert "confirm_runway_credits_then_one_paid_smoke" in [item["next_action"] for item in output.road_to_10]


def test_engine_audit_api_and_ui_render_scorecard():
    with client() as api:
        api_response = api.post("/api/engine-audit/run", json={"write_report": False})
        latest_response = api.get("/api/engine-audit/latest")
        recommendations_response = api.get("/api/engine-audit/recommendations")
        page_response = api.get("/engine-audit")

    assert api_response.status_code == 200, api_response.text
    payload = api_response.json()
    assert payload["score_scale"] == "1_to_10"
    assert len(payload["dimensions"]) == 9
    assert latest_response.status_code == 200, latest_response.text
    assert recommendations_response.status_code == 200, recommendations_response.text
    assert recommendations_response.json()["recommendations"]
    assert payload["road_to_10"]
    assert page_response.status_code == 200, page_response.text
    assert "Engine Audit" in page_response.text
    assert "Road to 10/10" in page_response.text
    assert "Scores by dimension" in page_response.text
    assert "Blockers" in page_response.text
    assert "Required fixes" in page_response.text
    assert "Interface usability" in page_response.text
    assert "Video quality" in page_response.text


def test_control_room_snapshot_uses_latest_engine_audit():
    reset_db()
    with SessionLocal() as db:
        audit_run = EngineAuditScorecardService(db).run()
        service = ControlRoomSnapshotService(db)
        snapshot = service.refresh(role="owner")
        output = service.output(snapshot)

    assert snapshot.engine_audit_run_id == audit_run.id
    assert output.summary["engine_audit_total_score"] == audit_run.total_score
    assert output.scorecard["id"] == audit_run.id


def test_control_room_owner_dashboard_shows_production_readiness():
    reset_db()
    with SessionLocal() as db:
        snapshot = ControlRoomSnapshotService(db).refresh(role="owner")
        output = ControlRoomSnapshotService(db).output(snapshot)

    assert any(item.label == "Engine scorecard available" for item in output.ready_items)
    assert output.summary["top_blocker_count"] >= 1
    assert "video_quality" in output.summary["dimension_scores"]
    assert "campaign_readiness" in output.summary
    assert "destination_capacity" in output.summary
    assert "metrics_coverage" in output.summary
    assert "payout_exposure" in output.summary
    assert "paid_smoke_status" in output.summary
    assert "real_video_next_action" in output.summary
    assert output.summary["executive_next_decisions"]
    assert any(action.target_module in {"engine_audit", "one_video_acceptance", "output_acceptance"} for action in output.next_actions)


def test_control_room_content_lead_shows_quality_and_review_items():
    with client() as api:
        product_id = create_product(api, title="Control Room Content Lead")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id, primary_url="https://example.com/control-room-wrapper.png")
            OneVideoAcceptanceService(db).build_plan(product_id, platform="Instagram Reels")
            snapshot = ControlRoomSnapshotService(db).refresh(role="content_lead")
            output = ControlRoomSnapshotService(db).output(snapshot)

    assert any("one-video plans ready" in item.label for item in output.ready_items)
    assert any(item.target_module in {"one_video_acceptance", "ai_brief_studio", "output_acceptance"} for item in [*output.blocked_items, *output.review_queue])


def test_control_room_reviewer_shows_output_acceptance_queue():
    with client() as api:
        _, brief_id, video_job_id = prepare_output_acceptance_fixture(api, title="Control Room Reviewer")
        with SessionLocal() as db:
            acceptance = AcceptanceReviewService(db).review(video_job_id=video_job_id, ai_production_brief_id=brief_id)
            snapshot = ControlRoomSnapshotService(db).refresh(role="reviewer")
            output = ControlRoomSnapshotService(db).output(snapshot)

    assert acceptance.status in {"needs_human_review", "needs_regeneration"}
    assert any(item.payload.get("output_acceptance_id") == acceptance.id for item in output.review_queue)


def test_control_room_creator_shows_assignment_final_url_and_payout_blockers():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            participant = ParticipantService(db).create(display_name="Control Creator", role="creator")
            assignment = AssignmentPortalService(db).create_assignment(participant_id=participant.id, campaign_id=campaign_id)
            SubmissionService(db).submit(assignment_id=assignment.id, external_url="https://example.com/video.mp4")
            rule = PayoutService(db).create_rule(name="Blocked payout", payout_type="per_video", amount_fixed=500)
            assignment.payout_rule_id = rule.id
            db.commit()
            PayoutService(db).calculate_for_assignment(assignment.id)
            snapshot = ControlRoomSnapshotService(db).refresh(role="creator_publisher")
            output = ControlRoomSnapshotService(db).output(snapshot)

    labels = [item.label for item in output.blocked_items]
    assert any("submissions missing final_url" in label for label in labels)
    assert any("payout blockers" in label for label in labels)


def test_control_room_metrics_operator_shows_unmatched_rows_and_missing_stats():
    with client():
        campaign_id = campaign_fixture(row_count=1, target_videos=2, target_destinations=1)
        with SessionLocal() as db:
            add_campaign_published_task(db, campaign_id, final_url="https://example.com/post/no-metrics")
            db.add(
                models.MetricsIntakeBatch(
                    campaign_id=campaign_id,
                    source_type="manual_csv",
                    imported_count=2,
                    matched_count=1,
                    unmatched_count=1,
                    unmatched_rows_json=[{"posted_url": "https://example.com/unmatched"}],
                )
            )
            db.commit()
            snapshot = ControlRoomSnapshotService(db).refresh(role="metrics_operator")
            output = ControlRoomSnapshotService(db).output(snapshot)

    assert any("unmatched metric rows" in item.label for item in output.blocked_items)
    assert any("publications missing metrics" in item.label for item in output.blocked_items)


def test_control_room_routes_actions_to_existing_modules():
    reset_db()
    with SessionLocal() as db:
        service = ControlRoomSnapshotService(db)
        snapshot = service.refresh(role="owner")
        action = service.actions(snapshot.id)[0]
        routed = service.route_action(action.id)

    assert routed.status == "routed"
    assert routed.target_url.startswith("/")


def test_control_room_respects_public_pilot_role_gates():
    with client() as api:
        product_id = create_product(api, title="Control Room Gates")
        with SessionLocal() as db:
            attach_approved_reference_pair(db, product_id, primary_url="https://example.com/gated-wrapper.png")
            plan = OneVideoAcceptanceService(db).build_plan(product_id, platform="Instagram Reels")
            OneVideoAcceptanceService(db).prompt_only(plan.id, provider="runway")
            EngineAuditScorecardService(db).run()
            snapshot = ControlRoomSnapshotService(db).refresh(role="content_lead")
            output = ControlRoomSnapshotService(db).output(snapshot)

    assert any(action.requires_spend_gate or action.reason in {"spend_gate_required", "role_producer_cannot_one_video_real_run"} for action in output.gated_actions)
    assert all(action.safe_to_execute is False for action in output.gated_actions)


def test_control_room_ui_renders_role_dashboards():
    with client() as api:
        response = api.get("/control-room?role=owner")

    assert response.status_code == 200, response.text
    assert "Unified Control Room" in response.text
    assert "Public Pilot Control Room" in response.text
    assert "Executive snapshot" in response.text
    assert "Scores by dimension" in response.text
    assert "Paid smoke" in response.text
    assert "owner" in response.text
    assert "What is ready" in response.text
    assert "What is blocked" in response.text
    assert "Road to 10/10" in response.text


def test_control_room_creator_alias_uses_creator_publisher_dashboard():
    with client() as api:
        response = api.get("/control-room?role=creator")

    assert response.status_code == 200, response.text
    assert "creator_publisher" in response.text
    assert "my assignments" in response.text


def test_control_room_is_main_post_login_entrypoint():
    with client() as api:
        response = api.post("/login", data={"email": "owner@example.com", "password": "local"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/control-room"


def test_engine_audit_cli_writes_report(tmp_path):
    reset_db()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/engine_audit_run.py",
            "--write-report",
            "--output-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Overall Score:" in result.stdout
    assert "Road to 10/10:" in result.stdout
    reports = list(tmp_path.glob("engine_audit_*.json"))
    assert len(reports) == 1
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert len(payload["dimensions"]) == 9


def test_engine_audit_cli_runs(tmp_path):
    reset_db()
    result = subprocess.run(
        [sys.executable, "scripts/engine_audit_report.py", "--output-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Report:" in result.stdout
    assert list(tmp_path.glob("engine_audit_*.json"))


def test_one_video_scene_policy_blocks_bite_without_edible_refs():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        policy = ProductScenePolicyService(db).evaluate(product_id, provider="runway")

    assert policy.wrapper_reference_count == 2
    assert policy.edible_reference_count == 0
    assert policy.current_asset_tier == "tier_1"
    assert policy.wrapper_scene_allowed is False
    assert policy.bite_scene_allowed is False
    assert policy.texture_macro_allowed is False
    assert "bite_scene" in policy.blocked_scene_types
    assert "approved_cutaway_insert" not in policy.allowed_scene_types
    assert "packshot_overlay" in policy.allowed_scene_types
    assert "add_edible_cutaway_texture_and_use_case_refs" in policy.next_actions


def test_one_video_scene_policy_does_not_count_lifestyle_as_edible_ref():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        lifestyle = ProductAssetStorage(db).attach_url(
            product_id,
            url="https://example.com/wibes_creator_table_context.png",
            asset_type="lifestyle",
            manual_label="female creator at table with coffee",
        )
        ProductAssetStorage(db).update_asset(lifestyle.id, review_status="approved", asset_type="lifestyle")
        policy = ProductScenePolicyService(db).evaluate(product_id, provider="runway")

    assert policy.lifestyle_reference_count == 1
    assert policy.style_reference_count == 1
    assert policy.edible_reference_count == 0
    assert policy.bite_scene_allowed is False
    assert policy.texture_macro_allowed is False
    assert policy.asset_audit is not None
    assert next(item for item in policy.asset_audit.lifestyle_refs if item.key == "coffee_table_context").status == "yes"
    assert next(item for item in policy.asset_audit.edible_refs if item.key == "bitten_bar").status == "no"
    assert policy.asset_audit.decision == "safe_prompt_only_or_overlay_until_edible_refs_ready"


def test_one_video_render_plan_uses_packshot_overlay_when_only_identity_refs_exist():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        plan = OneVideoAcceptanceService(db).build_plan(product_id, platform="Instagram Reels")

    policy = plan.product_scene_policy_json
    proof_scene = next(scene for scene in plan.scene_plan_json if scene["role"] == "proof_use_case")
    assert plan.creative_variant_id
    assert plan.ai_production_brief_id
    assert plan.director_prompt_pack_id
    assert policy["bite_scene_allowed"] is False
    assert "exact approved front packshot" in proof_scene["visual"].lower()
    assert "do not generate wrapper handling" in proof_scene["visual"].lower()
    assert "generic muesli bar" in plan.negative_prompt
    assert "granola bar" in plan.negative_prompt
    assert "pink raspberry interior" in plan.negative_prompt
    assert "green pistachio center" in plan.negative_prompt
    assert "hazelnut flavor variant" in plan.negative_prompt
    flavor_identity = plan.prompt_preview_json["product_flavor_identity"]
    assert flavor_identity["target_variant"] == "Bombbar Pro Dubai Mango & Kunafa"
    assert "bright yellow mango center" in flavor_identity["required_visuals"]
    assert all("Flavor identity lock" in item["prompt_text"] for item in plan.prompt_preview_json["scene_prompts"])
    assert "no_muesli_granola_visual_drift" in plan.acceptance_checklist_json
    assert plan.product_scene_policy_json["asset_audit"]["decision"] == "safe_prompt_only_or_overlay_until_edible_refs_ready"
    assert plan.prompt_preview_json["mvp_scorecard"]["total_score"] == 76
    assert plan.prompt_preview_json["mvp_scorecard"]["verdict"] == "usable_with_fixes"


def test_one_video_acceptance_api_uses_issue_endpoint_names():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_tier_2_contract(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")

    build_response = api.post(
        "/api/one-video-acceptance/plans/build",
        json={"product_id": product_id, "platform": "Instagram Reels", "duration_seconds": 15},
    )
    assert build_response.status_code == 200, build_response.text
    plan_id = build_response.json()["id"]

    prompt_response = api.post(f"/api/one-video-acceptance/plans/{plan_id}/prompt-only", json={})
    assert prompt_response.status_code == 200, prompt_response.text
    assert prompt_response.json()["status"] == "prompt_only_ready"

    real_response = api.post(f"/api/one-video-acceptance/plans/{plan_id}/run-real", json={"real_run": False})
    assert real_response.status_code == 400
    assert "real-run" in real_response.text


def test_one_video_prompt_only_builds_prompt_pack_without_video_job():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        service = OneVideoAcceptanceService(db)
        plan = service.build_plan(product_id, platform="Instagram Reels")
        before_jobs = db.scalar(select(func.count()).select_from(models.VideoJob))
        plan = service.prompt_only(plan.id, provider="runway")
        after_jobs = db.scalar(select(func.count()).select_from(models.VideoJob))
        prompt_pack = db.get(models.PromptPack, plan.prompt_pack_id)

    assert before_jobs == after_jobs
    assert plan.status == "prompt_only_ready"
    assert prompt_pack is not None
    assert prompt_pack.prompt_pack_json["one_video_render_plan_id"] == plan.id
    assert prompt_pack.prompt_pack_json["product_scene_policy"]["bite_scene_allowed"] is False
    assert prompt_pack.prompt_pack_json["asset_audit"]["decision"] == "safe_prompt_only_or_overlay_until_edible_refs_ready"
    assert prompt_pack.prompt_pack_json["mvp_scorecard"]["verdict"] == "usable_with_fixes"
    assert any("granola bar" in item["negative_prompt"] for item in prompt_pack.negative_prompts_json)


def test_one_video_real_run_records_blocked_by_runway_credits(monkeypatch):
    captured = {}

    class FakeRunner:
        def __init__(self, db: Session):
            self.db = db

        def run_from_variant(self, *_args, **kwargs):
            captured.update(kwargs)
            prepared = self.db.get(models.VideoGenerationVariant, kwargs["prepared_generation_variant_id"])
            assert prepared is not None
            assert prepared.prompt_pack_json["one_video_render_plan_id"]
            assert prepared.prompt_pack_json["product_asset_contract"]
            assert prepared.provider_payload_json["product_asset_contract"]
            raise ProviderConfigurationError("Runway generation request failed: HTTP 400: You do not have enough credits to run this task.")

    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    monkeypatch.setattr("app.one_video_acceptance.acceptance_service.RealSmokeRunner", FakeRunner)
    with SessionLocal() as db:
        attach_approved_tier_2_contract(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        service = OneVideoAcceptanceService(db)
        plan = service.prompt_only(service.build_plan(product_id, platform="Instagram Reels").id, provider="runway")
        result = service.run_real(plan.id, provider="runway", real_run=True, max_scenes=1)
        db.refresh(plan)
        audit_run = EngineAuditScorecardService(db).run()
        audit = EngineAuditScorecardService(db).output(audit_run)
        video_quality = next(item for item in audit.dimensions if item.key == "video_quality")
        production = next(item for item in audit.dimensions if item.key == "production")

    assert result.status == "blocked_by_runway_credits"
    assert result.human_review_status == "blocked"
    assert result.video_job_id is None
    assert result.output_acceptance_id is None
    assert result.result_json["blocker"] == "blocked_by_runway_credits"
    assert result.result_json["next_action"] == "add_runway_credits_then_rerun_one_scene_real_smoke"
    assert captured["prepared_generation_variant_id"] == plan.video_generation_variant_id
    assert plan.status == "real_run_blocked_by_runway_credits"
    assert video_quality.next_action == "blocked_by_runway_credits"
    assert production.next_action == "blocked_by_runway_credits"
    assert production.evidence["paid_smoke_status"] == "pending"


def test_one_video_human_review_records_muesli_and_wrapper_drift():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        service = OneVideoAcceptanceService(db)
        plan = service.prompt_only(service.build_plan(product_id, platform="Instagram Reels").id, provider="runway")
        generation_variant = db.get(models.VideoGenerationVariant, plan.video_generation_variant_id)
        video_job = models.VideoJob(
            script_variant_id=generation_variant.script_variant_id,
            provider="runway",
            status="video_generated",
            duration_seconds=15,
            output_video_path="test_media/fake_one_video.mp4",
        )
        db.add(video_job)
        db.flush()
        result = models.OneVideoRenderResult(
            plan_id=plan.id,
            product_id=product_id,
            creative_variant_id=plan.creative_variant_id,
            video_generation_variant_id=generation_variant.id,
            prompt_pack_id=plan.prompt_pack_id,
            video_job_id=video_job.id,
            provider="runway",
            status="needs_human_review",
            human_review_status="needs_human_review",
        )
        db.add(result)
        db.commit()
        result = service.review(
            result.id,
            status="needs_regeneration",
            notes="Wrapper drifted and edible bar became muesli-like.",
        )
        acceptance = db.get(models.VideoOutputAcceptance, result.output_acceptance_id)

    assert result.human_review_status == "needs_regeneration"
    assert acceptance is not None
    assert acceptance.status == "needs_regeneration"
    assert "packaging_drift" in acceptance.blockers_json
    assert "edible_product_drift" in acceptance.blockers_json
    assert acceptance.publishing_readiness == "blocked"


def test_real_smoke_wrapper_drift_routes_control_room_to_product_compositing():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        service = OneVideoAcceptanceService(db)
        plan = service.prompt_only(service.build_plan(product_id, platform="Instagram Reels").id, provider="runway")
        generation_variant = db.get(models.VideoGenerationVariant, plan.video_generation_variant_id)
        video_job = models.VideoJob(
            script_variant_id=generation_variant.script_variant_id,
            provider="runway",
            status="video_generated",
            duration_seconds=2.04,
            output_video_path="test_media/real_smoke_wrapper_drift.mp4",
        )
        db.add(video_job)
        db.flush()
        result = models.OneVideoRenderResult(
            plan_id=plan.id,
            product_id=product_id,
            creative_variant_id=plan.creative_variant_id,
            video_generation_variant_id=generation_variant.id,
            prompt_pack_id=plan.prompt_pack_id,
            video_job_id=video_job.id,
            provider="runway",
            status="video_generated",
            human_review_status="needs_human_review",
        )
        db.add(result)
        db.commit()
        result = service.review(
            result.id,
            status="needs_regeneration",
            notes=(
                "Wrapper, logo and label drifted. Output is 2.04 seconds and has no locked end card. "
                "No edible product was shown, so muesli drift was not tested."
            ),
        )
        acceptance = db.get(models.VideoOutputAcceptance, result.output_acceptance_id)
        audit_run = EngineAuditScorecardService(db).run()
        audit = EngineAuditScorecardService(db).output(audit_run)
        snapshot = ControlRoomSnapshotService(db).output(ControlRoomSnapshotService(db).refresh(role="owner"))

    video_quality = next(item for item in audit.dimensions if item.key == "video_quality")
    production = next(item for item in audit.dimensions if item.key == "production")
    assert acceptance is not None
    assert "packaging_drift" in acceptance.blockers_json
    assert "edible_product_drift" not in acceptance.blockers_json
    assert video_quality.next_action == "product_compositing_required"
    assert production.next_action == "product_compositing_required"
    assert production.evidence["paid_smoke_status"] == "completed"
    assert snapshot.summary["paid_smoke_status"] == "completed"
    assert snapshot.summary["real_video_next_action"] == "product_compositing_required"
    assert any(action.action_type == "product_compositing_required" for action in snapshot.next_actions)
    assert any(action.action_type == "product_compositing_required" for action in snapshot.safe_actions)


def test_one_video_acceptance_ui_renders_plan():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        plan = OneVideoAcceptanceService(db).build_plan(product_id, platform="Instagram Reels")

    response = api.get(f"/one-video-acceptance?plan_id={plan.id}")
    assert response.status_code == 200
    assert "One Video Acceptance" in response.text
    assert "Product Asset Contract" in response.text
    assert "Нельзя генерировать bite/macro" in response.text
    assert "Interaction" in response.text
    assert "Asset Audit" in response.text
    assert "MVP Scorecard" in response.text


def test_smoke_readiness_reports_missing_plan():
    api = client()
    response = api.post("/api/smoke-readiness/recover", json={"plan_id": 3})
    assert response.status_code == 200, response.text
    payload = response.json()
    latest = api.get("/api/smoke-readiness/latest")
    run_response = api.get(f"/api/smoke-readiness/runs/{payload['id']}")

    assert latest.status_code == 200
    assert run_response.status_code == 200
    assert payload["report"]["requested_plan_id"] == 3
    assert payload["report"]["requested_plan_exists"] is False
    assert payload["report"]["final_decision"] == "blocked_by_missing_plan"
    assert any(blocker["blocker_type"] == "missing_plan" for blocker in payload["blockers"])


def test_smoke_readiness_rebuilds_plan_when_requested():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        run = RecoveryService(db).recover(product_id=product_id, rebuild_plan=True)
        output = ReadinessReportService(db).output(run)
        plan = db.get(models.OneVideoRenderPlan, output.one_video_render_plan_id)

    assert plan is not None
    assert plan.status == "prompt_only_ready"
    assert output.prompt_pack_id is not None
    assert output.report.rebuilt_plan_id == plan.id
    assert output.report.prompt_only_status == "prompt_only_ready"
    assert output.report.final_decision == "blocked_by_spend_gate"


def test_smoke_readiness_does_not_call_provider(monkeypatch):
    called = {"provider": False}

    def fail_provider(*_args, **_kwargs):
        called["provider"] = True
        raise AssertionError("provider should not be called by smoke readiness")

    monkeypatch.setattr("app.video_generator.real_smoke_runner.RealSmokeRunner.run_from_variant", fail_provider)
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        run = RecoveryService(db).recover(product_id=product_id, rebuild_plan=True)
        output = ReadinessReportService(db).output(run)

    assert called["provider"] is False
    assert output.report.prompt_only_status == "prompt_only_ready"
    assert output.report.final_decision == "blocked_by_spend_gate"


def test_smoke_readiness_seed_demo_does_not_create_fake_refs():
    reset_db()
    with SessionLocal() as db:
        run = RecoveryService(db).recover(seed_demo=True, rebuild_plan=True)
        output = ReadinessReportService(db).output(run)
        asset_count = db.scalar(select(func.count()).select_from(models.ProductAsset))

    assert output.product_id is not None
    assert output.one_video_render_plan_id is not None
    assert output.prompt_pack_id is not None
    assert asset_count == 0
    assert any(blocker.blocker_type == "missing_refs" for blocker in output.blockers)


def test_smoke_readiness_reports_spend_gate_off(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "false")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway-secret")
    get_settings.cache_clear()
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        run = RecoveryService(db).recover(product_id=product_id, rebuild_plan=True, runway_credits_confirmed=True)
        output = ReadinessReportService(db).output(run)

    assert output.report.generation_mode == "real"
    assert output.report.spend_gate_status["allow_real_spend"] is False
    assert output.report.final_decision == "blocked_by_spend_gate"
    assert any(blocker.blocker_type == "spend_gate_off" for blocker in output.blockers)


def test_smoke_readiness_reports_generation_mode_not_real(monkeypatch):
    monkeypatch.setenv("QVF_GENERATION_MODE", "mock")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-runway-secret")
    get_settings.cache_clear()
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        run = RecoveryService(db).recover(product_id=product_id, rebuild_plan=True, runway_credits_confirmed=True)
        output = ReadinessReportService(db).output(run)

    assert output.report.generation_mode == "mock"
    assert output.report.final_decision == "blocked_by_spend_gate"
    assert any(blocker.blocker_type == "generation_mode_not_real" for blocker in output.blockers)


def test_smoke_readiness_masks_runway_key_value(monkeypatch):
    monkeypatch.setenv("RUNWAYML_API_SECRET", "secret-value-that-must-not-leak")
    get_settings.cache_clear()
    reset_db()
    with SessionLocal() as db:
        run = RecoveryService(db).recover(plan_id=99)
        output = ReadinessReportService(db).output(run)
        payload = output.model_dump(mode="json")

    serialized = json.dumps(payload, ensure_ascii=False)
    assert output.report.runway_key_configured is True
    assert output.report.runway_key_value == "[redacted]"
    assert "secret-value-that-must-not-leak" not in serialized


def test_smoke_readiness_updates_engine_audit():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        run = RecoveryService(db).recover(product_id=product_id, rebuild_plan=True)
        output = ReadinessReportService(db).output(run)

    assert output.engine_audit_run_id is not None
    assert output.control_room_snapshot_id is not None
    assert output.report.engine_audit_latest_score is not None
    assert output.report.control_room_snapshot_id == output.control_room_snapshot_id


def test_smoke_readiness_control_room_section_renders():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        RecoveryService(db).recover(product_id=product_id, rebuild_plan=True)

    response = api.get("/control-room?role=owner")

    assert response.status_code == 200, response.text
    assert "Paid Smoke Readiness" in response.text
    assert "blocked_by_spend_gate" in response.text
    assert "Runway key" in response.text


def test_smoke_readiness_cli_report_latest():
    api = client()
    product_id = create_product(api, title="Bombbar Pro Dubai Mango Kunafa")
    with SessionLocal() as db:
        attach_approved_reference_pair(db, product_id, primary_url="https://example.com/bombbar_wrapper_front.png")
        RecoveryService(db).recover(product_id=product_id, rebuild_plan=True)

    result = subprocess.run(
        [sys.executable, "scripts/smoke_readiness_report.py", "--latest"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "ContentEngine smoke readiness report" in result.stdout
    assert "Decision: blocked_by_spend_gate" in result.stdout
    assert "Runway key configured:" in result.stdout
