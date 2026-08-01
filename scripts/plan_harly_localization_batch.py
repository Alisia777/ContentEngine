#!/usr/bin/env python3
"""Offline dry-run planner for a rights-safe Harly 10-output localization batch.

The command accepts only internal identifiers, hashes and bounded planning
facts. It rejects raw URLs, captions, prompts and transcripts, never calls a
provider and never starts paid generation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any

from app.competitive_intelligence import SourceRelationship
from app.video_localization import (
    LocalizationMode,
    LocalizationPlanError,
    LocalizationProvider,
    VideoSource,
    build_localization_batch,
    microusd_to_usd,
)


MAX_INPUT_BYTES = 1_048_576
FORBIDDEN_KEYS = frozenset(
    {
        "url",
        "source_url",
        "video_url",
        "audio_url",
        "caption",
        "raw_caption",
        "prompt",
        "raw_prompt",
        "transcript",
        "raw_transcript",
    }
)


class InputContractError(ValueError):
    """A safe input-contract failure for CLI output."""


def _reject_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_KEYS:
                raise InputContractError(f"forbidden_key:{path}.{normalized}")
            _reject_forbidden_keys(nested, f"{path}.{normalized}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, f"{path}[{index}]")


def _read_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise InputContractError("input_file_missing")
    size = path.stat().st_size
    if size <= 0 or size > MAX_INPUT_BYTES:
        raise InputContractError("input_file_size_invalid")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputContractError("input_json_invalid") from exc
    if not isinstance(payload, dict):
        raise InputContractError("input_root_must_be_object")
    _reject_forbidden_keys(payload)
    return payload


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputContractError(f"{key}_required")
    return value.strip()


def _source(row: Any) -> VideoSource:
    if not isinstance(row, dict):
        raise InputContractError("source_must_be_object")
    try:
        duration = int(row.get("duration_seconds"))
    except (TypeError, ValueError) as exc:
        raise InputContractError("duration_seconds_invalid") from exc
    return VideoSource(
        source_id=_required_text(row, "source_id"),
        sku=_required_text(row, "sku"),
        category_key=_required_text(row, "category_key"),
        duration_seconds=duration,
        source_language=_required_text(row, "source_language").lower(),
        source_relationship=SourceRelationship(
            _required_text(row, "source_relationship")
        ),
        rights_confirmed=row.get("rights_confirmed") is True,
        qa_approved=row.get("qa_approved") is True,
        asset_sha256=_required_text(row, "asset_sha256").lower(),
        speech_present=row.get("speech_present", True) is True,
        on_screen_text_present=row.get("on_screen_text_present", False) is True,
    )


def _enum_list(
    payload: dict[str, Any],
    key: str,
    enum_type: type[Enum],
) -> tuple[Enum, ...]:
    raw = payload.get(key)
    if not isinstance(raw, list) or not raw:
        raise InputContractError(f"{key}_required")
    try:
        return tuple(enum_type(str(item)) for item in raw)
    except ValueError as exc:
        raise InputContractError(f"{key}_invalid") from exc


def _provider_overrides(
    payload: dict[str, Any],
) -> dict[LocalizationMode, LocalizationProvider]:
    raw = payload.get("provider_overrides", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise InputContractError("provider_overrides_invalid")
    try:
        return {
            LocalizationMode(str(mode)): LocalizationProvider(str(provider))
            for mode, provider in raw.items()
        }
    except ValueError as exc:
        raise InputContractError("provider_overrides_invalid") from exc


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def plan_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise InputContractError("sources_required")
    raw_languages = payload.get("target_languages")
    if not isinstance(raw_languages, list) or not raw_languages:
        raise InputContractError("target_languages_required")
    if any(not isinstance(item, str) for item in raw_languages):
        raise InputContractError("target_languages_invalid")

    modes = _enum_list(payload, "modes", LocalizationMode)
    try:
        target_count = int(payload.get("target_count", 10))
        qa_gate = int(payload.get("qa_gate_after_sequence", 2))
    except (TypeError, ValueError) as exc:
        raise InputContractError("batch_number_invalid") from exc

    plan = build_localization_batch(
        [_source(row) for row in raw_sources],
        target_languages=[item.lower() for item in raw_languages],
        modes=modes,
        target_count=target_count,
        provider_overrides=_provider_overrides(payload),
        qa_gate_after_sequence=qa_gate,
    )
    result = _jsonable(plan)
    result["total_estimated_cost_usd"] = microusd_to_usd(
        plan.total_estimated_cost_microusd
    )
    result["full_generation_baseline_usd"] = microusd_to_usd(
        plan.full_generation_baseline_microusd
    )
    result["estimated_savings_percent"] = round(
        plan.estimated_savings_ratio * 100,
        2,
    )
    result["dry_run"] = True
    result["provider_calls_started"] = False
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan a rights-safe Harly 10× localization batch without provider calls"
        ),
    )
    parser.add_argument("input", type=Path, help="Bounded JSON planning input")
    parser.add_argument("--output", type=Path, help="Optional output JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = plan_from_payload(_read_payload(args.input))
    except (InputContractError, LocalizationPlanError, ValueError) as exc:
        print(f"Harly localization plan stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Harly localization plan stopped: unexpected internal failure",
            file=sys.stderr,
        )
        return 1

    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
