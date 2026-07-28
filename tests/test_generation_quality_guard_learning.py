import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260001_generation_quality_guard_learning.sql"
).read_text(encoding="utf-8")
HANDOFF_PATH = ROOT / "web/app/content-generation-handoff.js"
HANDOFF = HANDOFF_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)


def _run_handoff(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable learning contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            HANDOFF,
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_quality_guard_policy_wraps_existing_learning_without_replacing_it() -> None:
    for token in (
        "set schema content_factory_private",
        "rename to creator_generation_learning_policy_independent_quality_v3",
        ".creator_generation_learning_policy_independent_quality_v3(p_payload)",
        "if base_policy -> 'applied' is distinct from 'true'::jsonb then",
        "(base_policy - 'policy_hash' - 'requested_model')",
        "'version', 'generation-learning-v4'",
        "content_factory_private.json_hash(policy_without_hash)",
        "'requested_model', requested_model_value",
        "notify pgrst, 'reload schema'",
    ):
        assert token in MIGRATION


def test_quality_guards_use_only_independent_exact_generated_results() -> None:
    for token in (
        "job.status = 'succeeded'",
        "job.mode = 'real'",
        "media.id::text = job.output ->> 'output_media_id'",
        "media.product_id = job.product_id",
        "'generated_video', 'generated_image'",
        "decision.review_completion_hash = review.completion_hash",
        "decision.media_sha256_snapshot =",
        "decision.decided_by is distinct from job.requested_by",
        "decision.decided_by is distinct from job.assigned_to",
        "signal.product_id = product_id_value",
        "signal.platform = platform_value",
        "signal.model = model_value",
        "observation_count_value < 6",
        "weakness.average_score < 78",
        "limit 3",
        "limit 60",
    ):
        assert token in MIGRATION


def test_quality_guard_learning_never_reuses_free_form_review_copy() -> None:
    policy_body = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_generation_learning_policy"
        ) :
        MIGRATION.rindex("commit;")
    ]
    for forbidden in (
        "decision.comment",
        "review.result -> 'findings'",
        "review.result -> 'recommendations'",
        "review.result -> 'strengths'",
        "review.result ->> 'summary'",
        "caption_text",
        "script_text",
    ):
        assert forbidden not in policy_body
    for token in (
        "'structured_score_dimensions_only', true",
        "'raw_review_copy_never_learned', true",
        "'quality_guard_count_bounded', true",
        "'independent_human_decision_required', true",
    ):
        assert token in policy_body


def test_compiler_applies_allowlisted_hook_and_recurring_quality_guards() -> None:
    result = _run_handoff(
        """
        const policy = {
          version: "generation-learning-v4",
          applied: true,
          confidence: "high",
          selection_mode: "performance",
          evidence_count: 18,
          preferred_angle: "demonstration",
          preferred_hook_patterns: ["demonstration"],
          quality_guard_codes: [
            "product_fidelity",
            "technical_stability",
            "<script>raw-review-copy</script>"
          ],
          quality_guard_evidence_count: 12,
          quality_guard_confidence: "high",
          policy_hash: "f".repeat(64),
        };
        const normalized = subject.normalizeGenerationLearningPolicy(policy);
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "Точный товар",
          sku: "SKU-GUARD-1",
          learningPolicy: policy,
        });
        return {
          ready: compiled.ready,
          guardCodes: normalized?.qualityGuardCodes,
          guardEvidence: normalized?.qualityGuardEvidenceCount,
          hook: compiled.prompt.includes(
            "Структурный hook: одно простое действие с товаром"
          ),
          fidelity: compiled.prompt.includes("упаковка без морфинга"),
          stability: compiled.prompt.includes(
            "без чёрных кадров, скачков и мерцания"
          ),
          productLock: compiled.prompt.includes(
            "Сохрани форму, цвет, упаковку, этикетку и пропорции"
          ),
          rawCopyRejected: !compiled.prompt.includes("raw-review-copy"),
        };
        """
    )
    assert result == {
        "ready": True,
        "guardCodes": ["product_fidelity", "technical_stability"],
        "guardEvidence": 12,
        "hook": True,
        "fidelity": True,
        "stability": True,
        "productLock": True,
        "rawCopyRejected": True,
    }


def test_learned_guards_fit_every_mode_at_maximum_product_identity_size() -> None:
    result = _run_handoff(
        """
        const policy = {
          version: "generation-learning-v4",
          applied: true,
          confidence: "high",
          selection_mode: "quality",
          evidence_count: 12,
          preferred_angle: "curiosity_gap",
          preferred_hook_patterns: ["comparison"],
          quality_guard_codes: [
            "product_fidelity",
            "technical_stability",
            "visual_quality"
          ],
          quality_guard_evidence_count: 12,
          quality_guard_confidence: "high",
          policy_hash: "e".repeat(64),
        };
        const modes = ["real_photo", "real_gen4", "real_seedance"];
        const results = modes.map((mode) => subject.compileSafeGenerationBrief({
          mode,
          productName: "Т".repeat(180),
          sku: "S".repeat(120),
          learningPolicy: policy,
        }));
        return {
          ready: results.every((item) => item.ready),
          lengths: results.map((item) => item.prompt.length),
          allGuardsApplied: results.every((item) =>
            item.prompt.includes("QA:")
            && item.prompt.includes("Обучен")
          ),
          maximum: subject.CONTENT_GENERATION_PROMPT_LIMIT,
        };
        """
    )
    assert result["ready"] is True
    assert all(0 < length <= result["maximum"] for length in result["lengths"])
    assert result["allGuardsApplied"] is True


def test_applied_learning_cannot_be_silently_dropped_from_long_auto_prompt() -> None:
    assert "required(generationLearningDirection(" in HANDOFF
    assert HANDOFF.count("required(learningDirection)") == 3
    assert "optional(generationLearningDirection(" not in HANDOFF

    for token in (
        "generationQualityGuardLabel",
        "generationHookPatternLabel",
        "Следующее авто-ТЗ уже включает",
        "QA-усиления${strongerGuardCount",
        "Тексты обещаний, права и параметры запуска не обучаются",
    ):
        assert token in APP

    paid_start = EDGE[
        EDGE.index("const startPayload = readStartPayload(body)") :
        EDGE.index("const { data: startData, error: startError }")
    ]
    assert '"creator_generation_learning_policy"' in paid_start
    assert '"generation_learning_policy_stale"' in paid_start
