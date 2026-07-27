from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web/app"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270002_generated_photo_review_context_approval.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generated_photo_context_approval_test.sql"
).read_text(encoding="utf-8")
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")


def test_database_reuses_visual_result_and_records_immutable_context() -> None:
    for token in (
        "content_review_context_amendments",
        "generated_photo_context_resolvable_codes()",
        "generated_photo_context_result(",
        "validate_content_review_result(",
        "'provider_analysis_reused', true",
        "'external_ai_invoked', false",
        "'generated-photo-context-v1'",
        "reject_content_review_context_amendment_mutation",
    ):
        assert token in MIGRATION
    assert "creator-content-review" not in MIGRATION
    assert "creator-generate" not in MIGRATION


def test_specialized_approval_is_exact_independent_and_fail_closed() -> None:
    rpc = MIGRATION[MIGRATION.index(
        "public.creator_approve_generated_photo_review_with_context"
    ) :]
    for token in (
        "source_review_row.idempotency_key",
        "'generated-photo-review:' || job_row.id::text",
        "source_review_row.requested_by is distinct from job_row.requested_by",
        "media_row.metadata ->> 'kind' <> 'generated_image'",
        "media_row.mime_type <> 'image/png'",
        "job_row.input ->> 'model' <> 'seedream5_lite'",
        "job_row.output ->> 'output_media_id'",
        "generated_image_independent_review_required",
        "generated_photo_context_non_context_blockers",
        "content_review_risk_acknowledgement_required",
        "insert into content_factory.content_review_runs",
        "insert into content_factory.content_review_context_amendments",
        "insert into content_factory.content_review_decisions",
        "media_row.id,\n    user_id,",
    ):
        assert token in rpc
    assert rpc.index(
        "insert into content_factory.content_review_context_amendments"
    ) < rpc.index("insert into content_factory.content_review_decisions")


def test_pgtap_proves_context_cannot_hide_content_blockers() -> None:
    for token in (
        "verified context removes only its deterministic blockers",
        "remaining platform risk still requires a human",
        "a claim blocker in the actual PNG is never hidden by context",
        "non-context content blocker remains exact in the derived result",
    ):
        assert token in PGTAP


def test_portal_offers_one_step_context_approval_without_new_ai() -> None:
    for token in (
        "generatedImageContextCanApprove",
        "generatedImagePostContextRequiredRiskCodes",
        'value="approve_with_context"',
        "без повторного AI",
        "approveGeneratedPhotoReviewWithContext",
        "external_ai_invoked: contextApproval ? false : null",
        "Для одобрения заполните реквизиты",
    ):
        assert token in VIEW or token in APP or token in API
    assert "запустите новую проверку — портал свяжет" not in VIEW
    for field in (
        'name="release_advertiser_name"',
        'name="release_erid"',
        'name="release_people_present"',
    ):
        assert f"{field} required" not in VIEW


def test_context_only_blockers_render_safe_approval_form() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://example.test/review" }} }};
const subject = await import({json.dumps(module_url)});
const raw = {{
  id: "11111111-1111-4111-8111-111111111111",
  status: "completed",
  media: {{
    id: "22222222-2222-4222-8222-222222222222",
    mime_type: "image/png",
    metadata: {{ kind: "generated_image", original_filename: "result.png" }},
    status: "ready",
    signed_url: "https://example.test/result.png"
  }},
  input: {{
    media_id: "22222222-2222-4222-8222-222222222222",
    platform: "telegram",
    content_kind: "advertising",
    product_category: "other",
    generation_job_id: "33333333-3333-4333-8333-333333333333",
    ai_generated: true,
    external_ai_processing_confirmed: true
  }},
  result: {{
    overall_score: 86,
    scores: {{ technical: 88, product_fidelity: 84 }},
    compliance_status: "block",
    blockers_count: 2,
    warnings_count: 1,
    strengths: ["Товар читается"],
    findings: [
      {{ code: "AD.MARKING.ERID", category: "legal", severity: "blocker", title: "Нет ERID", detail: "Нет ERID", action: "Добавить ERID" }},
      {{ code: "RIGHTS.MEDIA", category: "rights", severity: "blocker", title: "Нет прав", detail: "Нет прав", action: "Подтвердить права" }},
      {{ code: "PLATFORM.CURRENT_STATUS_REVIEW", category: "platform", severity: "high", title: "Проверить площадку", detail: "Нужен человек", action: "Проверить", human_review_required: true }}
    ],
    recommendations: [
      {{ code: "FIX.AD.MARKING.ERID", category: "compliance", priority: "high", title: "ERID", detail: "Добавить", action: "Добавить" }}
    ],
    comparison: {{ previous_score: null, delta: null, summary: "Первая" }}
  }}
}};
const run = subject.normalizeContentReviewRun(raw);
if (!subject.generatedImageContextCanApprove(run)) throw new Error("context path unavailable");
const required = subject.generatedImagePostContextRequiredRiskCodes(run);
if (JSON.stringify(required) !== JSON.stringify(["PLATFORM.CURRENT_STATUS_REVIEW"])) throw new Error(JSON.stringify(required));
const html = subject.contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [raw] }},
  currentRun: raw,
  canDecide: true
}});
if (!html.includes('value="approve_with_context"')) throw new Error("approval missing");
if (!html.includes("Изображение повторно не отправляется внешнему AI")) throw new Error("privacy copy missing");
if (!html.includes('name="release_erid"')) throw new Error("ERID input missing");
if (!html.includes('value="PLATFORM.CURRENT_STATUS_REVIEW"')) throw new Error("risk acknowledgement missing");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout
