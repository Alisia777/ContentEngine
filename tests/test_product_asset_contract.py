from __future__ import annotations

import os
import subprocess
import sys

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")
os.environ["QVF_AUTH_REQUIRED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app import models
from app.assets.asset_storage import ProductAssetStorage
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.engine_audit import EngineAuditScorecardService
from app.main import app
from app.one_video_acceptance import OneVideoAcceptanceService, ProductScenePolicyService
from app.product_asset_contract import ProductAssetTierService, ReferenceRequirementService
from app.product_asset_contract.asset_classifier import normalize_key
from app.product_asset_contract.reference_requirement_service import product_profile


@pytest.fixture(autouse=True)
def reset_contract_db():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


def create_product(*, profile: str = "food_snack", variant_key: str | None = None) -> int:
    with SessionLocal() as db:
        attributes = {"product_profile": profile}
        if variant_key:
            attributes["variant_key"] = variant_key
        product = models.Product(
            sku=f"SKU-{profile}-{variant_key or 'base'}",
            brand="Test Brand",
            title=f"Test {profile} product {variant_key or ''}".strip(),
            description="Product for hard asset contract acceptance.",
            category=profile,
            attributes_json=attributes,
            benefits_json=["fits a real everyday use case"],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product.id


def attach_contract_asset(
    db,
    product_id: int,
    contract_type: str,
    *,
    variant_key: str | None = None,
    primary: bool = False,
    asset_type: str = "product",
):
    storage = ProductAssetStorage(db)
    asset = storage.attach_url(
        product_id,
        url=f"https://example.com/{contract_type}_{variant_key or 'base'}.png",
        asset_type=asset_type,
        manual_label=contract_type.replace("_", " "),
        is_primary_reference=primary,
    )
    return storage.update_asset(
        asset.id,
        review_status="approved",
        is_primary_reference=primary,
        contract_type=contract_type,
        variant_key=variant_key,
    )


def tier(product_id: int):
    with SessionLocal() as db:
        service = ProductAssetTierService(db)
        return service.output(service.evaluate(product_id))


def seed_food_tier_2(db, product_id: int, variant_key: str | None = None):
    attach_contract_asset(db, product_id, "front_packshot", variant_key=variant_key, primary=True, asset_type="packshot")
    attach_contract_asset(db, product_id, "angled_wrapper", variant_key=variant_key)
    attach_contract_asset(db, product_id, "wrapper_in_hand", variant_key=variant_key)


def seed_food_tier_3(db, product_id: int, variant_key: str | None = None):
    seed_food_tier_2(db, product_id, variant_key)
    attach_contract_asset(db, product_id, "whole_unwrapped_product", variant_key=variant_key, asset_type="unwrapped")
    attach_contract_asset(db, product_id, "cutaway_product", variant_key=variant_key, asset_type="cutaway")
    attach_contract_asset(db, product_id, "wrapper_plus_product", variant_key=variant_key)


def test_packshot_only_is_tier_1_and_blocks_wrapper_in_hand():
    product_id = create_product()
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", primary=True, asset_type="packshot")
    output = tier(product_id)
    assert output.current_tier == "tier_1"
    assert output.permissions.wrapper_scene_allowed is False
    assert output.permissions.provider_generated_packaging_allowed is False
    assert "closed_wrapper_reveal" in output.blocked_scenes


def test_style_refs_do_not_unlock_edible_scenes():
    product_id = create_product()
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", primary=True, asset_type="packshot")
        attach_contract_asset(db, product_id, "style_reference", asset_type="style")
        attach_contract_asset(db, product_id, "lifestyle_reference", asset_type="lifestyle")
    output = tier(product_id)
    assert output.current_tier == "tier_1"
    assert output.style_refs_count == 1
    assert output.lifestyle_refs_count == 1
    assert output.edible_refs_count == 0
    assert output.permissions.bite_scene_allowed is False


def test_wrapper_ready_allows_closed_wrapper_but_blocks_bite():
    product_id = create_product()
    with SessionLocal() as db:
        seed_food_tier_2(db, product_id)
    output = tier(product_id)
    assert output.current_tier == "tier_2"
    assert output.permissions.wrapper_scene_allowed is True
    assert output.permissions.provider_generated_packaging_allowed is False
    assert output.permissions.product_compositor_ready is True
    assert output.permissions.bite_scene_allowed is False


def test_edible_ready_allows_cutaway_but_blocks_bite_without_bitten_ref():
    product_id = create_product()
    with SessionLocal() as db:
        seed_food_tier_3(db, product_id)
    output = tier(product_id)
    assert output.current_tier == "tier_3"
    assert output.permissions.cutaway_proof_allowed is True
    assert output.permissions.texture_macro_allowed is True
    assert output.permissions.bite_scene_allowed is False


def test_tier_4_required_for_bite_scene():
    product_id = create_product()
    with SessionLocal() as db:
        seed_food_tier_3(db, product_id)
        for contract_type in ["bitten_product", "product_in_hand", "product_near_mouth", "semi_open_wrapper", "opening_video_reference"]:
            attach_contract_asset(db, product_id, contract_type)
    output = tier(product_id)
    assert output.current_tier == "tier_4"
    assert output.permissions.bite_scene_allowed is True
    assert output.permissions.near_mouth_allowed is True
    assert output.permissions.opening_scene_allowed is True


def test_final_ad_requires_end_card():
    product_id = create_product()
    with SessionLocal() as db:
        seed_food_tier_2(db, product_id)
        tier_service = ProductAssetTierService(db)
        tier_output = tier_service.output(tier_service.evaluate(product_id))
        requirement_service = ReferenceRequirementService(db)
        requirement = requirement_service.output(requirement_service.evaluate(tier_output, purpose="final_ad"))
    assert requirement.status == "ready"
    assert requirement.required_tier == "tier_2"
    assert requirement.end_card_required is True


def test_mixed_variant_references_never_raise_current_sku_tier():
    product_id = create_product(variant_key="mango-kunafa")
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", variant_key="mango-kunafa", primary=True, asset_type="packshot")
        mismatched = attach_contract_asset(db, product_id, "angled_wrapper", variant_key="raspberry-pistachio")
        attach_contract_asset(db, product_id, "wrapper_in_hand", variant_key="raspberry-pistachio")
    output = tier(product_id)
    assert output.current_tier == "tier_1"
    assert mismatched.id in output.variant_mismatch_asset_ids
    assert "product_asset_contract:variant_identity_unverified_or_mismatched" in output.blockers


def test_multiple_asset_variants_without_product_variant_are_hard_blocked():
    product_id = create_product()
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", variant_key="mango-kunafa", primary=True, asset_type="packshot")
        attach_contract_asset(db, product_id, "angled_wrapper", variant_key="raspberry-pistachio")
        attach_contract_asset(db, product_id, "wrapper_in_hand", variant_key="raspberry-pistachio")
    output = tier(product_id)
    assert output.current_tier == "tier_1"
    assert "product_asset_contract:multiple_variants_attached_to_one_product" in output.blockers
    assert len(output.variant_mismatch_asset_ids) == 2


def test_cyrillic_variant_key_is_preserved():
    assert normalize_key("Малина и фисташка") == "малина-и-фисташка"


def test_profile_inference_does_not_treat_barcode_or_skin_barrier_as_food():
    with SessionLocal() as db:
        scanner = models.Product(
            sku="SCAN-1",
            brand="Tools",
            title="Barcode scanner",
            description="Handheld inventory tool",
            category="electronics",
            attributes_json={},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
        serum = models.Product(
            sku="SERUM-1",
            brand="Care",
            title="Skin barrier serum",
            description="Daily skincare serum",
            category="beauty",
            attributes_json={},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
        bombbar = models.Product(
            sku="FOOD-1",
            brand="Bombbar",
            title="Bombbar Pro Dubai Mango & Kunafa",
            description="",
            category="",
            attributes_json={},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
        assert product_profile(scanner) == "general"
        assert product_profile(serum) == "cosmetic"
        assert product_profile(bombbar) == "food_snack"


def test_cosmetic_profile_unlocks_application_not_bite():
    product_id = create_product(profile="cosmetic", variant_key="rose-serum")
    with SessionLocal() as db:
        for contract_type in ["front_packshot", "angled_product", "product_in_hand", "dispenser_closeup", "texture_swatch", "application_area", "application_demo", "use_video_reference"]:
            attach_contract_asset(
                db,
                product_id,
                contract_type,
                variant_key="rose-serum",
                primary=contract_type == "front_packshot",
                asset_type="packshot" if contract_type == "front_packshot" else "product",
            )
    output = tier(product_id)
    assert output.current_tier == "tier_4"
    assert output.permissions.interaction_mode == "apply"
    assert output.permissions.interaction_scene_allowed is True
    assert output.permissions.application_scene_allowed is True
    assert output.permissions.try_on_scene_allowed is False
    assert output.permissions.bite_scene_allowed is False


def test_apparel_profile_unlocks_try_on_not_application_or_bite():
    product_id = create_product(profile="apparel", variant_key="black-dress")
    with SessionLocal() as db:
        for contract_type in ["front_view", "back_view", "detail_closeup", "on_body", "application_context", "movement_reference", "use_video_reference"]:
            attach_contract_asset(db, product_id, contract_type, variant_key="black-dress", primary=contract_type == "front_view")
    output = tier(product_id)
    assert output.current_tier == "tier_4"
    assert output.permissions.interaction_mode == "try_on"
    assert output.permissions.try_on_scene_allowed is True
    assert output.permissions.application_scene_allowed is False
    assert output.permissions.bite_scene_allowed is False


def test_household_profile_unlocks_operation_not_cosmetic_application():
    product_id = create_product(profile="household", variant_key="steam-cleaner-white")
    with SessionLocal() as db:
        for contract_type in ["front_packshot", "angled_product", "product_in_hand", "detail_closeup", "application_context", "result_context", "application_demo", "use_video_reference"]:
            attach_contract_asset(db, product_id, contract_type, variant_key="steam-cleaner-white", primary=contract_type == "front_packshot")
    output = tier(product_id)
    assert output.current_tier == "tier_4"
    assert output.permissions.interaction_mode == "demonstrate"
    assert output.permissions.demonstration_scene_allowed is True
    assert output.permissions.application_scene_allowed is False
    assert output.permissions.try_on_scene_allowed is False
    assert output.permissions.bite_scene_allowed is False


def test_asset_contract_integrates_with_one_video_policy():
    product_id = create_product()
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", primary=True, asset_type="packshot")
        policy = ProductScenePolicyService(db).evaluate(product_id)
    assert policy.current_asset_tier == "tier_1"
    assert policy.required_asset_tier == "tier_2"
    assert policy.provider_generated_packaging_allowed is False
    assert policy.asset_contract["requirement"]["status"] == "needs_assets"
    assert any(item.startswith("product_asset_contract:") for item in policy.blockers)


def test_generic_cosmetic_video_plan_uses_blogger_apply_flow_without_bar_language():
    product_id = create_product(profile="cosmetic", variant_key="rose-serum")
    with SessionLocal() as db:
        product = db.get(models.Product, product_id)
        product.attributes_json = {
            **(product.attributes_json or {}),
            "visual_identity": ["clear rose serum", "white pump bottle"],
            "excluded_variants": ["amber dropper bottle"],
        }
        db.commit()
        for contract_type in ["front_packshot", "angled_product", "product_in_hand", "dispenser_closeup", "texture_swatch", "application_area", "application_demo", "use_video_reference"]:
            attach_contract_asset(
                db,
                product_id,
                contract_type,
                variant_key="rose-serum",
                primary=contract_type == "front_packshot",
                asset_type="packshot" if contract_type == "front_packshot" else "product",
            )
        plan = OneVideoAcceptanceService(db).build_plan(product_id, platform="Instagram Reels")
    policy = plan.product_scene_policy_json
    proof = next(scene for scene in plan.scene_plan_json if scene["role"] == "proof_use_case")
    assert policy["interaction_mode"] == "apply"
    assert policy["application_scene_allowed"] is True
    assert "наношу средство" in proof["spoken_line"]
    assert "approved apply use-video/reference insert" in proof["visual"]
    assert policy["provider_generated_product_allowed"] is False
    assert "generic muesli bar" not in plan.negative_prompt
    assert "wrong dispenser" in plan.negative_prompt
    assert "no_muesli_granola_visual_drift" not in plan.acceptance_checklist_json
    assert "application_area_and_motion_match_references" in plan.acceptance_checklist_json
    assert all("Flavor identity lock" not in item["prompt_text"] for item in plan.prompt_preview_json["scene_prompts"])
    assert all("Variant identity lock" in item["prompt_text"] for item in plan.prompt_preview_json["scene_prompts"])


def test_asset_contract_updates_engine_audit_asset_readiness():
    product_id = create_product(variant_key="mango-kunafa")
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", variant_key="mango-kunafa", primary=True, asset_type="packshot")
        run = EngineAuditScorecardService(db).run()
        output = EngineAuditScorecardService(db).output(run)
    assets = next(item for item in output.dimensions if item.key == "asset_readiness")
    assert assets.evidence["product_asset_contracts"][0]["current_tier"] == "tier_1"
    assert "product_asset_contract_below_tier_2" in assets.reasons


def test_engine_audit_does_not_request_edible_refs_for_non_food_product():
    product_id = create_product(profile="cosmetic", variant_key="rose-serum")
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", variant_key="rose-serum", primary=True, asset_type="packshot")
        run = EngineAuditScorecardService(db).run()
        output = EngineAuditScorecardService(db).output(run)
    assets = next(item for item in output.dimensions if item.key == "asset_readiness")
    assert "edible_reference_count_below_3" not in assets.reasons
    assert assets.evidence["product_asset_contracts"][0]["interaction_mode"] == "apply"


def test_control_room_shows_product_asset_contract_blocker():
    product_id = create_product(variant_key="mango-kunafa")
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", variant_key="mango-kunafa", primary=True, asset_type="packshot")
    response = TestClient(app).get("/control-room?role=owner")
    assert response.status_code == 200
    assert "Product Asset Contract" in response.text
    assert "tier_1" in response.text
    assert "Собрать недостающие фото товара" in response.text


def test_product_asset_contract_api_exposes_profile_variant_and_interaction():
    product_id = create_product(profile="apparel", variant_key="black-dress")
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_view", variant_key="black-dress", primary=True)
    response = TestClient(app).get(f"/api/assets/products/{product_id}/contract?purpose=final_ad")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tier"]["product_profile"] == "apparel"
    assert payload["tier"]["variant_key"] == "black-dress"
    assert payload["tier"]["permissions"]["interaction_mode"] == "try_on"
    assert payload["tier"]["permissions"]["interaction_scene_allowed"] is False
    assert payload["requirement"]["status"] == "needs_assets"


def test_human_review_maps_generic_variant_and_interaction_drift():
    blockers = OneVideoAcceptanceService._blockers_from_review(
        "needs_regeneration",
        "Wrong SKU variant, dispenser changed and wrong application motion.",
    )
    fixes = OneVideoAcceptanceService._fixes_from_blockers(blockers)
    assert "product_variant_drift" in blockers
    assert "product_interaction_drift" in blockers
    assert "separate_variant_refs_and_use_exact_packshot_or_compositor" in fixes
    assert "replace_generated_action_with_approved_use_reference" in fixes


def test_check_product_asset_contract_cli_outputs_missing_assets():
    product_id = create_product()
    with SessionLocal() as db:
        attach_contract_asset(db, product_id, "front_packshot", primary=True, asset_type="packshot")
    result = subprocess.run(
        [sys.executable, "scripts/check_product_asset_contract.py", "--product-id", str(product_id), "--purpose", "bite_scene"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "QVF_DATABASE_URL": str(engine.url)},
    )
    assert result.returncode == 0, result.stderr
    assert "Current Tier: tier_1" in result.stdout
    assert "Required Tier: tier_4 (bite_scene)" in result.stdout
    assert "Missing Assets:" in result.stdout
