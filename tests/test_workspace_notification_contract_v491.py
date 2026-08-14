from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "workspace-notification-contract.js"
SOURCE = MODULE.read_text(encoding="utf-8")


def _run_node(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the Notification Center contract")
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


def test_contract_is_pure_and_exposes_bounded_frozen_vocabularies() -> None:
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
        "dispatchEvent(",
        "Date.now(",
        "workspace-command-registry.js\"",
        "workspace-command-registry.js'",
    ):
        assert forbidden not in SOURCE

    result = _run_node(
        """
        process.stdout.write(JSON.stringify({
          version: subject.WORKSPACE_NOTIFICATION_CONTRACT_VERSION,
          readVersion: subject.WORKSPACE_NOTIFICATION_READ_STATE_VERSION,
          types: subject.WORKSPACE_NOTIFICATION_TYPES,
          severities: subject.WORKSPACE_NOTIFICATION_SEVERITIES,
          filters: subject.WORKSPACE_NOTIFICATION_FILTERS,
          actions: subject.WORKSPACE_NOTIFICATION_ACTION_KEYS,
          actionStates: subject.WORKSPACE_NOTIFICATION_ACTION_STATES,
          frozen: [
            subject.WORKSPACE_NOTIFICATION_TYPES,
            subject.WORKSPACE_NOTIFICATION_SEVERITIES,
            subject.WORKSPACE_NOTIFICATION_FILTERS,
            subject.WORKSPACE_NOTIFICATION_ACTION_KEYS,
            subject.WORKSPACE_NOTIFICATION_ACTION_STATES,
          ].every(Object.isFrozen),
          exports: [
            typeof subject.normalizeWorkspaceNotification,
            typeof subject.normalizeWorkspaceNotificationFeed,
            typeof subject.workspaceNotificationMatchesRecipient,
            typeof subject.isWorkspaceNotificationExpired,
            typeof subject.describeWorkspaceNotificationAction,
            typeof subject.evaluateWorkspaceNotificationAction,
            typeof subject.filterWorkspaceNotificationItems,
            typeof subject.countWorkspaceNotificationItems,
            typeof subject.formatWorkspaceNotificationBadge,
            typeof subject.applyWorkspaceNotificationReadTransition,
          ],
        }));
        """
    )
    assert result == {
        "version": "4.9.1",
        "readVersion": "contentengine-notification-read-v4.9.1",
        "types": [
            "action_required",
            "mention",
            "assignment",
            "process_complete",
            "warning",
            "error",
            "access_change",
            "system_info",
        ],
        "severities": ["neutral", "info", "success", "warning", "danger"],
        "filters": [
            "all",
            "unread",
            "action_required",
            "mentions",
            "processes",
            "system",
        ],
        "actions": [
            "ai.open-decisions",
            "process.open",
            "review.open-object",
            "object.open",
        ],
        "actionStates": ["none", "inert", "blocked"],
        "frozen": True,
        "exports": ["function"] * 10,
    }


def test_schema_normalizes_legacy_system_and_snake_case_without_retaining_payload() -> None:
    result = _run_node(
        """
        const normalized = subject.normalizeWorkspaceNotification({
          notification_id: "notice-system-1",
          organization_id: "org-1",
          recipient_user_id: "user-1",
          recipient_role_id: "role-owner",
          recipient_role_ids: ["role-editor", "role-owner", "role-editor"],
          dedupe_key: "system:release-491",
          type: "system",
          severity: "neutral",
          source_section: "  System  ",
          title: "  Обновление системы  ",
          body: "  Доступна новая версия  ",
          created_at: "2026-08-13T09:00:00+03:00",
          expires_at: null,
          resolved_at: "2026-08-13T10:00:00+03:00",
          requires_action: false,
          project_id: "project-1",
          object_id: "object-1",
          process_id: "process-1",
          action_key: "object.open",
          expired: false,
          arbitrary: { nested: "not retained" },
        });
        process.stdout.write(JSON.stringify(normalized));
        """
    )
    assert result["ok"] is True
    assert result["legacyExpired"] is False
    assert result["issues"] == []
    assert result["notification"] == {
        "notificationId": "notice-system-1",
        "organizationId": "org-1",
        "recipientUserId": "user-1",
        "recipientRoleId": "role-owner",
        "recipientRoleIds": ["role-editor", "role-owner"],
        "dedupeKey": "system:release-491",
        "type": "system_info",
        "severity": "neutral",
        "sourceSection": "System",
        "title": "Обновление системы",
        "body": "Доступна новая версия",
        "createdAt": "2026-08-13T06:00:00.000Z",
        "expiresAt": None,
        "resolvedAt": "2026-08-13T07:00:00.000Z",
        "requiresAction": False,
        "projectId": "project-1",
        "objectId": "object-1",
        "processId": "process-1",
        "actionKey": "object.open",
    }
    encoded = json.dumps(result, ensure_ascii=False)
    assert "arbitrary" not in encoded
    assert "not retained" not in encoded


