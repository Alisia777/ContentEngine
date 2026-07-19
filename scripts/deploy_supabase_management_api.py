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
MAX_PRIVATE_TRAINING_KEYS_BYTES = 262_144
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
  exam_answer_total integer;
begin
  select count(*) into exam_answer_total
  from content_factory_private.training_answer_keys answer_key
  join content_factory.training_questions question
    on question.code = answer_key.question_code
  where question.module_code = 'operator_final_exam';

  if exam_answer_total <> 12 then
    raise exception using
      errcode = '23514',
      message = 'private_exam_key_contract_failed';
  end if;
end;
$contentengine_exam_contract$;
""".strip()


PRIVATE_TRAINING_CONTRACT_SQL = """
do $contentengine_training_key_contract$
declare
  course_key_total integer;
  platform_key_total integer;
begin
  select count(*) into course_key_total
  from content_factory_private.training_answer_keys answer_key
  join content_factory.training_questions question
    on question.code = answer_key.question_code
  where question.module_code in (
    'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
  )
    and question.order_index between 901 and 906
    and not exists (
      select 1
      from jsonb_array_elements_text(
        answer_key.correct_answers || answer_key.critical_answers
      ) submitted(value)
      where not exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = submitted.value
      )
    );

  select count(*) into platform_key_total
  from content_factory_private.training_platform_answer_keys answer_key
  where answer_key.assessment_version = 1;

  if course_key_total <> 24 or platform_key_total <> 18 then
    raise exception using
      errcode = '23514',
      message = 'private_training_key_contract_failed';
  end if;
