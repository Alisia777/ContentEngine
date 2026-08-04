from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
from uuid import UUID

import pytest

from scripts.import_ai_historical_cases import (
    EDGE_FUNCTION_NAME,
    HistoricalCaseImportError,
    MAX_RESPONSE_BYTES,
    PUBLIC_APP_ORIGIN,
    build_batches,
    canonical_sha256,
    run,
    validate_manifest,
)


SOURCE_ID = "10000000-0000-4000-8000-000000000001"
ORGANIZATION_ID = "20000000-0000-4000-8000-000000000002"
PUBLISHABLE_KEY = "sb_publishable_fixture_browser_key_123456"
USER_ACCESS_TOKEN = "authenticated_user_jwt_fixture_must_never_be_logged"


def test_cli_accepts_the_bounded_full_control_room_receipt() -> None:
    assert MAX_RESPONSE_BYTES >= 8 * 1024 * 1024


def case(number: int = 1) -> dict[str, object]:
    return {
        "external_case_id": f"fixture:wb:sku-{number}",
        "product_category": "baa",
        "product_sku": f"sku-{number}",
        "marketplace_sku": str(500_000_000 + number),
        "product_title": f"Fixture product {number}",
        "brand": "Fixture Brand",
        "platform": "wildberries",
        "channel": "marketplace_funnel",
        "period_start": "2026-05-01",
        "period_end": "2026-07-29",
        "outcome": "good",
        "outcome_dimension": "overall",
        "status_label": "Fixture reviewed status",
        "metrics": {"orders": 120 + number, "buyout_rate": 0.82},
        "confidence": 0.95,
        "creative_angle": "product_focus",
        "provenance": {
            "sheet": "Fixture",
            "row": number + 1,
            "row_hash": f"{number:064x}",
        },
    }


def manifest(case_count: int = 1) -> dict[str, object]:
    return {
        "schema_version": "ai_historical_cases.v1",
        "product_category": "baa",
        "original_filename": "reviewed-source.xlsx",
        "source_sha256": "a" * 64,
        "parser_version": "fixture-parser-v1",
        "cases": [case(index) for index in range(1, case_count + 1)],
    }


def write_manifest(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update({"unknown": True}), "unknown field"),
        (
            lambda value: value.update({"original_filename": "source.xlsm"}),
            "macro-enabled",
        ),
        (
            lambda value: value["cases"][0].update({"product_title": '=WEBSERVICE("https://example.test")'}),
            "raw URL",
        ),
        (
            lambda value: value["cases"][0].update({"confidence": 1.01}),
            "between 0 and 1",
        ),
        (
            lambda value: value["cases"][0].update({"outcome_dimension": "free_text_dimension"}),
            "outcome_dimension",
        ),
        (
            lambda value: value["cases"][0].update({"creative_angle": "invented_angle"}),
            "creative_angle",
        ),
        (
            lambda value: value["cases"][0]["metrics"].update({"not-finite": float("inf")}),
            "metric key",
        ),
        (
            lambda value: value["cases"][0].update({"caption": "raw source prose is forbidden"}),
            "unknown field",
        ),
        (
            lambda value: value["cases"][0]["provenance"].update({"row_hash": "not-a-hash"}),
            "SHA-256",
        ),
    ],
)
def test_manifest_rejects_invalid_or_unreviewed_values(mutate, message: str) -> None:
    value = manifest()
    mutate(value)

    with pytest.raises(HistoricalCaseImportError, match=message):
        validate_manifest(value)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value["cases"][0].update({"product_sku": "s" * 121}), "product_sku"),
        (lambda value: value["cases"][0].update({"platform": "p" * 41}), "platform"),
        (lambda value: value["cases"][0].update({"channel": "c" * 61}), "channel"),
        (
            lambda value: value["cases"][0].update({"metrics": {"m" * 41: 1}}),
            "metric key",
        ),
        (
            lambda value: value["cases"][0].update({"period_start": "2000-01-01", "period_end": "2011-01-01"}),
            "period",
        ),
    ],
)
def test_manifest_matches_database_field_bounds(mutate, message: str) -> None:
    value = manifest()
    mutate(value)

    with pytest.raises(HistoricalCaseImportError, match=message):
        validate_manifest(value)


def test_manifest_accepts_database_field_boundaries_and_dimensions() -> None:
    value = manifest()
    item = value["cases"][0]
    item["product_sku"] = "s" * 120
    item["channel"] = "c" * 60
    item["metrics"] = {"m" * 40: 1}
    item["period_start"] = "2020-01-01"
    item["period_end"] = (date(2020, 1, 1) + timedelta(days=3_660)).isoformat()
    item["outcome_dimension"] = "overall_performance"

    assert validate_manifest(value) is value

    value["product_category"] = "overall_performance"
    with pytest.raises(HistoricalCaseImportError, match="product_category"):
        validate_manifest(value)


def test_manifest_schema_publishes_database_parity_bounds() -> None:
    schema = json.loads(Path("data/ai-historical-cases/manifest-v1.schema.json").read_text(encoding="utf-8"))

    assert schema["$defs"]["sku"]["maxLength"] == 120
    assert schema["$defs"]["channel"]["maxLength"] == 60
    assert schema["$defs"]["case"]["properties"]["platform"]["maxLength"] == 40
    assert schema["$defs"]["case"]["properties"]["metrics"]["propertyNames"]["maxLength"] == 40
    assert schema["$defs"]["case"]["x-contentengine-max-period-days"] == 3_660


