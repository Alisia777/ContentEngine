from __future__ import annotations

import atexit
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Mapping

from app.config import get_settings, normalized_supabase_base_url
from app.media_storage.backend import StorageBackend
from app.media_storage.errors import StorageSecurityError
from app.media_storage.local import LocalStorage
from app.media_storage.s3 import S3CompatibleStorage
from app.media_storage.supabase import SupabaseStorage
from app.supabase_keys import resolve_supabase_server_key


PRODUCTION_ENVIRONMENTS = frozenset({"prod", "production"})
_STORAGE_ENV_KEYS = (
    "ENVIRONMENT",
    "QVF_DEPLOYMENT_ENV",
    "QVF_ENVIRONMENT",
    "QVF_MEDIA_SIGNING_SECRET",
    "QVF_RUNTIME_PROFILE",
    "QVF_S3_ACCESS_KEY_ID",
    "QVF_S3_BUCKET",
    "QVF_S3_ENDPOINT_URL",
    "QVF_S3_REGION",
    "QVF_S3_SECRET_ACCESS_KEY",
    "QVF_S3_SESSION_TOKEN",
    "QVF_STORAGE_BACKEND",
    "QVF_STORAGE_BUCKET",
    "QVF_STORAGE_LOCAL_BASE_URL",
    "QVF_STORAGE_LOCAL_ROOT",
    "QVF_STORAGE_S3_ACCESS_KEY_ID",
    "QVF_STORAGE_S3_ENDPOINT",
    "QVF_STORAGE_S3_REGION",
    "QVF_STORAGE_S3_SECRET_ACCESS_KEY",
    "QVF_STORAGE_S3_SESSION_TOKEN",
    "QVF_STORAGE_SIGNING_SECRET",
    "QVF_STORAGE_SUPABASE_SERVICE_ROLE_KEY",
    "QVF_STORAGE_SUPABASE_URL",
    "QVF_SUPABASE_STORAGE_BUCKET",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_URL",
)
_STORAGE_SETTING_NAMES = (
    "deployment_env",
    "environment",
    "local_session_secret",
    "media_root",
    "media_signing_secret",
    "runtime_profile",
    "s3_access_key_id",
    "s3_bucket",
    "s3_endpoint_url",
    "s3_region",
    "s3_secret_access_key",
    "s3_session_token",
    "storage_backend",
    "storage_bucket",
    "storage_local_base_url",
    "storage_local_root",
    "storage_s3_access_key_id",
    "storage_s3_endpoint",
    "storage_s3_region",
    "storage_s3_secret_access_key",
    "storage_s3_session_token",
    "storage_signing_secret",
    "storage_supabase_service_role_key",
    "storage_supabase_url",
    "supabase_secret_key",
    "supabase_storage_bucket",
    "supabase_url",
)
_BACKEND_CACHE_LIMIT = 8
_backend_cache: dict[str, StorageBackend] = {}
_backend_cache_order: list[str] = []
_backend_cache_lock = RLock()


@dataclass(frozen=True)
class SupabaseStorageRuntimeConfig:
    project_url: str
    bucket: str
    server_key: str


def resolve_supabase_storage_runtime_config(
    *,
    settings=None,
    environ: Mapping[str, str] | None = None,
) -> SupabaseStorageRuntimeConfig:
    """Resolve the one canonical Supabase Storage configuration."""

    settings = settings or get_settings()
    env = dict(os.environ if environ is None else environ)

    def value(env_key: str, setting_name: str) -> str | None:
        raw = env.get(env_key)
        if raw is None:
            raw = getattr(settings, setting_name, None)
        text = str(raw).strip() if raw is not None else ""
        return text or None

    try:
        server_key = resolve_supabase_server_key(settings=settings, environ=env)
    except ValueError as exc:
        raise StorageSecurityError("Supabase server key configuration is invalid.") from exc

    deployment = str(
        env.get("QVF_DEPLOYMENT_ENV")
        or env.get("QVF_RUNTIME_PROFILE")
        or getattr(settings, "runtime_profile", "development")
    ).strip().casefold()
    canonical_project_url = (
        str(env.get("SUPABASE_URL") or getattr(settings, "supabase_url", "") or "")
        .strip()
    )
    legacy_project_url = value(
        "QVF_STORAGE_SUPABASE_URL",
        "storage_supabase_url",
    )
    if deployment in PRODUCTION_ENVIRONMENTS:
        normalized_project_url = normalized_supabase_base_url(canonical_project_url)
        if not normalized_project_url:
            raise StorageSecurityError(
                "Production Supabase Storage requires the canonical HTTPS SUPABASE_URL."
            )
        if legacy_project_url and legacy_project_url.rstrip("/") != normalized_project_url:
            raise StorageSecurityError(
                "A separate Supabase Storage project URL is forbidden in production."
            )
        project_url = normalized_project_url
    else:
        project_url = legacy_project_url or canonical_project_url

    return SupabaseStorageRuntimeConfig(
        project_url=_required(
            project_url,
            "Supabase project URL",
        ),
        bucket=_required(
            value("QVF_STORAGE_BUCKET", "storage_bucket")
            or env.get("QVF_SUPABASE_STORAGE_BUCKET")
            or getattr(settings, "supabase_storage_bucket", None),
            "storage bucket",
        ),
        server_key=server_key,
    )


