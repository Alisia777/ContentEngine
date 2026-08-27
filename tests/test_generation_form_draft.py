from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web/app"
MODULE = APP_DIR / "generation-form-draft.js"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation draft contracts")
    script = (
        f"const subject = await import({json.dumps(MODULE.resolve().as_uri())});\n"
        f"const result = {expression};\n"
        "process.stdout.write(JSON.stringify(result));\n"
    )
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_generation_draft_is_bounded_and_never_contains_spend_confirmation() -> None:
    value = json.dumps(
        {
            "generation_mode": "real_seedance",
            "duration_seconds": "15",
            "campaign_id": "11111111-1111-4111-8111-111111111111",
            "campaign_selection_required": True,
            "sku": " WB-42 ",
            "product_name": " Точный товар ",
            "product_category": "cosmetics",
            "platform": "tiktok",
            "destination_ref": "@exact",
            "assignee_id": "22222222-2222-4222-8222-222222222222",
            "payout_rub": "150",
            "count": 1,
            "format": "9:16",
            "brief": "Безопасное ТЗ",
            "scenario_intent": "Блогер готовит лосось в пароварке",
            "generation_reference_url": "https://www.youtube.com/shorts/RIJ_v--Yncw",
            "generation_reference_mechanics": "Show the result, demonstrate one action, then reveal the result again.",
            "generation_reference_source_access_confirmed": True,
            "generation_reference_transformative_use_confirmed": True,
            "media_ids": ["media-a", "media-a", "media-b"],
            "primary_media_id": "media-b",
            "real_spend_confirmation": "I_CONFIRM_PAID_GENERATION",
        },
        ensure_ascii=False,
    )
    result = _evaluate(
        f"subject.buildGenerationFormDraft({value}, {{"
        "now: 1000, context: {projectId: '11111111-1111-4111-8111-111111111111', handoffDraftId: 'draft-1'}"
        "})"
    )
    assert result["version"] == 4
    assert result["updatedAt"] == 1000
    assert result["context"]["projectId"] == "11111111-1111-4111-8111-111111111111"
    assert result["context"]["handoffDraftId"] == "draft-1"
    assert result["values"]["sku"] == "WB-42"
    assert result["values"]["duration_seconds"] == "15"
    assert result["values"]["campaign_selection_required"] is True
    assert result["values"]["media_ids"] == ["media-a", "media-b"]
    assert result["values"]["primary_media_id"] == "media-b"
    assert result["values"]["scenario_intent"] == "Блогер готовит лосось в пароварке"
    assert result["values"]["generation_reference_url"].endswith("RIJ_v--Yncw")
    assert result["values"]["generation_reference_mechanics"].startswith("Show the result")
    assert result["values"]["generation_reference_source_access_confirmed"] is True
    assert result["values"]["generation_reference_transformative_use_confirmed"] is True
    assert "real_spend_confirmation" not in result
    assert "real_spend_confirmation" not in result["values"]


def test_strategy_draft_keeps_role_ids_but_never_persists_human_consent() -> None:
    value = json.dumps(
        {
            "generation_mode": "real_seedance",
            "generation_strategy_id": "viral_product_swap",
            "generation_strategy_version": "2026-08-14.v1",
            "generation_strategy_recipe_version": "2026-06",
            "generation_strategy_source_basis": "exact_source_video",
            "generation_strategy_duration_seconds": "10",
            "generation_strategy_resolution": "1080p",
            "generation_strategy_audio": "true",
            "generation_strategy_source_video_id":
                "11111111-1111-4111-8111-111111111111",
            "generation_strategy_original_product_media_id":
                "22222222-2222-4222-8222-222222222222",
            "generation_strategy_attestations": {
                "source_media_rights_confirmed": True,
                "transformative_use_confirmed": True,
                "not valid": True,
            },
            "provider": "client-must-not-persist-provider",
            "recipe": "client-must-not-persist-recipe",
            "estimated_cost_minor": 999999,
            "signed_url": "https://example.invalid/private",
        }
    )
    result = _evaluate(
        f"subject.buildGenerationFormDraft({value}, {{"
        "now: 1000, context: {projectId: '33333333-3333-4333-8333-333333333333'}"
        "})"
    )
    strategy = result["values"]
    assert strategy["generation_strategy_id"] == "viral_product_swap"
    assert strategy["generation_strategy_version"] == "2026-08-14.v1"
    assert strategy["generation_strategy_recipe_version"] == "2026-06"
    assert strategy["generation_strategy_source_basis"] == "exact_source_video"
    assert strategy["generation_strategy_duration_seconds"] == 10
    assert strategy["generation_strategy_resolution"] == "1080p"
    assert strategy["generation_strategy_audio"] == "true"
    assert strategy["generation_strategy_attestations"] == {}
    for forbidden in ("signed_url", "estimated_cost_minor", "provider", "recipe"):
        assert forbidden not in strategy


