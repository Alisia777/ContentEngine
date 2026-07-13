import pytest
from types import SimpleNamespace

from app.supabase_keys import resolve_supabase_server_key, server_api_key_headers


def test_current_secret_key_is_never_misrepresented_as_a_bearer_jwt() -> None:
    key = "sb_secret_server_only_example"
    assert server_api_key_headers(key) == {"apikey": key}


def test_legacy_service_role_jwt_keeps_authorization_header() -> None:
    key = "eyJhbGciOiJIUzI1NiJ9.legacy-service-role.signature"
    assert server_api_key_headers(key) == {
        "apikey": key,
        "authorization": f"Bearer {key}",
    }


@pytest.mark.parametrize("key", ["", "   ", "sb_publishable_public_example"])
def test_public_or_missing_key_is_rejected_for_server_operations(key: str) -> None:
    with pytest.raises(ValueError):
        server_api_key_headers(key)


def test_canonical_secret_is_shared_by_all_server_operations() -> None:
    settings = SimpleNamespace(runtime_profile="production", supabase_secret_key=None)
    key = resolve_supabase_server_key(
        settings=settings,
        environ={
            "QVF_RUNTIME_PROFILE": "production",
            "SUPABASE_SECRET_KEY": "sb_secret_canonical",
        },
    )

    assert key == "sb_secret_canonical"


def test_legacy_service_role_is_fallback_but_conflicts_fail_in_production() -> None:
    settings = SimpleNamespace(runtime_profile="production", supabase_secret_key=None)
    assert resolve_supabase_server_key(
        settings=settings,
        environ={
            "QVF_RUNTIME_PROFILE": "production",
            "SUPABASE_SERVICE_ROLE_KEY": "legacy-service-role",
        },
    ) == "legacy-service-role"

    with pytest.raises(ValueError, match="Conflicting"):
        resolve_supabase_server_key(
            settings=settings,
            environ={
                "QVF_RUNTIME_PROFILE": "production",
                "SUPABASE_SECRET_KEY": "sb_secret_canonical",
                "SUPABASE_SERVICE_ROLE_KEY": "different-legacy-key",
            },
        )
