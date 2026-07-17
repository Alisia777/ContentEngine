from __future__ import annotations

from pathlib import Path
import re
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase" / "functions" / "creator-recovery" / "index.ts"
API = ROOT / "web" / "app" / "supabase-api.js"
APP = ROOT / "web" / "app" / "app.js"
CONFIG = ROOT / "supabase" / "config.toml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
DEPLOY = ROOT / ".github" / "workflows" / "supabase-pages.yml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _recovery_migration() -> str:
    candidates = sorted(
        (ROOT / "supabase" / "migrations").glob("*public*recovery*.sql")
    )
    assert candidates, "A versioned public-recovery receipt migration is required"
    return "\n".join(_text(path) for path in candidates).casefold()


def _function_block(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_public_recovery_edge_has_exact_request_and_status_protocol() -> None:
    assert EDGE.is_file()
    edge = _text(EDGE)

    assert 'if (action === "status")' in edge
    assert 'if (action !== "request")' in edge
    assert "UUID_PATTERN" in edge
    assert "UUID_PATTERN.test" in edge
    assert 'code: "request_id_invalid"' in edge
    assert 'new Set(["action", "email", "request_id"])' in edge
    assert 'new Set(["action", "receipt_token"])' in edge
    assert '"redirect_to"' not in edge
    assert "encodeURIComponent(RECOVERY_REDIRECT_URL)" in edge
    assert 'action: "request"' in edge
    assert 'action: "status"' in edge
    assert "/auth/v1/recover?redirect_to=" in edge

    # Public recovery must stay non-enumerating: the Edge Function asks GoTrue
    # to recover an address but never performs an identity lookup of its own.
    for forbidden in (
        "listUsers(",
        "getUserById(",
        "getUserByEmail(",
        "user_exists",
        "account_exists",
        "identity_exists",
    ):
        assert forbidden not in edge


def test_public_recovery_is_reserved_before_the_only_provider_send() -> None:
    edge = _text(EDGE)

    reserve = edge.index("system_reserve_public_recovery")
    provider = edge.index("/auth/v1/recover?redirect_to=")
    assert reserve < provider
    assert edge.count("/auth/v1/recover?redirect_to=") == 1
    assert "system_finalize_public_recovery" in edge
    assert "retry_after_seconds" in edge
    assert "delivery_confirmed: false" in edge

    migration = _recovery_migration()
    for marker in (
        "request_id",
        "receipt_hash",
        "retry_after_seconds",
        "pg_advisory_xact_lock",
        "system_reserve_public_recovery",
        "system_finalize_public_recovery",
        "system_read_public_recovery",
    ):
        assert marker in migration
    assert "to service_role" in migration
    assert "from public, anon, authenticated" in migration
    assert re.search(
        r"unique\s*\([^)]*request_id[^)]*\)|request_id[^\n]+unique",
        migration,
    )


def test_same_request_id_returns_the_reserved_receipt_without_a_second_send() -> None:
    edge = _text(EDGE)
    migration = _recovery_migration()

    # A retry is resolved by the server-side reservation. The provider call is
    # only reachable for a newly reserved row, never for an existing request.
    assert "receiptMaterial(requestId" in edge
    assert '"HMAC"' in edge
    assert "receipt_token" in edge
    assert "existing_receipt" in migration
    assert "'replayed', true" in migration
    assert "'dispatch_required', false" in migration
    assert edge.index("system_reserve_public_recovery") < edge.index(
        "/auth/v1/recover?redirect_to="
    )


def test_browser_api_uses_only_creator_recovery_with_public_safe_shapes() -> None:
    api = _text(API)

    assert 'const PUBLIC_RECOVERY_FUNCTION = "creator-recovery"' in api
    assert "requestPublicPasswordRecovery({" in api
    assert "getPublicRecoveryReceipt({ receiptToken } = {})" in api
    request = _function_block(
        api,
        "requestPublicPasswordRecovery(",
        "getPublicRecoveryReceipt(",
    )
    status = api[api.index("getPublicRecoveryReceipt(") :]
    assert 'this.invokePublicRecovery("request"' in request
    assert "email:" in request
    assert "request_id:" in request
    assert "redirect_to:" not in request
    assert 'this.invokePublicRecovery("status"' in status
    assert "receipt_token:" in status
    assert "resetPasswordForEmail" not in api


def test_reset_ui_persists_only_opaque_recovery_coordinates() -> None:
    app = _text(APP)
    submit = _function_block(
        app,
        "async function submitReset(form)",
        "async function submitPassword(form)",
    )

    assert "resetPasswordForEmail" not in submit
    assert "requestPublicPasswordRecovery" in submit
    assert "crypto.randomUUID()" in submit
    assert "persistPublicRecovery" in app
    assert "readStoredPublicRecoveryReceipt" in app
    assert "getPublicRecoveryReceipt" in app

    persist_match = re.search(
        r"function\s+persistPublicRecovery\w*\([^)]*\)\s*\{(?P<body>.*?)\n\}",
        app,
        flags=re.DOTALL,
    )
    assert persist_match, "A dedicated localStorage persistence boundary is required"
    persistence = persist_match.group("body")
    assert "localStorage" in persistence
    assert "receipt" in persistence
    assert "request" in persistence
    assert "email" not in persistence.casefold()
    assert "maskedEmail" not in persistence


def test_network_failure_preserves_request_id_for_safe_retry_and_reload() -> None:
    app = _text(APP)
    submit = _function_block(
        app,
        "async function submitReset(form)",
        "async function submitPassword(form)",
    )

    request_call = submit.index("requestPublicPasswordRecovery")
    assert submit.index("persistPublicRecovery") < request_call
    assert "requestId" in submit
    assert "catch (error)" in submit
    catch = submit[submit.index("catch (error)") :]
    assert "removeItem" not in catch
    assert "resetReceipt = null" not in catch

    # Restoration must be part of application startup, not only reset-page
    # rendering, so a reload or a new tab can recover server cooldown state.
    restore_call = app.index("readStoredPublicRecoveryReceipt()")
    submit_index = app.index("async function submitReset(form)")
    assert restore_call < submit_index
    assert "retry_after_seconds" in app


def test_public_recovery_is_deployed_unauthenticated_but_ci_checked() -> None:
    config = tomllib.loads(_text(CONFIG))
    assert config["functions"]["creator-recovery"]["verify_jwt"] is False

    ci = _text(CI)
    for command in (
        "deno fmt --check supabase/functions/creator-recovery",
        "deno lint supabase/functions/creator-recovery/index.ts",
        "deno check supabase/functions/creator-recovery/index.ts",
    ):
        assert command in ci

    deploy = yaml.safe_load(_text(DEPLOY))
    steps = deploy["jobs"]["migrate"]["steps"]
    recovery_steps = [
        step
        for step in steps
        if str(step.get("name", "")).startswith("Deploy public")
    ]
    assert len(recovery_steps) == 1
    assert "--no-verify-jwt" in recovery_steps[0]["run"]
