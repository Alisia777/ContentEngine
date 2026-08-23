from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "staging_workbench.py"
PRODUCTION_CONFIG = ROOT / "web" / "app" / "config.js"
STAGING_REF = "stagingworkbench1234"
STAGING_URL = f"https://{STAGING_REF}.supabase.co"
PUBLISHABLE_KEY = "sb_publishable_browser_safe_fixture_1234567890"


def load_module():
    spec = importlib.util.spec_from_file_location("staging_workbench", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_values() -> dict[str, str]:
    return {
        "STAGING_SUPABASE_PROJECT_REF": STAGING_REF,
        "STAGING_SUPABASE_URL": STAGING_URL,
        "STAGING_SUPABASE_PUBLISHABLE_KEY": PUBLISHABLE_KEY,
    }


def test_build_generates_only_safe_staging_config_and_preserves_production(
    tmp_path: Path,
) -> None:
    module = load_module()
    before = PRODUCTION_CONFIG.read_bytes()
    output = tmp_path / "site"
    config_path = module.build_staging_site(
        module.validate_staging_settings(valid_values()),
        source_dir=ROOT / "web" / "app",
        output_dir=output,
    )

    assert config_path == output / "config.js"
    assert (output / "index.html").is_file()
    assert PRODUCTION_CONFIG.read_bytes() == before
    assert list(output.rglob("config.js")) == [config_path]
    config = module.validate_generated_config(config_path)
    assert config["SUPABASE_URL"] == STAGING_URL
    assert config["SUPABASE_PUBLISHABLE_KEY"] == PUBLISHABLE_KEY
    assert config["MOCK_ENABLED"] is True
    assert config["REAL_GENERATION_ENABLED"] is False
    assert config["ALLOW_REAL_SPEND"] is False
    assert config["CREATOR_GENERATE_MOCK_ONLY"] is True
    assert config["CHARACTER_PERFORMANCE_ENABLED"] is False
    assert module.PRODUCTION_PROJECT_REF not in config_path.read_text(
        encoding="utf-8"
    )


def test_generated_config_parses_with_node(tmp_path: Path) -> None:
    module = load_module()
    node = module._find_executable("node")
    config_path = module.build_staging_site(
        module.validate_staging_settings(valid_values()),
        source_dir=ROOT / "web" / "app",
        output_dir=tmp_path / "site",
    )
    completed = subprocess.run(
        [node, "--check", str(config_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_staging_test_uses_repository_venv_interpreter(tmp_path: Path) -> None:
    module = load_module()
    windows_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    posix_python = tmp_path / ".venv" / "bin" / "python"
    windows_python.parent.mkdir(parents=True)
    posix_python.parent.mkdir(parents=True)
    windows_python.touch()
    posix_python.touch()

    assert module.staging_test_python_executable(
        root=tmp_path,
        platform_name="nt",
    ) == str(windows_python.resolve())
    assert module.staging_test_python_executable(
        root=tmp_path,
        platform_name="posix",
    ) == str(posix_python.resolve())

    windows_python.unlink()
    posix_python.unlink()
    with pytest.raises(SystemExit, match="repository .venv"):
        module.staging_test_python_executable(root=tmp_path)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"STAGING_SUPABASE_URL": "http://127.0.0.1:54321"},
            "loopback",
        ),
        (
            {
                "STAGING_SUPABASE_PROJECT_REF": "iyckwryrucqrxwlowxow",
                "STAGING_SUPABASE_URL": (
                    "https://iyckwryrucqrxwlowxow.supabase.co"
                ),
            },
            "production",
        ),
        (
            {
                "STAGING_SUPABASE_URL": (
                    "https://differentproject123.supabase.co"
                )
            },
            "matching HTTPS project origin",
        ),
        (
            {"STAGING_SUPABASE_PUBLISHABLE_KEY": "sb_secret_server_value_123456"},
            "server credential",
        ),
        (
            {"STAGING_SUPABASE_PUBLISHABLE_KEY": "service_role_unsafe_value"},
            "server credential",
        ),
        (
            {
                "STAGING_SUPABASE_PUBLISHABLE_KEY": (
                    "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiJ9."
                    "signaturefixture123"
                )
            },
            "JWT",
        ),
        (
            {
                "STAGING_SUPABASE_PUBLISHABLE_KEY": (
                    "sb_publishable_REPLACE_WITH_STAGING_KEY"
                )
            },
            "placeholder",
        ),
    ],
)
def test_settings_reject_unsafe_coordinates(
    updates: dict[str, str],
    message: str,
) -> None:
    module = load_module()
    values = valid_values()
    values.update(updates)
    with pytest.raises(ValueError, match=message):
        module.validate_staging_settings(values)


def test_env_reader_allows_only_three_public_fields(tmp_path: Path) -> None:
    module = load_module()
    env_file = tmp_path / ".env.staging"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in valid_values().items())
        + "\n",
        encoding="utf-8",
    )
    assert module.read_staging_env(env_file) == valid_values()

    env_file.write_text(
        env_file.read_text(encoding="utf-8")
        + "SUPABASE_SERVICE_ROLE_KEY=service_role_forbidden\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="server credential field"):
        module.read_staging_env(env_file)


def test_staging_compose_is_static_loopback_only() -> None:
    compose = (ROOT / "docker-compose.staging.yml").read_text(encoding="utf-8")
    assert "staging-web:" in compose
    assert '"127.0.0.1:8768:80"' in compose
    assert "./.local/staging/site:/usr/share/nginx/html:ro" in compose
    assert "./dev/nginx.staging.conf:/etc/nginx/conf.d/default.conf:ro" in compose
    assert "\n  app:" not in compose
    assert "worker:" not in compose
    assert "provider" not in compose.lower()
    assert "supabase" not in compose.lower()


def test_staging_command_surface_and_ignored_runtime_env() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for command in (
        "staging-build",
        "staging-up",
        "staging-down",
        "staging-status",
        "staging-test",
    ):
        assert f"{command}:" in makefile
        assert f"staging_workbench.py {command}" in makefile

    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env.*" in ignore
    assert "!.env.staging.example" in ignore
    assert "!.env.staging\n" not in ignore


def test_scaffold_contains_no_remote_mutation_or_paid_authority() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    source_lower = source.lower()
    for forbidden in (
        "supabase link",
        "supabase db push",
        "supabase functions deploy",
        "creator-generate",
        "requests.post",
        "urllib.request",
    ):
        assert forbidden not in source_lower
    assert '"REAL_GENERATION_ENABLED": False' in source
    assert '"ALLOW_REAL_SPEND": False' in source
    assert '"CHARACTER_PERFORMANCE_ENABLED": False' in source


def test_nginx_disables_cache_for_generated_config() -> None:
    nginx = (ROOT / "dev" / "nginx.staging.conf").read_text(encoding="utf-8")
    assert "location = /config.js" in nginx
    assert 'Cache-Control "no-store, no-cache, must-revalidate"' in nginx
    assert "try_files $uri $uri/ /index.html" in nginx
