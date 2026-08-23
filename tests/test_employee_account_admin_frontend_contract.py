import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "web" / "app" / "app.js"
API_PATH = ROOT / "web" / "app" / "supabase-api.js"
VIEW_PATH = ROOT / "web" / "app" / "admin-people-view.js"

APP = APP_PATH.read_text(encoding="utf-8")
API = API_PATH.read_text(encoding="utf-8")
VIEW = VIEW_PATH.read_text(encoding="utf-8")


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    return node


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _node(),
            "--experimental-vm-modules",
            "--input-type=module",
            "-e",
            script,
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_admin_browser_modules_parse_as_native_esm() -> None:
    paths = [APP_PATH, API_PATH, VIEW_PATH]
    script = f"""
      import fs from 'node:fs';
      import vm from 'node:vm';
      for (const path of {json.dumps([str(path) for path in paths])}) {{
        const source = fs.readFileSync(path, 'utf8');
        new vm.SourceTextModule(source, {{ identifier: path }});
      }}
      console.log('employee-admin-esm-parse: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-esm-parse: PASS" in result.stdout


def test_admin_route_precedes_academy_and_workspace_gates_for_owner_and_admin() -> None:
    render = _between(APP, "function render() {", "function renderLogin(")
    compatible = _between(
        APP,
        "function authenticatedRouteCompatible(",
        "async function refreshBootstrapAccessState(",
    )
    is_admin_route = _between(
        APP,
        "function isAdminRoute(",
        "function canManageTeam(",
    )
    can_manage = _between(
        APP,
        "function canManageTeam() {",
        "function canManageGenerationSpendPolicy(",
    )

    assert render.index("if (isAdminRoute(path))") < render.index(
        "if (academyRequired())"
    )
    assert render.index("if (isAdminRoute(path))") < render.index(
        "if (!hasWorkspaceAccess())"
    )
    assert "training" not in can_manage.casefold()
    assert "workspace" not in can_manage.casefold()

    harness = f"""
      const ADMIN_PEOPLE_PATH = '/admin/people';
      const WORKSPACE_START_PATH = '/workspace/home';
      const state = {{
        authLinkError: null,
        session: {{ user: {{ id: 'actor' }} }},
        forcePassword: false,
        bootstrapStatus: 'ready',
        bootstrap: null,
        route: {{ path: ADMIN_PEOPLE_PATH }},
      }};
      let calls = [];
      let gateCalls = 0;
      function closeTrainingAchievement() {{}}
      function stopAllTrainingWalkthroughs() {{}}
      function destroyAccountVisualController() {{}}
      function renderAuthLinkError() {{ calls.push('auth-link-error'); }}
      function renderResetRequest() {{ calls.push('reset-request'); }}
      function renderLogin() {{ calls.push('login'); }}
      function renderSetPassword() {{ calls.push('set-password'); }}
      function renderBootstrapLoading() {{ calls.push('bootstrap-loading'); }}
      function renderBootstrapError() {{ calls.push('bootstrap-error'); }}
      function membershipLockDetails() {{ return null; }}
      function renderMembershipLocked() {{ calls.push('membership-locked'); }}
      function navigate(path) {{ calls.push(`navigate:${{path}}`); }}
      function renderAdminForbidden() {{ calls.push('admin-forbidden'); }}
      function renderAdminPeople() {{ calls.push('admin-people'); }}
      function academyRequired() {{
        gateCalls += 1;
        throw new Error('academy gate was reached before the admin route');
      }}
      function hasWorkspaceAccess() {{
        gateCalls += 1;
        throw new Error('workspace gate was reached before the admin route');
      }}
      {is_admin_route}
      {can_manage}
      {compatible}
      {render}
      export function runScenario(role, path = ADMIN_PEOPLE_PATH) {{
        calls = [];
        gateCalls = 0;
        state.route.path = path;
        state.bootstrap = {{
          membership: {{ role }},
          accessState: 'learning',
          workspaceAccess: false,
          training: {{ completedModules: [], exam: {{ passed: false }} }},
        }};
        render();
        return {{ calls: [...calls], gateCalls }};
      }}
      export function routeCompatible(role) {{
        state.bootstrap = {{ membership: {{ role }} }};
        return authenticatedRouteCompatible(ADMIN_PEOPLE_PATH, '/learn');
      }}
    """
    script = f"""
      import assert from 'node:assert/strict';
      import vm from 'node:vm';
      const module = new vm.SourceTextModule({json.dumps(harness)}, {{
        identifier: 'employee-admin-route-harness.js',
      }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();
      const {{ runScenario, routeCompatible }} = module.namespace;

      for (const role of ['owner', 'admin']) {{
        assert.deepEqual(runScenario(role), {{
          calls: ['admin-people'],
          gateCalls: 0,
        }});
        assert.equal(routeCompatible(role), true);
      }}
      for (const role of ['producer', 'reviewer', 'operator', 'trainee', 'viewer']) {{
        assert.deepEqual(runScenario(role), {{
          calls: ['admin-forbidden'],
          gateCalls: 0,
        }});
        assert.equal(routeCompatible(role), false);
      }}
      assert.deepEqual(runScenario('owner', '/admin'), {{
        calls: ['navigate:/admin/people'],
        gateCalls: 0,
      }});
      console.log('employee-admin-route-execution: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-route-execution: PASS" in result.stdout


def test_admin_api_crud_validates_inputs_and_sends_only_narrow_rpc_payloads() -> None:
    script = f"""
      import assert from 'node:assert/strict';
      import {{ webcrypto }} from 'node:crypto';
      import fs from 'node:fs';
      import vm from 'node:vm';

      if (!globalThis.crypto) globalThis.crypto = webcrypto;
      const sessionValues = new Map();
      globalThis.window = {{
        sessionStorage: {{
          getItem(key) {{ return sessionValues.get(key) ?? null; }},
          setItem(key, value) {{ sessionValues.set(key, value); }},
        }},
      }};

      const source = fs.readFileSync({json.dumps(str(API_PATH))}, 'utf8');
      const module = new vm.SourceTextModule(source, {{ identifier: 'supabase-api.js' }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();
      const {{ CreatorApi, RPC }} = module.namespace;

      const calls = [];
      const supabase = {{
        schema(name) {{
          assert.equal(name, 'public');
          return {{
            async rpc(functionName, args) {{
              calls.push({{ functionName, args }});
              return {{ data: {{ ok: true }}, error: null }};
            }},
          }};
        }},
      }};
      const api = new CreatorApi(supabase, {{
        RPC_SCHEMA: 'public',
        STORAGE_BUCKET: 'contentengine-private',
      }});
      const organizationId = '11111111-1111-4111-8111-111111111111';
      const profileId = '22222222-2222-4222-8222-222222222222';
      const accountId = '33333333-3333-4333-8333-333333333333';
      const expectedAt = '2026-08-12T09:30:00.000Z';
      api.organizationId = organizationId;

      async function expectCode(label, expectedCode, operation) {{
        try {{
          await operation();
          assert.fail(`${{label}} did not reject`);
        }} catch (error) {{
          assert.equal(error.code, expectedCode, label);
        }}
      }}

      await expectCode('unknown member action', 'admin_member_action_invalid', () =>
        api.adminMemberAction('promote_member', {{ profileId, reason: 'documented reason' }}));
      await expectCode('member uuid', 'admin_member_profile_invalid', () =>
        api.adminMemberAction('suspend_member', {{ profileId: 'not-a-uuid', reason: 'documented reason' }}));
      await expectCode('member reason', 'admin_reason_invalid', () =>
        api.adminMemberAction('suspend_member', {{ profileId, reason: 'short' }}));
      await expectCode('platform', 'admin_account_platform_invalid', () =>
        api.createManagedAccount({{ platform: 'javascript:', label: 'Main' }}));
      await expectCode('label', 'admin_account_label_invalid', () =>
        api.createManagedAccount({{ platform: 'youtube', label: 'x' }}));
      await expectCode('handle controls', 'admin_account_handle_invalid', () =>
        api.createManagedAccount({{ platform: 'youtube', label: 'Main', handle: 'bad\\nhandle' }}));
      await expectCode('url scheme', 'admin_account_url_invalid', () =>
        api.createManagedAccount({{ platform: 'youtube', label: 'Main', url: 'javascript:alert(1)' }}));
      await expectCode('url basic auth', 'admin_account_url_invalid', () =>
        api.createManagedAccount({{
          platform: 'youtube',
          label: 'Main',
          url: 'https://publisher:super-secret@example.com/channel',
        }}));
      await expectCode('url username only', 'admin_account_url_invalid', () =>
        api.createManagedAccount({{
          platform: 'youtube',
          label: 'Main',
          url: 'http://publisher@example.com/channel',
        }}));
      await expectCode('notes length', 'admin_account_notes_invalid', () =>
        api.createManagedAccount({{ platform: 'youtube', label: 'Main', notes: 'x'.repeat(1001) }}));
      await expectCode('update version', 'admin_account_version_invalid', () =>
        api.updateManagedAccount(accountId, 'not-a-date', {{ platform: 'youtube', label: 'Main' }}));
      await expectCode('archive reason', 'admin_reason_invalid', () =>
        api.archiveManagedAccount(accountId, expectedAt, 'short'));
      await expectCode('assignment account uuid', 'admin_account_id_invalid', () =>
        api.assignManagedAccount('not-a-uuid', profileId));
      await expectCode('assignment profile uuid', 'admin_member_profile_invalid', () =>
        api.assignManagedAccount(accountId, 'not-a-uuid'));
      assert.equal(calls.length, 0, 'invalid client inputs must not reach RPC');

      await api.inviteAttempts();
      await api.adminSnapshot();
      for (const action of ['suspend_member', 'reactivate_member', 'revoke_member']) {{
        await api.adminMemberAction(action, {{
          profileId: profileId.toUpperCase(),
          reason: '  audited member change  ',
        }});
      }}
      await api.createManagedAccount({{
        platform: '  YouTube  ',
        label: '  Main channel  ',
        handle: '  @main  ',
        url: '  https://example.com/channel  ',
        notes: '  Public publishing profile  ',
        password: 'CREATE_SECRET_MUST_NOT_CROSS_RPC',
        access_token: 'CREATE_TOKEN_MUST_NOT_CROSS_RPC',
      }});
      await api.updateManagedAccount(accountId.toUpperCase(), expectedAt, {{
        platform: 'youtube',
        label: 'Updated channel',
        handle: '',
        url: '',
        notes: '',
        cookie: 'UPDATE_COOKIE_MUST_NOT_CROSS_RPC',
      }});
      await api.archiveManagedAccount(accountId, expectedAt, '  retired after audit  ');
      await api.assignManagedAccount(accountId.toUpperCase(), profileId.toUpperCase());
      await api.assignManagedAccount(accountId, '');

      assert.equal(RPC.inviteAttempts, 'creator_invite_delivery_attempts');
      assert.equal(RPC.adminSnapshot, 'creator_admin_snapshot');
      assert.equal(RPC.adminMutate, 'creator_admin_mutate');
      assert.deepEqual(calls[0], {{
        functionName: 'creator_invite_delivery_attempts',
        args: {{ p_payload: {{ organization_id: organizationId }} }},
      }});
      assert.deepEqual(calls[1], {{
        functionName: 'creator_admin_snapshot',
        args: {{ p_payload: {{ organization_id: organizationId }} }},
      }});

      const mutations = calls.slice(2);
      assert.deepEqual(
        mutations.map((call) => call.args.p_payload.action),
        [
          'suspend_member',
          'reactivate_member',
          'revoke_member',
          'create_account',
          'update_account',
          'archive_account',
          'bind_account',
          'unbind_account',
        ],
      );
      for (const call of mutations) {{
        assert.equal(call.functionName, 'creator_admin_mutate');
        assert.equal(call.args.p_payload.organization_id, organizationId);
        assert.match(call.args.p_payload.idempotency_key, /^[0-9a-f-]{{36}}$/u);
      }}

      const revoke = mutations.find((call) => call.args.p_payload.action === 'revoke_member')
        .args.p_payload;
      assert.equal(revoke.confirmation, 'REVOKE_MEMBER');
      assert.equal(revoke.reason, 'audited member change');

      const created = mutations.find((call) => call.args.p_payload.action === 'create_account')
        .args.p_payload;
      assert.deepEqual(
        {{
          platform: created.platform,
          label: created.label,
          handle: created.handle,
          url: created.url,
          notes: created.notes,
        }},
        {{
          platform: 'youtube',
          label: 'Main channel',
          handle: '@main',
          url: 'https://example.com/channel',
          notes: 'Public publishing profile',
        }},
      );
      for (const forbidden of ['password', 'access_token', 'refresh_token', 'cookie']) {{
        assert.equal(Object.hasOwn(created, forbidden), false);
      }}

      const updated = mutations.find((call) => call.args.p_payload.action === 'update_account')
        .args.p_payload;
      assert.equal(updated.account_id, accountId);
      assert.equal(updated.expected_updated_at, expectedAt);
      assert.equal(updated.handle, null);
      assert.equal(updated.url, null);
      assert.equal(updated.notes, null);
      assert.equal(Object.hasOwn(updated, 'cookie'), false);

      const archived = mutations.find((call) => call.args.p_payload.action === 'archive_account')
        .args.p_payload;
      assert.equal(archived.confirmation, 'ARCHIVE_ACCOUNT');
      assert.equal(archived.reason, 'retired after audit');

      const bound = mutations.find((call) => call.args.p_payload.action === 'bind_account')
        .args.p_payload;
      assert.equal(bound.account_id, accountId);
      assert.equal(bound.target_profile_id, profileId);
      const unbound = mutations.find((call) => call.args.p_payload.action === 'unbind_account')
        .args.p_payload;
      assert.equal(Object.hasOwn(unbound, 'target_profile_id'), false);
      console.log('employee-admin-api-execution: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-api-execution: PASS" in result.stdout


def test_admin_invite_is_org_scoped_and_late_results_cannot_cross_sessions() -> None:
    submit_invites = _between(
        APP,
        "async function submitTeamInvites(form) {",
        "async function submitManagerAccess(",
    )
    harness = f"""
      const ORG_A = '11111111-1111-4111-8111-111111111111';
      const ORG_B = '22222222-2222-4222-8222-222222222222';
      const INVITE_REQUEST_TIMEOUT_MS = 25_000;
      const invokeCalls = [];
      const persisted = [];
      const toasts = [];
      const renders = [];
      const tracks = [];
      const loads = [];
      const busyChanges = [];
      let resolveInvoke = null;

      class FormData {{
        constructor(form) {{ this.form = form; }}
        get(name) {{ return this.form.fields?.[name] ?? null; }}
      }}
      function createSupabase(label) {{
        return {{
          label,
          functions: {{
            invoke(name, options) {{
              invokeCalls.push({{ label, name, options }});
              return new Promise((resolve) => {{ resolveInvoke = resolve; }});
            }},
          }},
        }};
      }}
      const state = {{
        dataEpoch: 7,
        user: {{ id: 'user-a' }},
        api: {{ organizationId: ORG_A }},
        supabase: createSupabase('session-a'),
        teamInviteResult: null,
        sections: {{ team: {{ status: 'ready' }} }},
        adminPeople: {{ notice: '' }},
      }};
      function canManageTeam() {{ return true; }}
      function toast(message, kind) {{ toasts.push({{ message, kind }}); }}
      function setFormBusy(form, busy, label) {{
        busyChanges.push({{ form: form.id, busy, label }});
      }}
      function withUiTimeout(promise) {{ return promise; }}
      async function normalizeInviteFunctionError(error) {{ return error; }}
      function persistTeamInviteResult(result) {{ persisted.push(result); }}
      async function loadAdminPeople(options) {{ loads.push(options); }}
      async function track(name, details) {{ tracks.push({{ name, details }}); }}
      function isAdminRoute() {{ return true; }}
      function render() {{ renders.push('render'); }}
      function actionErrorMessage(error) {{ return String(error?.message || error); }}

      {submit_invites}

      function formFor(emails) {{
        return {{
          id: 'admin-invite-form',
          fields: {{ emails }},
          dataset: {{ dirty: '1' }},
        }};
      }}
      function accepted(email) {{
        return {{
          ok: true,
          requested: 1,
          invited: 1,
          already_exists: 0,
          failed: 0,
          results: [{{ email, status: 'invited' }}],
        }};
      }}
      function clearLogs() {{
        invokeCalls.length = 0;
        persisted.length = 0;
        toasts.length = 0;
        renders.length = 0;
        tracks.length = 0;
        loads.length = 0;
        busyChanges.length = 0;
      }}

      export async function runCurrentSession() {{
        clearLogs();
        state.dataEpoch = 7;
        state.user = {{ id: 'user-a' }};
        state.api = {{ organizationId: ORG_A }};
        state.supabase = createSupabase('session-a');
        state.teamInviteResult = null;
        state.adminPeople = {{ notice: '' }};
        const form = formFor('  Employee@Example.test  \\nemployee@example.test');
        const pending = submitTeamInvites(form);
        const call = invokeCalls[0];
        resolveInvoke({{ data: accepted('employee@example.test'), error: null }});
        await pending;
        return {{
          call,
          persisted: [...persisted],
          toasts: [...toasts],
          renders: [...renders],
          tracks: [...tracks],
          loads: [...loads],
          result: state.teamInviteResult,
          dirty: form.dataset.dirty,
        }};
      }}

      export async function runStaleSession() {{
        clearLogs();
        state.dataEpoch = 20;
        state.user = {{ id: 'user-a' }};
        state.api = {{ organizationId: ORG_A }};
        state.supabase = createSupabase('old-session');
        state.teamInviteResult = {{ marker: 'old-placeholder' }};
        state.adminPeople = {{ notice: 'new-session-notice' }};
        const form = formFor('private-a@example.test');
        const pending = submitTeamInvites(form);
        const call = invokeCalls[0];

        state.dataEpoch = 21;
        state.user = {{ id: 'user-b' }};
        state.api = {{ organizationId: ORG_B }};
        state.supabase = createSupabase('new-session');
        state.teamInviteResult = {{ marker: 'new-session-result' }};
        state.adminPeople = {{ notice: 'new-session-notice' }};
        resolveInvoke({{ data: accepted('private-a@example.test'), error: null }});
        await pending;
        return {{
          call,
          persisted: [...persisted],
          toasts: [...toasts],
          renders: [...renders],
          tracks: [...tracks],
          loads: [...loads],
          result: state.teamInviteResult,
          notice: state.adminPeople.notice,
          dirty: form.dataset.dirty,
        }};
      }}
    """
    script = f"""
      import assert from 'node:assert/strict';
      import vm from 'node:vm';
      const module = new vm.SourceTextModule({json.dumps(harness)}, {{
        identifier: 'employee-admin-invite-race-harness.js',
      }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();

      const current = await module.namespace.runCurrentSession();
      assert.equal(current.call.name, 'creator-invite');
      assert.deepEqual(current.call.options.body, {{
        emails: ['employee@example.test'],
        organization_id: '11111111-1111-4111-8111-111111111111',
      }});
      assert.equal(current.persisted.length, 1);
      assert.equal(current.result.results[0].email, 'employee@example.test');
      assert.equal(current.loads.length, 1);
      assert.equal(current.tracks.length, 1);
      assert.equal(current.toasts.length, 1);
      assert.equal(current.renders.length, 1);
      assert.equal(current.dirty, undefined);

      const stale = await module.namespace.runStaleSession();
      assert.deepEqual(stale.call.options.body, {{
        emails: ['private-a@example.test'],
        organization_id: '11111111-1111-4111-8111-111111111111',
      }});
      assert.deepEqual(stale.result, {{ marker: 'new-session-result' }});
      assert.equal(stale.notice, 'new-session-notice');
      assert.equal(stale.persisted.length, 0);
      assert.equal(stale.loads.length, 0);
      assert.equal(stale.tracks.length, 0);
      assert.equal(stale.toasts.length, 0);
      assert.equal(stale.renders.length, 0);
      assert.equal(stale.dirty, '1');
      console.log('employee-admin-invite-org-race: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-invite-org-race: PASS" in result.stdout


def test_admin_mutation_late_success_or_failure_cannot_touch_a_new_session() -> None:
    run_mutation = _between(
        APP,
        "async function runAdminMutation(busyKey, operation, successMessage) {",
        "function trainingAchievementShelfMarkup(",
    )
    harness = f"""
      const ORG_A = '11111111-1111-4111-8111-111111111111';
      const ORG_B = '22222222-2222-4222-8222-222222222222';
      const WORKSPACE_REQUEST_TIMEOUT_MS = 25_000;
      const toasts = [];
      const renders = [];
      const loads = [];
      const state = {{
        dataEpoch: 1,
        user: {{ id: 'user-a' }},
        api: {{ organizationId: ORG_A, adminSnapshot() {{}} }},
        adminPeople: {{
          busyKey: '',
          error: '',
          notice: '',
          data: {{ ok: true }},
          status: 'ready',
        }},
      }};
      function canManageTeam() {{ return true; }}
      function toast(message, kind) {{ toasts.push({{ message, kind }}); }}
      function isAdminRoute() {{ return true; }}
      function renderAdminPeople() {{ renders.push('render'); }}
      function withUiTimeout(promise) {{ return promise; }}
      async function loadAdminPeople(options) {{ loads.push(options); }}
      function actionErrorMessage(error) {{ return `safe:${{String(error?.message || error)}}`; }}

      {run_mutation}

      function reset() {{
        toasts.length = 0;
        renders.length = 0;
        loads.length = 0;
        state.dataEpoch = 1;
        state.user = {{ id: 'user-a' }};
        state.api = {{ organizationId: ORG_A, adminSnapshot() {{}} }};
        state.adminPeople = {{
          busyKey: '', error: '', notice: '', data: {{ ok: true }}, status: 'ready',
        }};
      }}
      async function beginDeferred(kind) {{
        let settle;
        const deferred = new Promise((resolve, reject) => {{
          settle = kind === 'reject' ? reject : resolve;
        }});
        const pending = runAdminMutation('member:target', () => deferred, 'saved');
        await Promise.resolve();
        return {{ pending, settle }};
      }}
      function switchSession() {{
        state.dataEpoch = 2;
        state.user = {{ id: 'user-b' }};
        state.api = {{ organizationId: ORG_B, adminSnapshot() {{}} }};
        state.adminPeople = {{
          busyKey: 'new-session-operation',
          error: 'new-session-error',
          notice: 'new-session-notice',
          data: {{ ok: true }},
          status: 'refreshing',
        }};
      }}
      function snapshot(result) {{
        return {{
          result,
          adminPeople: {{ ...state.adminPeople }},
          toasts: [...toasts],
          renders: [...renders],
          loads: [...loads],
        }};
      }}

      export async function runCurrent() {{
        reset();
        const result = await runAdminMutation(
          'member:target',
          () => Promise.resolve({{ ok: true }}),
          'saved',
        );
        return snapshot(result);
      }}
      export async function runStaleSuccess() {{
        reset();
        const {{ pending, settle }} = await beginDeferred('resolve');
        switchSession();
        settle({{ ok: true }});
        return snapshot(await pending);
      }}
      export async function runStaleFailure() {{
        reset();
        const {{ pending, settle }} = await beginDeferred('reject');
        switchSession();
        settle(new Error('old-session-failure'));
        return snapshot(await pending);
      }}
    """
    script = f"""
      import assert from 'node:assert/strict';
      import vm from 'node:vm';
      const module = new vm.SourceTextModule({json.dumps(harness)}, {{
        identifier: 'employee-admin-mutation-race-harness.js',
      }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();

      const current = await module.namespace.runCurrent();
      assert.equal(current.result, true);
      assert.equal(current.adminPeople.busyKey, '');
      assert.equal(current.adminPeople.notice, 'saved');
      assert.equal(current.loads.length, 1);
      assert.deepEqual(current.toasts, [{{ message: 'saved', kind: 'success' }}]);

      for (const stale of [
        await module.namespace.runStaleSuccess(),
        await module.namespace.runStaleFailure(),
      ]) {{
        assert.equal(stale.result, false);
        assert.equal(stale.adminPeople.busyKey, 'new-session-operation');
        assert.equal(stale.adminPeople.notice, 'new-session-notice');
        assert.equal(stale.adminPeople.error, 'new-session-error');
        assert.equal(stale.adminPeople.status, 'refreshing');
        assert.equal(stale.loads.length, 0);
        assert.equal(stale.toasts.length, 0);
        assert.equal(stale.renders.length, 1, 'only the pre-await old-session render is allowed');
      }}
      console.log('employee-admin-mutation-race: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-mutation-race: PASS" in result.stdout


def test_admin_load_recovers_invite_history_from_server_with_local_fallback() -> None:
    load_admin = _between(
        APP,
        "async function loadAdminPeople({ silent = false } = {}) {",
        "async function runAdminMutation(",
    )
    harness = f"""
      const WORKSPACE_REQUEST_TIMEOUT_MS = 25_000;
      const AUTH_REQUEST_TIMEOUT_MS = 25_000;
      const persistedResults = [];
      const rendered = [];
      const warnings = [];
      const fallback = {{ persistence: 'session', results: [{{ email: 'local@example.test' }}] }};
      const console = {{ warn(...args) {{ warnings.push(args); }} }};
      class CreatorApiError extends Error {{
        constructor(message, options = {{}}) {{
          super(message);
          this.code = options.code || '';
        }}
      }}
      const validSnapshot = {{
        ok: true,
        organization: {{ id: '11111111-1111-4111-8111-111111111111' }},
        actor: {{ role: 'owner' }},
        members: [],
        accounts: [],
      }};
      const state = {{
        dataEpoch: 10,
        user: {{ id: 'owner-a' }},
        api: null,
        teamInviteResult: null,
        adminPeople: {{
          requestId: 0,
          status: 'idle',
          data: null,
          error: '',
        }},
      }};
      function canManageTeam() {{ return true; }}
      function withUiTimeout(promise) {{ return promise; }}
      function normalizeAdminSnapshot(raw) {{ return raw; }}
      function persistTeamInviteResult(value) {{ persistedResults.push(value); }}
      function restoreTeamInviteResult() {{ return fallback; }}
      function isAdminRoute() {{ return true; }}
      function renderAdminPeople() {{ rendered.push('render'); }}
      function actionErrorMessage(error) {{ return String(error?.message || error); }}

      {load_admin}

      function reset() {{
        persistedResults.length = 0;
        rendered.length = 0;
        warnings.length = 0;
        state.dataEpoch += 1;
        state.user = {{ id: 'owner-a' }};
        state.teamInviteResult = null;
        state.adminPeople = {{ requestId: 0, status: 'idle', data: null, error: '' }};
      }}
      export async function serverHistory() {{
        reset();
        const server = {{
          persistence: 'stored',
          results: [{{ email: 'server@example.test', status: 'invited' }}],
        }};
        state.api = {{
          adminSnapshot: () => Promise.resolve(validSnapshot),
          inviteAttempts: () => Promise.resolve(server),
        }};
        const result = await loadAdminPeople();
        return {{
          result,
          invite: state.teamInviteResult,
          persisted: [...persistedResults],
          rendered: [...rendered],
          warnings: [...warnings],
          status: state.adminPeople.status,
        }};
      }}
      export async function localFallback() {{
        reset();
        state.api = {{
          adminSnapshot: () => Promise.resolve(validSnapshot),
          inviteAttempts: () => Promise.reject(new Error('journal offline')),
        }};
        const result = await loadAdminPeople();
        return {{
          result,
          invite: state.teamInviteResult,
          persisted: [...persistedResults],
          rendered: [...rendered],
          warnings: [...warnings],
          status: state.adminPeople.status,
        }};
      }}
    """
    script = f"""
      import assert from 'node:assert/strict';
      import vm from 'node:vm';
      const module = new vm.SourceTextModule({json.dumps(harness)}, {{
        identifier: 'employee-admin-journal-recovery-harness.js',
      }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();

      const server = await module.namespace.serverHistory();
      assert.equal(server.result.ok, true);
      assert.equal(server.status, 'ready');
      assert.equal(server.invite.persistence, 'stored');
      assert.equal(server.invite.results[0].email, 'server@example.test');
      assert.equal(server.persisted.length, 1);
      assert.equal(server.persisted[0], server.invite);
      assert.equal(server.warnings.length, 0);
      assert.equal(server.rendered.length, 2);

      const fallback = await module.namespace.localFallback();
      assert.equal(fallback.result.ok, true);
      assert.equal(fallback.status, 'ready');
      assert.equal(fallback.invite.persistence, 'session');
      assert.equal(fallback.invite.results[0].email, 'local@example.test');
      assert.equal(fallback.persisted.length, 0);
      assert.equal(fallback.warnings.length, 1);
      assert.equal(fallback.rendered.length, 2);
      console.log('employee-admin-journal-recovery: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-journal-recovery: PASS" in result.stdout


def test_admin_view_escapes_untrusted_values_and_drops_credential_fields() -> None:
    script = f"""
      import assert from 'node:assert/strict';
      import fs from 'node:fs';
      import vm from 'node:vm';

      const source = fs.readFileSync({json.dumps(str(VIEW_PATH))}, 'utf8');
      const module = new vm.SourceTextModule(source, {{ identifier: 'admin-people-view.js' }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();
      const {{ normalizeAdminSnapshot, adminPeopleMarkup }} = module.namespace;

      const attack = '\"><img src=x onerror=alert(1)>';
      const snapshot = normalizeAdminSnapshot({{
        ok: true,
        organization: {{ id: 'org', name: attack, password: 'ORG_SECRET' }},
        actor: {{ profile_id: 'actor', role: attack, access_token: 'ACTOR_TOKEN' }},
        members: [{{
          membership_id: 'membership',
          profile_id: `profile-${{attack}}`,
          email: `employee-${{attack}}@example.test`,
          display_name: attack,
          role: attack,
          status: 'active',
          auth_confirmed: true,
          auth_active: true,
          courses_completed: 4,
          courses_required: 4,
          exam_passed: false,
          access_waiver_active: true,
          access_waiver_reason: attack,
          password: 'MEMBER_PASSWORD_SENTINEL',
          refresh_token: 'MEMBER_REFRESH_TOKEN_SENTINEL',
          accounts: [{{
            account_id: 'nested-account',
            platform: 'youtube',
            label: attack,
            handle: attack,
            url: 'javascript:alert(1)',
            password: 'NESTED_ACCOUNT_SECRET_SENTINEL',
          }}],
        }}],
        accounts: [{{
          id: `account-${{attack}}`,
          platform: 'youtube',
          label: attack,
          handle: attack,
          url: 'javascript:alert(1)',
          notes: attack,
          status: 'active',
          updated_at: '2026-08-12T09:30:00.000Z',
          assigned_profile_id: `profile-${{attack}}`,
          password: 'ACCOUNT_PASSWORD_SENTINEL',
          cookie: 'ACCOUNT_COOKIE_SENTINEL',
          api_key: 'ACCOUNT_API_KEY_SENTINEL',
          two_factor_code: 'ACCOUNT_2FA_SENTINEL',
        }}],
        password: 'SNAPSHOT_PASSWORD_SENTINEL',
      }});

      assert.equal(snapshot.accounts[0].url, '');
      assert.equal(snapshot.members[0].accounts[0].url, '');
      assert.equal(snapshot.members[0].accessWaiverActive, true);
      assert.equal(snapshot.members[0].accessWaiverReason, attack);
      const people = adminPeopleMarkup({{
        snapshot,
        view: 'people',
        notice: attack,
        error: attack,
        inviteResult: {{ results: [{{ email: attack, status: attack }}] }},
      }});
      const accounts = adminPeopleMarkup({{
        snapshot,
        view: 'accounts',
        notice: attack,
        error: attack,
      }});
      const html = `${{people}}\n${{accounts}}`;

      assert.equal(/<(?:script|img|svg|iframe)\\b/iu.test(html), false);
      assert.equal(html.includes('javascript:'), false);
      assert.equal(html.includes('&lt;img src=x onerror=alert(1)&gt;'), true);
      assert.equal(
        html.includes('title="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"'),
        true,
        'the waiver reason must be escaped inside its title attribute',
      );
      for (const sentinel of [
        'ORG_SECRET',
        'ACTOR_TOKEN',
        'MEMBER_PASSWORD_SENTINEL',
        'MEMBER_REFRESH_TOKEN_SENTINEL',
        'NESTED_ACCOUNT_SECRET_SENTINEL',
        'ACCOUNT_PASSWORD_SENTINEL',
        'ACCOUNT_COOKIE_SENTINEL',
        'ACCOUNT_API_KEY_SENTINEL',
        'ACCOUNT_2FA_SENTINEL',
        'SNAPSHOT_PASSWORD_SENTINEL',
      ]) {{
        assert.equal(html.includes(sentinel), false, sentinel);
      }}

      const allowedFields = new Set([
        'emails',
        'reason',
        'confirm',
        'platform',
        'label',
        'handle',
        'url',
        'notes',
        'profile_id',
        // Владение (фаза 0 авторазмещения): реквизиты без секретов.
        'ownership_kind',
        'custodian_profile_id',
        'registration_email_alias',
        'registration_phone_ref',
        'external_account_id',
        'posting_mode',
      ]);
      const formFields = [...html.matchAll(/\\bname="([^"]+)"/gu)]
        .map((match) => match[1]);
      assert.equal(formFields.length > 0, true);
      for (const field of formFields) assert.equal(allowedFields.has(field), true, field);
      for (const forbidden of [
        'password',
        'token',
        'cookie',
        'secret',
        'credential',
        'two_factor',
        'otp',
      ]) {{
        assert.equal(
          formFields.some((field) => field.toLowerCase().includes(forbidden)),
          false,
          forbidden,
        );
      }}

      const memberKeys = Object.keys(snapshot.members[0]);
      const accountKeys = Object.keys(snapshot.accounts[0]);
      assert.equal(memberKeys.includes('accessWaiverActive'), true);
      assert.equal(memberKeys.includes('accessWaiverReason'), true);
      for (const forbidden of ['password', 'access_token', 'refresh_token', 'cookie', 'api_key']) {{
        assert.equal(memberKeys.includes(forbidden), false);
        assert.equal(accountKeys.includes(forbidden), false);
      }}
      console.log('employee-admin-view-security: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-view-security: PASS" in result.stdout


def test_admin_view_enforces_role_matrix_and_assignment_eligibility() -> None:
    script = f"""
      import assert from 'node:assert/strict';
      import fs from 'node:fs';
      import vm from 'node:vm';

      const source = fs.readFileSync({json.dumps(str(VIEW_PATH))}, 'utf8');
      const module = new vm.SourceTextModule(source, {{ identifier: 'admin-people-view.js' }});
      await module.link(() => {{ throw new Error('unexpected import'); }});
      await module.evaluate();
      const {{ normalizeAdminSnapshot, adminPeopleMarkup }} = module.namespace;

      const members = [
        {{
          profile_id: 'owner-actor', display_name: 'Owner Actor', email: 'owner@example.test', role: 'owner',
          status: 'active', auth_confirmed: true, auth_active: true,
        }},
        {{
          profile_id: 'admin-target', display_name: 'Admin Target', email: 'admin@example.test', role: 'admin',
          status: 'active', auth_confirmed: true, auth_active: true,
        }},
        {{
          profile_id: 'operator-ok', display_name: 'Duplicate Name', email: 'operator-one@example.test', role: 'operator',
          status: 'active', auth_confirmed: true, auth_active: true,
        }},
        {{
          profile_id: 'operator-ok-two', display_name: 'Duplicate Name', email: 'operator-two@example.test', role: 'operator',
          status: 'active', auth_confirmed: true, auth_active: true,
        }},
        {{
          profile_id: 'operator-unconfirmed', display_name: 'Unconfirmed Candidate', email: 'unconfirmed@example.test', role: 'operator',
          status: 'active', auth_confirmed: false, auth_active: true,
        }},
        {{
          profile_id: 'operator-disabled', display_name: 'Disabled Candidate', email: 'disabled@example.test', role: 'operator',
          status: 'active', auth_confirmed: true, auth_active: false,
        }},
        {{
          profile_id: 'operator-suspended', display_name: 'Suspended Candidate', email: 'suspended@example.test', role: 'operator',
          status: 'suspended', auth_confirmed: true, auth_active: true,
        }},
      ];
      const accounts = [
        {{
          id: 'account-open', platform: 'youtube', label: 'Open Account',
          status: 'active', updated_at: '2026-08-12T09:30:00.000Z',
        }},
        {{
          id: 'account-admin', platform: 'youtube', label: 'Admin Account',
          status: 'active', updated_at: '2026-08-12T09:30:00.000Z',
          assigned_profile_id: 'admin-target',
        }},
        {{
          id: 'account-suspended', platform: 'youtube', label: 'Suspended Account',
          status: 'active', updated_at: '2026-08-12T09:30:00.000Z',
          assigned_profile_id: 'operator-suspended',
        }},
      ];
      function snapshot(actor) {{
        return normalizeAdminSnapshot({{
          ok: true,
          organization: {{ id: 'org', name: 'Org' }},
          actor,
          members,
          accounts,
        }});
      }}
      function markup(data, view) {{
        return adminPeopleMarkup({{ snapshot: data, view }});
      }}
      // Выбор хранителя (владелец/админ/продюсер) живёт в отдельной форме
      // владения; право назначения исполнителя проверяется по форме закрепления.
      function bindForm(card) {{
        const start = card.indexOf('<form class="admin-account-bind-form"');
        if (start === -1) return '';
        const end = card.indexOf('</form>', start);
        return card.slice(start, end);
      }}
      function accountCard(html, id) {{
        const startMarker = `<article class="admin-account" data-account-id="${{id}}">`;
        const start = html.indexOf(startMarker);
        assert.notEqual(start, -1, `missing account card ${{id}}`);
        const end = html.indexOf('</article>', start);
        assert.notEqual(end, -1, `unterminated account card ${{id}}`);
        return html.slice(start + startMarker.length, end);
      }}
      function personCard(html, id) {{
        const startMarker = `<article class="admin-person" data-profile-id="${{id}}">`;
        const start = html.indexOf(startMarker);
        assert.notEqual(start, -1, `missing person card ${{id}}`);
        const end = html.indexOf('</article>', start);
        assert.notEqual(end, -1, `unterminated person card ${{id}}`);
        return html.slice(start + startMarker.length, end);
      }}

      const adminSnapshot = snapshot({{ profile_id: 'actor-admin', role: 'admin' }});
      const adminAccounts = markup(adminSnapshot, 'accounts');
      const openForAdmin = bindForm(accountCard(adminAccounts, 'account-open'));
      assert.equal(openForAdmin.includes('value="operator-ok"'), true);
      assert.equal(openForAdmin.includes('value="operator-ok-two"'), true);
      assert.equal(openForAdmin.includes('Duplicate Name · operator-one@example.test'), true);
      assert.equal(openForAdmin.includes('Duplicate Name · operator-two@example.test'), true);
      for (const forbidden of [
        'owner-actor',
        'admin-target',
        'operator-unconfirmed',
        'operator-disabled',
        'operator-suspended',
      ]) {{
        assert.equal(
          openForAdmin.includes(`value="${{forbidden}}"`),
          false,
          `${{forbidden}} must not be an eligible assignee for an admin`,
        );
      }}

      const protectedAccount = accountCard(adminAccounts, 'account-admin');
      assert.equal(protectedAccount.includes('admin-account-bind-form'), false);
      assert.equal(protectedAccount.includes('admin-account-edit-form'), false);
      assert.equal(protectedAccount.includes('admin-account-archive-form'), false);
      assert.equal(protectedAccount.includes('admin-action-note'), true);
      const suspendedAccount = accountCard(adminAccounts, 'account-suspended');
      assert.equal(
        suspendedAccount.includes('data-current-profile-id="operator-suspended"'),
        true,
      );
      assert.equal(
        suspendedAccount.includes('value="operator-suspended" selected disabled'),
        false,
      );
      assert.equal(
        suspendedAccount.includes('value="operator-suspended" selected'),
        true,
      );
      assert.equal(
        suspendedAccount.includes('Suspended Candidate · suspended@example.test'),
        true,
      );
      const adminPeople = markup(adminSnapshot, 'people');
      const adminTargetForAdmin = personCard(adminPeople, 'admin-target');
      assert.equal(adminTargetForAdmin.includes('data-member-action='), false);
      assert.equal(adminTargetForAdmin.includes('admin-action-note'), true);

      const ownerSnapshot = snapshot({{ profile_id: 'owner-actor', role: 'owner' }});
      const ownerAccounts = markup(ownerSnapshot, 'accounts');
      const adminAccountForOwner = accountCard(ownerAccounts, 'account-admin');
      assert.equal(adminAccountForOwner.includes('admin-account-bind-form'), true);
      assert.equal(adminAccountForOwner.includes('admin-account-edit-form'), true);
      assert.equal(adminAccountForOwner.includes('admin-account-archive-form'), true);
      assert.equal(adminAccountForOwner.includes('admin-account-ownership-form'), true);
      const adminBindForOwner = bindForm(adminAccountForOwner);
      assert.equal(adminBindForOwner.includes('value="admin-target"'), true);
      for (const forbidden of [
        'operator-unconfirmed',
        'operator-disabled',
        'operator-suspended',
      ]) {{
        assert.equal(adminBindForOwner.includes(`value="${{forbidden}}"`), false);
      }}
      const ownerPeople = markup(ownerSnapshot, 'people');
      const adminTargetForOwner = personCard(ownerPeople, 'admin-target');
      assert.equal(
        adminTargetForOwner.includes('data-member-action="suspend_member"'),
        true,
      );
      assert.equal(
        adminTargetForOwner.includes('data-member-action="revoke_member"'),
        true,
      );
      const ownerSelf = personCard(ownerPeople, 'owner-actor');
      assert.equal(ownerSelf.includes('data-member-action='), false);
      console.log('employee-admin-view-policy: PASS');
    """
    result = _run_node(script)
    assert "employee-admin-view-policy: PASS" in result.stdout


def test_admin_route_and_forms_are_wired_to_the_hash_spa() -> None:
    index = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")
    assert 'const ADMIN_PEOPLE_PATH = "/admin/people"' in APP
    assert 'path === "/admin" || path === ADMIN_PEOPLE_PATH' in APP
    assert 'form.id === "admin-invite-form"' in APP
    assert 'requestSupabase.functions.invoke("creator-invite"' in APP
    assert "state.api.adminMemberAction" in APP
    assert "state.api.createManagedAccount" in APP
    assert "state.api.updateManagedAccount" in APP
    assert "state.api.assignManagedAccount" in APP
    assert 'const currentProfileId = String(form.dataset.currentProfileId || "")' in APP
    assert 'if (profileId === currentProfileId)' in APP
    assert 'toast("Назначение не изменилось.", "info")' in APP
    assert "state.api.archiveManagedAccount" in APP
    assert 'href="#/admin/people"' in VIEW
    assert "admin-people.css" in index
    assert "admin-people-view.js" in APP
    assert "accessWaiverActive: source.access_waiver_active === true" in VIEW
    assert "accessWaiverReason: text(source.access_waiver_reason)" in VIEW
    assert 'class="admin-waiver"' in VIEW
    load_section = _between(
        APP,
        "async function loadSection(",
        "function beginMyWorkNotificationFetch(",
    )
    team_history = _between(
        load_section,
        'if (section === "team") {',
        'if (section === "media" || section === "board" || section === "review")',
    )
    assert "const requestApi = state.api" in load_section
    assert "const requestOrganizationId = requestApi?.organizationId" in load_section
    assert "requestApi === state.api" in load_section
    assert "requestOrganizationId === state.api?.organizationId" in load_section
    assert "requestApi.inviteAttempts()" in team_history
    assert team_history.count("if (!requestIsCurrent()) return") >= 2

    load_bootstrap = _between(
        APP,
        "async function loadBootstrap(",
        "function authenticatedRouteCompatible(",
    )
    context_change = _between(
        load_bootstrap,
        "previousProjectContextKey !== nextProjectContextKey",
        "state.bootstrap = bootstrap",
    )
    assert "state.teamInviteResult = null" in context_change
    assert "resetAdminPeopleState()" in context_change
