from functools import lru_cache
from pathlib import Path
import sys
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, ConfigDict, Field
from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.supabase_keys import resolve_supabase_server_key


PRODUCTION_POSTGRES_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})


class Settings(BaseSettings):
    app_name: str = "Контент ИИ Завод"
    runtime_profile: Literal["development", "test", "production"] = "development"
    auto_init_db: bool = True
    public_app_url: str | None = None
    database_url: str = "sqlite:///./qharisma.db"
    media_root: Path = Path("media")
    storage_backend: Literal["local", "supabase", "s3"] = "local"
    media_signing_secret: str | None = None
    mock_provider_enabled: bool = True
    generation_mode: Literal["mock", "real"] = "mock"
    allow_real_spend: bool = False
    mass_generation_credit_limit: int = Field(default=30_000, ge=1, le=300_000)
    max_video_seconds_per_run: int = 5
    max_scenes_per_real_run: int = 1
    max_provider_poll_seconds: int = 600
    llm_provider: str = "mock"
    openai_model: str = "gpt-5.5"
    video_provider: str = "mock"
    runway_model: str = "gen4.5"
    video_ratio: str = "720:1280"
    video_scene_duration: int = 5
    # Media tools can live outside PATH on Windows and in managed deployments.
    # Values are executable paths/names only; they are not credentials.
    tesseract_path: str | None = None
    tessdata_prefix: str | None = None
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    public_pilot_mode: bool = False
    auth_required: bool = False
    auth_dev_bypass_email: str = "owner@local.contentengine"
    local_auth_email: str | None = None
    local_auth_password_hash: str | None = None
    local_session_secret: str | None = None
    local_session_ttl_seconds: int = 28_800
    supabase_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_URL", "QVF_SUPABASE_URL"))
    supabase_project_ref: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_PROJECT_REF", "QVF_SUPABASE_PROJECT_REF"))
    supabase_publishable_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_ANON_KEY",
            "QVF_SUPABASE_PUBLISHABLE_KEY",
            "QVF_SUPABASE_ANON_KEY",
        ),
    )
    supabase_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SUPABASE_SECRET_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "QVF_SUPABASE_SECRET_KEY",
            "QVF_SUPABASE_SERVICE_ROLE_KEY",
        ),
    )
    supabase_storage_bucket: str = "contentengine-private"
    supabase_jwt_secret: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_JWT_SECRET", "QVF_SUPABASE_JWT_SECRET"))
    supabase_jwks_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_JWKS_URL", "QVF_SUPABASE_JWKS_URL"))
    supabase_issuer: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_ISSUER", "QVF_SUPABASE_ISSUER"))
    supabase_audience: str = Field(default="authenticated", validation_alias=AliasChoices("SUPABASE_AUDIENCE", "QVF_SUPABASE_AUDIENCE"))
    supabase_auth_timeout_seconds: float = 8.0
    supabase_readiness_timeout_seconds: float = Field(default=5.0, ge=0.5, le=15.0)
    supabase_jwks_cache_seconds: int = 300
    supabase_jwt_clock_skew_seconds: int = 30
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_session_token: str | None = None
    session_cookie_name: str = "qvf_session"
    session_refresh_cookie_name: str = "qvf_refresh"
    session_refresh_cookie_max_age_seconds: int = 2_592_000
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    public_pilot_default_org: str = "ALTEA Beauty"
    public_pilot_invite_only: bool = True
    public_pilot_real_spend_default_enabled: bool = False
    public_pilot_training_threshold: float = 0.8
    public_pilot_strict_training_gates: bool = True

    model_config = ConfigDict(env_file=".env", env_prefix="QVF_", populate_by_name=True)


class RuntimeConfigurationError(RuntimeError):
    """Raised before a production process can start with an unsafe cloud profile."""


