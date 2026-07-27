from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270004_generation_audio_speech_learning.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
HANDOFF_PATH = ROOT / "web/app/content-generation-handoff.js"
HANDOFF = HANDOFF_PATH.read_text(encoding="utf-8")

AUDIO_REQUIREMENT = (
    "QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации."
)
SPEECH_REQUIREMENT = (
    "QA: реплика произносится дословно, без пропусков, замен и новых слов."
)


def _run_handoff(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable handoff contracts")
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


def test_recurring_learning_uses_only_exact_structured_evidence() -> None:
    resolver = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_learning_policy"
        ) : MIGRATION.index(
            "-- Keep the six audited score dimensions"
        )
    ]
    for token in (
        "job.input ->> 'model' = 'seedance2_fast'",
        "job.input -> 'audio' = 'true'::jsonb",
        "review_row.media_sha256_snapshot = media.sha256",
        "decision.review_completion_hash = review_row.completion_hash",
        "decision.media_sha256_snapshot",
        "evidence.source_sha256_snapshot = media.sha256",
        "valid_content_review_audio_metrics(",
        "'{speech_analysis,similarity_ratio}'",
        "'{speech_analysis,coverage_ratio}'",
        "'{speech_analysis,word_error_rate}'",
        "audio_evidence_count_value >= 6",
        "audio_issue_count_value * 3 >= audio_evidence_count_value",
        "speech_evidence_count_value >= 6",
        "speech_issue_count_value * 3 >= speech_evidence_count_value",
        "then 'audio_quality'",
        "then 'speech_fidelity'",
        "'provider_spend_requires_separate_confirmation', true",
    ):
        assert token in resolver
    for forbidden in (
        "decision.comment",
        "-> 'findings'",
        "-> 'recommendations'",
        "transcript_excerpt",
        "caption_text",
        "script_text",
    ):
        assert forbidden not in resolver


def test_immediate_repair_specializes_without_copying_review_text() -> None:
    resolver = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_repair_policy"
        ) : MIGRATION.index(
            "-- Extend both paid-boundary compilers"
        )
    ]
    for token in (
        "creator_generation_repair_policy_structured_scores_v1",
        "base_policy ->> 'model' <> 'seedance2_fast'",
        "base_policy ->> 'source_review_completion_hash'",
        "base_policy ->> 'source_media_sha256'",
        "valid_content_review_audio_metrics(",
        "speech_value ->> 'similarity_ratio'",
        "speech_value ->> 'coverage_ratio'",
        "speech_value ->> 'word_error_rate'",
        "then 'audio_quality'",
        "then 'speech_fidelity'",
        "'transcript_copy_excluded', true",
    ):
        assert token in resolver
    for forbidden in (
        "decision.comment",
        "-> 'findings'",
        "-> 'recommendations'",
        "transcript_excerpt",
        "caption_text",
        "script_text",
    ):
        assert forbidden not in resolver


def test_all_paid_boundary_compilers_share_exact_specialized_fragments() -> None:
    for fragment in (AUDIO_REQUIREMENT, SPEECH_REQUIREMENT):
        assert fragment in MIGRATION
        assert fragment in EDGE
        assert fragment in HANDOFF
    for code in ("audio_quality", "speech_fidelity"):
        assert code in MIGRATION
        assert code in EDGE
        assert code in HANDOFF
    assert "model !== \"seedance2_fast\"" in EDGE
    assert "mode !== REAL_SEEDANCE_MODE" in HANDOFF


def test_browser_compiles_specialized_guards_only_for_seedance() -> None:
    result = _run_handoff(
        f"""
        const repair = {{
          version: "review-repair-v1",
          applied: true,
          source_review_id: "11111111-1111-4111-8111-111111111111",
          source_generation_job_id: "22222222-2222-4222-8222-222222222222",
          source_media_id: "33333333-3333-4333-8333-333333333333",
          input_media_id: "44444444-4444-4444-8444-444444444444",
          product_id: "55555555-5555-4555-8555-555555555555",
          model: "seedance2_fast",
          platform: "tiktok",
          destination_ref: "campaign-seed",
          guard_codes: ["audio_quality", "speech_fidelity"],
          score_snapshot: {{
            technical: 65,
            product_fidelity: 90,
            hook_clarity: 60,
            visual_quality: 91,
            trust: 89,
            platform_fit: 92,
          }},
          source_review_completion_hash: "a".repeat(64),
          source_media_sha256: "b".repeat(64),
          policy_hash: "c".repeat(64),
        }};
        const normalized = subject.normalizeGenerationRepairPolicy(repair);
        const seedance = subject.compileSafeGenerationBrief({{
          mode: "real_seedance",
          productName: "Точный товар",
          sku: "SKU-SOUND",
          spokenScript: "Показываю точный товар крупно.",
          repairPolicy: normalized,
        }});
        const forgedGen4 = subject.normalizeGenerationRepairPolicy({{
          ...repair,
          model: "gen4_turbo",
        }});
        return {{
          applied: normalized.applied,
          seedanceReady: seedance.ready,
          hasAudio: seedance.prompt.includes({json.dumps(AUDIO_REQUIREMENT)}),
          hasSpeech: seedance.prompt.includes({json.dumps(SPEECH_REQUIREMENT)}),
          gen4FailsClosed: forgedGen4.applied === false,
        }};
        """
    )
    assert result == {
        "applied": True,
        "seedanceReady": True,
        "hasAudio": True,
        "hasSpeech": True,
        "gen4FailsClosed": True,
    }
