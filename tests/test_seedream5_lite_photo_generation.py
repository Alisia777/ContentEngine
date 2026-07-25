from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240007_seedream5_lite_photo_generation.sql"
).read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
WORKER = (
    ROOT / "supabase/functions/creator-background-worker/index.ts"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_database_adds_one_fixed_price_2k_photo_sku() -> None:
    for token in (
        "'seedream5_lite'",
        "'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04'",
        "'ratio', '2048:2048'",
        "'estimated_cost_minor', 4",
        "'estimated_credits', 4",
        "'duration_seconds', 0",
        "'audio', false",
        "'format', '1:1'",
    ):
        assert token in MIGRATION


def test_photo_constraints_can_resume_after_legacy_partial_application() -> None:
    for constraint_name in (
        "generation_batches_model_v2_check",
        "generation_batches_sku_contract_v2_check",
        "generation_jobs_spend_contract_v2_check",
    ):
        drop = f"drop constraint if exists {constraint_name}"
        add = f"add constraint {constraint_name}"
        assert drop in MIGRATION
        assert add in MIGRATION
        assert MIGRATION.index(drop) < MIGRATION.index(add)


def test_photo_start_requires_one_owned_rights_confirmed_product_image() -> None:
    photo_start = MIGRATION[
        MIGRATION.index("creator_start_seedream5_lite_photo"):
        MIGRATION.index("-- Compose the photo command")
    ]
    for token in (
        "jsonb_array_length(media_ids) <> 1",
        "'product_photo', 'packshot'",
        "media_row.mime_type not in ('image/jpeg', 'image/png', 'image/webp')",
        "media_row.metadata -> 'rights_confirmed' is distinct from 'true'::jsonb",
        "media_row.product_id is distinct from product_id_value",
        "certification.module_code = 'operator_final_exam'",
    ):
        assert token in photo_start


def test_photo_uses_campaign_budget_idempotency_and_no_auto_retry() -> None:
    for token in (
        "content_factory.generation_campaign_id",
        "creator_start_real_generation_campaign_v1",
        "begin_command(",
        "finish_command(",
        "generation_jobs_spend_contract_v2_check",
        "real_generation_spend_confirmation_required",
    ):
        assert token in MIGRATION
    provider_create = EDGE[EDGE.index("let createResponse"):EDGE.index(
        "let createdValue"
    )]
    assert provider_create.count("fetchWithTimeout(") == 1


def test_edge_calls_runway_text_to_image_with_one_reference_and_png() -> None:
    for token in (
        'model: "seedream5_lite"',
        "duration_seconds: 0",
        'format: "1:1"',
        '"RUNWAY_SEEDREAM5_LITE_2K_USD_0.04"',
        'const SEEDREAM5_LITE_RATIO = "2048:2048"',
        '`${RUNWAY_API_ORIGIN}/v1/text_to_image`',
        'outputFormat: "png"',
        "outputCount: 1",
        "referenceImages: [{ uri: signedInputUrl }]",
        'const outputMimeType = photoOutput ? "image/png" : "video/mp4"',
        "photoOutput ? !isPng(outputBytes) : !isMp4(outputBytes)",
        "view.getUint32(0, false) === 2_048",
        "view.getUint32(4, false) === 2_048",
        "system_complete_seedream5_lite_photo",
    ):
        assert token in EDGE


def test_photo_success_registers_private_generated_image_and_review_task() -> None:
    success = MIGRATION[MIGRATION.index(
        "public.system_complete_seedream5_lite_photo"
    ):MIGRATION.index("-- Failed output cleanup")]
    for token in (
        "output_object_name_value !~",
        "'image/png'",
        "'kind', 'generated_image'",
        "'content_kind', 'photo'",
        "'content_review_status', 'queued'",
        "'review_required', true",
        "set status = 'succeeded'",
        "set status = 'review'",
        "'real_generation_succeeded'",
    ):
        assert token in success
    assert "insert into content_factory.content_review_runs" in success
    assert "'ai_generated', true" in success
    assert "'external_ai_processing_confirmed', true" in success


def test_png_storage_cleanup_is_fail_closed() -> None:
    assert "'[.](mp4|png)$'" in MIGRATION
    assert 'endsWith(`/${value.generation_job_id}.png`)' in WORKER
    assert "generation_storage_cleanup_object_name_v2_check" in MIGRATION


def test_portal_exposes_photo_mode_with_dynamic_copy_and_download() -> None:
    for token in (
        'const REAL_PHOTO_MODE = "real_photo"',
        'contentKind: "photo"',
        'model: "seedream5_lite"',
        'label: "Фото товара · квадрат 2K · ≈ $0.04"',
        'Скачать ${details.photo ? "PNG" : "MP4"}',
        '<img src="${escapeHtml(previewUrl)}"',
        'photo ? "png" : "mp4"',
        "Платное фото готово",
    ):
        assert token in APP
    for token in (
        "seedream5_lite: Object.freeze",
        'format: "1:1"',
        '"RUNWAY_SEEDREAM5_LITE_2K_USD_0.04"',
    ):
        assert token in ADAPTER
