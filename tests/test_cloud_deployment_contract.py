from pathlib import Path
import re
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_WORKFLOW = ".github/workflows/supabase-pages.yml"
EXPECTED_CREATOR_RPCS = (
    "creator_bootstrap",
    "creator_complete_module",
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
)
ACTION_PINS = {
    "actions/checkout": "df4cb1c069e1874edd31b4311f1884172cec0e10",
    "actions/configure-pages": "983d7736d9b0ae728b81ab479565c72886d7745b",
    "actions/upload-pages-artifact": "7b1f4a764d45c48632c6b24a0339c27f5614fb0b",
    "actions/deploy-pages": "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    "actions/setup-python": "ece7cb06caefa5fff74198d8649806c4678c61a1",
    "supabase/setup-cli": "3c2f5e2ae34c34e428e8e206e2c4d21fa2d20fbf",
    "denoland/setup-deno": "22d081ff2d3a40755e97629de92e3bcbfa7cf2ed",
}


def _pinned(action: str) -> str:
    return f"{action}@{ACTION_PINS[action]}"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    payload = yaml.safe_load(_text(path))
    assert isinstance(payload, dict)
    return payload


def _production_migration_sql() -> str:
    migration_paths = sorted((ROOT / "supabase/migrations").glob("*.sql"))
    assert migration_paths
    assert [path.name for path in migration_paths] == sorted(
        path.name for path in migration_paths
    )
    return "\n".join(path.read_text(encoding="utf-8") for path in migration_paths)


def test_production_path_is_supabase_native_pages_without_render_or_container_publish() -> None:
    assert not (ROOT / "render.yaml").exists()
    assert not (ROOT / ".github/workflows/container.yml").exists()

    workflow = _text(PRODUCTION_WORKFLOW)
    assert "Deploy Supabase and GitHub Pages" in workflow
    assert "supabase db push --linked" in workflow
    assert _pinned("actions/upload-pages-artifact") in workflow
    assert _pinned("actions/deploy-pages") in workflow
    assert "docker build" not in workflow
    assert "ghcr.io" not in workflow
    assert "Render" not in workflow


def test_production_workflow_migrates_before_publishing_pages() -> None:
    workflow = _yaml(PRODUCTION_WORKFLOW)
    jobs = workflow["jobs"]
    migrate = jobs["migrate"]
    build = jobs["build-pages"]
    deploy = jobs["deploy-pages"]

    assert migrate["environment"] == "production"
    assert "workflow_run.conclusion == 'success'" in migrate["if"]
    assert "workflow_run.event == 'push'" in migrate["if"]
    assert "workflow_run.head_branch == 'main'" in migrate["if"]
    assert "workflow_run.head_repository.full_name == github.repository" in migrate["if"]
    assert "github.ref == 'refs/heads/main'" in migrate["if"]
    assert migrate["env"]["SUPABASE_ACCESS_TOKEN"] == "${{ secrets.SUPABASE_ACCESS_TOKEN }}"
    assert migrate["env"]["SUPABASE_DB_PASSWORD"] == "${{ secrets.SUPABASE_DB_PASSWORD }}"
    assert migrate["env"]["SUPABASE_PROJECT_REF"] == "${{ vars.SUPABASE_PROJECT_REF }}"
    assert migrate["env"]["EXPECTED_SUPABASE_PROJECT_REF"] == "iyckwryrucqrxwlowxow"
    assert any(
        step.get("uses") == _pinned("supabase/setup-cli")
        and step.get("with", {}).get("version") == "2.109.1"
        for step in migrate["steps"]
    )
    config_push_index = next(
        index
        for index, step in enumerate(migrate["steps"])
        if step.get("run")
        == 'supabase config push --project-ref "$SUPABASE_PROJECT_REF"'
    )
    dry_run_index = next(
        index
        for index, step in enumerate(migrate["steps"])
        if step.get("run") == "supabase db push --linked --dry-run"
    )
    database_push_index = next(
        index
        for index, step in enumerate(migrate["steps"])
        if step.get("run") == "supabase db push --linked"
    )
    assert dry_run_index < config_push_index < database_push_index
    assert any(
        "supabase db push --linked" in str(step.get("run", ""))
        for step in migrate["steps"]
    )
    assert any(
        step.get("run") == "supabase db push --linked --dry-run"
        for step in migrate["steps"]
    )
    assert all(
        "--password" not in str(step.get("run", ""))
        for step in migrate["steps"]
    )
    invite_deploy = next(
        step
        for step in migrate["steps"]
        if step.get("name") == "Deploy authenticated creator invitation function"
    )
    assert invite_deploy["run"] == (
        'supabase functions deploy creator-invite --project-ref "$SUPABASE_PROJECT_REF"'
    )
    assert "--no-verify-jwt" not in invite_deploy["run"]
    assert "--prune" not in invite_deploy["run"]

    assert build["env"]["SUPABASE_PUBLISHABLE_KEY"] == (
        "${{ vars.SUPABASE_PUBLISHABLE_KEY }}"
    )
    assert build["env"]["EXPECTED_SUPABASE_PROJECT_REF"] == "iyckwryrucqrxwlowxow"
    assert "workflow_run.conclusion == 'success'" in build["if"]
    assert "workflow_run.event == 'push'" in build["if"]
    assert "workflow_run.head_repository.full_name == github.repository" in build["if"]
    assert build["permissions"] == {"contents": "read", "pages": "write"}
    assert any(
        step.get("uses") == _pinned("actions/configure-pages")
        for step in build["steps"]
    )
    upload = next(
        step
        for step in build["steps"]
        if step.get("uses") == _pinned("actions/upload-pages-artifact")
    )
    assert upload["with"]["path"] == "_site"

    assert set(deploy["needs"]) == {"migrate", "build-pages"}
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["environment"]["name"] == "github-pages"
    assert deploy["steps"][-1]["uses"] == _pinned("actions/deploy-pages")


