from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.creator_operations import CreatorOperationsError, CreatorOperationsService
from app.database import Base, get_db
from app.publishing.errors import PublishingError
from app.publishing.manual_upload import ManualUploadProvider
from app.publishing.publication_identity import (
    PublicationIdentityError,
    canonical_publication_url,
    find_task_by_publication_url,
)
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers import creator_operations as creator_operations_router


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    with TestSession() as session:
        yield session


def _scope(db: Session, slug: str):
    organization = models.Organization(name=slug, slug=slug, status="active", settings_json={})
    owner = models.UserProfile(
        supabase_user_id=f"owner:{slug}",
        email=f"owner@{slug}.test",
        display_name="Owner",
        status="active",
        is_active=True,
        metadata_json={},
    )
    creator = models.UserProfile(
        supabase_user_id=f"creator:{slug}",
        email=f"creator@{slug}.test",
        display_name="Creator",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add_all([organization, owner, creator])
    db.flush()
    db.add_all(
        [
            models.Membership(
                organization_id=organization.id,
                user_profile_id=owner.id,
                role="owner",
                status="active",
                permissions_json=[],
            ),
            models.Membership(
                organization_id=organization.id,
                user_profile_id=creator.id,
                role="producer",
                status="active",
                permissions_json=[],
            ),
        ]
    )
    module = db.scalar(select(models.TrainingModule).where(models.TrainingModule.code == "portal_operator_exam"))
    if module is None:
        module = models.TrainingModule(
            code="portal_operator_exam",
            title="Final exam",
            description="Scenario exam",
            order_index=100,
            required_for_roles_json=[],
            required_for_permissions_json=[],
            is_active=True,
        )
        db.add(module)
        db.flush()
    question = db.scalar(
        select(models.TrainingQuestion).where(models.TrainingQuestion.module_id == module.id)
    )
    if question is None:
        question = models.TrainingQuestion(
            module_id=module.id,
            question_text="What should an operator do before paid generation?",
            question_type="single_choice",
            options_json=["verify", "skip"],
            correct_answer_json=["verify"],
            explanation="Paid generation requires a verified preflight.",
            order_index=1,
        )
        db.add(question)
        db.flush()
    for user in (owner, creator):
        attempt = models.UserTrainingAttempt(
            user_profile_id=user.id,
            module_id=module.id,
            status="passed",
            score=1.0,
            passed=True,
            answers_json={str(question.id): "verify"},
            started_at=models.utcnow(),
            completed_at=models.utcnow(),
        )
        db.add(attempt)
        db.flush()
        db.add(
            models.TrainingCertification(
                user_profile_id=user.id,
                module_id=module.id,
                attempt_id=attempt.id,
                module_code=module.code,
                status="passed",
            )
        )
    product = models.Product(
        organization_id=organization.id,
        sku=f"SKU-{slug}",
        brand="ALTEA",
        title=f"Product {slug}",
        attributes_json={},
        benefits_json=[],
        images_json=[],
        reviews_json=[],
        restrictions_json=[],
    )
    db.add(product)
    db.flush()
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        created_by_user_profile_id=owner.id,
        assigned_to_user_profile_id=creator.id,
        sku=product.sku,
        variant_key="red",
        status="ready_for_paid_preflight",
        platform="Instagram Reels",
        language="ru",
        character_image_path="storage://creator.jpg",
        character_image_filename="creator.jpg",
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_asset_ids_json=[11, 12, 13],
        product_info="A validated product brief with exact packaging and claims.",
        user_concept="Creator demonstrates the product and explains one honest benefit.",
        creative_inputs_json={"hook": "test"},
        duration_seconds=15,
        ratio="720:1280",
        audio_enabled=True,
        estimated_credits=25,
        provider_payload_preview_json={"model": "gen4.5"},
        blockers_json=[],
        warnings_json=[],
        local_output_paths_json=[],
        human_review_status="not_generated",
        publishing_readiness="blocked",
    )
    db.add(draft)
    db.commit()
    return organization, owner, creator, product, draft


def _publishing_scope(
    db: Session,
    tmp_path,
    *,
    slug: str,
    package_count: int = 2,
    daily_limit: int = 10,
    weekly_limit: int = 20,
):
    organization, owner, creator, product, _ = _scope(db, slug)
    video_path = tmp_path / f"{slug}.mp4"
    video_path.write_bytes(b"video")
    packages = []
    for index in range(1, package_count + 1):
        artifact = models.MediaArtifact(
            public_id=f"{organization.id:08d}{index:024d}",
            idempotency_key=f"placement-artifact:{slug}:{index}",
            organization_id=organization.id,
            created_by_user_profile_id=owner.id,
            product_id=product.id,
            kind="master_video",
            backend_name="local",
            bucket="private-media",
            object_key=f"organizations/{organization.id:08d}/videos/{slug}-{index}.mp4",
            original_filename=f"{slug}-{index}.mp4",
            mime_type="video/mp4",
            size_bytes=5,
            sha256=f"{index:064x}",
            status="ready",
            metadata_json={},
            retention_class="master_365d",
            legal_hold=False,
        )
        db.add(artifact)
        db.flush()
        package = models.PublishingPackage(
            organization_id=organization.id,
            video_job_id=10_000 + index,
            media_artifact_id=artifact.id,
            product_id=product.id,
            brand="ALTEA",
            target_platform="Instagram Reels",
            title=f"Approved package {index}",
            description=f"Measured product publication {index}",
            hashtags_json=["#altea", "#contentfactory"],
            cta="Перейдите по отслеживаемой ссылке",
            product_url=f"https://www.wildberries.ru/catalog/{100000 + index}/detail.aspx",
            video_file_path=str(video_path),
            metadata_json={
                "human_review": {
                    "confirmed": True,
                    "reviewer_role": "owner",
                    "reviewer_user_profile_id": owner.id,
                }
            },
            review_status="approved",
            status="approved",
        )
        db.add(package)
        packages.append(package)
    destination = models.PublishingDestination(
        organization_id=organization.id,
        brand="ALTEA",
        platform="Instagram Reels",
        name=f"Destination {slug}",
        status="active",
        posting_mode="manual",
        auth_status="manual_only",
        allowed_formats_json=["vertical_video"],
        daily_limit=daily_limit,
        weekly_limit=weekly_limit,
    )
    db.add(destination)
    db.commit()
    return organization, owner, creator, packages, destination


def test_generation_dry_run_is_measurable_and_spend_free(db: Session):
    organization, owner, creator, _, draft = _scope(db, "dry-run")
    service = CreatorOperationsService(db)

    batch = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=5,
        name="Five creator videos",
        idempotency_key="generation:dry-run:0001",
        dry_run=True,
        confirm_real_spend=False,
    )

    assert batch.status == "validated"
    assert batch.total_requested == batch.total_accepted == 5
    assert batch.parameters_json["estimated_credits"] == 125
    assert len(batch.results_json) == 5
    assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 0
    assert db.scalar(select(func.count()).select_from(models.CreatorTask)) == 0


def test_generation_batch_clones_drafts_and_enqueues_one_durable_job_each(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _, draft = _scope(db, "execute")
    creator_artifact = models.MediaArtifact(
        public_id="a" * 32,
        organization_id=organization.id,
        created_by_user_profile_id=owner.id,
        product_id=draft.product_id,
        kind="creator_reference",
        backend_name="supabase",
        bucket="private-media",
        object_key=(
            f"organizations/{organization.id:08d}/products/{draft.product_id}/"
            f"drafts/unassigned/videos/unassigned/creator_reference/{'a' * 32}.png"
        ),
        original_filename="creator.png",
        mime_type="image/png",
        size_bytes=123,
        sha256="b" * 64,
        status="ready",
        metadata_json={},
        retention_class="standard",
        legal_hold=False,
    )
    db.add(creator_artifact)
    db.flush()
    draft.character_media_artifact_id = creator_artifact.id
    db.commit()
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)

    batch = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=3,
        name="Three real creator videos",
        idempotency_key="generation:execute:0001",
        dry_run=False,
        confirm_real_spend=True,
        confirmed_total_credits=75,
    )

    assert batch.status == "queued"
    assert batch.total_accepted == 3
    assert batch.total_failed == 0
    assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 3
    assert db.scalar(select(func.count()).select_from(models.CreatorTask)) == 3
    clones = db.scalars(
        select(models.ProductUGCRecipeDraft).where(models.ProductUGCRecipeDraft.id != draft.id)
    ).all()
    assert len(clones) == 3
    assert {item.assigned_to_user_profile_id for item in clones} == {creator.id}
    assert {item.variant_key for item in clones} == {draft.variant_key}
    assert {
        item.creative_inputs_json["mass_batch"]["sequence"] for item in clones
    } == {1, 2, 3}
    assert {item.character_media_artifact_id for item in clones} == {creator_artifact.id}

    repeated = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=3,
        name="Three real creator videos",
        idempotency_key="generation:execute:0001",
        dry_run=False,
        confirm_real_spend=True,
        confirmed_total_credits=75,
    )
    assert repeated.id == batch.id
    assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 3

    with pytest.raises(CreatorOperationsError, match="idempotency_key_reused_with_different_payload"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=3,
            name="Different payload",
            idempotency_key="generation:execute:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=75,
        )


def test_generation_batch_rejects_uncertified_or_cross_tenant_assignee(db: Session):
    organization, owner, _, _, draft = _scope(db, "one")
    foreign_org, _, foreign_creator, _, _ = _scope(db, "two")
    assert foreign_org.id != organization.id
    service = CreatorOperationsService(db)

    with pytest.raises(CreatorOperationsError, match="active_membership_required"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[foreign_creator.id],
            quantity=1,
            name="Cross tenant attempt",
            idempotency_key="generation:cross-tenant:0001",
            dry_run=True,
            confirm_real_spend=False,
        )


