from pathlib import Path
import importlib.util
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "configure_supabase_auth_smtp.py"
DNS_SCRIPT_PATH = ROOT / "scripts" / "validate_auth_dns.py"
WORKFLOW = (ROOT / ".github" / "workflows" / "configure-auth-smtp.yml").read_text(
    encoding="utf-8"
)


def _module():
    spec = importlib.util.spec_from_file_location("configure_smtp", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _dns_module():
    spec = importlib.util.spec_from_file_location("validate_auth_dns", DNS_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _valid_environment() -> dict[str, str]:
    return {
        "SUPABASE_PROJECT_REF": "iyckwryrucqrxwlowxow",
        "SUPABASE_ACCESS_TOKEN": "sbp_private_management_token",
        "SMTP_ADMIN_EMAIL": "no-reply@auth.example.com",
        "SMTP_HOST": "smtp.provider.example",
        "SMTP_PORT": "587",
        "SMTP_USER": "smtp-user",
        "SMTP_PASS": "smtp-password",
        "SMTP_SENDER_NAME": "ALTEA",
    }


def test_smtp_payload_uses_secure_email_change_and_never_autoconfirms() -> None:
    module = _module()
    settings = module.SmtpSettings.from_environment(_valid_environment())

    assert settings.management_payload() == {
        "external_email_enabled": True,
        "mailer_secure_email_change_enabled": True,
        "mailer_autoconfirm": False,
        "smtp_admin_email": "no-reply@auth.example.com",
        "smtp_host": "smtp.provider.example",
        "smtp_port": 587,
        "smtp_user": "smtp-user",
        "smtp_pass": "smtp-password",
        "smtp_sender_name": "ALTEA",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("SUPABASE_PROJECT_REF", "wrong-project"),
        ("SMTP_ADMIN_EMAIL", "not-an-email"),
        ("SMTP_HOST", "https://smtp.example.com"),
        ("SMTP_PORT", "70000"),
        ("SMTP_USER", ""),
        ("SMTP_PASS", ""),
        ("SMTP_SENDER_NAME", "bad\nheader"),
    ],
)
def test_smtp_configuration_fails_closed_on_invalid_protected_input(
    field: str,
    value: str,
) -> None:
    module = _module()
    environment = _valid_environment()
    environment[field] = value

    with pytest.raises(module.SmtpConfigurationError):
        module.SmtpSettings.from_environment(environment)


def test_smtp_workflow_is_manual_protected_and_checks_dns_before_patch() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "environment: production" in WORKFLOW
    assert "github.ref == 'refs/heads/main'" in WORKFLOW
    assert "Verify public SPF, DKIM and DMARC records" in WORKFLOW
    assert "scripts/validate_auth_dns.py" in WORKFLOW
    assert "expected_spf_include:" in WORKFLOW
    assert "expected_dkim_value:" in WORKFLOW
    assert "dkim_record_type:" in WORKFLOW
    assert "DKIM_SELECTOR" in WORKFLOW
    assert WORKFLOW.index("Verify public SPF, DKIM and DMARC records") < WORKFLOW.index(
        "Configure Supabase Auth custom SMTP"
    )


def test_smtp_workflow_never_echoes_secret_values_or_accepts_them_as_inputs() -> None:
    inputs_block = WORKFLOW.split("permissions:", 1)[0]
    assert "SMTP_PASS" not in inputs_block
    assert "SMTP_USER" not in inputs_block
    assert "SUPABASE_ACCESS_TOKEN" not in inputs_block
    assert "echo $SMTP_PASS" not in WORKFLOW
    assert "echo $SMTP_USER" not in WORKFLOW
    assert "echo $SUPABASE_ACCESS_TOKEN" not in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW


def test_dns_validator_requires_exact_provider_records() -> None:
    module = _dns_module()

    answers = {
        ("TXT", "auth.example.com"): ('"v=spf1 include:spf.mail.example -all"\n'),
        ("TXT", "_dmarc.auth.example.com"): (
            '"v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"\n'
        ),
        ("TXT", "mail._domainkey.auth.example.com"): "",
        ("CNAME", "mail._domainkey.auth.example.com"): (
            "mail-auth.example.provider.\n"
        ),
    }

    module.validate_auth_dns(
        domain="auth.example.com",
        selector="mail",
        expected_spf_include="include:spf.mail.example",
        dkim_record_type="CNAME",
        expected_dkim_value="mail-auth.example.provider",
        lookup=lambda record_type, name: answers[(record_type, name)],
    )


@pytest.mark.parametrize(
    "root_txt",
    [
        '"v=spf1 -all"\n',
        (
            '"v=spf1 include:spf.mail.example -all"\n'
            '"v=spf1 include:legacy.example -all"\n'
        ),
    ],
)
def test_dns_validator_rejects_missing_provider_or_duplicate_spf(
    root_txt: str,
) -> None:
    module = _dns_module()
    answers = {
        ("TXT", "auth.example.com"): root_txt,
        ("TXT", "_dmarc.auth.example.com"): '"v=DMARC1; p=none"\n',
        ("TXT", "mail._domainkey.auth.example.com"): "",
        ("CNAME", "mail._domainkey.auth.example.com"): (
            "mail-auth.example.provider.\n"
        ),
    }

    with pytest.raises(module.DnsValidationError):
        module.validate_auth_dns(
            domain="auth.example.com",
            selector="mail",
            expected_spf_include="include:spf.mail.example",
            dkim_record_type="CNAME",
            expected_dkim_value="mail-auth.example.provider",
            lookup=lambda record_type, name: answers[(record_type, name)],
        )


def test_dns_validator_rejects_revoked_or_wrong_dkim() -> None:
    module = _dns_module()
    answers = {
        ("TXT", "auth.example.com"): ('"v=spf1 include:spf.mail.example -all"\n'),
        ("TXT", "_dmarc.auth.example.com"): '"v=DMARC1; p=reject"\n',
        ("TXT", "mail._domainkey.auth.example.com"): '"v=DKIM1; p="\n',
        ("CNAME", "mail._domainkey.auth.example.com"): "",
    }

    with pytest.raises(module.DnsValidationError):
        module.validate_auth_dns(
            domain="auth.example.com",
            selector="mail",
            expected_spf_include="include:spf.mail.example",
            dkim_record_type="TXT",
            expected_dkim_value="v=DKIM1; p=",
            lookup=lambda record_type, name: answers[(record_type, name)],
        )