end;
$contentengine_training_key_contract$;
""".strip()


PRIVATE_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9_]{1,99}$")
COURSE_KEY_PREFIXES = (
    "course_check_factory_basics_",
    "course_check_video_quality_",
    "course_check_publishing_funnel_",
    "course_check_security_wb_",
)
PLATFORM_KEY_STEPS = (
    "account",
    "warmup",
    "publication",
    "review",
    "link",
    "result",
)


def _private_jsonb_literal(values: list[str]) -> str:
    serialized = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return f"{_sql_literal(serialized)}::jsonb"


def _private_key_list(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> list[str]:
    if (
        not isinstance(value, list)
        or not minimum <= len(value) <= maximum
        or not all(isinstance(item, str) and PRIVATE_KEY_ID.fullmatch(item) for item in value)
        or len(set(value)) != len(value)
    ):
        raise ConfigurationError(f"{label} has an invalid shape")
    return value


def decode_private_training_keys(encoded: str) -> str:
    """Validate private assessment JSON and render data-only upserts."""

    if not encoded or not encoded.strip():
        raise ConfigurationError("SUPABASE_TRAINING_KEYS_B64 is required")
    try:
        raw = base64.b64decode(encoded.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigurationError(
            "SUPABASE_TRAINING_KEYS_B64 is not valid base64"
        ) from exc
    if not raw or len(raw) > MAX_PRIVATE_TRAINING_KEYS_BYTES:
        raise ConfigurationError("Private training-key payload has an invalid size")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(
            "Private training-key payload is not valid JSON"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {"version", "course", "platform"}:
        raise ConfigurationError("Private training-key payload has an invalid shape")
    if payload["version"] != 1:
        raise ConfigurationError("Private training-key payload version is unsupported")

    course_rows = payload["course"]
    platform_rows = payload["platform"]
    if not isinstance(course_rows, list) or len(course_rows) != 24:
        raise ConfigurationError("Private course-key payload must contain 24 rows")
    if not isinstance(platform_rows, list) or len(platform_rows) != 18:
        raise ConfigurationError("Private platform-key payload must contain 18 rows")

    course_values: list[str] = []
    course_codes: set[str] = set()
    for row in course_rows:
        if not isinstance(row, dict) or set(row) != {
            "question_code", "correct_answers", "critical_answers", "rubric"
        }:
            raise ConfigurationError("Private course-key row has an invalid shape")
        code = row["question_code"]
        rubric = row["rubric"]
        if (
            not isinstance(code, str)
            or not any(code.startswith(prefix) for prefix in COURSE_KEY_PREFIXES)
            or not PRIVATE_KEY_ID.fullmatch(code)
            or code in course_codes
            or not isinstance(rubric, str)
            or not 20 <= len(rubric.strip()) <= 1200
            or any(ord(character) < 32 and character not in "\n\t" for character in rubric)
        ):
            raise ConfigurationError("Private course-key row is invalid")
        correct = _private_key_list(
            row["correct_answers"],
            label="Private course correct_answers",
            minimum=1,
            maximum=5,
        )
        critical = _private_key_list(
            row["critical_answers"],
            label="Private course critical_answers",
            minimum=0,
            maximum=5,
        )
        if set(correct).intersection(critical):
            raise ConfigurationError("Private course key sets overlap")
        course_codes.add(code)
        course_values.append(
            "(" + ", ".join((
                _sql_literal(code),
                _private_jsonb_literal(correct),
                _private_jsonb_literal(critical),
                _sql_literal(rubric.strip()),
                "now()",
            )) + ")"
        )

    platform_values: list[str] = []
    platform_keys: set[tuple[str, str]] = set()
    for row in platform_rows:
        if not isinstance(row, dict) or set(row) != {
            "assessment_version", "platform_code", "step_code",
            "allowed_options", "correct_option", "critical_options",
        }:
            raise ConfigurationError("Private platform-key row has an invalid shape")
        assessment_version = row["assessment_version"]
        platform_code = row["platform_code"]
        step_code = row["step_code"]
        correct_option = row["correct_option"]
        key = (platform_code, step_code)
        if (
            assessment_version != 1
            or platform_code not in {"instagram", "youtube", "vk"}
            or step_code not in PLATFORM_KEY_STEPS
            or key in platform_keys
            or not isinstance(correct_option, str)
            or not PRIVATE_KEY_ID.fullmatch(correct_option)
        ):
            raise ConfigurationError("Private platform-key row is invalid")
        allowed = _private_key_list(
            row["allowed_options"],
            label="Private platform allowed_options",
            minimum=3,
            maximum=4,
        )
        critical = _private_key_list(
            row["critical_options"],
            label="Private platform critical_options",
            minimum=0,
            maximum=3,
        )
        if correct_option not in allowed or not set(critical).issubset(allowed):
            raise ConfigurationError("Private platform options are inconsistent")
        if correct_option in critical:
            raise ConfigurationError("Private platform key sets overlap")
        platform_keys.add(key)
        platform_values.append(
            "(" + ", ".join((
                "1",
                _sql_literal(platform_code),
                _sql_literal(step_code),
                _private_jsonb_literal(allowed),
                _sql_literal(correct_option),
                _private_jsonb_literal(critical),
                "now()",
            )) + ")"
        )

    expected_platform_keys = {
        (platform, step)
        for platform in ("instagram", "youtube", "vk")
        for step in PLATFORM_KEY_STEPS
    }
    if platform_keys != expected_platform_keys:
        raise ConfigurationError("Private platform-key coverage is incomplete")

    return "\n".join((
        "insert into content_factory_private.training_answer_keys (\n"
        "  question_code, correct_answers, critical_answers, rubric, updated_at\n"
        ") values\n  " + ",\n  ".join(course_values) + "\n"
        "on conflict (question_code) do update set\n"
        "  correct_answers = excluded.correct_answers,\n"
        "  critical_answers = excluded.critical_answers,\n"
        "  rubric = excluded.rubric,\n"
        "  updated_at = now();",
        "insert into content_factory_private.training_platform_answer_keys (\n"
        "  assessment_version, platform_code, step_code, allowed_options,\n"
        "  correct_option, critical_options, updated_at\n"
        ") values\n  " + ",\n  ".join(platform_values) + "\n"
        "on conflict (assessment_version, platform_code, step_code) do update set\n"
        "  allowed_options = excluded.allowed_options,\n"
        "  correct_option = excluded.correct_option,\n"
        "  critical_options = excluded.critical_options,\n"
        "  updated_at = now();",
        PRIVATE_TRAINING_CONTRACT_SQL,
    ))


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
    # Fail closed even when a marker appears inside a literal. Private grading
    # data has no reason to contain SQL comments, and checking the original
    # statement prevents a literal masker from hiding comment-based structure.
    contains_comment = "--" in insert.raw or "/*" in insert.raw
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
        private_training_encoded = os.environ.get(
            "SUPABASE_TRAINING_KEYS_B64", ""
        )
        client = ManagementApiClient(
            project_ref=project_ref,
            access_token=access_token,
        )
        migrations = load_migrations(args.migrations_dir)
        private_exam_sql_body = "\n".join((
            decode_private_exam_sql(private_exam_encoded),
            decode_private_training_keys(private_training_encoded),
        ))
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
    print("Private grading data was provisioned without logging its contents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
