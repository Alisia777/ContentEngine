from __future__ import annotations

import base64
import json
import os

os.environ["QVF_DATABASE_URL"] = "sqlite:///./test_qharisma.db"
os.environ["QVF_MEDIA_ROOT"] = "test_media"
os.environ["QVF_AUTH_REQUIRED"] = "false"
os.environ["QVF_GENERATION_MODE"] = "mock"
os.environ["QVF_ALLOW_REAL_SPEND"] = "false"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import ProviderVideoJob, ProviderVideoStatus
from app.main import app
from app.runway_recipes import (
    ProductImageUpload,
    ProductUGCRecipeRequest,
    ProductUGCRecipeRunner,
    ProductUGCRecipeService,
    RecipeImageInput,
    RunwayRecipeError,
    RunwayRecipeProvider,
)


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def reset_recipe_db(monkeypatch, tmp_path):
    monkeypatch.setenv("QVF_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("QVF_GENERATION_MODE", "mock")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "false")
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    get_settings.cache_clear()


def create_product(*, profile: str = "cosmetic") -> int:
    with SessionLocal() as db:
        product = models.Product(
            sku="ROSE-GLOSS-LUMIERE",
            brand="ALTEA",
            title="ROSÉ GLOSS — Crystal Shine Lip Lacquer",
            description="Sheer rosé-pink gloss in a clear barrel with a rose-gold cap.",
            category="Cosmetics",
            attributes_json={
                "product_profile": profile,
                "variant_key": "rose-lumiere",
                "shade": "warm pink with gold pearl",
            },
            benefits_json=["High shine", "Non-sticky feel"],
            images_json=[],
            reviews_json=[],
            restrictions_json=["Do not invent medical claims"],
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product.id


def upload(slot: str, contract_type: str, *, primary: bool = False) -> ProductImageUpload:
    return ProductImageUpload(
        slot=slot,
        filename=f"{slot}.png",
        content=PNG + slot.encode("ascii"),
        contract_type=contract_type,
        primary=primary,
    )


def create_draft(
    db,
    product_id: int,
    *,
    interaction_mode: str = "presentation",
    proof: bool = False,
    audio: bool = True,
    character_clean: bool = True,
):
    uploads = [
        upload("front", "front_packshot", primary=True),
        upload("angle", "angled_product"),
        upload("scale", "product_in_hand"),
    ]
    if proof:
        uploads.append(upload("proof", "application_demo"))
    return ProductUGCRecipeService(db).create_draft(
        product_id=product_id,
        variant_key="rose-lumiere",
        character_filename="creator.png",
        character_content=PNG,
        product_uploads=uploads,
        task="Показать блеск в живом утреннем макияже.",
        creator_profile="Русскоязычная beauty-блогер 27 лет.",
        setting="У зеркала перед выходом из дома.",
        hook="Смотрите, какой живой микрошимер даёт один слой.",
        product_action="Показывает точный флакон рядом с лицом." if interaction_mode == "presentation" else "Показывает флакон и аккуратно наносит блеск.",
        proof_moment="Поворачивает флакон к свету, чтобы был виден оттенок." if interaction_mode == "presentation" else "Поворачивает лицо к свету, чтобы был виден финиш.",
        spoken_message="Он сияет, но не выглядит тяжёлым на губах.",
        cta="Сохраните оттенок, чтобы не потерять.",
        interaction_mode=interaction_mode,
        duration=15,
        ratio="720:1280",
        audio=audio,
        likeness_consent=True,
        character_product_free_confirmed=character_clean,
        exact_variant_confirmed=True,
    )


def test_three_exact_references_build_official_product_ugc_payload():
    product_id = create_product()
    with SessionLocal() as db:
        draft = create_draft(db, product_id)
        output = ProductUGCRecipeService(db).output(draft)
        assert output.status == "ready_for_paid_preflight"
        assert len(output.product_asset_ids) == 3
        assert output.estimated_credits == 588
        assert output.payload_preview == {
            "version": "2026-06",
            "characterImage": {"uri": f"character-asset://draft/{draft.id}"},
            "productImage": {"uri": f"product-asset://{draft.primary_product_asset_id}"},
            "productInfo": draft.product_info,
            "userConcept": draft.user_concept,
            "duration": 15,
            "ratio": "720:1280",
            "audio": True,
        }
        request = ProductUGCRecipeService(db).provider_request(draft)
        payload = request.model_dump(mode="json", by_alias=True)
        assert set(payload) == {
            "version",
            "characterImage",
            "productImage",
            "productInfo",
            "userConcept",
            "duration",
            "ratio",
            "audio",
        }
        assert payload["characterImage"]["uri"].startswith("data:image/png;base64,")
        assert payload["productImage"]["uri"].startswith("data:image/png;base64,")
        assert "RUNWAYML_API_SECRET" not in json.dumps(output.payload_preview)


def test_provider_product_image_can_be_exact_use_composite_while_front_remains_identity_evidence():
    product_id = create_product(profile="food_snack")
    uploads = [
        upload("front", "front_packshot"),
        upload("angle", "angled_product"),
        upload("surface", "product_on_surface", primary=True),
        upload("proof", "cutaway_product"),
    ]
    with SessionLocal() as db:
        draft = ProductUGCRecipeService(db).create_draft(
            product_id=product_id,
            variant_key="rose-lumiere",
            character_filename="creator.png",
            character_content=PNG,
            product_uploads=uploads,
            task="Показать точный продукт и его реальный разрез.",
            creator_profile="Русскоязычная спортивная блогер 27 лет.",
            setting="После тренировки у окна.",
            hook="Покажу, что внутри, без рекламного глянца.",
            product_action="Показывает упаковку и пробует продукт.",
            proof_moment="В кадре виден точный разрез из product reference.",
            spoken_message="Внутри мягкая начинка, а не мюсли или гранола.",
            cta="Сохраните вариант, чтобы не потерять.",
            interaction_mode="use",
            likeness_consent=True,
            character_product_free_confirmed=True,
            exact_variant_confirmed=True,
        )
        primary = db.get(models.ProductAsset, draft.primary_product_asset_id)
        assert draft.status == "ready_for_paid_preflight"
        assert primary.metadata_json["contract_type"] == "product_on_surface"
        request = ProductUGCRecipeService(db).provider_request(draft)
        expected = base64.b64encode(PNG + b"surface").decode("ascii")
        assert request.product_image.uri.endswith(expected)


def test_use_scene_requires_fourth_category_appropriate_proof_reference():
    product_id = create_product()
    with SessionLocal() as db:
        blocked = create_draft(db, product_id, interaction_mode="use", proof=False)
        assert blocked.status == "blocked"
        assert "use_proof" in blocked.blockers_json

        ready = create_draft(db, product_id, interaction_mode="use", proof=True)
        assert ready.status == "ready_for_paid_preflight"
        assert "use_proof" not in ready.blockers_json


def test_character_reference_with_another_product_is_a_hard_blocker():
    product_id = create_product()
    with SessionLocal() as db:
        draft = create_draft(db, product_id, character_clean=False)
        assert draft.status == "blocked"
        assert "character_reference_clean" in draft.blockers_json


@pytest.mark.parametrize(
    ("profile", "proof_type", "action", "expected_safety", "forbidden_leak"),
    [
        ("food_snack", "cutaway_product", "Открывает упаковку и пробует продукт.", "сначала физически открыть упаковку", "Аппликатор"),
        ("cosmetic", "application_demo", "Наносит продукт аппликатором.", "Аппликатор, дозатор, оттенок", "внутренняя текстура"),
        ("apparel", "on_body", "Примеряет товар и показывает посадку.", "Посадка, длина, материал", "Аппликатор"),
        ("household", "application_demo", "Показывает, как продукт работает.", "реальный и безопасный способ применения", "внутренняя текстура"),
        ("general", "application_context", "Показывает реальное применение продукта.", "реальный и безопасный способ применения", "Аппликатор"),
    ],
)
def test_recipe_use_proof_is_product_category_agnostic(profile, proof_type, action, expected_safety, forbidden_leak):
    product_id = create_product(profile=profile)
    uploads = [
        upload("front", "front_packshot", primary=True),
        upload("angle", "angled_product"),
        upload("scale", "product_in_hand"),
        upload("proof", proof_type),
    ]
    with SessionLocal() as db:
        draft = ProductUGCRecipeService(db).create_draft(
            product_id=product_id,
            variant_key="rose-lumiere",
            character_filename="creator.png",
            character_content=PNG,
            product_uploads=uploads,
            task="Показать реальное применение товара.",
            creator_profile="Русскоязычный блогер 27 лет.",
            setting="Естественная домашняя ситуация.",
            hook="Покажу, как это выглядит в жизни.",
            product_action=action,
            proof_moment="В кадре виден результат действия.",
            spoken_message="Показываю без фильтров и лишних обещаний.",
            cta="Сохраните, чтобы не потерять.",
            interaction_mode="use",
            likeness_consent=True,
            character_product_free_confirmed=True,
            exact_variant_confirmed=True,
        )
        assert draft.status == "ready_for_paid_preflight"
        assert expected_safety in draft.user_concept
        assert forbidden_leak not in draft.user_concept


def test_same_file_cannot_be_reused_as_three_reference_roles():
    product_id = create_product()
    same = PNG + b"same-product-image"
    uploads = [
        ProductImageUpload(slot="front", filename="front.png", content=same, contract_type="front_packshot", primary=True),
        ProductImageUpload(slot="angle", filename="angle.png", content=same, contract_type="angled_product"),
        ProductImageUpload(slot="scale", filename="scale.png", content=same, contract_type="product_in_hand"),
    ]
    with SessionLocal() as db:
        draft = ProductUGCRecipeService(db).create_draft(
            product_id=product_id,
            variant_key="rose-lumiere",
            character_filename="creator.png",
            character_content=PNG,
            product_uploads=uploads,
            task="Показать точный товар.",
            creator_profile="Русскоязычная beauty-блогер 27 лет.",
            setting="Перед зеркалом утром.",
            hook="Покажу новый оттенок.",
            product_action="Показывает закрытый флакон в руке.",
            proof_moment="Поворачивает флакон к дневному свету.",
            spoken_message="Посмотрите на оттенок во флаконе.",
            cta="Сохраните оттенок.",
            likeness_consent=True,
            character_product_free_confirmed=True,
            exact_variant_confirmed=True,
        )
        assert draft.status == "blocked"
        assert "unique_references" in draft.blockers_json


def test_audio_can_be_disabled_and_is_reflected_in_wire_payload():
    product_id = create_product()
    with SessionLocal() as db:
        draft = create_draft(db, product_id, audio=False)
        request = ProductUGCRecipeService(db).provider_request(draft)
        assert request.audio is False
        assert request.model_dump(mode="json", by_alias=True)["audio"] is False


def test_provider_uses_official_recipe_endpoint_and_never_sends_internal_reference_list(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "recipe-task-123", "status": "PENDING"})

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    get_settings.cache_clear()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = RunwayRecipeProvider(api_secret="test-secret", client=client)
    request = ProductUGCRecipeRequest(
        character_image=RecipeImageInput(uri="data:image/png;base64,AA=="),
        product_image=RecipeImageInput(uri="data:image/png;base64,BB=="),
        product_info="Exact product information",
        user_concept="Russian creator presents the exact product naturally.",
        duration=8,
        ratio="720:1280",
        audio=False,
    )
    job = provider.create_product_ugc(request)
    assert job.provider_job_id == "recipe-task-123"
    assert captured["url"] == "https://api.dev.runwayml.com/v1/recipes/product_ugc"
    assert captured["headers"]["x-runway-version"] == "2024-11-06"
    assert captured["payload"]["audio"] is False
    assert "productAssetIds" not in captured["payload"]
    assert set(captured["payload"]) == {
        "version",
        "characterImage",
        "productImage",
        "productInfo",
        "userConcept",
        "duration",
        "ratio",
        "audio",
    }


def test_provider_is_blocked_before_http_without_explicit_spend_gate():
    provider = RunwayRecipeProvider(api_secret="test-secret")
    request = ProductUGCRecipeRequest(
        character_image=RecipeImageInput(uri="data:image/png;base64,AA=="),
        product_image=RecipeImageInput(uri="data:image/png;base64,BB=="),
        product_info="Exact product information",
        user_concept="Creator presents exact product in Russian language.",
    )
    with pytest.raises(ProviderConfigurationError, match="QVF_GENERATION_MODE"):
        provider.create_product_ugc(request)


def test_human_review_cannot_approve_a_draft_without_downloaded_output():
    product_id = create_product()
    with SessionLocal() as db:
        draft = create_draft(db, product_id)
        with pytest.raises(RunwayRecipeError, match="downloaded, non-empty"):
            ProductUGCRecipeService(db).record_human_review(
                draft.id,
                status="approved",
                notes="Looks correct.",
            )


def test_recipe_runner_downloads_output_and_keeps_it_blocked_for_human_review(monkeypatch, tmp_path):
    product_id = create_product()
    with SessionLocal() as db:
        draft = create_draft(db, product_id)
        draft_id = draft.id

    class FakeProvider:
        def create_product_ugc(self, request):
            assert request.product_info
            return ProviderVideoJob(
                provider="runway_product_ugc_recipe",
                provider_job_id="recipe-task-safe",
                status="PENDING",
                raw_response={"id": "recipe-task-safe", "status": "PENDING"},
            )

        def get_status(self, provider_job_id):
            return ProviderVideoStatus(
                provider_job_id=provider_job_id,
                status="SUCCEEDED",
                raw_response={"id": provider_job_id, "status": "SUCCEEDED", "output_count": 1},
            )

        def download_outputs(self, provider_job_id, target_dir):
            target_dir.mkdir(parents=True, exist_ok=True)
            output = target_dir / f"{provider_job_id}.mp4"
            output.write_bytes(b"real-looking-test-video-bytes")
            return [output]

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "never-write-this-secret")
    get_settings.cache_clear()
    with SessionLocal() as db:
        result = ProductUGCRecipeRunner(db, provider_factory=FakeProvider, sleep=lambda _: None).run(
            draft_id,
            real_run=True,
        )
        assert result.status == "generated_needs_human_review"
        assert result.human_review_status == "needs_human_review"
        assert result.publishing_readiness == "blocked"
        assert result.provider_task_id == "recipe-task-safe"
        report = open(result.generation_report_path, encoding="utf-8").read()
        assert "never-write-this-secret" not in report
        assert "data:image" not in report
        assert "signed" not in report.lower()
        reviewed = ProductUGCRecipeService(db).record_human_review(
            draft_id,
            status="approved",
            notes="Exact product and natural creator action verified by a human.",
        )
        assert reviewed.human_review_status == "approved"
        assert reviewed.publishing_readiness == "ready_for_package"


