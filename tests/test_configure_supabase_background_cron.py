from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import scripts.configure_supabase_background_cron as cron_config
from scripts.configure_supabase_background_cron import (
    BackgroundCronSettings,
    CRON_JOB_NAME,
    CRON_SCHEDULE,
    VAULT_URL_SECRET_NAME,
    VAULT_WORKER_SECRET_NAME,
    build_configuration_sql,
    configure_background_cron,
)
from scripts.deploy_supabase_management_api import (
    ConfigurationError,
    DeploymentError,
    EXPECTED_PROJECT_REF,
)


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "supabase-pages.yml"
WATCHDOG_WORKFLOW = ROOT / ".github" / "workflows" / "background-worker.yml"
SCHEDULER_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202607170001_native_worker_scheduler_watchdog.sql"
)
TEST_ACCESS_TOKEN = "management-test-token"
TEST_WORKER_SECRET = "worker-secret-with-single-quote-'" + "x" * 24


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "SUPABASE_PROJECT_REF": EXPECTED_PROJECT_REF,
        "SUPABASE_ACCESS_TOKEN": TEST_ACCESS_TOKEN,
        "CONTENTENGINE_WORKER_SECRET": TEST_WORKER_SECRET,
    }
    values.update(overrides)
    return values


def _settings() -> BackgroundCronSettings:
    return BackgroundCronSettings.from_environment(_environment())


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def execute(self, sql: str, *, read_only: bool = False) -> object:
        self.calls.append((sql, read_only))
        return []


def test_settings_are_bound_to_reviewed_project_and_derive_exact_worker_url() -> None:
    settings = _settings()

    assert settings.project_ref == EXPECTED_PROJECT_REF
    assert settings.worker_url == (
        f"https://{EXPECTED_PROJECT_REF}.supabase.co/functions/v1/"
        "creator-background-worker"
    )
    assert TEST_ACCESS_TOKEN not in repr(settings)
    assert TEST_WORKER_SECRET not in repr(settings)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"SUPABASE_PROJECT_REF": "aaaaaaaaaaaaaaaaaaaa"}, "reviewed production"),
        ({"SUPABASE_ACCESS_TOKEN": ""}, "SUPABASE_ACCESS_TOKEN"),
        ({"CONTENTENGINE_WORKER_SECRET": "too-short"}, "32 to 512"),
        ({"CONTENTENGINE_WORKER_SECRET": " " + "x" * 32}, "32 to 512"),
        ({"CONTENTENGINE_WORKER_SECRET": "x" * 31 + "\n"}, "32 to 512"),
    ],
)
def test_settings_fail_closed_before_any_management_request(
    override: dict[str, str], message: str
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        BackgroundCronSettings.from_environment(_environment(**override))


def test_sql_atomically_upserts_vault_and_replaces_one_named_native_cron() -> None:
    settings = _settings()
    sql = build_configuration_sql(settings)

    assert sql.startswith("begin;")
    assert sql.endswith("commit;")
    assert "pg_advisory_xact_lock" in sql
    assert "create extension if not exists pg_cron with schema pg_catalog" in sql
    assert "create extension if not exists pg_net with schema extensions" in sql
    assert "to_regclass('vault.secrets')" in sql
    assert "vault.create_secret" in sql
    assert "vault.update_secret" in sql
    assert VAULT_URL_SECRET_NAME in sql
    assert VAULT_WORKER_SECRET_NAME in sql
    assert "from cron.job job" in sql
    assert "perform cron.unschedule(existing_job.jobid)" in sql
    assert "perform cron.schedule(" in sql
    assert CRON_JOB_NAME in sql
    assert CRON_SCHEDULE in sql
    assert "background_cron_vault_postcondition_failed" in sql
    assert "background_cron_job_postcondition_failed" in sql
    assert "from cron.job job" in sql
    assert "and job.active" in sql
    assert "position('contentengine_background_worker_url' in job.command) > 0" in sql
    assert (
        "position('contentengine_background_worker_secret' in job.command) > 0" in sql
    )
    assert "in job.command) = 0" in sql

    command = sql.split("$contentengine_worker_command$", 2)[1]
    assert "select net.http_post(" in command
    assert "vault.decrypted_secrets" in command
    assert "x-contentengine-internal-worker" in command
    assert "x-contentengine-worker-secret" in command
    assert '"generation_limit":4' in command
    assert '"research_limit":1' in command
    assert '"review_limit":1' in command
    assert "timeout_milliseconds := 150000" in command
    assert settings.worker_secret not in command
    assert settings.worker_url not in command

    # The secret is present only in the protected Vault upsert and SQL quotes
    # are escaped before the Management API request is constructed.
    assert TEST_WORKER_SECRET not in sql
    assert TEST_WORKER_SECRET.replace("'", "''") in sql


def test_configuration_is_one_deterministic_write_and_safe_to_repeat() -> None:
    settings = _settings()
    client = RecordingClient()

    configure_background_cron(settings, client=client)
    configure_background_cron(settings, client=client)

    assert len(client.calls) == 2
    assert client.calls[0] == client.calls[1]
    assert client.calls[0][1] is False


def test_configurator_migration_and_runbook_share_one_vault_contract() -> None:
    migration = SCHEDULER_MIGRATION.read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "BACKGROUND_WORKER_OPERATIONS.md").read_text(
        encoding="utf-8"
    )

    for name in (VAULT_URL_SECRET_NAME, VAULT_WORKER_SECRET_NAME):
        assert name in migration
        assert name in runbook
    assert "contentengine_worker_url" not in migration
    assert "contentengine_worker_secret" not in migration
    assert CRON_JOB_NAME in migration
    assert CRON_SCHEDULE in migration


