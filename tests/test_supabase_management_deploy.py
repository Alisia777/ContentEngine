from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import re
from urllib import error

import pytest

import scripts.deploy_supabase_management_api as deployment_runner
from scripts.deploy_supabase_management_api import (
    DEFAULT_CHECKSUM_COMPATIBILITY_PATH,
    ConfigurationError,
    DeploymentError,
    EXPECTED_PROJECT_REF,
    ManagementApiClient,
    MigrationChecksumCompatibility,
    _validate_history_prefix,
    decode_private_exam_sql,
    decode_private_training_keys,
    deploy,
    load_checksum_compatibility,
    load_migrations,
    main,
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


EXPECTED_CHECKSUM_COMPATIBILITY = frozenset({
    (
        "202608170004",
        "9823275126659b5946abd3ee133f4384318c72f5834e37503cd2c7843e78ef42",
        "98fdaf8f8aa32c5b14460e83562167822a65e4be4adf2d60376d1d007802f242",
    ),
    (
        "202608170005",
        "55d14d923fcdbfdbbcf3dfd98ef21ce127194e4cd6e17ad3c2d81ec5795e0733",
        "00e718642fb03e0f7b36d7292cc024c33f93e9bbfa348e911c9d614adcab65d6",
    ),
    (
        "202608170006",
        "c6500af339ae7974210a762afce7715e80ef38b11a3754c0fab64b15cb01c618",
        "4bdca1aba76d773804b7948370d9e9447da60ba7d1be47f4aa9c1ffe195e1fa4",
    ),
    (
        "202608180001",
        "f01a1d71a73613c6909012639a6b3b3c71a031e50890078efa00e36b8157b64d",
        "45d6c0aa1ac37d95c336a56a033a0826b8d2571fb5775271b994a6808720f824",
    ),
    (
        "202608180002",
        "f7d25096e1064ad9be7f85118f296db188990edbaa0010c81614d5561f33abb9",
        "f9e134bd76c343a8ec1fc7c98ce7c2d4869dcf6f69fdd735f819b269dc49499f",
    ),
    (
        "202608180003",
        "cdb01b4e5f4be43ad08825c560dcaa1d61789534544b11d8d0075dcba831f792",
        "781fc88b2e73c16a09ef64dfafb0318ffc3c2bc9101d570a5dd8ab2a9b6ac928",
    ),
    (
        "202608180004",
        "8e3531bbb08e38bbc823eb3fe80d0b1e366bcdef1ea28560bd89587f55f21c11",
        "2c9473a90b3bd5d0e6869bad1c48c2e6749c4241d9103159b05b898516799853",
    ),
    (
        "202608180005",
        "4be94c2acbdcc2e39d328513c247d2e8ce5cff65eb08ee3f9320474e0441cdb4",
        "e85fbb6eb9dba2b5463b4fe125875483018a860057cc80777cdf833160bdae01",
    ),
    (
        "202608180006",
        "b7f1ff59f4b0aefb51ceb617f2da626e32965e437931ef7786f45d9827134d41",
        "f5c651239c9221fefc08f7ec13376fd7e94f91685870b2b6b7731fd1db84f603",
    ),
    (
        "202608180007",
        "ea33dd9b31e093bd6b44acb157f1d185ce8c3e128eaa665ddcb5fbc286ba8ca1",
        "d1339f78fdaa7fc3e1f98f43041d9476b5cb9b42fe5eb8e9cf7bbda2ee029cdd",
    ),
    (
        "202608180008",
        "d5eea2829f9b1e7838153e002cdbc835a2c6d564c3cd8625bbf1d425213cb539",
        "a03b01ddf5e1c6580c72139a6b6cb6a44e8c61f0b00266962227b911dc637d4e",
    ),
    (
        "202608190001",
        "1d81ea0573763eaa92ba49f2d883020f52dea76a56e025218b3c0287b84ac7aa",
        "e7881c6b0dc5136bf3684015d2b785e27086cb9a5bf7ed246d942f776c9fd389",
    ),
})


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
        self.history_initialized = history is not None
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
        if "select to_regclass(" in sql:
            return FakeResponse([{
                "history_table": (
                    "contentengine_deploy.schema_migrations"
                    if self.history_initialized
                    else None
                ),
            }])
        if "create schema if not exists contentengine_deploy" in sql:
            self.history_initialized = True
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


def test_repository_migrations_match_the_production_transaction_contract() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    migrations = load_migrations(repository_root / "supabase" / "migrations")

    assert migrations


def test_checked_in_checksum_compatibility_is_the_exact_recovered_set() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    migrations = load_migrations(repository_root / "supabase" / "migrations")
    local_by_version = {migration.version: migration for migration in migrations}

    compatibility = load_checksum_compatibility(
        DEFAULT_CHECKSUM_COMPATIBILITY_PATH
    )

    assert frozenset(
        (
            item.version,
            item.deployed_sha256,
            item.repository_sha256,
        )
        for item in compatibility
    ) == EXPECTED_CHECKSUM_COMPATIBILITY
    assert all(
        local_by_version[item.version].sha256 == item.repository_sha256
        for item in compatibility
    )
    simulated_history = {
        migration.version: migration.sha256 for migration in migrations
    }
    simulated_history.update({
        item.version: item.deployed_sha256 for item in compatibility
    })
    _validate_history_prefix(
        migrations,
        simulated_history,
        compatibility,
    )


def test_exact_checksum_compatibility_tuple_is_accepted_without_rewrite(
    tmp_path: Path,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    migration = migrations[0]
    deployed_sha256 = "0" * 64
    compatibility = frozenset({MigrationChecksumCompatibility(
        version=migration.version,
        deployed_sha256=deployed_sha256,
        repository_sha256=migration.sha256,
    )})
    fake_http = FakeManagementApi({migration.version: deployed_sha256})

    applied = deploy(
        client=_client(fake_http),
        migrations=migrations[:1],
        private_exam_sql_body=None,
        checksum_compatibility=compatibility,
    )

    assert applied == []
    assert fake_http.history == {migration.version: deployed_sha256}
    assert len(fake_http.requests) == 2  # probe and immutable history read only


def test_checksum_compatibility_never_changes_fresh_database_receipts(
    tmp_path: Path,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    migration = migrations[0]
    compatibility = frozenset({MigrationChecksumCompatibility(
        version=migration.version,
        deployed_sha256="0" * 64,
        repository_sha256=migration.sha256,
    )})
    fake_http = FakeManagementApi()

    applied = deploy(
        client=_client(fake_http),
        migrations=migrations,
        private_exam_sql_body=None,
        checksum_compatibility=compatibility,
    )

    assert applied == [migration.version for migration in migrations]
    assert fake_http.history == {
        item.version: item.sha256 for item in migrations
    }


def test_checksum_compatibility_rejects_unknown_deployed_hash(
    tmp_path: Path,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    migration = migrations[0]
    compatibility = frozenset({MigrationChecksumCompatibility(
        version=migration.version,
        deployed_sha256="0" * 64,
        repository_sha256=migration.sha256,
    )})

    with pytest.raises(DeploymentError, match="Immutable checksum mismatch"):
        _validate_history_prefix(
            migrations,
            {migration.version: "1" * 64},
            compatibility,
        )


def test_checksum_compatibility_rejects_unknown_repository_hash(
    tmp_path: Path,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    migration = migrations[0]
    compatibility = frozenset({MigrationChecksumCompatibility(
        version=migration.version,
        deployed_sha256="0" * 64,
        repository_sha256="1" * 64,
    )})

    with pytest.raises(DeploymentError, match="does not match this checkout"):
        _validate_history_prefix(
            migrations,
            {migration.version: "0" * 64},
            compatibility,
        )


def test_checksum_compatibility_rejects_unknown_version(tmp_path: Path) -> None:
    migrations = _fixture_migrations(tmp_path)
    migration = migrations[0]
    compatibility = frozenset({MigrationChecksumCompatibility(
        version="202607139999",
        deployed_sha256="0" * 64,
        repository_sha256=migration.sha256,
    )})

    with pytest.raises(DeploymentError, match="does not match this checkout"):
        _validate_history_prefix(
            migrations,
            {migration.version: "0" * 64},
            compatibility,
        )


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


def test_read_only_management_query_retries_bounded_transient_544() -> None:
    calls = 0
    delays: list[float] = []

    def flaky_http(api_request, *, timeout: int):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise error.HTTPError(
                api_request.full_url,
                544,
                "gateway timeout",
                {},
                BytesIO(b"private database error"),
            )
        return FakeResponse([{"ready": True}])

    client = ManagementApiClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="test-access-token",
        opener=flaky_http,
        sleeper=delays.append,
    )

    assert client.execute("select 1", read_only=True) == [{"ready": True}]
    assert calls == 3
    assert delays == [2.0, 5.0]


def test_ambiguous_management_write_is_never_retried_automatically() -> None:
    calls = 0
    delays: list[float] = []

    def failing_http(api_request, *, timeout: int):
        nonlocal calls
        calls += 1
        raise error.HTTPError(
            api_request.full_url,
            544,
            "gateway timeout",
            {},
            BytesIO(b"private database error"),
        )

    client = ManagementApiClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="test-access-token",
        opener=failing_http,
        sleeper=delays.append,
    )

    with pytest.raises(DeploymentError, match=r"HTTP 544"):
        client.execute("insert into private_table values (1)")
    assert calls == 1
    assert delays == []


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


def test_skip_private_grading_makes_no_private_management_api_write(
    tmp_path: Path,
) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi(
        {migration.version: migration.sha256 for migration in migrations}
    )

    applied = deploy(
        client=_client(fake_http),
        migrations=migrations,
        private_exam_sql_body=None,
    )

    assert applied == []
    assert len(fake_http.requests) == 2  # history probe and immutable read
    assert all(
        "pg_advisory_xact_lock" not in item["query"]
        for item in fake_http.requests
    )


def test_cli_skip_private_grading_ignores_private_secrets_and_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    migrations = _fixture_migrations(tmp_path)
    captured: dict[str, object] = {}
    fake_client = object()

    def fake_client_factory(**kwargs):
        captured["client_configuration"] = kwargs
        return fake_client

    def fake_deploy(**kwargs):
        captured["deploy"] = kwargs
        return [migrations[-1].version]

    monkeypatch.setenv("SUPABASE_PROJECT_REF", EXPECTED_PROJECT_REF)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "test-access-token")
    # Malformed values prove the opt-in path does not read or decode them.
    monkeypatch.setenv("SUPABASE_EXAM_KEYS_B64", "not-valid-base64")
    monkeypatch.setenv("SUPABASE_TRAINING_KEYS_B64", "not-valid-json")
    monkeypatch.setattr(deployment_runner, "ManagementApiClient", fake_client_factory)
    monkeypatch.setattr(deployment_runner, "deploy", fake_deploy)

    result = main([
        "--migrations-dir",
        str(tmp_path),
        "--skip-private-grading",
    ])

    assert result == 0
    assert captured["deploy"] == {
        "client": fake_client,
        "migrations": migrations,
        "private_exam_sql_body": None,
        "checksum_compatibility": load_checksum_compatibility(),
    }
    output = capsys.readouterr()
    assert output.err == ""
    assert "Applied 1 immutable Supabase migration(s)." in output.out
    assert "Private grading data provisioning was explicitly skipped." in output.out


def test_cli_default_remains_fail_closed_without_private_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fixture_migrations(tmp_path)
    fake_client = object()
    deploy_called = False

    def fake_deploy(**_kwargs):
        nonlocal deploy_called
        deploy_called = True
        return []

    monkeypatch.setenv("SUPABASE_PROJECT_REF", EXPECTED_PROJECT_REF)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "test-access-token")
    monkeypatch.delenv("SUPABASE_EXAM_KEYS_B64", raising=False)
    monkeypatch.delenv("SUPABASE_TRAINING_KEYS_B64", raising=False)
    monkeypatch.setattr(
        deployment_runner,
        "ManagementApiClient",
        lambda **_kwargs: fake_client,
    )
    monkeypatch.setattr(deployment_runner, "deploy", fake_deploy)

    result = main(["--migrations-dir", str(tmp_path)])

    assert result == 1
    assert deploy_called is False
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == (
        "Supabase deployment stopped: SUPABASE_EXAM_KEYS_B64 is required\n"
    )


def test_existing_history_skips_repeated_production_ddl(tmp_path: Path) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi(
        {migration.version: migration.sha256 for migration in migrations}
    )

    deploy(
        client=_client(fake_http),
        migrations=migrations,
        private_exam_sql_body="select 1;",
    )

    assert any("select to_regclass(" in item["query"] for item in fake_http.requests)
    assert not any(
        "create schema if not exists contentengine_deploy" in item["query"]
        for item in fake_http.requests
    )


def test_immutable_checksum_mismatch_stops_before_any_write(tmp_path: Path) -> None:
    migrations = _fixture_migrations(tmp_path)
    fake_http = FakeManagementApi({migrations[0].version: "0" * 64})

    with pytest.raises(DeploymentError, match="Immutable checksum mismatch"):
        deploy(
            client=_client(fake_http),
            migrations=migrations,
            private_exam_sql_body="select 1;",
        )

    assert len(fake_http.requests) == 2  # history probe and immutable read
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

    assert fake_http.history == {
        migrations[0].version: migrations[0].sha256,
    }
    failed_query = fake_http.requests[-1]["query"].casefold()
    assert failed_query.startswith("begin;")
    assert "insert into contentengine_deploy.schema_migrations" in failed_query
    migration_body = failed_query.split("$contentengine_deployment_guard$;", 1)[1]
    assert migrations[0].version not in migration_body
    assert migrations[1].version in migration_body
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


def test_each_migration_and_its_history_receipt_share_one_transaction(
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
    assert len(migration_queries) == len(migrations)
    for migration, query in zip(migrations, migration_queries, strict=True):
        assert query.startswith("begin;")
        assert query.count(
            "insert into contentengine_deploy.schema_migrations"
        ) == 1
        assert migration.version in query
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


def test_private_training_json_accepts_wrapped_standard_base64() -> None:
    encoded = _encode_private_training(_private_training_payload())
    wrapped = "\n".join(
        encoded[index : index + 76]
        for index in range(0, len(encoded), 76)
    )

    validated = decode_private_training_keys(wrapped)

    assert validated.count("insert into content_factory_private.") == 2
    assert "private_training_key_contract_failed" in validated


def test_private_training_json_accepts_direct_secret_scoped_json() -> None:
    encoded = json.dumps(_private_training_payload(), ensure_ascii=False)

    validated = decode_private_training_keys(encoded)

    assert validated.count("insert into content_factory_private.") == 2
    assert "private_training_key_contract_failed" in validated


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
