#!/usr/bin/env python3
"""Configure and read back Supabase Auth SMTP plus reviewed email templates.

The script reads credentials only from environment variables, sends them
directly to the official Supabase Management API, and prints no response body
or secret value. Invite and recovery templates are committed artifacts and are
verified before PATCH and again through a separate GET readback.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.utils import parseaddr
import json
import os
from pathlib import Path
import re
import sys
from typing import Mapping
from urllib import error, request


PROJECT_REF_RE = re.compile(r"^[a-z0-9]{20}$")
HOST_RE = re.compile(
    r"^(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)
MAX_RESPONSE_BYTES = 1_000_000
MAX_TEMPLATE_BYTES = 64_000
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTH_TEMPLATE_VERSION = "v1"
AUTH_TEMPLATE_SPECS = {
    "invite": {
        "path": REPOSITORY_ROOT
        / "supabase"
        / "templates"
        / "auth-invite-v1.html",
        "marker": "<!-- contentengine-auth-template:v1:invite -->",
        "link": (
            "{{ .SiteURL }}auth/accept#token_hash={{ .TokenHash }}"
            "&amp;type=invite"
        ),
        "subject": "ALTEA · Приглашение в Контент ИИ Завод",
    },
    "recovery": {
        "path": REPOSITORY_ROOT
        / "supabase"
        / "templates"
        / "auth-recovery-v1.html",
        "marker": "<!-- contentengine-auth-template:v1:recovery -->",
        "link": (
            "{{ .SiteURL }}auth/accept#token_hash={{ .TokenHash }}"
            "&amp;type=recovery"
        ),
        "subject": "ALTEA · Восстановление доступа",
    },
}


class SmtpConfigurationError(RuntimeError):
    """A safe, user-facing configuration failure."""


@dataclass(frozen=True)
class SmtpSettings:
    project_ref: str
    access_token: str
    admin_email: str
    host: str
    port: int
    user: str
    password: str
    sender_name: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "SmtpSettings":
        project_ref = environment.get("SUPABASE_PROJECT_REF", "").strip()
        access_token = environment.get("SUPABASE_ACCESS_TOKEN", "").strip()
        admin_email = environment.get("SMTP_ADMIN_EMAIL", "").strip()
        host = environment.get("SMTP_HOST", "").strip().lower().rstrip(".")
        raw_port = environment.get("SMTP_PORT", "").strip()
        user = environment.get("SMTP_USER", "").strip()
        password = environment.get("SMTP_PASS", "")
        sender_name = environment.get(
            "SMTP_SENDER_NAME", "ALTEA · Контент ИИ Завод"
        ).strip()

        if PROJECT_REF_RE.fullmatch(project_ref) is None:
            raise SmtpConfigurationError("SUPABASE_PROJECT_REF has an invalid format")
        if not access_token:
            raise SmtpConfigurationError("SUPABASE_ACCESS_TOKEN is required")
        if not _valid_email(admin_email):
            raise SmtpConfigurationError(
                "SMTP_ADMIN_EMAIL must be a valid sender address"
            )
        if HOST_RE.fullmatch(host) is None:
            raise SmtpConfigurationError("SMTP_HOST must be a DNS hostname")
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise SmtpConfigurationError("SMTP_PORT must be an integer") from exc
        if port < 1 or port > 65535:
            raise SmtpConfigurationError("SMTP_PORT must be between 1 and 65535")
        if not user or len(user) > 512 or _contains_control(user):
            raise SmtpConfigurationError("SMTP_USER is required and must be safe")
        if not password or len(password) > 4096 or _contains_control(password):
            raise SmtpConfigurationError("SMTP_PASS is required and must be safe")
        if not sender_name or len(sender_name) > 120 or _contains_control(sender_name):
            raise SmtpConfigurationError(
                "SMTP_SENDER_NAME must contain 1 to 120 safe characters"
            )

        return cls(
            project_ref=project_ref,
            access_token=access_token,
            admin_email=admin_email,
            host=host,
            port=port,
            user=user,
            password=password,
            sender_name=sender_name,
        )

    def management_payload(self) -> dict[str, object]:
        return {
            "external_email_enabled": True,
            "mailer_secure_email_change_enabled": True,
            "mailer_autoconfirm": False,
            "smtp_admin_email": self.admin_email,
            "smtp_host": self.host,
            "smtp_port": self.port,
            "smtp_user": self.user,
            "smtp_pass": self.password,
            "smtp_sender_name": self.sender_name,
            **auth_template_payload(),
        }


def configure_smtp(
    settings: SmtpSettings,
    *,
    management_api_base_url: str = "https://api.supabase.com",
    timeout_seconds: int = 30,
) -> None:
    endpoint = (
        f"{management_api_base_url.rstrip('/')}/v1/projects/"
        f"{settings.project_ref}/config/auth"
    )
    expected_payload = settings.management_payload()
    _management_request(
        settings,
        endpoint=endpoint,
        method="PATCH",
        payload=expected_payload,
        timeout_seconds=timeout_seconds,
    )
    readback = _management_request(
        settings,
        endpoint=endpoint,
        method="GET",
        timeout_seconds=timeout_seconds,
    )
    _verify_management_readback(readback, expected_payload)


def auth_template_payload() -> dict[str, str]:
    templates = {
        purpose: _read_auth_template(purpose)
        for purpose in ("invite", "recovery")
    }
    return {
        "mailer_subjects_invite": str(AUTH_TEMPLATE_SPECS["invite"]["subject"]),
        "mailer_templates_invite_content": templates["invite"],
        "mailer_subjects_recovery": str(
            AUTH_TEMPLATE_SPECS["recovery"]["subject"]
        ),
        "mailer_templates_recovery_content": templates["recovery"],
    }


def _read_auth_template(purpose: str) -> str:
    spec = AUTH_TEMPLATE_SPECS.get(purpose)
    if spec is None:
        raise SmtpConfigurationError("Auth email template purpose is invalid")
    path = spec["path"]
    if not isinstance(path, Path):
        raise SmtpConfigurationError("Auth email template path is invalid")
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SmtpConfigurationError("Auth email template is unavailable") from exc
    if len(content.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise SmtpConfigurationError("Auth email template is too large")
    marker = str(spec["marker"])
    required_link = str(spec["link"])
    if content.count(marker) != 1 or content.count(required_link) != 1:
        raise SmtpConfigurationError(
            f"Auth email {purpose} template does not match {AUTH_TEMPLATE_VERSION}"
        )
    if "{{ .ConfirmationURL }}" in content:
        raise SmtpConfigurationError(
            "Auth email template must use the reviewed token-hash bridge"
        )
    return content


def _management_request(
    settings: SmtpSettings,
    *,
    endpoint: str,
    method: str,
    timeout_seconds: int,
    payload: Mapping[str, object] | None = None,
) -> dict[str, object]:
    body = None
    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {settings.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "contentengine-smtp-config/2",
        },
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
    except error.HTTPError as exc:
        # Never include the response body: a provider can echo credentials.
        raise SmtpConfigurationError(
            f"Supabase Management API rejected Auth configuration (HTTP {exc.code})"
        ) from None
    except error.URLError as exc:
        raise SmtpConfigurationError("Supabase Management API is unavailable") from exc

    if status < 200 or status >= 300:
        raise SmtpConfigurationError(
            f"Supabase Management API rejected Auth configuration (HTTP {status})"
        )
    if len(response_body) > MAX_RESPONSE_BYTES:
        raise SmtpConfigurationError("Supabase Management API response was too large")
    try:
        response_payload = (
            json.loads(response_body.decode("utf-8")) if response_body else {}
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmtpConfigurationError(
            "Supabase Management API returned an invalid response"
        ) from exc
    if not isinstance(response_payload, dict):
        raise SmtpConfigurationError(
            "Supabase Management API returned an invalid response"
        )
    return response_payload


def _verify_management_readback(
    readback: Mapping[str, object],
    expected_payload: Mapping[str, object],
) -> None:
    required_fields = {
        "external_email_enabled",
        "mailer_secure_email_change_enabled",
        "mailer_autoconfirm",
        "smtp_admin_email",
        "smtp_host",
        "smtp_port",
        "smtp_sender_name",
        "mailer_subjects_invite",
        "mailer_templates_invite_content",
        "mailer_subjects_recovery",
        "mailer_templates_recovery_content",
    }
    for field in sorted(required_fields):
        if field not in readback:
            raise SmtpConfigurationError(
                f"Supabase Management API readback omitted {field}"
            )
        expected = expected_payload[field]
        actual = readback[field]
        if field == "smtp_port":
            try:
                actual = int(str(actual))
            except ValueError as exc:
                raise SmtpConfigurationError(
                    "Supabase Management API returned an invalid smtp_port"
                ) from exc
        if actual != expected:
            raise SmtpConfigurationError(
                f"Supabase Management API did not persist {field}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure production Supabase Auth custom SMTP",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate protected environment variables without sending them",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        settings = SmtpSettings.from_environment(os.environ)
        if args.dry_run:
            settings.management_payload()
            print("Supabase Auth SMTP settings validated; no request was made.")
            return 0
        configure_smtp(settings)
    except SmtpConfigurationError as exc:
        print(f"SMTP configuration failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Supabase Auth custom SMTP configured. "
        "Verify a real invite/recovery and the provider delivery log next."
    )
    return 0


def _valid_email(value: str) -> bool:
    _, parsed = parseaddr(value)
    if parsed != value or value.count("@") != 1 or len(value) > 254:
        return False
    local, domain = value.rsplit("@", 1)
    return (
        bool(local)
        and len(local) <= 64
        and not _contains_control(local)
        and HOST_RE.fullmatch(domain.rstrip(".")) is not None
    )


def _contains_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


if __name__ == "__main__":
    raise SystemExit(main())
