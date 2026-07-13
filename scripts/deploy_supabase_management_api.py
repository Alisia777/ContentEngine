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
DEPLOYMENT_LOCK_NAME = "contentengine_deploy:production"
MAX_RESPONSE_BYTES = 1_048_576
MAX_PRIVATE_SQL_BYTES = 1_048_576
MIGRATION_NAME = re.compile(
    r"^(?P<version>[0-9]{12,20})_[a-z0-9][a-z0-9_]*[.]sql$"
)
TRANSACTION_WRAPPER = re.compile(
    r"\A(?:\ufeff)?\s*begin\s*;(?P<body>.*)commit\s*;\s*\Z",
    flags=re.IGNORECASE | re.DOTALL,
)
DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
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


@dataclass(frozen=True)
class SqlStatement:
    raw: str
    tokens: tuple[str, ...]


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _top_level_statements(sql: str, *, source_label: str) -> list[SqlStatement]:
    """Split SQL on real top-level semicolons, ignoring quoted bodies."""

    statements: list[SqlStatement] = []
    tokens: list[str] = []
    statement_start = 0
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index + 2)
            index = length if newline < 0 else newline + 1
            continue
        if sql.startswith("/*", index):
            depth = 1
            index += 2
            while index < length and depth:
                if sql.startswith("/*", index):
                    depth += 1
                    index += 2
                elif sql.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                raise ConfigurationError(f"{source_label} has an unterminated comment")
            continue
        if char == "'":
            escape_string = (
                index > 0
                and sql[index - 1] in {"e", "E"}
                and (
                    index == 1
                    or not (
                        sql[index - 2].isalnum()
                        or sql[index - 2] in {"_", "$"}
                    )
                )
            )
            index += 1
            while index < length:
                if escape_string and sql[index] == "\\":
                    if index + 1 >= length:
                        raise ConfigurationError(
                            f"{source_label} has an unterminated escape string"
                        )
                    index += 2
                    continue
                if (
                    not escape_string
                    and sql[index] == "\\"
                    and index + 1 < length
                    and sql[index + 1] == "'"
                ):
                    raise ConfigurationError(
                        f"{source_label} has an ambiguous backslash quote"
                    )
                if sql[index] == "'":
                    if index + 1 < length and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise ConfigurationError(f"{source_label} has an unterminated string")
            continue
        if char == '"':
            tokens.append("__quoted_identifier__")
            index += 1
            while index < length:
                if sql[index] == '"':
                    if index + 1 < length and sql[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise ConfigurationError(
                    f"{source_label} has an unterminated quoted identifier"
                )
            continue
        if char == "$":
            delimiter_match = DOLLAR_QUOTE.match(sql, index)
            if delimiter_match is not None:
                tokens.append("__dollar_quote__")
                delimiter = delimiter_match.group(0)
                closing = sql.find(delimiter, delimiter_match.end())
                if closing < 0:
                    raise ConfigurationError(
                        f"{source_label} has an unterminated dollar quote"
                    )
                index = closing + len(delimiter)
                continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < length and (
                sql[end].isalnum() or sql[end] in {"_", "$"}
            ):
                end += 1
            tokens.append(sql[index:end].casefold())
            index = end
            continue
        if char == ";":
            if tokens:
                statements.append(
                    SqlStatement(
                        raw=sql[statement_start : index + 1].strip(),
                        tokens=tuple(tokens),
                    )
                )
            tokens = []
            statement_start = index + 1
            index += 1
            continue
        index += 1

    if tokens:
        statements.append(
            SqlStatement(raw=sql[statement_start:].strip(), tokens=tuple(tokens))
        )
    return statements


def _is_transaction_control(tokens: tuple[str, ...]) -> bool:
    if not tokens:
        return False
    first = tokens[0]
    if first in {
        "abort",
        "begin",
        "commit",
        "end",
        "prepare",
        "release",
        "rollback",
        "savepoint",
        "start",
    }:
        return True
    return first == "set" and len(tokens) > 1 and tokens[1] in {
        "session",
        "transaction",
    }


def _unwrap_transaction(sql: str, *, source_label: str) -> str:
    statements = _top_level_statements(sql, source_label=source_label)
    if (
        len(statements) < 3
        or statements[0].tokens != ("begin",)
        or statements[-1].tokens != ("commit",)
    ):
        raise ConfigurationError(
            f"{source_label} must have one explicit BEGIN/COMMIT wrapper"
        )
    if any(_is_transaction_control(item.tokens) for item in statements[1:-1]):
        raise ConfigurationError(f"{source_label} contains transaction control")

    match = TRANSACTION_WRAPPER.fullmatch(sql)
    if match is None:
        raise ConfigurationError(
            f"{source_label} must have one explicit BEGIN/COMMIT wrapper"
        )
    body = match.group("body").strip()
    if not body:
        raise ConfigurationError(f"{source_label} is empty")
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


PRIVATE_EXAM_CONTRACT_SQL = """
do $contentengine_exam_contract$
declare
  answer_total integer;
  exam_answer_total integer;
begin
  select count(*) into answer_total
  from content_factory_private.training_answer_keys;

  select count(*) into exam_answer_total
  from content_factory_private.training_answer_keys answer_key
  join content_factory.training_questions question
    on question.code = answer_key.question_code
  where question.module_code = 'operator_final_exam';

  if answer_total <> 12 or exam_answer_total <> 12 then
    raise exception using
      errcode = '23514',
      message = 'private_exam_key_contract_failed';
  end if;
end;
$contentengine_exam_contract$;
""".strip()


def _contains_token_sequence(
    tokens: tuple[str, ...],
    expected: tuple[str, ...],
) -> bool:
    width = len(expected)
    return any(
        tokens[index : index + width] == expected
        for index in range(len(tokens) - width + 1)
    )


def _is_approved_catalog_case_select(tokens: tuple[str, ...]) -> bool:
    """Accept the existing secret's data-only catalog answer projection."""

    prefix = ("select", "q", "code", "case", "q", "code")
    suffix = (
        "else",
        "jsonb",
        "end",
        "from",
        "content_factory",
        "training_questions",
        "q",
        "where",
        "q",
        "module_code",
    )
    if (
        len(tokens) <= len(prefix) + len(suffix)
        or tokens[: len(prefix)] != prefix
        or tokens[-len(suffix) :] != suffix
    ):
        return False

    cursor = len(prefix)
    case_limit = len(tokens) - len(suffix)
    case_count = 0
    while cursor < case_limit:
        if tokens[cursor : cursor + 3] != (
            "when",
            "then",
            "jsonb_build_array",
        ):
            return False
        cursor += 3
        option_count = 0
        while tokens[cursor : cursor + 2] == ("q", "options"):
            cursor += 2
            option_count += 1
        if option_count < 1:
            return False
        case_count += 1
    return cursor == case_limit and case_count == 12


SQL_LITERAL = re.compile(r"'(?:''|[^'])*'", flags=re.DOTALL)
APPROVED_UPSERT_CLAUSE = re.compile(
    r"""
    on\s+conflict\s*\(\s*question_code\s*\)\s+do\s+update\s+set\s+
    correct_answers\s*=\s*excluded\s*\.\s*correct_answers\s*,\s*
    rubric\s*=\s*excluded\s*\.\s*rubric
    (?:\s*,\s*updated_at\s*=\s*now\s*\(\s*\))?
    \s*;\s*\Z
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
APPROVED_CATALOG_SCOPE = re.compile(
    r"""
    from\s+content_factory\s*\.\s*training_questions\s+q\s+
    where\s+q\s*\.\s*module_code\s*=\s*
    __operator_final_exam_literal__\s+
    on\s+conflict\s*\(\s*question_code\s*\)
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def _masked_sql_structure(sql: str) -> str:
    def replace_literal(match: re.Match[str]) -> str:
        value = match.group(0)[1:-1].replace("''", "'")
        if value == "operator_final_exam":
            return " __operator_final_exam_literal__ "
        return " __literal__ "

    return SQL_LITERAL.sub(replace_literal, sql)


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

    all_statements = _top_level_statements(
        sql,
        source_label="Private exam-key payload",
    )
    if not all_statements or all_statements[0].tokens != ("begin",):
        raise ConfigurationError(
            "Private exam-key payload must have an explicit transaction wrapper"
        )
    statements = all_statements[1:]
    trailing_commits = 0
    while statements and statements[-1].tokens == ("commit",):
        statements = statements[:-1]
        trailing_commits += 1
    # The already-provisioned secret may contain the original migration COMMIT
    # plus its envelope COMMIT. Neither is ever sent back to the database.
    if trailing_commits not in {1, 2}:
        raise ConfigurationError(
            "Private exam-key payload must have an explicit transaction wrapper"
        )
    if any(_is_transaction_control(item.tokens) for item in statements):
        raise ConfigurationError("Private exam-key payload contains transaction control")
    if len(statements) != 2:
        raise ConfigurationError("Private exam-key payload has an unexpected shape")

    insert, supplied_contract = statements
    required_prefix = (
        "insert",
        "into",
        "content_factory_private",
        "training_answer_keys",
        "question_code",
        "correct_answers",
        "rubric",
    )
    required_upsert = (
        "on",
        "conflict",
        "question_code",
        "do",
        "update",
        "set",
    )
    if insert.tokens[: len(required_prefix)] != required_prefix:
        raise ConfigurationError(
            "Private exam-key payload may only upsert the approved answer table"
        )
    source_index = len(required_prefix)
    upsert_index = next(
        (
            index
            for index in range(
                source_index + 1,
                len(insert.tokens) - len(required_upsert) + 1,
            )
            if insert.tokens[index : index + len(required_upsert)]
            == required_upsert
        ),
        -1,
    )
    source_keyword = (
        insert.tokens[source_index]
        if source_index < len(insert.tokens)
        else ""
    )
    approved_catalog_select = (
        source_keyword == "select"
        and upsert_index > source_index
        and _is_approved_catalog_case_select(
            insert.tokens[source_index:upsert_index]
        )
    )
    masked_insert = _masked_sql_structure(insert.raw)
    contains_comment = "--" in masked_insert or "/*" in masked_insert
    if (
        upsert_index < 0
        or source_keyword not in {"select", "values"}
        or (source_keyword == "select" and not approved_catalog_select)
        or contains_comment
        or APPROVED_UPSERT_CLAUSE.search(masked_insert) is None
        or (
            approved_catalog_select
            and APPROVED_CATALOG_SCOPE.search(masked_insert) is None
        )
    ):
        raise ConfigurationError(
            "Private exam-key payload may only upsert the approved answer table"
        )
    forbidden_tokens = {
        "alter",
        "call",
        "copy",
        "create",
        "delete",
        "drop",
        "grant",
        "revoke",
        "select",
        "truncate",
    }
    allowed_source_keyword = {"select"} if approved_catalog_select else set()
    if forbidden_tokens.intersection(insert.tokens) - allowed_source_keyword:
        raise ConfigurationError("Private exam-key payload contains forbidden SQL")
    allowed_insert_tokens = {
        "conflict",
        "content_factory_private",
        "correct_answers",
        "do",
        "e",
        "excluded",
        "insert",
        "into",
        "jsonb",
        "jsonb_build_array",
        "now",
        "null",
        "on",
        "question_code",
        "rubric",
        "set",
        "training_answer_keys",
        "update",
        "updated_at",
        "values",
    }
    if approved_catalog_select:
        allowed_insert_tokens.update(
            {
                "case",
                "code",
                "content_factory",
                "else",
                "end",
                "from",
                "module_code",
                "options",
                "q",
                "select",
                "then",
                "training_questions",
                "when",
                "where",
            }
        )
    if set(insert.tokens) - allowed_insert_tokens:
        raise ConfigurationError(
            "Private exam-key payload contains an unapproved expression"
        )

    # Validate but do not execute the secret-supplied DO block. The deployer owns
    # the exact contract check below, so the secret can only provide answer data.
    if (
        supplied_contract.tokens != ("do", "__dollar_quote__")
        or re.match(
            r"^\s*do\s+\$catalog_contract\$",
            supplied_contract.raw,
            flags=re.IGNORECASE,
        )
        is None
    ):
        raise ConfigurationError(
            "Private exam-key payload has an unexpected catalog contract"
        )
    return f"{insert.raw}\n{PRIVATE_EXAM_CONTRACT_SQL}"


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
select pg_advisory_xact_lock(hashtextextended('{DEPLOYMENT_LOCK_NAME}', 0));
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


def _deployment_transaction(
    *,
    migrations: list[Migration],
    remote_history: dict[str, str],
    private_exam_sql_body: str,
) -> tuple[str, list[str]]:
    pending = [
        migration
        for migration in migrations
        if migration.version not in remote_history
    ]
    expected_rows = ",\n".join(
        f"({_sql_literal(version)}, {_sql_literal(checksum)})"
        for version, checksum in sorted(remote_history.items())
    )
    if expected_rows:
        history_match = f"""
if exists (
  select 1
  from (values {expected_rows}) expected(version, sha256)
  left join {HISTORY_SCHEMA}.{HISTORY_TABLE} actual
    on actual.version = expected.version
  where actual.sha256 is distinct from expected.sha256
) then
  raise exception using message = 'deployment_history_changed_retry';
end if;
""".strip()
    else:
        history_match = ""

    migration_blocks: list[str] = []
    for migration in pending:
        version = _sql_literal(migration.version)
        checksum = _sql_literal(migration.sha256)
        migration_blocks.append(
            f"""
{migration.body}
insert into {HISTORY_SCHEMA}.{HISTORY_TABLE} (version, sha256)
values ({version}, {checksum});
""".strip()
        )

    guard = f"""
do $contentengine_deployment_guard$
begin
  if (select count(*) from {HISTORY_SCHEMA}.{HISTORY_TABLE})
       <> {len(remote_history)} then
    raise exception using message = 'deployment_history_changed_retry';
  end if;
  {history_match}
end;
$contentengine_deployment_guard$;
""".strip()
    sql = f"""
begin;
select pg_advisory_xact_lock(hashtextextended('{DEPLOYMENT_LOCK_NAME}', 0));
{guard}
{os.linesep.join(migration_blocks)}
{private_exam_sql_body}
commit;
""".strip()
    return sql, [migration.version for migration in pending]


def deploy(
    *,
    client: ManagementApiClient,
    migrations: list[Migration],
    private_exam_sql_body: str,
) -> list[str]:
    client.execute(HISTORY_BOOTSTRAP_SQL)
    remote_history = read_remote_history(client)
    _validate_history_prefix(migrations, remote_history)

    deployment_sql, applied = _deployment_transaction(
        migrations=migrations,
        remote_history=remote_history,
        private_exam_sql_body=private_exam_sql_body,
    )
    client.execute(deployment_sql)
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
