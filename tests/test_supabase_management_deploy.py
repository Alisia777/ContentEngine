from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import re
from urllib import error

import pytest

from scripts.deploy_supabase_management_api import (
    ConfigurationError,
    DeploymentError,
    EXPECTED_PROJECT_REF,
    ManagementApiClient,
    decode_private_exam_sql,
    decode_private_training_keys,
    deploy,
    load_migrations,
)


def _private_training_payload() -> dict:
    course = []
    for module in (
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    ):
        for index in range(6):
            course.append({
                "question_code": f"course_check_{module}_case_{index}",
                "correct_answers": [f"safe_{index}"],
                "critical_answers": [f"risk_{index}"],
                "rubric": "Проверяется рабочий риск, доказательство и безопасный следующий шаг.",
            })
    platform = []
    for platform_code in ("instagram", "youtube", "vk"):
        for step_code in (
            "account", "warmup", "publication", "review", "link", "result"
        ):
            platform.append({
                "assessment_version": 1,
                "platform_code": platform_code,
                "step_code": step_code,
                "allowed_options": ["safe", "hold", "risk"],
                "correct_option": "safe",
                "critical_options": ["risk"],
            })
    return {"version": 1, "course": course, "platform": platform}


def _encode_private_training(payload: dict) -> str:
    return base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")


PRIVATE_EXAM_SQL = """begin;
insert into content_factory_private.training_answer_keys (
  question_code, correct_answers, rubric
) values ('test_only', '[]'::jsonb, 'catalog_contract')
on conflict (question_code) do update set
  correct_answers = excluded.correct_answers,
  rubric = excluded.rubric;
do $catalog_contract$
begin
  perform 1;
end;
$catalog_contract$;
commit;
"""


def _catalog_case_select_sql(*, case_count: int = 12) -> str:
    cases = "\n".join(
        "when 'test_%02d' then jsonb_build_array(q.options -> %d)"
        % (index, index % 4)
        for index in range(case_count)
    )
    return f"""begin;
insert into content_factory_private.training_answer_keys (
  question_code, correct_answers, rubric
)
select
  q.code,
  case q.code
    {cases}
    else '[]'::jsonb
  end,
  'catalog_contract'
from content_factory.training_questions q
where q.module_code = 'operator_final_exam'
on conflict (question_code) do update set
  correct_answers = excluded.correct_answers,
  rubric = excluded.rubric,
  updated_at = now();
do $catalog_contract$
begin
  perform 1;
end;
$catalog_contract$;
commit;
"""


class FakeResponse:
    def __init__(self, payload=(), *, status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1) -> bytes:
        return self._body


class FakeManagementApi:
    def __init__(self, history: dict[str, str] | None = None) -> None:
        self.history = dict(history or {})
        self.requests: list[dict] = []
        self.fail_version: str | None = None
        self.fail_private = False

    def __call__(self, api_request, *, timeout: int):
        assert timeout == 60
        payload = json.loads(api_request.data.decode("utf-8"))
        self.requests.append(
            {
                "url": api_request.full_url,
                "authorization": api_request.headers["Authorization"],
                **payload,
            }
        )
        sql = payload["query"]
        if "select version, sha256" in sql:
            return FakeResponse(
                [
                    {"version": version, "sha256": checksum}
                    for version, checksum in sorted(self.history.items())
                ]
            )
        migration_inserts = list(re.finditer(
            r"insert into contentengine_deploy[.]schema_migrations"
            r"\s*[(]version, sha256[)]\s*values\s*"
            r"[(]'([0-9]+)', '([0-9a-f]{64})'[)]",
            sql,
            flags=re.IGNORECASE,
        ))
        planned_history = [match.groups() for match in migration_inserts]
        for version, _checksum in planned_history:
            if version == self.fail_version:
                raise error.HTTPError(
                    api_request.full_url,
                    500,
                    "database query failed",
                    {},
                    BytesIO(sql.encode("utf-8")),
                )
        if "test_only" in sql and self.fail_private:
            raise error.HTTPError(
                api_request.full_url,
                400,
                "private query failed",
                {},
                BytesIO(sql.encode("utf-8")),
            )
        # This update represents the entire outer transaction succeeding.
        for version, checksum in planned_history:
            self.history[version] = checksum
        return FakeResponse([])


