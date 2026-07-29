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
            "media_ids": ["media-a", "media-a", "media-b"],
            "real_spend_confirmation": "I_CONFIRM_PAID_GENERATION",
        },
        ensure_ascii=False,
    )
    result = _evaluate(
        f"subject.buildGenerationFormDraft({value}, {{"
        "now: 1000, context: {handoffDraftId: 'draft-1'}"
        "})"
    )
    assert result["version"] == 1
    assert result["updatedAt"] == 1000
    assert result["context"]["handoffDraftId"] == "draft-1"
    assert result["values"]["sku"] == "WB-42"
    assert result["values"]["duration_seconds"] == "15"
    assert result["values"]["media_ids"] == ["media-a"]
    assert "real_spend_confirmation" not in result
    assert "real_spend_confirmation" not in result["values"]


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
        context: {handoffDraftId: "draft-1", handoffResearchId: "research-1"},
      });
      const options = {
        now: 11_000,
        maxAgeMs: 5_000,
        activeContext: {
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
          {...options, activeContext: {handoffDraftId: "draft-2"}},
        ),
        subject.normalizeGenerationFormDraft(
          {...draft, version: 99},
          options,
        ),
      ];
    })()
    """
    assert _evaluate(expression) == [True, None, None, None]


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
    assert "generation-form-draft.js?v=20260728.2" in APP
    assert "app.js?v=20260728.13" in INDEX


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
