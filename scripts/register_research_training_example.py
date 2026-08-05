#!/usr/bin/env python3
"""Register one governed public YouTube example in ContentEngine research.

The command uses the production management API only from a protected GitHub
Environment.  It calls the service-only SQL wrapper installed by the reviewed
migration, performs no provider request and prints only a bounded receipt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

from scripts.bootstrap_supabase_owner import (
    OwnerBootstrapError,
    SupabaseManagementClient,
    _rows_from_response,
    _sql_literal,
    _validated_uuid,
)


VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE = re.compile(
    r"^https://(?:www\.|m\.)?(?:"
    r"youtu\.be/(?P<short>[A-Za-z0-9_-]{11})(?:[/?#&].*)?"
    r"|youtube\.com/(?:shorts|embed|live)/(?P<path>[A-Za-z0-9_-]{11})(?:[/?#&].*)?"
    r"|youtube\.com/watch\?(?:[^#]*&)?v=(?P<watch>[A-Za-z0-9_-]{11})(?:[&#].*)?"
    r")$",
    re.IGNORECASE,
)


class TrainingExampleRegistrationError(RuntimeError):
    """A non-sensitive failure safe for Actions logs."""


def _video_id(value: str) -> str:
    match = YOUTUBE.fullmatch(str(value or "").strip())
    if not match:
        raise TrainingExampleRegistrationError("youtube_source_url_invalid")
    candidate = next((item for item in match.groupdict().values() if item), "")
    if not VIDEO_ID.fullmatch(candidate):
        raise TrainingExampleRegistrationError("youtube_video_id_invalid")
    return candidate


def _bounded(value: Any, maximum: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text[:maximum]


def register_training_example(
    *,
    client: SupabaseManagementClient,
    project_id: str,
    source_url: str,
    compliance_category: str,
    market_category_name: str,
    training_role: str,
    human_summary: str,
    idempotency_key: str,
) -> dict[str, Any]:
    project = _validated_uuid(project_id)
    video_id = _video_id(source_url)
    category = str(compliance_category or "").strip().lower()
    if category not in {
        "cosmetics",
        "baa",
        "sports_food",
        "food",
        "household",
        "apparel",
        "electronics",
        "other",
    }:
        raise TrainingExampleRegistrationError("compliance_category_invalid")
    market = _bounded(market_category_name, 160)
    summary = _bounded(human_summary, 1000)
    role = str(training_role or "").strip().lower()
    key = _bounded(idempotency_key, 180)
    if len(market) < 2 or len(summary) < 20:
        raise TrainingExampleRegistrationError("training_example_text_invalid")
    if role not in {"reference", "competitor_mechanic", "anti_example"}:
        raise TrainingExampleRegistrationError("training_role_invalid")
    if len(key) < 8:
        raise TrainingExampleRegistrationError("idempotency_key_invalid")

    payload_sql = (
        "jsonb_build_object("
        f"'project_id', {_sql_literal(project)}, "
        f"'source_url', {_sql_literal(source_url.strip())}, "
        f"'compliance_category', {_sql_literal(category)}, "
        f"'market_category_name', {_sql_literal(market)}, "
        f"'training_role', {_sql_literal(role)}, "
        f"'human_summary', {_sql_literal(summary)}, "
        "'public_source_ack', true, "
        "'no_exact_copy_ack', true, "
        f"'idempotency_key', {_sql_literal(key)}"
        ")"
    )
    response = client.execute(
        "select public.system_register_research_training_example("
        f"{payload_sql}"
        ") as result"
    )
    rows = _rows_from_response(response)
    if len(rows) != 1 or not isinstance(rows[0].get("result"), dict):
        raise TrainingExampleRegistrationError(
            "training_example_receipt_unavailable"
        )
    result = rows[0]["result"]
    if result.get("ok") is not True:
        raise TrainingExampleRegistrationError("training_example_not_registered")
    if result.get("youtube_video_id") != video_id:
        raise TrainingExampleRegistrationError("training_example_video_mismatch")
    if result.get("compliance_category") != category:
        raise TrainingExampleRegistrationError("training_example_category_mismatch")
    if result.get("source_registered") is not True:
        raise TrainingExampleRegistrationError("training_example_source_missing")
    if result.get("provider_call_performed") is not False:
        raise TrainingExampleRegistrationError("unexpected_provider_call")
    if result.get("paid_analysis_performed") is not False:
        raise TrainingExampleRegistrationError("unexpected_paid_analysis")
    if result.get("exact_copy_allowed") is not False:
        raise TrainingExampleRegistrationError("unsafe_copy_policy")

    return {
        "ok": True,
        "version": _bounded(result.get("version"), 80),
        "project_id": project,
        "run_id": _bounded(result.get("run_id"), 40),
        "run_status": _bounded(result.get("run_status"), 40),
        "run_error_code": _bounded(result.get("run_error_code"), 100),
        "source_id": _bounded(result.get("source_id"), 40),
        "youtube_video_id": video_id,
        "compliance_category": category,
        "market_category_hint": market,
        "category_binding_name": _bounded(
            result.get("category_binding_name"), 160
        ),
        "category_binding_matches": result.get("category_binding_matches")
        is True,
        "source_ledger_id": _bounded(result.get("source_ledger_id"), 40),
        "analysis_event_id": _bounded(result.get("analysis_event_id"), 40),
        "learning_state": _bounded(result.get("learning_state"), 80),
        "replay": result.get("replay") is True,
        "provider_call_performed": False,
        "paid_analysis_performed": False,
        "exact_copy_allowed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register one public YouTube example without paid analysis",
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--compliance-category", required=True)
    parser.add_argument("--market-category-name", required=True)
    parser.add_argument(
        "--training-role",
        choices=("reference", "competitor_mechanic", "anti_example"),
        default="reference",
    )
    parser.add_argument("--human-summary", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--receipt-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        client = SupabaseManagementClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        receipt = register_training_example(
            client=client,
            project_id=args.project_id,
            source_url=args.source_url,
            compliance_category=args.compliance_category,
            market_category_name=args.market_category_name,
            training_role=args.training_role,
            human_summary=args.human_summary,
            idempotency_key=args.idempotency_key,
        )
    except (
        TrainingExampleRegistrationError,
        OwnerBootstrapError,
    ) as exc:
        print(f"Training example registration stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Training example registration stopped: unexpected internal failure",
            file=sys.stderr,
        )
        return 1

    encoded = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)
    if args.receipt_path:
        with open(args.receipt_path, "w", encoding="utf-8") as target:
            target.write(encoded + "\n")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
