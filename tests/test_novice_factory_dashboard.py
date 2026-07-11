from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.interface_productization.factory_dashboard_service import FactoryDashboardService
from app.main import app
from app.product_telemetry import ProductTelemetryService


@pytest.fixture(autouse=True)
def reset_factory_dashboard_db():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


def test_control_room_presents_all_nine_novice_blocks_and_real_north_star():
    response = TestClient(app).get("/control-room")
    assert response.status_code == 200
    for label in [
        "Старт и интерфейс",
        "Генерация видео",
        "Качество",
        "Воронка",
        "Данные из сетей",
        "Оплата и расходы",
        "Артикулы Wildberries",
        "Аналитика",
        "Обучение",
    ]:
        assert label in response.text
    assert "Измеримые контент-циклы" in response.text
    assert "Недоступные функции не маскируются демонстрационными данными" in response.text
    assert "Fake provider metrics" not in response.text


def test_workbench_exposes_real_actions_for_each_factory_block():
    client = TestClient(app)
    expected = {
        "product": "Начать с товара",
        "video": "Создать новый ролик",
        "video-quality": "Оценка движка — только предварительный сигнал",
        "funnel": "Внести или проверить метрики",
        "sources": "Автоматические коннекторы соцсетей ещё не считаются подключёнными",
        "payments": "Деньги не переводятся этой системой",
        "wb": "не угадывает артикулы",
        "analytics": "Главный показатель",
        "people": "Короткие уроки и мини-тесты",
    }
    for tab, copy in expected.items():
        response = client.get(f"/workbench?tab={tab}")
        assert response.status_code == 200
        assert copy in response.text


def test_public_mode_uses_factory_as_root(monkeypatch):
    monkeypatch.setenv("QVF_PUBLIC_PILOT_MODE", "true")
    get_settings.cache_clear()
    response = TestClient(app).get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/control-room"


def test_public_shell_loads_product_telemetry_and_mobile_rules():
    response = TestClient(app).get("/control-room")
    assert response.status_code == 200
    assert "/static/public_pilot/product_telemetry.js" in response.text
    css = Path("app/static/public_pilot/public_pilot.css").read_text(encoding="utf-8")
    assert ".public-module-grid" in css
    assert "grid-template-columns: 1fr" in css
    assert ":focus-visible" in css


