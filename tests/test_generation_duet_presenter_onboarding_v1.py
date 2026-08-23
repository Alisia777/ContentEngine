"""Заведение ведущего «Дуэта» — один сценарий из четырёх шагов (23.08.2026).

Владелица: «не очевидна работа, блок собрать воедино, непонятно как заводить».
Было: выключенный select «Ведущий проекта ещё не заведён» и свёрнутая деталька
с кнопкой, двумя пустыми select и полем имени. И дыра: форма всегда заводила
ведущего как выдуманного персонажа (likeness_kind: "synthetic"), хотя база с
202608220009 различает живого человека и требует для него записанное согласие.

Контракт: без ведущего сценарий раскрыт сам и сам читает каталог; шаги
пронумерованы; шаг 4 спрашивает, кто это, и для живого человека требует
подтверждения согласия; API передаёт вид и согласие серверу.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"
CSS = ROOT / "web/app/generation-strategy-intake-v4.css"
API = ROOT / "web/app/supabase-api.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def between(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def test_onboarding_is_one_numbered_scenario_that_opens_itself() -> None:
    source = text(INTAKE)
    block = between(source, "function duetPresenterRegistration()", "function syncDuetLikenessConsent(")
    assert 'presenterStep(1, "Каталог кабинета HeyGen"' in block
    assert 'presenterStep(2, "Личность и голос"' in block
    assert 'presenterStep(3, "Имя в проекте"' in block
    assert 'presenterStep(4, "Кто это"' in block
    # Раскрытый сценарий читает каталог сам; кнопка остаётся для обновления.
    assert 'details.addEventListener("toggle", () => {' in block
    assert "void loadDuetPresenterCatalog(form, state)" in block
    assert 'setNodeText(load, "Обновить каталог")' in source
    # Превью выбранной личности.
    assert "preview.dataset.generationIntakeDuetCatalogPreview" in block
    assert "option.dataset.preview = item.preview_image_url" in source
    render = between(source, "function renderDuetPresenters(form, state)", "function applyDuetPresenterLayout(")
    assert "register.open = true;" in render
    assert 'setNodeText(registerSummary, "Сменить или добавить ведущего")' in render
    assert "if (!select.hidden) select.hidden = true;" in render
    css = text(CSS)
    assert ".generation-intake-v4__presenter-step {" in css
    assert ".generation-intake-v4__presenter-preview[hidden] {\n  display: none;" in css


def test_real_person_requires_recorded_consent_and_reaches_the_server() -> None:
    source = text(INTAKE)
    assert '["synthetic", "Выдуманный персонаж"' in source
    assert '["real_person", "Живой человек"' in source
    register = between(source, "async function registerDuetPresenterFromForm(", "function duetLayoutControls()")
    assert 'likenessKind === "real_person" && !likenessConsentConfirmed' in register
    assert "likenessKind,\n      likenessConsentConfirmed," in register
    assert "duet_presenter_likeness_consent_required" in register
    api = between(text(API), "async registerDuetPresenter(projectId, input)", "async updateDuetPresenterLayout(")
    assert 'likeness_kind: input?.likenessKind === "real_person" ? "real_person" : "synthetic"' in api
    assert "payload.likeness_consent_confirmed = input?.likenessConsentConfirmed === true;" in api
    assert 'likeness_kind: "synthetic"' not in api
