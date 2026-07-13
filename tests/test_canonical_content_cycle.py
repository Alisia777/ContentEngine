from __future__ import annotations

import os
import hashlib
import uuid
from datetime import date
from pathlib import Path

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_content_cycles.db")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, inspect, select, text

from app import models
from app.content_cycles import (
    ContentCycleConflictError,
    ContentCycleOwnershipError,
    ContentCycleService,
    ContentCycleStateError,
)
from app.database import Base, SessionLocal, _ensure_sqlite_schema, engine
from app.interface_productization import FactoryDashboardService
from app.output_acceptance import AcceptanceReviewService, OutputQualityChecker
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
import app.routers.public_pilot as public_pilot_module
from app.routers.public_pilot import router as public_pilot_router
from app.visual_evidence import VisualEvidenceService


class _PackagingOCR:
    name = "test_packaging_ocr"
    available = True

    def extract_text(self, _image_path, *, language: str, timeout_seconds: float) -> str:
        del language, timeout_seconds
        return "CYCLE BRAND"


@pytest.fixture(autouse=True)
def reset_content_cycle_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def make_actor(db, *, slug: str = "cycle-org") -> tuple[models.Organization, models.UserProfile]:
    organization = models.Organization(name=slug.title(), slug=slug)
    profile = models.UserProfile(
        supabase_user_id=f"test:{slug}",
        email=f"owner@{slug}.test",
        display_name=f"{slug.title()} Owner",
    )
    db.add_all([organization, profile])
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="owner",
            status="active",
        )
    )
    db.commit()
    return organization, profile


def make_product(db, organization: models.Organization, *, sku: str = "CYCLE-SKU-1") -> models.Product:
    product = models.Product(
        organization_id=organization.id,
        sku=sku,
        brand="Cycle Brand",
        title="Traceable Product",
        description="Exact product description",
        restrictions_json=["no unsupported claims"],
        product_url="https://shop.example.test/products/traceable",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def make_approved_draft(
    db,
    product: models.Product,
    tmp_path: Path,
    *,
    filename: str = "real-product-ugc.mp4",
) -> models.ProductUGCRecipeDraft:
    character = tmp_path / "character.png"
    character.write_bytes(b"character-image")
    output = tmp_path / filename
    output.write_bytes(b"non-empty-provider-video")
    reference = tmp_path / f"reference-{filename}.png"
    Image.new("RGB", (720, 1280), color=(255, 255, 255)).save(reference)
    kit = models.ProductAssetKit(product_id=product.id, status="ready")
    db.add(kit)
    db.flush()
    primary_asset = models.ProductAsset(
        product_id=product.id,
        asset_kit_id=kit.id,
        source_ref=reference.as_posix(),
        source_type="local",
        asset_type="front_packshot",
        filename=reference.name,
        exists=True,
        is_primary_reference=True,
        review_status="approved",
        metadata_json={"required_packaging_tokens": ["CYCLE", "BRAND"]},
    )
    db.add(primary_asset)
    db.flush()
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        sku=product.sku,
        variant_key="red-500ml",
        status="approved",
        platform="Instagram Reels",
        character_image_path=character.as_posix(),
        character_image_filename=character.name,
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_asset_ids_json=[primary_asset.id],
        primary_product_asset_id=primary_asset.id,
        product_info="Exact reviewed product information",
        user_concept="Creator demonstrates the exact product and proof moment.",
        creative_inputs_json={"required_packaging_tokens": ["CYCLE", "BRAND"]},
        duration_seconds=8,
        ratio="720:1280",
        provider_task_id="runway-real-task-1",
        provider_status="SUCCEEDED",
        local_output_paths_json=[output.as_posix()],
        human_review_status="approved",
        publishing_readiness="ready_for_package",
        human_review_notes="Human verified identity, packaging, action, and consent.",
        blockers_json=[],
        warnings_json=[],
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def start_cycle(db, organization, profile, draft, *, key: str = "cycle-request-1") -> models.ContentCycle:
    return ContentCycleService(db).start_from_product_ugc(
        organization_id=organization.id,
        actor_user_profile_id=profile.id,
        product_ugc_recipe_draft_id=draft.id,
        idempotency_key=key,
    )


def approve_cycle_output(
    db,
    cycle: models.ContentCycle,
    tmp_path: Path,
    *,
    decision: str = "approve",
) -> models.VideoOutputAcceptance:
    frame = tmp_path / f"frame-{cycle.id}-1.png"
    second_frame = tmp_path / f"frame-{cycle.id}-2.png"
    contact_sheet = tmp_path / f"contact-{cycle.id}.png"
    Image.new("RGB", (720, 1280), color=(220, 42, 54)).save(frame)
    Image.new("RGB", (720, 1280), color=(36, 92, 220)).save(second_frame)
    Image.new("RGB", (1440, 1280), color=(245, 245, 245)).save(contact_sheet)
    source = Path(cycle.video_job.output_video_path)
    db.add(
        models.FrameExtractionResult(
            video_job_id=cycle.video_job_id,
            status="created",
            frame_paths_json=[frame.as_posix(), second_frame.as_posix()],
            contact_sheet_path=contact_sheet.as_posix(),
            duration_seconds=8,
            fps=24,
            warnings_json=[],
            extraction_key=f"test-cycle-{cycle.id}-{uuid.uuid4().hex}",
            source_video_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_video_size_bytes=source.stat().st_size,
        )
    )
    db.commit()
    return AcceptanceReviewService(
        db,
        quality_checker=OutputQualityChecker(
            VisualEvidenceService(ocr_backend=_PackagingOCR())
        ),
    ).review(
        video_job_id=cycle.video_job_id,
        ai_production_brief_id=cycle.ai_production_brief_id,
        decision=decision,
        product_identity_status="pass",
        packaging_status="pass",
        geometry_status="pass",
        blogger_authenticity_status="pass",
        scene_match_status="pass",
        proof_moment_status="pass",
        cta_status="pass",
        reviewer_notes="Human reviewed decoded frames and approved the exact product output.",
    )


def make_destination(db, organization: models.Organization, *, name: str = "Owned manual Reels") -> models.PublishingDestination:
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="Cycle Brand",
        platform="Instagram Reels",
        name=name,
        status="active",
        posting_mode="manual",
        auth_status="manual_only",
        allowed_formats_json=["vertical_video"],
        daily_limit=5,
        weekly_limit=20,
    )
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return destination


