from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web" / "app" / "workspace-ai-research-training.js"
API_PATH = ROOT / "web" / "app" / "supabase-api.js"


def run_module_script(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = f"""
      const {{ readFileSync }} = await import('node:fs');
      const source = readFileSync(process.argv[1], 'utf8');
      const encoded = Buffer.from(source).toString('base64');
      const mod = await import(`data:text/javascript;base64,${{encoded}}`);

      class MemoryStorage {{
        constructor() {{ this.values = new Map(); }}
        getItem(key) {{ return this.values.has(key) ? this.values.get(key) : null; }}
        setItem(key, value) {{ this.values.set(key, String(value)); }}
        removeItem(key) {{ this.values.delete(key); }}
        get size() {{ return this.values.size; }}
      }}

      const ids = Object.freeze({{
        organizationA: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        actorA: '11111111-1111-4111-8111-111111111111',
        actorB: '12121212-1212-4121-8121-121212121212',
        projectA: '22222222-2222-4222-8222-222222222222',
        projectB: '23232323-2323-4232-8232-232323232323',
        receiptA: '33333333-3333-4333-8333-333333333333',
        receiptB: '34343434-3434-4343-8343-343434343434',
        selectionA: '44444444-4444-4444-8444-444444444444',
        selectionB: '45454545-4545-4454-8454-454545454545',
      }});
      const receiptHash = 'a'.repeat(64);

      function scope({{ actorId = ids.actorA, projectId = ids.projectA,
                         receiptId = ids.receiptA }} = {{}}) {{
        return {{
          actorId,
          organizationId: ids.organizationA,
          projectId,
          receiptId,
        }};
      }}

      function request({{ projectId = ids.projectA, receiptId = ids.receiptA,
                           decision = 'approve', title = 'Human edit' }} = {{}}) {{
        return {{
          organization_id: ids.organizationA,
          project_id: projectId,
          product_category: 'cosmetics',
          receipt_id: receiptId,
          receipt_hash: receiptHash,
          decision,
          selected_insight_keys: decision === 'approve'
            ? ['trends', 'category']
            : [],
          selected_scenario_positions: decision === 'approve' ? [1] : [],
          edits: decision === 'approve' ? [{{
            position: 1,
            title,
            hook: 'Human hook',
            spoken_script: 'Human script',
            shot_list: 'frame one\\nframe two',
            key_message: 'Human message',
            visual_direction: 'Human visual',
            cta: 'Human CTA',
          }}] : [],
          operator_notes: 'Checked by human',
          confirmation: true,
        }};
      }}

      function matchingSnapshot({{
        actorId = ids.actorA,
        projectId = ids.projectA,
        receiptId = ids.receiptA,
        selectionId = ids.selectionA,
        decision = 'approve',
        title = 'Human edit',
      }} = {{}}) {{
        return {{
          organization_id: ids.organizationA,
          project_id: projectId,
          product_category: 'cosmetics',
          queue: [],
          learned: [{{
            selection_id: selectionId,
            receipt_id: receiptId,
            receipt_hash: receiptHash,
            project_id: projectId,
            product_category: 'cosmetics',
            selected_by: actorId,
            decision,
            selected_insight_keys: decision === 'approve'
              ? ['category', 'trends']
              : [],
            selected_scenario_positions: decision === 'approve' ? [1] : [],
            recommendations: decision === 'approve' ? [{{
              position: 1,
              title,
              hook: 'Human hook',
              spoken_script: 'Human script',
              shot_list: 'frame one\\nframe two',
              key_message: 'Human message',
              visual_direction: 'Human visual',
              cta: 'Human CTA',
            }}] : [],
            operator_notes: 'Checked by human',
            ownership: 'own',
          }}],
        }};
      }}

      function pendingSnapshot({{ projectId = ids.projectA,
                                  receiptId = ids.receiptA }} = {{}}) {{
        return {{
          organization_id: ids.organizationA,
          project_id: projectId,
          product_category: 'cosmetics',
          queue: [{{
            receipt_id: receiptId,
            receipt_hash: receiptHash,
            project_id: projectId,
            ownership: 'own',
          }}],
          learned: [],
        }};
      }}

      {body}
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, str(MODULE_PATH)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def run_api_script(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = f"""
      const mod = await import({json.dumps(API_PATH.as_uri())});
      const result = await (async () => {{
{body}
      }})();
      process.stdout.write(JSON.stringify(result));
    """
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_committed_but_lost_response_is_recovered_from_exact_receipt() -> None:
    value = run_module_script(
        """
        const storage = new MemoryStorage();
        let sentKey = '';
        let reloads = 0;
        const result = await mod.performTrainingDecisionMutation({
          storage,
          scope: scope(),
          request: request(),
          now: 1000,
          createIdempotencyKey: () =>
            'research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          send: async (payload) => {
            sentKey = payload.idempotency_key;
            const lost = new TypeError('connection closed after commit');
            lost.code = 'network_response_lost';
            throw lost;
          },
          reload: async () => {
            reloads += 1;
            return matchingSnapshot();
          },
        });
        console.log(JSON.stringify({
          status: result.status,
          recovered: result.recovered,
          decision: result.intent.request.decision,
          selectionId: result.selection.selection_id,
          sentKey,
          reloads,
          storageSize: storage.size,
        }));
        """
    )

    assert value == {
        "status": "success",
        "recovered": True,
        "decision": "approve",
        "selectionId": "44444444-4444-4444-8444-444444444444",
        "sentKey": "research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "reloads": 1,
        "storageSize": 0,
    }


def test_already_decided_is_success_only_for_the_matching_server_selection() -> None:
    value = run_module_script(
        """
        const storage = new MemoryStorage();
        let matchingSends = 0;
        const matching = await mod.performTrainingDecisionMutation({
          storage,
          scope: scope(),
          request: request(),
          now: 1000,
          createIdempotencyKey: () =>
            'research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          send: async () => {
            matchingSends += 1;
            const error = new Error('already decided');
            error.code = '40001';
            error.serverCode = 'ai_research_training_already_decided';
            throw error;
          },
          reload: async () => matchingSnapshot(),
        });

        let conflictCode = '';
        let conflictSends = 0;
        const conflictStorage = new MemoryStorage();
        try {
          await mod.performTrainingDecisionMutation({
            storage: conflictStorage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: () =>
              'research-training-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
            send: async () => {
              conflictSends += 1;
              const error = new Error('already decided');
              error.serverCode = 'ai_research_training_already_decided';
              throw error;
            },
            reload: async () => matchingSnapshot({ actorId: ids.actorB }),
          });
        } catch (error) {
          conflictCode = error.code;
        }
        console.log(JSON.stringify({
          matchingStatus: matching.status,
          matchingRecovered: matching.recovered,
          matchingSends,
          matchingStorageSize: storage.size,
          conflictCode,
          conflictSends,
          conflictStorageSize: conflictStorage.size,
        }));
        """
    )

    assert value == {
        "matchingStatus": "success",
        "matchingRecovered": True,
        "matchingSends": 1,
        "matchingStorageSize": 0,
        "conflictCode": "ai_research_training_decision_conflict",
        "conflictSends": 1,
        "conflictStorageSize": 0,
    }


def test_repeat_after_reload_reuses_the_same_logical_decision_key() -> None:
    value = run_module_script(
        """
        const storage = new MemoryStorage();
        const keys = [];
        let generated = 0;
        let reloads = 0;
        let firstError = '';
        const makeKey = () => {
          generated += 1;
          return 'research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
        };
        try {
          await mod.performTrainingDecisionMutation({
            storage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: makeKey,
            send: async (payload) => {
              keys.push(payload.idempotency_key);
              const error = new TypeError('response lost');
              error.code = 'network_response_lost';
              throw error;
            },
            reload: async () => {
              reloads += 1;
              return pendingSnapshot();
            },
          });
        } catch (error) {
          firstError = error.code;
        }

        const second = await mod.performTrainingDecisionMutation({
          storage,
          scope: scope(),
          request: request(),
          now: 1001,
          createIdempotencyKey: makeKey,
          send: async (payload) => {
            keys.push(payload.idempotency_key);
            return { snapshot: matchingSnapshot() };
          },
          reload: async () => {
            reloads += 1;
            return pendingSnapshot();
          },
        });
        console.log(JSON.stringify({
          firstError,
          secondStatus: second.status,
          generated,
          keys,
          reloads,
          storageSize: storage.size,
        }));
        """
    )

    assert value == {
        "firstError": "ai_research_training_decision_unconfirmed",
        "secondStatus": "success",
        "generated": 1,
        "keys": [
            "research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        ],
        "reloads": 2,
        "storageSize": 0,
    }


def test_pending_key_is_never_reused_across_actor_or_project_scope() -> None:
    value = run_module_script(
        """
        const storage = new MemoryStorage();
        const generatedKeys = [
          'research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          'research-training-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
          'research-training-cccccccc-cccc-4ccc-8ccc-cccccccccccc',
        ];
        let generated = 0;
        const makeKey = () => generatedKeys[generated++];
        const sent = [];

        try {
          await mod.performTrainingDecisionMutation({
            storage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: makeKey,
            send: async (payload) => {
              sent.push(payload.idempotency_key);
              throw new TypeError('response lost');
            },
            reload: async () => pendingSnapshot(),
          });
        } catch {}

        await mod.performTrainingDecisionMutation({
          storage,
          scope: scope({ actorId: ids.actorB }),
          request: request(),
          now: 1001,
          createIdempotencyKey: makeKey,
          send: async (payload) => {
            sent.push(payload.idempotency_key);
            return { snapshot: matchingSnapshot({ actorId: ids.actorB }) };
          },
          reload: async () => { throw new Error('must not preflight another actor'); },
        });

        await mod.performTrainingDecisionMutation({
          storage,
          scope: scope({ projectId: ids.projectB, receiptId: ids.receiptB }),
          request: request({ projectId: ids.projectB, receiptId: ids.receiptB }),
          now: 1002,
          createIdempotencyKey: makeKey,
          send: async (payload) => {
            sent.push(payload.idempotency_key);
            return {
              snapshot: matchingSnapshot({
                projectId: ids.projectB,
                receiptId: ids.receiptB,
                selectionId: ids.selectionB,
              }),
            };
          },
          reload: async () => { throw new Error('must not preflight another project'); },
        });

        console.log(JSON.stringify({
          generated,
          sent,
          storageSize: storage.size,
          actorAKey: mod.trainingDecisionIntentStorageKey(scope()),
          actorBKey: mod.trainingDecisionIntentStorageKey(
            scope({ actorId: ids.actorB }),
          ),
          projectBKey: mod.trainingDecisionIntentStorageKey(
            scope({ projectId: ids.projectB, receiptId: ids.receiptB }),
          ),
        }));
        """
    )

    assert value["generated"] == 3
    assert value["sent"] == [
        "research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "research-training-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "research-training-cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    ]
    assert value["storageSize"] == 1
    assert len(
        {value["actorAKey"], value["actorBKey"], value["projectBKey"]}
    ) == 3


def test_changed_human_choice_gets_a_new_key_only_after_exact_pending_reload() -> None:
    value = run_module_script(
        """
        const storage = new MemoryStorage();
        const events = [];
        const keys = [
          'research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          'research-training-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        ];
        let keyIndex = 0;
        try {
          await mod.performTrainingDecisionMutation({
            storage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: () => keys[keyIndex++],
            send: async (payload) => {
              events.push(`send:${payload.decision}:${payload.idempotency_key}`);
              throw new TypeError('response lost');
            },
            reload: async () => {
              events.push('reload');
              return pendingSnapshot();
            },
          });
        } catch {}

        const changed = await mod.performTrainingDecisionMutation({
          storage,
          scope: scope(),
          request: request({ decision: 'reject' }),
          now: 1001,
          createIdempotencyKey: () => keys[keyIndex++],
          send: async (payload) => {
            events.push(`send:${payload.decision}:${payload.idempotency_key}`);
            return { snapshot: matchingSnapshot({ decision: 'reject' }) };
          },
          reload: async () => {
            events.push('reload');
            return pendingSnapshot();
          },
        });
        console.log(JSON.stringify({
          events,
          keyIndex,
          decision: changed.intent.request.decision,
          storageSize: storage.size,
        }));
        """
    )

    assert value == {
        "events": [
            "send:approve:research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "reload",
            "reload",
            "send:reject:research-training-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        ],
        "keyIndex": 2,
        "decision": "reject",
        "storageSize": 0,
    }


def test_ambiguous_response_retains_key_but_definite_rejection_clears_it() -> None:
    value = run_module_script(
        """
        const ambiguousStorage = new MemoryStorage();
        let ambiguousCode = '';
        try {
          await mod.performTrainingDecisionMutation({
            storage: ambiguousStorage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: () =>
              'research-training-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            send: async () => ({ ok: true }),
            reload: async () => pendingSnapshot(),
          });
        } catch (error) {
          ambiguousCode = error.code;
        }

        const rejectedStorage = new MemoryStorage();
        let rejectedCode = '';
        try {
          await mod.performTrainingDecisionMutation({
            storage: rejectedStorage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: () =>
              'research-training-bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
            send: async () => {
              const error = new Error('selection required');
              error.serverCode = 'ai_research_training_selection_required';
              throw error;
            },
            reload: async () => ({ project_id: ids.projectB }),
          });
        } catch (error) {
          rejectedCode = error.serverCode || error.code;
        }

        const changedActorStorage = new MemoryStorage();
        let changedActorCode = '';
        try {
          await mod.performTrainingDecisionMutation({
            storage: changedActorStorage,
            scope: scope(),
            request: request(),
            now: 1000,
            createIdempotencyKey: () =>
              'research-training-cccccccc-cccc-4ccc-8ccc-cccccccccccc',
            send: async () => {
              const error = new Error('actor changed');
              error.code = 'auth_session_actor_changed';
              throw error;
            },
            reload: async () => pendingSnapshot(),
          });
        } catch (error) {
          changedActorCode = error.code;
        }

        console.log(JSON.stringify({
          ambiguousCode,
          ambiguousStorageSize: ambiguousStorage.size,
          rejectedCode,
          rejectedStorageSize: rejectedStorage.size,
          changedActorCode,
          changedActorStorageSize: changedActorStorage.size,
        }));
        """
    )

    assert value == {
        "ambiguousCode": "ai_research_training_decision_unconfirmed",
        "ambiguousStorageSize": 1,
        "rejectedCode": "ai_research_training_selection_required",
        "rejectedStorageSize": 0,
        "changedActorCode": "auth_session_actor_changed",
        "changedActorStorageSize": 0,
    }


def test_browser_integration_reloads_exact_scope_and_derives_actor_from_session() -> None:
    module = MODULE_PATH.read_text(encoding="utf-8")
    start = module.index("async function decide(card, decision)")
    end = module.index("\nfunction handleChange", start)
    decision = module[start:end]

    assert "authenticatedTrainingDecisionScope(" in decision
    assert "storage: trainingDecisionStorage()" in decision
    assert "receiptScope: shellAccess.receiptScope" in decision
    assert "const callWithinDecisionScope = (rpcName, payload)" in decision
    assert "mutationRoot.isConnected" in decision
    assert "currentTrainingProjectId() === projectId" in decision
    assert "decisionUuid(api.organizationId) === scope.organizationId" in decision
    assert "api.callAsExpectedActor(rpcName, payload, scope.actorId, {" in decision
    assert "isContextCurrent: decisionScopeIsCurrent" in decision
    assert "send: (payload) => callWithinDecisionScope(RPC_DECIDE, payload)" in decision
    assert "reload: () => callWithinDecisionScope(" in decision
    assert "RPC_QUEUE" in decision
    assert "product_category: request.product_category" in decision
    assert "receipt_id: receiptId" in decision
    assert "}, projectId))" in decision

    auth_start = module.index("async function authenticatedTrainingDecisionScope")
    auth_end = module.index("\nfunction trainingDecisionStorage", auth_start)
    auth_scope = module[auth_start:auth_end]
    assert "api?.supabase?.auth?.getSession" in auth_scope
    assert "data?.session?.user?.id" in auth_scope
    assert "api?.organizationId" in auth_scope
    assert "contextProjectId !== projectId" in auth_scope


def test_expected_actor_rpc_pins_the_checked_jwt_and_never_sends_on_mismatch() -> None:
    value = run_api_script(
        r"""
        const actorA = '11111111-1111-4111-8111-111111111111';
        const actorB = '12121212-1212-4121-8121-121212121212';
        let sessionActor = actorB;
        let contextCurrent = true;
        let fetchCalls = 0;
        let captured = null;
        globalThis.fetch = async (url, options) => {
          fetchCalls += 1;
          captured = {
            url: String(url),
            authorization: options.headers.Authorization,
            body: JSON.parse(options.body),
          };
          sessionActor = actorB;
          return {
            ok: true,
            status: 200,
            async text() {
              return JSON.stringify({ organization_id: options.body ?
                JSON.parse(options.body).p_payload.organization_id : null });
            },
          };
        };
        const api = Object.create(mod.CreatorApi.prototype);
        api.config = {
          SUPABASE_URL: 'https://example.supabase.co',
          SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test',
          RPC_SCHEMA: 'public',
        };
        api.supabase = {
          auth: {
            async getSession() {
              return {
                data: {
                  session: {
                    access_token: `token-${sessionActor}`,
                    user: { id: sessionActor },
                  },
                },
                error: null,
              };
            },
          },
        };

        let mismatchCode = '';
        try {
          await api.callAsExpectedActor(
            'contentengine_decide_ai_research_training',
            { organization_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' },
            actorA,
          );
        } catch (error) {
          mismatchCode = error.code;
        }
        const callsAfterMismatch = fetchCalls;

        sessionActor = actorA;
        contextCurrent = false;
        let contextCode = '';
        try {
          await api.callAsExpectedActor(
            'contentengine_decide_ai_research_training',
            { organization_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' },
            actorA,
            { isContextCurrent: () => contextCurrent },
          );
        } catch (error) {
          contextCode = error.code;
        }
        const callsAfterContextChange = fetchCalls;

        contextCurrent = true;
        const response = await api.callAsExpectedActor(
          'contentengine_decide_ai_research_training',
          { organization_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' },
          actorA,
          { isContextCurrent: () => contextCurrent },
        );
        return {
          mismatchCode,
          callsAfterMismatch,
          contextCode,
          callsAfterContextChange,
          fetchCalls,
          authorization: captured.authorization,
          url: captured.url,
          payload: captured.body.p_payload,
          response,
        };
        """
    )

    assert value == {
        "mismatchCode": "auth_session_actor_changed",
        "callsAfterMismatch": 0,
        "contextCode": "auth_session_context_changed",
        "callsAfterContextChange": 0,
        "fetchCalls": 1,
        "authorization": "Bearer token-11111111-1111-4111-8111-111111111111",
        "url": (
            "https://example.supabase.co/rest/v1/rpc/"
            "contentengine_decide_ai_research_training"
        ),
        "payload": {
            "organization_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
        "response": {
            "organization_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
    }
