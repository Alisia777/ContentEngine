from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_invalid_auth_link_is_sanitized_only_after_a_definitive_result() -> None:
    app = _text("web/app/app.js")

    assert "function waitForAuthLinkResult(operation)" in app
    assert "function handleAuthLinkFailure(error)" in app
    assert 'state.authLinkError = failure' in app
    assert 'if (failure.definitive) clearAuthLinkUrl("/auth-link-error")' in app
    assert "if (state.authLinkError)" in app
    assert "function renderAuthLinkError()" in app
    assert 'data-action="retry-auth-link"' in app
    assert 'data-action="request-new-auth-link"' in app
    assert "Повторить эту же ссылку" in app
    assert "Запросить новую ссылку" in app
    assert 'next.search = ""' in app
    assert "Токен удалён из адресной строки" in app
    assert "не удаляли одноразовый токен" in app


def _run_node(source: str) -> dict:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable Auth-link contracts"
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)

def _app_function_block(start: str, end: str) -> str:
    app = _text("web/app/app.js")
    return app[app.index(start):app.index(end, app.index(start))]


def test_auth_link_classifier_and_url_handling_are_executable_and_fail_closed() -> None:
    functions = _app_function_block(
        "function normalizeAuthLinkError",
        "function requiresPasswordChange",
    )
    result = _run_node(
        functions
        + r'''
let current;
let replaceCalls;
let state;
let window;
function parseRoute() { return { path: window.location.hash.slice(1) || "/" }; }
function run(error, href) {
  current = new URL(href);
  replaceCalls = 0;
  state = { authLinkError: null, route: null };
  window = {
    get location() { return current; },
    history: {
      replaceState: (_state, _title, next) => {
        replaceCalls += 1;
        current = new URL(next);
      },
    },
  };
  const before = current.href;
  const failure = handleAuthLinkFailure(error);
  return {
    failure,
    before,
    after: current.href,
    replaceCalls,
    search: current.search,
    hash: current.hash,
  };
}
const failedFetch = new TypeError("Failed to fetch");
failedFetch.authPurpose = "recovery";
const cases = {
  otpExpired: run({ code: "otp_expired", status: 400, message: "Email link expired", authPurpose: "recovery" }, "https://example.test/?token_hash=secret&type=recovery"),
  badVerifier: run({ code: "bad_code_verifier", status: 400, message: "Verifier rejected", authPurpose: "invite" }, "https://example.test/?code=secret&type=invite"),
  network: run(failedFetch, "https://example.test/?token_hash=secret&type=recovery"),
  rateLimit: run({ code: "rate_limit", status: 429, message: "Too many requests" }, "https://example.test/?code=secret&type=invite"),
  invalid503: run({ code: "upstream", status: 503, message: "invalid response from upstream" }, "https://example.test/#access_token=secret&refresh_token=refresh&type=recovery"),
  unknown400: run({ code: "unexpected", status: 400, message: "Unexpected response" }, "https://example.test/?token_hash=secret&type=recovery"),
  missingSession: run({ code: "auth_link_session_missing", authLinkTransient: true, message: "missing" }, "https://example.test/?token_hash=secret&type=recovery"),
};
process.stdout.write(JSON.stringify(cases));
'''
    )

    for key in ("otpExpired", "badVerifier"):
        assert result[key]["failure"]["definitive"] is True
        assert result[key]["replaceCalls"] == 1
        assert result[key]["search"] == ""
        assert result[key]["hash"] == "#/auth-link-error"
    for key in ("network", "rateLimit", "invalid503", "unknown400", "missingSession"):
        assert result[key]["failure"]["definitive"] is False
        assert result[key]["failure"]["transient"] is True
        assert result[key]["replaceCalls"] == 0
        assert result[key]["after"] == result[key]["before"]


