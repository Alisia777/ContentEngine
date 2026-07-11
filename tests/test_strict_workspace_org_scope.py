from __future__ import annotations

from collections.abc import Generator
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.database import Base, get_db
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.public_pilot.control_room import PublicPilotControlRoomService
from app.routers import public_pilot


FOREIGN_SKU = "FOREIGN-SKU-DO-NOT-LEAK-987"
FOREIGN_PROVIDER = "FOREIGN_PROVIDER_SECRET_DO_NOT_LEAK"
FOREIGN_VIDEO_ID = 987654
OWNED_VIDEO_ID = 123456


@pytest.fixture()
def strict_cross_org_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    previous_public_mode = os.environ.get("QVF_PUBLIC_PILOT_MODE")
    previous_auth_required = os.environ.get("QVF_AUTH_REQUIRED")
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_AUTH_REQUIRED"] = "false"
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LocalSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    owned_output = tmp_path / "owned-output.mp4"
    foreign_output = tmp_path / "foreign-output.mp4"
    owned_output.write_bytes(b"owned-video")
    foreign_output.write_bytes(b"foreign-video")
    with LocalSession() as db:
        owned_org = models.Organization(name="Owned Org", slug="owned-org")
        foreign_org = models.Organization(name="Foreign Org", slug="foreign-org")
        owner = models.UserProfile(
            supabase_user_id="strict-owner",
            email="strict-owner@example.test",
            display_name="Strict Owner",
        )
        foreign_user = models.UserProfile(
            supabase_user_id="foreign-owner",
            email="foreign-owner@example.test",
            display_name="Foreign Owner",
        )
        db.add_all([owned_org, foreign_org, owner, foreign_user])
        db.flush()
        membership = models.Membership(
            organization_id=owned_org.id,
            user_profile_id=owner.id,
            role="owner",
            status="active",
        )
        db.add_all(
            [
                membership,
                models.Membership(
                    organization_id=foreign_org.id,
                    user_profile_id=foreign_user.id,
                    role="owner",
                    status="active",
                ),
            ]
        )
        owned_product = models.Product(
            organization_id=owned_org.id,
            sku="OWNED-SKU-VISIBLE",
            brand="Owned Brand",
            title="Owned Product",
        )
        foreign_product = models.Product(
            organization_id=foreign_org.id,
            sku=FOREIGN_SKU,
            brand="Foreign Brand",
            title="Foreign Product",
        )
        db.add_all([owned_product, foreign_product])
        db.flush()
        owned_draft = models.ProductUGCRecipeDraft(
            product_id=owned_product.id,
            sku=owned_product.sku,
            status="completed",
            character_image_path=(tmp_path / "owned-character.png").as_posix(),
            character_image_filename="owned-character.png",
            likeness_consent=True,
            exact_variant_confirmed=True,
            product_info="Owned exact product",
            user_concept="Owned concept",
            local_output_paths_json=[owned_output.as_posix()],
            human_review_status="needs_human_review",
            publishing_readiness="blocked",
        )
        foreign_draft = models.ProductUGCRecipeDraft(
            product_id=foreign_product.id,
            sku=FOREIGN_SKU,
            status="provider_failed",
            character_image_path=(tmp_path / "foreign-character.png").as_posix(),
            character_image_filename="foreign-character.png",
            likeness_consent=True,
            exact_variant_confirmed=True,
            product_info=FOREIGN_PROVIDER,
            user_concept="Foreign concept",
            blockers_json=[FOREIGN_PROVIDER],
            provider_task_id=FOREIGN_PROVIDER,
            provider_status=FOREIGN_PROVIDER,
            local_output_paths_json=[foreign_output.as_posix()],
            human_review_status="needs_regeneration",
            publishing_readiness="blocked",
        )
        db.add_all([owned_draft, foreign_draft])
        db.flush()
        owned_video = models.VideoJob(
            id=OWNED_VIDEO_ID,
            script_variant_id=1,
            organization_id=owned_org.id,
            created_by_user_profile_id=owner.id,
            product_id=owned_product.id,
            source_product_ugc_draft_id=owned_draft.id,
            provider="runway-owned",
            status="generated",
            output_video_path=owned_output.as_posix(),
        )
        foreign_video = models.VideoJob(
            id=FOREIGN_VIDEO_ID,
            script_variant_id=2,
            organization_id=foreign_org.id,
            created_by_user_profile_id=foreign_user.id,
            product_id=foreign_product.id,
            source_product_ugc_draft_id=foreign_draft.id,
            provider=FOREIGN_PROVIDER,
            status="generated",
            output_video_path=foreign_output.as_posix(),
        )
        db.add_all([owned_video, foreign_video])
        db.flush()
        owned_brief = models.AIProductionBrief(
            product_id=owned_product.id,
            sku=owned_product.sku,
            status="approved",
        )
        foreign_brief = models.AIProductionBrief(
            product_id=foreign_product.id,
            sku=FOREIGN_SKU,
            status="approved",
        )
        db.add_all([owned_brief, foreign_brief])
        db.flush()
        foreign_acceptance = models.VideoOutputAcceptance(
            id=876543,
            video_job_id=foreign_video.id,
            ai_production_brief_id=foreign_brief.id,
            status="needs_regeneration",
            reviewer_notes=FOREIGN_PROVIDER,
        )
        db.add(foreign_acceptance)
        db.flush()
        owned_cycle = models.ContentCycle(
            organization_id=owned_org.id,
            created_by_user_profile_id=owner.id,
            product_id=owned_product.id,
            product_ugc_recipe_draft_id=owned_draft.id,
            video_job_id=owned_video.id,
            ai_production_brief_id=owned_brief.id,
            idempotency_key="owned-cycle",
            status="needs_output_acceptance",
        )
        foreign_cycle = models.ContentCycle(
            organization_id=foreign_org.id,
            created_by_user_profile_id=foreign_user.id,
            product_id=foreign_product.id,
            product_ugc_recipe_draft_id=foreign_draft.id,
            video_job_id=foreign_video.id,
            ai_production_brief_id=foreign_brief.id,
            idempotency_key="foreign-cycle",
            status="needs_output_acceptance",
        )
        db.add_all([owned_cycle, foreign_cycle])
        db.flush()
        audit_run = models.EngineAuditRun(
            status="weak",
            scope_type="global",
            total_score=1,
            scores_json=[{"provider": FOREIGN_PROVIDER}],
            blockers_json=[FOREIGN_PROVIDER],
        )
        db.add(audit_run)
        db.flush()
        legacy_snapshot = models.ControlRoomSnapshot(
            scope_type="global",
            role="owner",
            overall_status="needs_review",
            engine_audit_run_id=audit_run.id,
            summary_json={"sku": FOREIGN_SKU, "provider": FOREIGN_PROVIDER},
            scorecard_json={"video_job_id": FOREIGN_VIDEO_ID},
            review_queue_json=[
                {
                    "label": FOREIGN_PROVIDER,
                    "status": "needs_review",
                    "target_module": "output_acceptance",
                    "target_url": f"/output-acceptance?video_job_id={FOREIGN_VIDEO_ID}",
                    "payload": {
                        "output_acceptance_id": foreign_acceptance.id,
                        "video_job_id": FOREIGN_VIDEO_ID,
                        "sku": FOREIGN_SKU,
                    },
                }
            ],
        )
        plan = models.OneVideoRenderPlan(
            product_id=foreign_product.id,
            sku=FOREIGN_SKU,
            provider=FOREIGN_PROVIDER,
            status="plan_ready",
        )
        db.add_all([legacy_snapshot, plan])
        db.flush()
        db.add(
            models.SmokeReadinessRun(
                status="blocked",
                product_id=foreign_product.id,
                sku=FOREIGN_SKU,
                one_video_render_plan_id=plan.id,
                engine_audit_run_id=audit_run.id,
                control_room_snapshot_id=legacy_snapshot.id,
                blockers_json=[{"blocker_type": FOREIGN_PROVIDER}],
                report_json={"final_decision": FOREIGN_PROVIDER},
            )
        )
        db.add_all(
            [
                models.AuditLog(
                    organization_id=owned_org.id,
                    user_profile_id=owner.id,
                    action="owned-audit",
                    status="allowed",
                ),
                models.AuditLog(
                    organization_id=foreign_org.id,
                    user_profile_id=foreign_user.id,
                    action=FOREIGN_PROVIDER,
                    status="denied",
                ),
                models.AuditLog(
                    organization_id=foreign_org.id,
                    user_profile_id=foreign_user.id,
                    action=FOREIGN_PROVIDER + "-2",
                    status="denied",
                ),
            ]
        )
        db.commit()
        public_user = PublicPilotUser(
            profile=owner,
            organization=owned_org,
            membership=membership,
        )

    def local_db() -> Generator[Session, None, None]:
        with LocalSession() as db:
            yield db

    api = FastAPI()
    api.mount("/static", StaticFiles(directory="app/static"), name="static")
    api.include_router(public_pilot.router)
    api.dependency_overrides[get_db] = local_db
    api.dependency_overrides[get_current_public_user] = lambda: public_user
    monkeypatch.setattr(public_pilot, "_run_product_ugc_background", lambda *_args: None)
    yield TestClient(api), LocalSession, public_user

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if previous_public_mode is None:
        os.environ.pop("QVF_PUBLIC_PILOT_MODE", None)
    else:
        os.environ["QVF_PUBLIC_PILOT_MODE"] = previous_public_mode
    if previous_auth_required is None:
        os.environ.pop("QVF_AUTH_REQUIRED", None)
    else:
        os.environ["QVF_AUTH_REQUIRED"] = previous_auth_required
    get_settings.cache_clear()


