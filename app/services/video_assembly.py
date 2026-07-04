from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import textwrap

from app.config import get_settings


class VideoAssemblyService:
    def __init__(self):
        self.settings = get_settings()
        self.output_dir = self.settings.media_root / "output"
        self.mock_dir = self.settings.media_root / "mock"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.mock_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ffmpeg_path(self) -> str | None:
        return shutil.which("ffmpeg")

    def create_mock_clip(
        self,
        video_job_id: int,
        scene_number: int,
        duration_seconds: int,
        caption: str,
        prompt: str,
    ) -> str:
        path = self.mock_dir / f"video_job_{video_job_id}_scene_{scene_number}.mp4"
        self._write_sidecar(
            path,
            f"Scene {scene_number}\nCaption: {caption}\nPrompt: {prompt}\nDuration: {duration_seconds}s\n",
        )
        if self.ffmpeg_path:
            color = self._color_for_scene(scene_number)
            try:
                subprocess.run(
                    [
                        self.ffmpeg_path,
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c={color}:s=720x1280:d={duration_seconds}",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-shortest",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "aac",
                        str(path),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return path.as_posix()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        self._write_placeholder_video(path, f"Mock clip placeholder\nScene {scene_number}\n{caption}\n{prompt}\n")
        return path.as_posix()

    def assemble(self, video_job_id: int, clip_paths: list[str], final_cta: str, captions: list[str]) -> tuple[str, str]:
        output_path = self.output_dir / f"video_job_{video_job_id}_final.mp4"
        preview_path = self.output_dir / f"video_job_{video_job_id}_preview.txt"
        preview_path.write_text(
            "Qharisma Video Factory preview\n\n"
            + "\n".join(f"- {caption}" for caption in captions)
            + f"\n\nCTA: {final_cta}\n",
            encoding="utf-8",
        )
        self._write_sidecar(output_path, self._srt(captions, final_cta))

        if self.ffmpeg_path and clip_paths and all(Path(path).exists() for path in clip_paths):
            concat_file = self.output_dir / f"video_job_{video_job_id}_concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{Path(path).resolve().as_posix()}'" for path in clip_paths),
                encoding="utf-8",
            )
            try:
                subprocess.run(
                    [
                        self.ffmpeg_path,
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_file),
                        "-c",
                        "copy",
                        str(output_path),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return output_path.as_posix(), preview_path.as_posix()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

        self._write_placeholder_video(
            output_path,
            "Mock final video placeholder\n"
            + "\n".join(Path(path).name for path in clip_paths)
            + f"\nCTA: {final_cta}\n",
        )
        return output_path.as_posix(), preview_path.as_posix()

    @staticmethod
    def _color_for_scene(scene_number: int) -> str:
        colors = ["#0f766e", "#334155", "#854d0e", "#7c2d12", "#155e75"]
        return colors[(scene_number - 1) % len(colors)]

    @staticmethod
    def _write_placeholder_video(path: Path, content: str) -> None:
        path.write_text(
            "FFmpeg unavailable or clip concat failed. This is a clear local placeholder artifact.\n\n"
            + content,
            encoding="utf-8",
        )

    @staticmethod
    def _write_sidecar(path: Path, content: str) -> None:
        path.with_suffix(path.suffix + ".txt").write_text(content, encoding="utf-8")

    @staticmethod
    def _srt(captions: list[str], final_cta: str) -> str:
        blocks = []
        start = 0
        for index, caption in enumerate(captions, start=1):
            end = start + 3
            blocks.append(
                textwrap.dedent(
                    f"""\
                    {index}
                    00:00:{start:02d},000 --> 00:00:{end:02d},000
                    {caption}
                    """
                )
            )
            start = end
        blocks.append(
            textwrap.dedent(
                f"""\
                {len(captions) + 1}
                00:00:{start:02d},000 --> 00:00:{start + 3:02d},000
                {final_cta}
                """
            )
        )
        return "\n".join(blocks)
