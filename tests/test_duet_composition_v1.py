"""Сборка дуэта: комментатор в углу поверх исходного ролика.

Формат: берём готовый рекламный ролик, НЕ трогаем его, и врезаем в угол
сгенерированного ведущего, который рассказывает, что в ролике происходит.
Результат — вертикальный шортс.

Раскладка вынесена в чистую функцию намеренно: это арифметика, и проверять её
надо арифметикой, а не запуском ffmpeg на настоящих файлах. Сам ffmpeg проверен
отдельно, живой сборкой — см. докстроку последнего теста.
"""

from __future__ import annotations

import pathlib

import pytest

from app.services.duet_composition import (
    CORNERS,
    SHAPES,
    DuetCompositionError,
    DuetLayout,
    SHORT_HEIGHT,
    SHORT_WIDTH,
    build_duet_filter,
)


def test_result_is_a_vertical_short_and_the_source_is_never_cropped() -> None:
    """Исходник вписывается целиком: мы комментируем ролик, а не его кусок."""

    expression = build_duet_filter(DuetLayout())

    assert f"scale={SHORT_WIDTH}:{SHORT_HEIGHT}" in expression
    assert (SHORT_WIDTH, SHORT_HEIGHT) == (1080, 1920)

    # Видимый слой исходника вписывается по МЕНЬШЕЙ стороне — ничего не
    # обрезается. Обрезка есть только у размытой подложки, которая заполняет
    # поля: без неё вертикальный кадр выглядел бы дырой.
    visible = expression.split("[src]", 1)[0].rsplit(";", 1)[-1]
    assert "force_original_aspect_ratio=decrease" in visible
    assert "crop=" not in visible

    background = expression.split("[bg]", 1)[0]
    assert "force_original_aspect_ratio=increase" in background
    assert "boxblur" in background


@pytest.mark.parametrize("corner", CORNERS)
def test_every_corner_places_the_presenter_inside_the_frame(corner: str) -> None:
    """Ведущий не уезжает за край ни в одном из четырёх углов."""

    expression = build_duet_filter(DuetLayout(corner=corner))
    overlay = expression.split("[base][pv]overlay=", 1)[1].split(":format", 1)[0]
    x, y = overlay.split(":")

    # Слева и сверху — отступ от нуля; справа и снизу — от края минус ширина
    # самого ведущего. Иначе окно вылезло бы за кадр ровно на свою ширину.
    assert (x.startswith("W-w-") if corner.endswith("_right") else x.isdigit())
    assert (y.isdigit() if corner.startswith("top_") else y.startswith("H-h-"))


def test_presenter_width_is_even_because_the_codec_demands_it() -> None:
    """Нечётная ширина ломает кодирование в yuv420p.

    Это не педантизм: ffmpeg отказывается кодировать кадр с нечётной стороной,
    и сборка падала бы на некоторых долях ширины — то есть через раз.
    """

    for ratio in (0.2, 0.25, 0.33, 0.34, 0.41, 0.5):
        expression = build_duet_filter(DuetLayout(width_ratio=ratio))
        width = int(expression.split("[1:v]scale=", 1)[1].split(":", 1)[0])
        assert width % 2 == 0, ratio
        assert 0 < width < SHORT_WIDTH


def test_window_shape_draws_a_plate_and_cutout_does_not() -> None:
    """Один и тот же файл ведущего даёт оба привычных вида.

    Прозрачный ведущий — надмножество: из выреза можно нарисовать окно с
    подложкой, из непрозрачного MP4 вырез не получить никогда. Поэтому оба вида
    собираются здесь, а провайдера просим всегда отдавать прозрачность.
    """

    cutout = build_duet_filter(DuetLayout(shape="cutout"))
    window = build_duet_filter(DuetLayout(shape="window"))

    assert "[plate]" not in cutout
    assert "[plate]" in window
    # Подложка кладётся ПОД ведущего, а не поверх: порядок здесь и есть смысл.
    assert window.index("[plate][pv]overlay") < window.index("[base][pw]overlay")


def test_both_voices_are_kept_because_a_duet_has_two() -> None:
    """Дуэт — это два голоса, а не подмена одного другим.

    Молчащий комментатор — не дуэт; исходник без своего звука — не исходник.
    """

    expression = build_duet_filter(DuetLayout())

    assert "[0:a][1:a]amix=inputs=2" in expression
    # Длительность задаёт исходник: ведущий может договорить раньше, но обрезать
    # комментируемый ролик под длину речи нельзя.
    assert "duration=first" in expression


