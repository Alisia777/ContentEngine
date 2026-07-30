from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES_LANDING = ROOT / "index.html"


def test_pages_landing_represents_the_novice_first_factory() -> None:
    html = PAGES_LANDING.read_text(encoding="utf-8")

    assert "Контент ИИ Завод" in html
    assert 'content="0; url=./web/app/"' in html
    assert 'window.location.replace(new URL("./web/app/", window.location.href).href)' in html
    assert '<link rel="canonical" href="./web/app/">' in html
    assert '<a href="./web/app/">Открыть Контент ИИ Завод</a>' in html
    assert "QVF_PUBLIC_APP_URL" not in html
    assert "http://127.0.0.1" not in html
    assert "Открыть локальный" not in html
    assert "после локального запуска" not in html
    assert 'href="docs/CLOUD_DEPLOYMENT.md"' not in html
    assert 'data-runtime-cta="pending"' not in html
    assert 'data-factory-block="' not in html


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