def test_invalid_schema_severity_matrix_and_ambiguous_aliases_are_rejected() -> None:
    result = _run_node(
        """
        const base = {
          notificationId: "notice-1",
          type: "error",
          severity: "danger",
          sourceSection: "Processes",
          title: "Ошибка",
          body: "Не удалось обработать объект",
          createdAt: "2026-08-13T09:00:00Z",
          requiresAction: true,
        };
        const cases = {
          nonRecord: subject.normalizeWorkspaceNotification([]),
          badType: subject.normalizeWorkspaceNotification({ ...base, type: "heartbeat" }),
          badSeverity: subject.normalizeWorkspaceNotification({ ...base, severity: "green" }),
          wrongTone: subject.normalizeWorkspaceNotification({ ...base, severity: "success" }),
          wrongAction: subject.normalizeWorkspaceNotification({ ...base, requiresAction: false }),
          ambiguous: subject.normalizeWorkspaceNotification({
            ...base, notification_id: "different",
          }),
          badTime: subject.normalizeWorkspaceNotification({ ...base, createdAt: "yesterday" }),
          emptyRoles: subject.normalizeWorkspaceNotification({ ...base, recipientRoleIds: [] }),
        };
        process.stdout.write(JSON.stringify(cases));
        """
    )
    assert result["nonRecord"]["issues"] == ["record_invalid"]
    assert "type_invalid" in result["badType"]["issues"]
    assert "severity_invalid" in result["badSeverity"]["issues"]
    assert "severity_type_mismatch" in result["wrongTone"]["issues"]
    assert "requires_action_type_mismatch" in result["wrongAction"]["issues"]
    assert "ambiguous_notificationId" in result["ambiguous"]["issues"]
    assert "created_at_invalid" in result["badTime"]["issues"]
    assert "recipient_roles_invalid" in result["emptyRoles"]["issues"]
    assert all(case["ok"] is False for case in result.values())


def test_sensitive_payloads_and_secret_like_values_are_rejected_before_admission() -> None:
    result = _run_node(
        """
        const base = {
          notificationId: "notice-secret",
          type: "warning",
          severity: "warning",
          sourceSection: "Review",
          title: "Нужно действие",
          body: "Откройте объект",
          createdAt: "2026-08-13T09:00:00Z",
          requiresAction: true,
          actionKey: "object.open",
          objectId: "object-1",
        };
        const cases = [
          { ...base, accessToken: "private-token" },
          { ...base, actionPayload: { objectId: "object-1" } },
          { ...base, nested: { signed_url: "https://storage.example/x" } },
          { ...base, rawData: { prompt: "private prompt" } },
          { ...base, title: "Bearer private-token" },
          { ...base, body: "https://example.test/?access_token=private" },
        ].map(subject.normalizeWorkspaceNotification);
        const feed = subject.normalizeWorkspaceNotificationFeed([
          base,
          { ...base, notificationId: "notice-secret-2", providerPayload: { ok: true } },
        ], {
          recipient: { organizationId: "org-1", userId: "user-1" },
          now: "2026-08-13T10:00:00Z",
        });
        process.stdout.write(JSON.stringify({ cases, feed }));
        """
    )
    assert all(case["ok"] is False for case in result["cases"])
    assert all(
        "sensitive_payload_rejected" in case["issues"]
        for case in result["cases"]
    )
    assert [item["notification"]["notificationId"] for item in result["feed"]["items"]] == [
        "notice-secret"
    ]
    assert result["feed"]["rejected"] == [
        {"index": 1, "issues": ["sensitive_payload_rejected"]}
    ]


