"""Ползунковый режим выбора ИИ (решение владельца 28.08.2026, v1).

«Вместо выбора ИИ-моделей — быстро/качество и второй ползунок»: ползунок
«Быстрее ↔ Качественнее» и ползунок длительности. Оба — зеркала прежнего
каскада: двигая их, человек кликает те же радио-чипы, поэтому советчик
ИИ-центра, цены, гейты и резерв денег не меняются. Точный список моделей
остаётся под спойлером «вручную».
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTAKE = (ROOT / "web" / "app" / "generation-strategy-intake-v4.js").read_text(
    encoding="utf-8"
)
CSS = (ROOT / "web" / "app" / "generation-strategy-intake-v4.css").read_text(
    encoding="utf-8"
)


def test_slider_is_a_mirror_of_the_cascade_not_a_second_authority() -> None:
    # Ползунок двигает те же радио-чипы модели (прокси-клик), а не пишет
    # собственное состояние: денежный путь один.
    assert "data-generation-intake-engine-slider" in INTAKE
    assert "generationIntakeEngineRange" in INTAKE or "data-generation-intake-engine-range" in INTAKE
    assert "radio.click()" in INTAKE
    assert INTAKE.count("radio.click()") == 2  # модель и длительность
    # Синхронизация — только по отпечатку: панели живут под MutationObserver.
    assert "function syncCascadeSliders(" in INTAKE
    assert "range.dataset.stamp !== stamp" in INTAKE
    # Подпись честная: движок, уровень, цена; совет ИИ-центра не теряется.
    assert "ИИ-центр советует" in INTAKE
    assert "Совет ИИ-центра под этот запуск" in INTAKE
    # Края шкалы говорят про деньги и качество прямо.
    assert "Быстрее и дешевле" in INTAKE
    assert "Качественнее и дороже" in INTAKE


def test_manual_model_list_stays_reachable() -> None:
    # Список моделей с ценами не исчез — он под спойлером.
    assert "Выбрать модель вручную — весь список с ценами" in INTAKE
    assert "gi-engine-manual" in INTAKE
    # Один включённый движок — ползунок прячется, остаётся ручной список.
    assert "usable.length < 2" in INTAKE


def test_duration_slider_respects_source_bound_routes() -> None:
    # Секунды-ползунок только для непрерывного окна выбора; у маршрутов
    # «длина от исходника» остаются прежние подписи (там выбора нет).
    assert "data-generation-intake-duration-slider" in INTAKE
    assert "durations.length - 1" in INTAKE
    assert "как в исходнике" in INTAKE
    assert ".gi-engine-slider" in CSS
    assert ".gi-engine-manual > summary" in CSS


def test_identity_fields_follow_the_active_panel_and_hint_tells_truth() -> None:
    """Боевой скрин 29.08: на «Создании» подсказка требовала артикул «в
    технических деталях», а полей там нет — refreshIdentityVisibility искал
    файлы только в панели «Копии» и прятал SKU/название. Поля следуют за
    активной панелью, рендер-цикл «Создания» держит их честными, подсказка
    ведёт в карточку «1. Ваш товар» и открывает поля сама."""
    assert 'state?.route === "strategy_video" ? "strategy_video" : "copy_video"' in INTAKE
    strategy_branch = INTAKE.split(
        'syncCompactCampaignControl(form, state, "strategy_video");', 1
    )[1].split("refreshVideoSelects(form, state);", 1)[0]
    assert "refreshIdentityVisibility(form, state);" in strategy_branch
    assert "поля открылись в карточке «1. Ваш товар»" in INTAKE
    assert "заполните артикул и название товара в технических деталях" not in INTAKE


def test_from_zero_failures_speak_human_and_duration_slider_never_drops() -> None:
    """Боевой скрин 29.08: «Создание» печатало сырой код
    express_preflight_blocked без причины, а выбранная ползунком длительность
    «слетала», если чипы секунд перестроились в момент движения (клик по
    несуществующему radio молча терялся)."""
    from_zero = INTAKE.split("async function continueStrategyFromZero", 1)[1]
    catch_block = from_zero.split("} catch (error) {", 1)[1]
    assert "fromZeroMessages" in catch_block
    assert "Мастер заблокирован: ${" in catch_block
    assert "Ничего не запущено и не оплачено" in catch_block
    # Ползунок секунд: потерянный radio → прямое applyCopyDuration в мастер.
    assert "applyCopyDuration(host, seconds)" in INTAKE
