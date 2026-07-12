from __future__ import annotations

import os
from typing import Mapping


PRODUCTION_ENVIRONMENTS = frozenset({"prod", "production"})


def resolve_supabase_server_key(
    *,
    settings,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve one server key and reject conflicting production aliases."""

    env = dict(os.environ if environ is None else environ)

    def clean(value) -> str | None:
        normalized = str(value).strip() if value is not None else ""
        return normalized or None

    primary = (
        clean(env.get("SUPABASE_SECRET_KEY"))
        or clean(env.get("QVF_SUPABASE_SECRET_KEY"))
        or clean(getattr(settings, "supabase_secret_key", None))
    )
    legacy_values = (
        clean(env.get("QVF_STORAGE_SUPABASE_SERVICE_ROLE_KEY")),
        clean(getattr(settings, "storage_supabase_service_role_key", None)),
        clean(env.get("SUPABASE_SERVICE_ROLE_KEY")),
        clean(env.get("QVF_SUPABASE_SERVICE_ROLE_KEY")),
    )
    configured = [value for value in (primary, *legacy_values) if value]
    if not configured:
        raise ValueError("A Supabase server key is required.")

    production = any(
        str(value or "").casefold() in PRODUCTION_ENVIRONMENTS
        for value in (
            clean(env.get("QVF_DEPLOYMENT_ENV")),
            clean(env.get("QVF_RUNTIME_PROFILE")),
            clean(getattr(settings, "runtime_profile", None)),
        )
    )
    if production:
        if len(set(configured)) != 1:
            raise ValueError("Conflicting Supabase server key settings are forbidden.")
    return primary or next(value for value in legacy_values if value)


def server_api_key_headers(value: str) -> dict[str, str]:
    """Build server headers for current opaque and legacy JWT API keys."""

    key = str(value or "").strip()
    if not key:
        raise ValueError("A Supabase server key is required.")
    if key.startswith("sb_publishable_"):
        raise ValueError("A Supabase publishable key cannot authorize server operations.")

    headers = {"apikey": key}
    # Current sb_secret keys are opaque API keys, not JWTs. Sending one as a
    # bearer token makes Supabase attempt JWT parsing and reject the request.
    if not key.startswith("sb_secret_"):
        headers["authorization"] = f"Bearer {key}"
    return headers