def build_storage_backend(
    *,
    settings=None,
    environ: Mapping[str, str] | None = None,
) -> StorageBackend:
    """Build one private backend without adding storage fields to Settings yet.

    Explicit environment variables win, then optional future Settings fields
    are read via ``getattr``.  A local fallback is available only outside a
    production deployment.
    """

    settings = settings or get_settings()
    env = dict(os.environ if environ is None else environ)

    def value(env_key: str, setting_name: str, default: str | None = None) -> str | None:
        raw = env.get(env_key)
        if raw is None:
            raw = getattr(settings, setting_name, None)
        if raw is None:
            raw = default
        text = str(raw).strip() if raw is not None else ""
        return text or None

    deployment = (
        value("QVF_DEPLOYMENT_ENV", "deployment_env")
        or env.get("QVF_RUNTIME_PROFILE")
        or getattr(settings, "runtime_profile", None)
        or value("QVF_ENVIRONMENT", "environment")
        or env.get("ENVIRONMENT", "development")
    ).strip().lower()
    production = deployment in PRODUCTION_ENVIRONMENTS
    backend_name = (value("QVF_STORAGE_BACKEND", "storage_backend") or "").lower()
    if not backend_name:
        if production:
            raise StorageSecurityError(
                "Production requires an explicit private object-storage backend."
            )
        backend_name = "local"

    if backend_name == "local":
        if production:
            raise StorageSecurityError("Local storage is forbidden in production.")
        media_root = Path(getattr(settings, "media_root", Path("media")))
        root = Path(value("QVF_STORAGE_LOCAL_ROOT", "storage_local_root") or (media_root / "objects"))
        secret = (
            value("QVF_STORAGE_SIGNING_SECRET", "storage_signing_secret")
            or env.get("QVF_MEDIA_SIGNING_SECRET")
            or getattr(settings, "media_signing_secret", None)
            or getattr(settings, "local_session_secret", None)
            or "local-development-storage-secret"
        )
        return LocalStorage(
            root,
            bucket=value("QVF_STORAGE_BUCKET", "storage_bucket", "private-media") or "private-media",
            signing_secret=str(secret),
            public_base_url=(
                value(
                    "QVF_STORAGE_LOCAL_BASE_URL",
                    "storage_local_base_url",
                    "/media-library/local",
                )
                or "/media-library/local"
            ),
        )

    if backend_name == "s3":
        return S3CompatibleStorage(
            endpoint_url=_required(
                value("QVF_STORAGE_S3_ENDPOINT", "storage_s3_endpoint")
                or env.get("QVF_S3_ENDPOINT_URL")
                or getattr(settings, "s3_endpoint_url", None),
                "S3 endpoint",
            ),
            bucket=_required(
                value("QVF_STORAGE_BUCKET", "storage_bucket")
                or env.get("QVF_S3_BUCKET")
                or getattr(settings, "s3_bucket", None),
                "storage bucket",
            ),
            region=(
                value("QVF_STORAGE_S3_REGION", "storage_s3_region")
                or env.get("QVF_S3_REGION")
                or getattr(settings, "s3_region", None)
                or "us-east-1"
            ),
            access_key_id=_required(
                value("QVF_STORAGE_S3_ACCESS_KEY_ID", "storage_s3_access_key_id")
                or env.get("QVF_S3_ACCESS_KEY_ID")
                or getattr(settings, "s3_access_key_id", None),
                "S3 access key id",
            ),
            secret_access_key=_required(
                value("QVF_STORAGE_S3_SECRET_ACCESS_KEY", "storage_s3_secret_access_key")
                or env.get("QVF_S3_SECRET_ACCESS_KEY")
                or getattr(settings, "s3_secret_access_key", None),
                "S3 secret access key",
            ),
            session_token=(
                value("QVF_STORAGE_S3_SESSION_TOKEN", "storage_s3_session_token")
                or env.get("QVF_S3_SESSION_TOKEN")
                or getattr(settings, "s3_session_token", None)
            ),
        )

    if backend_name == "supabase":
        supabase = resolve_supabase_storage_runtime_config(
            settings=settings,
            environ=env,
        )
        return SupabaseStorage(
            project_url=supabase.project_url,
            bucket=supabase.bucket,
            service_role_key=supabase.server_key,
        )

    raise StorageSecurityError("Unknown object-storage backend.")


def get_default_storage_backend() -> StorageBackend:
    settings = get_settings()
    fingerprint = _storage_fingerprint(settings, os.environ)
    with _backend_cache_lock:
        cached = _backend_cache.get(fingerprint)
        if cached is not None:
            _backend_cache_order.remove(fingerprint)
            _backend_cache_order.append(fingerprint)
            return cached
        backend = build_storage_backend(settings=settings)
        _backend_cache[fingerprint] = backend
        _backend_cache_order.append(fingerprint)
        while len(_backend_cache_order) > _BACKEND_CACHE_LIMIT:
            expired = _backend_cache_order.pop(0)
            stale = _backend_cache.pop(expired, None)
            if stale is not None:
                stale.close()
        return backend


def get_storage_backends() -> dict[str, StorageBackend]:
    # Reuse one transport pool for each effective process configuration. The
    # fingerprint changes automatically in tests that replace environment or
    # Settings values, without leaking a client per request or worker job.
    backend = get_default_storage_backend()
    return {backend.name: backend}


def close_storage_backends() -> None:
    """Close every cached remote transport during graceful process shutdown."""

    with _backend_cache_lock:
        backends = list({id(item): item for item in _backend_cache.values()}.values())
        _backend_cache.clear()
        _backend_cache_order.clear()
    for backend in backends:
        backend.close()


def _storage_fingerprint(settings, environ: Mapping[str, str]) -> str:
    payload = {
        "env": {key: environ.get(key) for key in _STORAGE_ENV_KEYS},
        "settings": {
            name: str(getattr(settings, name, None))
            for name in _STORAGE_SETTING_NAMES
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required(value: str | None, label: str) -> str:
    if not value:
        raise StorageSecurityError(f"Missing {label}.")
    return value


atexit.register(close_storage_backends)
