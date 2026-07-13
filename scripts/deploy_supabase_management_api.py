#!/usr/bin/env python3
"""Apply production Supabase SQL through the official Management API.

The deployer intentionally uses only the Python standard library.  SQL and
credentials are never written to disk or included in error messages.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Any, Callable, Iterable
from urllib import error, request


EXPECTED_PROJECT_REF = "iyckwryrucqrxwlowxow"
MANAGEMENT_API_ORIGIN = "https://api.supabase.com"
HISTORY_SCHEMA = "contentengine_deploy"
HISTORY_TABLE = "schema_migrations"
MAX_RESPONSE_BYTES = 1_048_576
MAX_PRIVATE_SQL_BYTES = 1_048_576
MIGRATION_NAME = re.compile(
    r"^(?P<version>[0-9]{12,20})_[a-z0-9][a-z0-9_]*[.]sql$"
)
TRANSACTION_WRAPPER = re.compile(
    r"\A(?:\ufeff)?\s*begin\s*;(?P<body>.*)commit\s*;\s*\Z",
    flags=re.IGNORECASE | re.DOTALL,
)
INNER_TRANSACTION_CONTROL = re.compile(
    r"^\s*(?:begin|commit|rollback|start\s+transaction)\s*;\s*(?:--.*)?$",
    flags=re.IGNORECASE | re.MULTILINE,
)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DeploymentError(RuntimeError):
    """A safe-to-display deployment failure."""


class ConfigurationError(DeploymentError):
    """A fail-closed configuration failure."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sha256: str
    body: str


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _unwrap_transaction(sql: str, *, source_label: str) -> str:
    match = TRANSACTION_WRAPPER.fullmatch(sql)
    if match is None:
        raise ConfigurationError(
            f"{source_label} must have one explicit BEGIN/COMMIT wrapper"
        )
    body = match.group("body").strip()
    if not body:
        raise ConfigurationError(f"{source_label} is empty")
    if INNER_TRANSACTION_CONTROL.search(body):
        raise ConfigurationError(
            f"{source_label} contains nested transaction control"
        )
    return body


def load_migrations(directory: Path) -> list[Migration]:
    if not directory.is_dir():
        raise ConfigurationError("Supabase migrations directory is missing")

    paths = sorted(directory.glob("*.sql"), key=lambda item: item.name)
    if not paths:
        raise ConfigurationError("No Supabase migrations were found")

    migrations: list[Migration] = []
    versions: set[str] = set()
    for path in paths:
        name_match = MIGRATION_NAME.fullmatch(path.name)
        if name_match is None:
            raise ConfigurationError("A migration filename has an invalid format")
        version = name_match.group("version")
        if version in versions:
            raise ConfigurationError("Duplicate Supabase migration version")
        versions.add(version)

        raw = path.read_bytes()
        try:
            sql = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ConfigurationError("A migration is not valid UTF-8") from exc
        migrations.append(
            Migration(
                version=version,
                path=path,
                sha256=hashlib.sha256(raw).hexdigest(),
                body=_unwrap_transaction(sql, source_label=path.name),
            )
        )

    if [item.version for item in migrations] != sorted(
        item.version for item in migrations
    ):
        raise ConfigurationError("Supabase migrations are not version-sorted")
    return migrations