def _write_migration(directory: Path, version: str, statement: str) -> None:
    (directory / f"{version}_test.sql").write_text(
        f"begin;\n{statement}\ncommit;\n",
        encoding="utf-8",
    )


def _fixture_migrations(tmp_path: Path):
    _write_migration(tmp_path, "202607130001", "select 1;")
    _write_migration(tmp_path, "202607130002", "select 2;")
    return load_migrations(tmp_path)


def _client(fake_http: FakeManagementApi) -> ManagementApiClient:
    return ManagementApiClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="test-access-token",
        opener=fake_http,
    )


def test_client_refuses_any_project_except_reviewed_production() -> None:
    fake_http = FakeManagementApi()
    with pytest.raises(ConfigurationError, match="reviewed production project"):
        ManagementApiClient(
            project_ref="aaaaaaaaaaaaaaaaaaaa",
            access_token="test-access-token",
            opener=fake_http,
        )
    assert fake_http.requests == []


def test_management_api_uses_exact_project_url_and_bearer_token() -> None:
    fake_http = FakeManagementApi()
    client = _client(fake_http)

    client.execute("select 1", read_only=True)

    sent = fake_http.requests[0]
    assert sent["url"] == (
        "https://api.supabase.com/v1/projects/"
        f"{EXPECTED_PROJECT_REF}/database/query"
    )
    assert sent["authorization"] == "Bearer test-access-token"
    assert sent["read_only"] is True


def test_applied_migrations_are_idempotently_skipped(tmp_path: Path) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi(
        {migration.version: migration.sha256 for migration in migrations}
    )

    applied = deploy(
        client=_client(fake_http),
        migrations=migrations,
        private_exam_sql_body=decode_private_exam_sql(
            base64.b64encode(PRIVATE_EXAM_SQL.encode()).decode()
        ),
    )

    assert applied == []
    assert not any(
        "insert into contentengine_deploy.schema_migrations" in item["query"]
        for item in fake_http.requests
    )
    assert sum("test_only" in item["query"] for item in fake_http.requests) == 1


def test_immutable_checksum_mismatch_stops_before_any_write(tmp_path: Path) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi({migrations[0].version: "0" * 64})

    with pytest.raises(DeploymentError, match="Immutable checksum mismatch"):
        deploy(
            client=_client(fake_http),
            migrations=migrations,
            private_exam_sql_body="select 1;",
        )

    assert len(fake_http.requests) == 2  # history bootstrap and read only
    assert fake_http.history == {migrations[0].version: "0" * 64}


def test_partial_failure_cannot_record_failed_migration(tmp_path: Path) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi()
    fake_http.fail_version = migrations[1].version

    with pytest.raises(DeploymentError, match=r"HTTP 500"):
        deploy(
            client=_client(fake_http),
            migrations=migrations,
            private_exam_sql_body="select 1;",
        )

    assert fake_http.history == {}
    failed_query = fake_http.requests[-1]["query"].casefold()
    assert failed_query.startswith("begin;")
    assert "insert into contentengine_deploy.schema_migrations" in failed_query
    assert failed_query.endswith("commit;")


