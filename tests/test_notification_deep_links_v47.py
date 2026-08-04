from __future__ import annotations

import json
from pathlib import Path
import subprocess

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql"
).read_text(encoding="utf-8")
APP_PATH = ROOT / "web/app/app.js"
APP = APP_PATH.read_text(encoding="utf-8")


def _function(source: str, declaration: str) -> str:
    start = source.index(declaration)
    brace = source.index("{", start)
    depth = 0
    quote = ""
    escaped = False
    for index in range(brace, len(source)):
        character = source[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'", "`"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unclosed function: {declaration}")


def test_project_notification_rewrite_is_valid_postgresql() -> None:
    assert parse_sql(MIGRATION)


def test_outbox_insert_policy_emits_exact_project_entity_destinations() -> None:
    policy_start = MIGRATION.index(
        "content_factory_private.notification_entity_scope_v47("
    )
    policy_end = MIGRATION.index("create or replace function", policy_start + 1)
    policy = MIGRATION[policy_start:policy_end]

    for table in (
        "content_factory.generation_jobs",
        "content_factory.content_review_runs",
        "content_factory.product_research_runs",
    ):
        assert table in policy
    for route in (
        "#/workspace/generation?project_id=",
        "&view=history&job=",
        "#/workspace/review?project_id=",
        "&view=current&review=",
        "#/workspace/research?project_id=",
        "&view=evidence&run=",
    ):
        assert route in policy
    assert "where job.organization_id = p_organization_id" in policy
    assert "where review.organization_id = p_organization_id" in policy
    assert "where research.organization_id = p_organization_id" in policy

    trigger_start = MIGRATION.index(
        "content_factory_private.scope_notification_outbox_v47()"
    )
    trigger_end = MIGRATION.index(
        "drop trigger if exists scope_notification_outbox_project_v47",
        trigger_start,
    )
    trigger = MIGRATION[trigger_start:trigger_end]
    assert "new.deep_link := scope_value ->> 'deep_link'" in trigger
    assert "'project_id', scope_value ->> 'project_id'" in trigger
    assert "scope_value ->> 'entity_query', new.entity_id" in trigger
    assert "new.request_hash := content_factory_private.json_hash(" in trigger
    assert "before insert on content_factory.notification_outbox" in MIGRATION


def test_existing_outbox_and_inbox_links_are_rewritten_with_hashes() -> None:
    outbox_start = MIGRATION.index(
        "drop trigger if exists guard_notification_outbox\n"
        "  on content_factory.notification_outbox;",
        MIGRATION.index("scope_notification_outbox_project_v47"),
    )
    inbox_start = MIGRATION.index(
        "drop trigger if exists guard_user_notification", outbox_start
    )
    outbox = MIGRATION[outbox_start:inbox_start]
    private_revoke = MIGRATION.index("-- Private helpers", inbox_start)
    inbox = MIGRATION[inbox_start:private_revoke]

    assert "update content_factory.notification_outbox outbox" in outbox
    assert "notification_entity_scope_v47(" in outbox
    assert "request_hash = content_factory_private.json_hash" in outbox
    assert "create trigger guard_notification_outbox" in outbox
    assert "update content_factory.user_notifications notification" in inbox
    assert "notification_entity_scope_v47(" in inbox
    assert "request_hash = content_factory_private.json_hash" in inbox
    assert "create trigger guard_user_notification" in inbox


def test_explicit_notification_project_is_never_rebound_to_active_project() -> None:
    module = "\n".join(
        (
            "const currentProject = '11111111-1111-4111-8111-111111111111';",
            "const explicitProject = '22222222-2222-4222-8222-222222222222';",
            "const currentWorkspaceProjectId = () => currentProject;",
            "const isWorkspaceProjectId = (value) => [currentProject, explicitProject].includes(String(value || '').toLowerCase());",
            _function(APP, "function workspaceProjectHref("),
            _function(APP, "function scopedWorkspaceAnchorHref("),
            "const job = '33333333-3333-4333-8333-333333333333';",
            "const exact = scopedWorkspaceAnchorHref(`#/workspace/generation?project_id=${explicitProject}&view=history&job=${job}`);",
            "const generic = scopedWorkspaceAnchorHref('#/workspace/work?view=notifications');",
            "if (!exact.includes(`project_id=${explicitProject}`) || exact.includes(`project_id=${currentProject}`) || !exact.includes(`job=${job}`)) throw new Error(exact);",
            "if (!generic.includes(`project_id=${currentProject}`)) throw new Error(generic);",
            "process.stdout.write(JSON.stringify({ exact, generic }));",
        )
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", module],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert "view=history" in payload["exact"]
    assert "view=notifications" in payload["generic"]

    scope = _function(APP, "function scopeWorkspaceAnchorHrefs(")
    click = _function(APP, "async function handleClick(")
    assert "scopedWorkspaceAnchorHref(href)" in scope
    assert "scopedWorkspaceAnchorHref(href)" in click


def test_exact_research_run_route_wins_and_fails_closed_across_projects() -> None:
    restore = _function(APP, "function restoreProductResearchSession(")
    route_branch = restore[: restore.index(
        "if (research.restoreAttempted || research.record) return;"
    )]

    assert 'state.route.query.has("run")' in route_branch
    assert 'safeWorkspaceRouteEntityId("project_id")' in route_branch
    assert 'safeWorkspaceRouteEntityId("run")' in route_branch
    assert "routeProjectId !== activeProjectId" in route_branch
    assert "research.record = null" in route_branch
    assert 'research.phase = "error"' in route_branch
    assert "persistProductResearchRunId(routeRunId)" in route_branch
    assert "pollProductResearchStatus({ silent: true })" in route_branch