def test_generation_rejects_foreign_template_and_forged_certificate(db: Session):
    organization, owner, creator, _, _ = _scope(db, "template-owner")
    _, _, _, _, foreign_draft = _scope(db, "template-foreign")
    service = CreatorOperationsService(db)

    with pytest.raises(CreatorOperationsError, match="template_draft_not_found"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=foreign_draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=1,
            name="Foreign template",
            idempotency_key="generation:foreign-template:0001",
            dry_run=True,
            confirm_real_spend=False,
        )

    certification = db.scalar(
        select(models.TrainingCertification).where(
            models.TrainingCertification.user_profile_id == creator.id,
            models.TrainingCertification.module_code == "portal_operator_exam",
        )
    )
    certification.attempt_id = None
    db.commit()
    own_draft = db.scalar(
        select(models.ProductUGCRecipeDraft)
        .join(models.Product)
        .where(models.Product.organization_id == organization.id)
    )
    with pytest.raises(CreatorOperationsError, match="assignee_final_exam_required"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=own_draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=1,
            name="Forged certificate",
            idempotency_key="generation:forged-certificate:0001",
            dry_run=True,
            confirm_real_spend=False,
        )


def test_generation_spend_gate_credit_confirmation_and_mass_limits(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _, draft = _scope(db, "spend-gates")
    service = CreatorOperationsService(db)

    monkeypatch.setattr(service.settings, "allow_real_spend", False)
    with pytest.raises(CreatorOperationsError, match="real_spend_gate_required"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=1,
            name="Disabled spend",
            idempotency_key="generation:disabled-spend:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )

    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    with pytest.raises(CreatorOperationsError, match="confirmed_total_credits_must_equal_25"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=1,
            name="Wrong confirmation",
            idempotency_key="generation:wrong-confirmation:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=24,
        )
    monkeypatch.setattr(service.settings, "mass_generation_credit_limit", 500)
    with pytest.raises(CreatorOperationsError, match="generation_credit_limit_exceeded:525>500"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=21,
            name="Over credit cap",
            idempotency_key="generation:over-credit-cap:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=525,
        )
    with pytest.raises(CreatorOperationsError, match="assignee_count_exceeds_50"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=list(range(1, 52)),
            quantity=1,
            name="Too many assignees",
            idempotency_key="generation:too-many-assignees:0001",
            dry_run=True,
            confirm_real_spend=False,
        )

    assert db.scalar(select(func.count()).select_from(models.MassOperationBatch)) == 0
    assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 0
    assert db.scalar(select(func.count()).select_from(models.CreatorTask)) == 0


def test_standard_fifteen_second_batch_fits_default_mass_credit_boundary(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _product, draft = _scope(
        db,
        "standard-credit-boundary",
    )
    draft.duration_seconds = 15
    draft.ratio = "720:1280"
    draft.estimated_credits = 588
    db.commit()
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    assert service.settings.mass_generation_credit_limit == 30_000

    batch = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=50,
        name="Fifty standard videos",
        idempotency_key="generation:standard-credit-boundary:0001",
        dry_run=False,
        confirm_real_spend=True,
        confirmed_total_credits=29_400,
    )

    assert batch.total_accepted == 50
    assert batch.parameters_json["estimated_credits"] == 29_400
    assert batch.parameters_json["credit_limit"] == 30_000
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 50
    assert db.scalar(select(func.count(models.CreatorTask.id))) == 50


def test_generation_rejects_paid_batch_without_positive_credit_estimate(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _, draft = _scope(db, "missing-credit-estimate")
    draft.estimated_credits = 0
    db.commit()
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)

    with pytest.raises(CreatorOperationsError, match="template_credit_estimate_required"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=1,
            name="Unknown spend",
            idempotency_key="generation:unknown-spend:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=0,
        )
    assert db.scalar(select(func.count()).select_from(models.MassOperationBatch)) == 0


def test_producer_cannot_authorize_real_spend(db: Session, monkeypatch):
    organization, _, creator, _, draft = _scope(db, "producer-spend")
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)

    with pytest.raises(CreatorOperationsError, match="real_spend_owner_admin_required"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=creator.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=1,
            name="Producer spend",
            idempotency_key="generation:producer-spend:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )
    assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 0


def test_generation_batch_rolls_back_every_row_on_mid_batch_failure(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _, draft = _scope(db, "rollback")
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    original_generation_task = service._generation_task

    def fail_second_task(**kwargs):
        if kwargs["sequence"] == 2:
            raise RuntimeError("synthetic failure")
        return original_generation_task(**kwargs)

    monkeypatch.setattr(service, "_generation_task", fail_second_task)
    with pytest.raises(CreatorOperationsError, match="generation_batch_transaction_failed"):
        service.generation_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            template_draft_id=draft.id,
            assignee_user_profile_ids=[creator.id],
            quantity=3,
            name="Atomic rollback",
            idempotency_key="generation:atomic-rollback:0001",
            dry_run=False,
            confirm_real_spend=True,
            confirmed_total_credits=75,
        )

    assert db.scalar(select(func.count()).select_from(models.MassOperationBatch)) == 0
    assert db.scalar(select(func.count()).select_from(models.ProductUGCGenerationJob)) == 0
    assert db.scalar(select(func.count()).select_from(models.CreatorTask)) == 0
    assert db.scalar(select(func.count()).select_from(models.ProductUGCRecipeDraft)) == 1


def test_placement_dry_run_reserves_limits_and_actual_batch_is_atomic(db: Session, tmp_path):
    organization, owner, _, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-limits",
        daily_limit=1,
        weekly_limit=3,
    )
    service = CreatorOperationsService(db)
    start_at = datetime.now(UTC) + timedelta(minutes=10)

    dry_run = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[item.id for item in packages],
        destination_ids=[destination.id],
        start_at=start_at,
        interval_minutes=5,
        name="Placement limit preview",
        idempotency_key="placement:limit-preview:0001",
        dry_run=True,
    )
    assert dry_run.status == "completed_with_errors"
    assert dry_run.total_accepted == 1
    assert dry_run.total_failed == 1
    assert "daily_publishing_limit_reached_in_batch" in dry_run.errors_json[0]["error"]
    assert db.scalar(select(func.count()).select_from(models.PublishingTask)) == 0

    actual = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[item.id for item in packages],
        destination_ids=[destination.id],
        start_at=start_at,
        interval_minutes=5,
        name="Placement limit actual",
        idempotency_key="placement:limit-actual:0001",
        dry_run=False,
    )
    assert actual.status == "blocked"
    assert actual.total_accepted == 0
    assert actual.total_failed == 2
    assert actual.errors_json[-1] == {"error": "atomic_placement_batch_cancelled"}
    assert db.scalar(select(func.count()).select_from(models.PublishingTask)) == 0


def test_placement_matches_platform_alias_brand_and_available_destination(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, instagram_destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-compatible-match",
        package_count=2,
    )
    instagram_destination.platform = "instagram"
    wrong_platform = models.PublishingDestination(
        organization_id=organization.id,
        brand="ALTEA",
        platform="TikTok",
        name="Wrong TikTok",
        status="active",
        posting_mode="manual",
        auth_status="manual_only",
        allowed_formats_json=["vertical_video"],
        daily_limit=10,
        weekly_limit=20,
    )
    wrong_brand = models.PublishingDestination(
        organization_id=organization.id,
        brand="OTHER",
        platform="Instagram Reels",
        name="Wrong brand",
        status="active",
        posting_mode="manual",
        auth_status="manual_only",
        allowed_formats_json=["vertical_video"],
        daily_limit=10,
        weekly_limit=20,
    )
    db.add_all([wrong_platform, wrong_brand])
    db.commit()

    batch = CreatorOperationsService(db).placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[item.id for item in packages],
        destination_ids=[wrong_platform.id, wrong_brand.id, instagram_destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Compatible destination matching",
        idempotency_key="placement:compatible-match:0001",
        dry_run=True,
    )

    assert batch.status == "validated"
    assert batch.total_accepted == 2
    assert {item["destination_id"] for item in batch.results_json} == {
        instagram_destination.id
    }
    assert all(
        item["matched_destination"]["platform"] == "instagram"
        and item["matched_destination"]["brand"] == "ALTEA"
        for item in batch.results_json
    )


def test_naive_placement_time_uses_explicit_browser_timezone_and_dst_rules():
    service = CreatorOperationsService.__new__(CreatorOperationsService)

    assert service._normalize_placement_start(
        datetime(2026, 1, 15, 15, 0),
        "Europe/Berlin",
    ) == datetime(2026, 1, 15, 14, 0)
    assert service._normalize_placement_start(
        datetime(2026, 7, 15, 15, 0),
        "Europe/Berlin",
    ) == datetime(2026, 7, 15, 13, 0)
    assert service._normalize_placement_start(
        datetime(2026, 7, 15, 15, 0),
        "Europe/Moscow",
    ) == datetime(2026, 7, 15, 12, 0)
    with pytest.raises(
        CreatorOperationsError,
        match="start_at_does_not_exist_in_timezone",
    ):
        service._normalize_placement_start(
            datetime(2026, 3, 29, 2, 30),
            "Europe/Berlin",
        )
    with pytest.raises(
        CreatorOperationsError,
        match="start_at_is_ambiguous_in_timezone",
    ):
        service._normalize_placement_start(
            datetime(2026, 10, 25, 2, 30),
            "Europe/Berlin",
        )


