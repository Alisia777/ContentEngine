from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, _ensure_generation_cost_ledger_schema
from app.generation_costs import (
    GenerationCostConflictError,
    GenerationCostLedgerService,
    GenerationCostOwnershipError,
    GenerationCostValidationError,
)


@pytest.fixture()
def db() -> Session:
    local_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(local_engine)
    factory = sessionmaker(bind=local_engine, expire_on_commit=False)
    with factory() as session:
        yield session
    local_engine.dispose()


def make_org(db: Session, slug: str) -> tuple[models.Organization, models.UserProfile, models.Product]:
    organization = models.Organization(name=slug.title(), slug=slug)
    profile = models.UserProfile(
        supabase_user_id=f"generation-cost:{slug}",
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
    product = models.Product(
        organization_id=organization.id,
        sku=f"COST-{slug.upper()}",
        brand="Cost Test",
        title="Traceable generation cost",
    )
    db.add(product)
    db.commit()
    return organization, profile, product


def make_video_job(
    db: Session,
    organization: models.Organization,
    product: models.Product,
    *,
    provider: str = "runway",
    provider_job_id: str | None = None,
    status: str = "video_generated",
    output_path: str | None = "/media/real-output.mp4",
) -> models.VideoJob:
    job = models.VideoJob(
        script_variant_id=10_000 + organization.id,
        organization_id=organization.id,
        product_id=product.id,
        provider=provider,
        status=status,
        output_video_path=output_path,
    )
    db.add(job)
    db.flush()
    if provider_job_id:
        db.add(
            models.VideoClip(
                video_job_id=job.id,
                scene_id=20_000 + job.id,
                provider_job_id=provider_job_id,
                status="completed",
            )
        )
    db.commit()
    db.refresh(job)
    return job


def approve_video(db: Session, job: models.VideoJob, product: models.Product) -> None:
    brief = models.AIProductionBrief(
        product_id=product.id,
        sku=product.sku,
        status="ready_for_output_review",
    )
    db.add(brief)
    db.flush()
    db.add(
        models.VideoOutputAcceptance(
            video_job_id=job.id,
            ai_production_brief_id=brief.id,
            status="approved",
            product_identity_status="pass",
            packaging_status="pass",
            geometry_status="pass",
            blogger_authenticity_status="pass",
            scene_match_status="pass",
            proof_moment_status="pass",
            cta_status="pass",
            publishing_readiness="ready",
            blockers_json=[],
            reviewer_notes="Human checked the exact decoded product video.",
        )
    )
    db.commit()


def test_sqlite_migration_creates_generation_cost_ledger_with_safe_columns() -> None:
    local_engine = create_engine("sqlite://")
    _ensure_generation_cost_ledger_schema(local_engine)
    schema = inspect(local_engine)

    assert "generation_cost_ledger_entries" in schema.get_table_names()
    columns = {column["name"] for column in schema.get_columns("generation_cost_ledger_entries")}
    assert {
        "organization_id",
        "video_job_id",
        "provider_job_id",
        "provider",
        "cost_scope",
        "cost_unit_key",
        "revision",
        "amount_minor",
        "currency",
        "entry_kind",
        "status",
        "source",
        "external_reference",
        "idempotency_key",
        "supersedes_entry_id",
        "recorded_by_user_profile_id",
        "occurred_at",
        "recorded_at",
    }.issubset(columns)
    unique_names = {item["name"] for item in schema.get_unique_constraints("generation_cost_ledger_entries")}
    assert "uq_generation_cost_idempotency_key" in unique_names
    assert "uq_generation_cost_unit_revision" in unique_names
    with local_engine.connect() as connection:
        trigger_names = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND tbl_name = 'generation_cost_ledger_entries'"
            )
        }
    assert trigger_names == {
        "generation_cost_ledger_no_update",
        "generation_cost_ledger_no_delete",
    }
    local_engine.dispose()


