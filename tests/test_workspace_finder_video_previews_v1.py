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
FINDER_CSS = ROOT / "web/app/workspace-os-v4-finder.css"


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


def test_finder_keeps_video_frames_inside_the_scrollable_collection() -> None:
    board = text(BOARD)
    finder_css = text(FINDER_CSS).replace("\r\n", "\n")
    assert 'data-created-at="${escapeHtml(item.createdAt)}"' in board
    assert ".workspace-board__item-preview video.workspace-board__preview-frame {" in finder_css
    video_rule = finder_css.split(
        ".workspace-board__item-preview video.workspace-board__preview-frame {",
        1,
    )[1].split("}", 1)[0]
    for marker in ("max-width: 100%", "max-height: 100%", "object-fit: cover"):
        assert marker in video_rule
    grid_rule = finder_css.split(
        "body.ce-v4-finder-route .workspace-board__grid {",
        1,
    )[1].split("}", 1)[0]
    assert "flex: 1 1 0" in grid_rule
    assert "overflow-y: auto" in grid_rule


def test_captured_frames_live_in_a_cache_so_rerenders_do_not_blink() -> None:
    """Перерисовки списка (поллинг, обновления) пересоздавали <video> — карточки
    мигали чёрным и заново тянули файл. Снятый кадр кэшируется по id материала,
    живой узел заменяется на <img> сразу после захвата."""
    board = text(BOARD)
    assert "const previewFrameCache = new Map();" in board
    assert "function capturePreviewFrame(video)" in board
    assert 'canvas.toDataURL("image/jpeg", 0.72)' in board
    assert "video.replaceWith(img);" in board
    assert '"loadeddata"' in board
    assert 'crossorigin="anonymous" data-preview-capture="${escapeHtml(item.id)}"' in board
    assert "const cachedFrame = previewFrameCache.get(String(item.id));" in board


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


def test_fallback_preview_signing_cannot_freeze_all_files() -> None:
    app = text(APP)
    assert "const fallbackData = {" in app
    assert (
        "target.data = await withUiTimeout(\n"
        "          hydratePrivateMedia(fallbackData),\n"
        "          WORKSPACE_REQUEST_TIMEOUT_MS,\n"
        '          "workspace_board_fallback_hydrate_timeout",\n'
        "        ).catch(() => fallbackData);"
    ) in app
