import hashlib
import json
from pathlib import Path
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
        "boot-watchdog.js",
        "generation-spend-view.js",
    }
    assert expected <= {path.name for path in APP.iterdir() if path.is_file()}

    bundle = "\n".join(_text(name) for name in expected)
    assert "http://localhost" not in bundle
    assert "http://127.0.0.1" not in bundle
    assert "render.com" not in bundle.casefold()
    assert (
        'const SUPABASE_SDK_URL = "./vendor/supabase-js-2.57.4.js?'
        'v=20260826.rebuild-clean.35";'
    ) in bundle
    assert "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm" not in bundle
    assert "@supabase/supabase-js@latest" not in bundle
    assert 'import { createClient } from "https://cdn.jsdelivr.net' not in _text("app.js")
    assert "import(SUPABASE_SDK_URL)" in _text("app.js")
    assert '<script src="./boot-watchdog.js?' in _text("index.html")


def test_supabase_browser_runtime_is_same_origin_versioned_and_integrity_pinned() -> None:
    vendor = APP / "vendor"
    umd = vendor / "supabase-js-2.57.4.umd.js"
    adapter = vendor / "supabase-js-2.57.4.js"
    license_file = vendor / "supabase-js-2.57.4.LICENSE.txt"
    notice = json.loads(
        (vendor / "supabase-js-2.57.4.NOTICE.json").read_text(encoding="utf-8")
    )

    assert umd.is_file()
    assert adapter.is_file()
    assert license_file.is_file()
    assert notice["package"] == "@supabase/supabase-js"
    assert notice["version"] == "2.57.4"
    assert notice["license"] == "MIT"
    assert notice["npm_tarball_integrity"] == (
        "sha512-LcbTzFhHYdwfQ7TRPfol0z04rLEyHabpGYANME6wkQ/kLtKNmI+Vy+WEM8HxeOZAtByUFxoUTTLwhXmrh+CcVw=="
    )
    assert hashlib.sha256(umd.read_bytes()).hexdigest() == (
        notice["vendored_file_sha256"]
    )
    assert hashlib.sha256(license_file.read_bytes()).hexdigest() == (
        notice["license_file_sha256"]
    )
    adapter_source = adapter.read_text(encoding="utf-8")
    assert 'import "./supabase-js-2.57.4.umd.js";' in adapter_source
    assert "export const createClient" in adapter_source
    assert "export const processLock" in adapter_source
    for runtime_name in ("app.js", "workspace-os-v4-context-trash.js"):
        runtime = _text(runtime_name)
        assert (
            'const SUPABASE_SDK_URL = "./vendor/supabase-js-2.57.4.js?'
            'v=20260826.rebuild-clean.35";'
        ) in runtime
        assert "cdn.jsdelivr.net/npm/@supabase/supabase-js" not in runtime
        assert "lock: processLock" in runtime


