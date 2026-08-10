from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607280004_generation_provider_readiness_receipts.sql"
).read_text(encoding="utf-8")
FLEXIBLE_MIGRATION = (
    ROOT
    / "supabase/migrations/202607280008_flexible_video_generation_durations.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT
    / "supabase/tests/generation_provider_readiness_receipts_test.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
READINESS_PATH = ROOT / "web/app/generation-provider-readiness.js"
READINESS = READINESS_PATH.read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _run_readiness(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable readiness contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(READINESS, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_provider_readiness_sql_and_pgtap_are_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(FLEXIBLE_MIGRATION)
    assert parse_sql(PGTAP)


def test_receipts_are_private_append_only_bounded_and_public_safe() -> None:
    table = _between(
        MIGRATION,
        "create table if not exists\n"
        "  content_factory.generation_provider_readiness_receipts",
        "-- Only the trusted Edge function",
    )
    for token in (
        "provider text not null check (provider = 'runway')",
        "model in ('gen4_turbo', 'seedance2_fast', 'seedream5_lite')",
        "check (expires_at = checked_at + interval '15 minutes')",
        "enable row level security",
        "from public, anon, authenticated",
        "before update or delete",
    ):
        assert token in table
    for forbidden in (
        "provider_key",
        "api_key",
        "credit_balance",
        "quota_count",
        "raw_response",
        "prompt_text",
        "transcript",
    ):
        assert forbidden not in table.lower()


def test_only_edge_can_record_exact_safe_provider_outcomes() -> None:
    recorder = _between(
        FLEXIBLE_MIGRATION,
        "create or replace function\n"
        "  public.system_record_generation_provider_readiness",
        "create or replace function\n"
        "  content_factory_private.generation_provider_readiness",
    )
    for token in (
        "security definer",
        "membership.status = 'active'",
        "'checked_at', checked_at_value",
        "'expires_at', expires_at_value",
        "json_hash(receipt_body)",
        "from public, anon, authenticated",
        "to service_role",
    ):
        assert token in recorder
    for forbidden in (
        "credit_balance",
        "quota_count",
        "raw_response",
        "provider_key",
    ):
        assert forbidden not in recorder.lower()


def test_edge_persists_every_free_check_before_answering_the_browser() -> None:
    recorder = _between(
        EDGE,
        "const recordProviderReadiness = async",
        "const handlePreflight = async",
    )
    handler = _between(
        EDGE,
        "const handlePreflight = async",
        "const preflightPayload = readPreflightPayload",
    )
    assert '"system_record_generation_provider_readiness"' in recorder
    assert "checked_by: checkedBy" in recorder
    assert "creditBalance" not in recorder
    assert "maxDailyGenerations" not in recorder
    assert handler.count("await recordProviderReadiness(") == 2
    assert "if (receipt === null)" in handler
    for token in (
        "receipt_id: receipt.receiptId",
        "receipt_hash: receipt.receiptHash",
        "duration_seconds: readiness.durationSeconds",
        'receipt_version: "generation-provider-readiness-receipt-v2"',
        "expires_at: receipt.expiresAt",
    ):
        assert token in handler


def test_browser_accepts_only_fresh_exact_receipts_and_rejects_duplicates() -> None:
    result = _run_readiness(
        """
const nowMs = Date.parse("2026-07-28T12:05:00.000Z");
const receipt = {
  provider: "runway",
  model: "seedream5_lite",
  duration_seconds: 0,
  status: "ready",
  reason_code: "provider_ready",
  ready: true,
  fresh: true,
  estimated_credits: 4,
  balance_sufficient: true,
  model_available: true,
  daily_quota_available: true,
  learning_gate_version: "2026-07-29.v8",
  checked_at: "2026-07-28T12:00:00.000Z",
  expires_at: "2026-07-28T12:15:00.000Z",
  receipt_id: "fa000000-0000-4000-8000-000000000001",
  receipt_hash: "a".repeat(64),
  receipt_version: "generation-provider-readiness-receipt-v2",
};
return {
  valid: subject.normalizeGenerationProviderPreflight(
    receipt,
    { gateVersion: "2026-07-29.v8", nowMs },
  )?.model || null,
  stale: subject.normalizeGenerationProviderPreflight(
    { ...receipt, expires_at: "2026-07-28T12:05:00.000Z" },
    { gateVersion: "2026-07-29.v8", nowMs },
  ),
  wrongGate: subject.normalizeGenerationProviderPreflight(
    { ...receipt, learning_gate_version: "2026-07-27.v9" },
    { gateVersion: "2026-07-29.v8", nowMs },
  ),
  badHash: subject.normalizeGenerationProviderPreflight(
    { ...receipt, receipt_hash: "unsafe" },
    { gateVersion: "2026-07-29.v8", nowMs },
  ),
  contradictoryFailure: subject.normalizeGenerationProviderPreflight(
    { ...receipt, failure_code: "provider_rate_limited" },
    { gateVersion: "2026-07-29.v8", nowMs },
  ),
  duplicateCount: subject.generationProviderReadinessPreflights(
    { provider_readiness: [receipt, { ...receipt }] },
    { gateVersion: "2026-07-29.v8", nowMs },
  ).length,
};
"""
    )
    assert result == {
        "valid": "seedream5_lite",
        "stale": None,
        "wrongGate": None,
        "badHash": None,
        "contradictoryFailure": None,
        "duplicateCount": 0,
    }


def test_spend_overview_restores_fresh_receipt_without_authorizing_payment() -> None:
    loader = _between(
        APP,
        "async function loadGenerationSpendOverview",
        "async function loadGenerationModelAcceptance",
    )
    hydrator = _between(
        APP,
        "function hydrateGenerationProviderReadiness",
        "function generationPreflightErrorCode",
    )
    paid_start = _between(
        APP,
        "async function runGenerationPreflightForPaidStart",
        "async function submitRealGenerationReconciliation",
    )
    assert "hydrateGenerationProviderReadiness(target.data)" in loader
    assert "generationProviderReadinessPreflights(value" in hydrator
    assert 'previous?.status === "loading"' in hydrator
    assert "previous.serverCheckedAt >= serverCheckedAt" in hydrator
    assert 'source: "server_receipt"' in hydrator
    assert "force: true" in paid_start
    assert "awaitRetry: true" in paid_start


def test_api_boundary_revalidates_receipt_before_app_state() -> None:
    preflight = _between(
        API,
        'if (action === "preflight")',
        "if (!data.job",
    )
    assert "normalizeApiGenerationProviderPreflight(" in preflight
    assert "realGenerationSku(" in preflight
    assert "payload.duration_seconds" in preflight
    assert "return { ...data, preflight }" in preflight
    normalizer = _between(
        API,
        "function normalizeApiGenerationProviderPreflight",
        "export function mediaKindRequiresProduct",
    )
    assert "GENERATION_LEARNING_GATE_VERSION" in normalizer
    assert "PROVIDER_READINESS_RECEIPT_VERSION" in normalizer
    assert "PROVIDER_READINESS_SHA256_PATTERN" in normalizer


def test_release_versions_include_the_readiness_module_and_gate() -> None:
    assert "./app.js?v=20260810.os4.27" in INDEX
    assert "./supabase-api.js?v=20260810.os4.27" in APP
    assert (
        "./generation-provider-readiness.js?v=20260728.2"
        in APP
    )
    assert (
        'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"'
        in APP
    )
    assert (
        'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"'
        in EDGE
    )