def test_platform_publication_identity_preserves_required_ids_and_rejects_short_links():
    instagram = models.PublishingDestination(
        brand="ALTEA",
        platform="Instagram",
        name="Instagram",
    )
    facebook = models.PublishingDestination(
        brand="ALTEA",
        platform="Facebook",
        name="Facebook",
    )
    pinterest = models.PublishingDestination(
        brand="ALTEA",
        platform="Pinterest",
        name="Pinterest",
    )
    vk = models.PublishingDestination(brand="ALTEA", platform="VK Clips", name="VK")
    rutube = models.PublishingDestination(brand="ALTEA", platform="Rutube", name="Rutube")
    telegram = models.PublishingDestination(
        brand="ALTEA",
        platform="Telegram",
        name="Telegram",
    )

    assert canonical_publication_url(
        "https://m.facebook.com/watch?utm_source=creator&v=Video_111",
        facebook,
    ) == "https://www.facebook.com/watch?v=Video_111"
    assert canonical_publication_url(
        "https://facebook.com/watch?v=Video_222&utm_medium=social",
        facebook,
    ) == "https://www.facebook.com/watch?v=Video_222"
    with pytest.raises(
        PublicationIdentityError,
        match="placement_final_url_invalid",
    ):
        canonical_publication_url(
            "https://www.instagram.com/reel/real-post-1?token=must-not-enter-logs",
            instagram,
        )
    with pytest.raises(
        PublicationIdentityError,
        match="placement_final_url_short_link_not_supported",
    ):
        canonical_publication_url("https://fb.watch/shortCode", facebook)
    with pytest.raises(
        PublicationIdentityError,
        match="placement_final_url_short_link_not_supported",
    ):
        canonical_publication_url("https://pin.it/shortCode", pinterest)
    assert canonical_publication_url(
        "https://vk.com/clip-123_456?utm_source=creator",
        vk,
    ) == "https://vk.com/clip-123_456"
    assert canonical_publication_url(
        "https://rutube.ru/video/abcde_12345",
        rutube,
    ) == "https://rutube.ru/video/abcde_12345"
    assert canonical_publication_url(
        "https://t.me/altea_team/123?single=true",
        telegram,
    ) == "https://t.me/altea_team/123"
    for unsafe_url, destination in (
        ("https://vk.com/feed", vk),
        ("https://vk.com/altea", vk),
        ("https://rutube.ru/channel/123", rutube),
        ("https://t.me/s/altea", telegram),
    ):
        with pytest.raises(
            PublicationIdentityError,
            match="placement_final_url_post_path_required",
        ):
            canonical_publication_url(unsafe_url, destination)


def test_metrics_matcher_uses_same_youtube_identity_as_completion(db: Session, tmp_path):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="youtube-publication-identity",
        package_count=1,
    )
    packages[0].target_platform = "YouTube Shorts"
    destination.platform = "youtube"
    db.commit()
    batch = CreatorOperationsService(db).placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[packages[0].id],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="YouTube identity",
        idempotency_key="placement:youtube-identity:0001",
        dry_run=False,
    )
    creator_task = db.scalar(
        select(models.CreatorTask).where(
            models.CreatorTask.mass_operation_batch_id == batch.id
        )
    )
    completed = CreatorOperationsService(db).complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=creator_task.id,
        final_url=(
            "https://www.youtube.com/watch?v=AbCdEf12345&utm_source=creator"
        ),
    )
    publishing_task = db.get(models.PublishingTask, completed.publishing_task_id)
    assert publishing_task.final_url == (
        "https://www.youtube.com/shorts/AbCdEf12345"
    )
    assert find_task_by_publication_url(
        db,
        "https://youtu.be/AbCdEf12345?utm_campaign=metrics",
        platform="YouTube Shorts",
        organization_id=organization.id,
    ).id == publishing_task.id

def test_placement_success_is_idempotent_and_tenant_scoped(db: Session, tmp_path):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-success",
    )
    foreign_org, _, _, foreign_packages, foreign_destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-foreign",
        package_count=1,
    )
    assert foreign_org.id != organization.id
    service = CreatorOperationsService(db)
    start_at = datetime.now(UTC) + timedelta(minutes=10)
    kwargs = {
        "organization_id": organization.id,
        "actor_user_profile_id": owner.id,
        "package_ids": [item.id for item in packages],
        "destination_ids": [destination.id],
        "assignee_user_profile_ids": [creator.id, owner.id],
        "start_at": start_at,
        "interval_minutes": 5,
        "name": "Successful placement",
        "idempotency_key": "placement:success:0001",
        "dry_run": False,
    }

    batch = service.placement_batch(**kwargs)
    assert batch.status == "queued"
    assert batch.completed_at is None
    assert batch.total_accepted == 2
    assert db.scalar(select(func.count()).select_from(models.PublishingTask)) == 2
    placement_tasks = list(
        db.scalars(select(models.CreatorTask).order_by(models.CreatorTask.id))
    )
    publishing_tasks = list(
        db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.id))
    )
    tracking_links = list(
        db.scalars(select(models.TrackingLink).order_by(models.TrackingLink.id))
    )
    assert len(placement_tasks) == 2
    assert len(tracking_links) == 2
    assert [item.assignee_user_profile_id for item in placement_tasks] == [creator.id, owner.id]
    assert [item.publishing_task_id for item in placement_tasks] == [
        item.id for item in publishing_tasks
    ]
    assert [item.media_artifact_id for item in placement_tasks] == [
        item.media_artifact_id for item in packages
    ]
    assert [item.due_at for item in placement_tasks] == [
        item.scheduled_at for item in publishing_tasks
    ]
    assert all(item.task_type == "manual_placement" and item.status == "todo" for item in placement_tasks)
    assert all(destination.platform in item.instructions for item in placement_tasks)
    assert all(destination.name in item.instructions for item in placement_tasks)
    assert [item.publishing_task_id for item in tracking_links] == [
        item.id for item in publishing_tasks
    ]
    assert all(item.target_url.startswith("https://www.wildberries.ru/") for item in tracking_links)
    assert all(
        item.result_json["manual_upload"]["tracking_link"].startswith("/r/mp-")
        and item.result_json["manual_upload"]["video_file_path"] is None
        and "tracking_link_missing" not in item.result_json["manual_upload"]["warnings"]
        and item.result_json["manual_upload"]["title"]
        and item.result_json["manual_upload"]["description"]
        and item.result_json["manual_upload"]["hashtags"]
        and item.result_json["manual_upload"]["cta"]
        for item in placement_tasks
    )
    assert {item["status"] for item in batch.results_json} == {"todo"}
    repeated = service.placement_batch(**kwargs)
    assert repeated.id == batch.id
    assert db.scalar(select(func.count()).select_from(models.PublishingTask)) == 2
    assert db.scalar(select(func.count()).select_from(models.CreatorTask)) == 2

    with pytest.raises(CreatorOperationsError, match="idempotency_key_reused_with_different_payload"):
        service.placement_batch(**{**kwargs, "name": "Changed placement"})
    with pytest.raises(CreatorOperationsError, match="publishing_package_not_found"):
        service.placement_batch(
            **{
                **kwargs,
                "package_ids": [foreign_packages[0].id],
                "idempotency_key": "placement:foreign-package:0001",
            }
        )
    with pytest.raises(CreatorOperationsError, match="publishing_destination_not_found"):
        service.placement_batch(
            **{
                **kwargs,
                "destination_ids": [foreign_destination.id],
                "idempotency_key": "placement:foreign-destination:0001",
            }
        )
    with pytest.raises(CreatorOperationsError, match="destination_count_exceeds_50"):
        service.placement_batch(
            **{
                **kwargs,
                "destination_ids": list(range(1, 52)),
                "idempotency_key": "placement:too-many-destinations:0001",
            }
        )


def test_clean_placement_dry_run_promotes_without_reentering_selection(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-promotion",
        package_count=2,
    )
    service = CreatorOperationsService(db)
    preview = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[item.id for item in packages],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=30),
        interval_minutes=5,
        payout_per_post_minor=12_345,
        name="Placement promotion preview",
        idempotency_key="placement:promotion-preview:0001",
        dry_run=True,
    )
    assert preview.status == "validated"

    promoted = service.promote_dry_run_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        batch_id=preview.id,
    )
    db.refresh(preview)
    assert promoted.dry_run is False
    assert promoted.status == "queued"
    assert promoted.total_accepted == 2
    assert promoted.parameters_json["source_dry_run_batch_id"] == preview.id
    assert preview.parameters_json["promoted_to_batch_id"] == promoted.id
    assert db.scalar(
        select(func.count(models.CreatorTask.id)).where(
            models.CreatorTask.mass_operation_batch_id == promoted.id
        )
    ) == 2
    repeated = service.promote_dry_run_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        batch_id=preview.id,
    )
    assert repeated.id == promoted.id


