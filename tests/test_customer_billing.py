from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta

# Importing app.models also imports the application database module. Pin a
# disposable URL before that happens so collection order can never expose a
# developer's qharisma.db to another test module's drop_all fixture.
os.environ.setdefault("QVF_DATABASE_URL", "sqlite://")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.customer_billing import (
    CustomerBillingConflictError,
    CustomerBillingOwnershipError,
    CustomerBillingService,
    CustomerBillingStateError,
    CustomerBillingValidationError,
    UsageChargeInput,
)
from app.database import Base, _ensure_customer_billing_schema


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


def make_org(
    db: Session,
    slug: str,
) -> tuple[models.Organization, models.UserProfile, models.UserProfile, models.Product]:
    organization = models.Organization(name=slug.title(), slug=slug)
    owner = models.UserProfile(
        supabase_user_id=f"billing-owner:{slug}",
        email=f"owner@{slug}.test",
        display_name=f"{slug.title()} Owner",
    )
    operator = models.UserProfile(
        supabase_user_id=f"billing-operator:{slug}",
        email=f"operator@{slug}.test",
        display_name=f"{slug.title()} Operator",
    )
    db.add_all([organization, owner, operator])
    db.flush()
    db.add_all(
        [
            models.Membership(
                organization_id=organization.id,
                user_profile_id=owner.id,
                role="owner",
                status="active",
            ),
            models.Membership(
                organization_id=organization.id,
                user_profile_id=operator.id,
                role="operator",
                status="active",
            ),
        ]
    )
    product = models.Product(
        organization_id=organization.id,
        sku=f"BILL-{slug.upper()}",
        brand="Billing Test",
        title="Traceable customer usage",
    )
    db.add(product)
    db.commit()
    return organization, owner, operator, product


def create_account_and_subscription(
    db: Session,
    organization: models.Organization,
    owner: models.UserProfile,
    *,
    currency: str = "RUB",
) -> tuple[models.CustomerBillingAccount, models.CustomerBillingSubscriptionState]:
    service = CustomerBillingService(db)
    account = service.create_account(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        currency=currency,
        idempotency_key=f"billing-account:{organization.id}",
    ).account
    now = datetime.now(UTC)
    subscription = service.transition_subscription(
        organization_id=organization.id,
        billing_account_id=account.id,
        actor_user_profile_id=owner.id,
        plan_code="factory-starter",
        status="active",
        billing_interval="month",
        recurring_amount_minor=49_000,
        included_content_cycles=10,
        currency=currency,
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
        expected_previous_state_id=None,
        idempotency_key=f"subscription:{organization.id}:v1",
    ).state
    return account, subscription


def make_cycle_and_actual_cost(
    db: Session,
    organization: models.Organization,
    owner: models.UserProfile,
    product: models.Product,
    *,
    currency: str = "RUB",
    cost_status: str = "confirmed",
    cost_kind: str = "actual",
) -> tuple[models.ContentCycle, models.GenerationCostLedgerEntry]:
    draft = models.ProductUGCRecipeDraft(
        product_id=product.id,
        sku=product.sku,
        status="approved",
        character_image_path="/media/owned-character.png",
        character_image_filename="owned-character.png",
        likeness_consent=True,
        exact_variant_confirmed=True,
        product_info="Exact product",
        user_concept="Exact creator demonstration",
    )
    db.add(draft)
    db.flush()
    job = models.VideoJob(
        script_variant_id=100_000 + organization.id,
        organization_id=organization.id,
        created_by_user_profile_id=owner.id,
        product_id=product.id,
        source_product_ugc_draft_id=draft.id,
        provider="runway",
        status="video_generated",
        output_video_path="/media/real-provider-output.mp4",
    )
    brief = models.AIProductionBrief(
        product_id=product.id,
        sku=product.sku,
        status="ready_for_output_review",
    )
    db.add_all([job, brief])
    db.flush()
    cycle = models.ContentCycle(
        organization_id=organization.id,
        created_by_user_profile_id=owner.id,
        product_id=product.id,
        product_ugc_recipe_draft_id=draft.id,
        video_job_id=job.id,
        ai_production_brief_id=brief.id,
        idempotency_key=f"billing-cycle:{organization.id}:{job.id}",
        status="needs_output_acceptance",
    )
    cost = models.GenerationCostLedgerEntry(
        organization_id=organization.id,
        video_job_id=job.id,
        provider="runway",
        cost_scope="video_job",
        cost_unit_key=f"video:{job.id}",
        revision=1,
        amount_minor=700,
        currency=currency,
        entry_kind=cost_kind,
        status=cost_status,
        source="provider_api" if cost_kind == "actual" else "internal_estimate",
        external_reference=f"provider/invoice/{organization.id}-{job.id}",
        idempotency_key=f"provider-cost:{organization.id}:{job.id}:{cost_kind}",
        recorded_by_user_profile_id=owner.id,
    )
    db.add_all([cycle, cost])
    db.commit()
    return cycle, cost


