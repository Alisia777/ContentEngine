from pathlib import Path
from types import SimpleNamespace

import httpx

from app.readiness import (
    ApplicationReadinessService,
    CRITICAL_TABLES,
    SupabaseReadinessProbe,
    SupabaseReadinessResult,
)


def _settings(**overrides):
    values = {
        "runtime_profile": "production",
        "auth_required": True,
        "storage_backend": "supabase",
        "supabase_url": "https://project.supabase.co",
        "supabase_jwks_url": None,
        "supabase_publishable_key": "publishable-test-key",
        "supabase_secret_key": "sb_secret_readiness-test-only",
        "supabase_storage_bucket": "contentengine-private",
        "supabase_readiness_timeout_seconds": 0.75,
        "s3_endpoint_url": None,
        "s3_bucket": None,
        "s3_access_key_id": None,
        "s3_secret_access_key": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _healthy_response(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/v1/.well-known/jwks.json":
        return httpx.Response(
            200,
            json={
                "keys": [
                    {
                        "kty": "EC",
                        "kid": "current-signing-key",
                        "use": "sig",
                        "alg": "ES256",
                        "crv": "P-256",
                        "x": "test-x-coordinate",
                        "y": "test-y-coordinate",
                    }
                ]
            },
        )
    if request.url.path == "/auth/v1/settings":
        return httpx.Response(200, json={"external": {}, "disable_signup": True})
    if request.url.path == "/storage/v1/bucket/contentengine-private":
        return httpx.Response(
            200,
            json={
                "id": "contentengine-private",
                "name": "contentengine-private",
                "public": False,
            },
        )
    raise AssertionError(f"unexpected readiness path: {request.url.path}")


def test_supabase_probe_is_bounded_read_only_and_confirms_private_bucket() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _healthy_response(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(),
            client=client,
        ).check(include_storage=True)

    assert result == SupabaseReadinessResult(
        jwks_ready=True,
        auth_api_ready=True,
        storage_private=True,
        errors=(),
    )
    assert [request.method for request in requests] == ["GET", "GET", "GET"]
    assert all(request.content == b"" for request in requests)
    assert requests[0].headers.get("apikey") is None
    assert requests[1].headers["apikey"] == "publishable-test-key"
    assert requests[2].headers["apikey"] == "sb_secret_readiness-test-only"
    for request in requests:
        phase_timeouts = request.extensions["timeout"]
        assert all(0 < float(value) <= 0.75 for value in phase_timeouts.values())


def test_supabase_probe_rejects_empty_jwks_and_public_bucket() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json"):
            return httpx.Response(200, json={"keys": []})
        if request.url.path.endswith("/settings"):
            return _healthy_response(request)
        return httpx.Response(
            200,
            json={"id": "contentengine-private", "public": True},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(),
            client=client,
        ).check(include_storage=True)

    assert not result.jwks_ready
    assert result.storage_private is False
    assert set(result.errors) == {
        "supabase_jwks_invalid",
        "supabase_storage_bucket_public",
    }


def test_supabase_probe_fails_closed_on_rejected_credentials_without_leaking_secret() -> None:
    secret = "sb_secret_must-never-appear-in-readiness"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json") or request.url.path.endswith("/settings"):
            return _healthy_response(request)
        return httpx.Response(
            403,
            json={"message": f"rejected key {secret}"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(supabase_secret_key=secret),
            client=client,
        ).check(include_storage=True)

    assert result.jwks_ready
    assert result.auth_api_ready
    assert result.storage_private is False
    assert result.errors == ("supabase_storage_credentials_rejected",)
    assert secret not in repr(result)


def test_supabase_probe_reports_missing_configured_bucket() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json") or request.url.path.endswith("/settings"):
            return _healthy_response(request)
        return httpx.Response(404, json={"message": "Bucket not found"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(),
            client=client,
        ).check(include_storage=True)

    assert result.storage_private is False
    assert result.errors == ("supabase_storage_bucket_missing",)


def test_supabase_probe_rejects_wrong_publishable_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("jwks.json"):
            return _healthy_response(request)
        if request.url.path.endswith("/settings"):
            return httpx.Response(401, json={"message": "invalid API key"})
        return _healthy_response(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(supabase_publishable_key="wrong-publishable-key"),
            client=client,
        ).check(include_storage=True)

    assert result.jwks_ready
    assert not result.auth_api_ready
    assert result.storage_private is True
    assert result.errors == ("supabase_publishable_key_rejected",)


def test_supabase_probe_uses_exact_canonical_storage_factory_credential() -> None:
    selected_key = "sb_secret_canonical-server-key"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/storage/v1/"):
            assert request.headers["apikey"] == selected_key
        return _healthy_response(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(supabase_secret_key="sb_secret_settings-fallback"),
            client=client,
            environ={
                "QVF_RUNTIME_PROFILE": "production",
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_SECRET_KEY": selected_key,
                "QVF_STORAGE_BUCKET": "contentengine-private",
            },
        ).check(include_storage=True)

    assert result.storage_private is True
    assert result.errors == ()


def test_supabase_probe_fails_closed_on_conflicting_legacy_storage_key() -> None:
    with httpx.Client(transport=httpx.MockTransport(_healthy_response)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(),
            client=client,
            environ={
                "QVF_RUNTIME_PROFILE": "production",
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_SECRET_KEY": "sb_secret_canonical",
                "SUPABASE_SERVICE_ROLE_KEY": "different-legacy-key",
                "QVF_STORAGE_BUCKET": "contentengine-private",
            },
        ).check(include_storage=True)

    assert result.storage_private is False
    assert result.errors == ("supabase_storage_not_configured",)


def test_supabase_probe_stops_when_shared_deadline_is_exhausted() -> None:
    requests: list[httpx.Request] = []
    clock_calls = 0

    def clock() -> float:
        nonlocal clock_calls
        clock_calls += 1
        return 0.0 if clock_calls == 1 else 1.0

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _healthy_response(request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = SupabaseReadinessProbe(
            settings=_settings(supabase_readiness_timeout_seconds=0.5),
            client=client,
            clock=clock,
        ).check(include_storage=True)

    assert not result.jwks_ready
    assert not result.auth_api_ready
    assert result.storage_private is False
    assert result.errors == ("supabase_probe_timeout",)
    assert requests == []


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _statement):
        return None


class _FakePostgresEngine:
    dialect = SimpleNamespace(name="postgresql")

    def connect(self):
        return _FakeConnection()


class _FixedProbe:
    def __init__(self, result: SupabaseReadinessResult) -> None:
        self.result = result
        self.include_storage: bool | None = None

    def check(self, *, include_storage: bool) -> SupabaseReadinessResult:
        self.include_storage = include_storage
        return self.result


def test_application_readiness_turns_probe_failure_into_nonready(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.readiness.inspect",
        lambda _engine: SimpleNamespace(get_table_names=lambda: list(CRITICAL_TABLES)),
    )
    probe = _FixedProbe(
        SupabaseReadinessResult(
            jwks_ready=True,
            auth_api_ready=True,
            storage_private=False,
            errors=("supabase_storage_bucket_public",),
        )
    )

    result = ApplicationReadinessService(
        settings=_settings(),
        database_engine=_FakePostgresEngine(),
        supabase_probe=probe,
        migration_head_checker=lambda _connection: True,
    ).check()

    assert not result.ready
    assert probe.include_storage is True
    assert result.checks["authentication"] is True
    assert result.checks["object_storage"] is False
    assert result.checks["supabase_storage_private"] is False
    assert "supabase_storage_bucket_public" in result.errors


def test_application_readiness_never_returns_probe_exception_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.readiness.inspect",
        lambda _engine: SimpleNamespace(get_table_names=lambda: list(CRITICAL_TABLES)),
    )
    secret = "server-key-that-must-not-leak"

    class ExplodingProbe:
        def check(self, *, include_storage: bool) -> SupabaseReadinessResult:
            raise RuntimeError(f"provider rejected {secret}")

    result = ApplicationReadinessService(
        settings=_settings(),
        database_engine=_FakePostgresEngine(),
        supabase_probe=ExplodingProbe(),
        migration_head_checker=lambda _connection: True,
    ).check()
    payload = result.payload()

    assert not result.ready
    assert result.errors == ["supabase_probe_failed"]
    assert secret not in repr(payload)


def test_application_readiness_fails_when_database_is_not_at_alembic_head(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.readiness.inspect",
        lambda _engine: SimpleNamespace(get_table_names=lambda: list(CRITICAL_TABLES)),
    )
    probe = _FixedProbe(
        SupabaseReadinessResult(
            jwks_ready=True,
            auth_api_ready=True,
            storage_private=True,
            errors=(),
        )
    )

    result = ApplicationReadinessService(
        settings=_settings(),
        database_engine=_FakePostgresEngine(),
        supabase_probe=probe,
        migration_head_checker=lambda _connection: False,
    ).check()

    assert not result.ready
    assert result.checks["migration_head"] is False
    assert "migration_head_mismatch" in result.errors


def test_readiness_endpoint_is_repository_managed() -> None:
    root = Path(__file__).resolve().parents[1]
    router = (root / "app" / "routers" / "readiness.py").read_text(encoding="utf-8")
    service = (root / "app" / "readiness.py").read_text(encoding="utf-8")

    assert '@router.get("/ready"' in router
    assert "status_code=200 if result.ready else 503" in router
    assert "production_requires_postgresql" in service
    assert "production_auth_not_configured" in service
    assert "production_storage_not_configured" in service
    assert "supabase_jwks" in service
    assert "supabase_auth_api" in service
    assert "supabase_storage_private" in service
    assert "migration_head" in service
    assert "media_artifacts" in service