def test_generation_draft_fails_closed_for_age_version_and_context() -> None:
    expression = """
    (() => {
      const draft = subject.buildGenerationFormDraft({
        generation_mode: "real_photo",
        product_category: "other",
        platform: "wildberries",
        media_ids: ["media-a"],
      }, {
        now: 10_000,
        context: {
          projectId: "11111111-1111-4111-8111-111111111111",
          handoffDraftId: "draft-1",
          handoffResearchId: "research-1",
        },
      });
      const options = {
        now: 11_000,
        maxAgeMs: 5_000,
        activeContext: {
          projectId: "11111111-1111-4111-8111-111111111111",
          handoffDraftId: "draft-1",
          handoffResearchId: "research-1",
        },
      };
      return [
        Boolean(subject.normalizeGenerationFormDraft(draft, options)),
        subject.normalizeGenerationFormDraft(
          draft,
          {...options, now: 20_000},
        ),
        subject.normalizeGenerationFormDraft(
          draft,
          {...options, activeContext: {
            projectId: "11111111-1111-4111-8111-111111111111",
            handoffDraftId: "draft-2",
          }},
        ),
        subject.normalizeGenerationFormDraft(
          {...draft, version: 99},
          options,
        ),
        subject.normalizeGenerationFormDraft(
          draft,
          {...options, activeContext: {
            projectId: "22222222-2222-4222-8222-222222222222",
            handoffDraftId: "draft-1",
            handoffResearchId: "research-1",
          }},
        ),
      ];
    })()
    """
    assert _evaluate(expression) == [True, None, None, None, None]


def test_portal_restores_generation_draft_but_requires_fresh_spend_confirmation() -> None:
    for token in (
        "generationFormDraftStorageKey",
        "normalizeGenerationFormDraft",
        "window.sessionStorage",
        "restoreGenerationFormDraft(generationForm)",
        "form.elements.real_spend_confirmation.checked = false",
        "Подтверждение оплаты никогда не сохраняется",
        "persistGenerationFormDraft(form, { manual: true })",
    ):
        assert token in APP
    assert "generation-form-draft.js?v=20260826.rebuild-clean.28" in APP
    assert "form.dataset.generationScenarioIntent" in APP
    assert "app.js?v=20260826.rebuild-clean.28" in INDEX


def test_generated_video_review_starts_automatically_after_durable_evidence() -> None:
    for token in (
        "startGeneratedVideoReviewFromEvidence",
        "resumeGeneratedVideoReviewAutopilot",
        "window.queueMicrotask(resumeGeneratedVideoReviewAutopilot)",
        "automatic: true",
        "entry.reviewAutostartApproved === true",
        "raw?.transcription_requested !== false",
        "reviewAutostartAttempted",
        "AI-проверка запускается автоматически; транскрипция выключена.",
        "обязательная AI-проверка запустится автоматически",
        "Это старый запуск без сохранённого согласия",
    ):
        assert token in APP
    assert APP.count("await startGeneratedVideoReviewFromEvidence(mediaId)") == 1


def test_video_review_autostart_consent_is_bound_to_the_new_job_and_session_fallback() -> None:
    for token in (
        "generationReviewAutostartStorageKey",
        "GENERATION_REVIEW_AUTOSTART_MAX_JOBS",
        "window.sessionStorage",
        "registerGenerationReviewAutostart(jobId)",
        "generationReviewAutostartApproved(job)",
        "job?.review_autostart_confirmed",
        "generated-video-qa-autostart-v1",
        "consumeGenerationReviewAutostart(previous.jobId)",
    ):
        assert token in APP
    submit = APP[
        APP.index("async function submitRealGeneration(form") :
        APP.index("async function submitMockBatch")
    ]
    assert submit.index(
        "registerGenerationReviewAutostart(jobId)"
    ) < submit.index("applyRealGenerationResult(jobId")
