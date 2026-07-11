from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.product_ugc_queue import ProductUGCGenerationQueueService
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers import public_pilot


@pytest.fixture()
def queue_public_app(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LocalSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with LocalSession() as db:
        organization = models.Organization(
            name="Queue Operations",
            slug="queue-operations",
            status="active",
        )
        profile = models.UserProfile(
            supabase_user_id="test:queue-operations-owner",
            email="owner@queue-operations.test",
            display_name="Queue owner",
            status="active",
            is_active=True,
        )
        db.add_all([organization, profile])
        db.flush()
        membership = models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="owner",
            status="active",
        )
        db.add(membership)
        db.commit()
        user = PublicPilotUser(
            profile=profile,
            organization=organization,
            membership=membership,
        )

    def local_db() -> Generator[Session, None, None]:
        with LocalSession() as db:
            yield db

    api = FastAPI()
    api.mount("/static", StaticFiles(directory="app/static"), name="static")
    api.include_router(public_pilot.router)
    api.dependency_overrides[get_db] = local_db
    api.dependency_overrides[get_current_public_user] = lambda: user
    monkeypatch.setattr(public_pilot, "_run_product_ugc_background", lambda *_args: None)
    yield TestClient(api), LocalSession, user
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _ambiguous_job(db: Session, user: PublicPilotUser, *, suffix: str):
    product = models.Product(
        organization_id=user.organization.id,
        sku=f"QUEUE-WEB-{suffix}",
        brand="Queue",
        title="Queue reconciliation product",
    )
    db.add(product)
    db.flush()
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        sku=product.sku,
        status="ready_for_paid_preflight",
        character_image_path="media/character.png",
        character_image_filename="character.png",
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_info="Exact product",
        user_concept="Exact product demo",
        blockers_json=[],
        warnings_json=[],
    )
    db.add(draft)
    db.commit()
    service = ProductUGCGenerationQueueService(db)
    job = service.enqueue(
        draft_id=draft.id,
        organization_id=user.organization.id,
        requested_by_user_profile_id=user.profile.id,
        idempotency_key=f"queue-web:{suffix}",
    ).job
    leased = service.lease_job(job.id, worker_id=f"queue-web-worker:{suffix}")
    service.begin_provider_submission(job.id, lease_token=leased.lease_token)
    job = service.fail(
        job.id,
        lease_token=leased.lease_token,
        error="submit result unknown",
    ).job
    return job


def test_workbench_and_machine_api_show_supervised_worker_health(queue_public_app):
    client, LocalSession, user = queue_public_app
    with LocalSession() as db:
        ProductUGCGenerationQueueService(db).record_worker_heartbeat(
            worker_id="supervised-worker-instance",
            state="idle",
            supervised=True,
        )

    page = client.get("/workbench?tab=video")
    assert page.status_code == 200
    assert "Воркер генерации на связи" in page.text
    assert "Задержка очереди" in page.text
    machine = client.get("/api/factory-dashboard")
    assert machine.status_code == 200
    operations = machine.json()["generation_queue_operations"]
    assert operations["worker_ready"] is True
    assert operations["worker_state"] == "idle"
    assert operations["queue_lag_seconds"] == 0
    assert "worker_key" not in operations
    assert "lease_token" not in operations


def test_owner_reconciles_both_safe_quarantine_outcomes_from_workbench(queue_public_app):
    client, LocalSession, user = queue_public_app
    with LocalSession() as db:
        attach_job = _ambiguous_job(db, user, suffix="attach")
        no_submit_job = _ambiguous_job(db, user, suffix="absent")
        attach_id = attach_job.id
        no_submit_id = no_submit_job.id

    page = client.get("/workbench?tab=video")
    assert page.status_code == 200
    assert "Задача у провайдера найдена" in page.text
    assert "Провайдер подтверждает: задачи нет" in page.text

    attached = client.post(
        f"/workbench/generation-jobs/{attach_id}/reconcile-quarantine",
        data={
            "resolution": "attach_existing_task",
            "provider_task_id": "provider-task-web-attach",
            "evidence_reference": "audit-web-attach-1",
            "reason": "Нашёл задачу в кабинете по времени и точному товару.",
            "confirm_provider_check": "true",
        },
        follow_redirects=False,
    )
    assert attached.status_code == 303
    assert "queue_notice=reconciled_existing_task" in attached.headers["location"]

    absent = client.post(
        f"/workbench/generation-jobs/{no_submit_id}/reconcile-quarantine",
        data={
            "resolution": "confirm_no_submission",
            "evidence_reference": "support-web-absent-1",
            "reason": "История кабинета и поддержка подтверждают отсутствие задачи.",
            "confirm_provider_check": "true",
        },
        follow_redirects=False,
    )
    assert absent.status_code == 303
    assert "queue_notice=reconciled_no_submission" in absent.headers["location"]

    with LocalSession() as db:
        attached_job = db.get(models.ProductUGCGenerationJob, attach_id)
        absent_job = db.get(models.ProductUGCGenerationJob, no_submit_id)
        assert attached_job.status == "retry_wait"
        assert attached_job.provider_task_id == "provider-task-web-attach"
        assert attached_job.spend_guarded_at is not None
        assert absent_job.status == "retry_wait"
        assert absent_job.provider_task_id is None
        assert absent_job.spend_guarded_at is None
        assert db.scalar(
            select(func.count()).select_from(models.ProductUGCQueueReconciliation)
        ) == 2

        denied_job = _ambiguous_job(db, user, suffix="denied")
        denied_id = denied_job.id
        membership = db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == user.organization.id,
                models.Membership.user_profile_id == user.profile.id,
            )
        )
        membership.role = "reviewer"
        db.commit()
        user.membership.role = "reviewer"

    denied = client.post(
        f"/workbench/generation-jobs/{denied_id}/reconcile-quarantine",
        data={
            "resolution": "confirm_no_submission",
            "evidence_reference": "support-web-denied-1",
            "reason": "История кабинета подтверждает отсутствие задачи у провайдера.",
            "confirm_provider_check": "true",
        },
        follow_redirects=False,
    )
    assert denied.status_code == 303
    assert "queue_error=" in denied.headers["location"]
    with LocalSession() as db:
        assert db.get(models.ProductUGCGenerationJob, denied_id).status == "quarantined"
