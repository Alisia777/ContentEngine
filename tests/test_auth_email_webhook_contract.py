from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = (
    ROOT / "supabase" / "functions" / "auth-email-webhook" / "index.ts"
).read_text(encoding="utf-8")


def test_webhook_is_not_browser_callable_and_fails_closed_without_secret() -> None:
    assert 'auth: "none"' in EDGE
    assert "cors: false" in EDGE
    assert 'request.headers.get("origin") !== null' in EDGE
    assert '"origin_not_allowed"' in EDGE
    assert 'Deno.env.get("RESEND_WEBHOOK_SECRET")' in EDGE
    assert '"webhook_not_configured"' in EDGE
    assert "access-control-allow-origin" not in EDGE


def test_svix_signature_is_verified_over_bounded_raw_body_before_json_parse() -> None:
    raw_read = EDGE.index("rawBody = await readBoundedStream")
    verification = EDGE.index("verifySvixSignature(request, rawBody)")
    parsing = EDGE.index("payload = JSON.parse")
    assert raw_read < verification < parsing
    assert 'request.headers.get("svix-id")' in EDGE
    assert 'request.headers.get("svix-timestamp")' in EDGE
    assert 'request.headers.get("svix-signature")' in EDGE
    assert "MAX_CLOCK_SKEW_SECONDS = 300" in EDGE
    assert 'crypto.subtle.importKey(' in EDGE
    assert '"HMAC", hash: "SHA-256"' in EDGE
    assert "timingSafeEqual" in EDGE


def test_resend_delivery_states_are_normalized_without_calling_failures_bounces() -> None:
    expected = {
        "email.sent": "accepted_unconfirmed",
        "email.delivered": "delivered",
        "email.delivery_delayed": "deferred",
        "email.failed": "failed",
        "email.bounced": "bounced",
        "email.suppressed": "suppressed",
        "email.complained": "complained",
    }
    for event_type, delivery_status in expected.items():
        assert f'["{event_type}", "{delivery_status}"]' in EDGE
    assert '["email.failed", "bounced"]' not in EDGE


def test_webhook_requires_one_recipient_message_id_and_event_time() -> None:
    assert "payload.data.email_id" in EDGE
    assert "eventRecipient(payload.data)" in EDGE
    assert "parseEventTimestamp(payload.created_at)" in EDGE
    assert (
        "providerMessageId === null || recipient === null ||\n"
        "    eventCreatedAt === null"
    ) in EDGE
    assert '"event_fields_invalid"' in EDGE


def test_verified_events_use_only_the_service_ingest_rpc_and_safe_response() -> None:
    assert '"system_ingest_auth_email_delivery_event"' in EDGE
    assert 'provider: "resend"' in EDGE
    assert "provider_event_id: verified.providerEventId" in EDGE
    assert "provider_message_id: providerMessageId" in EDGE
    assert "recipient," in EDGE
    assert "rawBody" not in EDGE[EDGE.index("p_payload: {") : EDGE.index(
        "if (error || !isRecord(data))"
    )]
    assert "correlation_status: correlationStatus" in EDGE
    assert "delivery_projected: data.delivery_projected === true" in EDGE


def test_replay_identity_is_forwarded_but_raw_headers_and_payload_are_not_stored() -> None:
    rpc_payload = EDGE[
        EDGE.index("p_payload: {") : EDGE.index("if (error || !isRecord(data))")
    ]
    assert "provider_event_id" in rpc_payload
    for forbidden in (
        "svix-signature",
        "authorization",
        "subject",
        "from",
        "rawBody",
        "payload.data.tags",
    ):
        assert forbidden not in rpc_payload