def test_recipient_admission_requires_exact_org_user_and_role_intersection() -> None:
    result = _run_node(
        """
        const base = {
          notificationId: "base",
          type: "mention",
          severity: "info",
          sourceSection: "Review",
          title: "Вас упомянули",
          body: "Комментарий",
          createdAt: "2026-08-13T09:00:00Z",
          requiresAction: false,
        };
        const make = (id, patch) => ({ ...base, notificationId: id, ...patch });
        const context = { organizationId: "org-1", userId: "user-1", roleIds: ["editor"] };
        const events = [
          make("global", {}),
          make("org", { organizationId: "org-1" }),
          make("user", { recipientUserId: "user-1" }),
          make("role-one", { recipientRoleId: "editor" }),
          make("role-many", { recipientRoleIds: ["owner", "editor"] }),
          make("wrong-org", { organizationId: "org-2" }),
          make("wrong-user", { recipientUserId: "user-2" }),
          make("wrong-role", { recipientRoleIds: ["owner", "manager"] }),
          make("org-and-role", { organizationId: "org-1", recipientRoleId: "editor" }),
          make("role-fields-conflict", { recipientRoleId: "owner", recipientRoleIds: ["editor"] }),
        ];
        const feed = subject.normalizeWorkspaceNotificationFeed(events, {
          recipient: context,
          now: "2026-08-13T10:00:00Z",
        });
        process.stdout.write(JSON.stringify({
          feed,
          direct: events.map((event) => subject.workspaceNotificationMatchesRecipient(event, context)),
          missingIdentity: subject.workspaceNotificationMatchesRecipient(events[0], {}),
        }));
        """
    )
    assert result["direct"] == [True, True, True, True, True, False, False, False, True, False]
    assert result["missingIdentity"] is False
    assert [item["notification"]["notificationId"] for item in result["feed"]["items"]] == [
        "global",
        "org",
        "org-and-role",
        "role-many",
        "role-one",
        "user",
    ]
    assert result["feed"]["excluded"] == [
        {"notificationId": "wrong-org", "reason": "wrong_recipient"},
        {"notificationId": "wrong-user", "reason": "wrong_recipient"},
        {"notificationId": "wrong-role", "reason": "wrong_recipient"},
        {"notificationId": "role-fields-conflict", "reason": "wrong_recipient"},
    ]


def test_expiry_legacy_expired_and_boundary_never_enter_feed_or_badge() -> None:
    result = _run_node(
        """
        const base = {
          type: "system_info",
          severity: "neutral",
          sourceSection: "System",
          title: "Система",
          body: "Сообщение",
          createdAt: "2026-08-13T08:00:00Z",
          requiresAction: false,
        };
        const events = [
          { ...base, notificationId: "live" },
          { ...base, notificationId: "future", expiresAt: "2026-08-13T10:00:00.001Z" },
          { ...base, notificationId: "boundary", expiresAt: "2026-08-13T10:00:00Z" },
          { ...base, notificationId: "past", expiresAt: "2026-08-13T09:59:59Z" },
          { ...base, notificationId: "legacy", expired: true },
        ];
        const feed = subject.normalizeWorkspaceNotificationFeed(events, {
          recipient: { organizationId: "org-1", userId: "user-1" },
          now: "2026-08-13T10:00:00Z",
        });
        const counts = subject.countWorkspaceNotificationItems(feed.items);
        process.stdout.write(JSON.stringify({
          feed,
          counts,
          expired: events.map((item) => subject.isWorkspaceNotificationExpired(item, "2026-08-13T10:00:00Z")),
        }));
        """
    )
    assert result["expired"] == [False, False, True, True, True]
    assert [item["notification"]["notificationId"] for item in result["feed"]["items"]] == [
        "future",
        "live",
    ]
    assert result["counts"]["all"] == 2
    assert result["counts"]["unread"] == 2
    assert result["feed"]["excluded"] == [
        {"notificationId": "boundary", "reason": "expired"},
        {"notificationId": "legacy", "reason": "expired"},
        {"notificationId": "past", "reason": "expired"},
    ]


