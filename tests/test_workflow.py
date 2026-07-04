from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"

import pytest
import httpx
from fastapi.testclient import TestClient

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.asset_storage import ProductAssetStorage
from app.assets.asset_validator import AssetValidator
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.assets.reference_bundle_builder import ProviderReferenceBundleBuilder
from app.assets.types import ProductAssetDescriptor
from app.config import get_settings
from app.creative.creative_spec_builder import CreativeSpecBuilder
from app.creative.creative_spec_validator import CreativeSpecValidator
from app.creative.hook_strategy import HookStrategySelector
from app.creative.types import CreativeSpec
from app.database import Base, SessionLocal, engine
from app.demand.demand_hypothesis_builder import DemandHypothesisBuilder
from app.demand.demand_validator import DemandValidator
from app.demand.types import DemandHypothesis
from app.engine import VideoFactoryEngine
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
from app.intelligence.video_generator import GeneratorVideoService
from app.main import app
from app.providers.openai_llm import OpenAILLMProvider
from app.providers.runway_video import RunwayVideoProvider
from app.services.video_assembly import VideoAssemblyService
from app.variants.creative_variant_builder import CreativeVariantBuilder
from app.variants.first_frame_builder import FirstFrameBuilder
from app.variants.variant_scorer import VariantScorer
from app.variants.variant_selector import VariantSelector
from app.video_generator.generator import VideoGenerator
from app.video_generator.product_identity import ProductIdentityService
from app.video_generator.real_smoke_runner import RealSmokeRunner
from app.video_generator.regeneration import VideoRegenerationService
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
        storage = ProductAssetStorage(db)
        asset = storage.attach_url(
            product_id,
            url=url,
            asset_type="packshot",
            is_primary_reference=True,
        )
        storage.update_asset(asset.id, review_status="approved", is_primary_reference=True)
        bundle = ProviderReferenceBundleBuilder(db).build(product_id, provider="runway")
    return product_id, spec_id, selected_variant_id, bundle.id


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


def test_runway_uses_image_to_video_when_reference_image_is_present(monkeypatch, tmp_path):
    captured: dict = {}
    reference_path = tmp_path / "packshot.png"
    reference_path.write_bytes(b"fake-png-bytes")

    class FakeResponse:
        status_code = 200
        text = "{}"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"id": "runway-image-job-1", "status": "RUNNING"}

    def capture_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr("app.providers.runway_video.httpx.post", capture_post)
    prompt_pack = PromptPackOutput(
        provider="runway",
        aspect_ratio="720:1280",
        duration_seconds=5,
        scene_prompts=[
            PromptSceneOutput(
                scene_number=1,
                duration_seconds=5,
                prompt_text="Keep the exact product packaging visible.",
                negative_prompt="distorted product",
                reference_images=[reference_path.as_posix()],
            )
        ],
    )

    job = RunwayVideoProvider(api_secret="test-key").create_generation(prompt_pack)

    assert captured["url"].endswith("/v1/image_to_video")
    assert captured["json"]["promptImage"].startswith("data:image/png;base64,")
    assert "fake-png-bytes" not in captured["json"]["promptImage"]
    assert captured["json"]["promptText"] == "Keep the exact product packaging visible."
    assert job.provider_job_id == "runway-image-job-1"


