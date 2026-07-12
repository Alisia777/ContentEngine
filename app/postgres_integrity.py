"""PostgreSQL database-level integrity guards used by runtime and Alembic.

Application/ORM listeners are useful feedback for normal code paths, but they
do not protect rows changed through SQL, an admin console, or a future service.
Production therefore installs these guards in the database migration itself.
The installer remains reusable by ``init_db`` for non-production/dev databases
that intentionally create their schema from SQLAlchemy metadata.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.engine import Connection


POSTGRES_INTEGRITY_TRIGGER_TABLES: Mapping[str, str] = {
    "generation_cost_ledger_entries_append_only": "generation_cost_ledger_entries",
    "product_ugc_queue_reconciliation_no_mutation": "product_ugc_queue_reconciliations",
    "customer_billing_accounts_append_only": "customer_billing_accounts",
    "customer_billing_subscription_states_append_only": "customer_billing_subscription_states",
    "customer_invoices_append_only": "customer_invoices",
    "customer_billing_ledger_entries_append_only": "customer_billing_ledger_entries",
    "customer_billing_ledger_no_overapply": "customer_billing_ledger_entries",
    "visual_evidence_snapshot_append_only": "visual_evidence_snapshots",
    "wildberries_analytics_sync_audits_append_only": "wildberries_analytics_sync_audits",
    "wildberries_metric_snapshots_append_only": "wildberries_metric_snapshots",
    "wildberries_metric_quarantine_append_only": "wildberries_metric_quarantine",
}

POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS: Mapping[str, str] = {
    "generation_cost_ledger_entries_append_only": "qvf_generation_cost_ledger_append_only",
    "product_ugc_queue_reconciliation_no_mutation": (
        "prevent_product_ugc_queue_reconciliation_mutation"
    ),
    "customer_billing_accounts_append_only": "qvf_customer_billing_append_only",
    "customer_billing_subscription_states_append_only": "qvf_customer_billing_append_only",
    "customer_invoices_append_only": "qvf_customer_billing_append_only",
    "customer_billing_ledger_entries_append_only": "qvf_customer_billing_append_only",
    "customer_billing_ledger_no_overapply": "qvf_customer_billing_no_overapply",
    "visual_evidence_snapshot_append_only": "qvf_visual_evidence_append_only",
    "wildberries_analytics_sync_audits_append_only": (
        "qvf_wildberries_analytics_append_only"
    ),
    "wildberries_metric_snapshots_append_only": "qvf_wildberries_analytics_append_only",
    "wildberries_metric_quarantine_append_only": "qvf_wildberries_analytics_append_only",
}

POSTGRES_INTEGRITY_FUNCTION_NAMES = frozenset(
    POSTGRES_INTEGRITY_TRIGGER_FUNCTIONS.values()
)


_FUNCTION_DDL = (
    """
    CREATE OR REPLACE FUNCTION qvf_generation_cost_ledger_append_only()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'generation cost ledger is append-only';
    END;
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION prevent_product_ugc_queue_reconciliation_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'product ugc queue reconciliation is append-only';
    END;
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION qvf_customer_billing_append_only()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'customer billing records are append-only';
    END;
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION qvf_customer_billing_no_overapply()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        outstanding BIGINT;
    BEGIN
        IF NEW.entry_kind IN ('credit', 'payment') THEN
            -- Serialize credits/payments for one invoice so two concurrent
            -- inserts cannot both observe the same outstanding balance.
            PERFORM id
            FROM customer_invoices
            WHERE id = NEW.invoice_id
              AND organization_id = NEW.organization_id
            FOR UPDATE;

            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN entry_kind = 'charge' THEN amount_minor
                        ELSE -amount_minor
                    END
                ),
                0
            )
            INTO outstanding
            FROM customer_billing_ledger_entries
            WHERE invoice_id = NEW.invoice_id
              AND organization_id = NEW.organization_id;

            IF NEW.amount_minor > outstanding THEN
                RAISE EXCEPTION
                    'customer billing entry exceeds outstanding balance';
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION qvf_visual_evidence_append_only()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'visual evidence snapshots are append-only';
    END;
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION qvf_wildberries_analytics_append_only()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'Wildberries analytics evidence is append-only';
    END;
    $$
    """,
)


_TRIGGER_DDL = (
    """
    CREATE TRIGGER generation_cost_ledger_entries_append_only
    BEFORE UPDATE OR DELETE ON generation_cost_ledger_entries
    FOR EACH ROW EXECUTE FUNCTION qvf_generation_cost_ledger_append_only()
    """,
    """
    CREATE TRIGGER product_ugc_queue_reconciliation_no_mutation
    BEFORE UPDATE OR DELETE ON product_ugc_queue_reconciliations
    FOR EACH ROW EXECUTE FUNCTION prevent_product_ugc_queue_reconciliation_mutation()
    """,
    """
    CREATE TRIGGER customer_billing_accounts_append_only
    BEFORE UPDATE OR DELETE ON customer_billing_accounts
    FOR EACH ROW EXECUTE FUNCTION qvf_customer_billing_append_only()
    """,
    """
    CREATE TRIGGER customer_billing_subscription_states_append_only
    BEFORE UPDATE OR DELETE ON customer_billing_subscription_states
    FOR EACH ROW EXECUTE FUNCTION qvf_customer_billing_append_only()
    """,
    """
    CREATE TRIGGER customer_invoices_append_only
    BEFORE UPDATE OR DELETE ON customer_invoices
    FOR EACH ROW EXECUTE FUNCTION qvf_customer_billing_append_only()
    """,
    """
    CREATE TRIGGER customer_billing_ledger_entries_append_only
    BEFORE UPDATE OR DELETE ON customer_billing_ledger_entries
    FOR EACH ROW EXECUTE FUNCTION qvf_customer_billing_append_only()
    """,
    """
    CREATE TRIGGER customer_billing_ledger_no_overapply
    BEFORE INSERT ON customer_billing_ledger_entries
    FOR EACH ROW EXECUTE FUNCTION qvf_customer_billing_no_overapply()
    """,
    """
    CREATE TRIGGER visual_evidence_snapshot_append_only
    BEFORE UPDATE OR DELETE ON visual_evidence_snapshots
    FOR EACH ROW EXECUTE FUNCTION qvf_visual_evidence_append_only()
    """,
    """
    CREATE TRIGGER wildberries_analytics_sync_audits_append_only
    BEFORE UPDATE OR DELETE ON wildberries_analytics_sync_audits
    FOR EACH ROW EXECUTE FUNCTION qvf_wildberries_analytics_append_only()
    """,
    """
    CREATE TRIGGER wildberries_metric_snapshots_append_only
    BEFORE UPDATE OR DELETE ON wildberries_metric_snapshots
    FOR EACH ROW EXECUTE FUNCTION qvf_wildberries_analytics_append_only()
    """,
    """
    CREATE TRIGGER wildberries_metric_quarantine_append_only
    BEFORE UPDATE OR DELETE ON wildberries_metric_quarantine
    FOR EACH ROW EXECUTE FUNCTION qvf_wildberries_analytics_append_only()
    """,
)


def _require_postgresql(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        raise ValueError("PostgreSQL integrity guards require a PostgreSQL connection")


def install_postgresql_integrity_guards(connection: Connection) -> None:
    """Install or repair every production integrity function and trigger."""

    _require_postgresql(connection)
    for statement in _FUNCTION_DDL:
        connection.execute(text(statement))

    # Drop/recreate is transactional in PostgreSQL and guarantees an existing
    # same-named trigger cannot silently retain an obsolete event or function.
    for trigger_name, table_name in POSTGRES_INTEGRITY_TRIGGER_TABLES.items():
        connection.execute(
            text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
        )
    for statement in _TRIGGER_DDL:
        connection.execute(text(statement))


def drop_postgresql_integrity_guards(connection: Connection) -> None:
    """Remove guards before the initial schema downgrade drops their tables."""

    _require_postgresql(connection)
    for trigger_name, table_name in POSTGRES_INTEGRITY_TRIGGER_TABLES.items():
        connection.execute(
            text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
        )
    for function_name in POSTGRES_INTEGRITY_FUNCTION_NAMES:
        connection.execute(text(f"DROP FUNCTION IF EXISTS {function_name}()"))