def _assert_foreign_state_absent(page: str) -> None:
    assert FOREIGN_SKU not in page
    assert FOREIGN_PROVIDER not in page
    assert str(FOREIGN_VIDEO_ID) not in page
    assert "/output-acceptance" not in page


def test_strict_control_room_uses_only_owned_canonical_state_and_scoped_audit(
    strict_cross_org_app,
):
    client, LocalSession, public_user = strict_cross_org_app

    response = client.get("/control-room")

    assert response.status_code == 200
    _assert_foreign_state_absent(response.text)
    assert "OWNED-SKU-VISIBLE" in response.text
    assert str(OWNED_VIDEO_ID) in response.text
    assert 'href="/workbench?tab=video-quality"' in response.text

    with LocalSession() as db:
        context = PublicPilotControlRoomService(db).context(public_user)
    audit_metric = next(
        item for item in context["metrics"] if item["label"] == "Audit events"
    )
    assert audit_metric["value"] == "1"
    assert audit_metric["detail"] == "0 denied"

    qa = client.get("/workbench?tab=video-quality")
    assert qa.status_code == 200


def test_strict_workbench_excludes_foreign_legacy_review_and_uses_safe_qa_link(
    strict_cross_org_app,
):
    client, _LocalSession, _public_user = strict_cross_org_app

    response = client.get("/workbench?tab=video-quality")

    assert response.status_code == 200
    _assert_foreign_state_absent(response.text)
    assert "OWNED-SKU-VISIBLE" in response.text
    assert str(OWNED_VIDEO_ID) in response.text
    assert 'href="/workbench?tab=video-quality"' in response.text


def test_auth_required_alone_uses_the_same_fail_closed_org_scope(
    strict_cross_org_app,
):
    client, _LocalSession, _public_user = strict_cross_org_app
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "false"
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    get_settings.cache_clear()

    for path in ("/control-room", "/workbench?tab=video-quality"):
        response = client.get(path)
        assert response.status_code == 200
        _assert_foreign_state_absent(response.text)
        assert "OWNED-SKU-VISIBLE" in response.text
        assert 'href="/workbench?tab=video-quality"' in response.text