def test_product_ugc_materializes_explicit_owned_video_job_and_is_idempotent(tmp_path: Path):
    with SessionLocal() as db:
        organization, profile = make_actor(db)
        product = make_product(db, organization)
        draft = make_approved_draft(db, product, tmp_path)

        cycle = start_cycle(db, organization, profile, draft)
        repeated = start_cycle(db, organization, profile, draft)
        trace = ContentCycleService(db).get_trace(
            organization_id=organization.id,
            actor_user_profile_id=profile.id,
            content_cycle_id=cycle.id,
        )

        assert repeated.id == cycle.id
        assert db.scalar(select(func.count()).select_from(models.ContentCycle)) == 1
        assert db.scalar(select(func.count()).select_from(models.VideoJob)) == 1
        assert trace.product_ugc_recipe_draft_id == draft.id
        assert trace.video_job_id == cycle.video_job_id
        assert trace.ai_production_brief_id == cycle.ai_production_brief_id
        assert trace.status == "needs_output_acceptance"
        assert not trace.manual_distribution_ready

        video_job = db.get(models.VideoJob, cycle.video_job_id)
        assert video_job.organization_id == organization.id
        assert video_job.created_by_user_profile_id == profile.id
        assert video_job.product_id == product.id
        assert video_job.source_product_ugc_draft_id == draft.id
        assert video_job.provider == "runway_product_ugc_recipe"
        assert video_job.status == "video_generated"

        brief = db.get(models.AIProductionBrief, cycle.ai_production_brief_id)
        assert brief.product_id == product.id
        assert brief.scene_blueprints[0].scene_role == "review_exact_product_ugc_output"
        evidence_contract = brief.product_identity_rules_json["visual_evidence_contract"]
        assert evidence_contract["ocr_required"] is True
        assert evidence_contract["required_packaging_tokens"] == ["CYCLE", "BRAND"]
        assert evidence_contract["reference_product_asset_id"] == draft.primary_product_asset_id