def test_record_is_idempotent_and_key_reuse_with_another_fact_is_blocked(db: Session) -> None:
    organization, profile, product = make_org(db, "idempotent-cost")
    job = make_video_job(db, organization, product, provider_job_id="runway-task-idempotent")
    service = GenerationCostLedgerService(db)

    created = service.record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-task-idempotent",
        amount_minor=1_250,
        currency="usd",
        entry_kind="estimated",
        status="pending",
        source="internal_estimate",
        idempotency_key="cost:runway-task-idempotent:estimate:v1",
        recorded_by_user_profile_id=profile.id,
    )
    replay = service.record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-task-idempotent",
        amount_minor=1_250,
        currency="USD",
        entry_kind="estimated",
        status="pending",
        source="internal_estimate",
        idempotency_key="cost:runway-task-idempotent:estimate:v1",
        recorded_by_user_profile_id=profile.id,
    )

    assert created.created is True
    assert replay.created is False
    assert replay.entry.id == created.entry.id
    assert created.entry.amount_minor == 1_250
    assert created.entry.currency == "USD"
    assert created.entry.revision == 1
    assert db.scalar(select(func.count()).select_from(models.GenerationCostLedgerEntry)) == 1

    with pytest.raises(GenerationCostConflictError, match="Idempotency key"):
        service.record(
            organization_id=organization.id,
            video_job_id=job.id,
            provider_job_id="runway-task-idempotent",
            amount_minor=9_999,
            currency="USD",
            entry_kind="estimated",
            status="pending",
            source="internal_estimate",
            idempotency_key="cost:runway-task-idempotent:estimate:v1",
            recorded_by_user_profile_id=profile.id,
        )


def test_estimate_actual_and_immutable_correction_are_not_double_counted(db: Session) -> None:
    organization, profile, product = make_org(db, "corrected-cost")
    job = make_video_job(db, organization, product, provider_job_id="runway-task-corrected")
    service = GenerationCostLedgerService(db)
    estimate = service.record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-task-corrected",
        amount_minor=1_000,
        currency="USD",
        entry_kind="estimated",
        status="pending",
        source="internal_estimate",
        idempotency_key="cost:corrected:estimate:v1",
        recorded_by_user_profile_id=profile.id,
    ).entry
    actual = service.record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-task-corrected",
        amount_minor=800,
        currency="USD",
        entry_kind="actual",
        status="confirmed",
        source="provider_api",
        idempotency_key="cost:corrected:actual:v1",
        external_reference="runway/invoice/item-1",
    ).entry

    first = service.aggregate(organization_id=organization.id)[0]
    assert first.estimated_cost_minor == 1_000
    assert first.confirmed_actual_cost_minor == 800
    assert first.recognized_cost_minor == 800
    assert first.cost_per_generated_video_minor == Decimal("800.00")

    with pytest.raises(GenerationCostConflictError, match="supersedes_entry_id"):
        service.record(
            organization_id=organization.id,
            video_job_id=job.id,
            provider_job_id="runway-task-corrected",
            amount_minor=900,
            currency="USD",
            entry_kind="actual",
            status="confirmed",
            source="invoice_import",
            idempotency_key="cost:corrected:actual:unsafe-parallel",
        )

    corrected = service.record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-task-corrected",
        amount_minor=900,
        currency="USD",
        entry_kind="actual",
        status="confirmed",
        source="invoice_import",
        idempotency_key="cost:corrected:actual:v2",
        supersedes_entry_id=actual.id,
        external_reference="runway/invoice/item-1-revised",
    ).entry
    aggregate = service.aggregate(organization_id=organization.id)[0]

    assert corrected.revision == 2
    assert corrected.supersedes_entry_id == actual.id
    assert aggregate.effective_entry_count == 2
    assert aggregate.estimated_cost_minor == 1_000
    assert aggregate.confirmed_actual_cost_minor == 900
    assert aggregate.recognized_cost_minor == 900
    assert db.scalar(select(func.count()).select_from(models.GenerationCostLedgerEntry)) == 3
    assert estimate.id != actual.id != corrected.id