def test_clean_generation_dry_run_requires_spend_confirmation_on_promotion(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _product, draft = _scope(
        db,
        "generation-promotion",
    )
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=2,
        name="Generation promotion preview",
        idempotency_key="generation:promotion-preview:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    snapshot = preview.parameters_json["template_snapshot"]
    snapshot_sha256 = preview.parameters_json["template_snapshot_sha256"]
    assert snapshot["schema"] == "generation_template_snapshot_v1"
    canonical_snapshot = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert snapshot_sha256 == hashlib.sha256(
        canonical_snapshot.encode("utf-8")
    ).hexdigest()
    assert snapshot["draft"]["user_concept"] == draft.user_concept
    assert snapshot["draft"]["product_asset_ids_json"] == [11, 12, 13]
    assert snapshot["draft"]["provider_payload_preview_json"] == {"model": "gen4.5"}
    assert snapshot["draft"]["estimated_credits"] == 25
    with pytest.raises(CreatorOperationsError, match="real_spend_gate_required"):
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
        )
    promoted = service.promote_dry_run_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        batch_id=preview.id,
        confirm_real_spend=True,
        confirmed_total_credits=50,
    )
    assert promoted.status == "queued"
    assert promoted.total_accepted == 2
    assert promoted.parameters_json["template_snapshot"] == snapshot
    clone = db.get(
        models.ProductUGCRecipeDraft,
        int(promoted.results_json[0]["draft_id"]),
    )
    assert clone is not None
    assert clone.user_concept == snapshot["draft"]["user_concept"]
    assert clone.product_asset_ids_json == snapshot["draft"]["product_asset_ids_json"]
    assert (
        clone.provider_payload_preview_json
        == snapshot["draft"]["provider_payload_preview_json"]
    )
    assert clone.estimated_credits == snapshot["draft"]["estimated_credits"]
    generation_job = db.get(
        models.ProductUGCGenerationJob,
        int(promoted.results_json[0]["generation_job_id"]),
    )
    assert generation_job is not None
    job_metadata = generation_job.metadata_json
    assert (
        job_metadata["generation_template_snapshot_schema"]
        == "generation_template_snapshot_v1"
    )
    assert job_metadata["generation_template_snapshot_hash"] == snapshot_sha256
    assert job_metadata["source_preview_batch_id"] == preview.id
    assert job_metadata["source_batch_id"] == promoted.id
    assert job_metadata["source_template_draft_id"] == draft.id
    assert job_metadata["launch_draft_id"] == clone.id
    assert job_metadata["estimated_credits_per_item"] == 25
    expected_provider_hash = hashlib.sha256(
        json.dumps(
            snapshot["draft"]["provider_payload_preview_json"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert job_metadata["provider_payload_sha256"] == expected_provider_hash
    repeated = service.promote_dry_run_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        batch_id=preview.id,
        confirm_real_spend=True,
        confirmed_total_credits=50,
    )
    assert repeated.id == promoted.id


@pytest.mark.parametrize(
    ("field_name", "mutated_value"),
    [
        ("attributes_json", {"material": "mutated-after-preview"}),
        ("restrictions_json", ["new-claim-restriction"]),
    ],
)
def test_generation_promotion_rejects_product_preflight_mutation(
    db: Session,
    monkeypatch,
    field_name: str,
    mutated_value: object,
):
    organization, owner, creator, product, draft = _scope(
        db,
        f"generation-product-{field_name.replace('_', '-')}",
    )
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Product preflight snapshot",
        idempotency_key=f"generation:product-snapshot:{field_name}:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    setattr(product, field_name, mutated_value)
    db.commit()

    with pytest.raises(CreatorOperationsError) as exc_info:
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )
    assert "generation_template_changed_since_dry_run:product" in str(exc_info.value)
    db.rollback()
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 0


@pytest.mark.parametrize("tamper_kind", ["schema", "hash"])
def test_generation_promotion_rejects_tampered_snapshot_contract(
    db: Session,
    monkeypatch,
    tamper_kind: str,
):
    organization, owner, creator, _product, draft = _scope(
        db,
        f"generation-snapshot-tamper-{tamper_kind}",
    )
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Tamper-resistant preview",
        idempotency_key=f"generation:snapshot-tamper:{tamper_kind}:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    parameters = dict(preview.parameters_json)
    snapshot = dict(parameters["template_snapshot"])
    if tamper_kind == "schema":
        snapshot["schema"] = "attacker_defined_snapshot_v999"
        parameters["template_snapshot"] = snapshot
        parameters["template_snapshot_sha256"] = hashlib.sha256(
            json.dumps(
                snapshot,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
    else:
        parameters["template_snapshot_sha256"] = "0" * 64
    preview.parameters_json = parameters
    db.commit()

    with pytest.raises(
        CreatorOperationsError,
        match="dry_run_template_snapshot_missing_or_invalid:create_new_dry_run",
    ):
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )
    db.rollback()
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 0


def test_generation_promotion_fails_closed_for_legacy_preview_without_snapshot(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _product, draft = _scope(
        db,
        "generation-legacy-preview",
    )
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Legacy preview",
        idempotency_key="generation:legacy-preview:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    parameters = dict(preview.parameters_json)
    parameters.pop("template_snapshot")
    parameters.pop("template_snapshot_sha256")
    preview.parameters_json = parameters
    db.commit()

    with pytest.raises(
        CreatorOperationsError,
        match="dry_run_template_snapshot_missing_or_invalid:create_new_dry_run",
    ):
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )
    db.rollback()
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 0


def test_generation_promotion_recovers_committed_orphan_independent_of_actor(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, _product, draft = _scope(
        db,
        "generation-orphan-recovery",
    )
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Orphan recovery preview",
        idempotency_key="generation:orphan-preview:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    snapshot = preview.parameters_json["template_snapshot"]
    snapshot_sha256 = preview.parameters_json["template_snapshot_sha256"]
    launch_key = f"promote:generation:{organization.id}:{preview.id}"

    # Simulate a process crash after generation_batch's internal commit and
    # before promote_dry_run_batch records promoted_to_batch_id on the preview.
    orphan = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Committed launch without lineage write",
        idempotency_key=launch_key,
        dry_run=False,
        confirm_real_spend=True,
        confirmed_total_credits=25,
        _expected_template_snapshot=snapshot,
        _expected_template_snapshot_sha256=snapshot_sha256,
        _source_dry_run_batch_id=preview.id,
    )
    db.refresh(preview)
    assert preview.parameters_json.get("promoted_to_batch_id") is None

    recovered = service.promote_dry_run_batch(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        batch_id=preview.id,
    )
    assert recovered.id == orphan.id
    db.refresh(preview)
    assert preview.parameters_json["promoted_to_batch_id"] == orphan.id
    assert db.scalar(
        select(func.count(models.MassOperationBatch.id)).where(
            models.MassOperationBatch.idempotency_key == launch_key
        )
    ) == 1
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 1


@pytest.mark.parametrize(
    ("field_name", "mutated_value", "changed_path"),
    [
        (
            "user_concept",
            "A different prompt that was never reviewed in the dry-run.",
            "draft.user_concept",
        ),
        ("product_asset_ids_json", [11, 12, 99], "draft.product_asset_ids_json"),
        (
            "provider_payload_preview_json",
            {"model": "gen4.5", "seed": 999},
            "draft.provider_payload_preview_json",
        ),
        ("estimated_credits", 30, "draft.estimated_credits"),
    ],
)
def test_generation_promotion_rejects_template_mutation_after_dry_run(
    db: Session,
    monkeypatch,
    field_name: str,
    mutated_value: object,
    changed_path: str,
):
    organization, owner, creator, _product, draft = _scope(
        db,
        f"generation-snapshot-{field_name.replace('_', '-')}",
    )
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=2,
        name="Immutable generation preview",
        idempotency_key=f"generation:snapshot:{field_name}:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )

    setattr(draft, field_name, mutated_value)
    db.commit()

    with pytest.raises(CreatorOperationsError) as exc_info:
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
            confirm_real_spend=True,
            confirmed_total_credits=50,
        )
    message = str(exc_info.value)
    assert message.startswith("generation_template_changed_since_dry_run:")
    assert changed_path in message
    assert message.endswith(":create_new_dry_run")
    db.rollback()
    assert db.scalar(
        select(func.count(models.MassOperationBatch.id)).where(
            models.MassOperationBatch.operation_type == "generation",
            models.MassOperationBatch.dry_run.is_(False),
        )
    ) == 0
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 0


def test_generation_promotion_rejects_referenced_asset_record_mutation(
    db: Session,
    monkeypatch,
):
    organization, owner, creator, product, draft = _scope(
        db,
        "generation-snapshot-linked-asset",
    )
    asset_kit = models.ProductAssetKit(
        product_id=product.id,
        status="ready",
        assets_json=[],
        required_assets_json=[],
        missing_assets_json=[],
        validation_report_json={},
        warnings_json=[],
        provider_reference_bundle_json={},
        real_generation_blockers_json=[],
    )
    db.add(asset_kit)
    db.flush()
    asset = models.ProductAsset(
        id=11,
        product_id=product.id,
        asset_kit_id=asset_kit.id,
        source_ref="https://cdn.example.test/product-v1.png",
        source_type="url",
        asset_type="image",
        asset_role="primary_reference",
        filename="product-v1.png",
        extension=".png",
        mime_type="image/png",
        exists=True,
        status="ready",
        is_primary_reference=True,
        is_safe_for_real_generation=True,
        review_status="approved",
        checksum="a" * 64,
        metadata_json={},
        warnings_json=[],
    )
    db.add(asset)
    draft.primary_product_asset_id = asset.id
    db.commit()
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Linked asset preview",
        idempotency_key="generation:snapshot:linked-asset:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    assert preview.parameters_json["template_snapshot"]["product_assets"][0][
        "checksum"
    ] == "a" * 64

    asset.source_ref = "https://cdn.example.test/product-v2.png"
    asset.checksum = "b" * 64
    db.commit()

    with pytest.raises(CreatorOperationsError) as exc_info:
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )
    message = str(exc_info.value)
    assert "generation_template_changed_since_dry_run:product_assets" in message
    assert message.endswith(":create_new_dry_run")
    db.rollback()
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 0


