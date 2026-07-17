from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607170006_auth_email_trusted_correlation.sql"
).read_text(encoding="utf-8")


def test_exact_delivery_requires_provider_message_and_recipient_identity() -> None:
    exact_query = MIGRATION[
        MIGRATION.index("-- Exact means all three immutable dispatch facts agree") :
        MIGRATION.index("-- Recipient-window matching is evidence")
    ]
    assert "attempt.provider = provider_value" in exact_query
    assert "attempt.provider_message_id = provider_message_value" in exact_query
    assert "attempt.email = recipient_value" in exact_query
    assert "legacy_attempt.delivery_status = 'not_requested'" in exact_query
    assert "correlation_value := 'exact'" in exact_query
    assert "basis_value := 'provider_message_id'" in exact_query


def test_recipient_window_is_never_exact_or_projected() -> None:
    window_query = MIGRATION[
        MIGRATION.index("-- Recipient-window matching is evidence") :
        MIGRATION.index("insert into content_factory.auth_email_delivery_events")
    ]
    assert "correlation_value := 'ambiguous'" in window_query
    assert "basis_value := 'unique_recipient_window'" in window_query
    assert "correlation_value := 'exact'" not in window_query
    assert "matched_attempt_id := null" in window_query

    projection = MIGRATION[
        MIGRATION.index("if correlation_value = 'exact'") :
        MIGRATION.index("return jsonb_build_object(", MIGRATION.index("if correlation_value = 'exact'"))
    ]
    assert "correlation_value = 'exact'" in projection
    assert "unique_recipient_window" not in projection
    assert "provider_message_id =" not in projection


def test_access_retry_is_fail_closed_without_trusted_correlation() -> None:
    assert "delivery_is_unresolved" in MIGRATION
    assert "delivery_snapshot ->> 'status' in ('reserved', 'accepted')" in MIGRATION
    assert "delivery_snapshot ->> 'correlation_status' = 'exact'" in MIGRATION
    assert "delivery_snapshot ->> 'correlation_basis' = 'provider_message_id'" in MIGRATION
    assert "result ->> 'recommended_action' in ('invite', 'recovery')" in MIGRATION
    assert "'{recommended_action}', '\"manual_review\"'::jsonb" in MIGRATION


def test_rpc_response_contract_keeps_existing_keys() -> None:
    response = MIGRATION[MIGRATION.rindex("return jsonb_build_object(") :]
    for key in (
        "'ok'",
        "'inserted'",
        "'event_id'",
        "'correlation_status'",
        "'correlation_basis'",
        "'attempt_id'",
        "'delivery_projected'",
    ):
        assert key in response

    assert "result :=" in MIGRATION
    assert "return result" in MIGRATION
    assert "jsonb_build_object" not in MIGRATION[
        MIGRATION.index("create or replace function public.creator_account_access_status") :
    ]
