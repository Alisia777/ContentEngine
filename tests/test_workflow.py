from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"

import pytest
import httpx
from fastapi.testclient import TestClient

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.asset_validator import AssetValidator
from app.assets.types import ProductAssetDescriptor
from app.config import get_settings
from app.creative.creative_spec_builder import CreativeSpecBuilder
from app.creative.creative_spec_validator import CreativeSpecValidator
from app.creative.hook_strategy import HookStrategySelector
from app.creative.types import CreativeSpec
from app.database import Base, SessionLocal, engine
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
    ScriptBriefOutput,
)
from app.intelligence.validators import validate_script_claim_refs
from app.main import app
from app.providers.openai_llm import OpenAILLMProvider
from app.providers.runway_video import RunwayVideoProvider
from app.variants.creative_variant_builder import CreativeVariantBuilder
from app.variants.first_frame_builder import FirstFrameBuilder
from app.variants.variant_scorer import VariantScorer
from app.variants.variant_selector import VariantSelector
from app.video_generator.generator import VideoGenerator


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
