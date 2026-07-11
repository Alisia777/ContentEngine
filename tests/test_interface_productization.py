from __future__ import annotations

import inspect
import os

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"
os.environ["QVF_AUTH_REQUIRED"] = "false"
os.environ["QVF_GENERATION_MODE"] = "mock"
os.environ["QVF_ALLOW_REAL_SPEND"] = "false"

import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.interface_productization import MVPLaunchWizardService, MVPWorkspaceService
from app.main import app


@pytest.fixture(autouse=True)
def reset_interface_db():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


def client() -> TestClient:
    return TestClient(app)


def create_product() -> int:
    with SessionLocal() as db:
        product = models.Product(
            sku="BOMBBAR-PRO-DUBAI-MANGO-KUNAFA",
            brand="Bombbar",
            title="Bombbar PRO DUBAI Mango & Kunafa",
            description="Chocolate-coated bar with a light filling and yellow mango center.",
            category="Sports nutrition snack",
            attributes_json={"flavor": "Mango & Kunafa", "variant": "mango_yellow_center"},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product.id


def test_workbench_renders_single_product_interface():
    response = client().get("/workbench")
    assert response.status_code == 200
    assert "Рабочая область" in response.text
    assert "Готовность товара" in response.text
    assert "Продолжить запуск MVP" in response.text
    assert "One-video QA" not in response.text
    assert "Metrics intake" not in response.text


def test_mvp_launch_wizard_shows_asset_prompt_smoke_review_steps():
    response = client().post("/api/mvp-launch/start", json={})
    assert response.status_code == 200
    payload = response.json()
    assert [step["key"] for step in payload["steps"]] == [
        "select_product",
        "check_assets",
        "build_prompt_only",
        "check_smoke_readiness",
        "run_or_block_paid_smoke",
        "review_output",
        "decide_next_action",
    ]
    page = client().get(f"/mvp-launch?run_id={payload['id']}")
    assert page.status_code == 200
    assert "Мастер не выполняет платный provider call" in page.text


def test_control_room_links_to_workbench_and_mvp_launch():
    response = client().get("/control-room")
    assert response.status_code == 200
    assert 'href="/workbench"' in response.text
    assert 'href="/mvp-launch"' in response.text
    assert response.text.count("Следующее действие") == 1


def test_workbench_uses_engine_audit_and_control_room_snapshots():
    response = client().get("/api/workbench/snapshot")
    assert response.status_code == 200
    payload = response.json()
    assert payload["control_room_snapshot_id"]
    assert payload["context"]["technical"]["engine_audit_run_id"]
    with SessionLocal() as db:
        record = db.get(models.MVPWorkspaceSnapshot, payload["id"])
        assert record.control_room_snapshot_id == payload["control_room_snapshot_id"]


def test_interface_productization_does_not_duplicate_business_logic():
    workspace_source = inspect.getsource(MVPWorkspaceService)
    launch_source = inspect.getsource(MVPLaunchWizardService)
    assert "ControlRoomSnapshotService" in workspace_source
    assert "ReadinessReportService" in workspace_source
    assert "OneVideoAcceptanceService" in launch_source
    assert "RecoveryService" in launch_source
    assert "RealSmokeRunner" not in launch_source
    assert "RunwayVideoProvider" not in launch_source


def test_premium_shell_used_by_control_room_workbench_and_launch():
    api = client()
    for path in ["/control-room", "/workbench", "/mvp-launch"]:
        response = api.get(path)
        assert response.status_code == 200
        assert "altea-bg" in response.text
        assert "/static/altea_motion/altea_motion.css" in response.text
        assert "CONTENT ENGINE" in response.text


def test_launch_wizard_never_calls_paid_provider(monkeypatch):
    product_id = create_product()
    with SessionLocal() as db:
        service = MVPLaunchWizardService(db)
        run = service.start(product_id=product_id)
        run.current_step = "run_or_block_paid_smoke"
        run.status = "in_progress"
        db.commit()

        def fail_if_called(*args, **kwargs):
            raise AssertionError("paid provider must not be called by MVP launch wizard")

        monkeypatch.setattr("app.video_generator.real_smoke_runner.RealSmokeRunner.run_from_variant", fail_if_called)
        advanced = service.advance(run.id)
        assert advanced.status == "spend_gated"
        assert advanced.context_json["provider_calls"] == 0
        assert advanced.context_json["paid_provider_called"] is False


def test_workbench_surfaces_exact_product_ugc_provider_failure():
    product_id = create_product()
    with SessionLocal() as db:
        draft = models.ProductUGCRecipeDraft(
            product_id=product_id,
            sku="BOMBBAR-PRO-DUBAI-MANGO-KUNAFA",
            variant_key="mango-kunafa",
            status="provider_failed",
            character_image_path="test_media/creator.png",
            character_image_filename="creator.png",
            product_info="Exact product info",
            user_concept="Creator presents the exact product.",
            creative_inputs_json={
                "provider_failure": {
                    "code": "INPUT_PREPROCESSING.SAFETY.THIRD_PARTY",
                    "message": "Blocked by provider moderation.",
                    "retry_allowed": False,
                }
            },
            provider_task_id="failed-task-id",
            provider_status="FAILED",
            estimated_credits=588,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        draft_id = draft.id

    response = client().get("/workbench?tab=video-quality")
    assert response.status_code == 200
    assert "INPUT_PREPROCESSING.SAFETY.THIRD_PARTY" in response.text
    assert "failed-task-id" in response.text
    assert f'/mvp-launch?product_id={product_id}&amp;recipe_draft_id={draft_id}' in response.text
    assert "Повторный paid run не выполняется автоматически" in response.text