def issue_invoice(
    db: Session,
    organization: models.Organization,
    owner: models.UserProfile,
    account: models.CustomerBillingAccount,
    subscription: models.CustomerBillingSubscriptionState,
    cycle: models.ContentCycle,
    cost: models.GenerationCostLedgerEntry,
    *,
    key: str = "invoice:usage:1",
    invoice_number: str = "INV-2026-0001",
    amount_minor: int = 2_000,
):
    return CustomerBillingService(db).issue_usage_invoice(
        organization_id=organization.id,
        billing_account_id=account.id,
        actor_user_profile_id=owner.id,
        subscription_state_id=subscription.id,
        invoice_number=invoice_number,
        currency=account.currency,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 8, 1),
        due_at=datetime(2099, 1, 1, tzinfo=UTC),
        usage_charges=[
            UsageChargeInput(
                content_cycle_id=cycle.id,
                generation_cost_ledger_entry_id=cost.id,
                amount_minor=amount_minor,
                description="One traceable AI content cycle",
            )
        ],
        idempotency_key=key,
    )


def test_sqlite_migration_creates_isolated_append_only_billing_schema() -> None:
    local_engine = create_engine("sqlite://")
    _ensure_customer_billing_schema(local_engine)
    schema = inspect(local_engine)

    assert {
        "customer_billing_accounts",
        "customer_billing_subscription_states",
        "customer_invoices",
        "customer_billing_ledger_entries",
    }.issubset(schema.get_table_names())
    ledger_columns = {
        column["name"]
        for column in schema.get_columns("customer_billing_ledger_entries")
    }
    assert {
        "organization_id",
        "billing_account_id",
        "invoice_id",
        "entry_kind",
        "amount_minor",
        "currency",
        "content_cycle_id",
        "generation_cost_ledger_entry_id",
        "related_entry_id",
        "transaction_reference",
        "idempotency_key",
    }.issubset(ledger_columns)
    unique_names = {
        item["name"]
        for item in schema.get_unique_constraints("customer_billing_ledger_entries")
    }
    assert "uq_customer_billing_ledger_idempotency" in unique_names
    assert "uq_customer_billing_transaction_reference" in unique_names
    with local_engine.connect() as connection:
        trigger_names = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND name LIKE 'customer_%_no_%'"
            )
        }
        connection.exec_driver_sql(
            "INSERT INTO customer_billing_accounts "
            "(organization_id, currency, status, idempotency_key, "
            "created_by_user_profile_id, created_at) "
            "VALUES (1, 'RUB', 'active', 'migration-account', 1, CURRENT_TIMESTAMP)"
        )
        with pytest.raises(DatabaseError, match="append-only"):
            connection.exec_driver_sql(
                "UPDATE customer_billing_accounts SET currency = 'USD' WHERE id = 1"
            )
    assert trigger_names == {
        "customer_billing_account_no_update",
        "customer_billing_account_no_delete",
        "customer_billing_subscription_no_update",
        "customer_billing_subscription_no_delete",
        "customer_invoice_no_update",
        "customer_invoice_no_delete",
        "customer_billing_ledger_no_update",
        "customer_billing_ledger_no_delete",
        "customer_billing_ledger_no_overapply",
    }
    local_engine.dispose()