@pytest.mark.parametrize(
    ("field_name", "mutated_value"),
    [
        ("sha256", "c" * 64),
        ("object_key", "organizations/changed/private-input.png"),
        ("status", "archived"),
    ],
)
def test_generation_promotion_rejects_private_artifact_identity_or_state_mutation(
    db: Session,
    monkeypatch,
    field_name: str,
    mutated_value: object,
):
    organization, owner, creator, product, draft = _scope(
        db,
        f"generation-artifact-{field_name.replace('_', '-')}",
    )
    artifact = models.MediaArtifact(
        public_id=f"artifact{field_name}".ljust(32, "0")[:32],
        idempotency_key=f"generation-artifact:{field_name}",
        organization_id=organization.id,
        created_by_user_profile_id=owner.id,
        product_id=product.id,
        kind="creator_reference",
        backend_name="supabase",
        bucket="private-media",
        object_key=(
            f"organizations/{organization.id:08d}/products/{product.id}/"
            f"creator_reference/{field_name}.png"
        ),
        original_filename="creator.png",
        mime_type="image/png",
        size_bytes=123,
        sha256="b" * 64,
        status="ready",
        metadata_json={},
        retention_class="standard",
        legal_hold=False,
    )
    db.add(artifact)
    db.flush()
    draft.character_media_artifact_id = artifact.id
    db.commit()
    service = CreatorOperationsService(db)
    monkeypatch.setattr(service.settings, "allow_real_spend", True)
    preview = service.generation_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        template_draft_id=draft.id,
        assignee_user_profile_ids=[creator.id],
        quantity=1,
        name="Private artifact snapshot",
        idempotency_key=f"generation:artifact-snapshot:{field_name}:0001",
        dry_run=True,
        confirm_real_spend=False,
        confirmed_total_credits=0,
    )
    assert len(preview.parameters_json["template_snapshot"]["media_artifacts"]) == 1

    setattr(artifact, field_name, mutated_value)
    db.commit()

    with pytest.raises(CreatorOperationsError) as exc_info:
        service.promote_dry_run_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            batch_id=preview.id,
            confirm_real_spend=True,
            confirmed_total_credits=25,
        )
    assert "generation_template_changed_since_dry_run:media_artifacts" in str(
        exc_info.value
    )
    db.rollback()
    assert db.scalar(select(func.count(models.ProductUGCGenerationJob.id))) == 0


def test_manual_placement_completion_updates_task_publication_and_batch_atomically(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-completion",
    )
    service = CreatorOperationsService(db)
    batch = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[item.id for item in packages],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id, owner.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Manual placement completion",
        idempotency_key="placement:completion:0001",
        dry_run=False,
    )
    creator_tasks = list(
        db.scalars(select(models.CreatorTask).order_by(models.CreatorTask.id))
    )

    first = service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=creator_tasks[0].id,
        final_url="https://INSTAGRAM.COM/reel/placement-one/?utm_source=creator",
    )

    first_publication = db.get(models.PublishingTask, first.publishing_task_id)
    db.refresh(batch)
    assert first.status == "done"
    assert first.completed_at is not None
    assert first.result_json["final_url"] == "https://www.instagram.com/reel/placement-one"
    assert first_publication.status == "published_manual"
    assert first_publication.final_url == "https://www.instagram.com/reel/placement-one"
    assert batch.status == "running"
    assert batch.completed_at is None
    assert [item["status"] for item in batch.results_json] == ["done", "todo"]

    repeated = service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=creator_tasks[0].id,
        final_url="https://www.instagram.com/reel/placement-one?utm_medium=social",
    )
    assert repeated.id == first.id
    with pytest.raises(CreatorOperationsError, match="placement_final_url_mismatch"):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=creator.id,
            task_id=creator_tasks[0].id,
            final_url="https://www.instagram.com/reel/different-post",
        )

    second_publication = db.get(
        models.PublishingTask,
        creator_tasks[1].publishing_task_id,
    )
    with pytest.raises(PublishingError, match="placement_final_url_already_used"):
        ManualUploadProvider(db).mark_published(
            second_publication,
            "https://instagram.com/reel/placement-one?utm_campaign=legacy-writer",
            "legacy-api",
        )

    with pytest.raises(CreatorOperationsError, match="placement_final_url_already_used"):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=creator_tasks[1].id,
            final_url="https://www.instagram.com/reel/placement-one?foo=another-value",
        )

    second = service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        task_id=creator_tasks[1].id,
        final_url="https://www.instagram.com/reel/placement-two",
    )
    db.refresh(batch)
    assert second.status == "done"
    assert batch.status == "completed"
    assert batch.completed_at is not None
    assert [item["status"] for item in batch.results_json] == ["done", "done"]
    assert {item["final_url"] for item in batch.results_json} == {
        "https://www.instagram.com/reel/placement-one",
        "https://www.instagram.com/reel/placement-two",
    }
    events = list(
        db.scalars(
            select(models.FactoryEvent)
            .where(models.FactoryEvent.event_name == "publication_completed")
            .order_by(models.FactoryEvent.id)
        )
    )
    assert len(events) == 2
    assert {item.publishing_task_id for item in events} == {
        item.publishing_task_id for item in creator_tasks
    }
    assert all(item.organization_id == organization.id and item.source == "server" for item in events)


def test_confirmed_placement_creates_idempotent_payout_and_manager_reconciles_it(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-payout",
        package_count=1,
    )
    service = CreatorOperationsService(db)
    batch = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[packages[0].id],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Paid placement",
        idempotency_key="placement:payout:0001",
        dry_run=False,
        payout_per_post_minor=25_050,
    )
    task = db.scalar(
        select(models.CreatorTask).where(models.CreatorTask.mass_operation_batch_id == batch.id)
    )

    service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=task.id,
        final_url="https://www.instagram.com/reel/paid-placement",
    )
    payouts = list(db.scalars(select(models.CreatorPayout)))
    assert len(payouts) == 1
    payout = payouts[0]
    assert payout.user_profile_id == creator.id
    assert payout.creator_task_id == task.id
    assert payout.publishing_task_id == task.publishing_task_id
    assert payout.amount_minor == 25_050
    assert payout.status == "pending"
    assert batch.parameters_json["payout_per_post_minor"] == 25_050

    service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=task.id,
        final_url="https://www.instagram.com/reel/paid-placement/",
    )
    assert db.scalar(select(func.count()).select_from(models.CreatorPayout)) == 1
    with pytest.raises(CreatorOperationsError, match="payout_manager_role_required"):
        service.decide_payout(
            organization_id=organization.id,
            actor_user_profile_id=creator.id,
            payout_id=payout.id,
            decision="approve",
        )

    approved = service.decide_payout(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        payout_id=payout.id,
        decision="approve",
    )
    assert approved.status == "approved"
    assert approved.approved_by_user_profile_id == owner.id
    assert approved.approved_at is not None
    paid = service.mark_payout_paid(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        payout_id=payout.id,
        external_payment_reference="PAY-2026-000123",
    )
    assert paid.status == "paid"
    assert paid.external_payment_reference == "PAY-2026-000123"
    assert paid.paid_at is not None
    assert service.mark_payout_paid(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        payout_id=payout.id,
        external_payment_reference="PAY-2026-000123",
    ).status == "paid"
    with pytest.raises(CreatorOperationsError, match="external_payment_reference_mismatch"):
        service.mark_payout_paid(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            payout_id=payout.id,
            external_payment_reference="PAY-2026-DIFFERENT",
        )


