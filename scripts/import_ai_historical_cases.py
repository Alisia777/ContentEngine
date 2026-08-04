#!/usr/bin/env python3
"""Validate an AI historical-case manifest and request a server-side import.

This command is intentionally offline by default.  ``--commit`` is the only
mode that opens a network connection.  Commit sends only an authenticated Edge
request for an already registered source; normalized manifest cases are never
sent to the service-role-only database RPC.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path, PurePath
import re
from typing import Any, Callable, Mapping, Sequence
from urllib import error, request
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5


SCHEMA_VERSION = "ai_historical_cases.v1"
EDGE_FUNCTION_NAME = "creator-ai-case-import"
PUBLIC_APP_ORIGIN = "https://alisia777.github.io"
MAX_MANIFEST_BYTES = 5_242_880
MAX_CASES = 10_000
MAX_BATCH_SIZE = 100
MAX_RESPONSE_BYTES = 8_388_608
DEFAULT_TIMEOUT_SECONDS = 60
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
SKU_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+()-]{0,119}$")
CHANNEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,59}$")
METRIC_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
PARSER_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
URL_LIKE_PATTERN = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
FORMULA_PREFIX_PATTERN = re.compile(r"^[\s\u0000-\u001f]*[=+@-]")

PRODUCT_CATEGORIES = {
    "cosmetics",
    "baa",
    "sports_food",
    "food",
    "household",
    "apparel",
    "electronics",
    "other",
}
OUTCOMES = {"good", "bad", "review"}
OUTCOME_DIMENSIONS = {
    "overall",
    "sales",
    "orders",
    "conversion",
    "buyout",
    "engagement",
    "cart_to_order",
    "visit_to_cart",
    "visit_to_order",
    "sale_per_view",
    "revenue",
    "profitability",
    "ad_efficiency",
    "funnel",
    "attribution",
    "creative_angle",
    "data_quality",
    "other",
    "overall_performance",
    "organic_growth",
    "advertising_efficiency",
    "product_card_conversion",
    "inventory",
    "evidence_sufficiency",
    "purchase_transition",
    "content_conversion",
    "product_mapping",
    "attribution_window",
}
CREATIVE_ANGLES = {
    "product_focus",
    "trust_builder",
    "demonstration",
    "comparison",
    "objection_handling",
    "curiosity_gap",
}
PLATFORMS = {
    "wildberries",
    "ozon",
    "instagram",
    "tiktok",
    "youtube",
    "vk",
    "telegram",
    "other",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "product_category",
    "original_filename",
    "source_sha256",
    "parser_version",
    "cases",
}
CASE_KEYS = {
    "external_case_id",
    "product_category",
    "product_sku",
    "marketplace_sku",
    "product_title",
    "brand",
    "platform",
    "channel",
    "period_start",
    "period_end",
    "outcome",
    "outcome_dimension",
    "status_label",
    "metrics",
    "confidence",
    "creative_angle",
    "provenance",
}
PROVENANCE_KEYS = {"sheet", "row", "row_hash"}


class HistoricalCaseImportError(ValueError):
    """A validation or transport failure safe to show in operator logs."""


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HistoricalCaseImportError(f"{path} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise HistoricalCaseImportError(f"{path} has a non-string field name")
    return value


def _require_only_keys(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise HistoricalCaseImportError(f"{path} has unknown field(s): {', '.join(unknown)}")


def _require_text(
    value: Any,
    path: str,
    *,
    minimum: int = 1,
    maximum: int,
    reject_formula: bool = True,
) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise HistoricalCaseImportError(f"{path} must be trimmed text")
    if not minimum <= len(value) <= maximum:
        raise HistoricalCaseImportError(f"{path} length must be between {minimum} and {maximum}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise HistoricalCaseImportError(f"{path} contains a control character")
    if URL_LIKE_PATTERN.search(value):
        raise HistoricalCaseImportError(f"{path} must not contain a raw URL")
    if reject_formula and FORMULA_PREFIX_PATTERN.search(value):
        raise HistoricalCaseImportError(f"{path} looks like a spreadsheet formula")
    return value


def _require_identifier(value: Any, path: str, *, maximum: int = 160) -> str:
    text = _require_text(value, path, maximum=maximum, reject_formula=False)
    if not IDENTIFIER_PATTERN.fullmatch(text):
        raise HistoricalCaseImportError(f"{path} has an invalid identifier")
    return text


def _require_sku(value: Any, path: str) -> str:
    text = _require_text(value, path, maximum=120, reject_formula=False)
    if SKU_PATTERN.fullmatch(text) is None:
        raise HistoricalCaseImportError(f"{path} has an invalid SKU")
    return text


def _require_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise HistoricalCaseImportError(f"{path} must be lowercase SHA-256")
    return value


def _require_iso_date(value: Any, path: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise HistoricalCaseImportError(f"{path} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise HistoricalCaseImportError(f"{path} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise HistoricalCaseImportError(f"{path} must be an ISO date")
    return parsed


def _validate_metrics(value: Any, path: str) -> None:
    metrics = _require_object(value, path)
    if not 1 <= len(metrics) <= 20:
        raise HistoricalCaseImportError(f"{path} must contain 1 to 20 metrics")
    for key, metric in metrics.items():
        if METRIC_KEY_PATTERN.fullmatch(key) is None:
            raise HistoricalCaseImportError(f"{path}.{key} has an invalid metric key")
        if isinstance(metric, bool) or not isinstance(metric, (int, float)):
            raise HistoricalCaseImportError(f"{path}.{key} must be numeric")
        number = float(metric)
        if not math.isfinite(number) or abs(number) > 1_000_000_000_000:
            raise HistoricalCaseImportError(f"{path}.{key} is outside safe bounds")


def _validate_case(value: Any, index: int) -> str:
    path = f"cases[{index}]"
    case = _require_object(value, path)
    _require_only_keys(case, CASE_KEYS, path)
    required = CASE_KEYS - {"product_sku", "marketplace_sku", "creative_angle"}
    missing = sorted(required - set(case))
    if missing:
        raise HistoricalCaseImportError(f"{path} is missing field(s): {', '.join(missing)}")

    external_case_id = _require_identifier(case["external_case_id"], f"{path}.external_case_id")
    category = case["product_category"]
    if category not in PRODUCT_CATEGORIES:
        raise HistoricalCaseImportError(f"{path}.product_category is invalid")
    for optional_sku in ("product_sku", "marketplace_sku"):
        if optional_sku in case:
            _require_sku(case[optional_sku], f"{path}.{optional_sku}")
    _require_text(case["product_title"], f"{path}.product_title", minimum=2, maximum=180)
    _require_text(case["brand"], f"{path}.brand", maximum=100)
    platform = _require_text(case["platform"], f"{path}.platform", maximum=40, reject_formula=False)
    if platform not in PLATFORMS:
        raise HistoricalCaseImportError(f"{path}.platform is invalid")
    channel = _require_text(case["channel"], f"{path}.channel", maximum=60, reject_formula=False)
    if CHANNEL_PATTERN.fullmatch(channel) is None:
        raise HistoricalCaseImportError(f"{path}.channel has an invalid identifier")
    period_start = _require_iso_date(case["period_start"], f"{path}.period_start")
    period_end = _require_iso_date(case["period_end"], f"{path}.period_end")
    if period_start > period_end or (period_end - period_start).days > 3_660:
        raise HistoricalCaseImportError(f"{path} has an invalid period")
    if case["outcome"] not in OUTCOMES:
        raise HistoricalCaseImportError(f"{path}.outcome is invalid")
    if case["outcome_dimension"] not in OUTCOME_DIMENSIONS:
        raise HistoricalCaseImportError(f"{path}.outcome_dimension is invalid")
    _require_text(case["status_label"], f"{path}.status_label", maximum=80)
    _validate_metrics(case["metrics"], f"{path}.metrics")
    confidence = case["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise HistoricalCaseImportError(f"{path}.confidence must be numeric")
    if not math.isfinite(float(confidence)) or not 0 <= float(confidence) <= 1:
        raise HistoricalCaseImportError(f"{path}.confidence must be between 0 and 1")
    if "creative_angle" in case and case["creative_angle"] not in CREATIVE_ANGLES:
        raise HistoricalCaseImportError(f"{path}.creative_angle is invalid")

    provenance = _require_object(case["provenance"], f"{path}.provenance")
    _require_only_keys(provenance, PROVENANCE_KEYS, f"{path}.provenance")
    if set(provenance) != PROVENANCE_KEYS:
        raise HistoricalCaseImportError(f"{path}.provenance is incomplete")
    _require_text(provenance["sheet"], f"{path}.provenance.sheet", maximum=100)
    row = provenance["row"]
    if isinstance(row, bool) or not isinstance(row, int) or not 1 <= row <= 1_000_000:
        raise HistoricalCaseImportError(f"{path}.provenance.row is invalid")
    _require_sha256(provenance["row_hash"], f"{path}.provenance.row_hash")
    return external_case_id


def validate_manifest(value: Any) -> dict[str, Any]:
    """Validate a manifest without mutating or normalizing source values."""

    manifest = _require_object(value, "manifest")
    _require_only_keys(manifest, TOP_LEVEL_KEYS, "manifest")
    missing = sorted(TOP_LEVEL_KEYS - set(manifest))
    if missing:
        raise HistoricalCaseImportError(f"manifest is missing field(s): {', '.join(missing)}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise HistoricalCaseImportError("manifest.schema_version is unsupported")
    if manifest["product_category"] not in PRODUCT_CATEGORIES:
        raise HistoricalCaseImportError("manifest.product_category is invalid")
    filename = _require_text(
        manifest["original_filename"],
        "manifest.original_filename",
        maximum=240,
        reject_formula=False,
    )
    if PurePath(filename).name != filename or "/" in filename or "\\" in filename:
        raise HistoricalCaseImportError("manifest.original_filename must be a basename")
    lower_filename = filename.casefold()
    if lower_filename.endswith((".xlsm", ".xlam", ".xlsb", ".docm", ".pptm")):
        raise HistoricalCaseImportError("macro-enabled source files are forbidden")
    if not lower_filename.endswith((".xlsx", ".csv")):
        raise HistoricalCaseImportError("source must be .xlsx or .csv")
    _require_sha256(manifest["source_sha256"], "manifest.source_sha256")
    parser_version = _require_text(
        manifest["parser_version"],
        "manifest.parser_version",
        maximum=80,
        reject_formula=False,
    )
    if PARSER_VERSION_PATTERN.fullmatch(parser_version) is None:
        raise HistoricalCaseImportError("manifest.parser_version is invalid")
    cases = manifest["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise HistoricalCaseImportError(f"manifest.cases must contain 1 to {MAX_CASES} cases")
    identifiers = [_validate_case(case, index) for index, case in enumerate(cases)]
    duplicates = sorted(identifier for identifier, count in Counter(identifiers).items() if count > 1)
    if duplicates:
        raise HistoricalCaseImportError(f"manifest has duplicate external_case_id: {duplicates[0]}")
    return manifest


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes (object keys sorted, no padding)."""

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise HistoricalCaseImportError("manifest cannot be canonicalized") from exc
    return text.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
        if size < 2 or size > MAX_MANIFEST_BYTES:
            raise HistoricalCaseImportError("manifest size is outside safe bounds")
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        value = json.loads(
            text,
            parse_constant=lambda token: (_ for _ in ()).throw(
                HistoricalCaseImportError(f"invalid JSON number: {token}")
            ),
        )
    except HistoricalCaseImportError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoricalCaseImportError("manifest is not valid UTF-8 JSON") from exc
    return validate_manifest(value)


