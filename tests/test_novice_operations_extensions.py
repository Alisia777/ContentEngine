from __future__ import annotations

from collections.abc import Generator
from datetime import date, timedelta
import os

os.environ.setdefault(
    "QVF_DATABASE_URL",
    "sqlite:///./test_novice_operations_extensions.db",
)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.content_cycles import ContentCycleService
from app.database import Base, get_db
from app.generation_costs import GenerationCostLedgerService
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.routers import public_pilot


@pytest.fixture()
def isolated_public_app(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LocalSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with LocalSession() as db:
        organization = models.Organization(name="Novice Ops", slug="novice-ops")
        profile = models.UserProfile(
            supabase_user_id="test:novice-ops-owner",
            email="owner@novice-ops.test",
            display_name="Owner",
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


def test_workbench_and_machine_snapshot_expose_queue_evidence_and_billing(isolated_public_app):
    client, _LocalSession, _user = isolated_public_app
    payments = client.get("/workbench?tab=payments")
    assert payments.status_code == 200
    assert "Клиентский биллинг" in payments.text
    assert "Настройте учёт в три шага" in payments.text
    assert "банк · эквайринг · возвраты" in payments.text
    assert "Деньги не переводятся этой системой" in payments.text

    video = client.get("/workbench?tab=video")
    assert video.status_code == 200
    assert "Надёжная очередь генерации" in video.text
    assert "Очередь пуста" in video.text

    sources = client.get("/workbench?tab=sources")
    assert sources.status_code == 200
    assert "Официальные API" in sources.text
    assert "Выберите способ получения данных" in sources.text
    assert "YouTube" in sources.text
    assert "официальный API" in sources.text
    assert "Instagram" in sources.text
    assert "ручной/CSV импорт готов" in sources.text
    assert "Сначала добавьте собственную площадку" in sources.text

    machine = client.get("/api/factory-dashboard")
    assert machine.status_code == 200
    payload = machine.json()
    assert payload["schema_version"] == 2
    assert payload["generation_queue"] == []
    assert payload["quality_evidence"] == []
    assert payload["customer_billing"]["configured"] is False
    operations = payload["operations_readiness"]
    assert operations["schema_version"] == 1
    assert operations["total_count"] == 4
    first_actionable = next(
        card
        for card in operations["cards"]
        if card["status"] == "action_required" and card.get("action")
    )
    assert operations["recommended_action"] == first_actionable["action"]
    cards = {card["key"]: card for card in operations["cards"]}
    assert {check["key"] for check in cards["media_quality"]["checks"]} == {
        "ffmpeg",
        "ffprobe",
        "tesseract",
        "ocr_languages",
    }
    assert cards["generation_worker"]["operations"]["worker_ready"] is False
    assert cards["customer_billing"]["external_acquiring_enabled"] is False
    platform_rows = {
        row["key"]: row for row in cards["social_connectors"]["platforms"]
    }
    assert platform_rows["youtube"]["mode"] == "official_api"
    assert platform_rows["youtube"]["adapter_status"] == "code_ready"
    assert platform_rows["youtube"]["setup_status"] == "code_ready"
    assert platform_rows["instagram"]["mode"] == "official_api"
    assert platform_rows["tiktok"]["mode"] == "official_api"
    assert platform_rows["telegram"]["mode"] == "manual_csv"
    serialized = machine.text.lower()
    assert "youtube_analytics_access_token=" not in serialized
    assert "bearer " not in serialized


def test_owner_configures_instagram_official_target_without_storing_token(
    isolated_public_app,
    tmp_path,
):
    client, LocalSession, user = isolated_public_app
    with LocalSession() as db:
        output = tmp_path / "instagram-output.mp4"
        output.write_bytes(b"real-provider-output")
        product = models.Product(
            organization_id=user.organization.id,
            sku="IG-CONNECTOR-1",
            brand="Novice",
            title="Instagram connector product",
        )
        db.add(product)
        db.flush()
        draft = models.ProductUGCRecipeDraft(
            product_id=product.id,
            sku=product.sku,
            status="approved",
            character_image_path=(tmp_path / "character.png").as_posix(),
            character_image_filename="character.png",
            likeness_consent=True,
            exact_variant_confirmed=True,
            product_info="Exact product",
            user_concept="Published Instagram demo",
            provider_task_id="provider-instagram-1",
            provider_status="SUCCEEDED",
            local_output_paths_json=[output.as_posix()],
            human_review_status="approved",
            publishing_readiness="ready_for_package",
            human_review_notes="Human verified the exact published product.",
            blockers_json=[],
            warnings_json=[],
        )
        db.add(draft)
        db.commit()
        cycle = ContentCycleService(db).start_from_product_ugc(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            product_ugc_recipe_draft_id=draft.id,
            idempotency_key="instagram-connector-cycle",
        )
        destination = models.PublishingDestination(
            organization_id=user.organization.id,
            brand=product.brand,
            platform="Instagram",
            name="Owned Instagram",
            status="active",
        )
        package = models.PublishingPackage(
            video_job_id=cycle.video_job_id,
            product_id=product.id,
            brand=product.brand,
            target_platform="Instagram",
            title="Published Instagram package",
            review_status="approved",
            status="ready",
        )
        db.add_all([destination, package])
        db.flush()
        task = models.PublishingTask(
            publishing_package_id=package.id,
            destination_id=destination.id,
            platform="Instagram",
            status="published",
            final_url="https://www.instagram.com/reel/owned-post/",
        )
        db.add(task)
        db.flush()
        cycle.destination_id = destination.id
        cycle.publishing_package_id = package.id
        cycle.publishing_task_id = task.id
        cycle_id = cycle.id
        destination_id = destination.id
        db.commit()

    response = client.post(
        "/workbench/official-connectors/instagram/setup",
        data={
            "cycle_id": str(cycle_id),
            "target_id": "17890000000000001",
            "credential_ref": "env:INSTAGRAM_OFFICIAL_ACCESS_TOKEN",
            "confirm_secret_reference_only": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "connector_notice=instagram_configured" in response.headers["location"]
    with LocalSession() as db:
        connection = db.scalar(
            select(models.DestinationConnection).where(
                models.DestinationConnection.destination_id == destination_id
            )
        )
        assert connection.connection_type == "instagram_oauth"
        assert connection.credential_ref == "env:INSTAGRAM_OFFICIAL_ACCESS_TOKEN"
        target = connection.settings_json["media_map"]["17890000000000001"]
        assert target["final_url"] == "https://www.instagram.com/reel/owned-post/"
        assert isinstance(target["publishing_task_id"], int)
        assert target["publishing_task_id"] > 0
        assert "token" not in str(connection.settings_json).lower()

    page = client.get("/workbench?tab=sources")
    assert page.status_code == 200
    assert "Настроить Instagram Insights без сохранения токена" in page.text
    assert "нужны credentials" in page.text
    assert "INSTAGRAM_OFFICIAL_ACCESS_TOKEN=" not in page.text
    operations = client.get("/api/factory-dashboard").json()["operations_readiness"]
    social = next(card for card in operations["cards"] if card["key"] == "social_connectors")
    instagram = next(row for row in social["platforms"] if row["key"] == "instagram")
    assert instagram["adapter_status"] == "code_ready"
    assert instagram["setup_status"] == "needs_credentials"
    assert instagram["credential_reference_status"] == "configured_but_unavailable"


def test_owner_gets_actionable_wb_seller_analytics_setup_without_raw_key(
    isolated_public_app,
):
    client, LocalSession, user = isolated_public_app
    with LocalSession() as db:
        product = models.Product(
            organization_id=user.organization.id,
            sku="WB-ANALYTICS-1",
            brand="Novice",
            title="WB Analytics product",
        )
        db.add(product)
        db.flush()
        db.add(
            models.MarketplaceListing(
                organization_id=user.organization.id,
                product_id=product.id,
                marketplace="wildberries",
                seller_account_ref="main-cabinet",
                nm_id="123456789",
                status="verified",
                verified_by=user.profile.id,
            )
        )
        db.commit()

    configured = client.post(
        "/workbench/wb-analytics/setup",
        data={
            "seller_account_ref": "main-cabinet",
            "credential_ref": "env:WB_SELLER_ANALYTICS_TOKEN",
            "confirm_secret_reference_only": "true",
        },
        follow_redirects=False,
    )
    assert configured.status_code == 303
    assert "wb_analytics_notice=connection_configured" in configured.headers["location"]

    page = client.get("/workbench?tab=wb")
    assert page.status_code == 200
    assert "Wildberries Seller Analytics" in page.text
    assert "Нужен API-ключ" in page.text
    assert "Подтверждённые nmID" in page.text
    assert "WB_SELLER_ANALYTICS_TOKEN=" not in page.text
    with LocalSession() as db:
        connection = db.scalar(select(models.WildberriesAnalyticsConnection))
        assert connection.credential_ref == "env:WB_SELLER_ANALYTICS_TOKEN"
        assert "token" not in str(connection.settings_json).lower()

    machine = client.get("/api/factory-dashboard").json()
    assert machine["wildberries_seller_analytics"]["mode"] == "official_api"
    operations = machine["operations_readiness"]
    social = next(card for card in operations["cards"] if card["key"] == "social_connectors")
    wb = next(row for row in social["platforms"] if row["key"] == "wb")
    assert wb["mode"] == "official_api"
    assert wb["adapter_status"] == "code_ready"
    assert wb["setup_status"] == "needs_credentials"
    assert wb["last_sync_at"] is None


def test_owner_can_create_ledger_account_invoice_and_external_payment(
    isolated_public_app,
    tmp_path,
):
    client, LocalSession, user = isolated_public_app
    account = client.post(
        "/workbench/customer-billing/account",
        data={"currency": "RUB", "confirm_ledger_only": "true"},
        follow_redirects=False,
    )
    assert account.status_code == 303
    assert "billing_notice=account_created" in account.headers["location"]

    subscription = client.post(
        "/workbench/customer-billing/subscription",
        data={
            "plan_code": "content-factory-start",
            "status": "active",
            "billing_interval": "month",
            "recurring_amount": "9900.00",
            "included_content_cycles": "10",
            "confirm_ledger_only": "true",
        },
        follow_redirects=False,
    )
    assert subscription.status_code == 303
    assert "billing_notice=subscription_created" in subscription.headers["location"]
    with LocalSession() as db:
        stored_account = db.scalar(
            select(models.CustomerBillingAccount).where(
                models.CustomerBillingAccount.organization_id == user.organization.id
            )
        )
        state = db.scalar(select(models.CustomerBillingSubscriptionState))
        assert stored_account.currency == "RUB"
        assert state.plan_code == "content-factory-start"
        assert state.recurring_amount_minor == 990000
        active_state_id = state.id
        assert db.scalar(select(models.CustomerBillingLedgerEntry)) is None

    paused = client.post(
        "/workbench/customer-billing/subscription",
        data={
            "plan_code": "content-factory-start",
            "status": "paused",
            "billing_interval": "month",
            "recurring_amount": "9900.00",
            "included_content_cycles": "10",
            "expected_previous_state_id": str(active_state_id),
            "confirm_ledger_only": "true",
        },
        follow_redirects=False,
    )
    assert paused.status_code == 303
    with LocalSession() as db:
        paused_state = db.scalar(
            select(models.CustomerBillingSubscriptionState).order_by(
                models.CustomerBillingSubscriptionState.version.desc()
            )
        )
        assert paused_state.status == "paused"
        paused_state_id = paused_state.id

    resumed = client.post(
        "/workbench/customer-billing/subscription",
        data={
            "plan_code": "content-factory-start",
            "status": "active",
            "billing_interval": "month",
            "recurring_amount": "9900.00",
            "included_content_cycles": "10",
            "expected_previous_state_id": str(paused_state_id),
            "confirm_ledger_only": "true",
        },
        follow_redirects=False,
    )
    assert resumed.status_code == 303

    with LocalSession() as db:

        character = tmp_path / "character.png"
        output = tmp_path / "real-output.mp4"
        character.write_bytes(b"character")
        output.write_bytes(b"real-provider-output")
        product = models.Product(
            organization_id=user.organization.id,
            sku="BILLABLE-1",
            brand="Novice",
            title="Billable product",
        )
        db.add(product)
        db.flush()
        draft = models.ProductUGCRecipeDraft(
            product_id=product.id,
            sku=product.sku,
            status="approved",
            character_image_path=character.as_posix(),
            character_image_filename=character.name,
            likeness_consent=True,
            exact_variant_confirmed=True,
            product_info="Exact billable product",
            user_concept="Human-reviewed product demonstration",
            provider_task_id="runway-billable-task-1",
            provider_status="SUCCEEDED",
            local_output_paths_json=[output.as_posix()],
            human_review_status="approved",
            publishing_readiness="ready_for_package",
            human_review_notes="Human verified the exact product and provider output.",
            blockers_json=[],
            warnings_json=[],
        )
        db.add(draft)
        db.commit()
        cycle = ContentCycleService(db).start_from_product_ugc(
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            product_ugc_recipe_draft_id=draft.id,
            idempotency_key="billable-cycle-1",
        )
        cost = GenerationCostLedgerService(db).record(
            organization_id=user.organization.id,
            video_job_id=cycle.video_job_id,
            provider_job_id=draft.provider_task_id,
            amount_minor=35000,
            currency="RUB",
            entry_kind="actual",
            status="confirmed",
            source="invoice_import",
            external_reference="provider-invoice-1",
            idempotency_key="billable-cost-1",
            recorded_by_user_profile_id=user.profile.id,
        ).entry
        cost_id = cost.id

    today = date.today()
    invoice = client.post(
        "/workbench/customer-billing/invoices",
        data={
            "generation_cost_entry_id": str(cost_id),
            "invoice_number": "INV-2026-001",
            "period_start": (today - timedelta(days=10)).isoformat(),
            "period_end": (today + timedelta(days=1)).isoformat(),
            "due_date": (today + timedelta(days=14)).isoformat(),
            "charge_amount": "990.00",
            "description": "One measured content cycle",
            "confirm_invoice_only": "true",
        },
        follow_redirects=False,
    )
    assert invoice.status_code == 303
    assert "billing_notice=invoice_created" in invoice.headers["location"]
    with LocalSession() as db:
        stored_invoice = db.scalar(select(models.CustomerInvoice))
        assert stored_invoice is not None
        invoice_id = stored_invoice.id
        charge_id = db.scalar(
            select(models.CustomerBillingLedgerEntry.id).where(
                models.CustomerBillingLedgerEntry.entry_kind == "charge"
            )
        )

    credit = client.post(
        f"/workbench/customer-billing/invoices/{invoice_id}/credits",
        data={
            "target_charge_entry_id": str(charge_id),
            "amount": "90.00",
            "reason": "Approved correction for an overcharged service line",
            "correction_reference": "CORR-2026-001",
            "confirm_ledger_only": "true",
        },
        follow_redirects=False,
    )
    assert credit.status_code == 303
    assert "billing_notice=credit_recorded" in credit.headers["location"]

    payment = client.post(
        f"/workbench/customer-billing/invoices/{invoice_id}/payments",
        data={
            "amount": "900.00",
            "transaction_reference": "bank/acquiring/2026-001",
            "occurred_date": today.isoformat(),
            "confirm_external_payment": "true",
        },
        follow_redirects=False,
    )
    assert payment.status_code == 303
    assert "billing_notice=payment_recorded" in payment.headers["location"]
    with LocalSession() as db:
        entries = db.scalars(
            select(models.CustomerBillingLedgerEntry).order_by(
                models.CustomerBillingLedgerEntry.id
            )
        ).all()
        assert [entry.entry_kind for entry in entries] == ["charge", "credit", "payment"]
        credit_entry = next(entry for entry in entries if entry.entry_kind == "credit")
        assert credit_entry.related_entry_id == charge_id
        assert sum(entry.amount_minor for entry in entries if entry.entry_kind == "payment") == 90000


def test_safe_retry_requeues_one_owned_job_without_second_provider_submit(isolated_public_app):
    client, LocalSession, user = isolated_public_app
    with LocalSession() as db:
        product = models.Product(
            organization_id=user.organization.id,
            sku="QUEUE-OWNED-1",
            brand="Novice",
            title="Owned product",
        )
        db.add(product)
        db.flush()
        draft = models.ProductUGCRecipeDraft(
            product_id=product.id,
            sku=product.sku,
            status="provider_failed",
            character_image_path="media/character.png",
            character_image_filename="character.png",
            product_info="Exact product",
            user_concept="Exact product demo",
        )
        db.add(draft)
        db.flush()
        job = models.ProductUGCGenerationJob(
            draft_id=draft.id,
            organization_id=user.organization.id,
            requested_by_user_profile_id=user.profile.id,
            idempotency_key="novice-queue-retry-1",
            status="failed_terminal",
            attempt_count=1,
            max_attempts=1,
            provider_status="PENDING",
            terminal_reason="download_timeout",
        )
        db.add(job)
        db.commit()
        job_id = job.id

    response = client.post(
        f"/workbench/generation-jobs/{job_id}/retry",
        data={"confirm_safe_retry": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "queue_notice=requeued" in response.headers["location"]
    with LocalSession() as db:
        refreshed = db.get(models.ProductUGCGenerationJob, job_id)
        assert refreshed.status == "retry_wait"
        assert refreshed.provider_task_id is None
        assert refreshed.spend_guarded_at is None