def test_performance_snapshot_uses_latest_metric_and_creator_scope(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="performance-main",
    )
    foreign_org, foreign_owner, _, foreign_packages, foreign_destination = _publishing_scope(
        db,
        tmp_path,
        slug="performance-foreign",
        package_count=1,
    )
    service = CreatorOperationsService(db)
    batch = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[item.id for item in packages],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id, owner.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Measured placement",
        idempotency_key="placement:metrics:0001",
        dry_run=False,
    )
    tasks = list(
        db.scalars(
            select(models.CreatorTask)
            .where(models.CreatorTask.mass_operation_batch_id == batch.id)
            .order_by(models.CreatorTask.id)
        )
    )
    for index, task in enumerate(tasks, start=1):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=task.assignee_user_profile_id,
            task_id=task.id,
            final_url=f"https://www.instagram.com/reel/measured-{index}",
        )
    service.record_manual_metrics(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=tasks[0].id,
        views=100,
        clicks=10,
        orders=1,
        revenue_minor=100_000,
    )
    latest_creator_metric = service.record_manual_metrics(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=tasks[0].id,
        views=250,
        clicks=25,
        orders=3,
        revenue_minor=350_050,
    )
    db.add_all(
        [
            models.DestinationPostMetric(
                destination_id=destination.id,
                publishing_task_id=tasks[1].publishing_task_id,
                product_id=packages[1].product_id,
                platform="instagram",
                posted_url="https://www.instagram.com/reel/measured-2",
                period_start=datetime(2026, 7, 1).date(),
                period_end=datetime(2026, 7, 5).date(),
                views=150,
                clicks=15,
                orders=1,
                revenue=1_500.0,
                raw_json={"ingestion_v1": {"canonical": True}},
            ),
            models.DestinationPostMetric(
                destination_id=destination.id,
                publishing_task_id=tasks[1].publishing_task_id,
                product_id=packages[1].product_id,
                platform="instagram",
                posted_url="https://www.instagram.com/reel/measured-2",
                period_start=datetime(2026, 7, 6).date(),
                period_end=datetime(2026, 7, 10).date(),
                views=250,
                clicks=25,
                orders=3,
                revenue=2_500.0,
                raw_json={"ingestion_v1": {"canonical": True}},
            ),
        ]
    )
    tracking_links = list(
        db.scalars(
            select(models.TrackingLink)
            .where(
                models.TrackingLink.publishing_task_id.in_(
                    [task.publishing_task_id for task in tasks]
                )
            )
            .order_by(models.TrackingLink.publishing_task_id)
        )
    )
    db.add_all(
        [
            models.TrackingClick(
                tracking_link_id=tracking_links[0].id,
                publishing_task_id=tasks[0].publishing_task_id,
                destination_id=destination.id,
                metadata_json={
                    "tracking_v1": {"accepted_for_human_kpi": True}
                },
            ),
            models.TrackingClick(
                tracking_link_id=tracking_links[0].id,
                publishing_task_id=tasks[0].publishing_task_id,
                destination_id=destination.id,
                metadata_json={
                    "tracking_v1": {"accepted_for_human_kpi": True}
                },
            ),
            models.TrackingClick(
                tracking_link_id=tracking_links[1].id,
                publishing_task_id=tasks[1].publishing_task_id,
                destination_id=destination.id,
                metadata_json={
                    "tracking_v1": {"accepted_for_human_kpi": False}
                },
            ),
        ]
    )
    db.commit()
    assert latest_creator_metric.raw_json["source"] == "manual_creator_cumulative_snapshot"
    foreign_batch = CreatorOperationsService(db).placement_batch(
        organization_id=foreign_org.id,
        actor_user_profile_id=foreign_owner.id,
        package_ids=[foreign_packages[0].id],
        destination_ids=[foreign_destination.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Foreign measured placement",
        idempotency_key="placement:metrics:foreign:0001",
        dry_run=False,
    )
    foreign_task = db.scalar(
        select(models.CreatorTask).where(
            models.CreatorTask.mass_operation_batch_id == foreign_batch.id
        )
    )
    CreatorOperationsService(db).complete_manual_placement(
        organization_id=foreign_org.id,
        actor_user_profile_id=foreign_owner.id,
        task_id=foreign_task.id,
        final_url="https://www.instagram.com/reel/foreign-measured",
    )
    CreatorOperationsService(db).record_manual_metrics(
        organization_id=foreign_org.id,
        actor_user_profile_id=foreign_owner.id,
        task_id=foreign_task.id,
        views=99_999,
        clicks=9_999,
        orders=999,
        revenue_minor=99_999_900,
    )
    foreign_link = db.scalar(
        select(models.TrackingLink).where(
            models.TrackingLink.publishing_task_id
            == foreign_task.publishing_task_id
        )
    )
    db.add(
        models.TrackingClick(
            tracking_link_id=foreign_link.id,
            publishing_task_id=foreign_task.publishing_task_id,
            destination_id=foreign_destination.id,
            metadata_json={
                "tracking_v1": {"accepted_for_human_kpi": True}
            },
        )
    )
    db.commit()

    assert service.performance_snapshot(
        organization_id=organization.id,
        viewer_user_profile_id=owner.id,
    ) == {
        "published_placements": 2,
        "tracking_clicks": 2,
        "tracking_clicks_raw": 3,
        "tracked_placements": 2,
        "views": 650,
        "clicks": 65,
        "orders": 7,
        "revenue": 7_500.5,
        "quarantined_metric_rows": 0,
    }
    assert service.performance_snapshot(
        organization_id=organization.id,
        viewer_user_profile_id=creator.id,
    ) == {
        "published_placements": 1,
        "tracking_clicks": 2,
        "tracking_clicks_raw": 2,
        "tracked_placements": 1,
        "views": 250,
        "clicks": 25,
        "orders": 3,
        "revenue": 3_500.5,
        "quarantined_metric_rows": 0,
    }

    # A monthly row overlapping both canonical weekly periods is ambiguous.
    # All three overlapping rows are quarantined instead of being summed.
    db.add(
        models.DestinationPostMetric(
            destination_id=destination.id,
            publishing_task_id=tasks[1].publishing_task_id,
            product_id=packages[1].product_id,
            platform="instagram",
            posted_url="https://www.instagram.com/reel/measured-2",
            period_start=datetime(2026, 7, 1).date(),
            period_end=datetime(2026, 7, 10).date(),
            views=500,
            clicks=50,
            orders=5,
            revenue=5_000.0,
            raw_json={"ingestion_v1": {"canonical": True}},
        )
    )
    db.commit()
    quarantined = service.performance_snapshot(
        organization_id=organization.id,
        viewer_user_profile_id=owner.id,
    )
    assert quarantined["quarantined_metric_rows"] == 3
    assert quarantined["tracked_placements"] == 1
    assert quarantined["views"] == 250
    assert quarantined["clicks"] == 25
    assert quarantined["orders"] == 3
    assert quarantined["revenue"] == 3_500.5


def test_manual_cumulative_metrics_require_manager_correction_for_decreases(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="manual-metric-correction",
        package_count=1,
    )
    service = CreatorOperationsService(db)
    batch = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[packages[0].id],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Metric correction",
        idempotency_key="placement:metric-correction:0001",
        dry_run=False,
    )
    task = db.scalar(
        select(models.CreatorTask).where(
            models.CreatorTask.mass_operation_batch_id == batch.id
        )
    )
    service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=task.id,
        final_url="https://www.instagram.com/reel/metric-correction",
    )
    service.record_manual_metrics(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=task.id,
        views=100,
        clicks=10,
        orders=2,
        revenue_minor=50_000,
    )
    with pytest.raises(
        CreatorOperationsError,
        match="manual_metrics_cumulative_decrease_requires_correction",
    ):
        service.record_manual_metrics(
            organization_id=organization.id,
            actor_user_profile_id=creator.id,
            task_id=task.id,
            views=90,
            clicks=10,
            orders=2,
            revenue_minor=50_000,
        )
    with pytest.raises(
        CreatorOperationsError,
        match="manual_metrics_correction_manager_required",
    ):
        service.record_manual_metrics(
            organization_id=organization.id,
            actor_user_profile_id=creator.id,
            task_id=task.id,
            views=90,
            clicks=10,
            orders=2,
            revenue_minor=50_000,
            allow_correction=True,
            correction_reason="Площадка исправила ошибочный счётчик.",
        )
    corrected = service.record_manual_metrics(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        task_id=task.id,
        views=90,
        clicks=10,
        orders=2,
        revenue_minor=50_000,
        allow_correction=True,
        correction_reason="Площадка исправила ошибочный счётчик.",
    )
    assert corrected.raw_json["cumulative_correction"]["confirmed"] is True
    assert corrected.raw_json["cumulative_correction"]["decreased_fields"] == [
        "views"
    ]


def test_manual_placement_requires_assignee_or_manager_and_destination_host(
    db: Session,
    tmp_path,
):
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-authorization",
        package_count=1,
    )
    outsider = models.UserProfile(
        supabase_user_id="creator:placement-outsider",
        email="outsider@placement.test",
        display_name="Outsider",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add(outsider)
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=outsider.id,
            role="producer",
            status="active",
            permissions_json=[],
        )
    )
    db.commit()
    service = CreatorOperationsService(db)
    with pytest.raises(CreatorOperationsError, match="assignee_final_exam_required"):
        service.placement_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            package_ids=[packages[0].id],
            destination_ids=[destination.id],
            assignee_user_profile_ids=[outsider.id],
            start_at=datetime.now(UTC) + timedelta(minutes=10),
            interval_minutes=5,
            name="Uncertified placement assignment",
            idempotency_key="placement:uncertified-assignee:0001",
            dry_run=False,
        )
    batch = service.placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[packages[0].id],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Authorized manual placement",
        idempotency_key="placement:authorization:0001",
        dry_run=False,
    )
    task = db.scalar(
        select(models.CreatorTask).where(models.CreatorTask.mass_operation_batch_id == batch.id)
    )

    with pytest.raises(CreatorOperationsError, match="placement_task_assignee_required"):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=outsider.id,
            task_id=task.id,
            final_url="https://www.instagram.com/reel/not-authorized",
        )
    with pytest.raises(CreatorOperationsError, match="placement_final_url_host_mismatch"):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            final_url="https://evil.example/reel/wrong-host",
        )
    with pytest.raises(CreatorOperationsError, match="placement_final_url_invalid"):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            final_url="http://www.instagram.com/reel/not-https",
        )

    db.refresh(task)
    publication = db.get(models.PublishingTask, task.publishing_task_id)
    assert task.status == "todo"
    assert publication.status == "scheduled"
    assert publication.final_url is None
    assert batch.status == "queued"

    completed = service.complete_manual_placement(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        task_id=task.id,
        final_url="https://www.instagram.com/reel/manager-override",
    )
    assert completed.status == "done"
    with pytest.raises(CreatorOperationsError, match="placement_task_assignee_required"):
        service.record_manual_metrics(
            organization_id=organization.id,
            actor_user_profile_id=outsider.id,
            task_id=task.id,
            views=1,
            clicks=0,
            orders=0,
            revenue_minor=0,
        )


def test_placement_default_assignee_remains_the_actor_for_existing_callers(
    db: Session,
    tmp_path,
):
    organization, owner, _creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-default-assignee",
        package_count=1,
    )

    batch = CreatorOperationsService(db).placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[packages[0].id],
        destination_ids=[destination.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="Default actor assignment",
        idempotency_key="placement:default-assignee:0001",
        dry_run=False,
    )

    task = db.scalar(
        select(models.CreatorTask).where(models.CreatorTask.mass_operation_batch_id == batch.id)
    )
    assert batch.parameters_json["assignee_user_profile_ids"] == [owner.id]
    assert task.assignee_user_profile_id == owner.id