def _validated_source_id(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise HistoricalCaseImportError("--source-id is required with --commit")
        return None
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HistoricalCaseImportError("--source-id must be a UUID") from exc
    return str(parsed)


def _validated_organization_id(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise HistoricalCaseImportError("--organization-id is required with --commit")
        return None
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HistoricalCaseImportError("--organization-id must be a UUID") from exc
    return str(parsed)


def build_batches(
    manifest: dict[str, Any],
    *,
    source_id: str | None = None,
    batch_size: int = MAX_BATCH_SIZE,
) -> tuple[str, list[dict[str, Any]]]:
    validate_manifest(manifest)
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise HistoricalCaseImportError(f"batch size must be between 1 and {MAX_BATCH_SIZE}")
    validated_source_id = _validated_source_id(source_id, required=False)
    manifest_hash = canonical_sha256(manifest)
    cases = manifest["cases"]
    chunks = [cases[index : index + batch_size] for index in range(0, len(cases), batch_size)]
    batch_count = len(chunks)
    batches: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "product_category": manifest["product_category"],
            "original_filename": manifest["original_filename"],
            "source_sha256": manifest["source_sha256"],
            "parser_version": manifest["parser_version"],
            "manifest_sha256": manifest_hash,
            "idempotency_key": (f"ai-historical:v1:{manifest_hash}:{index:04d}/{batch_count:04d}"),
            "batch_index": index,
            "batch_count": batch_count,
            "cases": chunk,
            "parsed_row_count": len(chunk),
            "parser_quarantined_row_count": 0,
            "parser_quarantine_summary": {},
        }
        if validated_source_id is not None:
            payload["source_id"] = validated_source_id
        batches.append(payload)
    return manifest_hash, batches


def _validated_supabase_origin(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError as exc:
        raise HistoricalCaseImportError("SUPABASE_URL is invalid") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".supabase.co")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise HistoricalCaseImportError("SUPABASE_URL must be an HTTPS Supabase origin")
    return f"https://{parsed.hostname}"


def _validated_api_credential(value: str, name: str) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not 32 <= len(value) <= 4096
        or any(ord(character) < 33 or ord(character) == 127 for character in value)
    ):
        raise HistoricalCaseImportError(f"{name} is invalid")
    return value