def test_one_cycle_reaches_manual_task_package_and_tracking_link_without_heuristics(tmp_path: Path):
    with SessionLocal() as db:
        organization, profile = make_actor(db)
        product = make_product(db, organization)
        draft = make_approved_draft(db, product, tmp_path)
        cycle = start_cycle(db, organization, profile, draft)
        acceptance = approve_cycle_output(db, cycle, tmp_path)
        destination = make_destination(db, organization)

        ready = ContentCycleService(db).prepare_manual_distribution(
            organization_id=organization.id,
            actor_user_profile_id=profile.id,
            content_cycle_id=cycle.id,
            output_acceptance_id=acceptance.id,
            destination_id=destination.id,
        )
        repeated = ContentCycleService(db).prepare_manual_distribution(
            organization_id=organization.id,
            actor_user_profile_id=profile.id,
            content_cycle_id=cycle.id,
            output_acceptance_id=acceptance.id,
            destination_id=destination.id,
        )
        trace = ContentCycleService.as_trace(ready)

        assert repeated.id == ready.id
        assert trace.manual_distribution_ready
        assert trace.output_acceptance_id == acceptance.id
        assert all(
            [trace.publishing_package_id, trace.publishing_task_id, trace.tracking_link_id, trace.destination_id]
        )
        assert db.scalar(select(func.count()).select_from(models.PublishingPackage)) == 1
        assert db.scalar(select(func.count()).select_from(models.PublishingTask)) == 1
        assert db.scalar(select(func.count()).select_from(models.TrackingLink)) == 1

        package = db.get(models.PublishingPackage, trace.publishing_package_id)
        task = db.get(models.PublishingTask, trace.publishing_task_id)
        link = db.get(models.TrackingLink, trace.tracking_link_id)
        assert package.video_job_id == trace.video_job_id
        assert package.metadata_json["content_cycle_id"] == trace.id
        assert package.metadata_json["video_output_acceptance_id"] == acceptance.id
        assert package.review_status == "approved"
        assert task.publishing_package_id == package.id
        assert task.status == "manual_upload_required"
        assert task.raw_response_json["no_external_publish_performed"] is True
        assert task.final_url is None
        assert link.publishing_task_id == task.id
        assert link.product_id == product.id
        assert link.target_url == product.product_url

        Path(acceptance.keyframes_json[0]["path"]).write_bytes(b"tampered-after-bind")
        dashboard = FactoryDashboardService(db).snapshot(
            user_profile_id=profile.id,
            organization_id=organization.id,
        )
        assert dashboard["metrics"]["approved_videos"] == 0
        assert dashboard["metrics"]["stale_approved_evidence"] == 1


def test_nonapproved_ambiguous_or_mock_outputs_fail_closed(tmp_path: Path):
    with SessionLocal() as db:
        organization, profile = make_actor(db)
        product = make_product(db, organization)
        draft = make_approved_draft(db, product, tmp_path)
        draft.human_review_status = "needs_human_review"
        draft.publishing_readiness = "blocked"
        db.commit()
        with pytest.raises(ContentCycleStateError, match="explicitly approved"):
            start_cycle(db, organization, profile, draft)

        draft.human_review_status = "approved"
        draft.publishing_readiness = "ready_for_package"
        second = tmp_path / "second-output.mp4"
        second.write_bytes(b"second")
        draft.local_output_paths_json = [draft.local_output_paths_json[0], second.as_posix()]
        db.commit()
        with pytest.raises(ContentCycleStateError, match="exactly one unambiguous"):
            start_cycle(db, organization, profile, draft)

        draft.local_output_paths_json = [draft.local_output_paths_json[0]]
        db.commit()
        cycle = start_cycle(db, organization, profile, draft)
        not_approved = approve_cycle_output(db, cycle, tmp_path, decision="needs_human_review")
        destination = make_destination(db, organization)
        with pytest.raises(ContentCycleStateError, match="not approved"):
            ContentCycleService(db).prepare_manual_distribution(
                organization_id=organization.id,
                actor_user_profile_id=profile.id,
                content_cycle_id=cycle.id,
                output_acceptance_id=not_approved.id,
                destination_id=destination.id,
            )
        db.expire_all()
        untouched_cycle = db.get(models.ContentCycle, cycle.id)
        assert untouched_cycle.output_acceptance_id is None
        assert db.scalar(select(func.count()).select_from(models.PublishingPackage)) == 0

        acceptance = approve_cycle_output(db, cycle, tmp_path)
        cycle = db.get(models.ContentCycle, cycle.id)
        cycle.video_job.provider = "mock"
        db.commit()
        with pytest.raises(ContentCycleStateError, match="Mock video output"):
            ContentCycleService(db).prepare_manual_distribution(
                organization_id=organization.id,
                actor_user_profile_id=profile.id,
                content_cycle_id=cycle.id,
                output_acceptance_id=acceptance.id,
                destination_id=destination.id,
            )
        db.expire_all()
        untouched_cycle = db.get(models.ContentCycle, cycle.id)
        assert untouched_cycle.output_acceptance_id is None
        assert db.scalar(select(func.count()).select_from(models.PublishingPackage)) == 0