def test_complete_placement_route_requires_session_bound_csrf(
    db: Session,
    tmp_path,
    monkeypatch,
):
    previous_auth_required = get_settings().auth_required
    monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    organization, owner, creator, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-route-csrf",
        package_count=1,
    )
    batch = CreatorOperationsService(db).placement_batch(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        package_ids=[packages[0].id],
        destination_ids=[destination.id],
        assignee_user_profile_ids=[creator.id],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
        interval_minutes=5,
        name="CSRF protected placement",
        idempotency_key="placement:route-csrf:0001",
        dry_run=False,
    )
    task = db.scalar(
        select(models.CreatorTask).where(models.CreatorTask.mass_operation_batch_id == batch.id)
    )
    membership = db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == creator.id,
        )
    )
    current_user = PublicPilotUser(
        profile=creator,
        organization=organization,
        membership=membership,
    )

    def local_db():
        with TestSession() as session:
            yield session

    api = FastAPI()
    api.include_router(creator_operations_router.router)
    api.dependency_overrides[get_db] = local_db
    api.dependency_overrides[get_current_public_user] = lambda: current_user
    client = TestClient(api, follow_redirects=False)
    session_token = "creator-placement-session"
    client.cookies.set(get_settings().session_cookie_name, session_token)
    try:
        rejected = client.post(
            f"/creator-operations/tasks/{task.id}/complete-placement",
            data={
                "csrf_token": "wrong-token",
                "final_url": "https://www.instagram.com/reel/csrf-protected",
            },
        )
        assert rejected.status_code == 403
        with TestSession() as check_db:
            assert check_db.get(models.CreatorTask, task.id).status == "todo"

        csrf_token = hmac.new(
            b"qvf-public-pilot-form-csrf-v1",
            session_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        completed = client.post(
            f"/creator-operations/tasks/{task.id}/complete-placement",
            data={
                "csrf_token": csrf_token,
                "final_url": "https://www.instagram.com/reel/csrf-protected",
            },
        )
        assert completed.status_code == 303
        assert completed.headers["location"] == (
            f"/creator-operations?tab=tasks&notice=task_{task.id}_done"
        )
        with TestSession() as check_db:
            assert check_db.get(models.CreatorTask, task.id).status == "done"
    finally:
        client.close()
        if previous_auth_required:
            monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
        else:
            monkeypatch.setenv("QVF_AUTH_REQUIRED", "false")
        get_settings.cache_clear()


def test_placement_rejects_unowned_packages_and_schedule_beyond_horizon(db: Session, tmp_path):
    organization, owner, _, packages, destination = _publishing_scope(
        db,
        tmp_path,
        slug="placement-boundaries",
    )
    service = CreatorOperationsService(db)
    packages[0].organization_id = None
    db.commit()

    with pytest.raises(CreatorOperationsError, match="publishing_package_not_found"):
        service.placement_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            package_ids=[packages[0].id],
            destination_ids=[destination.id],
            start_at=datetime.now(UTC) + timedelta(minutes=10),
            interval_minutes=5,
            name="Unowned package",
            idempotency_key="placement:unowned-package:0001",
            dry_run=True,
        )

    packages[0].organization_id = organization.id
    db.commit()
    with pytest.raises(CreatorOperationsError, match="schedule_exceeds_180_day_horizon"):
        service.placement_batch(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            package_ids=[item.id for item in packages],
            destination_ids=[destination.id],
            start_at=datetime.now(UTC) + timedelta(days=175),
            interval_minutes=10_080,
            name="Schedule beyond horizon",
            idempotency_key="placement:beyond-horizon:0001",
            dry_run=True,
        )


def test_creator_operations_forms_keep_csrf_idempotency_and_credit_confirmation():
    template = (
        Path(__file__).parents[1]
        / "app"
        / "templates"
        / "creator_operations.html"
    ).read_text(encoding="utf-8")
    router = (
        Path(__file__).parents[1]
        / "app"
        / "routers"
        / "creator_operations.py"
    ).read_text(encoding="utf-8")

    assert template.count('name="csrf_token"') >= 4
    assert template.count('name="idempotency_key"') >= 2
    assert 'name="assignee_user_profile_ids"' in template
    assert 'action="/creator-operations/tasks/{{ task.id }}/complete-placement"' in template
    assert 'name="final_url" type="url"' in template
    assert '@router.post("/tasks/{task_id}/complete-placement")' in router
    assert '@router.post("/tasks/{task_id}/metrics")' in router
    assert '@router.post("/payouts/{payout_id}/decision")' in router
    assert '@router.post("/payouts/{payout_id}/paid")' in router
    assert "require_form_csrf(request, csrf_token)" in router
    assert 'name="payout_per_post_rub"' in template
    assert 'name="external_payment_reference"' in template
    assert 'name="revenue_rub"' in template
    assert "manual_upload" in template and "tracking_link" in template
    assert 'name="confirmed_total_credits"' in template
    assert 'name="quantity"' in template and 'max="50"' in template
    assert (
        'name="confirmed_total_credits" type="number" min="0" '
        'max="{{ mass_generation_credit_limit }}"'
    ) in template
    assert '"mass_generation_credit_limit": service.settings.mass_generation_credit_limit' in router
    assert 'mode not in {"dry_run", "enqueue"}' in router
    assert 'mode not in {"dry_run", "schedule"}' in router
    assert "HTTPS-ссылку на карточку товара" in creator_operations_router._flash(
        "tracking_target_url_required"
    )
    assert "проверена без расходов" in creator_operations_router._flash(
        "batch_42_validated"
    )


def test_task_and_payout_views_are_personal_for_non_admins(db: Session):
    organization, owner, creator, product, _ = _scope(db, "inbox")
    second = models.UserProfile(
        supabase_user_id="creator:second",
        email="second@inbox.test",
        display_name="Second",
        status="active",
        is_active=True,
        metadata_json={},
    )
    db.add(second)
    db.flush()
    db.add(
        models.Membership(
            organization_id=organization.id,
            user_profile_id=second.id,
            role="producer",
            status="active",
            permissions_json=[],
        )
    )
    for index, assignee in enumerate((creator, second), start=1):
        task = models.CreatorTask(
            organization_id=organization.id,
            assignee_user_profile_id=assignee.id,
            created_by_user_profile_id=owner.id,
            product_id=product.id,
            task_type="create_video",
            title=f"Task {index}",
            status="todo",
            priority=3,
            checklist_json=[],
            result_json={},
            blockers_json=[],
            idempotency_key=f"task:inbox:{index:04d}",
        )
        db.add(task)
        db.flush()
        db.add(
            models.CreatorPayout(
                organization_id=organization.id,
                user_profile_id=assignee.id,
                creator_task_id=task.id,
                amount_minor=10_000 * index,
                currency="RUB",
                status="pending",
                idempotency_key=f"payout:inbox:{index:04d}",
            )
        )
    db.commit()

    service = CreatorOperationsService(db)
    assert [item.assignee_user_profile_id for item in service.task_inbox(
        organization_id=organization.id, viewer_user_profile_id=creator.id
    )] == [creator.id]
    assert [item.user_profile_id for item in service.payout_ledger(
        organization_id=organization.id, viewer_user_profile_id=creator.id
    )] == [creator.id]
    assert len(service.task_inbox(organization_id=organization.id, viewer_user_profile_id=owner.id)) == 2
    assert len(service.payout_ledger(organization_id=organization.id, viewer_user_profile_id=owner.id)) == 2


def test_workload_totals_are_not_truncated_by_creator_page_limits(db: Session):
    organization, owner, creator, product, _ = _scope(db, "workload-pagination")
    for index in range(251):
        task = models.CreatorTask(
            organization_id=organization.id,
            assignee_user_profile_id=creator.id,
            created_by_user_profile_id=owner.id,
            product_id=product.id,
            task_type="manual_placement",
            title=f"Placement {index}",
            status="done" if index < 50 else "todo",
            priority=3,
            idempotency_key=f"workload-task-{index:04d}",
        )
        db.add(task)
        db.flush()
        db.add(
            models.CreatorPayout(
                organization_id=organization.id,
                user_profile_id=creator.id,
                creator_task_id=task.id,
                amount_minor=100,
                currency="RUB",
                status="paid" if index < 51 else "pending",
                idempotency_key=f"workload-payout-{index:04d}",
            )
        )
    db.commit()
    service = CreatorOperationsService(db)

    assert service.workload_snapshot(
        organization_id=organization.id,
        viewer_user_profile_id=owner.id,
    ) == {
        "tasks_open": 201,
        "tasks_done": 50,
        "tasks_cancelled": 0,
        "tasks_closed": 50,
        "payout_pending_minor": 20_000,
        "payout_paid_minor": 5_100,
    }
    assert len(
        service.task_inbox(
            organization_id=organization.id,
            viewer_user_profile_id=owner.id,
            limit=50,
            offset=250,
        )
    ) == 1
    assert len(
        service.payout_ledger(
            organization_id=organization.id,
            viewer_user_profile_id=owner.id,
            limit=50,
            offset=250,
        )
    ) == 1


def _review_task(db: Session, slug: str):
    organization, owner, creator, product, draft = _scope(db, slug)
    artifact = models.MediaArtifact(
        public_id=f"artifact-{slug}",
        idempotency_key=f"artifact-{slug}",
        organization_id=organization.id,
        created_by_user_profile_id=creator.id,
        product_id=product.id,
        product_ugc_recipe_draft_id=draft.id,
        kind="master_video",
        backend_name="local",
        bucket="private-media",
        object_key=f"organizations/{organization.id:08d}/videos/{slug}.mp4",
        mime_type="video/mp4",
        size_bytes=128,
        sha256="a" * 64,
        status="ready",
        metadata_json={},
        retention_class="master_365d",
    )
    db.add(artifact)
    db.flush()
    task = models.CreatorTask(
        organization_id=organization.id,
        assignee_user_profile_id=creator.id,
        created_by_user_profile_id=owner.id,
        product_id=product.id,
        product_ugc_recipe_draft_id=draft.id,
        media_artifact_id=artifact.id,
        task_type="review_generated_video",
        title="Review generated video",
        status="todo",
        priority=3,
        idempotency_key=f"review-task-{slug}",
    )
    db.add(task)
    db.commit()
    return organization, owner, creator, draft, artifact, task


def _review_identity(artifact: models.MediaArtifact) -> dict[str, object]:
    return {
        "expected_media_artifact_id": artifact.id,
        "expected_media_artifact_public_id": artifact.public_id,
        "expected_media_artifact_sha256": artifact.sha256,
    }