def test_every_external_action_is_pinned_to_an_immutable_commit() -> None:
    for workflow_path in (PRODUCTION_WORKFLOW, ".github/workflows/ci.yml"):
        workflow = _yaml(workflow_path)
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                action = step.get("uses")
                if action is None or action.startswith("./"):
                    continue
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action), (
                    f"{workflow_path} contains a mutable action reference: {action}"
                )


def test_production_workflow_releases_the_successful_main_ci_commit() -> None:
    workflow_text = _text(PRODUCTION_WORKFLOW)

    assert "workflow_run:" in workflow_text
    assert "workflows:\n      - CI" in workflow_text
    assert "branches:\n      - main" in workflow_text
    assert "push:" not in workflow_text
    assert workflow_text.count(
        "ref: ${{ github.event.workflow_run.head_sha || github.sha }}"
    ) == 2
    assert workflow_text.count("persist-credentials: false") == 2


def test_pages_build_accepts_only_browser_safe_configuration() -> None:
    workflow = _text(PRODUCTION_WORKFLOW)

    assert "SUPABASE_PUBLISHABLE_KEY" in workflow
    assert workflow.count(
        'if [ "$SUPABASE_PROJECT_REF" != "$EXPECTED_SUPABASE_PROJECT_REF" ]'
    ) == 2
    assert "sb_publishable_*" in workflow
    assert "SUPABASE_SECRET_KEY" not in workflow
    assert "SUPABASE_SERVICE_ROLE_KEY" not in workflow
    assert "OPENAI_API_KEY" not in workflow
    assert "RUNWAYML_API_SECRET" not in workflow
    assert "_site/config.js" in workflow
    assert "cp -R web/app/. _site/" in workflow
    assert "test -f _site/index.html" in workflow
    assert "__SET_SUPABASE_|127\\.0\\.0\\.1|localhost" in workflow
    assert '"MOCK_ONLY": True' in workflow
    assert '"MAX_BATCH_SIZE": 50' in workflow
    assert '"STORAGE_BUCKET": "contentengine-private"' in workflow


def test_private_exam_keys_are_step_scoped_and_never_printed() -> None:
    workflow = _yaml(PRODUCTION_WORKFLOW)
    migrate = workflow["jobs"]["migrate"]
    build = workflow["jobs"]["build-pages"]
    steps = migrate["steps"]
    provision_index, provision = next(
        (index, step)
        for index, step in enumerate(steps)
        if step.get("name") == "Provision private exam grading keys"
    )
    database_push_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("run") == "supabase db push --linked"
    )

    assert "SUPABASE_EXAM_KEYS_B64" not in migrate["env"]
    assert provision["env"] == {
        "SUPABASE_EXAM_KEYS_B64": "${{ secrets.SUPABASE_EXAM_KEYS_B64 }}"
    }
    assert database_push_index < provision_index
    command = provision["run"]
    assert "base64.b64decode" in command
    assert "validate=True" in command
    assert 'chmod(0o600)' in command
    assert '>"$command_log" 2>&1' in command
    assert 'rm -f "$key_file" "$command_log"' in command
    assert "cat \"$command_log\"" not in command
    assert "set -x" not in command
    assert "SUPABASE_EXAM_KEYS_B64" not in build.get("env", {})


def test_creator_invite_function_is_explicitly_jwt_verified() -> None:
    config = tomllib.loads(_text("supabase/config.toml"))
    source = _text("supabase/functions/creator-invite/index.ts")

    assert (ROOT / "supabase/functions/creator-invite/index.ts").is_file()
    assert config["functions"]["creator-invite"]["verify_jwt"] is True
    assert 'npm:@supabase/server@1.3.0' in source
    assert 'auth: "user"' in source
    assert 'new Set(["owner", "admin"])' in source
    assert 'const MAX_INVITES = 50' in source
    assert 'bootstrap.workspaceOpen' in source
    assert '"system_provision_invited_member"' in source
    assert "inviteData.user?.id" in source
    assert "deleteUser" not in source
    assert "idempotency_key:" in source
    assert "localhost" not in source
    assert "127.0.0.1" not in source
    workflow = _text(PRODUCTION_WORKFLOW)
    assert "supabase functions deploy creator-invite" in workflow
    assert "--no-verify-jwt" not in workflow
    assert "--prune" not in workflow


