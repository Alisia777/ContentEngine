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


def log(message: str) -> None:
    print(f"[media-worker {WORKER_ID}] {message}", flush=True)


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


def upload(bucket: str, object_name: str, source_path: str) -> None:
    with open(source_path, "rb") as source:
        body = source.read()
    request = urllib.request.Request(
        f"{SUPABASE_URL}/storage/v1/object/{bucket}/{object_name}",
        data=body,
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "video/mp4",
            "x-upsert": "false",
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
