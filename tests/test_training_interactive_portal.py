from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web/app/training-interactive.js"
STYLES_PATH = ROOT / "web/app/training-interactive.css"
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202607160002_training_interactive_walkthroughs.sql"
)

MODULE = MODULE_PATH.read_text(encoding="utf-8")
STYLES = STYLES_PATH.read_text(encoding="utf-8")
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")

COURSE_CODES = (
    "factory_basics",
    "video_quality",
    "publishing_funnel",
    "security_wb",
)


def _run_javascript(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable training contracts")

    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "training-interactive.mjs").write_text(
            MODULE,
            encoding="utf-8",
        )
        (module_directory / "contract.mjs").write_text(
            "import * as training from './training-interactive.mjs';\n"
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


def _migration_catalog() -> dict[str, list[dict]]:
    catalog: dict[str, list[dict]] = {}
    for code, tag in (
        ("factory_basics", "factory_walkthroughs"),
        ("video_quality", "quality_walkthroughs"),
        ("publishing_funnel", "publishing_walkthroughs"),
        ("security_wb", "security_walkthroughs"),
    ):
        match = re.search(
            rf"'{re.escape(code)}'\s*,\s*\${tag}\$\s*(.*?)\s*\${tag}\$::jsonb",
            MIGRATION,
            flags=re.DOTALL,
        )
        assert match, f"missing interactive walkthrough payload for {code}"
        catalog[code] = json.loads(match.group(1))
    return catalog


def test_module_exports_the_isolated_walkthrough_contract() -> None:
    for export in (
        "normalizeInteractiveWalkthroughs",
        "trainingInteractiveMarkup",
        "setTrainingWalkthroughStep",
        "stopTrainingWalkthrough",
        "trainingWalkthroughStorageKey",
    ):
        assert f"export function {export}(" in MODULE

    assert "window." not in MODULE
    assert "document." not in MODULE
    assert "innerHTML" not in MODULE
    assert "outerHTML" not in MODULE


def test_catalog_includes_real_local_training_video_examples() -> None:
    catalog = _migration_catalog()
    walkthroughs = [
        walkthrough
        for course_walkthroughs in catalog.values()
        for walkthrough in course_walkthroughs
    ]
    videos = [
        walkthrough
        for walkthrough in walkthroughs
        if isinstance(walkthrough.get("video_url"), str)
        and walkthrough["video_url"]
    ]

    assert len(videos) >= 2
    for walkthrough in videos:
        video_path = ROOT / "web/app" / walkthrough["video_url"].removeprefix("./")
        poster_path = ROOT / "web/app" / walkthrough["poster_url"].removeprefix("./")
        assert video_path.is_file() and video_path.stat().st_size > 1_000_000
        assert poster_path.is_file() and poster_path.stat().st_size > 10_000


def test_normalization_and_markup_are_safe_accessible_and_video_ready() -> None:
    payload = _run_javascript(
        r"""
        const raw = [
          {
            id: "safe_demo",
            title: "Видео <разбор>",
            summary: "Один & безопасный маршрут",
            duration_seconds: 72,
            reviewed_at: "2026-07-16",
            video_url: "https://storage.example.test/training/demo.mp4",
            poster_url: "javascript:alert(1)",
            frames: [
              { id: "one", time: "00:00", title: "Первый <кадр>", body: "Начните здесь", cue: "Проверьте товар" },
              { id: "two", time: "00:24", title: "Второй кадр", body: "Продолжите здесь" },
              { id: "three", time: "00:48", title: "Финал", body: "Завершите проверку" },
            ],
            checklist: ["Пункт 1", "Пункт 2"],
            transcript: [
              { time: "00:00", text: "Первая реплика" },
              { time: "00:24", text: "Вторая реплика" },
            ],
          },
          {
            id: "frames_only",
            title: "Покадровая репетиция",
            video_url: "javascript:alert(2)",
            frames: [
              { title: "Шаг A", body: "Действие A" },
              { title: "Шаг B", body: "Действие B" },
            ],
            checklist: ["Готово A", "Готово B"],
          },
          {
            id: "safe_demo",
            title: "Дубликат",
            frames: [
              { title: "A", body: "A" },
              { title: "B", body: "B" },
            ],
          },
          {
            id: "invalid",
            frames: [{ title: "Только один", body: "Недостаточно" }],
          },
        ];
        const normalized = training.normalizeInteractiveWalkthroughs(raw);
        const nested = training.normalizeInteractiveWalkthroughs({
          content: { interactive_walkthroughs: raw },
        });
        const markup = training.trainingInteractiveMarkup("video_quality", raw);
        return {
          ids: normalized.map((item) => item.id),
          nestedIds: nested.map((item) => item.id),
          urls: normalized.map((item) => ({ video: item.videoUrl, poster: item.posterUrl })),
          transcriptCounts: normalized.map((item) => item.transcript.length),
          frozen: Object.isFrozen(normalized) && normalized.every((item) => Object.isFrozen(item) && Object.isFrozen(item.frames)),
          markup,
        };
        """
    )

    assert payload["ids"] == ["safe_demo", "frames_only"]
    assert payload["nestedIds"] == ["safe_demo", "frames_only"]
    assert payload["urls"] == [
        {
            "video": "https://storage.example.test/training/demo.mp4",
            "poster": "",
        },
        {"video": "", "poster": ""},
    ]
    assert payload["transcriptCounts"] == [2, 2]
    assert payload["frozen"] is True

    markup = payload["markup"]
    assert markup.count("data-training-walkthrough=") == 2
    assert markup.count('data-action="training-walkthrough-play"') == 2
    assert markup.count('data-action="training-walkthrough-previous"') == 2
    assert markup.count('data-action="training-walkthrough-next"') == 2
    assert markup.count('data-action="training-walkthrough-reset"') == 2
    assert 'data-training-frame-index="0"' in markup
    assert 'data-training-frame-index="1"' in markup
    assert 'hidden aria-hidden="true"' in markup
    assert 'role="progressbar"' in markup
    assert "data-training-progress-fill" in markup
    assert "data-training-check" in markup
    assert "<details" in markup and "<summary>" in markup
    assert "<video" in markup
    assert 'controls preload="none" playsinline' in markup
    assert "https://storage.example.test/training/demo.mp4" in markup
    assert "javascript:" not in markup
    assert "<iframe" not in markup
    assert "<разбор>" not in markup
    assert "&lt;разбор&gt;" in markup


def test_step_controller_clamps_updates_progress_and_stops_media() -> None:
    payload = _run_javascript(
        r"""
        const makeAttributeNode = () => ({
          attributes: {},
          setAttribute(name, value) { this.attributes[name] = String(value); },
        });
        const frames = [makeAttributeNode(), makeAttributeNode(), makeAttributeNode()];
        const current = { textContent: "" };
        const label = { textContent: "" };
        const progress = makeAttributeNode();
        const fill = { style: {} };
        const previous = { disabled: true };
        const next = { disabled: false };
        const play = makeAttributeNode();
        let pauses = 0;
        const video = { pause() { pauses += 1; } };
        const selectors = new Map([
          ["[data-training-current-step]", current],
          ["[data-training-progress-label]", label],
          ["[data-training-progress]", progress],
          ["[data-training-progress-fill]", fill],
          ['[data-action="training-walkthrough-previous"]', previous],
          ['[data-action="training-walkthrough-next"]', next],
          ['[data-action="training-walkthrough-play"]', play],
        ]);
        const root = {
          dataset: {},
          matches(selector) { return selector === "[data-training-walkthrough]"; },
          querySelectorAll(selector) {
            if (selector === "[data-training-frame]") return frames;
            if (selector === "[data-training-video]") return [video];
            return [];
          },
          querySelector(selector) { return selectors.get(selector) || null; },
        };

        const selected = training.setTrainingWalkthroughStep(root, 99);
        const stopped = training.stopTrainingWalkthrough(root);
        return {
          selected,
          hidden: frames.map((frame) => frame.hidden),
          ariaHidden: frames.map((frame) => frame.attributes["aria-hidden"]),
          current: current.textContent,
          label: label.textContent,
          progress: progress.attributes["aria-valuenow"],
          fill: fill.style.width,
          previousDisabled: previous.disabled,
          nextDisabled: next.disabled,
          step: root.dataset.trainingStep,
          playing: root.dataset.trainingPlaying,
          playPressed: play.attributes["aria-pressed"],
          pauses,
          stopped,
          key: training.trainingWalkthroughStorageKey("user 1", "video_quality", "safe/demo"),
          missingKey: training.trainingWalkthroughStorageKey("", "video_quality", "safe_demo"),
        };
        """
    )

    assert payload == {
        "selected": 2,
        "hidden": [True, True, False],
        "ariaHidden": ["true", "true", "false"],
        "current": "3",
        "label": "100%",
        "progress": "100",
        "fill": "100%",
        "previousDisabled": False,
        "nextDisabled": True,
        "step": "2",
        "playing": "false",
        "playPressed": "false",
        "pauses": 2,
        "stopped": 1,
        "key": "contentengine.training-walkthrough.v1:user%201:video_quality:safe%2Fdemo",
        "missingKey": None,
    }


def test_migration_adds_exactly_two_walkthroughs_to_each_required_course() -> None:
    catalog = _migration_catalog()

    assert tuple(catalog) == COURSE_CODES
    assert sum(len(items) for items in catalog.values()) == 8
    video_examples = 0
    for course_code, walkthroughs in catalog.items():
        assert len(walkthroughs) == 2, course_code
        assert len({item["id"] for item in walkthroughs}) == 2
        for item in walkthroughs:
            assert re.fullmatch(r"[a-z0-9_]{3,80}", item["id"])
            assert item["title"]
            assert item["summary"]
            assert 15 <= item["duration_seconds"] <= 600
            assert item["reviewed_at"] == "2026-07-16"
            if item["video_url"] is None:
                assert item["poster_url"] is None
            else:
                video_examples += 1
                assert item["video_url"].startswith("./assets/training/")
                assert item["poster_url"].startswith("./assets/training/")
            assert len(item["frames"]) >= 3
            assert len(item["transcript"]) >= 3
            assert len(item["checklist"]) >= 3

    assert "'{interactive_walkthroughs}'" in MIGRATION
    assert "jsonb_set(" in MIGRATION
    assert "walkthrough_count <> 8" in MIGRATION
    assert video_examples == 2


def test_migration_is_content_only_and_does_not_change_certification_logic() -> None:
    forbidden = (
        "training_answer_keys",
        "training_certifications",
        "creator_complete_module",
        "creator_submit_course_check",
        "grant execute",
        "revoke all",
    )
    lowered = MIGRATION.lower()
    assert lowered.strip().startswith("begin;")
    assert lowered.strip().endswith("commit;")
    assert lowered.count("begin;") == 1
    assert lowered.count("commit;") == 1
    for token in forbidden:
        assert token not in lowered

    assert "insert into content_factory.training_questions" not in lowered
    assert "alter table content_factory.training_modules" not in lowered
    assert "update content_factory.training_modules" in lowered


def test_styles_are_scoped_responsive_and_accessible() -> None:
    assert STYLES.count(".training-") > 55
    assert ".training-walkthrough__frame[hidden]" in STYLES
    assert "display: none" in STYLES
    assert "min-height: 44px" in STYLES
    assert ":focus-visible" in STYLES
    assert "@media (min-width: 720px)" in STYLES
    assert "@media (min-width: 1080px)" in STYLES
    assert "@media (max-width: 420px)" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    assert "@media (forced-colors: active)" in STYLES
    assert "body {" not in STYLES
    assert ":root" not in STYLES
    assert "position: fixed" not in STYLES
    assert "url(" not in STYLES
    assert "--ti-on-primary: var(--portal-action-ink, #ffffff)" in STYLES
    assert STYLES.count("color: var(--ti-on-primary)") >= 4
