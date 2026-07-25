from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
FIXTURE = (
    ROOT
    / "web"
    / "app"
    / "assets"
    / "training"
    / "ugc_bombbar_pro_poster.png"
)


def test_local_media_fixture_exists_and_is_https_fail_closed() -> None:
    assert FIXTURE.is_file()
    assert 'window.location.protocol === "http:"' in APP
    assert "LOCAL_QA_MEDIA_FIXTURE_ENABLED ?" in APP


def test_local_media_fixture_uses_the_normal_file_input() -> None:
    for marker in (
        'data-action="use-local-media-fixture"',
        'fetch(LOCAL_QA_MEDIA_FIXTURE_URL, { cache: "no-store" })',
        'new File([blob], "ugc_bombbar_pro_poster.png"',
        "const transfer = new DataTransfer()",
        "input.files = transfer.files",
        'input.dispatchEvent(new Event("change", { bubbles: true }))',
    ):
        assert marker in APP
