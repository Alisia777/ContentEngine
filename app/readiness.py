from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
import os
import time
from typing import Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import (
    Settings,
    get_settings,
    normalized_supabase_base_url,
    supabase_jwks_url_for_base,
)
from app.database import engine
from app.media_storage.factory import resolve_supabase_storage_runtime_config
from app.migration_state import database_is_at_migration_head
from app.postgres_security import (
    PostgresPublicSchemaSecurityResult,
    inspect_postgresql_public_schema_security,
)
from app.supabase_keys import server_api_key_headers


CRITICAL_TABLES = frozenset(
    {
        "organizations",
        "user_profiles",
        "memberships",
        "products",
        "product_ugc_generation_jobs",
        "public_training_modules",
        "public_training_certifications",
        "media_artifacts",
        "mass_operation_batches",
        "creator_tasks",
        "creator_payouts",
        "publishing_packages",
    }
)


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    checks: dict[str, bool]
    errors: list[str]

    def payload(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "blocked",
            "checks": self.checks,
            "errors": self.errors,
        }


@dataclass(frozen=True)
class SupabaseReadinessResult:
    jwks_ready: bool
    auth_api_ready: bool
    storage_private: bool | None
    errors: tuple[str, ...]


class SupabaseProbe(Protocol):
    def check(self, *, include_storage: bool) -> SupabaseReadinessResult: ...


class _ProbeDeadlineExceeded(RuntimeError):
    pass


