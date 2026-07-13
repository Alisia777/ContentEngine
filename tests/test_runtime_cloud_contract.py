from types import SimpleNamespace

import pytest

from app.config import RuntimeConfigurationError, Settings, validate_runtime_settings
from app.media_storage import StorageSecurityError, SupabaseStorage, build_storage_backend


def _production_settings(**overrides) -> Settings:
    values = {
        "runtime_profile": "production",
        "database_url": "postgresql+psycopg://user:password@db.example.test/contentengine?sslmode=require",
        "auto_init_db": False,
        "public_app_url": "https://factory.example.test",
        "storage_backend": "supabase",
        "auth_required": True,
        "public_pilot_invite_only": True,
        "session_cookie_secure": True,
        "supabase_url": "https://project.supabase.co",
        "supabase_publishable_key": "publishable-test-key",
        "supabase_secret_key": "server-only-test-key",
        "supabase_storage_bucket": "contentengine-private",
        "supabase_jwks_url": None,
        "supabase_issuer": None,
        "local_auth_email": None,
        "local_auth_password_hash": None,
        "local_session_secret": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_safe_production_runtime_contract_is_accepted() -> None:
    settings = _production_settings()

    assert validate_runtime_settings(settings) is settings


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"database_url": "sqlite:///./production.db"}, "PostgreSQL"),
        ({"auto_init_db": True}, "Alembic"),
        ({"public_app_url": "http://127.0.0.1:8014"}, "public HTTPS"),
        ({"storage_backend": "local"}, "local media storage"),
        ({"supabase_secret_key": None}, "SUPABASE_SECRET_KEY"),
        ({"session_cookie_secure": False}, "SESSION_COOKIE_SECURE"),
        ({"session_cookie_samesite": "none"}, "SAMESITE=none"),
    ],
)
def test_unsafe_production_runtime_fails_before_serving(override, message) -> None:
    with pytest.raises(RuntimeConfigurationError, match=message):
        validate_runtime_settings(_production_settings(**override))


@pytest.mark.parametrize("sslmode", [None, "disable", "allow", "prefer", "verify-ca&sslmode=disable"])
def test_production_database_rejects_missing_weak_or_ambiguous_tls_mode(sslmode) -> None:
    suffix = "" if sslmode is None else f"?sslmode={sslmode}"
    settings = _production_settings(
        database_url=(
            "postgresql+psycopg://user:password@db.example.test/contentengine"
            f"{suffix}"
        )
    )

    with pytest.raises(RuntimeConfigurationError, match="sslmode must be"):
        validate_runtime_settings(settings)


@pytest.mark.parametrize("sslmode", ["require", "verify-ca", "verify-full"])
def test_production_database_accepts_only_strong_tls_modes(sslmode) -> None:
    settings = _production_settings(
        database_url=(
            "postgresql+psycopg://user:password@db.example.test/contentengine"
            f"?sslmode={sslmode}"
        )
    )

    assert validate_runtime_settings(settings) is settings


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (
            {"supabase_url": "https://project.supabase.co/proxy"},
            "SUPABASE_URL must be an HTTPS origin",
        ),
        (
            {
                "supabase_jwks_url": (
                    "https://another-project.supabase.co/"
                    "auth/v1/.well-known/jwks.json"
                )
            },
            "JWKS_URL must belong",
        ),
        (
            {"supabase_issuer": "https://another-project.supabase.co/auth/v1"},
            "ISSUER must belong",
        ),
    ],
)
def test_production_auth_endpoints_must_belong_to_configured_supabase_project(
    override,
    message,
) -> None:
    with pytest.raises(RuntimeConfigurationError, match=message):
        validate_runtime_settings(_production_settings(**override))


def test_exact_explicit_supabase_auth_endpoints_are_accepted() -> None:
    settings = _production_settings(
        supabase_jwks_url=(
            "https://project.supabase.co/auth/v1/.well-known/jwks.json"
        ),
        supabase_issuer="https://project.supabase.co/auth/v1/",
    )

    assert validate_runtime_settings(settings) is settings


def test_production_rejects_conflicting_legacy_supabase_server_key(monkeypatch) -> None:
    settings = _production_settings()
    monkeypatch.setenv("QVF_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "different-legacy-server-key")

    with pytest.raises(RuntimeConfigurationError, match="single canonical server key"):
        validate_runtime_settings(settings)


@pytest.mark.parametrize(
    ("field", "environment_name", "value"),
    [
        ("local_auth_email", "QVF_LOCAL_AUTH_EMAIL", "owner@local.test"),
        ("local_auth_password_hash", "QVF_LOCAL_AUTH_PASSWORD_HASH", "pbkdf2-secret"),
        ("local_session_secret", "QVF_LOCAL_SESSION_SECRET", "local-session-secret"),
        ("local_auth_email", "QVF_LOCAL_AUTH_EMAIL", ""),
    ],
)
def test_production_rejects_every_local_auth_setting(field, environment_name, value) -> None:
    with pytest.raises(RuntimeConfigurationError, match=environment_name) as exc_info:
        validate_runtime_settings(_production_settings(**{field: value}))

    assert value == "" or value not in str(exc_info.value)


def test_render_supabase_environment_keys_build_the_private_backend(tmp_path) -> None:
    settings = SimpleNamespace(
        runtime_profile="production",
        storage_backend="supabase",
        media_root=tmp_path,
        supabase_url=None,
        supabase_secret_key=None,
        supabase_storage_bucket=None,
    )
    backend = build_storage_backend(
        settings=settings,
        environ={
            "QVF_RUNTIME_PROFILE": "production",
            "QVF_STORAGE_BACKEND": "supabase",
            "SUPABASE_URL": "https://project.supabase.co",
            "SUPABASE_SECRET_KEY": "server-only-key",
            "QVF_SUPABASE_STORAGE_BUCKET": "contentengine-private",
        },
    )

    assert isinstance(backend, SupabaseStorage)
    assert backend.bucket == "contentengine-private"
    backend.close()


def test_production_storage_rejects_a_separate_or_insecure_project_url(tmp_path) -> None:
    settings = SimpleNamespace(
        runtime_profile="production",
        storage_backend="supabase",
        media_root=tmp_path,
        supabase_url=None,
        supabase_secret_key=None,
        supabase_storage_bucket=None,
    )

    with pytest.raises(StorageSecurityError, match="separate Supabase Storage"):
        build_storage_backend(
            settings=settings,
            environ={
                "QVF_RUNTIME_PROFILE": "production",
                "QVF_STORAGE_BACKEND": "supabase",
                "SUPABASE_URL": "https://project.supabase.co",
                "QVF_STORAGE_SUPABASE_URL": "http://attacker.example.test",
                "SUPABASE_SECRET_KEY": "server-only-key",
                "QVF_SUPABASE_STORAGE_BUCKET": "contentengine-private",
            },
        )


def test_runtime_profile_alone_forbids_local_storage_in_production(tmp_path) -> None:
    settings = SimpleNamespace(
        runtime_profile="production",
        storage_backend="local",
        media_root=tmp_path,
    )

    with pytest.raises(StorageSecurityError, match="forbidden"):
        build_storage_backend(settings=settings, environ={})


def test_cloud_creator_routes_are_registered_in_one_web_app() -> None:
    from app.main import app

    paths = {route.path for route in app.routes}
    assert {
        "/auth/confirm",
        "/auth/accept",
        "/onboarding",
        "/onboarding/set-password",
        "/creator-operations",
        "/media-library",
        "/team",
        "/ready",
    }.issubset(paths)
