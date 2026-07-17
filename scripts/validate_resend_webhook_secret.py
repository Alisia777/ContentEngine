#!/usr/bin/env python3
"""Validate a Resend/Svix signing secret without printing it."""

from __future__ import annotations

import base64
import binascii
import os
import sys


MIN_SECRET_CHARACTERS = 24
MAX_SECRET_CHARACTERS = 512
MIN_KEY_BYTES = 16
MAX_KEY_BYTES = 128
PREFIX = "whsec_"


class WebhookSecretValidationError(RuntimeError):
    """Safe validation failure that never contains the supplied secret."""


def validate_resend_webhook_secret(value: str) -> None:
    secret = str(value or "").strip()
    if not MIN_SECRET_CHARACTERS <= len(secret) <= MAX_SECRET_CHARACTERS:
        raise WebhookSecretValidationError(
            "RESEND_WEBHOOK_SECRET has an invalid length"
        )
    if not secret.startswith(PREFIX):
        raise WebhookSecretValidationError(
            "RESEND_WEBHOOK_SECRET must use the whsec_ Svix format"
        )

    encoded = secret[len(PREFIX) :]
    padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise WebhookSecretValidationError(
            "RESEND_WEBHOOK_SECRET contains invalid base64 key material"
        ) from exc
    if not MIN_KEY_BYTES <= len(decoded) <= MAX_KEY_BYTES:
        raise WebhookSecretValidationError(
            "RESEND_WEBHOOK_SECRET contains an invalid signing-key length"
        )


def main() -> int:
    try:
        validate_resend_webhook_secret(os.environ.get("RESEND_WEBHOOK_SECRET", ""))
    except WebhookSecretValidationError as exc:
        print(f"Webhook secret validation failed: {exc}", file=sys.stderr)
        return 1
    print("Resend webhook signing secret format validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
