from pathlib import Path
import json
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CREATOR_RPC_MIGRATION = ROOT / "supabase" / "migrations" / "202607130004_creator_rpcs.sql"


def _text(name: str) -> str:
    return (APP / name).read_text(encoding="utf-8")


def test_static_spa_assets_are_complete_and_cloud_only() -> None:
    expected = {
        "index.html",
        "styles.css",
        "config.js",
        "config.example.js",
        "catalog.js",
        "supabase-api.js",
        "app.js",
        "generation-spend-view.js",
    }
    assert expected <= {path.name for path in APP.iterdir() if path.is_file()}

    bundle = "\n".join(_text(name) for name in expected)
    assert "http://localhost" not in bundle
    assert "http://127.0.0.1" not in bundle
    assert "render.com" not in bundle.casefold()
    assert "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm" in bundle
    assert "@supabase/supabase-js@latest" not in bundle


def test_pages_config_contains_only_browser_safe_coordinates_and_generation_flags() -> None:
    config = _text("config.js")
    example = _text("config.example.js")
    assert 'SUPABASE_URL: "https://iyckwryrucqrxwlowxow.supabase.co"' in config
    assert re.search(
        r'SUPABASE_PUBLISHABLE_KEY: "sb_publishable_[A-Za-z0-9_-]{20,}"', config
    )
    assert 'STORAGE_BUCKET: "contentengine-private"' in config
    assert "MOCK_ENABLED: true" in config
    assert "REAL_GENERATION_ENABLED: true" in config
    assert "MOCK_ONLY:" not in config
    assert "MOCK_ENABLED: true" in example
    assert "REAL_GENERATION_ENABLED: false" in example
    app = _text("app.js")
    assert 'typeof config.MOCK_ENABLED !== "boolean"' in app
    assert 'typeof config.REAL_GENERATION_ENABLED !== "boolean"' in app
    assert "config.MOCK_ONLY" not in app
    assert "MAX_BATCH_SIZE: 50" in config
    assert not re.search(r"(?:eyJ[a-zA-Z0-9_-]{20,}|sb_secret_[a-zA-Z0-9_-]+)", config)
    assert "postgresql://" not in config


def test_auth_supports_password_invite_recovery_and_hash_routes_without_signup() -> None:
    app = _text("app.js")
    for method in (
        "signInWithPassword",
        "verifyOtp",
        "exchangeCodeForSession",
        "setSession",
        "resetPasswordForEmail",
        "updateUser",
    ):
        assert method in app
    assert "signUp(" not in app
    assert 'window.addEventListener("hashchange"' in app
    assert 'query.get("token_hash") || fragment.get("token_hash")' in app
    assert '#/set-password' in app
    assert '#/workspace/generation' in app


def test_auth_session_is_tab_scoped_while_only_pkce_verifier_is_cross_tab() -> None:
    app = _text("app.js")
    assert "persistSession: true" in app
    assert "storage: createHybridAuthStorage()" in app
    assert "contentengine.creator-workspace." in app
    assert ".auth-session.v1" in app
    assert "const verifierStorage = window.localStorage" in app
    assert "const sessionStorage = window.sessionStorage" in app
    assert "isPkceVerifierStorageKey" in app
    assert "safeStorageSet(sessionStorage, key, value)" in app
    assert "safeStorageSet(verifierStorage, key, value)" in app
    assert "clearStoredPkceVerifier();" in app
    assert "Сессия действует только в этой вкладке" in app
    assert "Самостоятельная регистрация закрыта" in app


def test_blocked_local_storage_keeps_pkce_verifier_in_session_fallback() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable auth storage contracts")

    app = _text("app.js")
    helpers = app[
        app.index("function createHybridAuthStorage()") :
        app.index("function clearStoredPkceVerifier()")
    ]
    script = f"""
const createMemoryStorage = (blocked = false) => {{
  const values = new Map();
  return {{
    getItem(key) {{
      if (blocked) throw new Error("blocked");
      return values.has(key) ? values.get(key) : null;
    }},
    setItem(key, value) {{
      if (blocked) throw new Error("blocked");
      values.set(key, String(value));
    }},
    removeItem(key) {{
      if (blocked) throw new Error("blocked");
      values.delete(key);
    }},
    dump() {{ return Object.fromEntries(values); }},
  }};
}};
{helpers}
const verifierKey = "contentengine.auth-code-verifier";
const sessionKey = "contentengine.auth-session";

const blockedLocal = createMemoryStorage(true);
const blockedSession = createMemoryStorage(false);
globalThis.window = {{
  localStorage: blockedLocal,
  sessionStorage: blockedSession,
}};
const blocked = createHybridAuthStorage();
blocked.setItem(verifierKey, "fallback-verifier");
blocked.setItem(sessionKey, "tab-token");

const availableLocal = createMemoryStorage(false);
const availableSession = createMemoryStorage(false);
globalThis.window = {{
  localStorage: availableLocal,
  sessionStorage: availableSession,
}};
const available = createHybridAuthStorage();
available.setItem(verifierKey, "shared-verifier");
available.setItem(sessionKey, "tab-token");

process.stdout.write(JSON.stringify({{
  blockedVerifier: blocked.getItem(verifierKey),
  blockedSessionValue: blocked.getItem(sessionKey),
  blockedSession: blockedSession.dump(),
  sharedVerifier: available.getItem(verifierKey),
  sharedLocal: availableLocal.dump(),
  sharedSession: availableSession.dump(),
}}));
"""
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["blockedVerifier"] == "fallback-verifier"
    assert payload["blockedSessionValue"] == "tab-token"
    assert payload["blockedSession"] == {
        "contentengine.auth-code-verifier": "fallback-verifier",
        "contentengine.auth-session": "tab-token",
    }
    assert payload["sharedVerifier"] == "shared-verifier"
    assert payload["sharedLocal"] == {
        "contentengine.auth-code-verifier": "shared-verifier",
    }
    assert payload["sharedSession"] == {
        "contentengine.auth-session": "tab-token",
    }


