from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607300002_content_review_media_context.sql"
).read_text(encoding="utf-8")
VIEW = (ROOT / "web" / "app" / "content-review-view.js").read_text(
    encoding="utf-8"
)
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")


def test_review_catalog_exposes_only_exact_category_and_platform_context() -> None:
    assert "creator_content_review_catalog_without_media_context" in MIGRATION
    assert "repair_next_action" in MIGRATION
    assert "catalog_value -> 'media'" in MIGRATION
    assert "product.metadata ->> 'content_review_category'" in MIGRATION
    assert "product.metadata ->> 'product_category'" in MIGRATION
    assert "generation.input ->> 'platform'" in MIGRATION
    assert "'product_category'" in MIGRATION
    assert "'platform'" in MIGRATION


def test_generated_media_defaults_follow_server_bound_context() -> None:
    assert "raw.product_category" in VIEW
    assert "metadata.content_review_category" in VIEW
    assert "raw.platform" in VIEW
    assert "metadata.generation_job_id" in VIEW
    defaults = APP[
        APP.index("function applyGeneratedMediaReviewDefaults") :
        APP.index("function bindContentReviewDecisionMedia")
    ]
    assert "categoryControl.value = media.productCategory" in defaults
    assert "platformControl.value = media.platform" in defaults
    assert 'form.elements.content_kind.value = "advertising"' in defaults
    assert "form.elements.ai_generated.checked = true" in defaults


def test_generated_video_recovers_a_fresh_url_from_its_exact_job() -> None:
    resolver = APP[
        APP.index("async function resolveGeneratedVideoReviewMedia") :
        APP.index("async function prepareGeneratedVideoTechnicalQa")
    ]
    assert "state.api.realGenerationStatus(source.generationJobId)" in resolver
    assert "outputMediaId === String(source.id" in resolver
    assert "isTrustedGenerationDownload(signedUrl)" in resolver
    assert '["succeeded", "completed"].includes' in resolver
    submit = APP[
        APP.index("async function submitContentReview(") :
        APP.index("async function submitContentReviewDecision(")
    ]
    assert "media = await resolveGeneratedVideoReviewMedia(media)" in submit


def test_missing_advertising_identifiers_block_release_not_quality_scan() -> None:
    submit = APP[
        APP.index("async function submitContentReview(") :
        APP.index("async function submitContentReviewDecision(")
    ]
    assert 'input.content_kind = "advertising"' in submit
    assert "Готовый платный AI-ролик проверяется только как реклама" not in submit
    notice = "Проверка продолжится, но публикация, скорее всего, будет заблокирована"
    assert notice in submit
    assert submit.index(notice) < submit.index("captureContentReviewEvidence")