def test_mock_cross_org_unlinked_provider_and_manual_entries_fail_closed(db: Session) -> None:
    first_org, first_profile, first_product = make_org(db, "first-cost-org")
    second_org, _, _ = make_org(db, "second-cost-org")
    real_job = make_video_job(
        db,
        first_org,
        first_product,
        provider_job_id="runway-owned-task",
    )
    mock_job = make_video_job(
        db,
        first_org,
        first_product,
        provider="mock",
        provider_job_id="mock-task",
    )
    service = GenerationCostLedgerService(db)

    common = dict(
        amount_minor=100,
        currency="USD",
        entry_kind="actual",
        status="confirmed",
        source="provider_api",
    )
    with pytest.raises(GenerationCostOwnershipError, match="not owned"):
        service.record(
            organization_id=second_org.id,
            video_job_id=real_job.id,
            provider_job_id="runway-owned-task",
            idempotency_key="cost:cross-org:blocked",
            **common,
        )
    with pytest.raises(GenerationCostValidationError, match="Mock"):
        service.record(
            organization_id=first_org.id,
            video_job_id=mock_job.id,
            provider_job_id="mock-task",
            idempotency_key="cost:mock:blocked",
            **common,
        )
    with pytest.raises(GenerationCostOwnershipError, match="not explicitly linked"):
        service.record(
            organization_id=first_org.id,
            video_job_id=real_job.id,
            provider_job_id="runway-someone-elses-task",
            idempotency_key="cost:unlinked-provider:blocked",
            **common,
        )
    with pytest.raises(GenerationCostValidationError, match="requires an organization member"):
        service.record(
            organization_id=first_org.id,
            video_job_id=real_job.id,
            provider_job_id="runway-owned-task",
            amount_minor=100,
            currency="USD",
            entry_kind="actual",
            status="confirmed",
            source="manual_reconciliation",
            idempotency_key="cost:manual:no-actor",
        )

    accepted = service.record(
        organization_id=first_org.id,
        video_job_id=real_job.id,
        provider_job_id="runway-owned-task",
        amount_minor=100,
        currency="USD",
        entry_kind="actual",
        status="confirmed",
        source="manual_reconciliation",
        idempotency_key="cost:manual:owned-actor",
        recorded_by_user_profile_id=first_profile.id,
    )
    assert accepted.created


def test_video_job_and_provider_job_scopes_cannot_be_mixed(db: Session) -> None:
    organization, profile, product = make_org(db, "scope-cost")
    job = make_video_job(db, organization, product, provider_job_id="runway-task-scope")
    service = GenerationCostLedgerService(db)
    service.record(
        organization_id=organization.id,
        video_job_id=job.id,
        amount_minor=700,
        currency="RUB",
        entry_kind="estimated",
        status="pending",
        source="internal_estimate",
        idempotency_key="cost:scope:video",
        recorded_by_user_profile_id=profile.id,
    )

    with pytest.raises(GenerationCostConflictError, match="cannot be mixed"):
        service.record(
            organization_id=organization.id,
            video_job_id=job.id,
            provider_job_id="runway-task-scope",
            amount_minor=650,
            currency="RUB",
            entry_kind="actual",
            status="confirmed",
            source="provider_api",
            idempotency_key="cost:scope:provider",
        )


def test_canonical_product_ugc_provider_task_is_an_explicit_cost_unit(db: Session) -> None:
    organization, _, product = make_org(db, "canonical-cost")
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        sku=product.sku,
        status="approved",
        character_image_path="/media/creator.png",
        character_image_filename="creator.png",
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_info="Exact owned product",
        user_concept="Creator demonstrates the product",
        provider_task_id="runway-canonical-provider-task",
        provider_status="SUCCEEDED",
        local_output_paths_json=["/media/canonical.mp4"],
        human_review_status="approved",
        publishing_readiness="ready_for_package",
    )
    db.add(draft)
    db.flush()
    job = models.VideoJob(
        script_variant_id=42_000,
        organization_id=organization.id,
        product_id=product.id,
        source_product_ugc_draft_id=draft.id,
        provider="runway_product_ugc_recipe",
        status="video_generated",
        output_video_path="/media/canonical.mp4",
    )
    db.add(job)
    db.commit()

    result = GenerationCostLedgerService(db).record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-canonical-provider-task",
        amount_minor=2_400,
        currency="RUB",
        entry_kind="actual",
        status="confirmed",
        source="provider_webhook",
        idempotency_key="cost:canonical-product-ugc:actual",
    )

    assert result.created
    assert result.entry.cost_scope == "provider_job"
    assert result.entry.provider == "runway_product_ugc_recipe"


