"""Персонаж «Дуэта» по описанию — с сервера, кредитами кабинета HeyGen (23.08.2026).

Владелица: «сэмулируй человека, цель — получить аватара и нанести его на
ролик». В кабинет HeyGen завод не заходит и ключ в браузер не отдаёт, поэтому
персонаж создаётся сервером: действие `duet_presenter_generate` просит HeyGen
(POST /v3/avatars, type "prompt") собрать фото-аватар по тексту, а
`duet_presenter_generation_status` опрашивает готовность образа
(GET /v3/avatars/looks/{id}) и сверяет его с каталогом v2, которым живёт дуэт.

Персонаж по описанию — всегда выдуманный; в денежный контур завода он не
входит (нет резервов и квитанций), цена — только кредиты HeyGen.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"
API = ROOT / "web/app/supabase-api.js"
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def between(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def test_edge_generates_a_prompt_avatar_and_polls_the_look() -> None:
    edge = text(EDGE)
    reader = between(edge, "function readDuetPresenterGeneratePayload(", "function readGenerationStrategyId(")
    assert 'new Set(["action", "organization_id", "name", "prompt", "aspect_ratio"])' in reader
    assert "if (prompt.length < 10 || prompt.length > 1_000) return null;" in reader
    assert '!/^[A-Za-z0-9_-]{1,128}$/u.test(value.look_id)' in reader
    handler = between(edge, "const duetPresenterGeneratePayload = readDuetPresenterGeneratePayload(body);", "const strategyCatalogPayload = readStrategyCatalogPayload(body);")
    # Та же проверка роли и тот же ключ, что у каталога; ключ только в заголовке.
    assert '"creator_generation_model_feature_flags"' in handler
    assert 'code: "duet_provider_key_missing"' in handler
    assert "`${HEYGEN_API_ORIGIN}/v3/avatars`" in handler
    assert 'type: "prompt",' in handler
    assert "`${HEYGEN_API_ORIGIN}/v3/avatars/looks/${statusPayload.look_id}`" in handler
    # Готовый образ сверяется с каталогом v2 — тем же, что видит «Дуэт».
    assert "`${HEYGEN_API_ORIGIN}/v2/avatars`" in handler
    assert 'safeText(entry.talking_photo_id, 128) === statusPayload.look_id' in handler
    assert "catalog_confirmed: true" in handler
    # Отказ провайдера называется его словами, но без ключа и без сырого тела.
    assert '"duet_provider_credits_unavailable"' in handler
    assert "hint: safeText(text, 300)," in handler
    assert 'version: "duet-presenter-generation-v1"' in handler
    assert 'version: "duet-presenter-generation-status-v1"' in handler
    # Действие платное для кабинета HeyGen: локальный mock-контур его НЕ пропускает.
    free = between(edge, "const LOCAL_MOCK_FREE_ACTIONS = new Set([", "]);")
    assert "duet_presenter_generate" not in free


def test_browser_api_validates_both_responses_exactly() -> None:
    api = text(API)
    generate = between(api, "async duetPresenterGenerate(input)", "async duetPresenterGenerationStatus(lookId)")
    assert 'this.invokeRealGeneration("duet_presenter_generate", {' in generate
    assert 'hasExactObjectKeys(data, ["ok", "version", "look_id", "group_id", "status"])' in generate
    status = between(api, "async duetPresenterGenerationStatus(lookId)", "async updateDuetPresenterLayout(")
    assert 'hasExactObjectKeys(data, ["ok", "version", "look_id", "status", "error_message", "presenter"])' in status
    assert "catalog_confirmed: data.presenter.catalog_confirmed === true," in status
    allowed = between(api, "const legacyAction = new Set([", "]).has(action);")
    assert '"duet_presenter_generate",' in allowed
    assert '"duet_presenter_generation_status",' in allowed
    for code in ("duet_provider_credits_unavailable", "duet_provider_generation_rejected", "duet_provider_key_missing"):
        assert f"{code}:" in api


def test_screen_offers_generation_inside_step_two_and_selects_the_result() -> None:
    source = text(INTAKE)
    assert 'setNodeText(generateSummary, "Нет подходящей личности? Создать персонажа по описанию");' in source
    assert 'presenterStep(2, "Личность и голос", "", labelled("Личность", presenter), preview, generate, labelled("Голос", voice))' in source
    flow = between(source, "async function generateDuetPresenterFromDescription(form, state)", "async function registerDuetPresenterFromForm(")
    # Имя обязательно до генерации; повторный клик во время работы заблокирован.
    assert "if (displayName.length < 2) {" in flow
    assert "if (button.disabled) return;" in flow
    assert "api.duetPresenterGenerate({ name: displayName, prompt, aspectRatio: \"9:16\" })" in flow
    assert "api.duetPresenterGenerationStatus(started.lookId)" in flow
    assert "presenterSelect.value = result.presenter.id;" in flow
    assert "syncDuetCatalogPreview(block);" in flow
    assert "HeyGen: ${hint}" in flow