def validate_runtime_settings(settings: Settings) -> Settings:
    if settings.runtime_profile != "production":
        return settings

    errors: list[str] = []
    try:
        database_url = make_url(settings.database_url)
    except (ArgumentError, TypeError, ValueError):
        database_url = None
    if database_url is None or database_url.drivername != "postgresql+psycopg":
        errors.append("QVF_DATABASE_URL must use PostgreSQL via postgresql+psycopg")
    else:
        sslmode = database_url.query.get("sslmode")
        normalized_sslmode = (
            sslmode.strip().casefold() if isinstance(sslmode, str) else None
        )
        if normalized_sslmode not in PRODUCTION_POSTGRES_SSLMODES:
            errors.append(
                "QVF_DATABASE_URL sslmode must be require, verify-ca, or verify-full"
            )
    if settings.auto_init_db:
        errors.append("QVF_AUTO_INIT_DB must be false; deploy with Alembic migrations")
    local_auth_values = {
        "QVF_LOCAL_AUTH_EMAIL": settings.local_auth_email,
        "QVF_LOCAL_AUTH_PASSWORD_HASH": settings.local_auth_password_hash,
        "QVF_LOCAL_SESSION_SECRET": settings.local_session_secret,
    }
    configured_local_auth = [
        name for name, value in local_auth_values.items() if value is not None
    ]
    if configured_local_auth:
        errors.append(
            "local authentication settings are forbidden in production: "
            + ", ".join(configured_local_auth)
        )
    if not settings.auth_required or not settings.public_pilot_invite_only:
        errors.append("Supabase authentication and invite-only access must be enabled")
    auth_required_values = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_PUBLISHABLE_KEY": settings.supabase_publishable_key,
        # Required server-side for team invitations and membership lifecycle.
        "SUPABASE_SECRET_KEY": settings.supabase_secret_key,
    }
    missing_auth = [name for name, value in auth_required_values.items() if not value]
    if missing_auth:
        errors.append("missing Supabase Auth settings: " + ", ".join(missing_auth))
    else:
        try:
            resolve_supabase_server_key(settings=settings)
        except ValueError:
            errors.append(
                "SUPABASE_SECRET_KEY must be the single canonical server key; "
                "conflicting legacy service-role settings are forbidden"
            )
    supabase_base_url = normalized_supabase_base_url(settings.supabase_url)
    if settings.supabase_url and not supabase_base_url:
        errors.append("SUPABASE_URL must be an HTTPS origin without path, query, or credentials")
    if supabase_base_url:
        expected_jwks_url = supabase_jwks_url_for_base(supabase_base_url)
        configured_jwks_url = str(settings.supabase_jwks_url or expected_jwks_url).strip()
        if configured_jwks_url != expected_jwks_url:
            errors.append("QVF_SUPABASE_JWKS_URL must belong to SUPABASE_URL")
        expected_issuer = supabase_issuer_for_base(supabase_base_url)
        configured_issuer = str(settings.supabase_issuer or expected_issuer).strip().rstrip("/")
        if configured_issuer != expected_issuer:
            errors.append("QVF_SUPABASE_ISSUER must belong to SUPABASE_URL")
    if not _is_public_https_url(settings.public_app_url):
        errors.append("QVF_PUBLIC_APP_URL must be the public HTTPS creator URL")
    if not settings.session_cookie_secure:
        errors.append("QVF_SESSION_COOKIE_SECURE must be true")
    if settings.session_cookie_samesite == "none":
        errors.append(
            "QVF_SESSION_COOKIE_SAMESITE=none is forbidden in production"
        )
    if settings.storage_backend == "local":
        errors.append("local media storage is forbidden in production")
    if settings.storage_backend == "supabase":
        if not settings.supabase_storage_bucket:
            errors.append("missing Supabase Storage setting: QVF_SUPABASE_STORAGE_BUCKET")
    elif settings.storage_backend == "s3":
        s3_required = {
            "QVF_S3_ENDPOINT_URL": settings.s3_endpoint_url,
            "QVF_S3_BUCKET": settings.s3_bucket,
            "QVF_S3_ACCESS_KEY_ID": settings.s3_access_key_id,
            "QVF_S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
        }
        missing_s3 = [name for name, value in s3_required.items() if not value]
        if missing_s3:
            errors.append("missing S3 settings: " + ", ".join(missing_s3))
        if settings.s3_endpoint_url and not _is_public_https_url(settings.s3_endpoint_url):
            errors.append("QVF_S3_ENDPOINT_URL must be an absolute HTTPS URL")
    if settings.allow_real_spend and settings.generation_mode != "real":
        errors.append("real spend requires QVF_GENERATION_MODE=real")

    if errors:
        raise RuntimeConfigurationError("Unsafe production configuration: " + "; ".join(errors))
    return settings


def _is_public_https_url(value: str | None) -> bool:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
    )


def normalized_supabase_base_url(value: str | None) -> str | None:
    """Return the exact Supabase HTTPS origin used by every Auth endpoint."""

    try:
        parsed = urlsplit(str(value or "").strip())
        port = parsed.port
    except (ValueError, TypeError):
        return None
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    host = parsed.hostname.casefold()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    authority = f"{host}:{port}" if port is not None else host
    return f"https://{authority}"


def supabase_jwks_url_for_base(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


def supabase_issuer_for_base(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if "pytest" in sys.modules and settings.media_root.resolve() == Path("media").resolve():
        raise RuntimeError(
            "Refusing to open the workspace media directory from pytest; "
            "configure an isolated QVF_MEDIA_ROOT."
        )
    settings.media_root.mkdir(parents=True, exist_ok=True)
    (settings.media_root / "mock").mkdir(parents=True, exist_ok=True)
    (settings.media_root / "output").mkdir(parents=True, exist_ok=True)
    (settings.media_root / "generation_reports").mkdir(parents=True, exist_ok=True)
    return settings
