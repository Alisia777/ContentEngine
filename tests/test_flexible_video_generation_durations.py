from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
HANDOFF_PATH = ROOT / "web/app/content-generation-handoff.js"
HANDOFF = HANDOFF_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
MIGRATION = (
    ROOT
    / "supabase/migrations/202607280008_flexible_video_generation_durations.sql"
).read_text(encoding="utf-8")
RUNTIME_MIGRATION = (
    ROOT
    / "supabase/migrations/202607290001_flexible_video_generation_runtime.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/flexible_video_generation_durations_test.sql"
).read_text(encoding="utf-8")


def test_flexible_duration_sql_contracts_parse() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(RUNTIME_MIGRATION)
    assert parse_sql(PGTAP)


def test_browser_compiler_binds_every_selected_duration() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable duration contracts")
    script = f"""
import * as subject from {json.dumps(HANDOFF_PATH.as_uri())};
const rows = [
  ["real_gen4", 2],
  ["real_gen4", 10],
  ["real_seedance", 4],
  ["real_seedance", 15],
].map(([mode, duration]) => {{
  const compiled = subject.compileSafeGenerationBrief({{
    mode,
    durationSeconds: duration,
    productName: "Точный товар",
    sku: "SKU-DURATION",
  }});
  const inspected = subject.inspectContentGenerationPrompt(
    compiled.prompt,
    mode,
    {{ productName: "Точный товар", durationSeconds: duration }},
  );
  return {{
    mode,
    duration,
    compiledDuration: compiled.durationSeconds,
    ready: compiled.ready && inspected.ready,
    durationBound: compiled.prompt.includes(
      `длительностью ${{duration}} секунд`,
    ),
  }};
}});
process.stdout.write(JSON.stringify({{
  rows,
  fourSecondWords: subject.seedanceSpokenWordLimit(4),
  fifteenSecondWords: subject.seedanceSpokenWordLimit(15),
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["rows"] == [
        {
            "mode": "real_gen4",
            "duration": 2,
            "compiledDuration": 2,
            "ready": True,
            "durationBound": True,
        },
        {
            "mode": "real_gen4",
            "duration": 10,
            "compiledDuration": 10,
            "ready": True,
            "durationBound": True,
        },
        {
            "mode": "real_seedance",
            "duration": 4,
            "compiledDuration": 4,
            "ready": True,
            "durationBound": True,
        },
        {
            "mode": "real_seedance",
            "duration": 15,
            "compiledDuration": 15,
            "ready": True,
            "durationBound": True,
        },
    ]
    assert payload["fourSecondWords"] == 11
    assert payload["fifteenSecondWords"] == 41


def test_portal_recalculates_price_confirmation_and_preflight_by_duration() -> None:
    for token in (
        "durationOptions: Object.freeze([2, 5, 8, 10])",
        "durationOptions: Object.freeze([4, 8, 12, 15])",
        "creditsPerSecond: 5",
        "creditsPerSecond: 29",
        "`RUNWAY_GEN4_TURBO_${durationSeconds}S_USD_${estimatedUsd}`",
        "`RUNWAY_SEEDANCE2_FAST_${durationSeconds}S_AUDIO_USD_${estimatedUsd}`",
        'name="duration_seconds"',
        "sku.durationSeconds",
        "generationPreflightKey(sku)",
    ):
        assert token in APP
    assert "preflight.duration_seconds !== sku.durationSeconds" in APP
    assert "preflight.duration_seconds !== payload.duration_seconds" in API


def test_edge_and_database_fail_closed_on_duration_price_drift() -> None:
    for token in (
        "minimumDuration: 2",
        "maximumDuration: 10",
        "creditsPerSecond: 5",
        "minimumDuration: 4",
        "maximumDuration: 15",
        "creditsPerSecond: 29",
        "readRunwayGenerationSku(model, value.duration_seconds)",
        "duration_seconds: readiness.durationSeconds",
        'generation-provider-readiness-receipt-v2',
    ):
        assert token in EDGE
    for token in (
        "duration_seconds between 2 and 10",
        "estimated_cost_minor = duration_seconds * 5",
        "duration_seconds between 4 and 15",
        "estimated_cost_minor = duration_seconds * 29",
        "real_generation_sku_binding_invalid",
        "generation-provider-readiness-receipt-v2",
    ):
        assert token in MIGRATION
    for token in (
        "creator_start_gen4_turbo_5s",
        "creator_start_seedance2_fast_8s",
        "duration_value := (sku_config ->> 'duration_seconds')::integer",
        "estimated_cost_minor_value :=",
        "estimated_credits_value :=",
        "creator_start_real_generation_pre_flexible_duration_v12",
    ):
        assert token in RUNTIME_MIGRATION
    assert "'duration_seconds', 5" not in RUNTIME_MIGRATION
    assert "'duration_seconds', 8" not in RUNTIME_MIGRATION


def test_duration_change_never_reuses_old_learning_or_provider_receipt() -> None:
    learning_key = APP[
        APP.index("function generationLearningKey")
        : APP.index("function generationProductCategoryLabel")
    ]
    for token in (
        "identity.mediaId",
        "sku.model",
        "sku.durationSeconds",
        "platform",
        "productCategory",
    ):
        assert token in learning_key
    assert "`${sku.model}:${sku.durationSeconds}`" in APP
    assert "counts.get(`${receipt.model}:${receipt.duration_seconds}`)" in (
        ROOT / "web/app/generation-provider-readiness.js"
    ).read_text(encoding="utf-8")
