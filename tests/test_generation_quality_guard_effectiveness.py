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
    / "supabase/migrations/202607280003_generation_quality_guard_effectiveness.sql"
).read_text(encoding="utf-8")
CONFLICT_MIGRATION = (
    ROOT
    / "supabase/migrations/202607300001_fix_learning_policy_snapshot_conflict_target.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT
    / "supabase/tests/generation_quality_guard_effectiveness_test.sql"
).read_text(encoding="utf-8")
HANDOFF_PATH = ROOT / "web/app/content-generation-handoff.js"
HANDOFF = HANDOFF_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
BUILD_ID = json.loads((ROOT / "web/app/build.json").read_text(encoding="utf-8"))["id"]


def _run_handoff(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable guard contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(HANDOFF, encoding="utf-8")
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


def test_effectiveness_sql_and_pgtap_are_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(CONFLICT_MIGRATION)
    assert parse_sql(PGTAP)


def test_effectiveness_uses_only_exact_applied_independent_numeric_outcomes() -> None:
    helper = MIGRATION[
        MIGRATION.index(
            "generation_quality_guard_effectiveness("
        )
        : MIGRATION.index(
            "-- Wrap the complete v6 policy."
        )
    ]
    for token in (
        "generation_quality_guard_lineage lineage",
        "lineage.guard_codes ? p_guard_code",
        "lineage.source = 'performance_learning'",
        "job.mode = 'real'",
        "job.provider = 'runway'",
        "job.status = 'succeeded'",
        "media.sha256 = job.output ->> 'sha256'",
        "review.media_sha256_snapshot = media.sha256",
        "decision.review_completion_hash = review.completion_hash",
        "decision.decided_by is distinct from job.requested_by",
        "decision.decided_by is distinct from job.assigned_to",
        "jsonb_typeof(review.result -> 'scores') = 'object'",
        "limit 60",
    ):
        assert token in helper
    for forbidden in (
        "decision.comment",
        "findings",
        "recommendations",
        "caption_text",
        "script_text",
        "transcript",
    ):
        assert forbidden not in helper.lower()


def test_two_variants_are_bounded_then_fail_closed_with_revalidation() -> None:
    for token in (
        "variant_1_count >= 6",
        "variant_1_average < 78",
        "selected_variant := 2",
        "variant_2_count >= 6",
        "variant_2_average < 78",
        "interval '30 days'",
        "status_value := 'cooldown'",
        "generation_allowed_value := false",
        "status_value := 'control_revalidation'",
        "status_value := 'control_pending_review'",
        "control_decision = 'approved' and control_score >= 78",
        "'minimum_observations_per_variant', 6",
        "'acceptance_threshold', 78",
    ):
        assert token in MIGRATION


def test_policy_snapshot_is_structural_private_append_only_and_exact() -> None:
    table = MIGRATION[
        MIGRATION.index(
            "create table if not exists\n"
            "  content_factory.generation_learning_policy_snapshots"
        )
        : MIGRATION.index(
            "-- Resolve one guard's exact post-application evidence."
        )
    ]
    for token in (
        "policy_hash text not null",
        "guard_codes jsonb not null",
        "guard_variants jsonb not null",
        "unique (\n      organization_id,\n      product_id,\n"
        "      platform,\n      model,\n      policy_hash\n    )",
        "enable row level security",
        "from public, anon, authenticated",
        "before update or delete",
    ):
        assert token in table
    for forbidden in (
        "prompt_text",
        "review_comment",
        "transcript",
        "finding",
        "recommendation",
        "caption",
        "script",
    ):
        assert forbidden not in table.lower()


def test_snapshot_is_written_before_the_existing_paid_command() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation("
        )
        :
    ]
    policy_call = wrapper.index(
        "server_policy := public.creator_generation_learning_policy("
    )
    snapshot_insert = wrapper.index(
        "insert into content_factory.generation_learning_policy_snapshots"
    )
    paid_command = wrapper.index(
        ".creator_start_real_generation_pre_policy_snapshot_v9(p_payload)",
        snapshot_insert,
    )
    assert policy_call < snapshot_insert < paid_command
    for token in (
        "server_policy -> 'generation_allowed' = 'false'::jsonb",
        "learning_context ->> 'applied_policy_hash'",
        "on conflict (\n    organization_id,\n    product_id,\n"
        "    platform,\n    model,\n    policy_hash\n  ) do nothing",
        "generation_learning_policy_snapshot_stale",
        "generation_learning_policy_snapshot_conflict",
    ):
        assert token in wrapper
    assert "or existing_snapshot.created_by" not in wrapper


