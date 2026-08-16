from __future__ import annotations

import os
from pathlib import Path
import json
import subprocess
import sys

import pytest

from scripts import dev_workbench


ROOT = Path(__file__).resolve().parents[1]


def test_local_profile_is_fail_closed_and_production_config_is_not_edited() -> None:
    compose = (ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
    example = (ROOT / ".env.local.example").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "dev_workbench.py").read_text(encoding="utf-8")
    assert 'QVF_ALLOW_REAL_SPEND: "false"' in compose
    assert "QVF_GENERATION_MODE: mock" in compose
    assert './dev/nginx.local.conf:/etc/nginx/conf.d/default.conf:ro' in compose
    nginx = (ROOT / "dev" / "nginx.local.conf").read_text(encoding="utf-8")
    assert 'Cache-Control "no-store, no-cache, must-revalidate"' in nginx
    assert "QVF_CREATOR_GENERATE_MOCK_ONLY=true" in example
    assert 'ROOT / "web" / "app", LOCAL_SITE' in script
    assert 'LOCAL_SITE / "config.js"' in script
    assert '"LOCAL_DEVELOPMENT": True' in script
    assert '"LOCAL_SUPABASE_ORIGIN": local_api_origin' in script
    assert "local-workbench={local_revision}" in script
    assert "Local Supabase API URL must be a loopback HTTP origin" in script
    assert "local_realtime_origin" in script
    assert '.replace("; upgrade-insecure-requests", "")' in script
    assert 'LOCAL_OWNER_CREDENTIALS = LOCAL / "owner.local.json"' in script
    assert 'LOCAL_PROJECT = LOCAL / "project.local.json"' in script
    assert '"email": "owner@contentengine.test"' in script
    assert "secrets.token_urlsafe" in script
    assert '"password": "' not in script
    assert "def provision_local_owner() -> str" in script
    assert '"creator_create_workspace_project"' in script
    assert '"idempotency_key": "local-workbench-project-v1"' in script
    assert 'json.dumps({"project_id": project_id}' in script
    assert '"Authorization": f"Bearer {access_token}"' in script
    assert "Authenticated local RPC requires a loopback HTTP origin" in script
    assert "def ensure_local_edge_runtime()" in script
    assert 'LOCAL_EDGE_RUNTIME_CONTAINER = "supabase_edge_runtime_contentengine-local"' in script
    assert 'LOCAL_KONG_CONTAINER = "supabase_kong_contentengine-local"' in script
    assert 'payload.get("message") == "ok"' in script
    assert "content_factory.training_access_waivers" in script
    assert "no training evidence is fabricated" in script
    assert "training_attempts" not in script
    assert '(LOCAL_SUPABASE / "functions" / ".env").write_text(' in script
    assert "web/app/config.js" not in script


