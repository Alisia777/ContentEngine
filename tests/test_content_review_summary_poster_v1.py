"""Focused contract for the non-interactive completed-review summary poster."""

import json
from pathlib import Path
import subprocess
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_workspace_notification_center_v491 import _run_exact_viewport  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
GUIDED = (APP_DIR / "workspace-os-v4-review-guided.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-os-v4-review-guided.css").read_text(encoding="utf-8")
HARNESS = ROOT / "tests" / "fixtures" / "content_review_summary_poster_v1_harness.html"


def test_pending_video_result_has_one_player_and_a_url_free_canvas_poster() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = rf"""
globalThis.window = {{ location: {{ href: "https://portal.test/" }} }};
const {{ contentReviewWorkspaceMarkup }} = await import({json.dumps(module_url)});
const run = {{
  id: "00000000-0000-4000-8000-000000000101",
  status: "completed",
  media: {{
    id: "00000000-0000-4000-8000-000000000102",
    name: "review-result.mp4",
    mime_type: "video/mp4",
    kind: "generated_video",
    status: "ready",
    signed_url: "https://example.test/private/review-result.mp4"
  }},
  input: {{
    platform: "tiktok",
    content_kind: "advertising",
    product_category: "electronics"
  }},
  result: {{
    overall_score: 82,
    compliance_status: "pass_with_warnings",
    findings: []
  }}
}};
for (const canDecide of [false, true]) {{
  const html = contentReviewWorkspaceMarkup({{
    catalog: {{ media: [], runs: [run] }},
    currentRun: run,
    canDecide,
    view: "current"
  }});
  const videos = html.match(/<video\b/g) || [];
  const canvases = html.match(/<canvas\b/g) || [];
  const signedUses = html.match(/https:\/\/example\.test\/private\/review-result\.mp4/g) || [];
  if (videos.length !== 1) throw new Error(`expected one exact player, got ${{videos.length}}`);
  if (canvases.length !== 1) throw new Error(`expected one canvas poster, got ${{canvases.length}}`);
  if (signedUses.length !== 1) throw new Error(`signed URL duplicated into poster: ${{signedUses.length}}`);
  if (!html.includes("data-content-review-summary-poster")) throw new Error("summary poster missing");
  if (!html.includes("data-content-review-summary-poster-label")) throw new Error("poster state label missing");
  if (!html.includes('controls preload="metadata" playsinline')) throw new Error("exact player contract changed");
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_poster_is_painted_from_the_existing_exact_media_without_a_second_video() -> None:
    for marker in (
        "function bindSummaryPoster(",
        "function paintSummaryPoster(",
        'q("[data-content-review-exact-media]", result)',
        'q(".content-review-readonly-preview .content-review-decision-preview__media", result)',
        'media.addEventListener("loadeddata", onReady)',
        'media.addEventListener("load", onReady)',
        'context.drawImage(media, offsetX, offsetY, drawWidth, drawHeight)',
        "updateSummaryPosterState(",
        '"ready",',
        "bindSummaryPoster(result)",
    ):
        assert marker in GUIDED

    assert 'document.createElement("video")' not in GUIDED
    assert "signed_url" not in GUIDED
    assert "signedUrl" not in GUIDED


def test_poster_and_glass_visuals_are_guided_scoped_and_motion_safe() -> None:
    assert 'data-content-review-summary-poster' in VIEW
    assert '<canvas class="content-review-summary-poster__canvas"' in VIEW
    assert 'data-ce-v4-review-guided="true"' in CSS
    assert ".content-review-summary-poster" in CSS
    assert '@media (prefers-reduced-motion: no-preference)' in CSS
    assert '@media (prefers-reduced-motion: reduce)' in CSS
    assert "ce-v4-review-poster-orbit" in CSS

    # Risk semantics remain distinct on the dark glass surface.
    for marker in (
        ".content-review-compliance.is-block",
        ".content-review-compliance:is(.is-review, .is-warning)",
        ".content-review-compliance.is-pass",
        "--review-danger: #ff718a",
        "--review-warning: #f2b85c",
        "--review-success: #55d9a3",
    ):
        assert marker in CSS


def test_human_decision_guardrails_remain_present() -> None:
    for marker in (
        "Финальное решение человека",
        'name="media_watched_confirmed"',
        "data-review-decision-submit disabled",
        "После сохранения решение нельзя переписать",
        "Результат AI — только подсказка",
    ):
        assert marker in VIEW


def test_canvas_poster_hydrates_in_chrome_without_becoming_interactive() -> None:
    expression = r"""
JSON.stringify((() => {
  const result = document.querySelector('.content-review-result');
  const poster = result.querySelector('[data-content-review-summary-poster]');
  const canvas = poster.querySelector('canvas');
  const panel = result.querySelector('.ce-v4-review-panel:not([hidden])');
  return {
    state: poster.dataset.summaryPosterState,
    bound: poster.dataset.summaryPosterBound,
    canvasWidth: canvas.width,
    canvasHeight: canvas.height,
    buttons: poster.querySelectorAll('button, a, input, video').length,
    canvasOpacity: getComputedStyle(canvas).opacity,
    panelBackground: getComputedStyle(panel).backgroundImage,
    guideBackground: getComputedStyle(result.querySelector('.ce-v4-review-guide')).backgroundColor,
    danger: getComputedStyle(result).getPropertyValue('--review-danger').trim(),
    warning: getComputedStyle(result).getPropertyValue('--review-warning').trim(),
    success: getComputedStyle(result).getPropertyValue('--review-success').trim(),
  };
})())
"""
    result = _run_exact_viewport(1280, 820, expression, HARNESS)

    assert result["state"] == "ready"
    assert result["bound"] == "true"
    assert result["canvasWidth"] == 640
    assert result["canvasHeight"] == 360
    assert result["buttons"] == 0
    assert float(result["canvasOpacity"]) > 0.75
    assert "linear-gradient" in result["panelBackground"]
    assert result["guideBackground"] != "rgb(14, 12, 10)"
    assert result["danger"] == "#ff718a"
    assert result["warning"] == "#f2b85c"
    assert result["success"] == "#55d9a3"
