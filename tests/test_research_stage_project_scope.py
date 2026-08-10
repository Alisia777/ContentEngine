from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608100004_research_stage_project_scope.sql"
)
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"
PGTAP = ROOT / "supabase/tests/research_stage_control_loop_test.sql"


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


def _class_method(source: str, name: str) -> str:
    header = re.compile(
        rf"^\s{{2}}(?:async\s+)?{re.escape(name)}\s*\(",
        re.MULTILINE,
    )
    match = header.search(source)
    assert match is not None, f"CreatorApi.{name} is missing"
    next_method = re.search(
        r"^\s{2}(?:async\s+)?[A-Za-z_$][\w$]*\s*\(",
        source[match.end() :],
        re.MULTILINE,
    )
    end = len(source) if next_method is None else match.end() + next_method.start()
    return source[match.start() : end]


def _top_level_function(source: str, name: str) -> str:
    header = re.compile(
        rf"^(?:export\s+)?(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        re.MULTILINE,
    )
    match = header.search(source)
    assert match is not None, f"JavaScript function {name} is missing"
    next_function = re.search(
        r"^(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(",
        source[match.end() :],
        re.MULTILINE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def test_project_scope_migration_is_valid_and_preserves_one_private_layer() -> None:
    sql = _read(MIGRATION)
    folded = _compact(sql)

    assert parse_sql(sql)
    for alias in (
        "creator_research_stage_control_status_pre_project_scope_v423",
        "creator_control_research_stage_pre_project_scope_v423",
    ):
        assert f"to_regprocedure( '{'content_factory_private.' + alias + '(jsonb)'}' ) is null" in folded
        assert f"revoke all on function content_factory_private.{alias}( jsonb )" in folded
    assert folded.count("set schema content_factory_private") == 2
    assert "notify pgrst, 'reload schema'" in folded


def test_status_and_control_fail_closed_to_the_exact_project_run() -> None:
    sql = _read(MIGRATION)
    status = _compact(
        _sql_function(sql, "public.creator_research_stage_control_status")
    )
    control = _compact(
        _sql_function(sql, "public.creator_control_research_stage")
    )

    for wrapper, alias in (
        (
            status,
            "creator_research_stage_control_status_pre_project_scope_v423",
        ),
        (control, "creator_control_research_stage_pre_project_scope_v423"),
    ):
        # An organization role is not enough: explicit project ACL is checked
        # before an exact project/run lookup and before the preserved function.
        acl = wrapper.index("require_workspace_project(")
        exact_run = wrapper.index("run.project_id = project_id_value")
        delegate = wrapper.index(f".{alias}(")
        assert acl < exact_run < delegate
        assert "require_uuid( p_payload, 'project_id' )" in wrapper
        assert "run.organization_id = organization_id_value" in wrapper
        assert "run.id = run_id_value" in wrapper
        assert "research_run_project_scope_mismatch" in wrapper
        assert "inner_payload := (p_payload - 'project_id')" in wrapper
        assert "'project_id', project_id_value" in wrapper

    assert "array['owner', 'admin', 'producer', 'reviewer']" in status
    assert "array['owner', 'admin', 'producer']" in control


def test_project_context_is_restored_on_success_and_exception() -> None:
    sql = _read(MIGRATION)
    for name in (
        "public.creator_research_stage_control_status",
        "public.creator_control_research_stage",
    ):
        wrapper = _compact(_sql_function(sql, name))
        assert "previous_project_setting := current_setting( 'contentengine.project_id', true )" in wrapper
        assert "set_config( 'contentengine.project_id', project_id_value::text, true )" in wrapper
        assert "exception when others then" in wrapper
        assert wrapper.count("coalesce(previous_project_setting, '')") == 2
        exception_at = wrapper.index("exception when others then")
        raise_at = wrapper.index("raise;", exception_at)
        restore_at = wrapper.index(
            "coalesce(previous_project_setting, '')",
            exception_at,
        )
        assert exception_at < restore_at < raise_at

    control = _compact(
        _sql_function(sql, "public.creator_control_research_stage")
    )
    status = _compact(
        _sql_function(sql, "public.creator_research_stage_control_status")
    )
    assert "'{recompute_request,invoke,project_id}'" in control
    assert "'{active_recompute,invoke,project_id}'" in status
    for wrapper in (status, control):
        assert "child_run.project_id = project_id_value" in wrapper
        assert "research_stage_recompute_child_project_scope_mismatch" in wrapper


def test_runtime_stage_control_fixture_uses_the_same_project_contract() -> None:
    sql = _read(PGTAP)
    folded = _compact(sql)

    assert parse_sql(sql)
    assert "insert into content_factory.workspace_folders" in folded
    assert "insert into content_factory.workspace_project_memberships" in folded
    assert "'fa500000-0000-4000-8000-000000000001'" in folded
    assert "'fa500000-0000-4000-8000-000000000002'" in folded
    assert re.search(
        r"insert\s+into\s+content_factory\.product_research_runs\s*\("
        r"[^)]*\bproject_id\b",
        sql,
        re.IGNORECASE | re.DOTALL,
    )

    calls = list(
        re.finditer(
            r"public\.creator_(?:research_stage_control_status|"
            r"control_research_stage)\s*\(\s*jsonb_build_object\s*\(",
            sql,
            re.IGNORECASE,
        )
    )
    assert len(calls) >= 24
    windows = [sql[call.start() : call.start() + 360] for call in calls]
    missing_project = [window for window in windows if "'project_id'" not in window]
    # One negative assertion deliberately proves that the browser contract
    # rejects an omitted project.  Every functional fixture call is scoped.
    assert len(missing_project) == 1
    assert "project_id_invalid" in sql
    assert "research_run_project_scope_mismatch" in sql
    assert sql.count(
        "'project_id', 'fa500000-0000-4000-8000-000000000001'"
    ) >= 24


def test_browser_contract_requires_and_propagates_project_id() -> None:
    api = _read(API)
    status = _class_method(api, "researchStageControlStatus")
    control = _class_method(api, "controlResearchStage")
    resume = _class_method(api, "resumeResearchStageRecompute")

    assert "requiredProjectId(" in status
    assert "project_id: projectId" in status
    assert "requiredProjectId(" in control
    assert "project_id: projectId" in control
    assert "recompute.invoke?.project_id" in control
    assert control.count("project_id: projectId") >= 2
    assert "requiredProjectId(" in resume
    assert "project_id: projectId" in resume
    assert "workspace_project_access_required:" in api
    assert "research_run_project_scope_mismatch:" in api
    assert "research_stage_recompute_child_project_scope_mismatch:" in api

    app = _read(APP)
    load = _top_level_function(app, "loadResearchStageControl")
    cancel = _top_level_function(app, "submitProductResearchStageCancel")
    mutation = _top_level_function(app, "submitProductResearchStageControl")
    assert "project_id: currentWorkspaceProjectId()" in load
    assert "project_id: currentWorkspaceProjectId()" in cancel
    assert "project_id: currentWorkspaceProjectId()" in mutation
    resume_call = re.search(
        r"resumeResearchStageRecompute\(childRunId, requestId,\s*\{(?P<body>.*?)\}\)",
        app,
        re.DOTALL,
    )
    assert resume_call is not None
    assert "project_id: currentWorkspaceProjectId()" in resume_call.group("body")
