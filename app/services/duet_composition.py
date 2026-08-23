"""Сборка дуэта: комментатор в углу поверх исходного ролика.

ЧТО ЭТО ЗА ФОРМАТ. Берём готовый рекламный ролик, НЕ трогаем его, и врезаем в
угол сгенерированного ведущего, который рассказывает, что в ролике происходит.
В соцсетях это называют дуэтом или реакцией. Результат — вертикальный шортс.

ПОЧЕМУ ЗДЕСЬ НЕТ ИИ. Ведущего рисует провайдер, и это единственная творческая
часть. Само наложение — арифметика: положить прямоугольник в заданные
координаты. Просить у модели «положи вот это вот сюда» значило бы платить за
то, что делается бесплатно, точно и предсказуемо. Поэтому сборка идёт локальным
ffmpeg, а не пятым провайдером.

ПРО ПРОЗРАЧНОСТЬ. Ведущий приходит от HeyGen в WebM с альфа-каналом. Это
надмножество обоих желаемых видов: из выреза можно нарисовать окно с подложкой,
а из непрозрачного MP4 вырез не получить никогда. Поэтому оба вида собираются
здесь, из одного и того же исходного файла ведущего.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from app.config import get_settings
from app.system_tools import resolve_ffmpeg


# Вертикальный кадр шортса. Значения не настраиваются вызывающим: результат
# уходит в ленту, где формат задан площадкой, а не нами.
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920

# Доля ширины кадра, которую занимает окно ведущего. Треть — то же, что в
# готовых шаблонах picture-in-picture: заметно, но не закрывает происходящее.
PRESENTER_WIDTH_RATIO = 0.34
# Отступ от краёв. Площадки накладывают свои элементы управления по низу кадра,
# поэтому запас снизу больше бокового.
MARGIN_X = 36
MARGIN_Y = 96

CORNERS = ("bottom_left", "bottom_right", "top_left", "top_right")
SHAPES = ("cutout", "window")


class DuetCompositionError(RuntimeError):
    """Сборка не удалась. Код машинный, чтобы попадать в журнал без прозы."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DuetLayout:
    """Раскладка дуэта. Всё, что влияет на картинку, названо явно."""

    corner: str = "bottom_left"
    # cutout — ведущий вырезан по контуру, окна нет.
    # window — под ведущим рисуется непрозрачная подложка, как на привычных
    # реакциях: тот же файл, другой вид.
    shape: str = "cutout"
    width_ratio: float = PRESENTER_WIDTH_RATIO

    def validate(self) -> None:
        if self.corner not in CORNERS:
            raise DuetCompositionError("duet_layout_corner_invalid")
        if self.shape not in SHAPES:
            raise DuetCompositionError("duet_layout_shape_invalid")
        # Ведущий меньше пятой части кадра неразличим, больше половины —
        # закрывает то, что комментирует. И то и другое делает формат бессмысленным.
        if not 0.2 <= self.width_ratio <= 0.5:
            raise DuetCompositionError("duet_layout_width_invalid")


class DuetCompositionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.output_dir = self.settings.media_root / "duet"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ffmpeg_path(self) -> str | None:
        return resolve_ffmpeg(self.settings).path

    def compose(
        self,
        *,
        source_path: str | Path,
        presenter_path: str | Path,
        output_name: str,
        layout: DuetLayout | None = None,
        timeout_seconds: int = 600,
    ) -> Path:
        """Собрать дуэт и вернуть путь к готовому файлу.

        Исходный ролик не изменяется ни одним кадром: он масштабируется в
        вертикальный кадр и остаётся собой. Меняется только то, что вокруг.
        """

        layout = layout or DuetLayout()
        layout.validate()

        ffmpeg = self.ffmpeg_path
        if not ffmpeg:
            raise DuetCompositionError("ffmpeg_unavailable")

        source = Path(source_path)
        presenter = Path(presenter_path)
        for path, code in (
            (source, "duet_source_missing"),
            (presenter, "duet_presenter_missing"),
        ):
            if not path.exists():
                raise DuetCompositionError(code)

        output = self.output_dir / output_name
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-i",
            str(presenter),
            "-filter_complex",
            build_duet_filter(layout),
            "-map",
            "[out]",
            # Дорожка исходника сохраняется, речь ведущего подмешивается к ней.
            # Молчащий комментатор — не дуэт, а исходник без звука — не исходник.
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DuetCompositionError("duet_compose_timeout") from error
        if completed.returncode != 0 or not output.exists():
            # Вывод ffmpeg наружу не переносится: он содержит пути к файлам.
            raise DuetCompositionError("duet_compose_failed")
        return output


def build_duet_filter(layout: DuetLayout) -> str:
    """Собрать выражение фильтра ffmpeg. Чистая функция — её можно проверить.

    Логика вынесена из вызова процесса намеренно: раскладка это арифметика, и
    проверять её надо арифметикой, а не запуском ffmpeg на настоящих файлах.
    """

    layout.validate()
    presenter_width = int(SHORT_WIDTH * layout.width_ratio)
    # Чётная ширина: нечётная ломает кодирование в yuv420p.
    if presenter_width % 2:
        presenter_width -= 1

    x = f"{MARGIN_X}" if layout.corner.endswith("_left") else f"W-w-{MARGIN_X}"
    y = f"{MARGIN_Y}" if layout.corner.startswith("top_") else f"H-h-{MARGIN_Y}"

    parts = [
        # Исходник вписывается в вертикальный кадр целиком и не обрезается:
        # мы комментируем ролик, а не показываем его кусок. Пустое место
        # заполняется его же размытой копией — так кадр не выглядит дырой.
        f"[0:v]scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={SHORT_WIDTH}:{SHORT_HEIGHT},boxblur=20:2[bg]",
        f"[0:v]scale={SHORT_WIDTH}:{SHORT_HEIGHT}:force_original_aspect_ratio=decrease[src]",
        "[bg][src]overlay=(W-w)/2:(H-h)/2[base]",
        # Ведущий масштабируется по ширине, высота считается по пропорции.
        f"[1:v]scale={presenter_width}:-2[pv]",
    ]

    if layout.shape == "window":
        # Подложка под ведущего: тот же вырез, но на непрозрачном прямоугольнике —
        # привычный вид реакции. Отдельным слоем, чтобы из одного и того же
        # файла ведущего получались оба вида.
        parts.append(
            f"color=c=black@0.85:s={presenter_width}x{presenter_width}"
            f":d=1,format=rgba[plate]"
        )
        parts.append("[plate][pv]overlay=(W-w)/2:(H-h)/2:format=auto[pw]")
        parts.append(f"[base][pw]overlay={x}:{y}:format=auto[out]")
    else:
        parts.append(f"[base][pv]overlay={x}:{y}:format=auto[out]")

    # Звук: исходник плюс речь ведущего. Дуэт — это два голоса, а не подмена.
    parts.append("[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]")
    return ";".join(parts)
