#!/usr/bin/env python3
"""Provider-free воркер подготовки видео (ТЗ 3.8–3.9, контур №1).

Крутится в docker на стенде, ходит в Supabase service-ключом из окружения и
выполняет ДВА вида заданий из content_factory.media_preparation_jobs:

- analyze: читаемость MP4, метаданные (длительность/размер/fps/звук),
  предложение crop (чёрные поля/рамка плеера) и статичные начало/хвост,
  эвристика «похоже на запись экрана». Результат уходит в metadata исходника
  (prep_*-ключи) — карточка «Материалов» показывает его человеку.
- clean_master: производный чистый исходник по подтверждённым человеком
  параметрам (или по предложению анализа): crop → при необходимости
  масштаб 720:-2 (lanczos) → H.264 yuv420p + faststart. Оригинал никогда
  не перезаписывается; новый файл регистрируется сервером как
  source_video_clean со ссылкой на оригинал и унаследованным следом
  происхождения.

Права воркера ограничены системными RPC очереди: он не умеет запускать
генерацию, трогать деньги, подтверждать выводы или публиковать.

Запуск: docker compose -f docker-compose.local.yml up -d media-preparation-worker
Ключ SUPABASE_SERVICE_ROLE_KEY добавляет владелец в .env — в репозитории его нет.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
WORKER_ID = os.environ.get(
    "MEDIA_WORKER_ID", f"media-worker-{socket.gethostname()}-{os.getpid()}"
)[:120]
POLL_SECONDS = max(1, int(os.environ.get("MEDIA_WORKER_POLL_SECONDS", "3")))
FFMPEG = os.environ.get("QVF_FFMPEG_PATH", "ffmpeg")
FFPROBE = os.environ.get("QVF_FFPROBE_PATH", "ffprobe")
MAX_OUTPUT_BYTES = 52_428_800
# Dead-man-switch: пустой env = полный no-op. Пинг шлётся после успешного
# claim-запроса (и на пустой очереди тоже) — сигналит «воркер жив И
# дотягивается до Supabase», а не просто «процесс запущен».
HEALTHCHECK_URL = os.environ.get("HEALTHCHECKS_MEDIA_WORKER_URL", "").strip()
HEALTHCHECK_MIN_INTERVAL = 60.0
_last_healthcheck_ping = 0.0


def log(message: str) -> None:
    print(f"[media-worker {WORKER_ID}] {message}", flush=True)


def ping_healthcheck() -> None:
    global _last_healthcheck_ping
    if not HEALTHCHECK_URL:
        return
    now = time.monotonic()
    if now - _last_healthcheck_ping < HEALTHCHECK_MIN_INTERVAL:
        return
    _last_healthcheck_ping = now
    try:
        with urllib.request.urlopen(HEALTHCHECK_URL, timeout=10):
            pass
    except Exception as error:  # noqa: BLE001 — мониторинг не роняет воркер
        log(f"healthcheck ping failed: {error}")


def rpc(name: str, payload: dict) -> dict:
    body = json.dumps({"p_payload": payload}).encode("utf-8")
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{name}",
        data=body,
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def download(bucket: str, object_name: str, target_path: str) -> None:
    request = urllib.request.Request(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_name}",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response, open(
        target_path, "wb"
    ) as target:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            target.write(chunk)


def upload(
    bucket: str, object_name: str, source_path: str, upsert: bool = False
) -> None:
    # upsert=True нужен финализации: имя результата детерминировано job_id,
    # и retry после успешной заливки, но упавшего complete, получал бы 409.
    with open(source_path, "rb") as source:
        body = source.read()
    request = urllib.request.Request(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_name}",
        data=body,
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "video/mp4",
            "x-upsert": "true" if upsert else "false",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        response.read()


def run_tool(args: list[str], timeout: int = 240) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    )


def probe(path: str) -> dict:
    completed = run_tool([
        FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ])
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe_failed: {completed.stderr[:300]}")
    data = json.loads(completed.stdout or "{}")
    video = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if not video:
        raise RuntimeError("no_video_stream")
    rate = str(video.get("r_frame_rate") or "0/1")
    num, _, den = rate.partition("/")
    fps = round(float(num) / float(den or 1), 2) if float(den or 1) else 0
    return {
        "duration_seconds": round(float(data.get("format", {}).get("duration", 0)), 2),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
        "audio": any(
            s.get("codec_type") == "audio" for s in data.get("streams", [])
        ),
    }


def detect_crop(path: str, duration: float) -> dict | None:
    start = min(1.0, max(0.0, duration / 10))
    completed = run_tool([
        FFMPEG, "-hide_banner", "-ss", str(start), "-i", path,
        "-t", str(min(8.0, max(2.0, duration - start))),
        "-vf", "cropdetect=24:2:0", "-f", "null", "-",
    ])
    matches = re.findall(
        r"crop=(\d+):(\d+):(\d+):(\d+)", completed.stderr or ""
    )
    if not matches:
        return None
    w, h, x, y = (int(v) for v in matches[-1])
    if w <= 0 or h <= 0:
        return None
    return {"w": w, "h": h, "x": x, "y": y}


def detect_static_edges(path: str, duration: float) -> tuple[float, float]:
    completed = run_tool([
        FFMPEG, "-hide_banner", "-i", path,
        "-vf", "freezedetect=n=0.003:d=0.6", "-map", "0:v",
        "-f", "null", "-",
    ], timeout=300)
    text = completed.stderr or ""
    starts = [float(v) for v in re.findall(r"freeze_start: ([0-9.]+)", text)]
    ends = [float(v) for v in re.findall(r"freeze_end: ([0-9.]+)", text)]
    intro = 0.0
    if starts and starts[0] <= 0.4:
        intro = round((ends[0] if ends else min(duration, 3.0)) or 0.0, 2)
    outro = 0.0
    if starts:
        last_start = starts[-1]
        last_end = ends[-1] if len(ends) >= len(starts) else duration
        if duration and last_end >= duration - 0.4:
            outro = round(duration - last_start, 2)
    return intro, outro


def analyze(path: str) -> dict:
    facts = probe(path)
    crop = detect_crop(path, facts["duration_seconds"])
    intro, outro = detect_static_edges(path, facts["duration_seconds"])
    frame_area = facts["width"] * facts["height"]
    crop_area = (crop["w"] * crop["h"]) if crop else frame_area
    cropped_strongly = frame_area > 0 and (crop_area / frame_area) < 0.85
    facts.update({
        "crop": crop,
        "static_intro_seconds": intro,
        "static_outro_seconds": outro,
        "screen_recording_likely": bool(
            cropped_strongly or (intro >= 0.7 and outro >= 0.7)
        ),
    })
    return facts


def number(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_master(path: str, output_path: str, job: dict) -> dict:
    facts = probe(path)
    params = job.get("params") or {}
    defaults = job.get("analysis_defaults") or {}
    trim_start = max(0.0, number(params.get("trim_start_seconds"),
                                 number(defaults.get("trim_start_seconds"))))
    trim_end = max(0.0, number(params.get("trim_end_seconds"),
                               number(defaults.get("trim_end_seconds"))))
    crop = params.get("crop") or defaults.get("crop") or None
    duration = facts["duration_seconds"]
    keep = duration - trim_start - trim_end
    if keep < 4.0:
        # Минимум стратегий — 4 секунды: короче резать нельзя.
        trim_start = 0.0
        trim_end = 0.0
        keep = duration
    filters = []
    width = facts["width"]
    if crop and int(crop.get("w", 0)) > 0 and int(crop.get("h", 0)) > 0:
        filters.append(
            f"crop={int(crop['w'])}:{int(crop['h'])}:{int(crop.get('x', 0))}:{int(crop.get('y', 0))}"
        )
        width = int(crop["w"])
    if width < 720:
        filters.append("scale=720:-2:flags=lanczos")
    args = [FFMPEG, "-hide_banner", "-y", "-ss", str(trim_start), "-i", path]
    if trim_end > 0:
        args += ["-t", str(max(4.0, keep))]
    if filters:
        args += ["-vf", ",".join(filters)]
    args += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-preset", "veryfast", "-movflags", "+faststart",
    ]
    args += (["-c:a", "aac", "-b:a", "128k"] if facts["audio"] else ["-an"])
    args += [output_path]
    completed = run_tool(args, timeout=540)
    if completed.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg_failed: {completed.stderr[-300:]}")
    if os.path.getsize(output_path) > MAX_OUTPUT_BYTES:
        raise RuntimeError("clean_master_exceeds_50mb")
    out_facts = probe(output_path)
    return {
        "applied": {
            "trim_start_seconds": trim_start,
            "trim_end_seconds": trim_end,
            "crop": crop,
        },
        **out_facts,
    }


# ---------------------------------------------------------------------------
# «Финализация» готового ролика (kind=finalize_video, миграция 202609020001):
# родной звук глушится, поверх — TTS-озвучка и три drawtext-плашки. Тайминги
# MVP калиброваны от 10-секундного ролика и масштабируются пропорционально.
# ---------------------------------------------------------------------------
FAL_KEY = os.environ.get("FAL_KEY", "")
FINALIZE_FONT = os.environ.get(
    "FINALIZE_FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
CAPTION_WINDOWS = ((0.3, 3.2, "top"), (3.6, 7.0, "bottom"), (7.3, 9.9, "bottom"))
# Словарь голосов сквозной с RPC-whitelist (202609020003) и select диалога.
# minimax_* требуют FAL_KEY; без ключа или при отказе fal — фолбэк на
# бесплатный edge-голос того же пола.
FINALIZE_VOICES = {
    "minimax_lovely_girl": ("minimax", "Lovely_Girl", "ru-RU-SvetlanaNeural"),
    "minimax_lively_girl": ("minimax", "Lively_Girl", "ru-RU-SvetlanaNeural"),
    "minimax_calm_woman": ("minimax", "Calm_Woman", "ru-RU-SvetlanaNeural"),
    "minimax_wise_woman": ("minimax", "Wise_Woman", "ru-RU-SvetlanaNeural"),
    "minimax_deep_voice_man": ("minimax", "Deep_Voice_Man", "ru-RU-DmitryNeural"),
    "minimax_friendly_person": ("minimax", "Friendly_Person", "ru-RU-DmitryNeural"),
    "edge_svetlana": ("edge", "ru-RU-SvetlanaNeural", "ru-RU-SvetlanaNeural"),
    "edge_dmitry": ("edge", "ru-RU-DmitryNeural", "ru-RU-DmitryNeural"),
}


def synthesize_tts(text: str, voice: str, workdir: str) -> tuple[str, str]:
    """Возвращает (путь к сырому аудио, кто озвучил). Платный MiniMax через
    fal — только по явному выбору голоса и при наличии ключа; любой его отказ
    (включая боевой лок TOP_UP) тихо откатывается на бесплатный edge-tts."""
    raw_path = os.path.join(workdir, "voice-raw.mp3")
    provider, voice_id, edge_fallback = FINALIZE_VOICES.get(
        voice, FINALIZE_VOICES["edge_svetlana"]
    )
    # Один повтор платного пути: докер-сеть эпизодически роняет TLS-хендшейк
    # (боевой случай 02.09), и без повтора честный ключ уезжал в фолбэк.
    for attempt in range(2):
        if provider != "minimax" or not FAL_KEY:
            break
        try:
            body = json.dumps({
                "text": text,
                "voice_setting": {"voice_id": voice_id, "speed": 1.05},
                "language_boost": "Russian",
            }).encode("utf-8")
            request = urllib.request.Request(
                "https://queue.fal.run/fal-ai/minimax/speech-02-hd",
                data=body,
                headers={
                    "Authorization": f"Key {FAL_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                submitted = json.loads(response.read().decode("utf-8"))
            request_id = submitted["request_id"]
            deadline = time.time() + 120
            while time.time() < deadline:
                status_request = urllib.request.Request(
                    "https://queue.fal.run/fal-ai/minimax/requests/"
                    f"{request_id}/status",
                    headers={"Authorization": f"Key {FAL_KEY}"},
                )
                with urllib.request.urlopen(status_request, timeout=60) as sr:
                    status = json.loads(sr.read().decode("utf-8"))
                if status.get("status") == "COMPLETED":
                    break
                time.sleep(2)
            result_request = urllib.request.Request(
                f"https://queue.fal.run/fal-ai/minimax/requests/{request_id}",
                headers={"Authorization": f"Key {FAL_KEY}"},
            )
            with urllib.request.urlopen(result_request, timeout=60) as rr:
                result = json.loads(rr.read().decode("utf-8"))
            audio_url = result["audio"]["url"]
            with urllib.request.urlopen(audio_url, timeout=120) as audio, open(
                raw_path, "wb"
            ) as target:
                target.write(audio.read())
            return raw_path, voice
        except Exception as error:  # noqa: BLE001 — платный путь не обязателен
            if attempt == 0:
                log(f"minimax tts attempt 1 failed, retrying: {error}")
                time.sleep(2)
                continue
            log(f"minimax tts failed, falling back to edge-tts: {error}")
    edge_voice = voice_id if provider == "edge" else edge_fallback
    completed = run_tool([
        sys.executable, "-m", "edge_tts",
        "--voice", edge_voice,
        "--rate", "+10%",
        "--text", text,
        "--write-media", raw_path,
    ], timeout=180)
    if completed.returncode != 0 or not os.path.exists(raw_path):
        raise RuntimeError(f"edge_tts_failed: {completed.stderr[:300]}")
    return raw_path, f"edge:{edge_voice}"


def fit_voice(raw_path: str, workdir: str, target_seconds: float) -> str:
    """Срез хвостовой тишины и мягкая подгонка длительности под ролик."""
    trimmed_path = os.path.join(workdir, "voice-trimmed.wav")
    completed = run_tool([
        FFMPEG, "-hide_banner", "-y", "-i", raw_path,
        "-af",
        "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
        trimmed_path,
    ])
    if completed.returncode != 0 or not os.path.exists(trimmed_path):
        raise RuntimeError(f"voice_trim_failed: {completed.stderr[:300]}")
    voice_seconds = probe_audio_seconds(trimmed_path)
    if voice_seconds <= target_seconds:
        return trimmed_path
    # atempo клампится диапазоном фильтра; остаток страхует -t на сборке.
    tempo = min(2.0, max(1.0, voice_seconds / target_seconds))
    fitted_path = os.path.join(workdir, "voice-fitted.wav")
    completed = run_tool([
        FFMPEG, "-hide_banner", "-y", "-i", trimmed_path,
        "-af", f"atempo={tempo:.4f}", fitted_path,
    ])
    if completed.returncode != 0 or not os.path.exists(fitted_path):
        raise RuntimeError(f"voice_fit_failed: {completed.stderr[:300]}")
    return fitted_path


def probe_audio_seconds(path: str) -> float:
    completed = run_tool([
        FFPROBE, "-v", "error", "-print_format", "json", "-show_format", path,
    ])
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe_failed: {completed.stderr[:300]}")
    data = json.loads(completed.stdout or "{}")
    return float(data.get("format", {}).get("duration", 0) or 0)


FINALIZE_FONT_SCALES = {"small": 0.034, "medium": 0.042, "large": 0.052}


def caption_positions_from_params(params: dict) -> list[str]:
    """Позиция каждой плашки: заданная оператором ('top'|'bottom') либо
    дефолт верх/низ/низ."""
    custom = params.get("caption_positions")
    defaults = [position for _s, _e, position in CAPTION_WINDOWS]
    if isinstance(custom, list) and len(custom) == 3 and all(
        value in ("top", "bottom") for value in custom
    ):
        return list(custom)
    return defaults


def caption_windows_from_params(params: dict, duration: float) -> list[tuple]:
    """Окна показа: заданные оператором абсолютные секунды (уже под конкретный
    ролик, масштабировать нельзя) либо дефолт k = duration / 10. Конец окна
    клампится к длительности, вырожденное окно выбрасывает задание в fail."""
    positions = caption_positions_from_params(params)
    custom = params.get("caption_windows")
    if isinstance(custom, list) and len(custom) == 3:
        windows = []
        for index, pair in enumerate(custom):
            try:
                start = float(pair[0])
                end = float(pair[1])
            except (TypeError, ValueError, IndexError):
                raise RuntimeError("finalize_caption_windows_invalid")
            end = min(end, max(0.1, duration - 0.05))
            if not (0 <= start < end):
                raise RuntimeError("finalize_caption_windows_invalid")
            windows.append((start, end, positions[index]))
        return windows
    scale = max(0.5, duration / 10.0)
    return [
        (start * scale, end * scale, positions[index])
        for index, (start, end, _default) in enumerate(CAPTION_WINDOWS)
    ]


def build_drawtext(captions: list[str], duration: float, height: int,
                   workdir: str, params: dict) -> str:
    """Три плашки через textfile= (никакого экранирования кавычек в -vf)."""
    font_ratio = FINALIZE_FONT_SCALES.get(
        str(params.get("font_scale") or "medium"),
        FINALIZE_FONT_SCALES["medium"],
    )
    font_size = max(24, int(height * font_ratio))
    filters = []
    windows = caption_windows_from_params(params, duration)
    for index, (start, end, position) in enumerate(windows):
        text_path = os.path.join(workdir, f"caption{index}.txt")
        with open(text_path, "w", encoding="utf-8") as target:
            target.write(captions[index])
        y_expr = "h*0.08" if position == "top" else "h-text_h-h*0.10"
        filters.append(
            f"drawtext=fontfile={FINALIZE_FONT}:textfile={text_path}"
            f":fontsize={font_size}:fontcolor=white"
            ":box=1:boxcolor=black@0.5:boxborderw=14"
            f":x=(w-text_w)/2:y={y_expr}"
            f":enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(filters)


def finalize_video(source_path: str, output_path: str, job: dict,
                   workdir: str) -> dict:
    params = job.get("params") or {}
    captions = [
        str(params.get("caption_top") or "").strip()[:120],
        str(params.get("caption_mid") or "").strip()[:120],
        str(params.get("caption_bottom") or "").strip()[:120],
    ]
    narration = str(params.get("narration_text") or "").strip()
    voice = str(params.get("voice") or "edge_svetlana").strip()
    if not narration or not all(captions):
        raise RuntimeError("finalize_params_incomplete")
    facts = probe(source_path)
    duration = facts["duration_seconds"]
    raw_voice, tts_provider = synthesize_tts(narration, voice, workdir)
    voice_path = fit_voice(raw_voice, workdir, max(1.0, duration - 0.2))
    drawtext_chain = build_drawtext(
        captions, duration, facts["height"], workdir, params
    )
    # Режим звука: replace (родная дорожка глушится) или duck — родной звук
    # тихо остаётся под голосом. Duck без родной дорожки честно падает в
    # replace, а не в ошибку amix.
    audio_mode = str(params.get("audio_mode") or "replace")
    if audio_mode == "duck" and facts["audio"]:
        audio_args = [
            "-filter_complex",
            "[0:a]volume=0.18[bg];[1:a][bg]amix=inputs=2:duration=first"
            ":dropout_transition=0[mix]",
            "-map", "0:v", "-map", "[mix]",
        ]
    else:
        audio_args = ["-map", "0:v", "-map", "1:a"]
    completed = run_tool([
        FFMPEG, "-hide_banner", "-y",
        "-i", source_path, "-i", voice_path,
        *audio_args,
        "-vf", drawtext_chain,
        "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "160k",
        "-t", str(duration),
        output_path,
    ], timeout=540)
    if completed.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"finalize_ffmpeg_failed: {completed.stderr[-300:]}")
    if os.path.getsize(output_path) > MAX_OUTPUT_BYTES:
        raise RuntimeError("finalize_exceeds_50mb")
    out_facts = probe(output_path)
    return {
        "applied": {
            "captions": captions,
            "voice": voice,
            "tts_provider": tts_provider,
            "audio_mode": audio_mode if facts["audio"] or audio_mode != "duck"
            else "replace",
            "font_scale": str(params.get("font_scale") or "medium"),
            "caption_positions": caption_positions_from_params(params),
            "caption_windows": [
                [round(start, 2), round(end, 2)]
                for start, end, _position in caption_windows_from_params(
                    params, duration
                )
            ],
        },
        **out_facts,
    }


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def handle(job: dict) -> None:
    job_id = job["job_id"]
    log(f"job {job_id} kind={job['kind']} media={job['media_id']}")
    with tempfile.TemporaryDirectory(prefix="media-prep-") as workdir:
        source_path = os.path.join(workdir, "source.mp4")
        download(job["bucket"], job["object_name"], source_path)
        rpc("system_heartbeat_media_preparation", {
            "job_id": job_id, "worker_id": WORKER_ID,
        })
        if job["kind"] == "analyze":
            result = analyze(source_path)
            rpc("system_complete_media_analysis", {
                "job_id": job_id, "worker_id": WORKER_ID, "result": result,
            })
            log(f"job {job_id} analyzed: {json.dumps(result)[:200]}")
            return
        if job["kind"] == "finalize_video":
            # Путь результата приходит из params постановки: claim для любого
            # kind предлагает suggested-путь клина ('/sources/clean/…'), и для
            # финализации он заведомо чужой.
            output_object_name = str(
                (job.get("params") or {}).get("output_object_name") or ""
            )
            if not output_object_name:
                raise RuntimeError("finalize_output_object_name_missing")
            output_path = os.path.join(workdir, "final.mp4")
            result = finalize_video(source_path, output_path, job, workdir)
            rpc("system_heartbeat_media_preparation", {
                "job_id": job_id, "worker_id": WORKER_ID,
            })
            upload(job["bucket"], output_object_name, output_path, upsert=True)
            rpc("system_complete_video_finalization", {
                "job_id": job_id,
                "worker_id": WORKER_ID,
                "object_name": output_object_name,
                "sha256": sha256_of(output_path),
                "size_bytes": os.path.getsize(output_path),
                "duration_seconds": result.get("duration_seconds"),
                "width": result.get("width"),
                "height": result.get("height"),
                "result": result,
            })
            log(f"job {job_id} finalized video ready")
            return
        if job["kind"] != "clean_master":
            raise RuntimeError(f"unknown_job_kind: {job['kind']}")
        output_path = os.path.join(workdir, "clean.mp4")
        result = clean_master(source_path, output_path, job)
        rpc("system_heartbeat_media_preparation", {
            "job_id": job_id, "worker_id": WORKER_ID,
        })
        upload(job["bucket"], job["suggested_output_object_name"], output_path)
        rpc("system_complete_media_clean_master", {
            "job_id": job_id,
            "worker_id": WORKER_ID,
            "object_name": job["suggested_output_object_name"],
            "sha256": sha256_of(output_path),
            "size_bytes": os.path.getsize(output_path),
            "duration_seconds": result.get("duration_seconds"),
            "width": result.get("width"),
            "height": result.get("height"),
            "result": result,
        })
        log(f"job {job_id} clean master ready")


def main() -> int:
    if not SUPABASE_URL or not SERVICE_KEY:
        log("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are required")
        return 2
    log(f"started, poll={POLL_SECONDS}s")
    while True:
        try:
            claimed = rpc("system_claim_media_preparation", {
                "worker_id": WORKER_ID,
            })
            ping_healthcheck()
            job = claimed.get("job")
            if not job:
                time.sleep(POLL_SECONDS)
                continue
            try:
                handle(job)
            except Exception as error:  # noqa: BLE001 — отказ уходит в очередь
                log(f"job {job.get('job_id')} failed: {error}")
                rpc("system_fail_media_preparation", {
                    "job_id": job.get("job_id"),
                    "worker_id": WORKER_ID,
                    "error": str(error)[:2000],
                })
        except urllib.error.URLError as error:
            log(f"network error: {error}")
            time.sleep(max(POLL_SECONDS, 5))
        except Exception as error:  # noqa: BLE001 — воркер живучий
            log(f"loop error: {error}")
            time.sleep(max(POLL_SECONDS, 5))


if __name__ == "__main__":
    sys.exit(main())
