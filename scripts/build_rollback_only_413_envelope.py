#!/usr/bin/env python3
"""Build the exact rollback-only SQL envelope for the Pika 413 incident test."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608210002_generation_strategy_fal_result_http_413_recovery_v1.sql"
)
INCIDENT_TEST = (
    ROOT
    / "supabase/incidents/generation_strategy_fal_result_http_413_exact_incident_test.sql"
)
TRANSACTION = re.compile(
    r"\A(?:\ufeff)?\s*begin\s*;(?P<body>.*?)(?P<end>commit|rollback)\s*;\s*\Z",
    flags=re.IGNORECASE | re.DOTALL,
)


def _unwrap(path: Path, expected_end: str) -> str:
    source = path.read_text(encoding="utf-8")
    match = TRANSACTION.fullmatch(source)
    if match is None or match.group("end").casefold() != expected_end:
        raise RuntimeError(f"transaction wrapper mismatch: {path.name}")
    return match.group("body").strip()


def build_envelope() -> str:
    migration_body = _unwrap(MIGRATION, "commit")
    incident_body = _unwrap(INCIDENT_TEST, "rollback")
    envelope = "\n".join(
        (
            "begin;",
            "set local lock_timeout = '5s';",
            "set local statement_timeout = '120s';",
            "set local idle_in_transaction_session_timeout = '120s';",
            "-- rollback-only migration compile and exact-incident runtime test",
            migration_body,
            incident_body,
            "rollback;",
            "",
        )
    )
    parse_sql(envelope)
    folded = envelope.casefold()
    if not envelope.startswith("begin;\n") or not envelope.endswith("rollback;\n"):
        raise RuntimeError("outer transaction wrapper invalid")
    if re.search(r"(^|\n)\s*commit\s*;", envelope, flags=re.IGNORECASE):
        raise RuntimeError("inner top-level commit remains")
    if len(re.findall(r"(^|\n)\s*rollback\s*;", envelope, flags=re.IGNORECASE)) != 1:
        raise RuntimeError("rollback cardinality invalid")
    for forbidden in (
        "http_post",
        "net.http",
        "pg_net",
        "fetch(",
        "system_record_generation_strategy_dispatch_result(",
        "system_mark_generation_strategy_dispatch_attempt(",
    ):
        if forbidden in folded:
            raise RuntimeError(f"forbidden network/dispatch primitive: {forbidden}")
    if (
        incident_body.casefold().count(
            "system_recover_generation_strategy_provider_result("
        )
        != 3
    ):
        raise RuntimeError("recovery call cardinality invalid")
    return envelope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    envelope = build_envelope()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(envelope, encoding="utf-8", newline="\n")
    payload = envelope.encode("utf-8")
    print(json.dumps({
        "path": str(args.output.resolve()),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "outer_begin": True,
        "final_rollback": True,
        "provider_network_calls": 0,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