def test_canonical_hash_is_independent_of_json_object_key_order() -> None:
    first = manifest()
    second = json.loads(json.dumps(first, ensure_ascii=False))
    second = dict(reversed(list(second.items())))
    second["cases"][0] = dict(reversed(list(second["cases"][0].items())))

    assert canonical_sha256(first) == canonical_sha256(second)
    assert len(canonical_sha256(first)) == 64


def test_dry_run_is_default_and_never_opens_network(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, manifest())

    def forbidden_opener(*_args, **_kwargs):
        pytest.fail("dry-run must not open a network connection")

    result = run([str(path)], environ={}, opener=forbidden_opener)

    assert result["ok"] is True
    assert result["mode"] == "dry_run"
    assert result["cases"] == 1
    assert result["batches"] == 1


class FakeResponse:
    status = 200

    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self, _limit: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RecordingOpener:
    def __init__(self) -> None:
        self.requests: list[tuple[object, int]] = []

    def __call__(self, api_request, *, timeout: int):
        self.requests.append((api_request, timeout))
        body = json.loads(api_request.data.decode("utf-8"))
        return FakeResponse(
            {
                "ok": True,
                "parsed": 205,
                "imported": 200,
                "quarantined": 5,
                "matched": 200,
                "per_category": {body["product_category"]: 205},
                "source_sha256": "b" * 64,
                "manifest_sha256": "c" * 64,
                "batch": {"status": "completed", "accepted": 3},
            }
        )


def test_commit_calls_authenticated_edge_without_sending_normalized_cases(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, manifest(205))
    opener = RecordingOpener()

    result = run(
        [
            str(path),
            "--commit",
            "--organization-id",
            ORGANIZATION_ID,
            "--source-id",
            SOURCE_ID,
        ],
        environ={
            "SUPABASE_URL": "https://fixture-project.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": PUBLISHABLE_KEY,
            "CONTENTENGINE_USER_ACCESS_TOKEN": USER_ACCESS_TOKEN,
        },
        opener=opener,
    )

    assert result["mode"] == "commit"
    assert result["registered_source_reparsed"] is True
    assert result["parsed"] == 205
    assert result["imported"] == 200
    assert result["quarantined"] == 5
    assert result["local_validation"]["batches"] == 3
    assert result["source_sha256"] == "b" * 64
    assert result["manifest_sha256"] == "c" * 64
    assert len(opener.requests) == 1
    api_request, timeout = opener.requests[0]
    payload = json.loads(api_request.data.decode("utf-8"))
    assert api_request.full_url.endswith(f"/functions/v1/{EDGE_FUNCTION_NAME}")
    assert "/rest/v1/rpc/" not in api_request.full_url
    assert api_request.get_method() == "POST"
    assert api_request.get_header("Authorization") == f"Bearer {USER_ACCESS_TOKEN}"
    assert api_request.get_header("Apikey") == PUBLISHABLE_KEY
    assert api_request.get_header("Origin") == PUBLIC_APP_ORIGIN
    assert timeout == 60
    assert set(payload) == {
        "action",
        "organization_id",
        "source_id",
        "product_category",
        "adapter",
        "commit",
        "idempotency_key",
    }
    assert payload["action"] == "parse_and_import"
    assert payload["organization_id"] == ORGANIZATION_ID
    assert payload["source_id"] == SOURCE_ID
    assert payload["product_category"] == "baa"
    assert payload["adapter"] == "auto"
    assert payload["commit"] is True
    assert str(UUID(payload["idempotency_key"])) == payload["idempotency_key"]
    assert "cases" not in payload
    assert "p_payload" not in payload
    assert USER_ACCESS_TOKEN not in api_request.data.decode("utf-8")


def test_batches_and_idempotency_keys_are_stable_and_source_bound() -> None:
    value = manifest(201)

    first_hash, first = build_batches(value, source_id=SOURCE_ID)
    second_hash, second = build_batches(deepcopy(value), source_id=SOURCE_ID)

    assert first_hash == second_hash
    assert first == second
    assert [len(batch["cases"]) for batch in first] == [100, 100, 1]
    assert [batch["parsed_row_count"] for batch in first] == [100, 100, 1]
    assert all(batch["parser_quarantined_row_count"] == 0 for batch in first)
    assert [batch["batch_index"] for batch in first] == [1, 2, 3]
    assert all(batch["batch_count"] == 3 for batch in first)
    assert all(batch["source_id"] == SOURCE_ID for batch in first)
    assert len({batch["idempotency_key"] for batch in first}) == 3
    assert all(first_hash in batch["idempotency_key"] for batch in first)


def test_commit_requires_source_and_credentials_before_network(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, manifest())

    with pytest.raises(HistoricalCaseImportError, match="--source-id"):
        run([str(path), "--commit"], environ={})

    with pytest.raises(HistoricalCaseImportError, match="--organization-id"):
        run([str(path), "--commit", "--source-id", SOURCE_ID], environ={})

    with pytest.raises(HistoricalCaseImportError, match="SUPABASE_URL"):
        run(
            [
                str(path),
                "--commit",
                "--organization-id",
                ORGANIZATION_ID,
                "--source-id",
                SOURCE_ID,
            ],
            environ={
                "SUPABASE_PUBLISHABLE_KEY": PUBLISHABLE_KEY,
                "CONTENTENGINE_USER_ACCESS_TOKEN": USER_ACCESS_TOKEN,
            },
        )

    with pytest.raises(HistoricalCaseImportError, match="service role"):
        run(
            [
                str(path),
                "--commit",
                "--organization-id",
                ORGANIZATION_ID,
                "--source-id",
                SOURCE_ID,
            ],
            environ={
                "SUPABASE_URL": "https://fixture-project.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "sb_secret_not_accepted_by_cli_1234567890",
            },
        )