def test_aggregate_cost_per_generated_and_human_approved_video_with_coverage(db: Session) -> None:
    organization, profile, product = make_org(db, "aggregate-cost")
    approved = make_video_job(
        db,
        organization,
        product,
        provider_job_id="runway-cost-approved",
        status="video_approved",
        output_path="/media/approved.mp4",
    )
    approve_video(db, approved, product)
    generated = make_video_job(
        db,
        organization,
        product,
        provider_job_id="runway-cost-generated",
        output_path="/media/generated.mp4",
    )
    failed = make_video_job(
        db,
        organization,
        product,
        provider_job_id="runway-cost-failed",
        status="failed",
        output_path=None,
    )
    unpriced = make_video_job(
        db,
        organization,
        product,
        provider_job_id="runway-cost-unpriced",
        output_path="/media/unpriced.mp4",
    )
    service = GenerationCostLedgerService(db)
    for job, amount, kind, status, source in (
        (approved, 1_000, "actual", "confirmed", "provider_api"),
        (generated, 500, "estimated", "pending", "internal_estimate"),
        (failed, 200, "actual", "confirmed", "provider_api"),
    ):
        provider_job_id = job.clips[0].provider_job_id
        service.record(
            organization_id=organization.id,
            video_job_id=job.id,
            provider_job_id=provider_job_id,
            amount_minor=amount,
            currency="USD",
            entry_kind=kind,
            status=status,
            source=source,
            idempotency_key=f"cost:aggregate:{provider_job_id}",
            recorded_by_user_profile_id=profile.id if kind == "estimated" else None,
        )

    aggregate = service.aggregate(organization_id=organization.id, currency="USD")[0]

    assert aggregate.estimated_cost_minor == 500
    assert aggregate.confirmed_actual_cost_minor == 1_200
    assert aggregate.recognized_cost_minor == 1_700
    assert aggregate.priced_video_count == 3
    assert aggregate.generated_video_count == 2
    assert aggregate.approved_video_count == 1
    assert aggregate.organization_generated_video_count == 3
    assert aggregate.organization_approved_video_count == 1
    assert aggregate.unpriced_generated_video_count == 1
    assert aggregate.unpriced_approved_video_count == 0
    assert aggregate.cost_per_generated_video_minor == Decimal("850.00")
    assert aggregate.cost_per_approved_video_minor == Decimal("1700.00")
    assert unpriced.id not in {
        entry.video_job_id
        for entry in db.scalars(select(models.GenerationCostLedgerEntry)).all()
    }


def test_ledger_rows_cannot_be_updated_or_deleted(db: Session) -> None:
    organization, profile, product = make_org(db, "immutable-cost")
    job = make_video_job(db, organization, product, provider_job_id="runway-task-immutable")
    entry = GenerationCostLedgerService(db).record(
        organization_id=organization.id,
        video_job_id=job.id,
        provider_job_id="runway-task-immutable",
        amount_minor=300,
        currency="USD",
        entry_kind="estimated",
        status="pending",
        source="internal_estimate",
        idempotency_key="cost:immutable:estimate",
        recorded_by_user_profile_id=profile.id,
    ).entry

    entry.amount_minor = 301
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()

    persisted = db.get(models.GenerationCostLedgerEntry, entry.id)
    assert persisted.amount_minor == 300
    db.delete(persisted)
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()
    assert db.get(models.GenerationCostLedgerEntry, entry.id) is not None