def test_local_docker_and_browser_artifacts_stay_inside_project() -> None:
    compose = (ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "dev_workbench.py").read_text(encoding="utf-8")
    browser = (ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile.local").read_text(encoding="utf-8")

    assert compose.count("./.local/docker/media:/app/media") == 2
    assert compose.count("./.local/docker/data:/app/.local-data") == 2
    assert compose.count("QVF_DATABASE_URL: sqlite:////app/.local-data/qharisma.db") == 2
    assert compose.count("QVF_MEDIA_ROOT: /app/media") == 2
    assert "local-media:" not in compose
    assert "local-data:" not in compose
    assert "LOCAL_DOCKER_MEDIA = LOCAL_DOCKER / \"media\"" in script
    assert "LOCAL_DOCKER_DATA = LOCAL_DOCKER / \"data\"" in script
    assert "def ensure_local_docker_dirs()" in script
    prepare = script[script.index("def prepare_overlay()") : script.index("def supabase_args")]
    assert "ensure_local_docker_dirs()" in prepare
    assert "/app/.local-data" in dockerfile

    assert 'ROOT / ".dev-artifacts" / "browser-smoke" / "profiles"' in browser
    assert "dir=profiles_root" in browser
    assert "shutil.rmtree(profile, ignore_errors=True)" in browser
    assert "tempfile.mkdtemp(prefix=\"contentengine-browser-smoke-\")" not in browser


def test_desktop_accepts_only_explicit_fail_closed_loopback_overlay() -> None:
    app = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
    helpers = app[
        app.index("function isAllowedSupabaseOrigin") :
        app.index("function renderSetup")
    ]
    cases = [
        {
            "name": "cloud",
            "config": {
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_browser_safe_value",
                "STORAGE_BUCKET": "contentengine-private",
                "MOCK_ENABLED": True,
                "REAL_GENERATION_ENABLED": True,
            },
            "valid": True,
        },
        {
            "name": "local-safe",
            "config": {
                "LOCAL_DEVELOPMENT": True,
                "LOCAL_SUPABASE_ORIGIN": "http://127.0.0.1:54321",
                "SUPABASE_URL": "http://127.0.0.1:54321",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_browser_safe_value",
                "STORAGE_BUCKET": "contentengine-private",
                "MOCK_ENABLED": True,
                "REAL_GENERATION_ENABLED": False,
                "ALLOW_REAL_SPEND": False,
                "CREATOR_GENERATE_MOCK_ONLY": True,
            },
            "valid": True,
        },
        {
            "name": "local-without-flag",
            "config": {
                "SUPABASE_URL": "http://127.0.0.1:54321",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_browser_safe_value",
                "STORAGE_BUCKET": "contentengine-private",
                "MOCK_ENABLED": True,
                "REAL_GENERATION_ENABLED": False,
            },
            "valid": False,
        },
        {
            "name": "local-unsafe-spend",
            "config": {
                "LOCAL_DEVELOPMENT": True,
                "LOCAL_SUPABASE_ORIGIN": "http://localhost:54321",
                "SUPABASE_URL": "http://localhost:54321",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_browser_safe_value",
                "STORAGE_BUCKET": "contentengine-private",
                "MOCK_ENABLED": True,
                "REAL_GENERATION_ENABLED": True,
                "ALLOW_REAL_SPEND": True,
                "CREATOR_GENERATE_MOCK_ONLY": False,
            },
            "valid": False,
        },
        {
            "name": "local-remote-host",
            "config": {
                "LOCAL_DEVELOPMENT": True,
                "SUPABASE_URL": "http://attacker.example.test:54321",
                "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_browser_safe_value",
                "STORAGE_BUCKET": "contentengine-private",
                "MOCK_ENABLED": True,
                "REAL_GENERATION_ENABLED": False,
                "ALLOW_REAL_SPEND": False,
                "CREATOR_GENERATE_MOCK_ONLY": True,
            },
            "valid": False,
        },
    ]
    script = f"""
{helpers}
const cases = {json.dumps(cases)};
const results = cases.map((item) => ({{
  name: item.name,
  valid: validateConfig(item.config).length === 0,
}}));
process.stdout.write(JSON.stringify(results));
"""
    result = subprocess.run(
        ["node", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert json.loads(result.stdout) == [
        {"name": item["name"], "valid": item["valid"]} for item in cases
    ]


def test_local_supabase_overlay_has_auth_storage_migrations_and_edge() -> None:
    overlay = (ROOT / "supabase" / "config.local.toml").read_text(encoding="utf-8")
    assert 'site_url = "http://127.0.0.1:8767/"' in overlay
    assert '"http://localhost:8767/**"' in overlay
    assert "[storage]" in overlay
    assert "[db.migrations]" in overlay
    assert "[functions.creator-generate]" in overlay
    assert "verify_jwt = true" in overlay
    assert (ROOT / "supabase" / "migrations").is_dir()


def test_creator_generate_local_mode_cannot_start_provider_post() -> None:
    edge = (ROOT / "supabase" / "functions" / "creator-generate" / "index.ts").read_text(encoding="utf-8")
    gate = edge.index("function localMockOnlyResponse")
    dispatch = edge.index(
        "if (isInternalWorkerRequest(request))", edge.index("export default", gate)
    )
    assert edge.index("const localMock = await localMockOnlyResponse(request);", gate) < dispatch
    assert 'Deno.env.get("QVF_ALLOW_REAL_SPEND") !== "false"' in edge[gate:dispatch]
    assert "provider_call_started: false" in edge[gate:dispatch]
    assert 'if (isInternalWorkerRequest(request))' in edge[gate:dispatch]
    assert 'action === "strategy_start"' in edge[gate:dispatch]
    assert '"local_mock_paid_start_blocked"' in edge[gate:dispatch]


def test_creator_generate_local_mode_preserves_strict_free_action_contracts() -> None:
    edge = (ROOT / "supabase" / "functions" / "creator-generate" / "index.ts").read_text(encoding="utf-8")
    free_actions = edge[
        edge.index("const LOCAL_MOCK_FREE_ACTIONS") :
        edge.index("async function localMockOnlyResponse")
    ]
    gate = edge[
        edge.index("async function localMockOnlyResponse") :
        edge.index("export default")
    ]
    for action in (
        "model_catalog",
        "strategy_catalog",
        "strategy_bind",
        "strategy_media_probe",
        "strategy_preflight",
        "strategy_status",
        "preflight",
        "status",
        "reconcile",
    ):
        assert f'"{action}"' in free_actions
    assert "await request.clone().json()" in gate
    assert "if (LOCAL_MOCK_FREE_ACTIONS.has(action)) return null;" in gate
    assert '"start"' not in free_actions
    assert '"strategy_start"' not in free_actions


def test_character_performance_stays_feature_gated() -> None:
    example = (ROOT / ".env.local.example").read_text(encoding="utf-8")
    browser = (ROOT / "dev" / "browser" / "workbench.js").read_text(encoding="utf-8")
    assert "QVF_CHARACTER_PERFORMANCE_ENABLED=false" in example
    assert "config.CHARACTER_PERFORMANCE_ENABLED !== true" in browser
    assert "feature gated" in browser


def test_copy_e2e_fails_closed_before_media_work(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update({"QVF_ALLOW_REAL_SPEND": "true", "QVF_GENERATION_MODE": "real"})
    result = subprocess.run(
        [sys.executable, "scripts/local_copy_e2e.py", "--output-root", str(tmp_path)],
        cwd=ROOT, env=environment, text=True, capture_output=True,
    )
    assert result.returncode != 0
    assert "fail-closed" in result.stderr
    assert not list(tmp_path.glob("**/*.mp4"))


def test_required_dev_commands_and_three_browser_routes_exist() -> None:
    dev = (ROOT / "scripts" / "dev_workbench.py").read_text(encoding="utf-8")
    for command in ("dev-up", "dev-down", "dev-reset", "dev-test", "dev-browser-smoke", "dev-status"):
        assert f'"{command}"' in dev
    for command_body in (
        dev[dev.index("def dev_up()") : dev.index("def dev_down()")],
        dev[dev.index("def dev_reset()") : dev.index("def node_parse()")],
        dev[dev.index("def dev_test()") : dev.index("def dev_browser_smoke()")],
    ):
        assert 'run(supabase_args("start"))' in command_body
        assert "ensure_local_edge_runtime()" in command_body
        assert command_body.index('run(supabase_args("start"))') < command_body.index(
            "ensure_local_edge_runtime()"
        )
    browser = (ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")
    assert '("copy", "avatar", "strategy")' in browser
    for marker in (
        "#/workspace/generation",
        "#mock-batch-form",
        "[data-generation-intake-v4]",
        '"copy_video"',
        '"avatar_video"',
        '"strategy_video"',
        '"copy-product-swap.png"',
        '"avatar-character-performance.png"',
        '"strategy-viral-rebuild.png"',
        '"guidedStepCount": 6',
        '"strategyCatalogReady": True',
        '"strategyButtonCount": 3',
        "!form?.textContent.includes('object_required')",
        "config.ALLOW_REAL_SPEND === false",
        'LOCAL_DESKTOP_ORIGIN = "http://127.0.0.1:8767"',
        "else project_id",
        'data-ce-v4-finder-mode=\\"organize\\"',
        'data-ce-v4-finder-view=\\"list\\"',
        'data-action=\\"finder-upload\\"',
    ):
        assert marker in browser


def test_parallel_pytest_defaults_to_six_shards_in_ignored_scratch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QVF_DEV_TEST_SHARDS", raising=False)
    assert dev_workbench.pytest_shard_count() == 6
    assert dev_workbench.PYTEST_RUNS_RELATIVE.as_posix() == ".dev-artifacts/pytest-runs"
    assert ".dev-artifacts/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_pytest_interpreter_prefers_explicit_valid_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    override = tmp_path / "locked-python"
    override.write_bytes(b"test interpreter placeholder")
    monkeypatch.setenv("QVF_DEV_TEST_PYTHON", str(override))

    selected = dev_workbench.pytest_python_executable(
        root=project_root,
        platform_name="nt",
        fallback="fallback-python",
    )

    assert selected == str(override.resolve())


def test_pytest_interpreter_prefers_platform_local_venv_without_host_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("QVF_DEV_TEST_PYTHON", raising=False)
    windows_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    posix_python = tmp_path / ".venv" / "bin" / "python"
    windows_python.parent.mkdir(parents=True)
    posix_python.parent.mkdir(parents=True)
    windows_python.write_bytes(b"windows test interpreter placeholder")
    posix_python.write_bytes(b"posix test interpreter placeholder")

    assert dev_workbench.pytest_python_executable(
        root=tmp_path,
        platform_name="nt",
        fallback="fallback-python",
    ) == str(windows_python.resolve())
    assert dev_workbench.pytest_python_executable(
        root=tmp_path,
        platform_name="posix",
        fallback="fallback-python",
    ) == str(posix_python.resolve())


def test_pytest_interpreter_falls_back_when_project_venv_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("QVF_DEV_TEST_PYTHON", raising=False)
    assert dev_workbench.pytest_python_executable(
        root=tmp_path,
        platform_name="nt",
        fallback="controlled-fallback-python",
    ) == "controlled-fallback-python"


def test_supabase_cli_uses_only_the_cached_pinned_npx_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probes: list[tuple[list[str], int]] = []

    def probe(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        probes.append((args, timeout))
        return subprocess.CompletedProcess(args, 0, "2.109.1\n", "")

    dev_workbench._resolved_supabase_executable.cache_clear()
    monkeypatch.setattr(
        dev_workbench.shutil,
        "which",
        lambda name: "E:/tools/npx.cmd" if name == "npx" else None,
    )
    monkeypatch.setattr(dev_workbench, "_run_bounded_npx_probe", probe)

    expected = [
        "E:/tools/npx.cmd",
        "--yes",
        "--offline",
        f"supabase@{dev_workbench.SUPABASE_CLI_VERSION}",
    ]
    assert dev_workbench.supabase_executable() == expected
    assert dev_workbench.supabase_executable() == expected
    assert probes == [
        (expected + ["--version"], dev_workbench.SUPABASE_CLI_CACHE_TIMEOUT_SECONDS)
    ]
    dev_workbench._resolved_supabase_executable.cache_clear()


def test_supabase_cli_cold_bootstrap_is_pinned_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probes: list[tuple[list[str], int]] = []

    def probe(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        probes.append((args, timeout))
        return subprocess.CompletedProcess(args, 1 if len(probes) == 1 else 0, "", "cache miss")

    dev_workbench._resolved_supabase_executable.cache_clear()
    monkeypatch.setattr(
        dev_workbench.shutil,
        "which",
        lambda name: "E:/tools/npx.cmd" if name == "npx" else None,
    )
    monkeypatch.setattr(dev_workbench, "_run_bounded_npx_probe", probe)

    assert dev_workbench.supabase_executable() == [
        "E:/tools/npx.cmd",
        "--yes",
        "--offline",
        f"supabase@{dev_workbench.SUPABASE_CLI_VERSION}",
    ]
    package = f"supabase@{dev_workbench.SUPABASE_CLI_VERSION}"
    assert probes == [
        (
            ["E:/tools/npx.cmd", "--yes", "--offline", package, "--version"],
            dev_workbench.SUPABASE_CLI_CACHE_TIMEOUT_SECONDS,
        ),
        (
            ["E:/tools/npx.cmd", "--yes", package, "--version"],
            dev_workbench.SUPABASE_CLI_BOOTSTRAP_TIMEOUT_SECONDS,
        ),
    ]
    dev_workbench._resolved_supabase_executable.cache_clear()


def test_supabase_cli_cold_bootstrap_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_probe(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "registry unavailable")

    dev_workbench._resolved_supabase_executable.cache_clear()
    monkeypatch.setattr(
        dev_workbench.shutil,
        "which",
        lambda name: "E:/tools/npx.cmd" if name == "npx" else None,
    )
    monkeypatch.setattr(dev_workbench, "_run_bounded_npx_probe", failed_probe)

    with pytest.raises(SystemExit, match=r"2\.109\.1 bootstrap failed.*registry unavailable"):
        dev_workbench.supabase_executable()
    dev_workbench._resolved_supabase_executable.cache_clear()


def test_supabase_cli_probe_timeout_terminates_its_owned_process_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminated: list[object] = []

    class HungProcess:
        pid = 4242
        returncode = -9

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.calls = 0

        def communicate(self, timeout: int | None = None) -> tuple[str, str]:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("npx", timeout)
            return "", ""

        def kill(self) -> None:
            raise AssertionError("the tree terminator owns process cleanup")

    monkeypatch.setattr(dev_workbench.subprocess, "Popen", HungProcess)
    monkeypatch.setattr(
        dev_workbench,
        "_terminate_process_tree",
        lambda process: terminated.append(process),
    )

    with pytest.raises(SystemExit, match=r"Timed out after 7s.*process tree"):
        dev_workbench._run_bounded_npx_probe(["npx", "--version"], timeout=7)
    assert len(terminated) == 1


def test_write_local_site_propagates_cli_bootstrap_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def unavailable_supabase(*_args: str) -> list[str]:
        raise SystemExit("bootstrap failed")

    monkeypatch.setattr(dev_workbench, "LOCAL", tmp_path / ".local")
    monkeypatch.setattr(dev_workbench, "LOCAL_SITE", tmp_path / ".local" / "site")
    monkeypatch.setattr(dev_workbench, "supabase_args", unavailable_supabase)

    with pytest.raises(SystemExit, match="bootstrap failed"):
        dev_workbench.write_local_site()


def test_dev_test_runs_parallel_hermetic_shards_and_aggregates_reports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shard_total = 3
    launches: list[dict[str, object]] = []

    class FakeProcess:
        def __init__(self, args: list[str], **kwargs: object) -> None:
            environment = kwargs["env"]
            assert isinstance(environment, dict)
            shard_index = int(environment["QVF_PYTEST_SHARD_INDEX"])
            junit_argument = next(
                argument for argument in args if argument.startswith("--junitxml=")
            )
            junit_path = Path(junit_argument.split("=", 1)[1])
            junit_path.write_text(
                '<testsuites><testsuite tests="2" failures="0" errors="0" '
                'skipped="0" time="1.25" /></testsuites>',
                encoding="utf-8",
            )
            output = kwargs["stdout"]
            output.write("2 passed, 4 deselected in 1.25s\n")
            output.flush()
            self.returncode = 0
            launches.append({
                "args": args,
                "environment": environment,
                "shell": kwargs["shell"],
                "shard_index": shard_index,
            })

        def wait(self, timeout: int | None = None) -> int:
            assert len(launches) == shard_total
            return self.returncode

        def poll(self) -> int:
            return self.returncode

        def terminate(self) -> None:
            raise AssertionError("successful fake shard must not be terminated")

        def kill(self) -> None:
            raise AssertionError("successful fake shard must not be killed")

    monkeypatch.setattr(dev_workbench, "pytest_scratch_root", lambda: tmp_path)
    monkeypatch.setattr(dev_workbench, "pytest_shard_count", lambda: shard_total)
    monkeypatch.setattr(
        dev_workbench,
        "pytest_python_executable",
        lambda: "locked-test-python",
    )
    monkeypatch.setattr(dev_workbench.subprocess, "Popen", FakeProcess)

    report = dev_workbench.run_parallel_pytest()

    assert report["status"] == "passed"
    assert report["shards"] == shard_total
    assert report["aggregate"] == {
        "tests": 6,
        "passed": 6,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "duration_seconds": 3.75,
    }
    environments = [launch["environment"] for launch in launches]
    assert all(launch["shell"] is False for launch in launches)
    assert all(
        launch["args"][:6]
        == [
            "locked-test-python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "scripts.pytest_shard_plugin",
        ]
        for launch in launches
    )
    assert {environment["QVF_PYTEST_SHARD_INDEX"] for environment in environments} == {
        "0",
        "1",
        "2",
    }
    assert all(environment["QVF_PYTEST_SHARD_TOTAL"] == "3" for environment in environments)
    assert all(environment["QVF_ALLOW_REAL_SPEND"] == "false" for environment in environments)
    for environment in environments:
        assert environment["TEMP"] == environment["TMP"] == environment["TMPDIR"]
        assert Path(environment["TEMP"]).is_relative_to(tmp_path)
        assert Path(environment["QVF_MEDIA_ROOT"]).is_relative_to(tmp_path)
        assert environment["QVF_DATABASE_URL"].startswith("sqlite:///")
        assert str(tmp_path).replace("\\", "/") in environment["QVF_DATABASE_URL"]
    assert len({environment["TEMP"] for environment in environments}) == shard_total
    assert len({environment["QVF_MEDIA_ROOT"] for environment in environments}) == shard_total
    assert len({environment["QVF_DATABASE_URL"] for environment in environments}) == shard_total
    assert all(Path(result["log"]).is_file() for result in report["shard_results"])
    assert all(Path(result["junit"]).is_file() for result in report["shard_results"])


def test_parallel_pytest_retains_logs_and_fails_when_one_shard_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    launches: list[int] = []

    class FakeProcess:
        def __init__(self, args: list[str], **kwargs: object) -> None:
            environment = kwargs["env"]
            assert isinstance(environment, dict)
            shard_index = int(environment["QVF_PYTEST_SHARD_INDEX"])
            junit_argument = next(
                argument for argument in args if argument.startswith("--junitxml=")
            )
            junit_path = Path(junit_argument.split("=", 1)[1])
            failures = 1 if shard_index == 1 else 0
            junit_path.write_text(
                '<testsuites><testsuite tests="2" '
                f'failures="{failures}" errors="0" skipped="0" time="1" />'
                "</testsuites>",
                encoding="utf-8",
            )
            output = kwargs["stdout"]
            output.write(
                "1 passed, 1 failed, 2 deselected in 1.00s\n"
                if failures
                else "2 passed, 2 deselected in 1.00s\n"
            )
            output.flush()
            self.returncode = 1 if failures else 0
            launches.append(shard_index)

        def wait(self, timeout: int | None = None) -> int:
            assert launches == [0, 1]
            return self.returncode

        def poll(self) -> int:
            return self.returncode

        def terminate(self) -> None:
            raise AssertionError("completed fake shard must not be terminated")

        def kill(self) -> None:
            raise AssertionError("completed fake shard must not be killed")

    monkeypatch.setattr(dev_workbench, "pytest_scratch_root", lambda: tmp_path)
    monkeypatch.setattr(dev_workbench, "pytest_shard_count", lambda: 2)
    monkeypatch.setattr(
        dev_workbench,
        "pytest_python_executable",
        lambda: "locked-test-python",
    )
    monkeypatch.setattr(dev_workbench.subprocess, "Popen", FakeProcess)

    with pytest.raises(SystemExit, match=r"failed in shard\(s\) 2; retained logs"):
        dev_workbench.run_parallel_pytest()

    output = capsys.readouterr().out
    assert '"status": "failed"' in output
    assert '"tests": 4' in output
    assert '"passed": 3' in output
    assert '"failures": 1' in output
    assert len(list(tmp_path.glob("*/shard-*/pytest.log"))) == 2


def test_browser_smoke_can_verify_live_finder_controls_for_a_local_project() -> None:
    browser = (ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")
    for marker in (
        'parser.add_argument("--finder-project-id"',
        "finder-mode",
        "finder-view",
        "finder-upload",
        "Finder organize control did not switch the route",
        "Finder list control did not switch the layout",
        "Finder upload control did not open the media route",
        'output / "finder-controls-local.png"',
    ):
        assert marker in browser


def test_browser_smoke_login_wait_matches_desktop_startup_contract_and_is_diagnostic() -> None:
    browser = (ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")
    assert "LOGIN_READY_TIMEOUT_SECONDS = 30" in browser
    assert "desktop-login-timeout.png" in browser
    assert "desktop_login_diagnostics" in browser
    assert "Runtime.consoleAPICalled" in browser
    assert "Network.loadingFailed" in browser
    assert "Desktop did not reach the local login screen within" in browser


def test_agents_guardrails_are_explicit() -> None:
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for phrase in (
        "only authority allowed to start a paid generation",
        "Do not add a second spend ledger",
        "Never issue a real provider `POST`",
        "Never commit secrets",
        "Never disable, skip, weaken, delete, or rewrite tests",
    ):
        assert phrase in rules