def test_account_and_subscription_history_are_owned_idempotent_and_linear(db: Session) -> None:
    organization, owner, operator, _product = make_org(db, "account-history")
    service = CustomerBillingService(db)
    created = service.create_account(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        currency="rub",
        idempotency_key="account-history:create",
    )
    replay = service.create_account(
        organization_id=organization.id,
        actor_user_profile_id=owner.id,
        currency="RUB",
        idempotency_key="account-history:create",
    )
    assert created.created is True
    assert replay.created is False
    assert replay.account.id == created.account.id
    assert replay.account.currency == "RUB"

    with pytest.raises(CustomerBillingOwnershipError, match="owner or admin"):
        service.transition_subscription(
            organization_id=organization.id,
            billing_account_id=created.account.id,
            actor_user_profile_id=operator.id,
            plan_code="factory-starter",
            status="active",
            billing_interval="month",
            recurring_amount_minor=49_000,
            included_content_cycles=10,
            currency="RUB",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            expected_previous_state_id=None,
            idempotency_key="account-history:operator-denied",
        )

    now = datetime.now(UTC)
    first = service.transition_subscription(
        organization_id=organization.id,
        billing_account_id=created.account.id,
        actor_user_profile_id=owner.id,
        plan_code="factory-starter",
        status="active",
        billing_interval="month",
        recurring_amount_minor=49_000,
        included_content_cycles=10,
        currency="RUB",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        expected_previous_state_id=None,
        idempotency_key="account-history:subscription:v1",
    )
    repeated = service.transition_subscription(
        organization_id=organization.id,
        billing_account_id=created.account.id,
        actor_user_profile_id=owner.id,
        plan_code="factory-starter",
        status="active",
        billing_interval="month",
        recurring_amount_minor=49_000,
        included_content_cycles=10,
        currency="RUB",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        expected_previous_state_id=None,
        idempotency_key="account-history:subscription:v1",
    )
    assert repeated.created is False
    assert repeated.state.id == first.state.id

    paused = service.transition_subscription(
        organization_id=organization.id,
        billing_account_id=created.account.id,
        actor_user_profile_id=owner.id,
        plan_code="factory-starter",
        status="paused",
        billing_interval="month",
        recurring_amount_minor=49_000,
        included_content_cycles=10,
        currency="RUB",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        expected_previous_state_id=first.state.id,
        idempotency_key="account-history:subscription:v2",
    ).state
    assert paused.version == 2
    assert paused.previous_state_id == first.state.id
    with pytest.raises(CustomerBillingConflictError, match="stale"):
        service.transition_subscription(
            organization_id=organization.id,
            billing_account_id=created.account.id,
            actor_user_profile_id=owner.id,
            plan_code="factory-pro",
            status="active",
            billing_interval="month",
            recurring_amount_minor=99_000,
            included_content_cycles=50,
            currency="RUB",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            expected_previous_state_id=first.state.id,
            idempotency_key="account-history:stale-transition",
        )


def test_usage_invoice_links_exact_cycle_and_actual_cost_without_mixing_ledgers(db: Session) -> None:
    organization, owner, _operator, product = make_org(db, "traceable-invoice")
    account, subscription = create_account_and_subscription(db, organization, owner)
    cycle, cost = make_cycle_and_actual_cost(db, organization, owner, product)
    service = CustomerBillingService(db)
    cost_count_before = db.scalar(
        select(func.count()).select_from(models.GenerationCostLedgerEntry)
    )
    payout_count_before = db.scalar(select(func.count()).select_from(models.PayoutLedgerEntry))

    created = issue_invoice(db, organization, owner, account, subscription, cycle, cost)
    replay = issue_invoice(db, organization, owner, account, subscription, cycle, cost)
    totals = service.invoice_totals(
        organization_id=organization.id,
        billing_account_id=account.id,
        invoice_id=created.invoice.id,
    )
    charge = db.scalar(
        select(models.CustomerBillingLedgerEntry).where(
            models.CustomerBillingLedgerEntry.invoice_id == created.invoice.id,
            models.CustomerBillingLedgerEntry.entry_kind == "charge",
        )
    )

    assert created.created is True
    assert replay.created is False
    assert replay.invoice.id == created.invoice.id
    assert charge.content_cycle_id == cycle.id
    assert charge.generation_cost_ledger_entry_id == cost.id
    assert charge.source == "content_cycle_usage"
    assert charge.amount_minor == 2_000
    assert totals.subtotal_minor == 2_000
    assert totals.credits_minor == 0
    assert totals.total_minor == 2_000
    assert totals.paid_minor == 0
    assert totals.balance_minor == 2_000
    assert totals.status == "issued"
    assert db.scalar(select(func.count()).select_from(models.GenerationCostLedgerEntry)) == cost_count_before
    assert db.scalar(select(func.count()).select_from(models.PayoutLedgerEntry)) == payout_count_before

    with pytest.raises(CustomerBillingConflictError, match="already present"):
        issue_invoice(
            db,
            organization,
            owner,
            account,
            subscription,
            cycle,
            cost,
            key="invoice:usage:duplicate",
            invoice_number="INV-2026-0002",
        )