def test_private_sql_and_http_error_body_are_never_exposed(
    tmp_path: Path,
    capsys,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi(
        {migration.version: migration.sha256 for migration in migrations}
    )
    fake_http.fail_private = True
    private_body = decode_private_exam_sql(
        base64.b64encode(PRIVATE_EXAM_SQL.encode()).decode()
    )

    with pytest.raises(DeploymentError) as captured:
        deploy(
            client=_client(fake_http),
            migrations=migrations,
            private_exam_sql_body=private_body,
        )

    assert "test_only" not in str(captured.value)
    assert "correct_answers" not in str(captured.value)
    assert "test-access-token" not in str(captured.value)
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_each_migration_is_wrapped_with_history_in_one_transaction(
    tmp_path: Path,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi()

    applied = deploy(
        client=_client(fake_http),
        migrations=migrations,
        private_exam_sql_body="select 1;",
    )

    assert applied == [migration.version for migration in migrations]
    migration_queries = [
        item["query"].casefold()
        for item in fake_http.requests
        if "insert into contentengine_deploy.schema_migrations" in item["query"]
    ]
    assert len(migration_queries) == 1
    query = migration_queries[0]
    assert query.startswith("begin;")
    assert query.count("insert into contentengine_deploy.schema_migrations") == 2
    assert "pg_advisory_xact_lock" in query
    assert "deployment_history_changed_retry" in query
    assert query.endswith("commit;")


@pytest.mark.parametrize(
    "nested_control",
    [
        "select 1; commit; select 2;",
        "select 1; END; select 2;",
        "select 1; COMMIT AND CHAIN; select 2;",
        "select 1; ROLLBACK TO SAVEPOINT risky; select 2;",
    ],
)
def test_migration_transaction_escape_is_rejected(
    tmp_path: Path,
    nested_control: str,
) -> None:
    _write_migration(tmp_path, "202607130001", nested_control)

    with pytest.raises(ConfigurationError, match="transaction control"):
        load_migrations(tmp_path)


def test_private_payload_executes_only_validated_upsert_not_supplied_do_block() -> None:
    encoded = base64.b64encode(PRIVATE_EXAM_SQL.encode()).decode()

    validated = decode_private_exam_sql(encoded)

    assert "insert into content_factory_private.training_answer_keys" in validated
    assert "test_only" in validated
    assert "perform 1" not in validated
    assert "private_exam_key_contract_failed" in validated
    assert "exam_answer_total <> 12" in validated
    assert "select count(*) into answer_total" not in validated
    assert "where question.module_code = 'operator_final_exam'" in validated


def test_private_training_json_renders_only_two_scoped_upserts_and_contract() -> None:
    validated = decode_private_training_keys(
        _encode_private_training(_private_training_payload())
    )

    assert validated.count("insert into content_factory_private.") == 2
    assert "training_answer_keys" in validated
    assert "training_platform_answer_keys" in validated
    assert validated.count("course_check_") == 24
    assert "private_training_key_contract_failed" in validated
    assert "auth.users" not in validated
    assert "delete " not in validated.casefold()
    assert "drop " not in validated.casefold()


def test_private_training_json_rejects_missing_rows_and_unknown_fields() -> None:
    missing = _private_training_payload()
    missing["course"] = missing["course"][:-1]
    with pytest.raises(ConfigurationError, match="24 rows"):
        decode_private_training_keys(_encode_private_training(missing))

    unknown = _private_training_payload()
    unknown["platform"][0]["sql"] = "delete from auth.users"
    with pytest.raises(ConfigurationError, match="invalid shape"):
        decode_private_training_keys(_encode_private_training(unknown))


def test_private_training_json_rejects_incomplete_platform_coverage() -> None:
    duplicate = _private_training_payload()
    duplicate["platform"][-1] = dict(duplicate["platform"][0])
    with pytest.raises(ConfigurationError, match="invalid"):
        decode_private_training_keys(_encode_private_training(duplicate))


def test_private_payload_safely_normalizes_existing_double_commit_envelope() -> None:
    payload = PRIVATE_EXAM_SQL.removesuffix("commit;\n") + "commit;\ncommit;\n"
    encoded = base64.b64encode(payload.encode()).decode()

    validated = decode_private_exam_sql(encoded)

    assert "test_only" in validated
    assert "commit" not in tuple(
        token.casefold() for token in re.findall(r"[A-Za-z_]+", validated)
    )


def test_private_payload_accepts_exact_catalog_case_projection() -> None:
    encoded = base64.b64encode(_catalog_case_select_sql().encode()).decode()

    validated = decode_private_exam_sql(encoded)

    assert "from content_factory.training_questions q" in validated
    assert validated.count("jsonb_build_array") == 12
    assert "perform 1" not in validated
    assert "private_exam_key_contract_failed" in validated
    assert "exam_answer_total <> 12" in validated
    assert "select count(*) into answer_total" not in validated


def test_private_payload_rejects_case_projection_from_another_table() -> None:
    payload = _catalog_case_select_sql().replace(
        "from content_factory.training_questions q",
        "from auth.users q",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_incomplete_catalog_case_projection() -> None:
    encoded = base64.b64encode(
        _catalog_case_select_sql(case_count=11).encode()
    ).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_broadened_catalog_scope() -> None:
    payload = _catalog_case_select_sql().replace(
        "q.module_code = 'operator_final_exam'",
        "q.module_code ~ '.*'",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_select_inside_upsert_assignment() -> None:
    payload = _catalog_case_select_sql().replace(
        "correct_answers = excluded.correct_answers,",
        "correct_answers = (select q.correct_answers "
        "from content_factory_private.training_answer_keys q "
        "where q.question_code = 'test_00'),",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_operator_inside_upsert_assignment() -> None:
    payload = _catalog_case_select_sql().replace(
        "correct_answers = excluded.correct_answers,",
        "correct_answers = excluded.correct_answers - 'guessed_answer',",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_scope_spoofed_by_line_comment() -> None:
    payload = _catalog_case_select_sql().replace(
        "where q.module_code = 'operator_final_exam'",
        "where q.module_code ~ '.*'\n"
        "-- from content_factory.training_questions q "
        "where q.module_code = 'operator_final_exam' "
        "on conflict (question_code)",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_upsert_spoofed_by_line_comment() -> None:
    payload = _catalog_case_select_sql().replace(
        "correct_answers = excluded.correct_answers,",
        "correct_answers = excluded.correct_answers - 'guessed_answer',",
    ).replace(
        "updated_at = now();",
        "updated_at = now()\n"
        "-- on conflict (question_code) do update set "
        "correct_answers = excluded.correct_answers, "
        "rubric = excluded.rubric, updated_at = now()\n"
        ";",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="approved answer table"):
        decode_private_exam_sql(encoded)


def test_private_payload_rejects_escape_string_literals() -> None:
    payload = PRIVATE_EXAM_SQL.replace(
        "'catalog_contract')",
        "E'catalog\\'contract')",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="unapproved expression"):
        decode_private_exam_sql(encoded)


def test_private_payload_cannot_smuggle_privileged_statement_in_one_line() -> None:
    payload = PRIVATE_EXAM_SQL.replace(
        "do $catalog_contract$",
        "delete from auth.users; do $catalog_contract$",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="unexpected shape"):
        decode_private_exam_sql(encoded)


def test_private_payload_cannot_call_side_effect_function() -> None:
    payload = PRIVATE_EXAM_SQL.replace(
        "'test_only'",
        "setval('content_factory.some_sequence', 1)::text",
    )
    encoded = base64.b64encode(payload.encode()).decode()

    with pytest.raises(ConfigurationError, match="unapproved expression"):
        decode_private_exam_sql(encoded)


def test_escape_string_cannot_hide_real_transaction_control(tmp_path: Path) -> None:
    (tmp_path / "202607130001_test.sql").write_text(
        "begin;\n"
        "select E'a\\''; COMMIT; SELECT 'b'; --';\n"
        "commit;\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="transaction control"):
        load_migrations(tmp_path)