def test_training_is_server_owned_with_exact_fail_closed_catalog_and_hard_gate() -> None:
    app = _text("app.js")
    catalog = _text("catalog.js")
    required_codes = (
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    )
    for code in required_codes:
        assert catalog.count(f'"{code}"') == 1
    assert "exam_sku_mismatch" not in catalog
    assert "COURSES" not in catalog
    assert "EXAM_QUESTIONS" not in catalog
    assert "COURSES" not in app
    assert "EXAM_QUESTIONS" not in app
    assert "correct_answers" not in catalog
    assert "answer_key" not in catalog.casefold()
    assert "trainingSource.modules" in app
    assert "examSource.questions" in app
    assert "return serverCourses;" in app
    assert "return serverQuestions;" in app
    assert "trainingCatalogReady" in app
    assert "examQuestionsReady" in app
    assert "normalizeExamOption" in app
    assert "option.value" in app
    assert "option.label" in app
    assert "source.workspace_open" in app
    assert "normalizeBoolean" in app
    assert "REQUIRED_MODULE_CODES.every" in app
    assert "state.bootstrap.training.exam.passed === true" in app
    assert "next_attempt_at" in app
    assert "attempt_count_24h" in app
    assert "attempt_limit_24h" in app
    assert "examRetryState" in app
    assert "exam_attempt_limit_active" in _text("supabase-api.js")


def test_suspended_and_revoked_memberships_are_locked_before_learning_or_workspace() -> None:
    app = _text("app.js")
    adapter = _text("supabase-api.js")
    sql = CREATOR_RPC_MIGRATION.read_text(encoding="utf-8")

    for state_key, title in (
        ("membership_suspended", "Доступ приостановлен"),
        ("membership_revoked", "Доступ отозван"),
    ):
        assert state_key in sql
        assert state_key in app
        assert state_key in adapter
        assert title in app

    bootstrap_sql = sql[
        sql.index("create or replace function public.creator_bootstrap") :
        sql.index("create or replace function public.creator_complete_module")
    ]
    inactive_branch = bootstrap_sql[
        bootstrap_sql.index("if membership_row.status <> 'active' then") :
        bootstrap_sql.index("if organization_row.id is null")
    ]
    assert "'workspace_open', false" in inactive_branch
    assert "'learning'" not in inactive_branch
    assert "'storage'" not in inactive_branch
    assert not re.search(
        r"on conflict\b.*?do update set\s+status\s*=\s*'active'",
        bootstrap_sql,
        flags=re.DOTALL,
    )

    assert 'accessState: String(source.state || "")' in app
    assert 'membershipLockDetails()) navigate("/access-locked", true)' in app
    assert "state.bootstrap || membershipLockDetails()" in app
    assert "Обратитесь к руководителю вашей команды." in app
    locked_gate = app.index("if (membershipLockDetails())")
    learning_gate = app.index("if (!hasWorkspaceAccess())")
    assert locked_gate < learning_gate

    locked_screen = app[
        app.index("function renderMembershipLocked()") : app.index("function renderLearningHome()")
    ]
    assert "escapeHtml(details.message)" in locked_screen
    assert 'data-action="logout"' in locked_screen
    assert 'data-action="retry-bootstrap"' not in locked_screen
    assert "renderLearningHome(" not in locked_screen
    assert "renderWorkspace(" not in locked_screen


