from __future__ import annotations

from dataclasses import dataclass

from app import models


@dataclass(frozen=True)
class UsageChargeInput:
    content_cycle_id: int
    generation_cost_ledger_entry_id: int
    amount_minor: int
    description: str


@dataclass(frozen=True)
class BillingAccountResult:
    account: models.CustomerBillingAccount
    created: bool


@dataclass(frozen=True)
class SubscriptionStateResult:
    state: models.CustomerBillingSubscriptionState
    created: bool


@dataclass(frozen=True)
class InvoiceIssueResult:
    invoice: models.CustomerInvoice
    created: bool


@dataclass(frozen=True)
class BillingLedgerRecordResult:
    entry: models.CustomerBillingLedgerEntry
    created: bool


@dataclass(frozen=True)
class InvoiceTotals:
    organization_id: int
    billing_account_id: int
    invoice_id: int
    invoice_number: str
    currency: str
    charge_count: int
    credit_count: int
    payment_count: int
    subtotal_minor: int
    credits_minor: int
    total_minor: int
    paid_minor: int
    balance_minor: int
    status: str