def test_dedupe_is_order_independent_newer_wins_and_duplicate_id_is_one_row() -> None:
    result = _run_node(
        """
        const base = {
          type: "warning",
          severity: "warning",
          sourceSection: "Processes",
          body: "Состояние процесса",
          requiresAction: true,
          actionKey: "process.open",
          processId: "process-1",
        };
        const events = [
          { ...base, notificationId: "same-id", dedupeKey: "process:other", title: "Старый ID", createdAt: "2026-08-13T08:00:00Z" },
          { ...base, notificationId: "same-id", dedupeKey: "process:other", title: "Новый ID", createdAt: "2026-08-13T09:30:00Z" },
          { ...base, notificationId: "running", dedupeKey: "process:1", title: "В работе", createdAt: "2026-08-13T09:00:00Z" },
          { ...base, notificationId: "completed", dedupeKey: "process:1", type: "process_complete", severity: "success", requiresAction: false, title: "Завершено", createdAt: "2026-08-13T10:00:00Z" },
          { ...base, notificationId: "tie-b", dedupeKey: "tie", title: "B", createdAt: "2026-08-13T11:00:00Z" },
          { ...base, notificationId: "tie-a", dedupeKey: "tie", title: "A", createdAt: "2026-08-13T11:00:00Z" },
        ];
        const options = {
          recipient: { organizationId: "org-1", userId: "user-1" },
          now: "2026-08-13T12:00:00Z",
        };
        const forward = subject.normalizeWorkspaceNotificationFeed(events, options);
        const reverse = subject.normalizeWorkspaceNotificationFeed([...events].reverse(), options);
        const project = (feed) => feed.items.map((item) => ({
          id: item.notification.notificationId,
          title: item.notification.title,
        }));
        process.stdout.write(JSON.stringify({
          forward: project(forward),
          reverse: project(reverse),
          dedupe: forward.dedupe,
        }));
        """
    )
    assert result["forward"] == result["reverse"]
    assert result["forward"] == [
        {"id": "tie-a", "title": "A"},
        {"id": "completed", "title": "Завершено"},
        {"id": "same-id", "title": "Новый ID"},
    ]
    assert result["dedupe"] == [
        {
            "notificationId": "tie-b",
            "reason": "replaced_by_newer_dedupe_key",
            "winnerNotificationId": "tie-a",
        },
        {
            "notificationId": "running",
            "reason": "replaced_by_newer_dedupe_key",
            "winnerNotificationId": "completed",
        },
        {
            "notificationId": "same-id",
            "reason": "duplicate_notification_id",
            "winnerNotificationId": "same-id",
        },
    ]


def test_filters_counts_system_alias_and_badge_zero_exact_and_99_plus() -> None:
    result = _run_node(
        """
        const base = {
          severity: "info",
          sourceSection: "Review",
          title: "Notice",
          body: "Body",
          createdAt: "2026-08-13T09:00:00Z",
          requiresAction: false,
        };
        const events = [
          { ...base, notificationId: "mention", type: "mention" },
          { ...base, notificationId: "assignment", type: "assignment", requiresAction: true },
          { ...base, notificationId: "process", type: "process_complete", severity: "success", sourceSection: "Processes" },
          { ...base, notificationId: "system", type: "system", severity: "neutral", sourceSection: "System" },
          { ...base, notificationId: "access", type: "access_change", severity: "neutral", sourceSection: "System" },
          { ...base, notificationId: "warning", type: "warning", severity: "warning", requiresAction: true },
          { ...base, notificationId: "resolved", type: "warning", severity: "warning", requiresAction: true, resolvedAt: "2026-08-13T09:30:00Z" },
        ];
        const readState = subject.createWorkspaceNotificationReadState(
          { organizationId: "org-1", userId: "user-1" },
          ["mention", "system"],
        );
        const feed = subject.normalizeWorkspaceNotificationFeed(events, {
          recipient: { organizationId: "org-1", userId: "user-1" },
          readState,
          now: "2026-08-13T10:00:00Z",
        });
        const filtered = Object.fromEntries(subject.WORKSPACE_NOTIFICATION_FILTERS.map((filter) => [
          filter,
          subject.filterWorkspaceNotificationItems(feed.items, filter).map((item) => item.notification.notificationId),
        ]));
        process.stdout.write(JSON.stringify({
          filtered,
          counts: subject.countWorkspaceNotificationItems(feed.items),
          badge0: subject.formatWorkspaceNotificationBadge(0),
          badge42: subject.formatWorkspaceNotificationBadge(42),
          badge100: subject.formatWorkspaceNotificationBadge(100),
          badgeNegative: subject.formatWorkspaceNotificationBadge(-3),
        }));
        """
    )
    assert result["filtered"] == {
        "all": ["access", "assignment", "mention", "process", "resolved", "system", "warning"],
        "unread": ["access", "assignment", "process", "resolved", "warning"],
        "action_required": ["assignment", "warning"],
        "mentions": ["mention"],
        "processes": ["process"],
        "system": ["access", "system"],
    }
    assert result["counts"] == {
        "all": 7,
        "unread": 5,
        "actionRequired": 2,
        "mentions": 1,
        "processes": 1,
        "system": 2,
    }
    assert result["badge0"] == {
        "count": 0,
        "hidden": True,
        "text": "",
        "ariaLabel": "Уведомления",
    }
    assert result["badge42"] == {
        "count": 42,
        "hidden": False,
        "text": "42",
        "ariaLabel": "Уведомления · 42 непрочитанных",
    }
    assert result["badge100"] == {
        "count": 100,
        "hidden": False,
        "text": "99+",
        "ariaLabel": "Уведомления · 100 непрочитанных",
    }
    assert result["badgeNegative"] == result["badge0"]