def test_runway_reference_image_missing_fails_before_provider_call(monkeypatch, tmp_path):
    called = False

    def capture_post(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("app.providers.runway_video.httpx.post", capture_post)
    prompt_pack = PromptPackOutput(
        provider="runway",
        aspect_ratio="720:1280",
        duration_seconds=5,
        scene_prompts=[
            PromptSceneOutput(
                scene_number=1,
                duration_seconds=5,
                prompt_text="Keep the exact product packaging visible.",
                negative_prompt="distorted product",
                reference_images=[(tmp_path / "missing.png").as_posix()],
            )
        ],
    )

    with pytest.raises(ProviderConfigurationError, match="reference image does not exist"):
        RunwayVideoProvider(api_secret="test-key").create_generation(prompt_pack)
    assert called is False


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
        assert generation_variant.prompt_pack_json["reference_images"] == ["https://example.com/packshot.png"]
        assert generation_variant.prompt_pack_json["provider_reference_bundle"]["reference_asset_ids"]


def test_generation_report_still_scrubs_signed_urls_and_secrets(monkeypatch):
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


def test_product_identity_constraints_added_to_prompt_pack():
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Identity Constraint Variant")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        prompt_pack = variant.prompt_pack_json
        first_scene = prompt_pack["scene_prompts"][0]
        assert prompt_pack["product_identity_spec"]["product_lock_mode"] == "reference_i2v"
        assert "Use the approved primary reference image as the exact product reference." in first_scene["prompt_text"]
        assert "Preserve white label if the approved reference has a white label." in first_scene["prompt_text"]
        assert "Product identity still requires human visual review" in first_scene["prompt_text"]


def test_negative_prompt_blocks_packaging_redesign():
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Negative Prompt Identity Variant")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        negative_prompt = variant.prompt_pack_json["scene_prompts"][0]["negative_prompt"]
        assert "wrong cap color" in negative_prompt
        assert "black cap if reference cap is not black" in negative_prompt
        assert "red label if reference label is white" in negative_prompt
        assert "redesigned packaging" in negative_prompt
        assert "invented label graphics" in negative_prompt


def test_manual_review_can_mark_identity_mismatch(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Manual Identity Mismatch Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            request = VideoRegenerationService(db).request(
                video_job_id=output.video_job_id,
                scene_number=1,
                reason="product_identity_mismatch",
                human_feedback="Generated bottle cap/dropper became black; label became red; keep reference packaging.",
            )
            review = db.get(models.VideoQualityReview, output.quality_review_id)

        assert request.status == "requested"
        assert review.human_visual_status == "fail"
        assert review.requires_regeneration is True
        assert "wrong_cap_color" in review.identity_mismatch_flags_json
        assert "label_mismatch" in review.identity_mismatch_flags_json


def test_regeneration_request_persists_human_feedback(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    feedback = "Generated bottle cap/dropper became black; label became red; keep reference packaging."
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Persist Regeneration Feedback Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            request = VideoRegenerationService(db).request(
                video_job_id=output.video_job_id,
                scene_number=1,
                reason="product_identity_mismatch",
                human_feedback=feedback,
            )

        assert request.human_feedback == feedback
        assert request.identity_corrections_json["feedback"] == feedback
        assert request.identity_corrections_json["identity_mismatch_flags"]


def test_regeneration_prompt_includes_identity_corrections(monkeypatch):
    enable_real_smoke_env(monkeypatch)
    install_fake_runway_provider(monkeypatch)
    feedback = "Generated bottle cap/dropper became black; label became red; keep reference packaging."
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Regeneration Prompt Variant")

        with SessionLocal() as db:
            output = RealSmokeRunner(db).run_from_variant(selected_variant_id, allow_real_spend=True)
            request = VideoRegenerationService(db).request(
                video_job_id=output.video_job_id,
                scene_number=1,
                reason="product_identity_mismatch",
                human_feedback=feedback,
            )
            request = VideoRegenerationService(db).build_prompt_pack(request.id)
            prompt_pack = db.get(models.PromptPack, request.new_prompt_pack_id)

        first_scene = prompt_pack.prompt_pack_json["scene_prompts"][0]
        assert "Human feedback: Generated bottle cap/dropper became black" in first_scene["prompt_text"]
        assert "Identity corrections" in first_scene["prompt_text"]
        assert "wrong cap color" in first_scene["negative_prompt"]
        assert prompt_pack.prompt_pack_json["regeneration_request_id"] == request.id


def test_regeneration_real_run_requires_spend_gates(monkeypatch):
    enable_real_smoke_env(monkeypatch, allow_spend="false")
    install_fake_runway_provider(monkeypatch)
    with client() as api:
        _, _, selected_variant_id, _ = prepare_ready_variant(api, title="Regeneration Spend Gate Variant")

        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")
            video_job = GeneratorVideoService(db).create_video_job_from_prompt_pack(
                variant.prompt_pack_id,
                "runway",
                max_scenes=1,
                full_video=False,
                apply_safety_limits=True,
            )
            variant.video_job_id = video_job.id
            db.commit()
            request = VideoRegenerationService(db).request(
                video_job_id=video_job.id,
                scene_number=1,
                reason="product_identity_mismatch",
                human_feedback="Keep reference packaging.",
            )
            with pytest.raises(ProviderConfigurationError, match="QVF_ALLOW_REAL_SPEND=true"):
                VideoRegenerationService(db).run_real(request.id, explicit_real_run=True)


def test_packshot_overlay_mode_uses_real_asset():
    with client() as api:
        product_id, _, selected_variant_id, _ = prepare_ready_variant(api, title="Packshot Overlay Mode Variant")

        with SessionLocal() as db:
            product = db.get(models.Product, product_id)
            identity = ProductIdentityService(db).get_or_create(product, primary_reference_asset_id=1)
            identity.product_lock_mode = "packshot_overlay"
            db.commit()
            variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        payload = variant.provider_payload_json
        scene = variant.prompt_pack_json["scene_prompts"][0]
        assert payload["product_lock_mode"] == "packshot_overlay"
        assert payload["packshot_overlay_asset"]
        assert "real approved packshot will be composited as an overlay" in scene["prompt_text"]


def test_end_card_packshot_uses_real_asset():
    with client() as api:
        product_id, _, selected_variant_id, _ = prepare_ready_variant(api, title="End Card Packshot Mode Variant")

        with SessionLocal() as db:
            product = db.get(models.Product, product_id)
            identity = ProductIdentityService(db).get_or_create(product, primary_reference_asset_id=1)
            identity.product_lock_mode = "end_card_packshot"
            db.commit()
            variant = VideoGenerator(db).build_prompt_pack_from_variant(selected_variant_id, provider="runway")

        payload = variant.provider_payload_json
        scene = variant.prompt_pack_json["scene_prompts"][0]
        assert payload["product_lock_mode"] == "end_card_packshot"
        assert payload["end_card_packshot_asset"]
        assert "final packshot/end card must use the real approved product asset" in scene["prompt_text"]


def test_single_scene_downloaded_output_not_replaced_by_placeholder(monkeypatch, tmp_path):
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