class SupabaseReadinessProbe:
    """Read-only, secret-safe probes for Supabase Auth and Storage.

    The probe performs GET requests only.  The private bucket check uses the
    server API key to fetch bucket metadata and never creates, lists, or reads
    an object.  Provider bodies and transport exceptions are deliberately not
    copied into readiness results.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        clock=time.monotonic,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client
        self.clock = clock
        self.environ = dict(os.environ if environ is None else environ)

    def check(self, *, include_storage: bool) -> SupabaseReadinessResult:
        timeout_seconds = max(
            0.5,
            min(
                float(
                    getattr(
                        self.settings,
                        "supabase_readiness_timeout_seconds",
                        5.0,
                    )
                ),
                15.0,
            ),
        )
        deadline = self.clock() + timeout_seconds
        if self.client is not None:
            return self._check_with_client(
                self.client,
                deadline=deadline,
                include_storage=include_storage,
            )
        with httpx.Client(follow_redirects=False) as client:
            return self._check_with_client(
                client,
                deadline=deadline,
                include_storage=include_storage,
            )

    def _check_with_client(
        self,
        client: httpx.Client,
        *,
        deadline: float,
        include_storage: bool,
    ) -> SupabaseReadinessResult:
        errors: list[str] = []
        jwks_ready = self._probe_jwks(client, deadline=deadline, errors=errors)
        auth_api_ready = self._probe_auth_api(
            client,
            deadline=deadline,
            errors=errors,
        )
        storage_private: bool | None = None
        if include_storage:
            storage_private = self._probe_private_bucket(
                client,
                deadline=deadline,
                errors=errors,
            )
        return SupabaseReadinessResult(
            jwks_ready=jwks_ready,
            auth_api_ready=auth_api_ready,
            storage_private=storage_private,
            errors=tuple(dict.fromkeys(errors)),
        )

    def _probe_jwks(
        self,
        client: httpx.Client,
        *,
        deadline: float,
        errors: list[str],
    ) -> bool:
        project_url = normalized_supabase_base_url(
            getattr(self.settings, "supabase_url", None)
        )
        if not project_url:
            errors.append("supabase_jwks_not_configured")
            return False
        jwks_url = supabase_jwks_url_for_base(project_url)
        try:
            response = client.get(
                jwks_url,
                headers={"accept": "application/json"},
                timeout=self._http_timeout(deadline),
                follow_redirects=False,
            )
        except _ProbeDeadlineExceeded:
            errors.append("supabase_probe_timeout")
            return False
        except (httpx.TimeoutException, httpx.TransportError, httpx.InvalidURL):
            errors.append("supabase_jwks_unavailable")
            return False
        if not 200 <= response.status_code < 300:
            errors.append("supabase_jwks_unavailable")
            return False
        try:
            payload = response.json()
        except ValueError:
            errors.append("supabase_jwks_invalid")
            return False
        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list) or not any(self._usable_signing_jwk(key) for key in keys):
            errors.append("supabase_jwks_invalid")
            return False
        return True

    @staticmethod
    def _usable_signing_jwk(value: object) -> bool:
        if not isinstance(value, dict):
            return False
        if not isinstance(value.get("kid"), str) or not value["kid"].strip():
            return False
        if value.get("use") not in {None, "sig"}:
            return False
        algorithm = value.get("alg")
        key_type = value.get("kty")
        if algorithm == "RS256" and key_type == "RSA":
            return all(
                isinstance(value.get(field), str) and bool(value[field].strip())
                for field in ("n", "e")
            )
        if algorithm == "ES256" and key_type == "EC" and value.get("crv") == "P-256":
            return all(
                isinstance(value.get(field), str) and bool(value[field].strip())
                for field in ("x", "y")
            )
        return False

    def _probe_auth_api(
        self,
        client: httpx.Client,
        *,
        deadline: float,
        errors: list[str],
    ) -> bool:
        project_url = normalized_supabase_base_url(
            getattr(self.settings, "supabase_url", None)
        )
        publishable_key = str(
            getattr(self.settings, "supabase_publishable_key", "") or ""
        ).strip()
        if not project_url or not publishable_key:
            errors.append("supabase_auth_api_not_configured")
            return False
        try:
            response = client.get(
                f"{project_url}/auth/v1/settings",
                headers={
                    "accept": "application/json",
                    "apikey": publishable_key,
                },
                timeout=self._http_timeout(deadline),
                follow_redirects=False,
            )
        except _ProbeDeadlineExceeded:
            errors.append("supabase_probe_timeout")
            return False
        except (httpx.TimeoutException, httpx.TransportError, httpx.InvalidURL):
            errors.append("supabase_auth_api_unavailable")
            return False
        if response.status_code in {401, 403}:
            errors.append("supabase_publishable_key_rejected")
            return False
        if not 200 <= response.status_code < 300:
            errors.append("supabase_auth_api_unavailable")
            return False
        try:
            payload = response.json()
        except ValueError:
            errors.append("supabase_auth_api_invalid")
            return False
        if not isinstance(payload, dict):
            errors.append("supabase_auth_api_invalid")
            return False
        return True

    def _probe_private_bucket(
        self,
        client: httpx.Client,
        *,
        deadline: float,
        errors: list[str],
    ) -> bool:
        try:
            storage_config = resolve_supabase_storage_runtime_config(
                settings=self.settings,
                environ=self.environ,
            )
        except Exception:
            errors.append("supabase_storage_not_configured")
            return False
        try:
            headers = {
                **server_api_key_headers(storage_config.server_key),
                "accept": "application/json",
            }
        except ValueError:
            errors.append("supabase_storage_credentials_invalid")
            return False
        bucket_url = (
            f"{storage_config.project_url.rstrip('/')}/storage/v1/bucket/"
            f"{quote(storage_config.bucket, safe='-_.~')}"
        )
        try:
            response = client.get(
                bucket_url,
                headers=headers,
                timeout=self._http_timeout(deadline),
                follow_redirects=False,
            )
        except _ProbeDeadlineExceeded:
            errors.append("supabase_probe_timeout")
            return False
        except (httpx.TimeoutException, httpx.TransportError, httpx.InvalidURL):
            errors.append("supabase_storage_unavailable")
            return False
        if response.status_code in {401, 403}:
            errors.append("supabase_storage_credentials_rejected")
            return False
        if response.status_code == 404:
            errors.append("supabase_storage_bucket_missing")
            return False
        if not 200 <= response.status_code < 300:
            errors.append("supabase_storage_unavailable")
            return False
        try:
            payload = response.json()
        except ValueError:
            errors.append("supabase_storage_response_invalid")
            return False
        if not isinstance(payload, dict):
            errors.append("supabase_storage_response_invalid")
            return False
        bucket_identity = payload.get("id") or payload.get("name")
        if str(bucket_identity or "") != storage_config.bucket:
            errors.append("supabase_storage_response_invalid")
            return False
        if payload.get("public") is not False:
            errors.append("supabase_storage_bucket_public")
            return False
        return True

    def _remaining_timeout(self, deadline: float) -> float:
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise _ProbeDeadlineExceeded
        return max(0.001, min(remaining, 15.0))

    def _http_timeout(self, deadline: float) -> httpx.Timeout:
        remaining = self._remaining_timeout(deadline)
        return httpx.Timeout(
            timeout=remaining,
            connect=min(remaining, 2.0),
            write=min(remaining, 2.0),
            pool=min(remaining, 1.0),
        )


class ApplicationReadinessService:
    """Secret-free checks for a production web instance."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        database_engine=None,
        supabase_probe: SupabaseProbe | None = None,
        migration_head_checker: Callable[[object], bool] | None = None,
        database_security_checker: Callable[
            [object, Collection[str]],
            PostgresPublicSchemaSecurityResult,
        ]
        | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.engine = database_engine or engine
        self.supabase_probe = supabase_probe
        self.migration_head_checker = (
            migration_head_checker or database_is_at_migration_head
        )
        self.database_security_checker = (
            database_security_checker
            or inspect_postgresql_public_schema_security
        )

    def check(self) -> ReadinessResult:
        settings = self.settings
        checks: dict[str, bool] = {}
        errors: list[str] = []
        production = (
            str(getattr(settings, "runtime_profile", "development")).casefold()
            == "production"
        )

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["database"] = True
        except SQLAlchemyError:
            checks["database"] = False
            errors.append("database_unavailable")

        checks["migration_head"] = not production
        if production:
            try:
                with self.engine.connect() as connection:
                    checks["migration_head"] = bool(
                        self.migration_head_checker(connection)
                    )
            except Exception:
                checks["migration_head"] = False
                errors.append("migration_state_unavailable")
            if not checks["migration_head"]:
                errors.append("migration_head_mismatch")

        try:
            table_names = set(inspect(self.engine).get_table_names())
            missing_tables = sorted(CRITICAL_TABLES - table_names)
        except SQLAlchemyError:
            missing_tables = sorted(CRITICAL_TABLES)
        checks["schema"] = not missing_tables
        if missing_tables:
            errors.append("schema_missing:" + ",".join(missing_tables))

        checks["production_database"] = (
            not production or self.engine.dialect.name == "postgresql"
        )
        if not checks["production_database"]:
            errors.append("production_requires_postgresql")

        checks["database_rls"] = not production
        checks["database_api_roles_restricted"] = not production
        if production and self.engine.dialect.name == "postgresql":
            try:
                with self.engine.connect() as connection:
                    database_security = self.database_security_checker(
                        connection,
                        CRITICAL_TABLES,
                    )
            except Exception:
                checks["database_rls"] = False
                checks["database_api_roles_restricted"] = False
                errors.append("database_security_state_unavailable")
            else:
                checks["database_rls"] = database_security.rls_enabled
                checks["database_api_roles_restricted"] = (
                    database_security.api_roles_restricted
                )
            if not checks["database_rls"]:
                errors.append("database_rls_not_enabled")
            if not checks["database_api_roles_restricted"]:
                errors.append("database_api_roles_have_table_privileges")
        elif production:
            checks["database_rls"] = False
            checks["database_api_roles_restricted"] = False

        auth_values = (
            bool(settings.auth_required),
            bool(settings.supabase_url),
            bool(getattr(settings, "supabase_publishable_key", None)),
        )
        checks["authentication"] = not production or all(auth_values)
        if not checks["authentication"]:
            errors.append("production_auth_not_configured")

        storage_backend = getattr(settings, "storage_backend", "local")
        if storage_backend == "supabase":
            try:
                storage_config = resolve_supabase_storage_runtime_config(
                    settings=settings,
                )
            except Exception:
                storage_values = (False,)
            else:
                storage_values = (
                    bool(storage_config.project_url),
                    bool(storage_config.server_key),
                    bool(storage_config.bucket),
                )
        elif storage_backend == "s3":
            storage_values = (
                bool(getattr(settings, "s3_endpoint_url", None)),
                bool(getattr(settings, "s3_bucket", None)),
                bool(getattr(settings, "s3_access_key_id", None)),
                bool(getattr(settings, "s3_secret_access_key", None)),
            )
        else:
            storage_values = (False,)
        checks["object_storage"] = not production or all(storage_values)
        if not checks["object_storage"]:
            errors.append("production_storage_not_configured")

        checks["supabase_jwks"] = not production
        checks["supabase_auth_api"] = not production
        checks["supabase_storage_private"] = not production or storage_backend != "supabase"
        if production:
            probe = self.supabase_probe or SupabaseReadinessProbe(settings=settings)
            include_storage = storage_backend == "supabase"
            try:
                probe_result = probe.check(include_storage=include_storage)
            except Exception:
                # This boundary deliberately never exposes exception text: an
                # injected HTTP client may include credentials or URLs in it.
                checks["supabase_jwks"] = False
                checks["supabase_auth_api"] = False
                checks["authentication"] = False
                if include_storage:
                    checks["supabase_storage_private"] = False
                    checks["object_storage"] = False
                errors.append("supabase_probe_failed")
            else:
                checks["supabase_jwks"] = probe_result.jwks_ready
                checks["supabase_auth_api"] = probe_result.auth_api_ready
                checks["authentication"] = (
                    checks["authentication"]
                    and probe_result.jwks_ready
                    and probe_result.auth_api_ready
                )
                if not probe_result.jwks_ready:
                    errors.append("supabase_jwks_not_ready")
                if not probe_result.auth_api_ready:
                    errors.append("supabase_auth_api_not_ready")
                if include_storage:
                    storage_private = probe_result.storage_private is True
                    checks["supabase_storage_private"] = storage_private
                    checks["object_storage"] = (
                        checks["object_storage"] and storage_private
                    )
                    if not storage_private:
                        errors.append("supabase_storage_not_ready")
                errors.extend(probe_result.errors)

        return ReadinessResult(
            ready=not errors,
            checks=checks,
            errors=list(dict.fromkeys(errors)),
        )
