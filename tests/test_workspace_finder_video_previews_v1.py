"""«Файлы»: первый кадр видео на карточке и раздел без вечной загрузки (24.08.2026).

Владелица: карточки видео — фиолетовые заглушки («не видно, что сгенерили»),
а «Все файлы» висит на «Обновляем данные…». Причины: у видео-карточек не было
ветки с кадром вовсе; подпись превью (fetch без таймаута) могла держать раздел
бесконечно; на локальном стенде превью резались целиком, потому что подписанные
URL там http://127.0.0.1, а safePreviewUrl принимал только https.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "web/app/workspace-board-view.js"
APP = ROOT / "web/app/app.js"
CSS = ROOT / "web/app/workspace-board.css"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_video_cards_paint_the_first_frame() -> None:
    board = text(BOARD)
    assert 'class="workspace-board__preview-frame"' in board
    # Фрагмент #t= рисует кадр без проигрывания; элемент немой и нефокусируемый.
    assert '#t=0.4" preload="metadata" muted playsinline disablepictureinpicture disableremoteplayback tabindex="-1"' in board
    assert 'class="workspace-board__preview-play"' in board
    css = text(CSS)
    assert ".workspace-board__preview-frame {" in css
    assert "object-fit: cover;" in css
    # Абсолютному кадру нужен позиционированный контейнер.
    assert ".workspace-board__item-preview {\n  position: relative;" in css.replace("\r\n", "\n")


def test_loopback_signed_urls_are_previews_too() -> None:
    """Без адресных литералов (их запрещает сборка Pages): http-превью проходит
    только когда сама страница на http и хост совпадает — то есть на стенде."""
    board = text(BOARD)
    assert 'const sameHostHttp = parsed.protocol === "http:"' in board
    assert 'window.location?.protocol === "http:"' in board
    assert "parsed.hostname === window.location.hostname" in board


def test_preview_signing_cannot_freeze_a_section() -> None:
    app = text(APP)
    assert (
        "data = await withUiTimeout(\n"
        "        hydratePrivateMedia(data),\n"
        "        WORKSPACE_REQUEST_TIMEOUT_MS,\n"
        '        "private_media_hydrate_timeout",\n'
        "      ).catch(() => data);"
    ) in app
    assert '"generation_media_preview_timeout",' in app
