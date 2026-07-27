import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web/app"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607250002_generated_photo_review_release.sql"
).read_text(encoding="utf-8")
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")


def test_generated_photo_review_is_bound_to_the_paid_output() -> None:
    for token in (
        "generated_image_review_input_guard",
        "enforce_generated_image_review_input",
        "media_row.metadata ->> 'kind' is distinct from 'generated_image'",
        "job_row.input ->> 'model' <> 'seedream5_lite'",
        "job_row.output ->> 'output_media_id'",
        "'content_kind', 'advertising'",
        "'ai_generated', true",
        "'generation_job_id', job_row.id",
        "'product_category_source'",
        "'product_metadata'",
        "new.request_hash := content_factory_private.json_hash(new.input)",
    ):
        assert token in MIGRATION


def test_generated_photo_approval_requires_independent_safe_review() -> None:
    release = MIGRATION[MIGRATION.index(
        "content_factory_private.release_generated_image_review()"
    ):MIGRATION.index(
        "revoke all on function\n"
        "  content_factory_private.release_generated_image_review()"
    )]
    for token in (
        "generated_image_independent_review_required",
        "new.media_watched_confirmed",
        "'ad_label_confirmed'",
        "'ord_confirmed'",
        "'advertiser_name'",
        "'erid'",
        "'rights_confirmed'",
        "'claims_verified'",
        "'ai_disclosure_confirmed'",
        "'mandatory_warning_confirmed'",
        "'rkn_registered'",
        "'content_review_blockers_unresolved'",
    ):
        assert token in release


def test_generated_photo_approval_finishes_task_and_creates_placement() -> None:
    for token in (
        "generated_image_review_release",
        "after insert on content_factory.content_review_decisions",
        "set status = 'done'",
        "'content_review_decision_id', new.id",
        "'Approved generated photo review: '",
        "'Опубликовать одобренное фото — '",
        "'content_kind', 'photo'",
        "insert into content_factory.placements",
        "'generated_photo_released'",
    ):
        assert token in MIGRATION
    assert "media_row.metadata ->> 'kind' not in (" in MIGRATION
    assert "'generated_video', 'generated_image'" in MIGRATION


def test_portal_blocks_unsafe_auto_review_and_uses_image_specific_copy() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://example.test/review" }} }};
const {{
  contentReviewWorkspaceMarkup,
  generatedImageApprovalContextReady,
  normalizeContentReviewRun
}} = await import({json.dumps(module_url)});

const base = {{
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
    platform: "tiktok",
    content_kind: "advertising",
    product_category: "food",
    generation_job_id: "33333333-3333-4333-8333-333333333333",
    ai_generated: true,
    external_ai_processing_confirmed: true
  }},
  result: {{
    overall_score: 91,
    compliance_status: "pass",
    blockers_count: 0,
    warnings_count: 0,
    findings: [],
    recommendations: []
  }}
}};
const unsafe = normalizeContentReviewRun(base);
if (generatedImageApprovalContextReady(unsafe)) throw new Error("unsafe auto review passed");
const unsafeHtml = contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [base] }},
  currentRun: base,
  canDecide: true
}});
if (unsafeHtml.includes('name="decision" value="approved"')) throw new Error("unsafe approval shown");
if (!unsafeHtml.includes('value="approve_with_context"')) throw new Error("context approval missing");
if (!unsafeHtml.includes("без повторного AI")) throw new Error("recovery guidance missing");

const safeRaw = {{
  ...base,
  input: {{
    ...base.input,
    product_category_verified: true,
    product_category_source: "product_metadata",
    ad_label_confirmed: true,
    ord_confirmed: true,
    advertiser_name: "ООО Альтея",
    erid: "2Vtzqexample",
    rights_confirmed: true,
    claims_verified: true
  }}
}};
const safe = normalizeContentReviewRun(safeRaw);
if (!generatedImageApprovalContextReady(safe)) throw new Error("safe review blocked");
const safeHtml = contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [safeRaw] }},
  currentRun: safeRaw,
  canDecide: true
}});
if (!safeHtml.includes('name="decision" value="approved"')) throw new Error("safe approval missing");
if (!safeHtml.includes("осмотрел(а) именно этот защищённый PNG")) throw new Error("image confirmation missing");
if (safeHtml.includes("проверил(а) звук и субтитры")) throw new Error("video copy leaked into image review");
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


def test_portal_has_recoverable_generated_photo_errors() -> None:
    for code in (
        "generated_image_review_task_invalid",
        "generated_image_job_invalid",
        "generated_image_platform_invalid",
        "generated_image_product_invalid",
        "generated_image_review_requester_invalid",
        "generated_image_independent_review_required",
        "generated_image_review_context_invalid",
    ):
        assert code in API
    assert "generatedImageApprovalContextReady" in VIEW
    assert 'data-release-context-ready="${generatedImageContextReady ? "true" : "false"}"' in VIEW