def test_estimated_cross_currency_and_cross_organization_usage_are_blocked(db: Session) -> None:
    organization, owner, _operator, product = make_org(db, "lineage-guard")
    account, subscription = create_account_and_subscription(db, organization, owner)
    estimated_cycle, estimated_cost = make_cycle_and_actual_cost(
        db,
        organization,
        owner,
        product,
        cost_kind="estimated",
        cost_status="pending",
    )
    with pytest.raises(CustomerBillingStateError, match="confirmed actual"):
        issue_invoice(
            db,
            organization,
            owner,
            account,
            subscription,
            estimated_cycle,
            estimated_cost,
            key="invoice:estimated-denied",
            invoice_number="INV-ESTIMATE-DENIED",
        )

    other_org, other_owner, _other_operator, other_product = make_org(db, "other-lineage")
    other_cycle, other_cost = make_cycle_and_actual_cost(
        db,
        other_org,
        other_owner,
        other_product,
    )
    with pytest.raises(CustomerBillingOwnershipError, match="Content cycle"):
        issue_invoice(
            db,
            organization,
            owner,
            account,
            subscription,
            other_cycle,
            other_cost,
            key="invoice:foreign-denied",
            invoice_number="INV-FOREIGN-DENIED",
        )

    usd_cycle, usd_cost = make_cycle_and_actual_cost(
        db,
        organization,
        owner,
        product,
        currency="USD",
    )
    with pytest.raises(CustomerBillingValidationError, match="Cross-currency"):
        issue_invoice(
            db,
            organization,
            owner,
            account,
            subscription,
            usd_cycle,
            usd_cost,
            key="invoice:fx-denied",
            invoice_number="INV-FX-DENIED",
        )


