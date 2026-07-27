from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web/app"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270003_generated_video_review_autopilot.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generated_video_review_autopilot_test.sql"
).read_text(encoding="utf-8")
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")
GENERATION_EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")


def test_server_starts_exact_video_review_without_transcription() -> None:
    start_rpc = MIGRATION[
        MIGRATION.index("public.creator_start_generated_video_review") :
        MIGRATION.index(
            "public.creator_approve_generated_video_review_with_context"
        )
    ]
    for token in (
        "'generated-video-review:' || job_row.id::text",
        "media_row.mime_type <> 'video/mp4'",
        "media_row.metadata ->> 'kind' <> 'generated_video'",
        "evidence_row.source_sha256_snapshot",
        "evidence_row.manifest_hash is null",
        "evidence_row.frame_count <> 5",
        "'technical_metrics', evidence_row.technical_metrics",
        "'platform', platform_value",
        "'product_category', category_value",
        "'script_text', script_value",
        "'external_ai_processing_confirmed', true",
        "'transcription_requested', false",
    ):
        assert token in start_rpc
    assert "creator-generate" not in start_rpc
    assert "'external_ai_processing_basis', 'synthetic_generated_media'" in MIGRATION
    assert 'run.input.transcription_requested === false' in (
        ROOT / "supabase/functions/creator-content-review/index.ts"
    ).read_text(encoding="utf-8")


def test_paid_generation_binds_product_category_before_provider_request() -> None:
    for token in (
        "creator_start_real_generation_pre_review_category_v1",
        "paid_generation_product_category_invalid",
        "'content_review_category', requested_category_value",
        "'generation_product_category_bound'",
        "'{job,product_category}'",
    ):
        assert token in MIGRATION
    for token in (
        "product_category:",
        '"product_category"',
        "productCategories.has(value.product_category)",
    ):
        assert token in GENERATION_EDGE
    for token in (
        'name="product_category"',
        "Категория товара для QA",
        "product_category: productCategory",
        "paid_generation_product_category_invalid",
    ):
        assert token in APP or token in API


def test_context_approval_reuses_analysis_and_keeps_video_blockers() -> None:
    approval_rpc = MIGRATION[
        MIGRATION.index(
            "public.creator_approve_generated_video_review_with_context"
        ) :
    ]
    for token in (
        "generated_video_context_result(",
        "generated_video_context_non_context_blockers",
        "generated_video_independent_review_required",
        "source_review_row.evidence_set_id",
        "evidence_row.status <> 'consumed'",
        "product_row.metadata ->> 'content_review_category'",
        "source_review_row.input ->> 'product_category'",
        "'provider_analysis_reused', true",
        "'external_ai_invoked', false",
        "'transcription_requested', false",
        "insert into content_factory.content_review_context_amendments",
        "public.creator_decide_content_review(",
    ):
        assert token in approval_rpc
    for token in (
        "generated_video_context_resolvable_codes()",
        "'ACCESSIBILITY.CAPTIONS'",
    ):
        assert token in MIGRATION
    assert approval_rpc.index(
        "insert into content_factory.content_review_context_amendments"
    ) < approval_rpc.index("public.creator_decide_content_review(")


def test_pgtap_covers_context_filter_and_rpc_security() -> None:
    for token in (
        "generated-video start RPC is available",
        "generated-video context approval RPC is available",
        "video context removes only deterministic publication blockers",
        "actual video-content blocker survives context amendment",
        "transcription remains an explicit opt-in outside autopilot",
        "public generation gate binds product category before returning",
    ):
        assert token in PGTAP


def test_portal_exposes_one_action_qa_and_video_context_approval() -> None:
    for token in (
        'data-action="start-generated-video-review"',
        "Запустить AI-проверку",
        "startGeneratedVideoReview",
        "transcription_requested !== false",
        "approveGeneratedVideoReviewWithContext",
        "generatedMediaContextCanApprove",
        "generatedMediaPostContextRequiredRiskCodes",
        "generated-video-context-v1",
        '"release_captions_confirmed"',
    ):
        assert token in APP or token in API or token in VIEW


def test_generated_video_context_form_is_safe_and_does_not_offer_rerun() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://example.test/review" }} }};
const subject = await import({json.dumps(module_url)});
const raw = {{
  id: "11111111-1111-4111-8111-111111111111",
  status: "completed",
  media: {{
    id: "22222222-2222-4222-8222-222222222222",
    mime_type: "video/mp4",
    metadata: {{
      kind: "generated_video",
      model: "seedance2_fast",
      spoken_script: "Это точная реплика героя."
    }},
    status: "ready",
    signed_url: "https://example.test/result.mp4"
  }},
  input: {{
    media_id: "22222222-2222-4222-8222-222222222222",
    platform: "telegram",
    content_kind: "advertising",
    product_category: "other",
    product_category_verified: true,
    product_category_source: "product_metadata",
    generation_job_id: "33333333-3333-4333-8333-333333333333",
    script_text: "Это точная реплика героя.",
    ai_generated: true,
    external_ai_processing_confirmed: false
  }},
  result: {{
    overall_score: 84,
    scores: {{ technical: 87, visual_quality: 82 }},
    compliance_status: "block",
    blockers_count: 2,
    warnings_count: 2,
    strengths: ["Ролик читается"],
    findings: [
      {{ code: "AD.MARKING.ERID", category: "legal", severity: "blocker", title: "Нет ERID", detail: "Нет ERID", action: "Добавить" }},
      {{ code: "RIGHTS.MEDIA", category: "rights", severity: "blocker", title: "Нет прав", detail: "Нет прав", action: "Подтвердить" }},
      {{ code: "ACCESSIBILITY.CAPTIONS", category: "accessibility", severity: "medium", title: "Субтитры", detail: "Проверить", action: "Проверить" }},
      {{ code: "PLATFORM.CURRENT_STATUS_REVIEW", category: "platform", severity: "high", title: "Площадка", detail: "Нужен человек", action: "Проверить", human_review_required: true }}
    ],
    recommendations: [
      {{ code: "FIX.AD.MARKING.ERID", category: "compliance", priority: "high", title: "ERID", detail: "Добавить", action: "Добавить" }}
    ],
    comparison: {{ previous_score: null, delta: null, summary: "Первая" }}
  }}
}};
const run = subject.normalizeContentReviewRun(raw);
if (!subject.generatedMediaContextCanApprove(run)) throw new Error("context unavailable");
const required = subject.generatedMediaPostContextRequiredRiskCodes(run);
if (JSON.stringify(required) !== JSON.stringify(["PLATFORM.CURRENT_STATUS_REVIEW"])) {{
  throw new Error(JSON.stringify(required));
}}
const mediumOnly = {{
  ...run,
  result: {{
    ...run.result,
    complianceStatus: "human_review",
    blockersCount: 0,
    findings: [
      {{ code: "VIDEO.MINOR_WARNING", severity: "medium", humanReviewRequired: false }}
    ]
  }}
}};
if (subject.generatedMediaPostContextRequiredRiskCodes(mediumOnly).length !== 0) {{
  throw new Error("video medium-only warning must not create an unknown synthetic risk code");
}}
const html = subject.contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [raw] }},
  currentRun: raw,
  canDecide: true
}});
for (const token of [
  'value="approve_with_context"',
  "MP4, звук и evidence повторно не отправляются",
  'name="release_captions_confirmed"',
  'value="PLATFORM.CURRENT_STATUS_REVIEW"'
]) {{
  if (!html.includes(token)) throw new Error(token);
}}
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