def test_action_descriptors_are_inert_exact_and_unknown_or_missing_targets_block() -> None:
    result = _run_node(
        """
        const base = {
          notificationId: "notice",
          type: "action_required",
          severity: "warning",
          sourceSection: "AI",
          title: "Нужно решение",
          body: "Откройте актуальный контекст",
          createdAt: "2026-08-13T09:00:00Z",
          requiresAction: true,
        };
        const cases = {
          noAction: subject.describeWorkspaceNotificationAction({ ...base }),
          unknown: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "paid.retry-generation" }),
          decisions: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "ai.open-decisions", projectId: "project-1" }),
          processMissing: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "process.open" }),
          process: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "process.open", processId: "process-1" }),
          objectMissing: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "object.open" }),
          object: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "object.open", objectId: "object-1", projectId: "project-1" }),
          review: subject.describeWorkspaceNotificationAction({ ...base, actionKey: "review.open-object", objectId: "object-2" }),
        };
        process.stdout.write(JSON.stringify(cases));
        """
    )
    assert result["noAction"]["state"] == "blocked"
    assert result["noAction"]["reason"] == "action_key_required"
    assert result["unknown"]["state"] == "blocked"
    assert result["unknown"]["reason"] == "unknown_action"
    assert result["unknown"]["actionKey"] == "paid.retry-generation"
    assert result["decisions"]["targetIntent"] == {
        "kind": "internal",
        "appId": "ai",
        "tab": "decisions",
        "projectId": "project-1",
    }
    assert result["processMissing"]["reason"] == "process_id_required"
    assert result["process"]["targetIntent"] == {
        "kind": "process",
        "processId": "process-1",
    }
    assert result["objectMissing"]["reason"] == "object_id_required"
    assert result["object"]["targetIntent"] == {
        "kind": "object",
        "objectId": "object-1",
        "projectId": "project-1",
    }
    assert result["review"]["targetIntent"] == {
        "kind": "object",
        "objectId": "object-2",
    }
    for key in ("decisions", "process", "object", "review"):
        assert result[key]["state"] == "inert"
        assert result[key]["executable"] is False
        assert result[key]["executionOwner"] == "workspace-command-registry"


def test_action_recheck_order_blocks_wrong_recipient_expired_stale_permission_and_target() -> None:
    result = _run_node(
        """
        const notice = {
          notificationId: "notice-action",
          organizationId: "org-1",
          recipientUserId: "user-1",
          recipientRoleId: "editor",
          type: "error",
          severity: "danger",
          sourceSection: "Processes",
          title: "Ошибка обработки",
          body: "Откройте задачу",
          createdAt: "2026-08-13T09:00:00Z",
          expiresAt: "2026-08-14T00:00:00Z",
          requiresAction: true,
          actionKey: "process.open",
          processId: "process-1",
        };
        const current = {
          recipient: { organizationId: "org-1", userId: "user-1", roleIds: ["editor"] },
          now: "2026-08-13T10:00:00Z",
          recordState: "current",
          permissionState: "allowed",
          targetState: "current",
        };
        const cases = {
          noContext: subject.evaluateWorkspaceNotificationAction(notice),
          wrongRecipient: subject.evaluateWorkspaceNotificationAction(notice, {
            ...current, recipient: { organizationId: "org-1", userId: "user-2", roleIds: ["editor"] },
          }),
          expired: subject.evaluateWorkspaceNotificationAction(notice, { ...current, now: "2026-08-14T00:00:00Z" }),
          staleRecord: subject.evaluateWorkspaceNotificationAction(notice, { ...current, recordState: "stale" }),
          denied: subject.evaluateWorkspaceNotificationAction(notice, { ...current, permissionState: "revoked" }),
          staleTarget: subject.evaluateWorkspaceNotificationAction(notice, { ...current, targetState: "missing" }),
          ready: subject.evaluateWorkspaceNotificationAction(notice, current),
        };
        process.stdout.write(JSON.stringify(cases));
        """
    )
    assert result["noContext"]["reason"] == "recipient_recheck_required"
    assert result["wrongRecipient"]["reason"] == "wrong_recipient"
    assert result["expired"]["reason"] == "expired"
    assert result["staleRecord"]["reason"] == "stale_notification"
    assert result["denied"]["reason"] == "permission_denied"
    assert result["staleTarget"]["reason"] == "stale_target"
    assert result["ready"]["state"] == "inert"
    assert result["ready"]["reason"] == "external_command_validation_required"
    assert all(value["executable"] is False for value in result.values())


