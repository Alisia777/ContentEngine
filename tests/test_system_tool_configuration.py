from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.output_acceptance.frame_extractor import FrameExtractor
from app.services.video_assembly import VideoAssemblyService
from app.system_tools import (
    resolve_executable,
    resolve_ffmpeg,
    resolve_ffprobe,
    resolve_tesseract,
)
from app.visual_evidence import LocalTesseractOCR


def test_explicit_executable_path_wins_and_invalid_value_does_not_silently_fallback(
    tmp_path: Path,
    monkeypatch,
):
    tool = tmp_path / "ffmpeg.exe"
    tool.write_bytes(b"not executed in this resolution test")
    resolved = resolve_executable(str(tool), "ffmpeg")
    assert resolved.path == str(tool.resolve())
    assert resolved.source == "explicit"
    assert resolved.configured_explicitly is True

    monkeypatch.setattr(
        "app.system_tools.shutil.which",
        lambda name: "C:/PATH/ffmpeg.exe" if name == "ffmpeg" else None,
    )
    invalid = resolve_executable(str(tmp_path / "missing-ffmpeg.exe"), "ffmpeg")
    assert invalid.path is None
    assert invalid.source == "explicit"


def test_ffprobe_is_discovered_next_to_explicit_ffmpeg(tmp_path: Path):
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    ffprobe.write_bytes(b"ffprobe")
    settings = Settings(
        _env_file=None,
        media_root=tmp_path / "media",
        ffmpeg_path=str(ffmpeg),
        ffprobe_path=None,
    )
    assert resolve_ffmpeg(settings).path == str(ffmpeg.resolve())
    probe = resolve_ffprobe(settings)
    assert probe.path == str(ffprobe.resolve())
    assert probe.source == "ffmpeg_sibling"

    extractor = object.__new__(FrameExtractor)
    extractor.settings = settings
    assembler = object.__new__(VideoAssemblyService)
    assembler.settings = settings
    assert extractor.ffmpeg_path == str(ffmpeg.resolve())
    assert extractor.ffprobe_path == str(ffprobe.resolve())
    assert assembler.ffmpeg_path == str(ffmpeg.resolve())


def test_tesseract_can_be_resolved_from_explicit_setting(tmp_path: Path):
    tesseract = tmp_path / "tesseract.exe"
    tesseract.write_bytes(b"tesseract")
    settings = Settings(
        _env_file=None,
        media_root=tmp_path / "media",
        tesseract_path=str(tesseract),
    )
    resolution = resolve_tesseract(settings)
    assert resolution.path == str(tesseract.resolve())
    assert resolution.source == "explicit"


def test_tesseract_readiness_requires_both_russian_and_english_languages(
    tmp_path: Path,
    monkeypatch,
):
    executable = tmp_path / "tesseract.exe"
    executable.write_bytes(b"probe is mocked")

    class Completed:
        returncode = 0
        stdout = "List of available languages (1):\neng\n"

    monkeypatch.setattr("app.visual_evidence.service.subprocess.run", lambda *_args, **_kwargs: Completed())
    readiness = LocalTesseractOCR(str(executable)).readiness()
    assert readiness["binary_ready"] is True
    assert readiness["ready"] is False
    assert readiness["missing_languages"] == ["rus"]
    assert "executable_path" not in readiness

    Completed.stdout = "List of available languages (2):\nrus\neng\n"
    readiness = LocalTesseractOCR(str(executable)).readiness()
    assert readiness["ready"] is True
    assert readiness["missing_languages"] == []


def test_tessdata_prefix_is_passed_only_to_subprocess_and_not_exposed(
    tmp_path: Path,
    monkeypatch,
):
    executable = tmp_path / "tesseract.exe"
    executable.write_bytes(b"probe is mocked")
    tessdata = tmp_path / "private-runtime-tessdata"
    tessdata.mkdir()
    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = "List of available languages (2):\nrus\neng\n"

    def fake_run(*_args, **kwargs):
        captured.update(kwargs)
        return Completed()

    monkeypatch.setattr("app.visual_evidence.service.subprocess.run", fake_run)
    readiness = LocalTesseractOCR(
        str(executable),
        tessdata_prefix=tessdata,
    ).readiness()
    assert captured["env"]["TESSDATA_PREFIX"] == str(tessdata.resolve())
    assert readiness["tessdata_configured_explicitly"] is True
    assert readiness["tessdata_directory_ready"] is True
    assert str(tessdata.resolve()) not in str(readiness)
