from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from threading import RLock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.customer_billing.errors import (
    CustomerBillingConflictError,
    CustomerBillingOwnershipError,
    CustomerBillingStateError,
    CustomerBillingValidationError,
)
from app.customer_billing.types import (
    BillingAccountResult,
    BillingLedgerRecordResult,
    InvoiceIssueResult,
    InvoiceTotals,
    SubscriptionStateResult,
    UsageChargeInput,
)


FINANCE_ROLES = {"owner", "admin"}
SUBSCRIPTION_STATUSES = {"trialing", "active", "paused", "cancelled", "expired"}
ACTIVE_SUBSCRIPTION_STATUSES = {"active"}
BILLING_INTERVALS = {"month", "year"}
ALLOWED_TRANSITIONS = {
    None: {"trialing", "active", "paused", "cancelled"},
    "trialing": {"trialing", "active", "paused", "cancelled", "expired"},
    "active": {"active", "paused", "cancelled", "expired"},
    "paused": {"active", "paused", "cancelled", "expired"},
    "cancelled": set(),
    "expired": set(),
}
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
SAFE_REFERENCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,159}$")
_BILLING_LOCK = RLock()
MAX_SQL_INTEGER = 2_147_483_647


class CustomerBillingService:
    """Safe accounting foundation for customer billing.

    The service never calls a payment provider and never initiates a charge,
    transfer, payout, or refund. A ``payment`` row only reconciles an external
    transaction that an owner/admin explicitly identifies. Provider costs are
    read for exact usage lineage but remain in their own immutable ledger.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_account(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        currency: str,
        idempotency_key: str,
    ) -> BillingAccountResult:
        with _BILLING_LOCK:
            organization_id = self._positive_id(organization_id, "organization_id")
            actor_user_profile_id = self._positive_id(
                actor_user_profile_id,
                "actor_user_profile_id",
            )
            currency = self._currency(currency)
            idempotency_key = self._safe_key(idempotency_key, "idempotency_key")
            self._require_organization(organization_id)
            self._require_finance_actor(organization_id, actor_user_profile_id)

            replay = self.db.scalar(
                select(models.CustomerBillingAccount).where(
                    models.CustomerBillingAccount.organization_id == organization_id,
                    models.CustomerBillingAccount.idempotency_key == idempotency_key,
                )
            )
            if replay:
                if (
                    replay.currency == currency
                    and replay.created_by_user_profile_id == actor_user_profile_id
                    and replay.status == "active"
                ):
                    return BillingAccountResult(account=replay, created=False)
                raise CustomerBillingConflictError(
                    "Idempotency key was already used for another billing account command."
                )

            existing = self.db.scalar(
                select(models.CustomerBillingAccount).where(
                    models.CustomerBillingAccount.organization_id == organization_id
                )
            )
            if existing:
                raise CustomerBillingConflictError(
                    "This organization already has a customer billing account."
                )

            account = models.CustomerBillingAccount(
                organization_id=organization_id,
                currency=currency,
                status="active",
                idempotency_key=idempotency_key,
                created_by_user_profile_id=actor_user_profile_id,
            )
            self.db.add(account)
            self._add_audit(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action="create_customer_billing_account",
                entity_type="customer_billing_account",
                entity_id=None,
                metadata={"currency": currency, "no_external_charge": True},
            )
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                concurrent = self.db.scalar(
                    select(models.CustomerBillingAccount).where(
                        models.CustomerBillingAccount.organization_id == organization_id,
                        models.CustomerBillingAccount.idempotency_key == idempotency_key,
                    )
                )
                if (
                    concurrent
                    and concurrent.currency == currency
                    and concurrent.created_by_user_profile_id == actor_user_profile_id
                ):
                    return BillingAccountResult(account=concurrent, created=False)
                raise CustomerBillingConflictError(
                    "Billing account command conflicts with existing immutable history."
                ) from exc
            self.db.refresh(account)
            return BillingAccountResult(account=account, created=True)

    def transition_subscription(
        self,
        *,
        organization_id: int,
        billing_account_id: int,
        actor_user_profile_id: int,
        plan_code: str,
        status: str,
        billing_interval: str,
        recurring_amount_minor: int,
        included_content_cycles: int,
        currency: str,
        current_period_start: datetime | None,
        current_period_end: datetime | None,
        expected_previous_state_id: int | None,
        idempotency_key: str,
        effective_at: datetime | None = None,
    ) -> SubscriptionStateResult:
        with _BILLING_LOCK:
            effective_at_was_supplied = effective_at is not None
            organization_id = self._positive_id(organization_id, "organization_id")
            billing_account_id = self._positive_id(billing_account_id, "billing_account_id")
            actor_user_profile_id = self._positive_id(
                actor_user_profile_id,
                "actor_user_profile_id",
            )
            expected_previous_state_id = (
                self._positive_id(expected_previous_state_id, "expected_previous_state_id")
                if expected_previous_state_id is not None
                else None
            )
            plan_code = self._safe_code(plan_code, "plan_code")
            status = str(status or "").strip().lower()
            billing_interval = str(billing_interval or "").strip().lower()
            recurring_amount_minor = self._nonnegative_minor(
                recurring_amount_minor,
                "recurring_amount_minor",
            )
            included_content_cycles = self._nonnegative_integer(
                included_content_cycles,
                "included_content_cycles",
            )
            currency = self._currency(currency)
            current_period_start = self._optional_utc_datetime(
                current_period_start,
                "current_period_start",
            )
            current_period_end = self._optional_utc_datetime(
                current_period_end,
                "current_period_end",
            )
            effective_at = self._occurred_at(effective_at, "effective_at")
            idempotency_key = self._safe_key(idempotency_key, "idempotency_key")

            if status not in SUBSCRIPTION_STATUSES:
                raise CustomerBillingValidationError("Unsupported subscription status.")
            if billing_interval not in BILLING_INTERVALS:
                raise CustomerBillingValidationError("billing_interval must be month or year.")
            if (current_period_start is None) != (current_period_end is None):
                raise CustomerBillingValidationError(
                    "Both current period boundaries must be provided together."
                )
            if current_period_start and current_period_end <= current_period_start:
                raise CustomerBillingValidationError(
                    "current_period_end must be later than current_period_start."
                )
            if status in {"trialing", "active"} and current_period_start is None:
                raise CustomerBillingValidationError(
                    "An active or trialing subscription requires a current period."
                )

            account = self._owned_account(organization_id, billing_account_id)
            self._require_finance_actor(organization_id, actor_user_profile_id)
            if account.currency != currency:
                raise CustomerBillingValidationError(
                    "Subscription currency must match the immutable billing account currency."
                )

            replay = self.db.scalar(
                select(models.CustomerBillingSubscriptionState).where(
                    models.CustomerBillingSubscriptionState.organization_id == organization_id,
                    models.CustomerBillingSubscriptionState.idempotency_key == idempotency_key,
                )
            )
            request_values = {
                "billing_account_id": billing_account_id,
                "plan_code": plan_code,
                "status": status,
                "billing_interval": billing_interval,
                "recurring_amount_minor": recurring_amount_minor,
                "included_content_cycles": included_content_cycles,
                "currency": currency,
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "previous_state_id": expected_previous_state_id,
                "recorded_by_user_profile_id": actor_user_profile_id,
            }
            if effective_at_was_supplied:
                request_values["effective_at"] = effective_at
            if replay:
                if self._matches(replay, **request_values):
                    return SubscriptionStateResult(state=replay, created=False)
                raise CustomerBillingConflictError(
                    "Idempotency key was already used for another subscription transition."
                )

            previous = self._latest_subscription_state(billing_account_id)
            actual_previous_id = previous.id if previous else None
            if actual_previous_id != expected_previous_state_id:
                raise CustomerBillingConflictError(
                    "Subscription changed; expected_previous_state_id is stale."
                )
            previous_status = previous.status if previous else None
            if status not in ALLOWED_TRANSITIONS[previous_status]:
                raise CustomerBillingStateError(
                    f"Subscription cannot transition from {previous_status or 'none'} to {status}."
                )

            state = models.CustomerBillingSubscriptionState(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                version=(previous.version + 1) if previous else 1,
                previous_state_id=actual_previous_id,
                plan_code=plan_code,
                status=status,
                billing_interval=billing_interval,
                recurring_amount_minor=recurring_amount_minor,
                included_content_cycles=included_content_cycles,
                currency=currency,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                effective_at=effective_at,
                idempotency_key=idempotency_key,
                recorded_by_user_profile_id=actor_user_profile_id,
            )
            self.db.add(state)
            self._add_audit(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action="record_customer_subscription_state",
                entity_type="customer_billing_account",
                entity_id=str(billing_account_id),
                metadata={
                    "plan_code": plan_code,
                    "status": status,
                    "version": state.version,
                    "no_external_charge": True,
                },
            )
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                concurrent = self.db.scalar(
                    select(models.CustomerBillingSubscriptionState).where(
                        models.CustomerBillingSubscriptionState.organization_id == organization_id,
                        models.CustomerBillingSubscriptionState.idempotency_key == idempotency_key,
                    )
                )
                if concurrent and self._matches(concurrent, **request_values):
                    return SubscriptionStateResult(state=concurrent, created=False)
                raise CustomerBillingConflictError(
                    "Subscription transition conflicts with existing immutable history."
                ) from exc
            self.db.refresh(state)
            return SubscriptionStateResult(state=state, created=True)

    def issue_usage_invoice(
        self,
        *,
        organization_id: int,
        billing_account_id: int,
        actor_user_profile_id: int,
        subscription_state_id: int,
        invoice_number: str,
        currency: str,
        period_start: date,
        period_end: date,
        due_at: datetime,
        usage_charges: Sequence[UsageChargeInput],
        idempotency_key: str,
    ) -> InvoiceIssueResult:
        with _BILLING_LOCK:
            organization_id = self._positive_id(organization_id, "organization_id")
            billing_account_id = self._positive_id(billing_account_id, "billing_account_id")
            actor_user_profile_id = self._positive_id(
                actor_user_profile_id,
                "actor_user_profile_id",
            )
            subscription_state_id = self._positive_id(
                subscription_state_id,
                "subscription_state_id",
            )
            invoice_number = self._safe_code(invoice_number, "invoice_number")
            currency = self._currency(currency)
            period_start = self._billing_date(period_start, "period_start")
            period_end = self._billing_date(period_end, "period_end")
            if period_end <= period_start:
                raise CustomerBillingValidationError("period_end must be later than period_start.")
            due_at = self._utc_datetime(due_at, "due_at")
            idempotency_key = self._safe_key(idempotency_key, "idempotency_key")
            normalized_charges = self._normalize_usage_charges(usage_charges)
            if not normalized_charges:
                raise CustomerBillingValidationError(
                    "A usage invoice requires at least one traceable charge."
                )

            account = self._owned_account(organization_id, billing_account_id)
            self._require_finance_actor(organization_id, actor_user_profile_id)
            if account.status != "active":
                raise CustomerBillingStateError("Billing account is not active.")
            if account.currency != currency:
                raise CustomerBillingValidationError(
                    "Invoice currency must match the immutable billing account currency."
                )

            replay = self.db.scalar(
                select(models.CustomerInvoice).where(
                    models.CustomerInvoice.organization_id == organization_id,
                    models.CustomerInvoice.idempotency_key == idempotency_key,
                )
            )
            if replay:
                if self._invoice_matches(
                    replay,
                    billing_account_id=billing_account_id,
                    actor_user_profile_id=actor_user_profile_id,
                    subscription_state_id=subscription_state_id,
                    invoice_number=invoice_number,
                    currency=currency,
                    period_start=period_start,
                    period_end=period_end,
                    due_at=due_at,
                    usage_charges=normalized_charges,
                ):
                    return InvoiceIssueResult(invoice=replay, created=False)
                raise CustomerBillingConflictError(
                    "Idempotency key was already used for another invoice."
                )

            subscription = self.db.get(
                models.CustomerBillingSubscriptionState,
                subscription_state_id,
            )
            if (
                not subscription
                or subscription.organization_id != organization_id
                or subscription.billing_account_id != billing_account_id
            ):
                raise CustomerBillingOwnershipError(
                    "Subscription state is not owned by this billing account."
                )
            latest_subscription = self._latest_subscription_state(billing_account_id)
            if not latest_subscription or latest_subscription.id != subscription.id:
                raise CustomerBillingStateError(
                    "Invoice must use the latest immutable subscription state."
                )
            if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
                raise CustomerBillingStateError("Only an active subscription can be invoiced.")
            if subscription.currency != currency:
                raise CustomerBillingValidationError(
                    "Invoice currency must match the subscription state currency."
                )

            self._validate_usage_lineage(
                organization_id=organization_id,
                currency=currency,
                usage_charges=normalized_charges,
            )
            now = datetime.now(UTC).replace(tzinfo=None)
            if due_at < now:
                raise CustomerBillingValidationError("due_at cannot be in the past.")

            invoice = models.CustomerInvoice(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                subscription_state_id=subscription_state_id,
                invoice_number=invoice_number,
                currency=currency,
                period_start=period_start,
                period_end=period_end,
                issued_at=now,
                due_at=due_at,
                idempotency_key=idempotency_key,
                created_by_user_profile_id=actor_user_profile_id,
            )
            self.db.add(invoice)
            self.db.flush()
            for charge in normalized_charges:
                self.db.add(
                    models.CustomerBillingLedgerEntry(
                        organization_id=organization_id,
                        billing_account_id=billing_account_id,
                        invoice_id=invoice.id,
                        entry_kind="charge",
                        source="content_cycle_usage",
                        amount_minor=charge.amount_minor,
                        currency=currency,
                        description=charge.description,
                        content_cycle_id=charge.content_cycle_id,
                        generation_cost_ledger_entry_id=charge.generation_cost_ledger_entry_id,
                        related_entry_id=None,
                        transaction_reference=None,
                        idempotency_key=self._charge_idempotency_key(
                            organization_id,
                            idempotency_key,
                            charge,
                        ),
                        recorded_by_user_profile_id=actor_user_profile_id,
                        occurred_at=now,
                    )
                )
            self._add_audit(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action="issue_customer_usage_invoice",
                entity_type="customer_invoice",
                entity_id=str(invoice.id),
                metadata={
                    "invoice_number": invoice_number,
                    "currency": currency,
                    "charge_count": len(normalized_charges),
                    "total_minor": sum(item.amount_minor for item in normalized_charges),
                    "no_external_charge": True,
                },
            )
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                concurrent = self.db.scalar(
                    select(models.CustomerInvoice).where(
                        models.CustomerInvoice.organization_id == organization_id,
                        models.CustomerInvoice.idempotency_key == idempotency_key,
                    )
                )
                if concurrent and self._invoice_matches(
                    concurrent,
                    billing_account_id=billing_account_id,
                    actor_user_profile_id=actor_user_profile_id,
                    subscription_state_id=subscription_state_id,
                    invoice_number=invoice_number,
                    currency=currency,
                    period_start=period_start,
                    period_end=period_end,
                    due_at=due_at,
                    usage_charges=normalized_charges,
                ):
                    return InvoiceIssueResult(invoice=concurrent, created=False)
                raise CustomerBillingConflictError(
                    "Invoice conflicts with existing immutable billing history."
                ) from exc
            self.db.refresh(invoice)
            return InvoiceIssueResult(invoice=invoice, created=True)

    def add_credit(
        self,
        *,
        organization_id: int,
        billing_account_id: int,
        invoice_id: int,
        target_charge_entry_id: int,
        actor_user_profile_id: int,
        amount_minor: int,
        reason: str,
        idempotency_key: str,
        occurred_at: datetime | None = None,
    ) -> BillingLedgerRecordResult:
        with _BILLING_LOCK:
            occurred_at_was_supplied = occurred_at is not None
            organization_id = self._positive_id(organization_id, "organization_id")
            billing_account_id = self._positive_id(billing_account_id, "billing_account_id")
            invoice_id = self._positive_id(invoice_id, "invoice_id")
            target_charge_entry_id = self._positive_id(
                target_charge_entry_id,
                "target_charge_entry_id",
            )
            actor_user_profile_id = self._positive_id(
                actor_user_profile_id,
                "actor_user_profile_id",
            )
            amount_minor = self._positive_minor(amount_minor, "amount_minor")
            reason = self._description(reason, "reason")
            idempotency_key = self._safe_key(idempotency_key, "idempotency_key")
            occurred_at = self._occurred_at(occurred_at, "occurred_at")

            account = self._owned_account(organization_id, billing_account_id)
            invoice = self._owned_invoice(
                organization_id,
                billing_account_id,
                invoice_id,
                for_update=True,
            )
            self._require_finance_actor(organization_id, actor_user_profile_id)

            request_values = {
                "billing_account_id": billing_account_id,
                "invoice_id": invoice_id,
                "entry_kind": "credit",
                "source": "manual_credit",
                "amount_minor": amount_minor,
                "currency": invoice.currency,
                "description": reason,
                "content_cycle_id": None,
                "generation_cost_ledger_entry_id": None,
                "related_entry_id": target_charge_entry_id,
                "transaction_reference": None,
                "recorded_by_user_profile_id": actor_user_profile_id,
            }
            if occurred_at_was_supplied:
                request_values["occurred_at"] = occurred_at
            replay = self._ledger_replay(organization_id, idempotency_key)
            if replay:
                if self._matches(replay, **request_values):
                    return BillingLedgerRecordResult(entry=replay, created=False)
                raise CustomerBillingConflictError(
                    "Idempotency key was already used for another billing ledger fact."
                )

            target = self.db.get(models.CustomerBillingLedgerEntry, target_charge_entry_id)
            if (
                not target
                or target.organization_id != organization_id
                or target.billing_account_id != billing_account_id
                or target.invoice_id != invoice_id
                or target.entry_kind != "charge"
            ):
                raise CustomerBillingOwnershipError(
                    "Credit must target an exact charge on this owned invoice."
                )
            existing_credit = self.db.scalar(
                select(models.CustomerBillingLedgerEntry).where(
                    models.CustomerBillingLedgerEntry.related_entry_id == target.id
                )
            )
            if existing_credit:
                raise CustomerBillingConflictError(
                    "This charge already has an immutable credit entry."
                )
            totals = self.invoice_totals(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                invoice_id=invoice_id,
            )
            if amount_minor > target.amount_minor:
                raise CustomerBillingValidationError("Credit cannot exceed its target charge.")
            if amount_minor > totals.balance_minor:
                raise CustomerBillingStateError(
                    "Credit would create an unhandled customer overpayment; reconcile it separately."
                )
            if account.currency != invoice.currency:
                raise CustomerBillingConflictError("Invoice/account currency history is inconsistent.")

            entry = models.CustomerBillingLedgerEntry(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                invoice_id=invoice_id,
                entry_kind="credit",
                source="manual_credit",
                amount_minor=amount_minor,
                currency=invoice.currency,
                description=reason,
                related_entry_id=target.id,
                idempotency_key=idempotency_key,
                recorded_by_user_profile_id=actor_user_profile_id,
                occurred_at=occurred_at,
            )
            self.db.add(entry)
            self._add_audit(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action="record_customer_invoice_credit",
                entity_type="customer_invoice",
                entity_id=str(invoice_id),
                metadata={
                    "target_charge_entry_id": target.id,
                    "amount_minor": amount_minor,
                    "currency": invoice.currency,
                    "no_external_transfer": True,
                },
            )
            return self._commit_ledger_entry(entry, request_values, idempotency_key)

    def record_manual_payment(
        self,
        *,
        organization_id: int,
        billing_account_id: int,
        invoice_id: int,
        actor_user_profile_id: int,
        amount_minor: int,
        transaction_reference: str,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> BillingLedgerRecordResult:
        """Reconcile one external payment; this method never moves money."""

        with _BILLING_LOCK:
            organization_id = self._positive_id(organization_id, "organization_id")
            billing_account_id = self._positive_id(billing_account_id, "billing_account_id")
            invoice_id = self._positive_id(invoice_id, "invoice_id")
            actor_user_profile_id = self._positive_id(
                actor_user_profile_id,
                "actor_user_profile_id",
            )
            amount_minor = self._positive_minor(amount_minor, "amount_minor")
            transaction_reference = self._transaction_reference(transaction_reference)
            idempotency_key = self._safe_key(idempotency_key, "idempotency_key")
            occurred_at = self._occurred_at(occurred_at, "occurred_at")

            account = self._owned_account(organization_id, billing_account_id)
            invoice = self._owned_invoice(
                organization_id,
                billing_account_id,
                invoice_id,
                for_update=True,
            )
            self._require_finance_actor(organization_id, actor_user_profile_id)
            if account.currency != invoice.currency:
                raise CustomerBillingConflictError("Invoice/account currency history is inconsistent.")

            description = "Manual reconciliation of an externally completed customer payment."
            request_values = {
                "billing_account_id": billing_account_id,
                "invoice_id": invoice_id,
                "entry_kind": "payment",
                "source": "manual_payment",
                "amount_minor": amount_minor,
                "currency": invoice.currency,
                "description": description,
                "content_cycle_id": None,
                "generation_cost_ledger_entry_id": None,
                "related_entry_id": None,
                "transaction_reference": transaction_reference,
                "recorded_by_user_profile_id": actor_user_profile_id,
                "occurred_at": occurred_at,
            }
            replay = self._ledger_replay(organization_id, idempotency_key)
            if replay:
                if self._matches(replay, **request_values):
                    return BillingLedgerRecordResult(entry=replay, created=False)
                raise CustomerBillingConflictError(
                    "Idempotency key was already used for another payment fact."
                )

            used_reference = self.db.scalar(
                select(models.CustomerBillingLedgerEntry).where(
                    models.CustomerBillingLedgerEntry.organization_id == organization_id,
                    models.CustomerBillingLedgerEntry.transaction_reference == transaction_reference,
                )
            )
            if used_reference:
                raise CustomerBillingConflictError(
                    "Transaction reference was already reconciled in this organization."
                )
            totals = self.invoice_totals(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                invoice_id=invoice_id,
            )
            if totals.balance_minor <= 0:
                raise CustomerBillingStateError("Invoice has no outstanding balance.")
            if amount_minor > totals.balance_minor:
                raise CustomerBillingValidationError(
                    "Manual payment cannot exceed the outstanding invoice balance."
                )

            entry = models.CustomerBillingLedgerEntry(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                invoice_id=invoice_id,
                entry_kind="payment",
                source="manual_payment",
                amount_minor=amount_minor,
                currency=invoice.currency,
                description=description,
                transaction_reference=transaction_reference,
                idempotency_key=idempotency_key,
                recorded_by_user_profile_id=actor_user_profile_id,
                occurred_at=occurred_at,
            )
            self.db.add(entry)
            self._add_audit(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action="record_manual_customer_payment",
                entity_type="customer_invoice",
                entity_id=str(invoice_id),
                metadata={
                    "amount_minor": amount_minor,
                    "currency": invoice.currency,
                    "ledger_source": "manual_payment",
                    "no_payment_provider_called": True,
                },
            )
            return self._commit_ledger_entry(entry, request_values, idempotency_key)

    def invoice_totals(
        self,
        *,
        organization_id: int,
        billing_account_id: int,
        invoice_id: int,
    ) -> InvoiceTotals:
        organization_id = self._positive_id(organization_id, "organization_id")
        billing_account_id = self._positive_id(billing_account_id, "billing_account_id")
        invoice_id = self._positive_id(invoice_id, "invoice_id")
        invoice = self._owned_invoice(organization_id, billing_account_id, invoice_id)
        entries = list(
            self.db.scalars(
                select(models.CustomerBillingLedgerEntry)
                .where(
                    models.CustomerBillingLedgerEntry.organization_id == organization_id,
                    models.CustomerBillingLedgerEntry.billing_account_id == billing_account_id,
                    models.CustomerBillingLedgerEntry.invoice_id == invoice_id,
                )
                .order_by(models.CustomerBillingLedgerEntry.id)
            ).all()
        )
        if any(entry.currency != invoice.currency for entry in entries):
            raise CustomerBillingConflictError(
                "Invoice contains mixed currencies and cannot be totaled safely."
            )
        charges = [entry for entry in entries if entry.entry_kind == "charge"]
        credits = [entry for entry in entries if entry.entry_kind == "credit"]
        payments = [entry for entry in entries if entry.entry_kind == "payment"]
        subtotal_minor = sum(entry.amount_minor for entry in charges)
        credits_minor = sum(entry.amount_minor for entry in credits)
        paid_minor = sum(entry.amount_minor for entry in payments)
        if credits_minor > subtotal_minor:
            raise CustomerBillingConflictError("Invoice credits exceed its immutable charges.")
        total_minor = subtotal_minor - credits_minor
        if paid_minor > total_minor:
            raise CustomerBillingConflictError("Invoice payments exceed the amount due.")
        balance_minor = total_minor - paid_minor
        if total_minor == 0:
            status = "credited"
        elif paid_minor == 0:
            status = "issued"
        elif balance_minor > 0:
            status = "partially_paid"
        else:
            status = "paid"
        return InvoiceTotals(
            organization_id=organization_id,
            billing_account_id=billing_account_id,
            invoice_id=invoice_id,
            invoice_number=invoice.invoice_number,
            currency=invoice.currency,
            charge_count=len(charges),
            credit_count=len(credits),
            payment_count=len(payments),
            subtotal_minor=subtotal_minor,
            credits_minor=credits_minor,
            total_minor=total_minor,
            paid_minor=paid_minor,
            balance_minor=balance_minor,
            status=status,
        )

    def _validate_usage_lineage(
        self,
        *,
        organization_id: int,
        currency: str,
        usage_charges: Sequence[UsageChargeInput],
    ) -> None:
        cycle_ids = [item.content_cycle_id for item in usage_charges]
        cost_ids = [item.generation_cost_ledger_entry_id for item in usage_charges]
        if len(cycle_ids) != len(set(cycle_ids)):
            raise CustomerBillingValidationError("One content cycle can be charged only once per invoice.")
        if len(cost_ids) != len(set(cost_ids)):
            raise CustomerBillingValidationError("One generation cost can back only one charge.")

        for item in usage_charges:
            cycle = self.db.get(models.ContentCycle, item.content_cycle_id)
            cost = self.db.get(
                models.GenerationCostLedgerEntry,
                item.generation_cost_ledger_entry_id,
            )
            if not cycle or cycle.organization_id != organization_id:
                raise CustomerBillingOwnershipError(
                    "Content cycle is not owned by the billing organization."
                )
            if not cost or cost.organization_id != organization_id:
                raise CustomerBillingOwnershipError(
                    "Generation cost is not owned by the billing organization."
                )
            if cycle.video_job_id != cost.video_job_id:
                raise CustomerBillingConflictError(
                    "Content cycle and generation cost do not identify the same video job."
                )
            if cost.entry_kind != "actual" or cost.status != "confirmed":
                raise CustomerBillingStateError(
                    "Customer usage requires a confirmed actual generation cost, never an estimate."
                )
            if cost.currency != currency:
                raise CustomerBillingValidationError(
                    "Cross-currency usage billing is blocked until an explicit FX policy exists."
                )
            successor_id = self.db.scalar(
                select(models.GenerationCostLedgerEntry.id).where(
                    models.GenerationCostLedgerEntry.supersedes_entry_id == cost.id
                )
            )
            if successor_id:
                raise CustomerBillingStateError(
                    "Generation cost was superseded; invoice the latest effective actual cost."
                )
            existing_charge = self.db.scalar(
                select(models.CustomerBillingLedgerEntry.id).where(
                    models.CustomerBillingLedgerEntry.organization_id == organization_id,
                    models.CustomerBillingLedgerEntry.entry_kind == "charge",
                    models.CustomerBillingLedgerEntry.content_cycle_id == cycle.id,
                )
            )
            if existing_charge:
                raise CustomerBillingConflictError(
                    "Content cycle is already present in customer billing history."
                )

    def _invoice_matches(
        self,
        invoice: models.CustomerInvoice,
        *,
        billing_account_id: int,
        actor_user_profile_id: int,
        subscription_state_id: int,
        invoice_number: str,
        currency: str,
        period_start: date,
        period_end: date,
        due_at: datetime,
        usage_charges: Sequence[UsageChargeInput],
    ) -> bool:
        if not self._matches(
            invoice,
            billing_account_id=billing_account_id,
            subscription_state_id=subscription_state_id,
            invoice_number=invoice_number,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
            due_at=due_at,
            created_by_user_profile_id=actor_user_profile_id,
        ):
            return False
        rows = list(
            self.db.scalars(
                select(models.CustomerBillingLedgerEntry).where(
                    models.CustomerBillingLedgerEntry.invoice_id == invoice.id,
                    models.CustomerBillingLedgerEntry.entry_kind == "charge",
                )
            ).all()
        )
        actual = sorted(
            (
                row.content_cycle_id,
                row.generation_cost_ledger_entry_id,
                row.amount_minor,
                row.description,
            )
            for row in rows
        )
        expected = sorted(
            (
                item.content_cycle_id,
                item.generation_cost_ledger_entry_id,
                item.amount_minor,
                item.description,
            )
            for item in usage_charges
        )
        return actual == expected

    def _commit_ledger_entry(
        self,
        entry: models.CustomerBillingLedgerEntry,
        request_values: dict,
        idempotency_key: str,
    ) -> BillingLedgerRecordResult:
        organization_id = entry.organization_id
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            concurrent = self._ledger_replay(organization_id, idempotency_key)
            if concurrent and self._matches(concurrent, **request_values):
                return BillingLedgerRecordResult(entry=concurrent, created=False)
            raise CustomerBillingConflictError(
                "Billing ledger command conflicts with existing immutable history."
            ) from exc
        self.db.refresh(entry)
        return BillingLedgerRecordResult(entry=entry, created=True)

    def _owned_account(
        self,
        organization_id: int,
        billing_account_id: int,
    ) -> models.CustomerBillingAccount:
        account = self.db.get(models.CustomerBillingAccount, billing_account_id)
        if not account or account.organization_id != organization_id:
            raise CustomerBillingOwnershipError(
                "Billing account is not owned by this organization."
            )
        return account

    def _owned_invoice(
        self,
        organization_id: int,
        billing_account_id: int,
        invoice_id: int,
        *,
        for_update: bool = False,
    ) -> models.CustomerInvoice:
        statement = select(models.CustomerInvoice).where(
            models.CustomerInvoice.id == invoice_id,
            models.CustomerInvoice.organization_id == organization_id,
            models.CustomerInvoice.billing_account_id == billing_account_id,
        )
        if for_update:
            statement = statement.with_for_update()
        invoice = self.db.scalar(statement)
        if not invoice:
            raise CustomerBillingOwnershipError("Invoice is not owned by this billing account.")
        return invoice

    def _latest_subscription_state(
        self,
        billing_account_id: int,
    ) -> models.CustomerBillingSubscriptionState | None:
        return self.db.scalar(
            select(models.CustomerBillingSubscriptionState)
            .where(models.CustomerBillingSubscriptionState.billing_account_id == billing_account_id)
            .order_by(models.CustomerBillingSubscriptionState.version.desc())
            .limit(1)
        )

    def _ledger_replay(
        self,
        organization_id: int,
        idempotency_key: str,
    ) -> models.CustomerBillingLedgerEntry | None:
        return self.db.scalar(
            select(models.CustomerBillingLedgerEntry).where(
                models.CustomerBillingLedgerEntry.organization_id == organization_id,
                models.CustomerBillingLedgerEntry.idempotency_key == idempotency_key,
            )
        )

    def _require_organization(self, organization_id: int) -> None:
        if not self.db.get(models.Organization, organization_id):
            raise CustomerBillingOwnershipError("Organization does not exist.")

    def _require_finance_actor(self, organization_id: int, user_profile_id: int) -> None:
        profile = self.db.get(models.UserProfile, user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        if (
            not profile
            or not profile.is_active
            or profile.status != "active"
            or not membership
            or membership.role not in FINANCE_ROLES
        ):
            raise CustomerBillingOwnershipError(
                "Customer billing changes require an active owner or admin membership."
            )

    def _add_audit(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        action: str,
        entity_type: str,
        entity_id: str | None,
        metadata: dict,
    ) -> None:
        self.db.add(
            models.AuditLog(
                organization_id=organization_id,
                user_profile_id=actor_user_profile_id,
                action=action,
                status="allowed",
                reason="Append-only customer billing accounting command.",
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_json=metadata,
            )
        )

    @classmethod
    def _normalize_usage_charges(
        cls,
        usage_charges: Sequence[UsageChargeInput],
    ) -> tuple[UsageChargeInput, ...]:
        if isinstance(usage_charges, (str, bytes)):
            raise CustomerBillingValidationError("usage_charges must be structured records.")
        normalized: list[UsageChargeInput] = []
        for item in usage_charges:
            if not isinstance(item, UsageChargeInput):
                raise CustomerBillingValidationError(
                    "Every usage charge must be a UsageChargeInput."
                )
            normalized.append(
                UsageChargeInput(
                    content_cycle_id=cls._positive_id(
                        item.content_cycle_id,
                        "content_cycle_id",
                    ),
                    generation_cost_ledger_entry_id=cls._positive_id(
                        item.generation_cost_ledger_entry_id,
                        "generation_cost_ledger_entry_id",
                    ),
                    amount_minor=cls._positive_minor(item.amount_minor, "amount_minor"),
                    description=cls._description(item.description, "description"),
                )
            )
        return tuple(normalized)

    @staticmethod
    def _charge_idempotency_key(
        organization_id: int,
        invoice_idempotency_key: str,
        charge: UsageChargeInput,
    ) -> str:
        raw = (
            f"{organization_id}:{invoice_idempotency_key}:"
            f"{charge.content_cycle_id}:{charge.generation_cost_ledger_entry_id}"
        )
        return f"usage-charge:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _matches(record, **values) -> bool:
        return all(getattr(record, field) == value for field, value in values.items())

    @staticmethod
    def _positive_id(value: int, field: str) -> int:
        if isinstance(value, bool):
            raise CustomerBillingValidationError(f"{field} must be a positive integer.")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise CustomerBillingValidationError(
                f"{field} must be a positive integer."
            ) from exc
        if normalized <= 0:
            raise CustomerBillingValidationError(f"{field} must be a positive integer.")
        return normalized

    @staticmethod
    def _nonnegative_integer(value: int, field: str) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > MAX_SQL_INTEGER
        ):
            raise CustomerBillingValidationError(
                f"{field} must be a non-negative integer."
            )
        return value

    @classmethod
    def _nonnegative_minor(cls, value: int, field: str) -> int:
        return cls._nonnegative_integer(value, field)

    @staticmethod
    def _positive_minor(value: int, field: str) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
            or value > MAX_SQL_INTEGER
        ):
            raise CustomerBillingValidationError(
                f"{field} must be a positive integer in minor currency units."
            )
        return value

    @staticmethod
    def _currency(value: str) -> str:
        normalized = str(value or "").strip().upper()
        if not CURRENCY_RE.fullmatch(normalized):
            raise CustomerBillingValidationError(
                "currency must be a three-letter ISO-style code."
            )
        return normalized

    @staticmethod
    def _safe_key(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not SAFE_KEY_RE.fullmatch(normalized):
            raise CustomerBillingValidationError(f"{field} has an invalid format.")
        return normalized

    @staticmethod
    def _safe_code(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not SAFE_CODE_RE.fullmatch(normalized):
            raise CustomerBillingValidationError(f"{field} has an invalid format.")
        return normalized

    @staticmethod
    def _description(value: str, field: str) -> str:
        normalized = " ".join(str(value or "").split())
        if not normalized or len(normalized) > 500:
            raise CustomerBillingValidationError(
                f"{field} must contain 1 to 500 characters."
            )
        return normalized

    @staticmethod
    def _transaction_reference(value: str) -> str:
        normalized = str(value or "").strip()
        if not SAFE_REFERENCE_RE.fullmatch(normalized):
            raise CustomerBillingValidationError(
                "transaction_reference is required and must use a safe external reference format."
            )
        return normalized

    @staticmethod
    def _billing_date(value: date, field: str) -> date:
        if isinstance(value, datetime) or not isinstance(value, date):
            raise CustomerBillingValidationError(f"{field} must be a date.")
        return value

    @classmethod
    def _optional_utc_datetime(
        cls,
        value: datetime | None,
        field: str,
    ) -> datetime | None:
        if value is None:
            return None
        return cls._utc_datetime(value, field)

    @staticmethod
    def _utc_datetime(value: datetime, field: str) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise CustomerBillingValidationError(f"{field} must include a timezone.")
        return value.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _occurred_at(cls, value: datetime | None, field: str) -> datetime:
        if value is None:
            return datetime.now(UTC).replace(tzinfo=None)
        normalized = cls._utc_datetime(value, field)
        if normalized > datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5):
            raise CustomerBillingValidationError(f"{field} cannot be in the future.")
        return normalized