def test_read_state_is_org_user_version_scoped_and_never_pruned_by_current_page() -> None:
    result = _run_node(
        """
        const scope = { organizationId: "org-1", userId: "user-1" };
        const original = subject.createWorkspaceNotificationReadState(scope, ["off-page", "visible-read"]);
        const accepted = subject.normalizeWorkspaceNotificationReadState(original, scope);
        const wrongUser = subject.normalizeWorkspaceNotificationReadState(original, { ...scope, userId: "user-2" });
        const wrongOrg = subject.normalizeWorkspaceNotificationReadState(original, { ...scope, organizationId: "org-2" });
        const wrongVersion = subject.normalizeWorkspaceNotificationReadState({ ...original, version: "old" }, scope);
        const feed = subject.normalizeWorkspaceNotificationFeed([
          {
            notificationId: "visible-unread", organizationId: "org-1", recipientUserId: "user-1",
            type: "system_info", severity: "neutral", sourceSection: "System", title: "A", body: "B",
            createdAt: "2026-08-13T09:00:00Z", requiresAction: false,
          },
          {
            notificationId: "visible-read", organizationId: "org-1", recipientUserId: "user-1",
            type: "system_info", severity: "neutral", sourceSection: "System", title: "A", body: "B",
            createdAt: "2026-08-13T08:00:00Z", requiresAction: false,
          },
        ], { recipient: scope, readState: original, now: "2026-08-13T10:00:00Z" });
        process.stdout.write(JSON.stringify({ original, accepted, wrongUser, wrongOrg, wrongVersion, feed }));
        """
    )
    assert result["accepted"]["ok"] is True
    assert result["accepted"]["state"]["readNotificationIds"] == ["off-page", "visible-read"]
    assert result["wrongUser"]["reason"] == "read_scope_mismatch"
    assert result["wrongUser"]["state"]["scope"]["userId"] == "user-2"
    assert result["wrongUser"]["state"]["readNotificationIds"] == []
    assert result["wrongOrg"]["reason"] == "read_scope_mismatch"
    assert result["wrongVersion"]["reason"] == "read_schema_mismatch"
    assert result["feed"]["readState"]["readNotificationIds"] == [
        "off-page",
        "visible-read",
    ]
    item_state = {
        item["notification"]["notificationId"]: item["unread"]
        for item in result["feed"]["items"]
    }
    assert item_state == {"visible-unread": True, "visible-read": False}


