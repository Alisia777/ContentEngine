from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = (ROOT / "docs" / "BACKGROUND_WORKER_OPERATIONS.md").read_text(
    encoding="utf-8"
)
CLOUD_GUIDE = (ROOT / "docs" / "CLOUD_DEPLOYMENT.md").read_text(
    encoding="utf-8"
)


def test_runbook_documents_the_browser_independent_supabase_scheduler() -> None:
    for marker in (
        "contentengine-background-worker-v1",
        "every two minutes",
        "pg_net",
        "Supabase Vault",
        "The browser is not part of this path",
        "never repeats the paid create request",
        "database lease",
        "stalled",
        "cron.job_run_details",
    ):
        assert marker in RUNBOOK


def test_runbook_names_only_the_reviewed_vault_secret_aliases() -> None:
    assert "contentengine_background_worker_url" in RUNBOOK
    assert "contentengine_background_worker_secret" in RUNBOOK
    assert "RUNWAYML_API_SECRET=" not in RUNBOOK
    assert "OPENAI_API_KEY=" not in RUNBOOK
    assert "sb_secret_" not in RUNBOOK


def test_cloud_guide_no_longer_claims_github_is_the_production_timer() -> None:
    durable_section = CLOUD_GUIDE.split(
        "### Durable background work and notification delivery", 1
    )[1].split("## Existing paid Supabase project", 1)[0]
    assert "Supabase Cron" in durable_section
    assert "every two minutes" in durable_section
    assert "browser and GitHub scheduler are not" in durable_section
    assert "runs every five minutes" not in durable_section
    assert "BACKGROUND_WORKER_OPERATIONS.md" in durable_section