def test_cycle_and_destination_are_strictly_organization_scoped(tmp_path: Path):
    with SessionLocal() as db:
        alpha, alpha_user = make_actor(db, slug="cycle-alpha")
        beta, beta_user = make_actor(db, slug="cycle-beta")
        product = make_product(db, alpha, sku="CYCLE-ALPHA-1")
        draft = make_approved_draft(db, product, tmp_path)

        with pytest.raises(ContentCycleOwnershipError, match="Product is not explicitly owned"):
            start_cycle(db, beta, beta_user, draft, key="beta-foreign-source")

        cycle = start_cycle(db, alpha, alpha_user, draft, key="alpha-source")
        with pytest.raises(ContentCycleOwnershipError, match="does not belong"):
            ContentCycleService(db).get_trace(
                organization_id=beta.id,
                actor_user_profile_id=beta_user.id,
                content_cycle_id=cycle.id,
            )

        acceptance = approve_cycle_output(db, cycle, tmp_path)
        foreign_destination = make_destination(db, beta, name="Foreign manual Reels")
        with pytest.raises(ContentCycleOwnershipError, match="destination is not owned"):
            ContentCycleService(db).prepare_manual_distribution(
                organization_id=alpha.id,
                actor_user_profile_id=alpha_user.id,
                content_cycle_id=cycle.id,
                output_acceptance_id=acceptance.id,
                destination_id=foreign_destination.id,
            )


def test_idempotency_key_cannot_be_reused_for_another_source(tmp_path: Path):
    with SessionLocal() as db:
        organization, profile = make_actor(db)
        first_product = make_product(db, organization, sku="CYCLE-IDEMP-1")
        second_product = make_product(db, organization, sku="CYCLE-IDEMP-2")
        first = make_approved_draft(db, first_product, tmp_path, filename="first-real.mp4")
        second = make_approved_draft(db, second_product, tmp_path, filename="second-real.mp4")
        start_cycle(db, organization, profile, first, key="same-request-key")

        with pytest.raises(ContentCycleConflictError, match="another Product UGC draft"):
            start_cycle(db, organization, profile, second, key="same-request-key")


def test_sqlite_legacy_schema_adds_canonical_bridge_columns_and_unique_source_index():
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE script_jobs (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE video_jobs ("
                "id INTEGER PRIMARY KEY, script_variant_id INTEGER NOT NULL, provider VARCHAR(120), "
                "status VARCHAR(80), aspect_ratio VARCHAR(20), duration_seconds INTEGER, "
                "cost_estimate FLOAT, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE publishing_destinations ("
                "id INTEGER PRIMARY KEY, brand VARCHAR(120), platform VARCHAR(120), name VARCHAR(160))"
            )
        )

    _ensure_sqlite_schema()
    inspector = inspect(engine)
    video_columns = {column["name"] for column in inspector.get_columns("video_jobs")}
    destination_columns = {column["name"] for column in inspector.get_columns("publishing_destinations")}
    product_columns = {column["name"] for column in inspector.get_columns("products")}
    unique_indexes = {
        index["name"]
        for index in inspector.get_indexes("video_jobs")
        if index.get("unique")
    }

    assert {
        "organization_id",
        "created_by_user_profile_id",
        "product_id",
        "source_product_ugc_draft_id",
    }.issubset(video_columns)
    assert "organization_id" in destination_columns
    assert "organization_id" in product_columns
    assert "uq_video_job_product_ugc_source" in unique_indexes