def test_process_lock_bypasses_cross_tab_navigator_lock_and_serializes_clients(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable vendored-runtime checks")

    source = APP / "vendor"
    runtime = tmp_path / "vendor"
    runtime.mkdir()
    for name in (
        "supabase-js-2.57.4.js",
        "supabase-js-2.57.4.umd.js",
    ):
        shutil.copy2(source / name, runtime / name)
    (runtime / "package.json").write_text(
        '{"type":"module"}\n',
        encoding="utf-8",
    )

    adapter_url = (runtime / "supabase-js-2.57.4.js").as_uri()
    script = f"""
globalThis.self = globalThis;
globalThis.window = globalThis;
globalThis.document = {{
  visibilityState: "visible",
  addEventListener() {{}},
  removeEventListener() {{}},
}};
Object.defineProperty(globalThis, "BroadcastChannel", {{
  value: undefined,
  configurable: true,
}});
let navigatorLockCalls = 0;
Object.defineProperty(globalThis, "navigator", {{
  value: {{
    locks: {{
      request() {{
        navigatorLockCalls += 1;
        return new Promise(() => {{}});
      }},
    }},
  }},
  configurable: true,
}});
const sdk = await import({json.dumps(adapter_url)});
if (typeof sdk.createClient !== "function") throw new Error("createClient missing");
if (typeof sdk.processLock !== "function") throw new Error("processLock missing");

const memoryStorage = () => {{
  const values = new Map();
  return {{
    getItem(key) {{ return values.has(key) ? values.get(key) : null; }},
    setItem(key, value) {{ values.set(key, String(value)); }},
    removeItem(key) {{ values.delete(key); }},
  }};
}};
const baseAuth = (storageKey, storage, lock) => ({{
  persistSession: true,
  autoRefreshToken: false,
  detectSessionInUrl: false,
  flowType: "pkce",
  storageKey,
  storage,
  ...(lock ? {{ lock }} : {{}}),
}});

// Reproduce a lock held by another same-origin tab: the SDK's browser default
// invokes Navigator LockManager and getSession cannot complete.
const defaultClient = sdk.createClient(
  "https://example.supabase.co",
  "sb_publishable_offline_runtime_contract_1234567890",
  {{ auth: baseAuth("default-browser-lock", memoryStorage(), null) }},
);
const defaultOutcome = await Promise.race([
  defaultClient.auth.getSession().then(() => "resolved"),
  new Promise((resolve) => setTimeout(() => resolve("blocked"), 50)),
]);
if (defaultOutcome !== "blocked" || navigatorLockCalls !== 1) {{
  throw new Error("Navigator Lock contention was not reproduced");
}}

// The explicit official processLock is scoped to this JavaScript realm. Two
// clients in the same tab still serialize, while the held Navigator Lock from
// another tab is never consulted.
const sharedStorage = memoryStorage();
const processClients = [0, 1].map(() => sdk.createClient(
  "https://example.supabase.co",
  "sb_publishable_offline_runtime_contract_1234567890",
  {{ auth: baseAuth("contentengine-tab-session", sharedStorage, sdk.processLock) }},
));
const sessions = await Promise.race([
  Promise.all(processClients.map((client) => client.auth.getSession())),
  new Promise((_, reject) => setTimeout(
    () => reject(new Error("processLock clients timed out")),
    1_000,
  )),
]);
if (
  sessions.some((result) => result.error || result.data.session !== null)
  || navigatorLockCalls !== 1
) {{
  throw new Error("processLock did not isolate the tab from Navigator LockManager");
}}
process.stdout.write(JSON.stringify({{
  defaultOutcome,
  navigatorLockCalls,
  processSessions: sessions.map((result) => result.data.session),
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout) == {
        "defaultOutcome": "blocked",
        "navigatorLockCalls": 1,
        "processSessions": [None, None],
    }


def test_hybrid_auth_storage_restores_password_session_after_reconstruction(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable auth reload checks")

    source = APP / "vendor"
    runtime = tmp_path / "vendor"
    runtime.mkdir()
    for name in (
        "supabase-js-2.57.4.js",
        "supabase-js-2.57.4.umd.js",
    ):
        shutil.copy2(source / name, runtime / name)
    (runtime / "package.json").write_text(
        '{"type":"module"}\n',
        encoding="utf-8",
    )

    app = _text("app.js")
    storage_helpers = app[
        app.index("function createHybridAuthStorage()") :
        app.index("function normalizeWorkspaceAccessRequestResult(")
    ]
    adapter_url = (runtime / "supabase-js-2.57.4.js").as_uri()
    script = f"""
globalThis.self = globalThis;
globalThis.window = globalThis;
globalThis.document = {{
  visibilityState: "visible",
  addEventListener() {{}},
  removeEventListener() {{}},
}};
Object.defineProperty(globalThis, "BroadcastChannel", {{
  value: undefined,
  configurable: true,
}});
Object.defineProperty(globalThis, "navigator", {{
  value: {{}},
  configurable: true,
}});

const memoryStorage = () => {{
  const values = new Map();
  return {{
    get length() {{ return values.size; }},
    key(index) {{ return [...values.keys()][index] ?? null; }},
    getItem(key) {{ return values.has(key) ? values.get(key) : null; }},
    setItem(key, value) {{ values.set(key, String(value)); }},
    removeItem(key) {{ values.delete(key); }},
  }};
}};
window.localStorage = memoryStorage();
window.sessionStorage = memoryStorage();

{storage_helpers}

const sdk = await import({json.dumps(adapter_url)});
const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
const user = {{
  id: "11111111-1111-4111-8111-111111111111",
  aud: "authenticated",
  role: "authenticated",
  email: "operator@example.com",
  user_metadata: {{}},
}};
const accessToken = [
  encode({{ alg: "HS256", typ: "JWT" }}),
  encode({{
    sub: user.id,
    aud: "authenticated",
    role: "authenticated",
    exp: Math.floor(Date.now() / 1_000) + 3_600,
  }}),
  "signature",
].join(".");
const mockFetch = async (input) => {{
  const url = String(input);
  if (!url.includes("/auth/v1/token?grant_type=password")) {{
    throw new Error(`unexpected auth request: ${{url}}`);
  }}
  return new Response(JSON.stringify({{
    access_token: accessToken,
    refresh_token: "refresh-token",
    expires_in: 3_600,
    token_type: "bearer",
    user,
  }}), {{
    status: 200,
    headers: {{ "content-type": "application/json" }},
  }});
}};
const storageKey = "contentengine.creator-workspace.example.supabase.co.auth-session.v1";
const options = () => ({{
  auth: {{
    persistSession: true,
    autoRefreshToken: false,
    detectSessionInUrl: false,
    flowType: "pkce",
    lock: sdk.processLock,
    storage: createHybridAuthStorage(),
    storageKey,
  }},
  global: {{ fetch: mockFetch }},
}});

const firstClient = sdk.createClient(
  "https://example.supabase.co",
  "sb_publishable_reload_contract_1234567890",
  options(),
);
const signedIn = await firstClient.auth.signInWithPassword({{
  email: "operator@example.com",
  password: "correct-password",
}});
if (signedIn.error || signedIn.data.user?.id !== user.id) {{
  throw signedIn.error || new Error("mock password login failed");
}}
const storedBeforeReconstruction = Boolean(window.sessionStorage.getItem(storageKey));

// A new client with a new hybrid adapter models a same-origin page reload.
const reconstructedClient = sdk.createClient(
  "https://example.supabase.co",
  "sb_publishable_reload_contract_1234567890",
  options(),
);
const restored = await reconstructedClient.auth.getSession();
if (restored.error || restored.data.session?.user?.id !== user.id) {{
  throw restored.error || new Error("session was not restored after reconstruction");
}}
process.stdout.write(JSON.stringify({{
  storedBeforeReconstruction,
  restoredUserId: restored.data.session.user.id,
  localSessionValue: window.localStorage.getItem(storageKey),
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout) == {
        "storedBeforeReconstruction": True,
        "restoredUserId": "11111111-1111-4111-8111-111111111111",
        "localSessionValue": None,
    }


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
        "updateUser",
    ):
        assert method in app
    assert "signUp(" not in app
    assert "resetPasswordForEmail" not in app
    assert "requestPublicPasswordRecovery" in app
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
        [node, "-"],
        input=script,
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
    assert 'if (membershipLockDetails()) return "/access-locked";' in app
    assert 'navigate(authenticatedStartPath(), true);' in app
    assert "state.bootstrap || membershipLockDetails()" in app
    assert "Обратитесь к руководителю вашей команды." in app
    locked_gate = app.index("if (membershipLockDetails())")
    learning_gate = app.index("if (!hasWorkspaceAccess())")
    assert locked_gate < learning_gate

    locked_screen = app[
        app.index("function renderMembershipLocked()") : app.index("function clearAcademyBootstrapLoading(")
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
        "creator_create_generation_campaign",
        "creator_update_generation_campaign_spend_policy",
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
    rpc_start = adapter.index("export const RPC = Object.freeze({")
    rpc_end = adapter.index("});", rpc_start) + len("});")
    rpc_contract = adapter[rpc_start:rpc_end]
    rpc_names = [
        name
        for name in re.findall(r'"(creator_[a-z0-9_]+)"', rpc_contract)
        if name != "creator_api_error"
    ]
    # 108 = 107 + creator_admin_account_ownership (202608230024, поля владения
    # аккаунтом компании из админки «Люди → Аккаунты»).
    # 110 = 108 + контур «Одобрить и разместить» (202608240001):
    # creator_publishing_accounts + creator_publish_generation_result.
    # 112 = 110 + очередь проверки и витрина аккаунтов (202608240003):
    # creator_reject_generation_result + creator_team_accounts.
    # 113 = 112 + creator_results_funnel (202608240004): воронка «Результатов».
    # 115 = 113 + «Паспорт ролика» (202608260003): реестр паспортов проекта и
    # полный срез одного ролика — обе read-only.
    # 120 = 115 + папка «Гипотезы» (202608260010): список, срез, сохранение,
    # утверждение версии и человеческое решение.
    assert len(set(rpc_names)) == 120
    assert "creator_admin_snapshot" in rpc_names
    assert "creator_admin_mutate" in rpc_names
    assert "creator_admin_account_ownership" in rpc_names
    assert "creator_publishing_accounts" in rpc_names
    assert "creator_publish_generation_result" in rpc_names
    assert "creator_reject_generation_result" in rpc_names
    assert "creator_team_accounts" in rpc_names
    assert "creator_results_funnel" in rpc_names
    assert "creator_content_passport_registry" in rpc_names
    assert "creator_content_result_passport" in rpc_names
    assert "creator_content_hypotheses" in rpc_names
    assert "creator_save_content_hypothesis" in rpc_names
    assert "creator_decide_content_hypothesis" in rpc_names
    assert "creator_operational_health" in rpc_names
    assert "creator_generation_learning_policy" in rpc_names
    assert "creator_generation_repair_policy" in rpc_names
    assert "creator_generation_archive" in rpc_names
    assert "creator_generation_strategy_repeat_data" in rpc_names
    assert "creator_generation_strategy_asset_candidates" in rpc_names
    assert "creator_create_generation_campaign" in rpc_names
    assert "creator_update_generation_campaign_spend_policy" in rpc_names
    assert "creator_prepare_content_review_evidence" in rpc_names
    assert "creator_commit_content_review_evidence" in rpc_names
    assert "creator_recover_content_review_sound_assessment" in rpc_names
    assert "creator_ai_learning_control_room" in rpc_names
    assert "creator_register_ai_knowledge_source" in rpc_names
    assert "creator_decide_ai_teaching_card" in rpc_names
    assert "creator_decide_ai_historical_case" in rpc_names
    assert "creator_project_members" in rpc_names
    assert "creator_grant_project_member" in rpc_names
    assert "creator_revoke_project_member" in rpc_names
    assert "creator_notification_center" in rpc_names
    assert "creator_validate_notification_action" in rpc_names
    assert "creator_mark_visible_notifications_read" in rpc_names
    for function_name in (
        "creator_project_flow",
        "creator_create_workspace_project",
        "creator_archive_workspace_project",
        "creator_start_project_research",
        "creator_project_research_status",
        "creator_save_project_creative_brief_draft",
        "creator_approve_project_creative_brief",
    ):
        assert function_name in rpc_names
    for revoked_legacy_alias in (
        "creator_start_product_research",
        "creator_product_research_status",
        "creator_save_creative_brief_draft",
        "creator_approve_creative_brief",
    ):
        assert revoked_legacy_alias not in rpc_names
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
    assert "Dry-run задач · без файлов и списаний" in app
    assert "Создано ${count} dry-run задач без списаний" in app
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
    assert "min_duration_seconds: 2" in adapter
    assert "max_duration_seconds: 10" in adapter
    assert "credits_per_second: 5" in adapter
    assert "min_duration_seconds: 4" in adapter
    assert "max_duration_seconds: 15" in adapter
    assert "credits_per_second: 29" in adapter
    assert "audio: true" in adapter
    assert "allow_real_spend: true" in adapter
    assert "`RUNWAY_GEN4_TURBO_${duration}S_USD_${estimatedUsd}`" in adapter
    assert "`RUNWAY_SEEDANCE2_FAST_${duration}S_AUDIO_USD_${estimatedUsd}`" in adapter
    assert 'String(batch?.spend_confirmation || "")' in adapter
    assert '!isUuid(String(batch?.provider_readiness_receipt_id || ""))' in adapter
    assert "PROVIDER_READINESS_SHA256_PATTERN.test(" in adapter
    assert "batch.media_ids.length > 5" in adapter
    assert "new Set(batch.media_ids.map(String)).size" in adapter
    assert "edge:${REAL_GENERATION_FUNCTION}" in adapter

    assert 'name="generation_mode"' in app
    assert "Анимация товара · 5 секунд · без голоса · ≈ $0.25" in app
    assert "Блогер + голос · 8 секунд · ≈ $2.32" in app
    assert 'name="real_spend_confirmation"' in app
    assert "values.get(\"real_spend_confirmation\") !== generationSku.confirmation" in app
    assert "Number(values.get(\"count\")) !== 1" in app
    assert "mediaIds.length < 1" in app
    assert "mediaIds.length > MAX_REAL_GENERATION_REFERENCES" in app
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
    assert "Сервер восстановления пока не подтвердил результат" in reset
    assert "finally" in reset
    assert "if (form.isConnected) setFormBusy(form, false)" in reset
    assert "Promise.race([operation, timeout])" in app
    assert './app.js?v=20260826.rebuild-clean.35' in index


def test_novice_workspace_has_required_tabs_and_last_mile_forms() -> None:
    catalog = _text("catalog.js")
    app = _text("app.js")
    for label in (
        "Материалы",
        "Создание контента",
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
    assert "body: { emails, organization_id: requestOrganizationId }" in app
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
