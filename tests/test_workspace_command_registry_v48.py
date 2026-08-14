from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "workspace-command-registry.js"
SOURCE = MODULE.read_text(encoding="utf-8")


def _run_node(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the workspace command registry contract")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
            import * as subject from {json.dumps(MODULE.as_uri())};
            {body}
            """,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_contract_is_pure_bounded_and_has_no_executor_or_side_effect_owner() -> None:
    for forbidden in (
        "document.",
        "globalThis.document",
        "window.document",
        "window.location",
        "window.history",
        "window.open(",
        "globalThis.window",
        "location.",
        "history.",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "navigator.",
        "postMessage(",
    ):
        assert forbidden not in SOURCE

    result = _run_node(
        """
        process.stdout.write(JSON.stringify({
          version: subject.WORKSPACE_COMMAND_REGISTRY_CONTRACT_VERSION,
          actions: subject.WORKSPACE_COMMAND_ACTIONS,
          sources: subject.WORKSPACE_COMMAND_SOURCES,
          exports: [
            typeof subject.normalizeWorkspaceObjectRef,
            typeof subject.normalizeWorkspaceInternalTarget,
            typeof subject.validateWorkspaceCommandTarget,
            typeof subject.resolveWorkspaceCommand,
            typeof subject.workspaceCommandDefinition,
          ],
          everyInert: subject.WORKSPACE_COMMAND_ACTIONS.every((key) => {
            const definition = subject.workspaceCommandDefinition(key);
            return !('handler' in definition) && !('execute' in definition);
          }),
          allFrozen: Object.isFrozen(subject.WORKSPACE_COMMAND_ACTIONS)
            && Object.isFrozen(subject.WORKSPACE_INTERNAL_APP_TABS)
            && Object.isFrozen(subject.WORKSPACE_COMMAND_BLOCK_REASONS),
        }));
        """
    )
    assert result["version"] == "4.9.1"
    assert result["exports"] == ["function"] * 5
    assert result["everyInert"] is True
    assert result["allFrozen"] is True
    assert set(result["actions"]) == {
        "object.create-folder",
        "smart-folder.create",
        "finder.open-object",
        "window.open-finder",
        "dock.pin-shortcut",
        "dock.pin-file-shortcut",
        "dock.pin-internal-shortcut",
        "internal-target.open",
        "object.open",
        "quicklook.open",
        "relation.add:research",
        "relation.add:create",
        "relation.add:review",
        "versions.open",
        "trash.move",
        "trash.restore",
        "trash.delete-permanent",
        "object.move",
        "project.transfer.prepare",
        "ai.open-decisions",
        "process.open",
        "review.open-object",
    }


def test_internal_targets_normalize_view_to_tab_and_preserve_exact_space() -> None:
    result = _run_node(
        """
        const targets = [
          'contentengine://desktop/bombbar',
          'contentengine://object/file:bombbar-short-01',
          'contentengine://folder/bombbar:inbox',
          'contentengine://app/ai?view=decisions&space=bombbar',
          'contentengine://app/review?tab=mine&space=blacktiger',
          'contentengine://app/settings?space=bombbar',
        ].map((value) => subject.normalizeWorkspaceInternalTarget(value));
        process.stdout.write(JSON.stringify(targets));
        """
    )
    desktop, object_target, folder, ai, review, settings = result
    assert desktop == {
        "kind": "desktop",
        "canonicalTarget": "contentengine://desktop/bombbar",
        "space": "bombbar",
    }
    assert object_target == {
        "kind": "object",
        "canonicalTarget": "contentengine://object/file%3Abombbar-short-01",
        "objectRef": {"type": "content_object", "id": "file:bombbar-short-01"},
    }
    assert folder == {
        "kind": "folder",
        "canonicalTarget": "contentengine://folder/bombbar%3Ainbox",
        "objectRef": {"type": "folder", "id": "bombbar:inbox"},
    }
    assert ai == {
        "kind": "app",
        "canonicalTarget": "contentengine://app/ai?space=bombbar&tab=decisions",
        "appId": "ai",
        "space": "bombbar",
        "tab": "decisions",
    }
    assert review["canonicalTarget"] == (
        "contentengine://app/review?space=blacktiger&tab=mine"
    )
    assert settings == {
        "kind": "app",
        "canonicalTarget": "contentengine://app/settings?space=bombbar",
        "appId": "settings",
        "space": "bombbar",
        "tab": "",
    }


def test_internal_target_allowlist_rejects_ambiguous_arbitrary_and_secretish_forms() -> None:
    result = _run_node(
        """
        const invalid = [
          'https://example.com',
          'javascript:alert(1)',
          'contentengine://unknown/value',
          'contentengine://desktop/other',
          'contentengine://desktop/bombbar?tab=today',
          'contentengine://object/file%2Fchild',
          'contentengine://object/token-secret',
          'contentengine://folder/folder-1?space=bombbar',
          'contentengine://app/ai?tab=decisions',
          'contentengine://app/ai?space=other&tab=decisions',
          'contentengine://app/ai?space=bombbar&tab=unknown',
          'contentengine://app/ai?space=bombbar&tab=decisions&view=decisions',
          'contentengine://app/ai?space=bombbar&tab=decisions&tab=history',
          'contentengine://app/ai?space=bombbar&tab=decisions&token=secret',
          'contentengine://app/settings?space=bombbar&tab=profile',
          'contentengine://user:pass@app/ai?space=bombbar&tab=decisions',
          'contentengine://app/ai/extra?space=bombbar&tab=decisions',
          'contentengine://app/ai?space=bombbar&tab=decisions#fragment',
          'contentengine://app/AI?space=bombbar&tab=decisions',
          'contentengine://app/ai?space=bombbar&tab=Decisions',
        ];
        process.stdout.write(JSON.stringify(invalid.map((value) => (
          subject.normalizeWorkspaceInternalTarget(value) === null
        ))));
        """
    )
    assert all(result)


def test_object_ref_is_typed_exact_and_carries_no_serialized_business_object() -> None:
    result = _run_node(
        """
        const candidates = [
          { type: 'file', id: 'file:bombbar-short-01' },
          { type: 'smart-folder', id: 'smart:needs-decisions' },
          { type: 'process', id: 'process:upload:mp4-17' },
          { type: 'file', id: 'file:one', signedUrl: 'https://secret.example/x' },
          { type: 'file' },
          { id: 'file:one' },
          { type: 'unknown', id: 'file:one' },
          { type: 'file', id: 'https://secret.example/x' },
          { type: 'file', id: ' token:secret' },
          { type: 'file', id: 'file/child' },
        ];
        process.stdout.write(JSON.stringify(candidates.map((candidate) => (
          subject.normalizeWorkspaceObjectRef(candidate)
        ))));
        """
    )
    assert result[:3] == [
        {"type": "file", "id": "file:bombbar-short-01"},
        {"type": "smart_folder", "id": "smart:needs-decisions"},
        {"type": "process", "id": "process:upload:mp4-17"},
    ]
    assert result[3:] == [None] * 7


def test_context_matrix_targets_are_exact_and_file_shortcuts_are_not_generic_pins() -> None:
    result = _run_node(
        """
        const object = { kind: 'object', objectRef: { type: 'file', id: 'file:one' } };
        const project = { kind: 'object', objectRef: { type: 'project', id: 'project:bombbar' } };
        const folder = { kind: 'object', objectRef: { type: 'folder', id: 'folder:inbox' } };
        const desktop = { kind: 'internal', canonicalTarget: 'contentengine://desktop/bombbar' };
        const folderTarget = { kind: 'internal', canonicalTarget: 'contentengine://folder/folder:inbox' };
        process.stdout.write(JSON.stringify({
          open: subject.validateWorkspaceCommandTarget('object.open', object),
          projectFinder: subject.validateWorkspaceCommandTarget('finder.open-object', project),
          newDesktopFolder: subject.validateWorkspaceCommandTarget('object.create-folder', desktop),
          newChildFolder: subject.validateWorkspaceCommandTarget('object.create-folder', folderTarget),
          badCreateContext: subject.validateWorkspaceCommandTarget('object.create-folder', folder),
          legacyProjectPin: subject.validateWorkspaceCommandTarget('dock.pin-shortcut', project),
          genericFilePin: subject.validateWorkspaceCommandTarget('dock.pin-shortcut', object),
          dedicatedFilePin: subject.validateWorkspaceCommandTarget('dock.pin-file-shortcut', object),
          extraTargetField: subject.validateWorkspaceCommandTarget('object.open', {
            ...object,
            signedUrl: 'https://secret.example/file',
          }),
        }));
        """
    )
    for key in (
        "open",
        "projectFinder",
        "newDesktopFolder",
        "newChildFolder",
        "legacyProjectPin",
        "dedicatedFilePin",
    ):
        assert result[key]["ok"] is True
    assert result["badCreateContext"]["reason"] == "invalid_target"
    assert result["genericFilePin"]["reason"] == "target_type_not_allowed"
    assert result["extraTargetField"]["reason"] == "invalid_target"


def test_authority_states_block_denied_missing_stale_and_every_unknown_explicitly() -> None:
    result = _run_node(
        """
        const base = {
          gestureId: 'gesture:authority',
          source: 'notification',
          actionKey: 'object.open',
          target: { kind: 'object', objectRef: { type: 'file', id: 'file:one' } },
        };
        const authority = (permission, existence, freshness) => ({
          permission, existence, freshness,
        });
        const states = {
          denied: authority('denied', 'present', 'current'),
          permissionUnknown: authority('unknown', 'present', 'current'),
          missing: authority('allowed', 'missing', 'current'),
          existenceUnknown: authority('allowed', 'unknown', 'current'),
          stale: authority('allowed', 'present', 'stale'),
          freshnessUnknown: authority('allowed', 'present', 'unknown'),
          fresh: authority('allowed', 'present', 'current'),
        };
        process.stdout.write(JSON.stringify(Object.fromEntries(
          Object.entries(states).map(([key, value]) => [
            key,
            subject.resolveWorkspaceCommand({ ...base, authority: value }),
          ]),
        )));
        """
    )
    assert result["denied"]["reason"] == "permission_denied"
    assert result["permissionUnknown"]["reason"] == "permission_unknown"
    assert result["missing"]["reason"] == "target_missing"
    assert result["existenceUnknown"]["reason"] == "existence_unknown"
    assert result["stale"]["reason"] == "target_stale"
    assert result["freshnessUnknown"]["reason"] == "freshness_unknown"
    assert result["fresh"]["status"] == "ready"
    for key in result:
        if key == "fresh":
            continue
        assert result[key]["status"] == "blocked"
        assert result[key]["envelope"] is None
        assert result[key]["blockedAt"] == "target"


def test_notification_actions_require_exact_decision_process_and_object_targets() -> None:
    result = _run_node(
        """
        const fresh = { permission: 'allowed', existence: 'present', freshness: 'current' };
        const resolve = (gestureId, actionKey, target) => subject.resolveWorkspaceCommand({
          gestureId,
          source: 'notification',
          actionKey,
          target,
          authority: fresh,
        });
        process.stdout.write(JSON.stringify({
          decisions: resolve('notice:decision', 'ai.open-decisions', {
            kind: 'internal',
            canonicalTarget: 'contentengine://app/ai?space=bombbar&view=decisions',
          }),
          wrongAiTab: resolve('notice:wrong-tab', 'ai.open-decisions', {
            kind: 'internal',
            canonicalTarget: 'contentengine://app/ai?space=bombbar&tab=today',
          }),
          process: resolve('notice:process', 'process.open', {
            kind: 'object',
            objectRef: { type: 'process', id: 'process:upload:mp4-17' },
          }),
          processWithoutId: resolve('notice:process-missing', 'process.open', {
            kind: 'object', objectRef: { type: 'process', id: '' },
          }),
          review: resolve('notice:review', 'review.open-object', {
            kind: 'object', objectRef: { type: 'file', id: 'file:bombbar-short-01' },
          }),
          unknown: resolve('notice:unknown', 'paid.retry-generation', {
            kind: 'object', objectRef: { type: 'file', id: 'file:one' },
          }),
        }));
        """
    )
    assert result["decisions"]["status"] == "ready"
    assert result["decisions"]["envelope"]["target"]["canonicalTarget"] == (
        "contentengine://app/ai?space=bombbar&tab=decisions"
    )
    assert result["wrongAiTab"]["reason"] == "invalid_target"
    assert result["process"]["status"] == "ready"
    assert result["processWithoutId"]["reason"] == "invalid_target"
    assert result["review"]["status"] == "ready"
    assert result["unknown"] == {
        "ok": False,
        "status": "blocked",
        "actionKey": "paid.retry-generation",
        "reason": "unknown_action",
        "blockedAt": "registry",
        "envelope": None,
    }


def test_one_gesture_produces_one_deterministic_inert_command_envelope() -> None:
    result = _run_node(
        """
        const request = {
          gestureId: 'gesture:quick-look:01',
          source: 'keyboard',
          actionKey: 'quicklook.open',
          target: { kind: 'object', objectRef: { type: 'file', id: 'file:one' } },
          authority: { permission: 'allowed', existence: 'present', freshness: 'current' },
        };
        const before = JSON.stringify(request);
        const first = subject.resolveWorkspaceCommand(request);
        const second = subject.resolveWorkspaceCommand(request);
        const hostile = subject.resolveWorkspaceCommand({
          ...request,
          commands: ['quicklook.open', 'trash.move'],
          payload: { signedUrl: 'https://secret.example/file', paidConfirmation: true },
        });
        process.stdout.write(JSON.stringify({
          first,
          same: JSON.stringify(first) === JSON.stringify(second),
          inputUnchanged: before === JSON.stringify(request),
          frozen: Object.isFrozen(first)
            && Object.isFrozen(first.envelope)
            && Object.isFrozen(first.envelope.target)
            && Object.isFrozen(first.envelope.policy),
          hostile,
          encoded: JSON.stringify(first),
        }));
        """
    )
    first = result["first"]
    assert first["status"] == "ready"
    assert first["envelope"]["commandId"] == (
        "workspace-command:gesture:quick-look:01"
    )
    assert first["envelope"]["gestureId"] == "gesture:quick-look:01"
    assert first["envelope"]["actionKey"] == "quicklook.open"
    assert first["envelope"]["policy"] == {
        "dispatchCount": 1,
        "paidAction": False,
        "startsAnalysis": False,
        "startsGeneration": False,
        "requiresAuthoritativeRecheck": True,
        "requiresSeparateConfirmation": False,
        "decisionRequired": None,
        "effect": "preview",
        "navigation": "none",
    }
    assert result["same"] is True
    assert result["inputUnchanged"] is True
    assert result["frozen"] is True
    assert result["hostile"]["reason"] == "invalid_request"
    for forbidden in ("signedUrl", "secret.example", "paidConfirmation", "commands"):
        assert forbidden not in result["encoded"]


def test_drag_drop_maps_to_one_non_paid_command_and_cross_project_requires_decision() -> None:
    result = _run_node(
        """
        const fresh = { permission: 'allowed', existence: 'present', freshness: 'current' };
        const file = { type: 'file', id: 'file:one' };
        const folder = { type: 'folder', id: 'folder:research' };
        const project = { type: 'project', id: 'project:blacktiger' };
        const resolve = (gestureId, actionKey, target, authority = fresh) => (
          subject.resolveWorkspaceCommand({
            gestureId,
            source: 'drag_drop',
            actionKey,
            target,
            authority,
          })
        );
        process.stdout.write(JSON.stringify({
          move: resolve('drop:folder', 'object.move', {
            kind: 'object_destination', objectRef: file, destinationRef: folder,
          }, { target: fresh, destination: fresh }),
          wrongDestination: resolve('drop:wrong', 'object.move', {
            kind: 'object_destination', objectRef: file, destinationRef: project,
          }, { target: fresh, destination: fresh }),
          destinationDenied: resolve('drop:denied', 'object.move', {
            kind: 'object_destination', objectRef: file, destinationRef: folder,
          }, {
            target: fresh,
            destination: { permission: 'denied', existence: 'present', freshness: 'current' },
          }),
          projectDecision: resolve('drop:project', 'project.transfer.prepare', {
            kind: 'object_destination', objectRef: file, destinationRef: project,
          }, { target: fresh, destination: fresh }),
          research: resolve('drop:research', 'relation.add:research', {
            kind: 'object', objectRef: file,
          }),
          create: resolve('drop:create', 'relation.add:create', {
            kind: 'object', objectRef: file,
          }),
          review: resolve('drop:review', 'relation.add:review', {
            kind: 'object', objectRef: file,
          }),
          trash: resolve('drop:trash', 'trash.move', {
            kind: 'object', objectRef: file,
          }),
        }));
        """
    )
    assert result["move"]["status"] == "ready"
    assert result["wrongDestination"]["reason"] == "target_type_not_allowed"
    assert result["destinationDenied"]["reason"] == "permission_denied"
    assert result["destinationDenied"]["blockedAt"] == "destination"
    assert result["projectDecision"]["status"] == "ready"
    assert result["projectDecision"]["envelope"]["policy"]["decisionRequired"] == (
        "move_or_copy"
    )
    for key in ("move", "projectDecision", "research", "create", "review", "trash"):
        envelope = result[key]["envelope"]
        assert envelope["policy"]["dispatchCount"] == 1
        assert envelope["policy"]["paidAction"] is False
        assert envelope["policy"]["startsAnalysis"] is False
        assert envelope["policy"]["startsGeneration"] is False


def test_permanent_delete_only_requests_a_separate_confirmation() -> None:
    result = _run_node(
        """
        const resolved = subject.resolveWorkspaceCommand({
          gestureId: 'gesture:delete-permanent',
          source: 'context_menu',
          actionKey: 'trash.delete-permanent',
          target: { kind: 'object', objectRef: { type: 'file', id: 'file:trash-01' } },
          authority: { permission: 'allowed', existence: 'present', freshness: 'current' },
        });
        process.stdout.write(JSON.stringify(resolved));
        """
    )
    assert result["status"] == "ready"
    policy = result["envelope"]["policy"]
    assert policy["effect"] == "confirmation_request"
    assert policy["requiresSeparateConfirmation"] is True
    assert policy["paidAction"] is False
    assert policy["startsAnalysis"] is False
    assert policy["startsGeneration"] is False


def test_invalid_source_and_invalid_authority_are_explicitly_blocked() -> None:
    result = _run_node(
        """
        const base = {
          gestureId: 'gesture:source',
          actionKey: 'trash.restore',
          target: { kind: 'object', objectRef: { type: 'file', id: 'file:trash-01' } },
        };
        process.stdout.write(JSON.stringify({
          source: subject.resolveWorkspaceCommand({
            ...base,
            source: 'notification',
            authority: { permission: 'allowed', existence: 'present', freshness: 'current' },
          }),
          absentAuthority: subject.resolveWorkspaceCommand({
            ...base,
            source: 'context_menu',
          }),
          authorityWithToken: subject.resolveWorkspaceCommand({
            ...base,
            source: 'context_menu',
            authority: {
              permission: 'allowed',
              existence: 'present',
              freshness: 'current',
              accessToken: 'secret',
            },
          }),
        }));
        """
    )
    assert result["source"]["reason"] == "source_not_allowed"
    assert result["source"]["blockedAt"] == "source"
    assert result["absentAuthority"]["reason"] == "invalid_authority"
    assert result["authorityWithToken"]["reason"] == "invalid_authority"