@pytest.mark.parametrize(
    "layout,code",
    [
        (DuetLayout(corner="middle"), "duet_layout_corner_invalid"),
        (DuetLayout(shape="floating"), "duet_layout_shape_invalid"),
        (DuetLayout(width_ratio=0.05), "duet_layout_width_invalid"),
        (DuetLayout(width_ratio=0.9), "duet_layout_width_invalid"),
    ],
)
def test_layout_refuses_values_that_would_make_the_format_meaningless(
    layout: DuetLayout, code: str
) -> None:
    """Ведущий меньше пятой части кадра неразличим, больше половины — закрывает
    то, что комментирует. И то и другое делает формат бессмысленным."""

    with pytest.raises(DuetCompositionError) as error:
        build_duet_filter(layout)
    assert error.value.code == code


def test_composition_was_verified_by_actually_rendering() -> None:
    """Отметка о живой проверке, а не только о расчёте.

    22.08.2026 фильтр прогнан настоящим ffmpeg в контейнере проекта на двух
    сгенерированных роликах: горизонтальный исходник 1280×720 со звуком и
    ведущий 512×512 с настоящим альфа-каналом. Результат — 1080×1920, две
    дорожки, ведущий слева внизу, фон под ним виден насквозь.

    Первый прогон показал ЧЁРНЫЙ КВАДРАТ вместо выреза. Причина оказалась в
    тестовом ролике, а не в фильтре: `color=c=black@0.0` альфы не даёт, маска
    выходила сплошь непрозрачной. Это стоит помнить — расчёт раскладки такую
    ошибку поймать не мог, её видно только глазами на кадре.

    ЧЕГО ПРОВЕРИТЬ НЕ УДАЛОСЬ. ffmpeg в контейнере не КОДИРУЕТ альфу в VP9
    (`-pix_fmt yuva420p` молча даёт непрозрачный поток), поэтому ведущий для
    проверки был собран в MOV/qtrle. Декодирование VP9-альфы — того формата, в
    котором отдаёт HeyGen, — на настоящем файле провайдера ещё не проверялось.
    Если оно окажется недоступным, вид `window` продолжит работать: подложка
    рисуется нами и прозрачности не требует.
    """

    # Тест намеренно не запускает ffmpeg: он документирует уже сделанную
    # проверку и её границу. Живой прогон стоит секунд и требует контейнера,
    # поэтому в наборе ему не место — но и умолчать о нём нельзя.
    assert build_duet_filter(DuetLayout()).endswith("[aout]")


LAYOUT_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "supabase" / "migrations" / "202608220012_duet_presenter_layout_v1.sql"
)


def test_database_and_composer_agree_on_what_a_valid_layout_is() -> None:
    """Пределы раскладки продублированы намеренно — и обязаны совпадать.

    База принимает раскладку при сохранении ведущего, сборщик проверяет её
    заново при сборке. Дублирование нужно: сборщик обязан отвергать негодную
    раскладку сам, даже если она пришла мимо базы.

    Но если два списка разойдутся, получится худшее из возможного — раскладка,
    принятая базой и отвергнутая при сборке. Отказ придёт УЖЕ ПОСЛЕ генерации
    ведущего, за которого заплачено посекундно.
    """

    sql = LAYOUT_MIGRATION.read_text(encoding="utf-8")

    for corner in CORNERS:
        assert f"'{corner}'" in sql, corner
    # И ничего сверх: угол, которого сборщик не знает, база принимать не должна.
    corner_check = sql.split("overlay_corner = any (array[", 1)[1].split("]))", 1)[0]
    assert sorted(
        part.strip().strip("',") for part in corner_check.split(",") if part.strip()
    ) == sorted(CORNERS)

    for shape in SHAPES:
        assert f"'{shape}'" in sql, shape
    shape_check = sql.split("overlay_shape = any (array[", 1)[1].split("]))", 1)[0]
    assert sorted(
        part.strip().strip("',") for part in shape_check.split(",") if part.strip()
    ) == sorted(SHAPES)

    # Ширина: база хранит целые проценты, сборщик принимает долю. Границы одни.
    assert "overlay_width_percent between 20 and 50" in sql
    minimum, maximum = 0.2, 0.5
    build_duet_filter(DuetLayout(width_ratio=minimum))
    build_duet_filter(DuetLayout(width_ratio=maximum))
    for outside in (minimum - 0.01, maximum + 0.01):
        with pytest.raises(DuetCompositionError):
            build_duet_filter(DuetLayout(width_ratio=outside))


def test_default_layout_matches_the_database_default() -> None:
    """Умолчание одно: иначе ведущий встал бы не там, где показала форма."""

    sql = LAYOUT_MIGRATION.read_text(encoding="utf-8")
    default = DuetLayout()

    assert f"default '{default.corner}'" in sql
    assert f"default '{default.shape}'" in sql
    assert f"default {int(default.width_ratio * 100)}" in sql
