from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import get_settings
from app.creator_operations import CreatorOperationsError, CreatorOperationsService
from app.database import Base, get_db
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
    organization, owner, _, product, _ = _scope(db, slug)
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
    return organization, owner, product, packages, destination


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
    assert len({item.variant_key for item in clones}) == 3
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
    assert len(placement_tasks) == 2
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
        final_url="https://WWW.INSTAGRAM.COM/reel/placement-one/",
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
        final_url="https://www.instagram.com/reel/placement-one/",
    )
    assert repeated.id == first.id
    with pytest.raises(CreatorOperationsError, match="placement_final_url_mismatch"):
        service.complete_manual_placement(
            organization_id=organization.id,
            actor_user_profile_id=creator.id,
            task_id=creator_tasks[0].id,
            final_url="https://www.instagram.com/reel/different-post",
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
    assert "require_form_csrf(request, csrf_token)" in router
    assert 'name="confirmed_total_credits"' in template
    assert 'name="quantity"' in template and 'max="50"' in template
    assert 'name="confirmed_total_credits" type="number" min="0" max="500"' in template
    assert 'mode not in {"dry_run", "enqueue"}' in router
    assert 'mode not in {"dry_run", "schedule"}' in router


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


def test_assigned_creator_can_approve_ready_video_and_open_placement_gate(db: Session):
    organization, _owner, creator, draft, artifact, task = _review_task(db, "approve-video")

    reviewed = CreatorOperationsService(db).review_generated_task(
        organization_id=organization.id,
        actor_user_profile_id=creator.id,
        task_id=task.id,
        decision="approve",
        notes="SKU, packaging, claims and platform rules verified.",
    )

    db.refresh(draft)
    assert reviewed.status == "done"
    assert reviewed.media_artifact_id == artifact.id
    assert reviewed.result_json["review_decision"] == "approve"
    assert draft.human_review_status == "approved"
    assert draft.publishing_readiness == "ready_for_publishing_package"


def test_rejection_requires_actionable_reason_and_blocks_placement(db: Session):
    organization, owner, _creator, draft, _artifact, task = _review_task(db, "reject-video")
    service = CreatorOperationsService(db)

    with pytest.raises(CreatorOperationsError, match="rejection_reason_too_short"):
        service.review_generated_task(
            organization_id=organization.id,
            actor_user_profile_id=owner.id,
            task_id=task.id,
            decision="reject",
            notes="bad",
        )

    reviewed = service.review_generated_task(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        task_id=task.id,
        decision="reject",
        notes="Packaging text does not match the approved product reference.",
    )
    db.refresh(draft)
    assert reviewed.status == "blocked"
    assert reviewed.blockers_json[0]["code"] == "human_review_changes_requested"
    assert draft.human_review_status == "changes_requested"
    assert draft.publishing_readiness == "blocked"
