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
    / "supabase/migrations/202607270009_generation_rejection_learning.sql"
).read_text(encoding="utf-8")
HANDOFF = (
    ROOT / "web/app/content-generation-handoff.js"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")


def test_rejection_learning_migration_parses() -> None:
    assert parse_sql(MIGRATION)


def _run_handoff(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable learning contracts")
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


def test_rejection_layer_preserves_the_complete_existing_policy_chain() -> None:
    for token in (
        "set schema content_factory_private",
        "rename to creator_generation_learning_policy_audio_speech_v5",
        ".creator_generation_learning_policy_audio_speech_v5(p_payload)",
        "(base_policy - 'policy_hash' - 'requested_model')",
        "'version', 'generation-learning-v6'",
        "content_factory_private.json_hash(policy_without_hash)",
        "'requested_model', requested_model_value",
        "notify pgrst, 'reload schema'",
    ):
        assert token in MIGRATION


def test_hard_rejection_uses_only_exact_independent_generated_outcomes() -> None:
    resolver = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_learning_policy"
        ) : MIGRATION.index(
            "-- Edge checks the same flag"
        )
    ]
    for token in (
        "job.status = 'succeeded'",
        "job.mode = 'real'",
        "media.id::text = job.output ->> 'output_media_id'",
        "review.media_sha256_snapshot = media.sha256",
        "decision.review_completion_hash = review.completion_hash",
        "decision.media_sha256_snapshot =",
        "decision.decided_by is distinct from job.requested_by",
        "decision.decided_by is distinct from job.assigned_to",
        "signal.product_id = product_id_value",
        "signal.platform = platform_value",
        "signal.model = model_value",
        "signal.hook_patterns = selected_patterns_value",
        "decision = 'rejected'",
        "selected_approval_count = 0",
    ):
        assert token in resolver
    for forbidden in (
        "decision.comment",
        "review.result",
        "review.result -> 'findings'",
        "review.result -> 'recommendations'",
        "review.result -> 'strengths'",
        "transcript_excerpt",
        "caption_text",
        "script_text",
    ):
        assert forbidden not in resolver


def test_rejected_exploration_is_replaced_only_with_server_bounded_structures() -> None:
    for token in (
        "'product_focus'::text",
        "'demonstration'::text",
        "'trust_builder'::text",
        "'objection_handling'::text",
        "model_value = 'seedream5_lite'",
        "job.status not in ('failed', 'cancelled')",
        "candidate.rejection_count = 0",
        "or candidate.approval_count > 0",
        "order by candidate.use_count, candidate.priority",
        '"hard_rejected_structure_replaced"',
        '"hard_rejected_structures_exhausted"',
        "'safe_recovery_structures_are_server_bounded', true",
    ):
        assert token in MIGRATION
    assert "'comparison'::text" not in MIGRATION
    assert "'curiosity_gap'::text" not in MIGRATION


def test_quality_hooks_are_rebuilt_from_approved_outcomes_only() -> None:
    quality_filter = MIGRATION[
        MIGRATION.index(
            "if generation_allowed_value"
        ) : MIGRATION.index(
            "policy_without_hash :="
        )
    ]
    for token in (
        "base_policy ->> 'selection_mode' = 'quality'",
        "on quality.decision = 'approved'",
        "jsonb_array_elements_text(",
        "limit 4",
        "selected_patterns_value := approved_patterns_value",
        "'quality_hooks_require_approval', true",
    ):
        assert token in MIGRATION
    for decision in ("'rejected'", "'needs_changes'"):
        assert decision not in quality_filter


def test_exhaustion_is_blocked_in_browser_edge_and_database_before_spend() -> None:
    assert (
        "learningPolicy.generation_allowed === false"
        in EDGE
    )
    assert "generation_learning_rejection_guard_blocked" in EDGE
    edge_guard = EDGE.index("learningPolicy.generation_allowed === false")
    edge_provider_state = EDGE.index(
        "const { data: startData, error: startError }"
    )
    assert edge_guard < edge_provider_state

    for token in (
        "guard_generation_rejection_before_paid_job",
        "before insert on content_factory.generation_jobs",
        "new.mode <> 'real'",
        "new.provider <> 'runway'",
        "not new.allow_real_spend",
        "new.input ->> 'input_media_id'",
        "server_policy -> 'generation_allowed' = 'false'::jsonb",
        "message = 'generation_learning_rejection_guard_blocked'",
        "'paid_start_fails_closed_when_structures_exhausted', true",
    ):
        assert token in MIGRATION

    for token in (
        "Автогенерация остановлена",
        "Все безопасные структуры",
        "Автогенерация остановлена после QA",
        "generation_learning_rejection_guard_blocked",
    ):
        assert token in APP


def test_browser_normalizer_fails_closed_on_exhausted_policy() -> None:
    result = _run_handoff(
        """
        const common = {
          version: "generation-learning-v6",
          applied: true,
          confidence: "medium",
          selection_mode: "bounded_exploration",
          preferred_angle: "product_focus",
          preferred_hook_patterns: [],
          policy_hash: "a".repeat(64),
        };
        const blocked = subject.normalizeGenerationLearningPolicy({
          ...common,
          generation_allowed: false,
          reason_codes: ["hard_rejected_structures_exhausted"],
        });
        const allowed = subject.normalizeGenerationLearningPolicy(common);
        return {
          blockedApplied: blocked.applied,
          blockedAllowed: blocked.generationAllowed,
          blockedReason: blocked.reasonCodes[0],
          legacyApplied: allowed.applied,
          legacyAllowed: allowed.generationAllowed,
        };
        """
    )
    assert result == {
        "blockedApplied": False,
        "blockedAllowed": False,
        "blockedReason": "hard_rejected_structures_exhausted",
        "legacyApplied": True,
        "legacyAllowed": True,
    }