def test_all_supported_auth_link_shapes_return_the_session_before_url_cleanup() -> None:
    functions = _app_function_block(
        "async function requireAuthLinkSession",
        "function normalizeAuthLinkError",
    )
    result = _run_node(
        functions
        + r'''
async function run(href, method) {
  let current = new URL(href);
  let replaceCalls = 0;
  let clearCalls = 0;
  const session = { marker: method };
  globalThis.window = {
    get location() { return current; },
    history: {
      replaceState: (_state, _title, next) => {
        replaceCalls += 1;
        current = new URL(next);
      },
    },
  };
  globalThis.state = {
    route: null,
    supabase: { auth: {
      verifyOtp: async () => ({ data: { session }, error: null }),
      exchangeCodeForSession: async () => ({ data: { session }, error: null }),
      setSession: async () => ({ data: { session }, error: null }),
      getSession: async () => { throw new Error("accepted link must not call getSession"); },
    } },
  };
  globalThis.clearStoredPkceVerifier = () => { clearCalls += 1; };
  globalThis.parseRoute = () => ({ path: current.hash.slice(1) });
  const value = await consumeAuthLink();
  return { marker: value.session?.marker, accepted: value.accepted, replaceCalls, clearCalls, href: current.href };
}
async function missing() {
  let current = new URL("https://example.test/?token_hash=secret&type=recovery");
  let replaceCalls = 0;
  globalThis.window = {
    get location() { return current; },
    history: { replaceState: () => { replaceCalls += 1; } },
  };
  globalThis.state = { route: null, supabase: { auth: {
    verifyOtp: async () => ({ data: { session: null }, error: null }),
  } } };
  globalThis.clearStoredPkceVerifier = () => {};
  globalThis.parseRoute = () => ({ path: "/" });
  try {
    await consumeAuthLink();
    return { code: "none", replaceCalls };
  } catch (error) {
    return { code: error.code, replaceCalls, href: current.href };
  }
}
const output = {
  tokenHash: await run("https://example.test/?token_hash=secret&type=recovery", "verifyOtp"),
  code: await run("https://example.test/?code=secret&type=invite", "exchangeCodeForSession"),
  tokens: await run("https://example.test/#access_token=secret&refresh_token=refresh&type=recovery", "setSession"),
  missing: await missing(),
};
process.stdout.write(JSON.stringify(output));
'''
    )

    for key, marker in (
        ("tokenHash", "verifyOtp"),
        ("code", "exchangeCodeForSession"),
        ("tokens", "setSession"),
    ):
        assert result[key]["accepted"] is True
        assert result[key]["marker"] == marker
        assert result[key]["replaceCalls"] == 1
        assert result[key]["clearCalls"] == 1
    assert result["missing"]["code"] == "auth_link_session_missing"
    assert result["missing"]["replaceCalls"] == 0
    assert "token_hash=secret" in result["missing"]["href"]

def test_required_password_change_is_server_marked_and_workspace_gated() -> None:
    app = _text("web/app/app.js")
    member = _text("scripts/provision_supabase_member.py")
    owner_reset = _text("scripts/reset_supabase_owner_password.py")
    edge = _text("supabase/functions/creator-set-password/index.ts")

    marker = "contentengine_password_change_required"
    completed = "contentengine_password_change_completed"
    assert marker in app and marker in member and marker in owner_reset and marker in edge
    assert completed in app and completed in edge
    assert "state.forcePassword = requiresPasswordChange(data.user)" in app
    assert 'navigate("/set-password", true)' in app
    assert 'state.supabase.functions.invoke("creator-set-password"' in app
    assert "getUserById(userId)" in edge
    assert "updateUserById(userId" in edge
    assert "passwordChangeRequired(metadata)" in edge
    assert "password_change_not_required" in edge


