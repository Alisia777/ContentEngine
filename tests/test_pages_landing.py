from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PAGES_LANDING = ROOT / "index.html"


def test_pages_landing_represents_the_novice_first_factory() -> None:
    html = PAGES_LANDING.read_text(encoding="utf-8")

    assert "Контент ИИ Завод" in html
    assert "QVF_PUBLIC_APP_URL/control-room" in html
    assert "http://127.0.0.1" not in html
    assert len(re.findall(r'data-factory-block="[^"]+"', html)) == 9
    assert "Публичная витрина" in html
    assert "Облачное приложение" in html
    assert "Измеримые контент-циклы за 7 дней" in html
    assert "без автоматического эквайринга" in html
    assert "Wildberries Seller Analytics" in html
    assert html.count("Код готов · нужны credentials") == 4
    assert "Telegram и VK" in html
    assert "Guided setup · manual" in html
    assert "код YT, IG, TT и WB готов к credentials" in html
    assert "Публичные рабочие данные и секреты не выставляются" in html
    assert "требует входа" not in html


def test_pages_landing_does_not_restore_the_legacy_shell() -> None:
    html = PAGES_LANDING.read_text(encoding="utf-8")

    obsolete_fragments = (
        "localhost:8013",
        "127.0.0.1:8013",
        "127.0.0.1:8014",
        "?role=",
        "PR #69",
        "/pull/69",
        "Unified Control Room v3.5",
        "РєР°Р±РёРЅРµС‚",
        "position: sticky",
        "position: fixed",
        "scroll-behavior: smooth",
    )

    for fragment in obsolete_fragments:
        assert fragment not in html
