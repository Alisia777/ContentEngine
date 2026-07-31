from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607310102_workspace_trash_visibility.sql"
).read_text(encoding="utf-8")


def test_trashed_tasks_are_hidden_from_task_and_publishing_feeds() -> None:
    for marker in (
        "public.creator_workspace_section(jsonb)",
        "workspace_placement_visibility_outer_patch_failed",
        "workspace_placement_visibility_candidate_patch_failed",
        "workspace_task_visibility_outer_patch_failed",
        "workspace_task_visibility_candidate_patch_failed",
        "trash.entity_id = placement.task_id",
        "trash.entity_id = candidate.task_id",
        "trash.entity_id = task.id",
        "trash.entity_id = candidate.id",
        "trash.status = 'trashed'",
    ):
        assert marker in MIGRATION


def test_trashed_tasks_are_hidden_from_my_work() -> None:
    for marker in (
        "public.creator_my_work(jsonb)",
        "my_work_task_visibility_patch_failed",
        "my_work_placement_visibility_patch_failed",
        "trash.entity_id = task.id",
        "trash.entity_id = placement.task_id",
        "my_work_trash_visibility_patch_empty",
    ):
        assert marker in MIGRATION


def test_visibility_patch_fails_closed_if_legacy_rpc_shape_changes() -> None:
    assert MIGRATION.count("if position(pattern in updated_definition) = 0") == 6
    assert MIGRATION.count("execute updated_definition") == 2
    assert "workspace_trash_visibility_patch_empty" in MIGRATION
    assert "revoke all on function public.creator_workspace_section(jsonb)" in MIGRATION
    assert "grant execute on function public.creator_workspace_section(jsonb)" in MIGRATION
    assert "revoke all on function public.creator_my_work(jsonb)" in MIGRATION
    assert "grant execute on function public.creator_my_work(jsonb)" in MIGRATION