def test_reset_and_invite_have_soft_timeouts_and_honest_delivery_copy() -> None:
    app = _text("web/app/app.js")
    api = _text("web/app/supabase-api.js")

    assert "AUTH_REQUEST_TIMEOUT_MS = 15_000" in app
    assert "INVITE_REQUEST_TIMEOUT_MS = 25_000" in app
    assert "PUBLIC_RECOVERY_RECEIPT_STORAGE_KEY" in app
    public_reset = app.split("async function submitReset", 1)[1].split(
        "async function submitPassword",
        1,
    )[0]
    manager_recovery = app.split('if (action === "send-manager-recovery")', 1)[1].split(
        'if (action === "copy-manager-reminder")',
        1,
    )[0]
    assert "resetPasswordForEmail" not in public_reset
    assert "state.api.requestPublicPasswordRecovery" in public_reset
    assert "withUiTimeout(" in public_reset
    assert "resetPasswordForEmail" not in manager_recovery
    assert 'const ACCESS_FUNCTION = "creator-access"' in api
    assert "state.api.inspectAccess(normalizedEmail)" in app
    assert "state.api.repairAccess(normalizedEmail)" in app
    assert "function startResetResendCountdown()" in app
    assert "Это квитанция запроса, а не подтверждение доставки письма" in app
    assert "Ответ одинаков для любого адреса и не раскрывает наличие аккаунта" in app
    assert 'status: "pending_verification"' in app
    assert 'reason_code: "client_timeout"' in app


def test_invite_attempts_are_reasoned_and_persisted_server_side() -> None:
    edge = _text("supabase/functions/creator-invite/index.ts")
    migration = _text(
        "supabase/migrations/202607150002_access_recovery_invite_reliability.sql"
    ).casefold()
    api = _text("web/app/supabase-api.js")
    app = _text("web/app/app.js")

    assert "reason_code" in edge
    assert "delivery_status" in edge
    assert 'const requestId = crypto.randomUUID()' in edge
    assert '"system_record_invite_delivery_attempts"' in edge
    assert "create table if not exists content_factory.invite_delivery_attempts" in migration
    assert "create or replace function public.system_record_invite_delivery_attempts" in migration
    assert "create or replace function public.creator_invite_delivery_attempts" in migration
    assert (
        "grant execute on function public.system_record_invite_delivery_attempts(jsonb)"
        in migration
    )
    assert "to service_role" in migration
    assert (
        "grant execute on function public.creator_invite_delivery_attempts(jsonb)"
        in migration
    )
    assert "creator_invite_delivery_attempts" in api
    assert "persistTeamInviteResult" in app
    assert 'data-action="prepare-failed-invites"' in app


def test_fifty_address_invite_is_prejournaled_bounded_and_idempotently_updated() -> None:
    edge = _text("supabase/functions/creator-invite/index.ts")
    migration = _text(
        "supabase/migrations/202607150004_invite_batch_resilience.sql"
    ).casefold()
    pgtap = _text("supabase/tests/invite_batch_resilience_test.sql").casefold()

    assert "const MAX_INVITES = 50" in edge
    assert "const MAX_CONCURRENT_INVITES = 5" in edge
    assert 'status: "pending_verification"' in edge
    assert 'reason_code: "invite_processing_started"' in edge
    assert 'delivery_status: "unknown"' in edge
    assert 'code: "invite_journal_unavailable"' in edge
    assert "const reservation = await persistResults(pendingResults)" in edge
    assert 'reason_code: "duplicate_request_suppressed"' in edge
    assert "const workIndexes: number[] = []" in edge
    assert edge.index("persistResults(pendingResults)") < edge.index(
        ".auth.admin.inviteUserByEmail"
    )
    assert "Math.min(MAX_CONCURRENT_INVITES, workIndexes.length)" in edge
    assert "await Promise.all(" in edge
    assert "persistResults([result])" in edge
    assert "persistencePending" in edge
    assert "persistResults(retryResults)" in edge
    assert edge.count(".auth.admin.inviteUserByEmail") == 1

    assert "pending_verification" in migration
    assert "delivery_status in ('accepted_unconfirmed', 'not_requested', 'unknown')" in migration
    assert "pg_catalog.pg_advisory_xact_lock" in migration
    assert "interval '10 minutes'" in migration
    assert "duplicate_request_suppressed" in migration
    assert "'suppressed', suppressed_value" in migration
    assert "on conflict on constraint invite_delivery_attempts_request_email_uq do update" in migration
    assert "to service_role" in migration
    assert "select plan(6)" in pgtap
    assert "duplicate_request_suppressed" in pgtap
    assert "not has_function_privilege" in pgtap
