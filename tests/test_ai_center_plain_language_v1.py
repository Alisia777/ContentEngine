"""Понятный язык ИИ-центра (фидбек владельца 27.08.2026).

Две жалобы: «что такое „Создать с рекомендациями“, что такое „Открыть
исследование“» — кнопки без объяснения последствий; «в истории и кейсах не
всегда понятен смысл» — журнал говорил серверными формулами («Use trust
building in this category», «operator_confirmed», state N).
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "web" / "app" / "workspace-ai-exact-youtube-sources.js"
).read_text(encoding="utf-8")
ROOM = (ROOT / "web" / "app" / "ai-learning-control-room.js").read_text(
    encoding="utf-8"
)
CSS = (
    ROOT / "web" / "app" / "workspace-ai-exact-youtube-sources.css"
).read_text(encoding="utf-8")


def test_source_card_buttons_explain_what_happens() -> None:
    # Словарь «что произойдёт при нажатии» покрывает обе кнопки со скрина
    # и остальные состояния жизненного цикла источника.
    assert "const ACTION_HINTS" in SOURCES
    for label in (
        '"Создать с рекомендациями"',
        '"Открыть исследование"',
        '"Загрузить MP4 и продолжить"',
        '"Отобрать для обучения"',
        '"Подготовить кадры для исследования"',
    ):
        assert label in SOURCES, label
    # Расшифровка видна без наведения: строка под кнопками + title.
    assert "ai-exact-youtube-source__hints" in SOURCES
    assert "primary.title = primaryHint" in SOURCES
    assert ".ai-exact-youtube-source__hints" in CSS


def test_history_journal_speaks_russian_without_losing_the_server_record() -> None:
    # «Use X in this category» переводится через существующий словарь приёмов
    # (trust building → trust_builder), решения оператора — по-русски.
    assert "function humanizeActivityTitle" in ROOM
    assert "ANGLE_TITLE_ALIASES" in ROOM
    assert 'trust_building: "trust_builder"' in ROOM
    assert "ACTIVITY_DESCRIPTION_LABELS" in ROOM
    assert "operator_confirmed:" in ROOM
    assert "operator_rejected:" in ROOM
    # Журнал append-only: серверная формулировка не выбрасывается, а уходит
    # мелкой строкой рядом с автором и временем.
    assert "humanTitle ? `${escapeHtml(item.title)} · `" in ROOM
