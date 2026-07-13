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
    deploy,
    load_migrations,
)


PRIVATE_EXAM_SQL = """begin;
insert into content_factory_private.training_answer_keys (
  question_code, correct_answers, rubric
) values ('test_only', '[]'::jsonb, 'catalog_contract');
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
        migration_insert = re.search(
            r"insert into contentengine_deploy[.]schema_migrations"
            r"\s*[(]version, sha256[)]\s*values\s*"
            r"[(]'([0-9]+)', '([0-9a-f]{64})'[)]",
            sql,
            flags=re.IGNORECASE,
        )
        if migration_insert:
            version, checksum = migration_insert.groups()
            if version == self.fail_version:
                raise error.HTTPError(
                    api_request.full_url,
                    500,
                    "database query failed",
                    {},
                    BytesIO(sql.encode("utf-8")),
                )
            # This update represents the atomic transaction succeeding.
            self.history[version] = checksum
        if "test_only" in sql and self.fail_private:
            raise error.HTTPError(
                api_request.full_url,
                400,
                "private query failed",
                {},
                BytesIO(sql.encode("utf-8")),
            )
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

    assert fake_http.history == {migrations[0].version: migrations[0].sha256}
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
    assert len(migration_queries) == 2
    for query in migration_queries:
        assert query.startswith("begin;")
        assert "pg_advisory_xact_lock" in query
        assert query.endswith("commit;")
