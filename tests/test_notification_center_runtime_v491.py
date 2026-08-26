from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
BASE_MIGRATION = ROOT / "supabase/migrations/202608130001_notification_center_v491.sql"
VALIDATOR_MIGRATION = (
    ROOT / "supabase/migrations/202608130005_notification_action_validation_v491.sql"
)
PGTAP = ROOT / "supabase/tests/notification_action_validation_v491_test.sql"
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"
SHELL = ROOT / "web/app/workspace-os-v4.js"
REGISTRY = ROOT / "web/app/workspace-command-registry.js"
FIXTURE = ROOT / "tests/fixtures/workspace_notification_center_runtime_v491_harness.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sql_function(source: str, signature: str) -> str:
    occurrence = source.index(signature)
    start = source.rfind("create or replace function", 0, occurrence)
    assert start >= 0
    match = re.search(r"\$function\$(.*?)\$function\$;", source[start:], re.DOTALL)
    assert match is not None
    return source[start : start + match.end()]


def _js_region(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start + len(start_marker))
    return source[start:end]


def test_additive_validator_and_pgtap_parse_without_replacing_feed_owner() -> None:
    base = _read(BASE_MIGRATION)
    migration = _read(VALIDATOR_MIGRATION)
    pgtap = _read(PGTAP)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert migration.lstrip().casefold().startswith("begin;")
    assert migration.rstrip().casefold().endswith("commit;")
    assert pgtap.lstrip().casefold().startswith("begin;")
    assert pgtap.rstrip().casefold().endswith("rollback;")
    assert "select plan(31);" in pgtap
    assertion_count = sum(
        len(re.findall(rf"(?im)^select\s+{name}\s*\(", pgtap))
        for name in ("has_function", "is", "ok", "matches", "unlike")
    )
    assert assertion_count == 31
    assert "creator_notification_center" in base
    assert "creator_mark_visible_notifications_read" in base
    assert "create table" not in migration.casefold()
    assert "creator_notification_center" not in migration
    assert "creator_mark_visible_notifications_read" not in migration


def test_validator_reloads_recipient_role_expiry_project_and_typed_target() -> None:
    source = _read(VALIDATOR_MIGRATION)
    validator = _sql_function(source, "public.creator_validate_notification_action(")

    for token in (
        "notification.organization_id = organization_id_value",
        "notification.recipient_id = user_id_value",
        "notification_row.contract_version <> 491",
        "notification_row.expires_at <= now()",
        "actor_role_value = any(notification_row.recipient_role_ids)",
        "notification_row.action_key is distinct from action_key_value",
        "notification_row.project_id is distinct from project_id_value",
        "notification_row.object_id is distinct from object_id_value",
        "notification_row.process_id is distinct from process_id_value",
        "workspace_project_access_allowed(",
        "content_factory.media_objects",
        "content_factory.generation_jobs",
        "content_factory.content_review_runs",
        "content_factory.placements",
    ):
        assert token in validator
    for action in (
        "ai.open-decisions",
        "process.open",
        "review.open-object",
        "object.open",
    ):
        assert f"'{action}'" in validator
    for reason in (
        "notification_unavailable",
        "legacy_action_unsupported",
        "expired",
        "permission_denied",
        "stale_notification",
        "stale_target",
        "target_ambiguous",
        "notification_action_target_unsupported",
    ):
        assert f"'{reason}'" in validator
    assert "job.mode = 'real'" not in validator
    assert "job.provider = 'runway'" not in validator


def test_validator_returns_only_closed_command_descriptor_and_never_mutates() -> None:
    validator = _sql_function(
        _read(VALIDATOR_MIGRATION),
        "public.creator_validate_notification_action(",
    )
    lowered = validator.casefold()

    assert "'command', jsonb_build_object(" in validator
    assert "'permission', 'allowed'" in validator
    assert "'existence', 'present'" in validator
    assert "'freshness', 'current'" in validator
    assert "'read_mutated', false" in validator
    assert "'paid_action', false" in validator
    assert "'starts_analysis', false" in validator
    assert "'starts_generation', false" in validator
    assert "'arbitrary_url_returned', false" in validator
    assert "deep_link" not in lowered
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "update content_factory.user_notifications" not in lowered
    assert "insert into" not in lowered
    assert "delete from" not in lowered


