from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607290002_multi_reference_category_generation.sql"
).read_text(encoding="utf-8")
PROMPT_CONTRACT_MIGRATION = (
    ROOT
    / "supabase/migrations/202607290004_sync_generation_interaction_prompt_contract.sql"
).read_text(encoding="utf-8")
CATEGORY_DELEGATION_MIGRATION = (
    ROOT
    / "supabase/migrations/202607290005_preserve_category_wrapper_delegation.sql"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_database_binds_one_to_five_ordered_references_to_one_product() -> None:
    for token in (
        "media_count < 1 or media_count > 5",
        "count(distinct item.value)",
        "media.product_id = product_id_value",
        "media.status = 'ready'",
        "'product_photo'",
        "'packshot'",
        "media.metadata -> 'rights_confirmed' = 'true'::jsonb",
        "reference_media_ids is distinct from media_ids",
        "'reference_object_names', reference_object_names",
        "'reference_count', media_count",
        "idempotency_key_conflict",
    ):
        assert token in MIGRATION

    provider_start = MIGRATION.index(
        "creator_start_real_generation_single_reference_v13"
    )
    bundle_validation = MIGRATION.index(
        "exact_product_reference_bundle_mismatch"
    )
    assert provider_start < bundle_validation
    assert "raise exception" in MIGRATION[provider_start:bundle_validation]


def test_client_and_edge_keep_primary_first_and_reject_duplicate_references() -> None:
    for token in (
        'name="primary_media_id"',
        "MAX_REAL_GENERATION_REFERENCES",
        "mixed_product_references",
        "too_many_references",
        "finalIdentity?.mediaIds",
    ):
        assert token in APP
    assert "new Set(batch.media_ids.map(String)).size" in ADAPTER
    assert "new Set(mediaIds).size !== mediaIds.length" in EDGE
    assert "mediaIds.length > 5" in EDGE
    assert "referenceObjectNames[0] !== job.input_object_name" in EDGE


def test_category_and_scale_requirements_are_enforced_on_both_server_layers() -> None:
    assert "generation_product_interaction_requirement" in MIGRATION
    assert "productInteractionRequirement" in EDGE
    legacy_validation = MIGRATION.index(
        "result_value :=\n    public.creator_start_real_generation_single_reference_v13"
    )
    interaction_validation = MIGRATION.index(
        "message = 'generation_product_interaction_invalid'"
    )
    assert legacy_validation < interaction_validation
    assert "if p_payload ? 'product_category'" in MIGRATION
    for token in (
        (
            "Масштаб и действие: товар показан целиком в естественном размере "
            "на устойчивой столешнице; герой взаимодействует с крышкой, "
            "панелью управления и готовым результатом."
        ),
        (
            "Масштаб и действие: упаковка БАДа показана целиком на столе; "
            "в кадре этикетка и форма выпуска без сцены приёма и медицинских "
            "обещаний."
        ),
        (
            "Масштаб и действие: устройство показано целиком на столе или "
            "рабочем месте; камера переходит к интерфейсу, управлению и "
            "видимым разъёмам без выдуманных функций."
        ),
        (
            "Масштаб и действие: товар целиком в естественном масштабе на "
            "устойчивой поверхности; камера показывает только видимые детали."
        ),
    ):
        assert token in PROMPT_CONTRACT_MIGRATION
        assert token in EDGE
    assert "generation_product_interaction_invalid" in MIGRATION
    assert "productInteractionRequirement(" in EDGE
    assert "payload.product_category" in EDGE


def test_supported_models_use_reference_bundle_without_changing_gen4_contract() -> None:
    assert "referenceImages: validReferenceUrls.map" in EDGE
    assert 'position: index === 0 ? "first" : "reference"' in EDGE
    assert "promptImage: signedInputUrl" in EDGE
    assert "Promise.all(" in EDGE


def test_category_wrapper_key_is_not_forwarded_to_legacy_payload_validator() -> None:
    assert "creator_start_real_generation_pre_category_learning_v14" in (
        CATEGORY_DELEGATION_MIGRATION
    )
    assert "p_payload - ''product_category''" in CATEGORY_DELEGATION_MIGRATION
    for code in (
        "real_generation_payload_invalid",
        "generation_product_interaction_invalid",
        "exact_product_reference_bundle_mismatch",
        "generation_learning_category_mismatch",
        "refreshed_courses_required",
    ):
        assert code in EDGE