def test_credit_and_manual_payment_are_append_only_bounded_and_owner_only(db: Session) -> None:
    organization, owner, operator, product = make_org(db, "manual-payment")
    account, subscription = create_account_and_subscription(db, organization, owner)
    cycle, cost = make_cycle_and_actual_cost(db, organization, owner, product)
    invoice = issue_invoice(
        db,
        organization,
        owner,
        account,
        subscription,
        cycle,
        cost,
    ).invoice
    service = CustomerBillingService(db)
    charge = db.scalar(
        select(models.CustomerBillingLedgerEntry).where(
            models.CustomerBillingLedgerEntry.invoice_id == invoice.id,
            models.CustomerBillingLedgerEntry.entry_kind == "charge",
        )
    )
    credit = service.add_credit(
        organization_id=organization.id,
        billing_account_id=account.id,
        invoice_id=invoice.id,
        target_charge_entry_id=charge.id,
        actor_user_profile_id=owner.id,
        amount_minor=500,
        reason="Approved service credit",
        idempotency_key="credit:manual-payment:1",
    )
    assert credit.entry.entry_kind == "credit"
    assert credit.entry.related_entry_id == charge.id

    occurred_at = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(CustomerBillingOwnershipError, match="owner or admin"):
        service.record_manual_payment(
            organization_id=organization.id,
            billing_account_id=account.id,
            invoice_id=invoice.id,
            actor_user_profile_id=operator.id,
            amount_minor=1_000,
            transaction_reference="BANK-TXN-OPERATOR-DENIED",
            idempotency_key="payment:operator-denied",
            occurred_at=occurred_at,
        )
    with pytest.raises(CustomerBillingValidationError, match="transaction_reference"):
        service.record_manual_payment(
            organization_id=organization.id,
            billing_account_id=account.id,
            invoice_id=invoice.id,
            actor_user_profile_id=owner.id,
            amount_minor=1_000,
            transaction_reference="",
            idempotency_key="payment:missing-reference",
            occurred_at=occurred_at,
        )
    with pytest.raises(CustomerBillingValidationError, match="outstanding"):
        service.record_manual_payment(
            organization_id=organization.id,
            billing_account_id=account.id,
            invoice_id=invoice.id,
            actor_user_profile_id=owner.id,
            amount_minor=1_501,
            transaction_reference="BANK-TXN-OVERPAY",
            idempotency_key="payment:overpay",
            occurred_at=occurred_at,
        )

    payment = service.record_manual_payment(
        organization_id=organization.id,
        billing_account_id=account.id,
        invoice_id=invoice.id,
        actor_user_profile_id=owner.id,
        amount_minor=1_000,
        transaction_reference="BANK-TXN-EXTERNAL-0001",
        idempotency_key="payment:manual:1",
        occurred_at=occurred_at,
    )
    replay = service.record_manual_payment(
        organization_id=organization.id,
        billing_account_id=account.id,
        invoice_id=invoice.id,
        actor_user_profile_id=owner.id,
        amount_minor=1_000,
        transaction_reference="BANK-TXN-EXTERNAL-0001",
        idempotency_key="payment:manual:1",
        occurred_at=occurred_at,
    )
    totals = service.invoice_totals(
        organization_id=organization.id,
        billing_account_id=account.id,
        invoice_id=invoice.id,
    )
    assert payment.created is True
    assert replay.created is False
    assert replay.entry.id == payment.entry.id
    assert payment.entry.source == "manual_payment"
    assert payment.entry.transaction_reference == "BANK-TXN-EXTERNAL-0001"
    assert totals.subtotal_minor == 2_000
    assert totals.credits_minor == 500
    assert totals.total_minor == 1_500
    assert totals.paid_minor == 1_000
    assert totals.balance_minor == 500
    assert totals.status == "partially_paid"

    with pytest.raises(CustomerBillingConflictError, match="already reconciled"):
        service.record_manual_payment(
            organization_id=organization.id,
            billing_account_id=account.id,
            invoice_id=invoice.id,
            actor_user_profile_id=owner.id,
            amount_minor=500,
            transaction_reference="BANK-TXN-EXTERNAL-0001",
            idempotency_key="payment:manual:duplicate-reference",
            occurred_at=occurred_at,
        )

    payment.entry.amount_minor = 999
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()
    persisted = db.get(models.CustomerBillingLedgerEntry, payment.entry.id)
    assert persisted.amount_minor == 1_000


def test_credit_cannot_create_overpayment_after_partial_payment(db: Session) -> None:
    organization, owner, _operator, product = make_org(db, "credit-overpayment")
    account, subscription = create_account_and_subscription(db, organization, owner)
    cycle, cost = make_cycle_and_actual_cost(db, organization, owner, product)
    invoice = issue_invoice(
        db,
        organization,
        owner,
        account,
        subscription,
        cycle,
        cost,
    ).invoice
    service = CustomerBillingService(db)
    charge = db.scalar(
        select(models.CustomerBillingLedgerEntry).where(
            models.CustomerBillingLedgerEntry.invoice_id == invoice.id,
            models.CustomerBillingLedgerEntry.entry_kind == "charge",
        )
    )
    service.record_manual_payment(
        organization_id=organization.id,
        billing_account_id=account.id,
        invoice_id=invoice.id,
        actor_user_profile_id=owner.id,
        amount_minor=1_800,
        transaction_reference="BANK-TXN-CREDIT-GUARD",
        idempotency_key="payment:credit-guard",
        occurred_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    with pytest.raises(CustomerBillingStateError, match="overpayment"):
        service.add_credit(
            organization_id=organization.id,
            billing_account_id=account.id,
            invoice_id=invoice.id,
            target_charge_entry_id=charge.id,
            actor_user_profile_id=owner.id,
            amount_minor=500,
            reason="Would make paid amount exceed total",
            idempotency_key="credit:would-overpay",
        )
