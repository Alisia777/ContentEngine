import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "web" / "app" / "account-launch-visual-examples.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web" / "app" / "account-launch-visual-examples.css").read_text(encoding="utf-8")


def _run_visual_javascript(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable visual-example contracts")

    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "visual-examples.mjs").write_text(MODULE, encoding="utf-8")
        (module_directory / "contract.mjs").write_text(
            "import * as visual from './visual-examples.mjs';\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=module_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_all_three_platforms_have_the_same_complete_five_step_route():
    contract = _run_visual_javascript(
        """
        const entries = Object.entries(visual.ACCOUNT_LAUNCH_VISUAL_EXAMPLES);
        return {
          order: visual.ACCOUNT_VISUAL_STEP_ORDER,
          platforms: Object.fromEntries(entries.map(([slug, guide]) => [slug, {
            name: guide.name,
            format: guide.format,
            steps: Object.keys(guide.steps),
            hotspotCounts: Object.values(guide.steps).map((step) => step.hotspots.length),
            screenItemCounts: Object.values(guide.steps).map((step) => step.screen.items.length),
          }])),
          frozen: Object.isFrozen(visual.ACCOUNT_LAUNCH_VISUAL_EXAMPLES)
            && entries.every(([, guide]) => Object.isFrozen(guide) && Object.isFrozen(guide.steps)),
        };
        """
    )

    expected_steps = ["access", "profile", "upload", "disclosure", "link"]
    assert contract["order"] == expected_steps
    assert contract["platforms"] == {
        "instagram": {
            "name": "Instagram",
            "format": "Reels",
            "steps": expected_steps,
            "hotspotCounts": [3, 3, 3, 3, 3],
            "screenItemCounts": [3, 3, 3, 3, 3],
        },
        "youtube": {
            "name": "YouTube",
            "format": "Shorts",
            "steps": expected_steps,
            "hotspotCounts": [3, 3, 3, 3, 3],
            "screenItemCounts": [3, 3, 3, 3, 3],
        },
        "vk": {
            "name": "VK",
            "format": "VK Клипы",
            "steps": expected_steps,
            "hotspotCounts": [3, 3, 3, 3, 3],
            "screenItemCounts": [3, 3, 3, 3, 3],
        },
    }
    assert contract["frozen"] is True


def test_markup_is_code_native_keyboard_accessible_and_self_explanatory():
    markup = _run_visual_javascript(
        """
        return visual.accountLaunchVisualExamplesMarkup({
          platform: "youtube",
          step: "disclosure",
          hotspot: 2,
          instanceId: "lesson <youtube>",
        });
        """
    )

    assert 'data-av-instance="lesson-youtube"' in markup
    assert len(re.findall(r'<button[^>]+data-av-platform="', markup)) == 3
    assert len(re.findall(r'<button[^>]+data-av-step="', markup)) == 5
    assert len(re.findall(r'<button[^>]+data-av-hotspot="', markup)) == 3
    assert 'aria-current="step"' in markup
    assert 'aria-pressed="true"' in markup
    assert 'aria-describedby="lesson-youtube-caption-2"' in markup
    assert 'aria-controls="lesson-youtube-detail"' in markup
    assert 'role="status" aria-live="polite" aria-atomic="true"' in markup
    assert 'role="group" aria-label="Учебный псевдоэкран:' in markup
    assert "Paid promotion" in markup
    assert "AI use / altered or synthetic content" in markup
    assert "Схема показывает смысл действия" in markup
    assert "<img" not in markup
    assert "http://" not in markup and "https://" not in markup
    assert "tabindex=" not in markup
    assert " style=" not in markup


def test_interaction_state_is_clamped_and_resets_at_safe_boundaries():
    states = _run_visual_javascript(
        """
        const initial = visual.normalizeAccountVisualState({ platform: "unknown", step: "missing", hotspot: 99 });
        const platform = visual.accountVisualStateAfter(initial, { type: "select-platform", platform: "youtube" });
        const disclosure = visual.accountVisualStateAfter(platform, { type: "select-step", step: "disclosure" });
        const hotspot = visual.accountVisualStateAfter(disclosure, { type: "select-hotspot", hotspot: 2 });
        const next = visual.accountVisualStateAfter(hotspot, { type: "move-step", delta: 1 });
        const afterEnd = visual.accountVisualStateAfter(next, { type: "move-step", delta: 1 });
        const invalidPlatform = visual.accountVisualStateAfter(afterEnd, { type: "select-platform", platform: "tiktok" });
        const back = visual.accountVisualStateAfter(invalidPlatform, { type: "move-step", delta: -1 });
        return {
          initial,
          platform,
          disclosure,
          hotspot,
          next,
          afterEnd,
          invalidPlatform,
          back,
          frozen: [initial, platform, disclosure, hotspot, next, afterEnd, invalidPlatform, back].every(Object.isFrozen),
        };
        """
    )

    assert states["initial"] == {"platform": "instagram", "step": "access", "hotspot": 0}
    assert states["platform"] == {"platform": "youtube", "step": "access", "hotspot": 0}
    assert states["disclosure"] == {"platform": "youtube", "step": "disclosure", "hotspot": 0}
    assert states["hotspot"] == {"platform": "youtube", "step": "disclosure", "hotspot": 2}
    assert states["next"] == {"platform": "youtube", "step": "link", "hotspot": 0}
    assert states["afterEnd"] == states["next"]
    assert states["invalidPlatform"] == states["next"]
    assert states["back"] == {"platform": "youtube", "step": "disclosure", "hotspot": 0}
    assert states["frozen"] is True


def test_embedded_lesson_can_lock_the_platform_to_avoid_mixed_guidance():
    markup = _run_visual_javascript(
        """
        return visual.accountLaunchVisualExamplesMarkup({
          platform: "vk",
          lockPlatform: true,
          instanceId: "locked-vk",
        });
        """
    )

    assert 'data-av-platform-current="vk"' in markup
    assert 'data-av-platform-locked="true"' in markup
    assert "Площадка урока" in markup
    assert "VK · VK Клипы" in markup
    assert 'data-av-platform="' not in markup


def test_copy_avoids_exact_ui_promises_and_label_evasion():
    lowered = MODULE.lower()
    for phrase in (
        "учебная схема, а не точная копия интерфейса",
        "названия и расположение элементов меняются",
        "ищите действие по смыслу",
        "актуальной официальной справкой площадки",
        "не предназначен для обхода маркировки",
        "при сомнении не публикуйте",
    ):
        assert phrase in lowered

    for required_term in (
        "instagram",
        "reels",
        "youtube",
        "shorts",
        "vk клипы",
        "branded content",
        "paid promotion",
        "ai use / altered or synthetic content",
        "скопировать ссылку",
    ):
        assert required_term in lowered

    for unsafe_promise in (
        "100%",
        "точно находится",
        "гарантированно не заблокируют",
        "безопасный лимит публикаций",
        "обойти маркировку",
    ):
        assert unsafe_promise not in lowered

    assert not re.search(r"https?://|<img|\.png|\.jpe?g|\.webp", MODULE, flags=re.IGNORECASE)


def test_styles_are_scoped_mobile_first_and_accessible():
    assert STYLES.index(".account-visual-layout") < STYLES.index("@media (min-width: 760px)")
    wide_block = STYLES[STYLES.index("@media (min-width: 1040px)") :]
    assert ".account-visual-layout" in wide_block
    assert "minmax(290px, 0.82fr) minmax(320px, 1.18fr)" in wide_block
    assert "grid-template-columns: minmax(0, 1fr);" in STYLES
    assert "min-width: 0" in STYLES
    assert "width: 100%" in STYLES
    assert "min-height: 44px" in STYLES
    assert "width: 44px" in STYLES
    assert ":focus-visible" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    assert "@media (forced-colors: active)" in STYLES
    assert "position: fixed" not in STYLES
    assert "100vh" not in STYLES
    assert "overflow-x" not in STYLES
    assert "url(" not in STYLES


def test_mount_contract_uses_delegated_native_controls_and_can_be_destroyed():
    for token in (
        'container.addEventListener("click", handleClick)',
        'container.removeEventListener("click", handleClick)',
        'event.target?.closest?.("[data-av-platform], [data-av-step], [data-av-hotspot], [data-av-move]")',
        "container.contains(control)",
        "queueMicrotask",
        "type=\"button\"",
        "destroy:",
    ):
        assert token in MODULE