def test_read_transitions_are_explicit_visible_scoped_and_failed_action_stays_unread() -> None:
    result = _run_node(
        """
        const scope = { organizationId: "org-1", userId: "user-1" };
        const original = subject.createWorkspaceNotificationReadState(scope, ["off-page"]);
        const panelOpen = original;
        const notice = (notificationId, recipientUserId = "user-1") => ({
          notificationId, organizationId: "org-1", recipientUserId,
          type: "action_required", severity: "warning", sourceSection: "AI", title: "A", body: "B",
          createdAt: "2026-08-13T09:00:00Z", requiresAction: true,
          actionKey: "ai.open-decisions", projectId: "project-1",
        });
        const plainNotice = (notificationId, recipientUserId = "user-1") => ({
          notificationId, organizationId: "org-1", recipientUserId,
          type: "system_info", severity: "neutral", sourceSection: "System", title: "A", body: "B",
          createdAt: "2026-08-13T09:00:00Z", requiresAction: false,
        });
        const failed = subject.applyWorkspaceNotificationReadTransition(original, {
          type: "action_result", notification: notice("failed"), outcome: "stale",
        }, scope);
        const blocked = subject.applyWorkspaceNotificationReadTransition(original, {
          type: "action_result", notification: notice("blocked"), outcome: "blocked",
        }, scope);
        const successful = subject.applyWorkspaceNotificationReadTransition(original, {
          type: "action_result", notification: notice("opened"), outcome: "success",
          exactTargetValidated: true, commandSucceeded: true,
        }, scope);
        const premature = subject.applyWorkspaceNotificationReadTransition(original, {
          type: "action_result", notification: notice("premature"), outcome: "success",
          exactTargetValidated: false, commandSucceeded: true,
        }, scope);
        const nonActionSuccess = subject.applyWorkspaceNotificationReadTransition(original, {
          type: "action_result", notification: plainNotice("not-actionable"), outcome: "success",
          exactTargetValidated: true, commandSucceeded: true,
        }, scope);
        const explicit = subject.applyWorkspaceNotificationReadTransition(successful.state, {
          type: "explicit_read", notification: plainNotice("one"),
        }, scope);
        const explicitForeign = subject.applyWorkspaceNotificationReadTransition(successful.state, {
          type: "explicit_read", notification: plainNotice("foreign-notice", "user-2"),
        }, scope);
        const visibleFeed = subject.normalizeWorkspaceNotificationFeed([
          {
            notificationId: "filtered-a", organizationId: "org-1", recipientUserId: "user-1",
            type: "warning", severity: "warning", sourceSection: "Review", title: "A", body: "B",
            createdAt: "2026-08-13T09:00:00Z", requiresAction: true,
          },
          {
            notificationId: "filtered-b", organizationId: "org-1", recipientUserId: "user-1",
            type: "assignment", severity: "info", sourceSection: "Review", title: "A", body: "B",
            createdAt: "2026-08-13T08:00:00Z", requiresAction: true,
          },
          {
            notificationId: "filtered-other", organizationId: "org-1", recipientUserId: "user-2",
            type: "assignment", severity: "info", sourceSection: "Review", title: "A", body: "B",
            createdAt: "2026-08-13T08:00:00Z", requiresAction: true,
          },
        ], { recipient: scope, now: "2026-08-13T10:00:00Z" });
        const visible = subject.applyWorkspaceNotificationReadTransition(explicit.state, {
          type: "mark_visible", items: visibleFeed.items, filter: "action_required",
          now: "2026-08-13T10:00:00Z",
        }, scope);
        const foreign = subject.applyWorkspaceNotificationReadTransition(original, {
          type: "explicit_read", notificationId: "foreign-attempt",
        }, { organizationId: "org-1", userId: "user-2" });
        process.stdout.write(JSON.stringify({ panelOpen, failed, blocked, premature, nonActionSuccess, successful, explicit, explicitForeign, visible, foreign }));
        """
    )
    assert result["panelOpen"]["readNotificationIds"] == ["off-page"]
    assert result["failed"]["changed"] is False
    assert result["failed"]["reason"] == "action_not_successful"
    assert result["failed"]["state"]["readNotificationIds"] == ["off-page"]
    assert result["blocked"]["state"]["readNotificationIds"] == ["off-page"]
    assert result["premature"]["state"]["readNotificationIds"] == ["off-page"]
    assert result["nonActionSuccess"]["ok"] is False
    assert result["nonActionSuccess"]["reason"] == "action_not_actionable"
    assert result["nonActionSuccess"]["state"]["readNotificationIds"] == ["off-page"]
    assert result["explicitForeign"]["ok"] is False
    assert result["explicitForeign"]["reason"] == "wrong_recipient"
    assert result["explicitForeign"]["state"]["readNotificationIds"] == ["off-page", "opened"]
    assert result["successful"]["state"]["readNotificationIds"] == ["off-page", "opened"]
    assert result["explicit"]["state"]["readNotificationIds"] == ["off-page", "one", "opened"]
    assert result["visible"]["state"]["readNotificationIds"] == [
        "filtered-a",
        "filtered-b",
        "off-page",
        "one",
        "opened",
    ]
    assert result["foreign"]["ok"] is False
    assert result["foreign"]["reason"] == "read_scope_mismatch"
    assert result["foreign"]["state"]["scope"]["userId"] == "user-2"
    assert result["foreign"]["state"]["readNotificationIds"] == []