def test_remote_auth_configuration_is_cloud_only_and_versioned() -> None:
    config = tomllib.loads(_text("supabase/config.toml"))
    auth = config["auth"]

    assert auth["site_url"] == "https://alisia777.github.io/ContentEngine/"
    assert auth["additional_redirect_urls"] == [
        "https://alisia777.github.io/ContentEngine/**"
    ]
    assert auth["enable_signup"] is False
    assert config["auth"]["email"]["enable_signup"] is False
    assert all(
        "localhost" not in url and "127.0.0.1" not in url
        for url in [auth["site_url"], *auth["additional_redirect_urls"]]
    )
    assert "supabase config push" in _text(PRODUCTION_WORKFLOW)


def test_supabase_migrations_own_schema_training_storage_and_mock_only_guards() -> None:
    sql = _production_migration_sql().casefold()

    assert "create schema if not exists content_factory" in sql
    assert "create schema if not exists content_factory_private" in sql
    assert "operator_final_exam" in sql
    assert "training_certifications" in sql
    assert "contentengine-private" in sql
    assert re.search(
        r"insert\s+into\s+storage\.buckets\s*\([^)]*public[^)]*\)"
        r"\s*values\s*\([^;]*false[^;]*\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert "real_generation_is_disabled" in sql
    assert "auth.uid()" in sql
    assert "enable row level security" in sql


def test_browser_adapter_and_database_publish_the_same_narrow_rpc_contract() -> None:
    adapter = _text("web/app/supabase-api.js")
    sql = _production_migration_sql()

    for function_name in EXPECTED_CREATOR_RPCS:
        assert f'"{function_name}"' in adapter
        declaration = re.search(
            rf"create\s+or\s+replace\s+function\s+public\.{function_name}"
            rf"\s*\(\s*p_payload\s+jsonb",
            sql,
            flags=re.IGNORECASE,
        )
        assert declaration, f"missing production RPC {function_name}(p_payload jsonb)"
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{function_name}"
            rf"\s*\(\s*jsonb\s*\)\s+to\s+authenticated",
            sql,
            flags=re.IGNORECASE,
        ), f"authenticated role cannot execute {function_name}"

    assert "p_payload: payload" in adapter
    assert "auth.uid()" in sql.casefold()
    assert "security definer" in sql.casefold()
    assert "set search_path = ''" in sql.casefold()


def test_ci_validates_supabase_contract_and_keeps_python_only_as_reference() -> None:
    _yaml(".github/workflows/ci.yml")
    ci = _text(".github/workflows/ci.yml")
    readme = _text("README.md")

    assert _pinned("supabase/setup-cli") in ci
    assert ci.count("version: 2.109.1") == 1
    assert "supabase db start" in ci
    assert "supabase db lint --local --level error" in ci
    assert "supabase test db" in ci
    assert (ROOT / "supabase/tests/creator_factory_test.sql").is_file()
    assert _pinned("denoland/setup-deno") in ci
    assert "deno-version: v2.8.1" in ci
    assert "deno fmt --check supabase/functions/creator-invite" in ci
    assert "deno lint supabase/functions/creator-invite/index.ts" in ci
    assert "deno check supabase/functions/creator-invite/index.ts" in ci
    assert "python -m pytest -q" in ci
    assert "reference-postgres-migration" in ci
    assert "docker build" not in ci
    assert "render.yaml" not in ci
    assert "reference/regression" in readme
    assert (ROOT / "Dockerfile").is_file()


def test_cloud_documentation_describes_one_public_browser_workspace() -> None:
    guide = _text("docs/CLOUD_DEPLOYMENT.md")
    normalized = " ".join(guide.split())

    assert "browser-only workspace" in guide
    assert "GitHub Pages" in guide
    assert "existing paid Supabase project" in guide
    assert "There is no general production application server or container" in normalized
    assert "authenticated creator-invite" in guide
    assert "mock-only" in guide
    assert "Creators do not install Python" in normalized
    assert "SUPABASE_ACCESS_TOKEN" in guide
    assert "SUPABASE_DB_PASSWORD" in guide
    assert "SUPABASE_EXAM_KEYS_B64" in guide
    assert "SUPABASE_PUBLISHABLE_KEY" in guide
    assert "contentengine-private" in guide
    assert "Do not promise external invitation delivery until custom SMTP" in guide
    assert "2 messages per hour" in guide
    assert "30-messages-per-hour" in guide
    assert "four modules plus the 12-scenario" in normalized
    assert "127.0.0.1" in guide
    assert "not a production deployment method" in normalized
    assert "Render" not in guide


def test_creator_templates_never_offer_localhost_or_local_mock_workflows() -> None:
    template_root = ROOT / "app" / "templates"
    forbidden = ("http://127.0.0.1", "http://localhost", "Mock local", "локаль")
    for path in template_root.glob("*.html"):
        content = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in content, (
                f"{path.name} exposes creator-local marker {marker!r}"
            )