def decode_private_exam_sql(encoded: str) -> str:
    if not encoded or not encoded.strip():
        raise ConfigurationError("SUPABASE_EXAM_KEYS_B64 is required")
    try:
        payload = base64.b64decode(encoded.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigurationError("SUPABASE_EXAM_KEYS_B64 is not valid base64") from exc
    if not payload or len(payload) > MAX_PRIVATE_SQL_BYTES:
        raise ConfigurationError("Private exam-key payload has an invalid size")
    try:
        sql = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigurationError("Private exam-key payload is not valid UTF-8") from exc

    normalized = sql.casefold()
    required_markers = (
        "content_factory_private.training_answer_keys",
        "correct_answers",
        "catalog_contract",
    )
    if any(marker not in normalized for marker in required_markers):
        raise ConfigurationError("Private exam-key payload targets an unexpected contract")

    # The private payload is data provisioning, never a schema/role management path.
    forbidden = re.compile(
        r"^\s*(?:drop|alter|create|truncate|grant|revoke|copy|call)\b",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if forbidden.search(sql):
        raise ConfigurationError("Private exam-key payload contains forbidden SQL")
    return _unwrap_transaction(sql, source_label="Private exam-key payload")


class ManagementApiClient:
    def __init__(
        self,
        *,
        project_ref: str,
        access_token: str,
        opener: Callable[..., Any] = request.urlopen,
        timeout_seconds: int = 60,
    ) -> None:
        if project_ref != EXPECTED_PROJECT_REF:
            raise ConfigurationError(
                "SUPABASE_PROJECT_REF does not match the reviewed production project"
            )
        if not access_token or not access_token.strip():
            raise ConfigurationError("SUPABASE_ACCESS_TOKEN is required")
        self._project_ref = project_ref
        self._access_token = access_token.strip()
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    @property
    def endpoint(self) -> str:
        return (
            f"{MANAGEMENT_API_ORIGIN}/v1/projects/"
            f"{self._project_ref}/database/query"
        )

    def execute(self, sql: str, *, read_only: bool = False) -> Any:
        body = json.dumps(
            {"query": sql, "read_only": read_only},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        api_request = request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "User-Agent": "ContentEngine-Supabase-Deployer/1",
            },
        )
        try:
            with self._opener(
                api_request,
                timeout=self._timeout_seconds,
            ) as response:
                status = int(getattr(response, "status", 200))
                response_body = response.read(MAX_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            # Deliberately discard the response body: PostgreSQL errors can quote SQL.
            try:
                exc.close()
            finally:
                raise DeploymentError(
                    f"Supabase Management API request failed (HTTP {exc.code})"
                ) from None
        except (error.URLError, TimeoutError, OSError):
            raise DeploymentError("Supabase Management API request failed") from None

        if status < 200 or status >= 300:
            raise DeploymentError(
                f"Supabase Management API request failed (HTTP {status})"
            )
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise DeploymentError("Supabase Management API response was too large")
        if not response_body:
            return None
        try:
            return json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DeploymentError(
                "Supabase Management API returned an invalid response"
            ) from None


HISTORY_BOOTSTRAP_SQL = f"""
begin;
create schema if not exists {HISTORY_SCHEMA};
revoke all on schema {HISTORY_SCHEMA} from public, anon, authenticated;
create table if not exists {HISTORY_SCHEMA}.{HISTORY_TABLE} (
  version text primary key,
  sha256 text not null,
  applied_at timestamptz not null default now(),
  constraint schema_migrations_version_format
    check (version ~ '^[0-9]{{12,20}}$'),
  constraint schema_migrations_sha256_format
    check (sha256 ~ '^[0-9a-f]{{64}}$')
);
revoke all on table {HISTORY_SCHEMA}.{HISTORY_TABLE}
  from public, anon, authenticated;
commit;
""".strip()

HISTORY_SELECT_SQL = (
    f"select version, sha256 from {HISTORY_SCHEMA}.{HISTORY_TABLE} "
    "order by version"
)


def _rows_from_response(payload: Any) -> list[dict[str, Any]]:
    rows = payload
    if isinstance(payload, dict):
        for key in ("result", "data"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise DeploymentError("Supabase migration history response was invalid")
    return rows


def read_remote_history(client: ManagementApiClient) -> dict[str, str]:
    payload = client.execute(HISTORY_SELECT_SQL, read_only=True)
    rows = _rows_from_response(payload)
    history: dict[str, str] = {}
    for row in rows:
        version = row.get("version")
        checksum = row.get("sha256")
        if (
            not isinstance(version, str)
            or MIGRATION_NAME.fullmatch(f"{version}_migration.sql") is None
            or not isinstance(checksum, str)
            or HEX_SHA256.fullmatch(checksum) is None
            or version in history
        ):
            raise DeploymentError("Supabase migration history contains invalid data")
        history[version] = checksum
    return history


def _validate_history_prefix(
    migrations: Iterable[Migration],
    remote_history: dict[str, str],
) -> None:
    local = list(migrations)
    local_by_version = {migration.version: migration for migration in local}
    for version, checksum in remote_history.items():
        migration = local_by_version.get(version)
        if migration is None:
            raise DeploymentError(
                "Remote migration history is not present in this checkout"
            )
        if migration.sha256 != checksum:
            raise DeploymentError(
                f"Immutable checksum mismatch for migration {version}"
            )

    applied_versions = sorted(remote_history)
    expected_prefix = [item.version for item in local[: len(applied_versions)]]
    if applied_versions != expected_prefix:
        raise DeploymentError("Remote migration history is not a valid local prefix")


def _migration_transaction(migration: Migration) -> str:
    version = _sql_literal(migration.version)
    checksum = _sql_literal(migration.sha256)
    return f"""
begin;
select pg_advisory_xact_lock(hashtextextended('contentengine_deploy:migrations', 0));
{migration.body}
insert into {HISTORY_SCHEMA}.{HISTORY_TABLE} (version, sha256)
values ({version}, {checksum});
commit;
""".strip()


def _private_exam_transaction(private_sql_body: str) -> str:
    return f"""
begin;
select pg_advisory_xact_lock(hashtextextended('contentengine_deploy:exam-keys', 0));
{private_sql_body}
commit;
""".strip()


def deploy(
    *,
    client: ManagementApiClient,
    migrations: list[Migration],
    private_exam_sql_body: str,
) -> list[str]:
    client.execute(HISTORY_BOOTSTRAP_SQL)
    remote_history = read_remote_history(client)
    _validate_history_prefix(migrations, remote_history)

    applied: list[str] = []
    for migration in migrations:
        if migration.version in remote_history:
            continue
        client.execute(_migration_transaction(migration))
        remote_history[migration.version] = migration.sha256
        applied.append(migration.version)

    client.execute(_private_exam_transaction(private_exam_sql_body))
    return applied


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deploy Supabase SQL with the official Management API",
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path("supabase/migrations"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
        access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
        private_exam_encoded = os.environ.get("SUPABASE_EXAM_KEYS_B64", "")
        client = ManagementApiClient(
            project_ref=project_ref,
            access_token=access_token,
        )
        migrations = load_migrations(args.migrations_dir)
        private_exam_sql_body = decode_private_exam_sql(private_exam_encoded)
        applied = deploy(
            client=client,
            migrations=migrations,
            private_exam_sql_body=private_exam_sql_body,
        )
    except DeploymentError as exc:
        print(f"Supabase deployment stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        # Do not let an unexpected exception expose a SQL payload via diagnostics.
        print("Supabase deployment stopped: unexpected internal failure", file=sys.stderr)
        return 1

    if applied:
        print(f"Applied {len(applied)} immutable Supabase migration(s).")
    else:
        print("Supabase migrations are already current.")
    print("Private exam grading data was provisioned without logging its contents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
