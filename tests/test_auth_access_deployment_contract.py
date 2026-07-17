from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads(
    (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
)
CI = yaml.safe_load(
    (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
)
DEPLOY = yaml.safe_load(
    (ROOT / ".github" / "workflows" / "supabase-pages.yml").read_text(
        encoding="utf-8"
    )
)
DNS_HEALTH = yaml.safe_load(
    (ROOT / ".github" / "workflows" / "auth-email-health.yml").read_text(
        encoding="utf-8"
    )
)


def _steps(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def test_access_and_webhook_authentication_modes_fail_closed() -> None:
    assert CONFIG["functions"]["creator-access"]["verify_jwt"] is True
    assert CONFIG["functions"]["auth-email-webhook"]["verify_jwt"] is False

    ci_source = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    for path in (
        "supabase/functions/creator-access/index.ts",
        "supabase/functions/auth-email-webhook/index.ts",
    ):
        assert path in ci_source
    assert '"creator-access"' in ci_source
    assert '"auth-email-webhook"' in ci_source


def test_production_deploys_both_functions_with_reviewed_modes() -> None:
    steps = _steps(DEPLOY, "migrate")
    access = next(
        step
        for step in steps
        if step.get("name") == "Deploy authenticated account access function"
    )
    webhook = next(
        step
        for step in steps
        if step.get("name") == "Deploy signed email delivery webhook"
    )
    assert "creator-access" in access["run"]
    assert "--no-verify-jwt" not in access["run"]
    assert "auth-email-webhook" in webhook["run"]
    assert "--no-verify-jwt" in webhook["run"]
    assert "--prune" not in access["run"]
    assert "--prune" not in webhook["run"]


def test_optional_webhook_secret_is_masked_and_never_required_for_deploy() -> None:
    step = next(
        step
        for step in _steps(DEPLOY, "migrate")
        if step.get("name") == "Synchronize optional signed email webhook secret"
    )
    assert step["env"]["RESEND_WEBHOOK_SECRET"] == (
        "${{ secrets.RESEND_WEBHOOK_SECRET }}"
    )
    assert 'echo "::add-mask::$RESEND_WEBHOOK_SECRET"' in step["run"]
    assert 'if [ -z "${RESEND_WEBHOOK_SECRET:-}" ]' in step["run"]
    assert "supabase secrets list" in step["run"]
    assert "--output json" in step["run"]
    assert 'value.get("name") == "RESEND_WEBHOOK_SECRET"' in step["run"]
    assert "supabase secrets unset RESEND_WEBHOOK_SECRET" in step["run"]
    assert "python scripts/validate_resend_webhook_secret.py" in step["run"]
    assert step["run"].index(
        "python scripts/validate_resend_webhook_secret.py"
    ) < step["run"].index("supabase secrets set")
    assert 'RESEND_WEBHOOK_SECRET="$RESEND_WEBHOOK_SECRET"' in step["run"]
    assert "echo $RESEND_WEBHOOK_SECRET" not in step["run"]


def test_auth_email_readiness_is_daily_and_fails_closed_when_unconfigured() -> None:
    assert DNS_HEALTH[True]["schedule"][0]["cron"] == "17 4 * * *"
    job = DNS_HEALTH["jobs"]["readiness"]
    assert job["environment"] == "production"
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["env"]["EXPECTED_SUPABASE_PROJECT_REF"] == (
        "iyckwryrucqrxwlowxow"
    )
    checkout = next(
        step
        for step in job["steps"]
        if str(step.get("name", "")).startswith("Check out")
    )
    assert checkout["with"]["ref"] == "main"
    assert checkout["with"]["persist-credentials"] is False
    source = (ROOT / ".github" / "workflows" / "auth-email-health.yml").read_text(
        encoding="utf-8"
    )
    for variable in (
        "SUPABASE_PROJECT_REF",
        "SUPABASE_ACCESS_TOKEN",
        "SMTP_ADMIN_EMAIL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "SMTP_SENDER_NAME",
        "RESEND_WEBHOOK_SECRET",
        "AUTH_EMAIL_SENDING_DOMAIN",
        "AUTH_EMAIL_DKIM_SELECTOR",
        "AUTH_EMAIL_EXPECTED_SPF_INCLUDE",
        "AUTH_EMAIL_DKIM_RECORD_TYPE",
        "AUTH_EMAIL_EXPECTED_DKIM_VALUE",
    ):
        assert variable in source
    assert "configured=false" not in source
    assert "Production Auth email is not ready" in source
    assert "exit 1" in source
    assert (
        'if [ "$SUPABASE_PROJECT_REF" != "$EXPECTED_SUPABASE_PROJECT_REF" ]'
        in source
    )
    assert "::add-mask::" not in source
    assert "scripts/validate_resend_webhook_secret.py" in source
    assert "scripts/validate_auth_dns.py" in source
    assert "scripts/configure_supabase_auth_smtp.py --check-only" in source
    assert source.index("scripts/validate_resend_webhook_secret.py") < source.index(
        "scripts/validate_auth_dns.py"
    )
    assert source.index("scripts/validate_auth_dns.py") < source.index(
        "scripts/configure_supabase_auth_smtp.py --check-only"
    )