def test_browser_uses_narrow_scoped_rpc_contract_and_stable_idempotency() -> None:
    adapter = _text("supabase-api.js")
    expected = (
        "creator_bootstrap",
        "creator_complete_module",
        "creator_submit_course_check",
        "creator_submit_exam",
        "creator_workspace_section",
        "creator_create_mock_batch",
        "creator_confirm_placement",
        "creator_record_metric",
        "creator_set_wb_alias",
        "creator_decide_payout",
        "creator_transition_task",
        "creator_create_feedback",
        "creator_register_media",
        "creator_capture_event",
    )
    for function_name in expected:
        assert f'"{function_name}"' in adapter
    assert "p_payload: payload" in adapter
    assert "organization_id: this.organizationId" in adapter
    assert "idempotency_key: idempotencyKey" in adapter
    assert "sessionStorage" in adapter
    assert "crypto.randomUUID()" in adapter
    assert ".rpc(functionName" in adapter
    assert ".supabase.from(" not in adapter


def test_spa_payload_and_workspace_fields_match_the_creator_rpc_migration() -> None:
    app = _text("app.js")
    adapter = _text("supabase-api.js")
    sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    )
    rpc_names = [
        name
        for name in re.findall(r'"(creator_[a-z0-9_]+)"', adapter)
        if name != "creator_api_error"
    ]
    assert len(set(rpc_names)) == 37
    assert "creator_operational_health" in rpc_names
    for function_name in set(rpc_names):
        assert re.search(
            rf"function\s+public\.{re.escape(function_name)}\s*"
            rf"\(\s*p_payload\s+jsonb",
            sql,
            flags=re.IGNORECASE,
        )

    for field in (
        "platform",
        "destination_ref",
        "assignee_id",
        "payout_minor",
        "media_ids",
        "placement_id",
        "current_article",
        "alias_article",
        "external_payment_reference",
        "object_key",
        "rights_confirmed",
    ):
        assert field in app or field in adapter
        assert f"'{field}'" in sql

    for field in (
        "courses_completed",
        "courses_required",
        "exam_passed",
        "tasks_done",
        "tasks_total",
        "published_count",
    ):
        assert f"'{field}'" in sql
        assert field in app


def test_generation_keeps_mock_safe_and_requires_explicit_paid_runway_confirmation() -> None:
    adapter = _text("supabase-api.js")
    app = _text("app.js")
    assert 'mode: "mock"' in adapter
    assert "allow_real_spend: false" in adapter
    assert 'spend_confirmation: "MOCK_ONLY"' in adapter
    assert "MOCK_GENERATION_ENABLED" in app
    assert "REAL_GENERATION_ENABLED" in app
    assert "MAX_BATCH_SIZE" in app
    assert "Math.min(50" in app
    assert "count > 50" in adapter
    assert 'name="platform"' in app
    assert 'name="destination_ref"' in app
    assert 'name="assignee_id"' in app
    assert 'name="payout_rub"' in app
    assert "payout_minor" in app
    assert "exactMedia" in app
    assert "exact_product_media_required" in adapter
    assert "state.sections.placement.status" in app
    assert "state.sections.tasks.status" in app
    assert "Тестовые варианты · без списаний" in app
    assert "Создано ${count} тестовых вариантов без списаний" in app
    assert "Реальная ИИ-генерация выключена: provider=mock" not in app

    assert 'REAL_GENERATION_FUNCTION = "creator-generate"' in adapter
    assert 'this.invokeRealGeneration("start"' in adapter
    assert 'this.invokeRealGeneration("status"' in adapter
    assert ".functions.invoke(REAL_GENERATION_FUNCTION" in adapter
    assert "this.supabase.auth.getSession()" in adapter
    assert 'headers: { Authorization: `Bearer ${accessToken}` }' in adapter
    assert 'mode: "real"' in adapter
    assert 'provider: "runway"' in adapter
    assert 'gen4_turbo: Object.freeze' in adapter
    assert 'seedance2_fast: Object.freeze' in adapter
    assert "duration_seconds: 5" in adapter
    assert "duration_seconds: 8" in adapter
    assert "audio: true" in adapter
    assert "allow_real_spend: true" in adapter
    assert 'confirmation: "RUNWAY_GEN4_TURBO_5S_USD_0.25"' in adapter
    assert 'confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32"' in adapter
    assert "batch?.spend_confirmation !== sku.confirmation" in adapter
    assert "media_ids.length !== 1" in adapter
    assert "edge:${REAL_GENERATION_FUNCTION}" in adapter

    assert 'name="generation_mode"' in app
    assert "Анимация товара · 5 секунд · без голоса · ≈ $0.25" in app
    assert "Блогер + голос · 8 секунд · ≈ $2.32" in app
    assert 'name="real_spend_confirmation"' in app
    assert "values.get(\"real_spend_confirmation\") !== generationSku.confirmation" in app
    assert "Number(values.get(\"count\")) !== 1" in app
    assert "mediaIds.length !== 1" in app
    assert "state.api.startRealGeneration(payload)" in app
    assert 'data-action="check-real-generation"' in app
    assert "parameters.job_id" in app
    assert "state.api.realGenerationStatus" in app
    assert "isTrustedGenerationDownload" in app
    assert 'link.rel = "noopener noreferrer"' in app
    assert 'item.task_type === "video_review"' in app
    assert 'result.provider === "runway"' in app
    assert 'String(result.generation_status || "")' in app