def test_public_cycle_routes_reach_publish_metric_and_cost_without_external_actions(
    tmp_path: Path,
    monkeypatch,
):
    with SessionLocal() as db:
        organization, profile = make_actor(db, slug="cycle-public-ui")
        membership = db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization.id,
                models.Membership.user_profile_id == profile.id,
            )
        )
        product = make_product(db, organization, sku="CYCLE-PUBLIC-1")
        draft = make_approved_draft(db, product, tmp_path)
        cycle = start_cycle(db, organization, profile, draft)
        frame = tmp_path / "public-ui-frame-1.png"
        second_frame = tmp_path / "public-ui-frame-2.png"
        contact_sheet = tmp_path / "public-ui-contact.png"
        Image.new("RGB", (720, 1280), color=(220, 42, 54)).save(frame)
        Image.new("RGB", (720, 1280), color=(36, 92, 220)).save(second_frame)
        Image.new("RGB", (1440, 1280), color=(245, 245, 245)).save(contact_sheet)
        source = Path(cycle.video_job.output_video_path)
        db.add(
            models.FrameExtractionResult(
                video_job_id=cycle.video_job_id,
                status="created",
                frame_paths_json=[frame.as_posix(), second_frame.as_posix()],
                contact_sheet_path=contact_sheet.as_posix(),
                duration_seconds=8,
                fps=24,
                warnings_json=[],
                extraction_key=f"test-public-cycle-{cycle.id}",
                source_video_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                source_video_size_bytes=source.stat().st_size,
            )
        )
        destination = make_destination(db, organization)
        db.commit()
        user = PublicPilotUser(profile=profile, organization=organization, membership=membership)
        cycle_id = cycle.id
        destination_id = destination.id

    api = FastAPI()
    api.include_router(public_pilot_router)
    api.dependency_overrides[get_current_public_user] = lambda: user
    monkeypatch.setattr(
        public_pilot_module,
        "AcceptanceReviewService",
        lambda db: AcceptanceReviewService(
            db,
            quality_checker=OutputQualityChecker(
                VisualEvidenceService(ocr_backend=_PackagingOCR())
            ),
        ),
    )
    today = date.today().isoformat()
    with TestClient(api) as client:
        reviewed = client.post(
            f"/workbench/content-cycles/{cycle_id}/review-output",
            data={
                "decision": "approved",
                "reviewer_notes": "Human checked every decoded frame and the exact product.",
                "confirm_video_watched": "true",
                "product_identity_ok": "true",
                "packaging_ok": "true",
                "geometry_ok": "true",
                "blogger_ok": "true",
                "scene_match_ok": "true",
                "proof_moment_ok": "true",
                "cta_ok": "true",
            },
            follow_redirects=False,
        )
        assert reviewed.status_code == 303
        assert "quality_notice=output_approved" in reviewed.headers["location"]

        prepared = client.post(
            f"/workbench/content-cycles/{cycle_id}/prepare-distribution",
            data={
                "destination_id": destination_id,
                "confirm_manual_distribution": "true",
            },
            follow_redirects=False,
        )
        assert prepared.status_code == 303
        assert "funnel_notice=distribution_ready" in prepared.headers["location"]

        published = client.post(
            f"/workbench/content-cycles/{cycle_id}/mark-published",
            data={
                "final_url": "https://www.instagram.com/reel/real-post-1?utm_source=removed",
                "confirm_uploaded": "true",
            },
            follow_redirects=False,
        )
        assert published.status_code == 303
        assert "funnel_notice=publication_completed" in published.headers["location"]

        metrics = client.post(
            "/workbench/social-metrics/ingest",
            data={
                "cycle_id": cycle_id,
                "period_start": today,
                "period_end": today,
                "views": "1000",
                "clicks": "40",
                "orders": "3",
                "revenue": "1497.00",
                "confirm_cumulative_snapshot": "true",
            },
            follow_redirects=False,
        )
        assert metrics.status_code == 303
        assert "metrics_notice=created" in metrics.headers["location"]

        cost = client.post(
            "/workbench/generation-costs/record",
            data={
                "cycle_id": cycle_id,
                "amount": "123.45",
                "currency": "RUB",
                "entry_kind": "actual",
                "external_reference": "invoice-2026-07-public-1",
                "confirm_accounting_fact": "true",
            },
            follow_redirects=False,
        )
        assert cost.status_code == 303
        assert "cost_notice=created" in cost.headers["location"]

    with SessionLocal() as db:
        cycle = db.get(models.ContentCycle, cycle_id)
        assert cycle.output_acceptance_id is not None
        assert cycle.status == "manual_distribution_ready"
        assert cycle.publishing_task.final_url == "https://www.instagram.com/reel/real-post-1"
        assert db.scalar(select(func.count()).select_from(models.DestinationPostMetric)) == 1
        assert db.scalar(select(func.count()).select_from(models.GenerationCostLedgerEntry)) == 1
        dashboard = FactoryDashboardService(db).snapshot(
            user_profile_id=profile.id,
            organization_id=organization.id,
        )
        assert dashboard["metrics"]["measurable_cycles_7d"] == 1

        Path(cycle.output_acceptance.keyframes_json[0]["path"]).write_bytes(
            b"tampered-after-measurement"
        )
        stale_dashboard = FactoryDashboardService(db).snapshot(
            user_profile_id=profile.id,
            organization_id=organization.id,
        )
        assert stale_dashboard["metrics"]["measurable_cycles_7d"] == 0
        event_names = set(db.scalars(select(models.FactoryEvent.event_name)).all())
        assert {"publishing_package_approved", "publication_completed", "first_metric_attributed", "first_order_attributed"}.issubset(event_names)
