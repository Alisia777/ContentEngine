from __future__ import annotations

from pathlib import Path
import base64
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
SOURCE = (APP / "workspace-research-video-intake.js").read_text(encoding="utf-8")
STYLES = (APP / "workspace-research-video-intake.css").read_text(encoding="utf-8")


def test_exact_youtube_url_is_an_identity_not_ingested_video_evidence() -> None:
    for marker in (
        "A YouTube page URL is an identity and metadata pointer, not a video file",
        "paid_analysis_allowed: false",
        "required_input: \"lawful_mp4\"",
        "blockUrlOnlySubmit",
        "event.preventDefault()",
        "event.stopImmediatePropagation()",
        "Остановлено до списания",
        "Перейти в Файлы и загрузить MP4",
        "Продолжить исследование рынка без разбора ролика",
    ):
        assert marker in SOURCE

    submit_handler = SOURCE.split(
        'form.addEventListener("submit", (event) => {', 1
    )[1].split("}, { capture: true });", 1)[0]
    assert "mergeResearchVideoReference(" not in submit_handler
    assert "blockUrlOnlySubmit(" in submit_handler


def test_zero_citation_provider_failure_disables_blind_paid_retry() -> None:
    for marker in (
        "zeroCitationProviderFailure",
        "0 цитат",
        "провайдер отклонил запрос",
        "retry.disabled = true",
        "Не повторять: источник не прочитан",
        "Новый такой же запуск платить не нужно",
        "Загрузить MP4 для настоящего разбора",
    ):
        assert marker in SOURCE
    assert ".research-youtube-failure-guard" in STYLES
    assert '[data-source-mode="media-required"]' in STYLES


def test_exact_acceptance_short_still_canonicalizes_without_network_or_spend() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    encoded = base64.b64encode(SOURCE.encode("utf-8")).decode("ascii")
    script = f"""
      const mod = await import('data:text/javascript;base64,{encoded}');
      const values = [
        'https://www.youtube.com/shorts/CXssfXBVInw',
        'https://youtu.be/CXssfXBVInw?si=test',
        'https://www.youtube.com/watch?v=CXssfXBVInw&utm_source=test'
      ].map(mod.canonicalResearchVideoUrl);
      console.log(JSON.stringify(values));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    values = json.loads(result.stdout)
    assert values == ["https://youtube.com/watch?v=CXssfXBVInw"] * 3


def test_youtube_source_gate_is_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    subprocess.run(
        [node, "--check", str(APP / "workspace-research-video-intake.js")],
        check=True,
    )
