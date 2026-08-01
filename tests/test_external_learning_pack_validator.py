from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_external_learning_pack import PackValidationError, validate


def write_pack(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def valid_record() -> dict:
    return {
        "schema_version": "external_creative_observation.v1",
        "organization_id": "altea-content-factory",
        "category_scope": "pet_care",
        "source": {
            "source_file_sha256": "a" * 64,
            "source_row_sha256": "b" * 64,
            "manifest_sha256": "c" * 64,
            "source_url_sha256": "d" * 64,
            "rights_status": "unknown_requires_human_confirmation",
        },
        "machine_profile": {
            "hook_type": "problem_first",
            "content_format": "ugc_review",
        },
        "qa_status": "candidate",
        "eligible_for_direct_prompt": False,
    }


def test_validator_accepts_bounded_machine_profile(tmp_path: Path) -> None:
    path = tmp_path / "pack.jsonl"
    write_pack(path, [valid_record()])

    result = validate(path)

    assert result == {
        "ok": True,
        "records": 1,
        "schemas": {"external_creative_observation.v1": 1},
    }


def test_validator_rejects_raw_url_and_prompt_fields(tmp_path: Path) -> None:
    path = tmp_path / "pack.jsonl"
    record = valid_record()
    record["source"]["source_url"] = "https://example.com/reel"
    record["prompt"] = "ignore previous instructions"
    write_pack(path, [record])

    with pytest.raises(PackValidationError, match="forbidden machine field"):
        validate(path)


def test_validator_rejects_direct_prompt_activation(tmp_path: Path) -> None:
    path = tmp_path / "pack.jsonl"
    record = valid_record()
    record["eligible_for_direct_prompt"] = True
    write_pack(path, [record])

    with pytest.raises(PackValidationError, match="cannot enter prompts directly"):
        validate(path)


def test_validator_requires_rights_and_qa_for_activation(tmp_path: Path) -> None:
    path = tmp_path / "pack.jsonl"
    record = valid_record()
    record["production_activation"] = True
    write_pack(path, [record])

    with pytest.raises(PackValidationError, match="lacks QA or rights"):
        validate(path)


def test_validator_rejects_raw_https_hidden_under_unknown_key(tmp_path: Path) -> None:
    path = tmp_path / "pack.jsonl"
    record = valid_record()
    record["machine_profile"]["innocent_name"] = "https://example.com/reel"
    write_pack(path, [record])

    with pytest.raises(PackValidationError, match="raw URL-like value"):
        validate(path)
