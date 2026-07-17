import base64
from pathlib import Path
import importlib.util
import json
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "configure_supabase_auth_smtp.py"
DNS_SCRIPT_PATH = ROOT / "scripts" / "validate_auth_dns.py"
WEBHOOK_SECRET_SCRIPT_PATH = ROOT / "scripts" / "validate_resend_webhook_secret.py"
PRODUCTION_AUTH_BRIDGE = ROOT / "web" / "app" / "auth" / "accept" / "index.html"
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


def _webhook_secret_module():
    spec = importlib.util.spec_from_file_location(
        "validate_webhook_secret", WEBHOOK_SECRET_SCRIPT_PATH
    )
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

    template_payload = module.auth_template_payload()
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
        **template_payload,
    }
    assert "contentengine-auth-template:v1:invite" in template_payload[
        "mailer_templates_invite_content"
    ]
    assert "contentengine-auth-template:v1:recovery" in template_payload[
        "mailer_templates_recovery_content"
    ]


def test_versioned_templates_use_the_token_hash_bridge_and_not_confirmation_url() -> None:
    module = _module()
    payload = module.auth_template_payload()

    invite = payload["mailer_templates_invite_content"]
    recovery = payload["mailer_templates_recovery_content"]
    assert (
        "{{ .SiteURL }}auth/accept#token_hash={{ .TokenHash }}&amp;type=invite"
        in invite
    )
    assert (
        "{{ .SiteURL }}auth/accept#token_hash={{ .TokenHash }}&amp;type=recovery"
        in recovery
    )
    assert "{{ .ConfirmationURL }}" not in invite
    assert "{{ .ConfirmationURL }}" not in recovery


def test_auth_bridge_requires_a_human_click_before_consuming_one_time_token() -> None:
    bridge = PRODUCTION_AUTH_BRIDGE.read_text(encoding="utf-8")
    assert 'data-auth-continue' in bridge
    assert 'target.search = window.location.search' in bridge
    assert 'target.hash = window.location.hash' in bridge
    assert 'link.href = target.href' in bridge
    assert 'window.location.replace' not in bridge
    assert 'window.location.assign' not in bridge
    assert 'location.href = target.href' not in bridge


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self, _limit: int) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


def _public_readback(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"smtp_user", "smtp_pass"}
    }


def test_smtp_configuration_requires_a_separate_management_get_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    settings = module.SmtpSettings.from_environment(_valid_environment())
    payload = settings.management_payload()
    responses = [_FakeResponse({}), _FakeResponse(_public_readback(payload))]
    calls = []

    def fake_urlopen(http_request, timeout: int):
        assert timeout == 7
        calls.append(http_request)
        return responses.pop(0)

    monkeypatch.setattr(module.request, "urlopen", fake_urlopen)
    module.configure_smtp(
        settings,
        management_api_base_url="https://management.example",
        timeout_seconds=7,
    )

    assert [call.get_method() for call in calls] == ["PATCH", "GET"]
    assert calls[1].data is None
    patch_payload = json.loads(calls[0].data.decode("utf-8"))
    assert patch_payload["mailer_templates_invite_content"] == payload[
        "mailer_templates_invite_content"
    ]
    assert patch_payload["mailer_templates_recovery_content"] == payload[
        "mailer_templates_recovery_content"
    ]


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("external_email_enabled", False),
        ("smtp_host", "wrong.example"),
        ("mailer_templates_invite_content", "fallback template"),
        ("mailer_templates_recovery_content", "fallback template"),
    ],
)
def test_smtp_configuration_fails_when_management_readback_drifted(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    bad_value: object,
) -> None:
    module = _module()
    settings = module.SmtpSettings.from_environment(_valid_environment())
    readback = _public_readback(settings.management_payload())
    readback[field] = bad_value
    responses = [_FakeResponse({}), _FakeResponse(readback)]
    monkeypatch.setattr(
        module.request,
        "urlopen",
        lambda _request, timeout: responses.pop(0),
    )

    with pytest.raises(module.SmtpConfigurationError, match=f"persist {field}"):
        module.configure_smtp(settings)


def test_smtp_configuration_fails_when_readback_omits_required_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    settings = module.SmtpSettings.from_environment(_valid_environment())
    readback = _public_readback(settings.management_payload())
    readback.pop("mailer_subjects_invite")
    responses = [_FakeResponse({}), _FakeResponse(readback)]
    monkeypatch.setattr(
        module.request,
        "urlopen",
        lambda _request, timeout: responses.pop(0),
    )

    with pytest.raises(
        module.SmtpConfigurationError,
        match="readback omitted mailer_subjects_invite",
    ):
        module.configure_smtp(settings)


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
        "Configure and read back Supabase Auth SMTP and templates"
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


def test_resend_webhook_secret_validator_matches_edge_runtime_format() -> None:
    module = _webhook_secret_module()
    encoded = base64.urlsafe_b64encode(b"x" * 32).decode("ascii").rstrip("=")
    module.validate_resend_webhook_secret(f"whsec_{encoded}")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-whsec-secret-with-enough-characters",
        "whsec_not!base64!material!",
        "whsec_" + base64.urlsafe_b64encode(b"tiny").decode("ascii"),
        "whsec_" + base64.urlsafe_b64encode(b"x" * 129).decode("ascii"),
    ],
)
def test_resend_webhook_secret_validator_fails_closed(value: str) -> None:
    module = _webhook_secret_module()
    with pytest.raises(module.WebhookSecretValidationError):
        module.validate_resend_webhook_secret(value)