def test_snapshot_conflict_targets_the_named_unique_constraint() -> None:
    for token in (
        "generation_learning_policy_snapshots_scope_uq",
        "unique (organization_id, product_id, platform, model, policy_hash)",
        (
            "on conflict on constraint "
            "generation_learning_policy_snapshots_scope_uq"
        ),
        "generation_learning_policy_snapshot_conflict_patch_failed",
        "generation_learning_policy_snapshot_conflict_contract_invalid",
        "creator_start_real_generation_pre_mode_prompt_v10(jsonb)",
    ):
        assert token in CONFLICT_MIGRATION.lower()


def test_browser_compiles_exact_variant_two_and_rejects_forged_variant() -> None:
    result = _run_handoff(
        """
const base = {
  version: "generation-learning-v7",
  applied: true,
  generation_allowed: true,
  confidence: "high",
  evidence_count: 12,
  preferred_angle: "product_focus",
  preferred_hook_patterns: ["concise"],
  quality_guard_codes: ["product_fidelity"],
  quality_guard_variants: { product_fidelity: 2 },
  quality_guard_effectiveness_status: "variant_2",
  policy_hash: "a".repeat(64),
};
const normalized = subject.normalizeGenerationLearningPolicy(base);
const compiled = subject.compileSafeGenerationBrief({
  mode: "real_gen4",
  productName: "Точный товар",
  sku: "SKU-V2",
  learningPolicy: base,
});
const forged = subject.normalizeGenerationLearningPolicy({
  ...base,
  quality_guard_variants: { product_fidelity: 3 },
});
return {
  ready: compiled.ready,
  variant: normalized.qualityGuardVariants.product_fidelity,
  status: normalized.qualityGuardEffectivenessStatus,
  stronger: compiled.prompt.includes(
    "QA+: один точный товар по исходнику"
  ),
  forgedApplied: forged.applied,
};
"""
    )
    assert result == {
        "ready": True,
        "variant": 2,
        "status": "variant_2",
        "stronger": True,
        "forgedApplied": False,
    }


def test_every_variant_two_fragment_matches_browser_edge_and_database() -> None:
    fragments = (
        "QA+: один товар строго по исходнику; не изменять ни одну букву, край, цвет или пропорцию упаковки.",
        "QA+: нейтральный ровный свет; весь товар резкий, без бликов, шума и размытия.",
        "QA+: товар занимает главный визуальный акцент и считывается без второго объекта.",
        "QA+: цельный чистый силуэт; никаких лишних деталей, дублей, швов и AI-артефактов.",
        "QA+: реалистичные материалы, масштаб и тени как в предметной съёмке.",
        "QA+: квадрат 1:1; упаковка целиком внутри безопасных полей.",
        "QA+: один точный товар по исходнику; упаковка, этикетка, текст, цвет и пропорции неизменны в каждом кадре.",
        "QA+: один непрерывный стабильный проход; без скачков, чёрных кадров, морфинга и мерцания.",
        "QA+: непрерывная разборчивая дорожка; без тишины, клиппинга, шума и рассинхронизации.",
        "QA+: произнести только точную реплику дословно; без пропусков, замен, повторов и новых слов.",
        "QA+: точный товар — главный объект первого кадра; одно действие начинается в первые 2 секунды.",
        "QA+: постоянные руки, лицо, упаковка и фактуры; без деформаций, дублей, швов и мерцания.",
        "QA+: естественный свет, материалы и движение; без гиперболы, постановочного эффекта и новых обещаний.",
        "QA+: вертикальный мастер 9:16; товар и лицо целиком остаются в безопасных полях.",
    )
    for fragment in fragments:
        assert fragment in MIGRATION
        assert fragment in HANDOFF
        assert fragment in EDGE


def test_edge_and_browser_fail_closed_on_cooldown_and_pending_control() -> None:
    for token in (
        "learningPolicy.quality_guard_effectiveness_status",
        "generation_quality_guard_control_review_pending",
        "generation_learning_rejection_guard_blocked",
    ):
        assert token in EDGE
    assert (
        'qualityGuardEffectivenessStatus\n'
        '        !== "control_pending_review"'
    ) in APP
    assert "ИИ советует дождаться QA" in APP
    assert "Это рекомендация" in APP
    assert "generation_quality_guard_control_review_pending" in API


def test_release_binds_new_compiler_gate_and_cache_versions() -> None:
    assert 'GENERATION_LEARNING_COMPILER_VERSION = "safe-brief-v7"' in HANDOFF
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in EDGE
    assert 'GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8"' in APP
    assert "./content-generation-handoff.js?v=20260826.rebuild-clean.7" in APP
    assert "./supabase-api.js?v=20260826.rebuild-clean.7" in APP
    assert "./app.js?v=20260826.rebuild-clean.7" in INDEX
    assert "select plan(19);" in PGTAP
    assert PGTAP.rstrip().endswith("rollback;")