def test_login_and_reset_capture_values_before_disabling_form_controls() -> None:
    app = _text("app.js")
    login_start = app.index("async function submitLogin(form)")
    login_end = app.index("async function submitReset(form)", login_start)
    login = app[login_start:login_end]
    assert login.index("new FormData(form)") < login.index("setFormBusy(form, true")

    reset_start = login_end
    reset_end = app.index("async function submitPassword(form)", reset_start)
    reset = app[reset_start:reset_end]
    assert reset.index("new FormData(form)") < reset.index("setFormBusy(form, true")

    feedback_start = app.index("async function submitFeedback(form)")
    feedback_end = app.index("async function submitTeamInvites(form)", feedback_start)
    feedback = app[feedback_start:feedback_end]
    assert feedback.index("new FormData(form)") < feedback.index("setFormBusy(form, true")


def test_password_reset_has_a_bounded_wait_and_always_unlocks_the_form() -> None:
    app = _text("app.js")
    index = _text("index.html")
    reset_start = app.index("async function submitReset(form)")
    reset_end = app.index("async function submitPassword(form)", reset_start)
    reset = app[reset_start:reset_end]

    assert "AUTH_REQUEST_TIMEOUT_MS = 15_000" in app
    assert "await withUiTimeout(" in reset
    assert "Сервер восстановления не ответил за 15 секунд" in reset
    assert "finally" in reset
    assert "if (form.isConnected) setFormBusy(form, false)" in reset
    assert "Promise.race([operation, timeout])" in app
    assert './app.js?v=20260717.3' in index


def test_novice_workspace_has_required_tabs_and_last_mile_forms() -> None:
    catalog = _text("catalog.js")
    app = _text("app.js")
    for label in (
        "Материалы",
        "Создание видео",
        "Публикации",
        "Результаты",
        "Выплаты",
        "Задачи",
        "Помощь и идеи",
        "Команда",
    ):
        assert label in catalog
    for form in (
        'id="manual-metric-form"',
        'id="wb-alias-form"',
        'class="payout-reject-form"',
        'class="payout-paid-form',
    ):
        assert form in app
    assert 'source: "manual"' in _text("supabase-api.js")
    assert "revenue_minor" in app
    assert 'value="social_data"' in app
    assert 'value="wb_aliases"' in app
    assert 'name="description"' in app
    assert 'decision: "paid"' in app
    assert "external_payment_reference" in app


def test_team_invites_are_owner_admin_only_and_use_the_edge_function() -> None:
    app = _text("app.js")
    catalog = _text("catalog.js")
    assert '["team", "Команда", "◎"]' in catalog
    assert '["owner", "admin"].includes' in app
    assert 'key !== "team" || canManageTeam()' in app
    assert 'id="team-invite-form"' in app
    assert 'split(/\\r?\\n/)' in app
    assert "emails.length > 50" in app
    assert 'functions.invoke("creator-invite"' in app
    assert "body: { emails }" in app
    for status in ("invited", "already_exists", "rate_limited", "smtp_required"):
        assert status in app
    assert "Каждый новый участник входит как trainee" in app
    assert "team_invites_completed" in app
    for field in (
        "courses_completed",
        "courses_required",
        "exam_passed",
        "tasks_done",
        "tasks_total",
        "published_count",
    ):
        assert field in app
    assert 'data-section="team"' in app


def test_private_upload_key_matches_supabase_rls_prefix() -> None:
    app = _text("app.js")
    adapter = _text("supabase-api.js")
    assert 'prefix !== `${org}/${user}/`' in app
    assert 'bucket !== "contentengine-private"' in app
    assert '`${prefix}uploads/${month}/${crypto.randomUUID()}-${safeName}`' in app
    assert "organizations/${org}" not in app
    assert "uploadPrivateObject" in adapter
    assert "signedPrivateObjectUrls" in adapter
    assert "createSignedUrls" in adapter
    assert "assertPrivateObjectKey" in adapter


def test_csp_blocks_inline_scripts_and_fatal_action_uses_delegation() -> None:
    index = _text("index.html")
    app = _text("app.js")
    assert "script-src 'self' https://cdn.jsdelivr.net" in index
    assert "script-src 'self' 'unsafe-inline'" not in index
    assert "onclick=" not in index
    assert "onclick=" not in app
    assert 'data-action="reload-page"' in app