class SupabaseEdgeImportClient:
    def __init__(
        self,
        *,
        supabase_url: str,
        publishable_key: str,
        user_access_token: str,
        opener: Callable[..., Any] = request.urlopen,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._origin = _validated_supabase_origin(supabase_url)
        self._publishable_key = _validated_api_credential(publishable_key, "SUPABASE_PUBLISHABLE_KEY")
        self._user_access_token = _validated_api_credential(user_access_token, "CONTENTENGINE_USER_ACCESS_TOKEN")
        self._opener = opener
        if not 1 <= timeout_seconds <= 300:
            raise HistoricalCaseImportError("timeout is outside safe bounds")
        self._timeout_seconds = timeout_seconds

    def import_registered_source(
        self,
        *,
        organization_id: str,
        source_id: str,
        product_category: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body = canonical_json_bytes(
            {
                "action": "parse_and_import",
                "organization_id": organization_id,
                "source_id": source_id,
                "product_category": product_category,
                "adapter": "auto",
                "commit": True,
                "idempotency_key": idempotency_key,
            }
        )
        api_request = request.Request(
            f"{self._origin}/functions/v1/{EDGE_FUNCTION_NAME}",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._user_access_token}",
                "Content-Type": "application/json",
                "Origin": PUBLIC_APP_ORIGIN,
                "apikey": self._publishable_key,
            },
        )
        try:
            with self._opener(api_request, timeout=self._timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                response_body = response.read(MAX_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            status = int(exc.code)
            exc.close()
            raise HistoricalCaseImportError(f"historical case Edge import failed (HTTP {status})") from None
        except (error.URLError, TimeoutError, OSError):
            raise HistoricalCaseImportError("historical case Edge import failed") from None
        if status < 200 or status >= 300:
            raise HistoricalCaseImportError(f"historical case Edge import failed (HTTP {status})")
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise HistoricalCaseImportError("historical case Edge response was too large")
        try:
            wire_result = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HistoricalCaseImportError("historical case Edge returned invalid JSON") from exc
        result = (
            wire_result["data"]
            if isinstance(wire_result, dict) and isinstance(wire_result.get("data"), dict)
            else wire_result
        )
        completed = (
            isinstance(result, dict)
            and result.get("ok") is True
            and isinstance(result.get("batch"), dict)
            and result["batch"].get("status") == "completed"
        )
        parser_rejected = (
            isinstance(result, dict)
            and result.get("ok") is False
            and result.get("status") == "parser_rejected_all"
            and result.get("retryable") is True
            and result.get("batch_persisted") is True
        )
        if not completed and not parser_rejected:
            raise HistoricalCaseImportError("historical case Edge rejected the import")
        return result


def _summary(manifest: dict[str, Any], manifest_hash: str, batches: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "manifest_sha256": manifest_hash,
        "source_sha256": manifest["source_sha256"],
        "cases": len(manifest["cases"]),
        "batches": len(batches),
        "per_category": dict(sorted(Counter(case["product_category"] for case in manifest["cases"]).items())),
        "per_outcome": dict(sorted(Counter(case["outcome"] for case in manifest["cases"]).items())),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate/import a reviewed AI historical-case manifest.")
    parser.add_argument("manifest", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate only (default)")
    mode.add_argument(
        "--commit",
        action="store_true",
        help="ask the authenticated Edge function to reparse a registered source",
    )
    parser.add_argument("--organization-id", help="organization UUID owning the registered source")
    parser.add_argument("--source-id", help="registered AI knowledge-source UUID")
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH_SIZE)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args(argv)


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Callable[..., Any] = request.urlopen,
) -> dict[str, Any]:
    args = parse_args(argv)
    manifest = load_manifest(args.manifest)
    source_id = _validated_source_id(args.source_id, required=args.commit)
    organization_id = _validated_organization_id(args.organization_id, required=args.commit)
    manifest_hash, batches = build_batches(manifest, source_id=source_id, batch_size=args.batch_size)
    result = _summary(manifest, manifest_hash, batches)
    if not args.commit:
        return {"ok": True, "mode": "dry_run", **result}

    env = os.environ if environ is None else environ
    if str(env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_SECRET_KEY") or ""):
        raise HistoricalCaseImportError("service role credentials are forbidden for CLI import")
    supabase_url = str(env.get("SUPABASE_URL") or "")
    publishable_key = str(env.get("SUPABASE_PUBLISHABLE_KEY") or "")
    primary_user_token = str(env.get("CONTENTENGINE_USER_ACCESS_TOKEN") or "")
    legacy_user_token = str(env.get("SUPABASE_USER_JWT") or "")
    if primary_user_token and legacy_user_token and primary_user_token != legacy_user_token:
        raise HistoricalCaseImportError("conflicting authenticated user tokens")
    user_access_token = primary_user_token or legacy_user_token
    client = SupabaseEdgeImportClient(
        supabase_url=supabase_url,
        publishable_key=publishable_key,
        user_access_token=user_access_token,
        opener=opener,
        timeout_seconds=args.timeout_seconds,
    )
    assert organization_id is not None
    assert source_id is not None
    idempotency_key = str(
        uuid5(
            NAMESPACE_URL,
            ":".join(
                (
                    "contentengine-ai-historical-import-v1",
                    organization_id,
                    source_id,
                    manifest_hash,
                )
            ),
        )
    )
    edge_result = client.import_registered_source(
        organization_id=organization_id,
        source_id=source_id,
        product_category=str(manifest["product_category"]),
        idempotency_key=idempotency_key,
    )
    edge_batch = edge_result.get("batch") if isinstance(edge_result.get("batch"), dict) else {}
    return {
        "ok": edge_result.get("ok") is True,
        "mode": "commit",
        "registered_source_reparsed": True,
        "local_validation": result,
        "organization_id": organization_id,
        "source_id": source_id,
        "idempotency_key": idempotency_key,
        "source_sha256": edge_result.get("source_sha256"),
        "manifest_sha256": edge_result.get("manifest_sha256"),
        "status": edge_result.get("status") or edge_batch.get("status") or edge_batch.get("import_status"),
        "parsed": edge_result.get("parsed"),
        "imported": edge_result.get("imported"),
        "quarantined": edge_result.get("quarantined"),
        "matched": edge_result.get("matched"),
        "per_category": edge_result.get("per_category"),
        "parser_quarantine_summary": edge_result.get("parser_quarantine_summary"),
        "batch": edge_batch,
        "batch_persisted": edge_result.get("batch_persisted", edge_result.get("ok") is True),
        "retryable": edge_result.get("retryable", False),
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(argv)
    except HistoricalCaseImportError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