def _replacement_review_artifact(
    db: Session,
    source: models.MediaArtifact,
    *,
    slug: str,
    sha256: str,
) -> models.MediaArtifact:
    artifact = models.MediaArtifact(
        public_id=f"artifact-{slug}",
        idempotency_key=f"artifact-{slug}",
        organization_id=source.organization_id,
        created_by_user_profile_id=source.created_by_user_profile_id,
        product_id=source.product_id,
        product_ugc_recipe_draft_id=source.product_ugc_recipe_draft_id,
        kind="master_video",
        backend_name="local",
        bucket="private-media",
        object_key=(
            f"organizations/{source.organization_id:08d}/videos/{slug}.mp4"
        ),
        mime_type="video/mp4",
        size_bytes=256,
        sha256=sha256,
        status="ready",
        metadata_json={},
        retention_class="master_365d",
    )
    db.add(artifact)
    db.flush()
    return artifact


def test_assigned_creator_can_approve_ready_video_and_open_placement_gate(db: Session):
    organization, _owner, creator, draft, artifact, task = _review_task(db, "approve-video")

    reviewed = CreatorOperationsService(db).review_generated_task(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=task.id,
        **_review_identity(artifact),
        decision="approve",
        notes="SKU, packaging, claims and platform rules verified.",
        confirm_video_watched=True,
    )

    db.refresh(draft)
    assert reviewed.status == "done"
    assert reviewed.media_artifact_id == artifact.id
    assert reviewed.result_json["review_decision"] == "approve"
    assert reviewed.result_json["media_artifact_id"] == artifact.id
    assert reviewed.result_json["media_artifact_public_id"] == artifact.public_id
    assert reviewed.result_json["media_artifact_sha256"] == artifact.sha256
    assert draft.human_review_status == "approved"
    assert draft.publishing_readiness == "ready_for_publishing_package"


def test_review_refuses_stale_artifact_pointer_before_recording_decision(db: Session):
    organization, owner, _creator, draft, viewed_artifact, task = _review_task(
        db,
        "stale-review-pointer",
    )
    viewed_identity = _review_identity(viewed_artifact)
    replacement = _replacement_review_artifact(
        db,
        viewed_artifact,
        slug="stale-review-pointer-worker-output",
        sha256="b" * 64,
    )
    task.media_artifact_id = replacement.id
    db.commit()

    with pytest.raises(CreatorOperationsError, match="review_video_identity_mismatch"):
        CreatorOperationsService(db).review_generated_task(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            **viewed_identity,
            decision="approve",
            notes="The previously opened MP4 looked correct to the reviewer.",
            confirm_video_watched=True,
        )

    db.refresh(task)
    db.refresh(draft)
    assert task.status == "todo"
    assert task.result_json == {}
    assert draft.human_review_status == "not_generated"
    assert draft.publishing_readiness == "blocked"


def test_review_refuses_stale_content_hash_before_recording_decision(db: Session):
    organization, owner, _creator, draft, artifact, task = _review_task(
        db,
        "stale-review-hash",
    )
    viewed_identity = _review_identity(artifact)
    artifact.sha256 = "c" * 64
    db.commit()

    with pytest.raises(CreatorOperationsError, match="review_video_identity_mismatch"):
        CreatorOperationsService(db).review_generated_task(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            **viewed_identity,
            decision="reject",
            notes="The previously opened MP4 had a packaging mismatch.",
            confirm_video_watched=True,
        )

    db.refresh(task)
    db.refresh(draft)
    assert task.status == "todo"
    assert task.result_json == {}
    assert draft.human_review_status == "not_generated"
    assert draft.creative_inputs_json.get("blocked_media_artifacts_v1") is None


def test_rejection_requires_new_artifact_before_approval(db: Session):
    organization, owner, _creator, draft, artifact, task = _review_task(db, "reject-video")
    service = CreatorOperationsService(db)

    with pytest.raises(CreatorOperationsError, match="rejection_reason_too_short"):
        service.review_generated_task(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            **_review_identity(artifact),
            decision="reject",
            notes="bad",
            confirm_video_watched=True,
        )

    reviewed = service.review_generated_task(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        task_id=task.id,
        **_review_identity(artifact),
        decision="reject",
        notes="Packaging text does not match the approved product reference.",
        confirm_video_watched=True,
    )
    db.refresh(draft)
    assert reviewed.status == "blocked"
    assert reviewed.blockers_json[0]["code"] == "human_review_changes_requested"
    assert draft.human_review_status == "changes_requested"
    assert draft.publishing_readiness == "blocked"
    assert draft.creative_inputs_json["blocked_media_artifacts_v1"][0][
        "media_artifact_id"
    ] == artifact.id

    with pytest.raises(
        CreatorOperationsError,
        match="review_rejected_artifact_requires_regeneration",
    ):
        service.review_generated_task(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            **_review_identity(artifact),
            decision="approve",
            notes="Trying to approve the same rejected bytes.",
            confirm_video_watched=True,
        )

    replacement = models.MediaArtifact(
        public_id="artifact-reject-video-replacement",
        idempotency_key="artifact-reject-video-replacement",
        organization_id=organization.id,
        created_by_user_profile_id=owner.id,
        product_id=artifact.product_id,
        product_ugc_recipe_draft_id=draft.id,
        kind="master_video",
        backend_name="local",
        bucket="private-media",
        object_key=(
            f"organizations/{organization.id:08d}/videos/reject-video-replacement.mp4"
        ),
        mime_type="video/mp4",
        size_bytes=256,
        sha256="b" * 64,
        status="ready",
        metadata_json={},
        retention_class="master_365d",
    )
    db.add(replacement)
    db.flush()
    task.media_artifact_id = replacement.id
    task.status = "todo"
    task.blockers_json = []
    db.commit()

    approved = service.review_generated_task(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        task_id=task.id,
        **_review_identity(replacement),
        decision="approve",
        notes="Replacement bytes match the SKU, claims and platform rules.",
        confirm_video_watched=True,
    )
    db.refresh(draft)
    assert approved.status == "done"
    assert draft.creative_inputs_json["approved_media_artifact_v1"][
        "media_artifact_id"
    ] == replacement.id


def test_review_and_payout_routes_forward_only_their_own_form_fields(
    db: Session,
    monkeypatch,
):
    previous_auth_required = get_settings().auth_required
    monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    organization, owner, creator, _draft, review_artifact, review_task = _review_task(
        db,
        "route-field-contract",
    )
    payout_task = models.CreatorTask(
        organization_id=organization.id,
        assignee_user_profile_id=creator.id,
        created_by_user_profile_id=owner.id,
        product_id=review_task.product_id,
        task_type="manual_placement",
        title="Payout route task",
        status="done",
        priority=3,
        idempotency_key="payout-route-task",
    )
    db.add(payout_task)
    db.flush()
    payout = models.CreatorPayout(
        organization_id=organization.id,
        user_profile_id=creator.id,
        creator_task_id=payout_task.id,
        amount_minor=1_000,
        currency="RUB",
        status="pending",
        idempotency_key="payout-route-entry",
    )
    db.add(payout)
    db.commit()
    membership = db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == owner.id,
        )
    )
    current_user = PublicPilotUser(
        profile=owner,
        organization=organization,
        membership=membership,
    )

    def local_db():
        with TestSession() as session:
            yield session

    api = FastAPI()
    api.mount("/static", StaticFiles(directory="app/static"), name="static")
    api.include_router(creator_operations_router.router)
    api.dependency_overrides[get_db] = local_db
    api.dependency_overrides[get_current_public_user] = lambda: current_user
    client = TestClient(api, follow_redirects=False)
    session_token = "review-payout-route-session"
    client.cookies.set(get_settings().session_cookie_name, session_token)
    csrf_token = hmac.new(
        b"qvf-public-pilot-form-csrf-v1",
        session_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    try:
        tasks_page = client.get("/creator-operations?tab=tasks")
        assert tasks_page.status_code == 200
        assert (
            f'name="expected_media_artifact_id" value="{review_artifact.id}"'
            in tasks_page.text
        )
        assert (
            'name="expected_media_artifact_public_id" '
            f'value="{review_artifact.public_id}"' in tasks_page.text
        )
        assert (
            'name="expected_media_artifact_sha256" '
            f'value="{review_artifact.sha256}"' in tasks_page.text
        )
        missing_identity = client.post(
            f"/creator-operations/tasks/{review_task.id}/review",
            data={
                "csrf_token": csrf_token,
                "decision": "approve",
                "notes": "SKU and claims were checked completely.",
                "confirm_video_watched": "true",
            },
        )
        assert missing_identity.status_code == 422
        missing_watch = client.post(
            f"/creator-operations/tasks/{review_task.id}/review",
            data={
                "csrf_token": csrf_token,
                **_review_identity(review_artifact),
                "decision": "approve",
                "notes": "SKU and claims were checked completely.",
            },
        )
        assert missing_watch.status_code == 303
        assert "video_review_watch_confirmation_required" in missing_watch.headers[
            "location"
        ]
        approved_review = client.post(
            f"/creator-operations/tasks/{review_task.id}/review",
            data={
                "csrf_token": csrf_token,
                **_review_identity(review_artifact),
                "decision": "approve",
                "notes": "SKU and claims were checked completely.",
                "confirm_video_watched": "true",
            },
        )
        assert approved_review.status_code == 303
        approved_payout = client.post(
            f"/creator-operations/payouts/{payout.id}/decision",
            data={
                "csrf_token": csrf_token,
                "decision": "approve",
                "notes": "",
            },
        )
        assert approved_payout.status_code == 303
        with TestSession() as check_db:
            assert check_db.get(models.CreatorTask, review_task.id).status == "done"
            assert check_db.get(models.CreatorPayout, payout.id).status == "approved"
    finally:
        client.close()
        if previous_auth_required:
            monkeypatch.setenv("QVF_AUTH_REQUIRED", "true")
        else:
            monkeypatch.setenv("QVF_AUTH_REQUIRED", "false")
        get_settings.cache_clear()