def test_mvp_launch_renders_product_ugc_operator_form_and_creates_draft():
    product_id = create_product()
    api = TestClient(app)
    page = api.get(f"/mvp-launch?product_id={product_id}")
    assert page.status_code == 200
    assert "Official Runway Recipe · Product UGC" in page.text
    assert "Ровно 3 или 4 фото одного варианта" in page.text
    assert 'name="audio_enabled"' in page.text
    assert 'name="interaction_mode"' in page.text
    assert 'name="character_product_free_confirmed"' in page.text

    response = api.post(
        "/mvp-launch/product-ugc-draft",
        data={
            "product_id": str(product_id),
            "variant_key": "rose-lumiere",
            "task": "Показать блеск в повседневном макияже.",
            "creator_profile": "Русскоязычная beauty-блогер 27 лет.",
            "setting": "Перед зеркалом утром.",
            "hook": "Один слой, и посмотрите на этот микрошимер.",
            "product_action": "Показывает флакон и наносит блеск.",
            "proof_moment": "Поворачивает лицо к дневному свету.",
            "spoken_message": "Сияние заметно, но выглядит естественно.",
            "cta": "Сохраните оттенок.",
            "interaction_mode": "use",
            "platform": "Instagram Reels",
            "duration": "15",
            "ratio": "720:1280",
            "audio_enabled": "true",
            "likeness_consent": "true",
            "character_product_free_confirmed": "true",
            "exact_variant_confirmed": "true",
        },
        files={
            "character_image": ("creator.png", PNG, "image/png"),
            "front_image": ("front.png", PNG + b"front", "image/png"),
            "angle_image": ("angle.png", PNG + b"angle", "image/png"),
            "scale_image": ("scale.png", PNG + b"scale", "image/png"),
            "proof_image": ("proof.png", PNG + b"proof", "image/png"),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "ТЗ готово к одному paid запуску" in response.text
    assert "Paid action скрыт" in response.text
    assert "Провайдер ещё не вызван" in response.text
    with SessionLocal() as db:
        draft = db.query(models.ProductUGCRecipeDraft).one()
        assert draft.status == "ready_for_paid_preflight"
        assert draft.provider_task_id is None


def test_paid_product_ugc_ui_runs_once_downloads_output_and_records_human_review(monkeypatch):
    product_id = create_product()
    with SessionLocal() as db:
        draft = create_draft(db, product_id, interaction_mode="use", proof=True)
        draft_id = draft.id
        credits = draft.estimated_credits

    calls = {"created": 0}

    class FakeProvider:
        def create_product_ugc(self, request):
            calls["created"] += 1
            assert request.audio is True
            return ProviderVideoJob(
                provider="runway_product_ugc_recipe",
                provider_job_id="recipe-ui-task-safe",
                status="PENDING",
                raw_response={"id": "recipe-ui-task-safe", "status": "PENDING"},
            )

        def get_status(self, provider_job_id):
            return ProviderVideoStatus(
                provider_job_id=provider_job_id,
                status="SUCCEEDED",
                raw_response={"id": provider_job_id, "status": "SUCCEEDED", "output_count": 1},
            )

        def download_outputs(self, provider_job_id, target_dir):
            target_dir.mkdir(parents=True, exist_ok=True)
            output = target_dir / f"{provider_job_id}.mp4"
            output.write_bytes(b"ui-controlled-product-ugc-video")
            return [output]

    monkeypatch.setenv("QVF_GENERATION_MODE", "real")
    monkeypatch.setenv("QVF_ALLOW_REAL_SPEND", "true")
    monkeypatch.setenv("RUNWAYML_API_SECRET", "test-key-never-persist")
    monkeypatch.setattr("app.runway_recipes.runner.RunwayRecipeProvider", FakeProvider)
    get_settings.cache_clear()

    api = TestClient(app)
    ready_page = api.get(f"/mvp-launch?product_id={product_id}&recipe_draft_id={draft_id}")
    assert ready_page.status_code == 200
    assert "Запустить 1 paid Product UGC" in ready_page.text
    assert "Spend gate включён" in ready_page.text

    generated_page = api.post(
        f"/mvp-launch/product-ugc/{draft_id}/run",
        data={
            "confirm_single_paid_run": "true",
            "confirmed_credits": str(credits),
            "confirm_human_review": "true",
        },
        follow_redirects=True,
    )
    assert generated_page.status_code == 200
    assert "Проверить реальный MP4" in generated_page.text
    assert "recipe-ui-task-safe" in generated_page.text
    assert "Сохранить human review" in generated_page.text
    assert calls["created"] == 1

    duplicate = api.post(
        f"/mvp-launch/product-ugc/{draft_id}/run",
        data={
            "confirm_single_paid_run": "true",
            "confirmed_credits": str(credits),
            "confirm_human_review": "true",
        },
        follow_redirects=True,
    )
    assert duplicate.status_code == 200
    assert "Paid run доступен только" in duplicate.text
    assert calls["created"] == 1

    reviewed_page = api.post(
        f"/mvp-launch/product-ugc/{draft_id}/review",
        data={
            "review_status": "approved",
            "review_notes": "Точный продукт, естественное применение и читаемая упаковка проверены человеком.",
            "confirm_visual_review": "true",
        },
        follow_redirects=True,
    )
    assert reviewed_page.status_code == 200
    assert "Ролик одобрен человеком" in reviewed_page.text
    assert "ready_for_package" in reviewed_page.text
    with SessionLocal() as db:
        reviewed = db.get(models.ProductUGCRecipeDraft, draft_id)
        assert reviewed.human_review_status == "approved"
        assert reviewed.publishing_readiness == "ready_for_package"
