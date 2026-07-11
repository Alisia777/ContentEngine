from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from app.config import Settings, get_settings


@dataclass(frozen=True)
class ExecutableResolution:
    path: str | None
    source: str
    configured_explicitly: bool


def resolve_executable(configured: str | None, fallback_name: str) -> ExecutableResolution:
    """Resolve an explicit executable first, otherwise use the process PATH.

    An invalid explicit value deliberately does not fall back silently: operators
    should see that their deployment configuration needs correction.
    """

    value = str(configured or "").strip()
    if value:
        candidate = Path(value).expanduser()
        if candidate.is_file():
            return ExecutableResolution(str(candidate.resolve()), "explicit", True)
        found = shutil.which(value)
        return ExecutableResolution(found, "explicit", True)
    return ExecutableResolution(shutil.which(fallback_name), "path", False)


def resolve_ffmpeg(settings: Settings | None = None) -> ExecutableResolution:
    resolved_settings = settings or get_settings()
    return resolve_executable(resolved_settings.ffmpeg_path, "ffmpeg")


def resolve_ffprobe(settings: Settings | None = None) -> ExecutableResolution:
    resolved_settings = settings or get_settings()
    explicit = str(resolved_settings.ffprobe_path or "").strip()
    if explicit:
        return resolve_executable(explicit, "ffprobe")

    ffmpeg = resolve_ffmpeg(resolved_settings)
    if ffmpeg.path:
        ffmpeg_path = Path(ffmpeg.path)
        sibling_names = (
            "ffprobe.exe" if ffmpeg_path.suffix.lower() == ".exe" else "ffprobe",
            "ffprobe",
        )
        for sibling_name in dict.fromkeys(sibling_names):
            sibling = ffmpeg_path.with_name(sibling_name)
            if sibling.is_file():
                return ExecutableResolution(
                    str(sibling.resolve()),
                    "ffmpeg_sibling",
                    ffmpeg.configured_explicitly,
                )
    return resolve_executable(None, "ffprobe")


def resolve_tesseract(settings: Settings | None = None) -> ExecutableResolution:
    resolved_settings = settings or get_settings()
    return resolve_executable(resolved_settings.tesseract_path, "tesseract")


def executable_responds(path: str | None, *args: str, timeout_seconds: float = 5) -> bool:
    if not path:
        return False
    try:
        completed = subprocess.run(
            [path, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def media_binary_readiness(settings: Settings | None = None) -> dict[str, object]:
    """Return secret-free FFmpeg/FFprobe deployment readiness."""

    resolved_settings = settings or get_settings()
    ffmpeg = resolve_ffmpeg(resolved_settings)
    ffprobe = resolve_ffprobe(resolved_settings)
    return {
        "ffmpeg_ready": executable_responds(ffmpeg.path, "-version"),
        "ffmpeg_configuration": ffmpeg.source,
        "ffmpeg_configured_explicitly": ffmpeg.configured_explicitly,
        "ffprobe_ready": executable_responds(ffprobe.path, "-version"),
        "ffprobe_configuration": ffprobe.source,
        "ffprobe_configured_explicitly": ffprobe.configured_explicitly,
    }
