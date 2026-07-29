from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607290002_multi_reference_category_generation.sql"
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
    for token in (
        "товар целиком стоит на устойчивой столешнице",
        "упаковка БАДа остаётся на столе",
        "электроника стоит на столе или установлена на рабочем месте",
        "cold start — товар на устойчивой поверхности",
        "generation_product_interaction_invalid",
    ):
        assert token in MIGRATION
        assert token in EDGE or token == "generation_product_interaction_invalid"
    assert "productInteractionRequirement(" in EDGE
    assert "payload.product_category" in EDGE


def test_supported_models_use_reference_bundle_without_changing_gen4_contract() -> None:
    assert "referenceImages: validReferenceUrls.map" in EDGE
    assert 'position: index === 0 ? "first" : "reference"' in EDGE
    assert "promptImage: signedInputUrl" in EDGE
    assert "Promise.all(" in EDGE
