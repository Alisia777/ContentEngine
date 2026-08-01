#!/usr/bin/env python3
"""Validate a private external-learning JSONL pack before server ingestion.

The validator is intentionally strict and offline. It rejects raw URLs, source
prose and records that claim production activation without human QA and rights.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


FORBIDDEN_KEYS = {
    "url",
    "source_url",
    "caption",
    "description",
    "prompt",
    "prompt_text",
    "raw_text",
    "concise_instruction",
    "provider_prompt",
    "author_name",
    "creator_name",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_SCHEMAS = {
    "external_creative_observation.v1",
    "funnel_observation.v1",
    "video_structure_observation.v1",
}


class PackValidationError(ValueError):
    pass


def walk(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_KEYS:
                raise PackValidationError(
                    f"forbidden machine field {'.'.join((*path, normalized))}"
                )
            walk(child, (*path, normalized))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, (*path, str(index)))
    elif isinstance(value, str) and "http://" in value.lower():
        raise PackValidationError(f"insecure URL-like value at {'.'.join(path)}")


def validate_record(value: Any, line_number: int) -> str:
    if not isinstance(value, dict):
        raise PackValidationError(f"line {line_number}: record must be an object")
    schema = str(value.get("schema_version") or "")
    if schema not in ALLOWED_SCHEMAS:
        raise PackValidationError(f"line {line_number}: unsupported schema {schema!r}")
    if not str(value.get("organization_id") or "").strip():
        raise PackValidationError(f"line {line_number}: organization_id is required")
    category = str(value.get("category_scope") or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,79}", category):
        raise PackValidationError(f"line {line_number}: invalid category_scope")
    source = value.get("source")
    if not isinstance(source, dict):
        raise PackValidationError(f"line {line_number}: source receipt is required")
    for key in ("source_file_sha256", "source_row_sha256", "manifest_sha256"):
        candidate = source.get(key)
        if candidate is not None and not SHA256.fullmatch(str(candidate)):
            raise PackValidationError(f"line {line_number}: invalid {key}")
    if value.get("eligible_for_direct_prompt") is True:
        raise PackValidationError(
            f"line {line_number}: external observations cannot enter prompts directly"
        )
    if value.get("production_activation") is True:
        if value.get("qa_status") != "approved" or source.get("rights_status") != "confirmed":
            raise PackValidationError(
                f"line {line_number}: production activation lacks QA or rights"
            )
    walk(value)
    return schema


def validate(path: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            total += 1
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PackValidationError(
                    f"line {line_number}: invalid JSON: {exc.msg}"
                ) from exc
            counts[validate_record(value, line_number)] += 1
    if total == 0:
        raise PackValidationError("pack is empty")
    return {"ok": True, "records": total, "schemas": dict(sorted(counts.items()))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.path)
    except (OSError, PackValidationError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