def test_dry_run_and_failure_output_never_reveal_protected_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key, value in _environment().items():
        monkeypatch.setenv(key, value)

    assert cron_config.main(["--dry-run"]) == 0
    dry_output = capsys.readouterr()
    assert TEST_ACCESS_TOKEN not in dry_output.out + dry_output.err
    assert TEST_WORKER_SECRET not in dry_output.out + dry_output.err

    class FailingClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def execute(self, _sql: str, *, read_only: bool = False) -> object:
            del read_only
            raise DeploymentError("Supabase Management API request failed")

    monkeypatch.setattr(cron_config, "ManagementApiClient", FailingClient)
    assert cron_config.main([]) == 1
    failed_output = capsys.readouterr()
    assert TEST_ACCESS_TOKEN not in failed_output.out + failed_output.err
    assert TEST_WORKER_SECRET not in failed_output.out + failed_output.err
    assert settings_secret_not_in_environment_dump() is True


def settings_secret_not_in_environment_dump() -> bool:
    """Guard against tests accidentally adding an environment-printing path."""

    source = Path(cron_config.__file__).read_text(encoding="utf-8")
    return "print(os.environ" not in source and "print(settings" not in source


def test_deploy_wires_native_cron_immediately_after_worker_deploy() -> None:
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["migrate"]["steps"]
    names = [step.get("name") for step in steps]
    worker_index = names.index("Deploy secret-authenticated background worker function")
    cron_index = names.index("Configure native Supabase background worker cron")

    assert cron_index == worker_index + 1
    cron_step = steps[cron_index]
    assert cron_step["env"] == {
        "SUPABASE_ACCESS_TOKEN": "${{ secrets.SUPABASE_ACCESS_TOKEN }}",
        "CONTENTENGINE_WORKER_SECRET": "${{ secrets.CONTENTENGINE_WORKER_SECRET }}",
    }
    assert cron_step["run"] == "python scripts/configure_supabase_background_cron.py"


def test_actions_schedule_is_only_hourly_provider_free_health_watchdog() -> None:
    text = WATCHDOG_WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on") or workflow.get(True)

    assert triggers["schedule"] == [{"cron": "17 * * * *"}]
    assert "workflow_dispatch" in triggers
    assert "inputs" not in (triggers["workflow_dispatch"] or {})
    assert (
        'payload=\'{"generation_limit":0,"research_limit":0,"review_limit":0}\'' in text
    )
    assert '"generation_limit":4' not in text
    assert '"research_limit":1' not in text
    assert '"review_limit":1' not in text
    assert "SMOKE_ONLY" not in text
    assert "inputs.smoke_only" not in text
    assert "x-contentengine-worker-secret" in text
    assert "creator-background-worker" in text
