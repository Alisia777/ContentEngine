from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
QUEUE_MIGRATION = (
    MIGRATIONS / "202608100001_research_ai_center_generation_presets.sql"
)
SCOPE_MIGRATION = (
    MIGRATIONS / "202608100008_ai_research_training_project_scope.sql"
)
TRAINING = ROOT / "web" / "app" / "workspace-ai-research-training.js"
GENERATION = (
    ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _compact(source: str) -> str:
    return re.sub(r"\s+", " ", source.casefold()).strip()


def _sql_function(source: str, qualified_name: str) -> str:
    header = re.compile(
        rf"\bcreate\s+(?:or\s+replace\s+)?function\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        re.IGNORECASE,
    )
    match = header.search(source)
    assert match is not None, f"SQL function {qualified_name} is missing"
    next_function = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def _run_module_script(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = f"""
      const {{ readFileSync }} = await import('node:fs');
      const source = readFileSync(process.argv[1], 'utf8');
      const encoded = Buffer.from(source).toString('base64');
      const mod = await import(`data:text/javascript;base64,${{encoded}}`);
      {body}
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, str(TRAINING)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_scope_migrations_parse_and_have_one_ordered_version() -> None:
    queue_sql = _read(QUEUE_MIGRATION)
    scope_sql = _read(SCOPE_MIGRATION)
    versions = [path.name.split("_", 1)[0] for path in MIGRATIONS.glob("*.sql")]

    assert parse_sql(queue_sql)
    assert parse_sql(scope_sql)
    assert versions.count("202608100008") == 1
    assert QUEUE_MIGRATION.name < SCOPE_MIGRATION.name
    assert _compact(scope_sql).startswith("begin;")
    assert _compact(scope_sql).endswith("commit;")


def test_creator_queue_filters_exact_project_before_both_limits() -> None:
    queue = _compact(
        _sql_function(
            _read(QUEUE_MIGRATION),
            "public.creator_ai_research_training_queue",
        )
    )

    assert "'organization_id', 'project_id', 'product_category', 'limit'" in queue
    assert "require_uuid( p_payload, 'project_id' )" in queue
    assert "require_workspace_project( organization_id_value, project_id_value )" in queue

    queue_filter = queue.index("or receipt.project_id = project_id_value")
    first_limit = queue.index("limit limit_value", queue_filter)
    learned_filter = queue.index("or selection.project_id = project_id_value", first_limit)
    second_limit = queue.index("limit limit_value", learned_filter)
    assert queue_filter < first_limit < learned_filter < second_limit

    # This ordering is the regression guard for >limit newer receipts in a
    # sibling project: exact-project filtering happens before each LIMIT.
    assert queue.count("project_id_value is null") == 2


def test_public_queue_and_decision_are_exact_project_acl_wrappers() -> None:
    sql = _read(SCOPE_MIGRATION)
    compact = _compact(sql)
    queue = _compact(
        _sql_function(sql, "public.contentengine_ai_research_training_queue")
    )
    decision = _compact(
        _sql_function(sql, "public.contentengine_decide_ai_research_training")
    )

    assert "require_uuid( p_payload, 'project_id' )" in queue
    assert "require_workspace_project( organization_id_value, project_id_value )" in queue
    assert "creator_ai_research_training_queue( p_payload )" in queue
    assert "entry.value ->> 'project_id' = project_id_value::text" in queue
    assert "'project_scoped', true" in queue

    acl = decision.index("require_workspace_project(")
    exact_receipt = decision.index("receipt.project_id = project_id_value")
    delegate = decision.index(
        "contentengine_decide_ai_research_training_unscoped_v1("
    )
    scoped_snapshot = decision.index(
        "public.contentengine_ai_research_training_queue("
    )
    assert acl < exact_receipt < delegate < scoped_snapshot
    assert "p_payload - 'project_id'" in decision
    assert "ai_research_training_receipt_stale" in decision
    assert "jsonb_set( result_value, '{snapshot}', snapshot_value, true )" in decision

    assert "set schema content_factory_private" in compact
    assert (
        "revoke all on function public.creator_ai_research_training_queue(jsonb) "
        "from public, anon, authenticated, service_role"
    ) in compact
    assert (
        "grant execute on function public.creator_ai_research_training_queue(jsonb) "
        "to service_role"
    ) in compact


def test_legacy_control_room_cannot_reopen_or_mutate_unscoped_research() -> None:
    sql = _read(SCOPE_MIGRATION)
    compact = _compact(sql)
    control_room = _compact(
        _sql_function(sql, "public.creator_ai_learning_control_room")
    )

    assert "creator_ai_learning_control_room_pre_research_inbox_v1" in control_room
    assert "'research_inbox', '[]'::jsonb" in control_room
    assert "'research_decisions', '[]'::jsonb" in control_room
    assert "'research_inbox_count', 0" in control_room
    assert "'research_decision_count', 0" in control_room
    assert "'can_read_research_inbox', false" in control_room
    assert "'can_decide_research_inbox', false" in control_room
    assert "'research_inbox_next_action', null" in control_room

    assert (
        "revoke all on function public.creator_decide_ai_research_receipt(jsonb) "
        "from public, anon, authenticated, service_role"
    ) in compact
    assert (
        "grant execute on function public.creator_decide_ai_research_receipt(jsonb) "
        "to service_role"
    ) in compact


def test_route_payload_and_stale_snapshot_contract_is_executable() -> None:
    value = _run_module_script(
        """
        const projectA = '11111111-1111-4111-8111-111111111111';
        const projectB = '22222222-2222-4222-8222-222222222222';
        const selected = mod.resolveTrainingProjectId({
          routeValues: [projectA],
          storedValue: projectB,
        });
        const ambiguous = mod.resolveTrainingProjectId({
          routeValues: [projectA, projectB],
          storedValue: projectA,
        });
        const queuePayload = mod.projectScopedTrainingPayload({
          product_category: 'food', limit: 30,
        }, selected);
        const decisionPayload = mod.projectScopedTrainingPayload({
          receipt_id: '33333333-3333-4333-8333-333333333333',
          decision: 'approve',
        }, selected);
        const exact = mod.projectScopedTrainingSnapshot({
          project_id: projectA,
          queue: [
            { project_id: projectB, receipt_id: 'stale' },
            { project_id: projectA, receipt_id: 'exact' },
          ],
          learned: [
            { project_id: projectA, selection_id: 'exact-learned' },
            { project_id: projectB, selection_id: 'stale-learned' },
          ],
        }, selected);
        const staleResponse = mod.projectScopedTrainingSnapshot({
          project_id: projectB,
          queue: [{ project_id: projectB, receipt_id: 'wrong-project' }],
          learned: [],
        }, selected);
        const hash = mod.trainingProjectHash(
          selected,
          '#/workspace/ai?category=food&view=knowledge',
        );
        console.log(JSON.stringify({
          selected,
          ambiguous,
          queuePayload,
          decisionPayload,
          exact,
          staleResponse,
          hash,
        }));
        """
    )

    project_a = "11111111-1111-4111-8111-111111111111"
    assert value["selected"] == project_a
    assert value["ambiguous"] == ""
    assert value["queuePayload"]["project_id"] == project_a
    assert value["decisionPayload"]["project_id"] == project_a
    assert [item["receipt_id"] for item in value["exact"]["queue"]] == ["exact"]
    assert [item["selection_id"] for item in value["exact"]["learned"]] == [
        "exact-learned"
    ]
    assert value["staleResponse"] is None
    assert "project_id=11111111-1111-4111-8111-111111111111" in value["hash"]
    assert "category=food" in value["hash"]
    assert "view=knowledge" in value["hash"]


def test_lazy_queue_decision_and_dynamic_links_keep_the_same_project() -> None:
    training = _read(TRAINING)
    generation = _read(GENERATION)

    assert "canonicalizeTrainingRoute(category, projectId)" in training
    assert training.count("projectScopedTrainingPayload({") >= 2
    assert "runtime.projectId !== selectedProjectId" in training
    assert "currentTrainingProjectId() !== selectedProjectId" in training
    assert "normalizedProjectId(card.dataset.projectId) !== projectId" in training
    assert "projectScopedTrainingSnapshot(snapshot, expectedProjectId)" in training
    assert 'oldInbox.hidden = true' in training
    assert 'oldInbox.hidden = false' not in training
    assert "Выберите проект для обучения на исследованиях" in training
    assert (
        "#/workspace/research?project_id=${encodeURIComponent(source.project_id)}"
        in training
    )

    assert (
        "#/workspace/ai?project_id=${encodeURIComponent(projectId())}" in generation
    )
    assert (
        "#/workspace/ai?project_id=${encodeURIComponent(context.projectId)}"
        in generation
    )