def test_factory_dashboard_json_is_scoped_and_machine_readable():
    response = TestClient(app).get("/api/factory-dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 2
    assert payload["north_star"]["label"] == "Измеримые контент-циклы"
    assert len(payload["modules"]) == 9
    assert payload["learning"]["total_steps"] == 7
    assert payload["data_quality"]["legacy_global_workspaces_enabled"] is False
    assert "generation_queue" in payload
    assert "quality_evidence" in payload
    assert payload["customer_billing"]["external_charges_enabled"] is False
    assert "email" not in response.text


def test_selecting_product_records_one_server_milestone_not_page_reloads():
    with SessionLocal() as db:
        product = models.Product(
            sku="WB-OWN-1001",
            brand="Demo",
            title="Own Wildberries product",
            attributes_json={},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        product_id = product.id

    client = TestClient(app)
    assert client.get(f"/mvp-launch?product_id={product_id}").status_code == 200
    assert client.get(f"/mvp-launch?product_id={product_id}").status_code == 200

    with SessionLocal() as db:
        count = db.scalar(
            select(func.count())
            .select_from(models.FactoryEvent)
            .where(models.FactoryEvent.event_name == "product_selected")
        )
        event = db.scalar(select(models.FactoryEvent).where(models.FactoryEvent.event_name == "product_selected"))
        assert count == 1
        assert event.source == "server"
        assert event.product_id == product_id


def test_public_product_creation_is_scoped_and_emits_server_event(monkeypatch):
    monkeypatch.setenv("QVF_PUBLIC_PILOT_MODE", "true")
    get_settings.cache_clear()
    response = TestClient(app).post(
        "/mvp-launch/products/create",
        data={
            "sku": "OWN-WB-NEW-1",
            "brand": "Own Brand",
            "title": "New scoped product",
            "marketplace": "wildberries",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with SessionLocal() as db:
        product = db.scalar(select(models.Product).where(models.Product.sku == "OWN-WB-NEW-1"))
        event = db.scalar(select(models.FactoryEvent).where(models.FactoryEvent.event_name == "product_created"))
        assert product.organization_id is not None
        assert event.product_id == product.id
        assert event.organization_id == product.organization_id
        assert event.source == "server"


def test_legacy_product_requires_explicit_owner_claim_in_public_mode(monkeypatch):
    with SessionLocal() as db:
        legacy = models.Product(sku="LEGACY-UNSCOPED-1", brand="Legacy", title="Legacy product")
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        legacy_id = legacy.id

    monkeypatch.setenv("QVF_PUBLIC_PILOT_MODE", "true")
    get_settings.cache_clear()
    client = TestClient(app)
    page = client.get("/mvp-launch")
    assert page.status_code == 200
    assert "Ранее созданные товары без владельца" in page.text
    claim = client.post(
        f"/mvp-launch/products/{legacy_id}/claim",
        data={"confirm_ownership": "true"},
        follow_redirects=False,
    )
    assert claim.status_code == 303
    with SessionLocal() as db:
        product = db.get(models.Product, legacy_id)
        audit = db.scalar(select(models.AuditLog).where(models.AuditLog.action == "claim_legacy_product"))
        assert product.organization_id is not None
        assert audit.entity_id == str(legacy_id)


def test_factory_dashboard_metrics_and_journey_are_organization_scoped():
    with SessionLocal() as db:
        organizations = [
            models.Organization(name="First factory", slug="first-factory"),
            models.Organization(name="Second factory", slug="second-factory"),
        ]
        users = [
            models.UserProfile(supabase_user_id="factory-user-1", email="one@example.test"),
            models.UserProfile(supabase_user_id="factory-user-2", email="two@example.test"),
        ]
        db.add_all([*organizations, *users])
        db.flush()
        products = [
            models.Product(
                organization_id=organizations[0].id,
                sku="ORG-ONE-SKU",
                brand="First",
                title="First product",
            ),
            models.Product(
                organization_id=organizations[1].id,
                sku="ORG-TWO-SKU",
                brand="Second",
                title="Second product",
            ),
        ]
        db.add_all(products)
        db.commit()

        for index in range(2):
            ProductTelemetryService(db).record_event(
                event_name="product_created",
                organization_id=organizations[index].id,
                user_profile_id=users[index].id,
                role="owner",
                idempotency_key=f"org-product-created-{index}",
                product_id=products[index].id,
            )

        snapshot = FactoryDashboardService(db).snapshot(
            user_profile_id=users[0].id,
            organization_id=organizations[0].id,
        )

    assert snapshot["metrics"]["products"] == 1
    assert snapshot["metrics"]["events_7d"] == 1
    assert snapshot["metrics"]["active_users_7d"] == 1
    product_step = next(step for step in snapshot["journey_funnel"] if step["event_name"] == "product_created")
    assert product_step["value"] == 1


def test_dashboard_does_not_count_legacy_unbound_approval_as_verified_quality():
    with SessionLocal() as db:
        organization = models.Organization(name="Evidence factory", slug="evidence-factory")
        db.add(organization)
        db.flush()
        product = models.Product(
            organization_id=organization.id,
            sku="EVIDENCE-1",
            brand="Evidence",
            title="Evidence product",
        )
        template = models.CreativeTemplate(name="Evidence dashboard template")
        brand_guide = models.BrandGuide(brand="Evidence")
        db.add_all([product, template, brand_guide])
        db.flush()
        script_job = models.ScriptJob(
            product_id=product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
            status="ready",
        )
        db.add(script_job)
        db.flush()
        script_variant = models.ScriptVariant(
            script_job_id=script_job.id,
            variant_number=1,
            full_script_json={"text": "Legacy output"},
            status="script_approved",
        )
        db.add(script_variant)
        db.flush()
        video_job = models.VideoJob(
            script_variant_id=script_variant.id,
            organization_id=organization.id,
            product_id=product.id,
            provider="runway",
            status="video_generated",
            output_video_path="test_media/legacy.mp4",
        )
        brief = models.AIProductionBrief(
            product_id=product.id,
            sku=product.sku,
            status="ready_for_output_review",
            one_sentence_thesis="Legacy brief",
            viewer_takeaway="Legacy takeaway",
            cta="Open",
        )
        db.add_all([video_job, brief])
        db.flush()
        db.add(
            models.VideoOutputAcceptance(
                video_job_id=video_job.id,
                ai_production_brief_id=brief.id,
                status="approved",
                publishing_readiness="ready_for_package",
                score=100,
            )
        )
        db.commit()

        snapshot = FactoryDashboardService(db).snapshot(
            organization_id=organization.id
        )

    assert snapshot["metrics"]["approved_videos"] == 0
    assert snapshot["metrics"]["reviews_waiting"] == 0
    quality = next(item for item in snapshot["modules"] if item["key"] == "video-quality")
    assert quality["status"] == "not_started"


def test_old_generation_failure_does_not_block_newer_success_for_same_product():
    with SessionLocal() as db:
        organization = models.Organization(name="Queue factory", slug="queue-factory")
        profile = models.UserProfile(
            supabase_user_id="queue-owner",
            email="queue-owner@example.test",
            is_active=True,
        )
        db.add_all([organization, profile])
        db.flush()
        product = models.Product(
            organization_id=organization.id,
            sku="QUEUE-1",
            brand="Queue",
            title="Queue product",
        )
        db.add(product)
        db.flush()
        db.add(
            models.Membership(
                organization=organization,
                user_profile=profile,
                role="owner",
                status="active",
            )
        )
        drafts = []
        for index, status in enumerate(("provider_failed", "approved"), start=1):
            draft = models.ProductUGCRecipeDraft(
                product_id=product.id,
                sku=product.sku,
                variant_key="one",
                status=status,
                character_image_path=f"test_media/creator-{index}.png",
                character_image_filename=f"creator-{index}.png",
                product_info="Exact product information",
                user_concept="Exact product demonstration",
                human_review_status="approved",
            )
            db.add(draft)
            db.flush()
            drafts.append(draft)
            db.add(
                models.ProductUGCGenerationJob(
                    draft_id=draft.id,
                    organization_id=organization.id,
                    requested_by_user_profile_id=profile.id,
                    idempotency_key=f"queue-current-{index}",
                    status="failed_terminal" if index == 1 else "succeeded",
                    provider_task_id=f"provider-task-{index}",
                )
            )
        db.commit()

        snapshot = FactoryDashboardService(db).snapshot(
            user_profile_id=profile.id,
            organization_id=organization.id,
        )

    assert snapshot["metrics"]["generation_queue_failed"] == 1
    assert snapshot["metrics"]["generation_queue_current_failed"] == 0
    video = next(item for item in snapshot["modules"] if item["key"] == "video")
    assert video["status"] == "ready"


def test_public_learning_path_requires_a_real_quiz_pass_before_certifying():
    client = TestClient(app)
    page = client.get("/workbench?tab=people&module=contentengine_overview")
    assert page.status_code == 200
    assert "Путь одного ролика" in page.text

    failed = client.post(
        "/control-room/training/contentengine_overview/submit",
        data={},
        follow_redirects=False,
    )
    assert failed.status_code == 303
    assert "training_result=failed" in failed.headers["location"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.TrainingCertification)) == 0
        module = db.scalar(
            select(models.TrainingModule).where(models.TrainingModule.code == "contentengine_overview")
        )
        question = db.scalar(
            select(models.TrainingQuestion).where(models.TrainingQuestion.module_id == module.id)
        )
        correct = question.correct_answer_json[0]

    passed = client.post(
        "/control-room/training/contentengine_overview/submit",
        data={f"answer_{question.id}": correct},
        follow_redirects=False,
    )
    assert passed.status_code == 303
    assert "training_result=passed" in passed.headers["location"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(models.TrainingCertification)) == 1


def test_owner_can_add_and_explicitly_verify_own_wb_listing_from_workbench(monkeypatch):
    monkeypatch.setenv("QVF_PUBLIC_PILOT_MODE", "true")
    get_settings.cache_clear()
    client = TestClient(app)
    created_product = client.post(
        "/mvp-launch/products/create",
        data={"sku": "WB-UI-OWN-1", "brand": "Own", "title": "Owned WB card"},
        follow_redirects=False,
    )
    assert created_product.status_code == 303
    with SessionLocal() as db:
        product = db.scalar(select(models.Product).where(models.Product.sku == "WB-UI-OWN-1"))
        product_id = product.id

    created_listing = client.post(
        "/workbench/wb/listings/create",
        data={
            "product_id": product_id,
            "seller_account_ref": "main-cabinet",
            "nm_id": "700001",
            "listing_url": "https://www.wildberries.ru/catalog/700001/detail.aspx",
            "confirm_owned_card": "true",
        },
        follow_redirects=False,
    )
    assert created_listing.status_code == 303
    assert "wb_notice=listing_created" in created_listing.headers["location"]
    with SessionLocal() as db:
        listing = db.scalar(select(models.MarketplaceListing).where(models.MarketplaceListing.nm_id == "700001"))
        assert listing.status == "draft"
        listing_id = listing.id

    verified = client.post(
        f"/workbench/wb/listings/{listing_id}/verify",
        data={"confirm_identifiers": "true"},
        follow_redirects=False,
    )
    assert verified.status_code == 303
    with SessionLocal() as db:
        assert db.get(models.MarketplaceListing, listing_id).status == "verified"