def test_supabase_api_is_the_only_three_rpc_transport_boundary() -> None:
    source = _read(API)
    assert 'notificationCenter: "creator_notification_center"' in source
    assert (
        'validateNotificationAction: "creator_validate_notification_action"'
        in source
    )
    assert (
        'markVisibleNotificationsRead: "creator_mark_visible_notifications_read"'
        in source
    )
    assert "notificationCenter(options = {})" in source
    assert "validateNotificationAction(intent = {})" in source
    assert "markVisibleNotificationsRead(notificationIds, filter = \"all\")" in source
    assert "return this.call(RPC.notificationCenter, this.withOrganization(payload))" in source
    assert "return this.call(RPC.validateNotificationAction, this.withOrganization({" in source
    assert "return this.mutate(RPC.markVisibleNotificationsRead, {" in source
    assert "all_unread" not in _js_region(
        source,
        "markVisibleNotificationsRead(notificationIds",
        "trainingProgress(moduleCode",
    )


def test_app_bridge_uses_registry_then_existing_router_then_exact_read() -> None:
    source = _read(APP)
    handler = _js_region(
        source,
        "async function handleNotificationRuntimeRequest",
        "function bindGlobalEvents",
    )
    open_flow = handler[handler.index("const validation =") :]

    assert 'from "./workspace-command-registry.js?v=20260826.rebuild-clean.21"' in source
    assert "resolveWorkspaceCommand({" in source
    assert "source: \"notification\"" in source
    assert "policy?.dispatchCount !== 1" in source
    assert "policy?.paidAction !== false" in source
    assert "policy?.startsAnalysis !== false" in source
    assert "policy?.startsGeneration !== false" in source
    assert "notificationReadResponseMatchesScope" in source
    assert 'response.scope === "visible_filter"' in source
    assert (
        'response.read_state_version === "contentengine-notification-read-v4.9.1"'
        in source
    )
    assert open_flow.index("validateNotificationAction({") < open_flow.index(
        "resolveNotificationRuntimeCommand(request, validation)"
    )
    assert open_flow.index("resolveNotificationRuntimeCommand(request, validation)") < (
        open_flow.index("navigate(command.destination")
    )
    assert open_flow.index("navigate(command.destination") < open_flow.index(
        "markVisibleNotificationsRead("
    )
    assert "window.location.href" not in handler
    assert "window.open(" not in handler
    assert "startRealGeneration" not in handler
    assert "startProductResearch" not in handler
    assert "decideAiResearchReceipt" not in handler


def test_shell_keeps_one_panel_and_uses_the_runtime_bridge() -> None:
    source = _read(SHELL)
    assert source.count('panel.id = "ce-v4-notification-panel"') == 1
    assert source.count('panel.setAttribute("aria-modal", "false")') == 1
    assert "contentengine:notification-center-request-v491" in source
    assert "contentengine:notification-center-response-v491" in source
    assert "requestNotificationCenterProjection" in source
    assert "acceptNotificationCenterProjection" in source
    assert "requestNotificationVisibleRead" in source
    assert "requestNotificationOpen" in source
    assert "notificationActionFailures" in source
    assert "notificationInitialLoadRequested" in source
    assert (
        "requestNotificationCenterProjection(runtime.notificationFilter, { force: true })"
        in source
    )
    assert "data-ce-v4-notification-fixture" not in source
    assert 'dataset.ceV4NotificationFixture === "true"' in source


def test_browser_harness_covers_320_390_and_1280_without_a_second_panel() -> None:
    source = _read(FIXTURE)
    assert 'data-ce-v4-notification-runtime-harness="true"' in source
    assert "contentengine:notification-center-request-v491" in source
    assert "creator_validate_notification_action" not in source
    assert "320" in source
    assert "390" in source
    assert "1280" in source
    assert "data-ce-v4-notification-panel" not in source


def test_release_literals_are_not_changed_by_notification_integration() -> None:
    app = _read(APP)
    shell = _read(SHELL)
    registry = _read(REGISTRY)
    # 25.08: живые пины импортов переведены на единый текущий штамп сборки —
    # эпоха os4.41 в app.js закончилась вместе с кэш-ловушкой F5.
    assert "20260826.rebuild-clean.21" in app
    assert "20260814.os4.41" not in app
    assert 'const BUILD = "20260826.rebuild-clean.21"' in shell
    assert 'WORKSPACE_COMMAND_REGISTRY_CONTRACT_VERSION = "4.9.1"' in registry
    assert "os4.40" not in app
    assert "os4.40" not in shell
