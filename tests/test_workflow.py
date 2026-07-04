from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"

from fastapi.testclient import TestClient

from app import models
from app.database import Base, SessionLocal, engine
from app.engine import VideoFactoryEngine
from app.main import app


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def client() -> TestClient:
    reset_db()
    return TestClient(app)


def create_product(api: TestClient, title: str = "Altea Test Bottle", benefits: list[str] | None = None) -> int:
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
            "images_json": [],
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
