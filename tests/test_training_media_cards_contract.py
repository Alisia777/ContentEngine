from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "web/app/assets/training/training-media-catalog.v1.json"
MODULE_PATH = ROOT / "web/app/training-media-cards.js"
STYLES_PATH = ROOT / "web/app/training-media-cards.css"

CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
MODULE = MODULE_PATH.read_text(encoding="utf-8")
STYLES = STYLES_PATH.read_text(encoding="utf-8")


def _run_javascript(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable media-card contracts")

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "training-media-cards.mjs").write_text(MODULE, encoding="utf-8")
        (directory / "catalog.json").write_text(
            json.dumps(CATALOG, ensure_ascii=False),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './training-media-cards.mjs';\n"
            "import { readFileSync } from 'node:fs';\n"
            "const catalog = JSON.parse(readFileSync('./catalog.json', 'utf8'));\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _comparison(comparison_id: str) -> dict:
    return next(
        comparison
        for comparison in CATALOG["comparisons"]
        if comparison["id"] == comparison_id
    )


def _checkpoint(comparison_id: str) -> dict:
    return next(
        checkpoint
        for checkpoint in CATALOG["checkpoints"]
        if checkpoint["comparison_id"] == comparison_id
    )


def _local_asset(raw_url: str) -> Path:
    assert raw_url.startswith("./assets/training/")
    return ROOT / "web/app" / raw_url.removeprefix("./")


def _vtt_cues(source: str) -> list[tuple[float, float, str]]:
    pattern = re.compile(
        r"(?P<start>\d{2}):(\d{2}):(\d{2}\.\d{3})\s+-->\s+"
        r"(?P<end>\d{2}):(\d{2}):(\d{2}\.\d{3})\s*\n"
        r"(?P<text>.*?)(?=\n\n|\Z)",
        flags=re.DOTALL,
    )

    def seconds(parts: tuple[str, str, str]) -> float:
        hours, minutes, raw_seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(raw_seconds)

    cues = []
    for match in pattern.finditer(source):
        start = seconds((match.group(1), match.group(2), match.group(3)))
        end = seconds((match.group(4), match.group(5), match.group(6)))
        cues.append((start, end, match.group("text").strip()))
    return cues


def test_catalog_covers_every_course_and_each_publication_platform() -> None:
    assert CATALOG["schema_version"] == 1
    assert CATALOG["language"] == "ru"
    assert CATALOG["editorial_policy"] == {
        **CATALOG["editorial_policy"],
        "autoplay": False,
        "captions_required_for_video": True,
        "transcript_required": True,
        "draft_caption_notice": True,
    }

    comparisons = CATALOG["comparisons"]
    assert len(comparisons) == 9
    assert {item["module_code"] for item in comparisons} == {
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    }
    joined_platforms = " ".join(item["platform"] for item in comparisons).casefold()
    assert "instagram" in joined_platforms
    assert "youtube" in joined_platforms
    assert "vk" in joined_platforms

    checkpoint_ids = [item["comparison_id"] for item in CATALOG["checkpoints"]]
    comparison_ids = [item["id"] for item in comparisons]
    assert len(checkpoint_ids) == len(set(checkpoint_ids))
    assert checkpoint_ids == comparison_ids


def test_every_side_is_a_distinct_accessible_teaching_unit() -> None:
    for comparison in CATALOG["comparisons"]:
        correct = comparison["correct"]
        mistake = comparison["mistake"]
        assert correct["label"] == "Правильно"
        assert mistake["label"] == "Ошибка"
        assert correct["headline"].casefold() != mistake["headline"].casefold()
        assert correct["reason"].casefold() != mistake["reason"].casefold()
        assert correct["fallback"]["title"].casefold() != mistake["fallback"]["title"].casefold()
        for side in (correct, mistake):
            assert len(side["reason"]) >= 50
            assert len(side["transcript"]) >= 2
            assert side["fallback"]["description"]
            assert len(side["fallback"]["points"]) >= 3
            assert all(item["text"] for item in side["transcript"])


def test_checkpoints_have_plausible_distractors_critical_risks_and_causal_feedback() -> None:
    causal_terms = re.compile(
        r"потому|поэтому|иначе|связ|позвол|сохраня|предотвращ|лома|может|"
        r"не\s+(?:меня|восстанав|отменя|исправля|доказыва|открыва|делает|устраня)|"
        r"повышает|рискует|требует|относится|привязан|получит|доказыва",
        flags=re.IGNORECASE,
    )
    for checkpoint in CATALOG["checkpoints"]:
        options = checkpoint["options"]
        assert 3 <= len(options) <= 5
        assert len({option["id"] for option in options}) == len(options)
        assert len({option["label"].casefold() for option in options}) == len(options)
        assert sum(option["correct"] is True for option in options) == 1
        assert any(option["critical"] is True for option in options)
        assert all(not option["critical"] for option in options if option["correct"])
        for option in options:
            assert len(option["feedback"]) >= 80
            assert causal_terms.search(option["feedback"]), option["feedback"]


def test_product_mismatch_and_disclosure_cases_teach_stop_rules_not_shortcuts() -> None:
    product = _checkpoint("approved-file-full-review")
    assert all(token in product["prompt"] for token in ("Vanilla", "Chocolate"))
    correct_product = next(option for option in product["options"] if option["correct"])
    same_brand = next(option for option in product["options"] if option["id"] == "accept_same_brand")
    assert "вернуть" in correct_product["label"].casefold()
    assert same_brand["critical"] is True
    assert "друг" in same_brand["feedback"].casefold()

    disclosure = _checkpoint("advertising-stop-check")
    assert all(token in disclosure["prompt"].casefold() for token in ("подар", "обязатель", "промокод"))
    correct_disclosure = next(option for option in disclosure["options"] if option["correct"])
    assert all(token in correct_disclosure["label"].casefold() for token in ("черновик", "решен"))
    wrong_disclosure = [option for option in disclosure["options"] if not option["correct"]]
    assert all(option["critical"] for option in wrong_disclosure)
    assert all("не меня" in option["feedback"].casefold() or "не отмен" in option["feedback"].casefold() for option in wrong_disclosure)


def test_forbidden_guarantees_only_appear_as_explicitly_refuted_distractors() -> None:
    forbidden = (
        "100% безопасно",
        "гарантированно не заблокируют",
        "обойдите маркировку",
        "скройте рекламу",
        "автоматически становится обычной",
    )
    correct_copy = " ".join(
        text
        for comparison in CATALOG["comparisons"]
        for text in (
            comparison["correct"]["headline"],
            comparison["correct"]["reason"],
            comparison["correct"]["fallback"]["description"],
        )
    ).casefold()
    assert all(phrase not in correct_copy for phrase in forbidden)

    for checkpoint in CATALOG["checkpoints"]:
        for option in checkpoint["options"]:
            matched = [phrase for phrase in forbidden if phrase in option["label"].casefold()]
            if matched:
                assert option["correct"] is False
                assert option["critical"] is True
                assert option["feedback"].casefold().startswith("критическая ошибка")


def test_all_local_videos_have_posters_russian_vtt_and_full_time_coverage() -> None:
    media_items = [
        side["media"]
        for comparison in CATALOG["comparisons"]
        for side in (comparison["correct"], comparison["mistake"])
        if side.get("media")
    ]
    assert len(media_items) == 2
    assert {Path(item["video_url"]).name for item in media_items} == {
        "ugc_bloody_peel_8s.mp4",
        "ugc_bombbar_pro_8s.mp4",
    }

    for media in media_items:
        video = _local_asset(media["video_url"])
        poster = _local_asset(media["poster_url"])
        captions = _local_asset(media["captions_url"])
        assert video.is_file() and video.stat().st_size > 1_000_000
        assert poster.is_file() and poster.stat().st_size > 100_000
        assert captions.is_file()
        source = captions.read_text(encoding="utf-8")
        assert source.startswith("WEBVTT\n")
        assert "Language: ru" in source
        assert "Редакторский черновик" in source
        assert re.search(r"[А-Яа-яЁё]", source)
        cues = _vtt_cues(source)
        assert len(cues) >= 3
        assert cues[0][0] == 0
        assert cues[-1][1] >= media["duration_seconds"]
        assert all(start < end for start, end, _ in cues)
        assert all(current[1] <= following[0] for current, following in zip(cues, cues[1:]))
        assert sum(end - start for start, end, _ in cues) >= media["duration_seconds"]
        assert media["captions_status"] == "draft_needs_audio_qc"


def test_module_is_isolated_safe_and_renders_video_fallback_transcript_and_cases() -> None:
    for export_name in (
        "normalizeTrainingMediaCatalog",
        "trainingMediaCardsForModule",
        "trainingMediaCardsMarkup",
        "setTrainingMediaCardFocus",
        "evaluateTrainingMediaCheckpoint",
        "bindTrainingMediaCards",
        "stopTrainingMedia",
    ):
        assert f"export function {export_name}(" in MODULE
    assert "window." not in MODULE
    assert "document." not in MODULE
    assert "innerHTML" not in MODULE
    assert "outerHTML" not in MODULE

    payload = _run_javascript(
        r"""
        const normalized = subject.normalizeTrainingMediaCatalog(catalog);
        const moduleItems = subject.trainingMediaCardsForModule(catalog, "video_quality");
        const markup = subject.trainingMediaCardsMarkup(catalog, { moduleCode: "video_quality" });
        const allMarkup = subject.trainingMediaCardsMarkup(catalog);
        const malicious = subject.trainingMediaCardsMarkup({ comparisons: [{
          id: "bad",
          module_code: "video_quality",
          title: "<img src=x onerror=alert(1)>",
          objective: "safe",
          correct: {
            headline: "ok",
            reason: "clean",
            media: { video_url: "javascript:alert(1)", captions_url: "./safe.vtt" },
            fallback: { title: "fallback", description: "safe", points: ["one"] },
            transcript: ["correct transcript"],
          },
          mistake: {
            headline: "bad",
            reason: "risk",
            fallback: { title: "fallback bad", description: "safe", points: ["one"] },
            transcript: ["mistake transcript"],
          },
        }] });
        return {
          count: normalized.comparisons.length,
          moduleCount: moduleItems.length,
          frozen: Object.isFrozen(normalized) && Object.isFrozen(normalized.comparisons) && normalized.comparisons.every((item) => Object.isFrozen(item)),
          markup,
          allMarkup,
          malicious,
        };
        """
    )
    assert payload["count"] == 9
    assert payload["moduleCount"] == 2
    assert payload["frozen"] is True
    markup = payload["markup"]
    assert markup.count("data-training-media-card=") == 2
    assert markup.count("data-training-media-checkpoint=") == 2
    assert markup.count("data-training-media-side=") == 4
    assert markup.count("data-training-media-checkpoint-option") == 6
    assert '<track kind="captions"' in markup
    assert 'srclang="ru"' in markup and " default " in markup
    assert "crossorigin=\"anonymous\"" in markup
    assert "preload=\"none\"" in markup
    assert "autoplay" not in markup
    assert "Текстовый разбор" in markup
    assert "training-media-side__fallback" in markup
    assert "Русские субтитры добавлены как редакторский черновик" in markup
    assert payload["allMarkup"].count("data-training-media-checkpoint=") == 9
    assert "javascript:" not in payload["malicious"]
    assert "<img" not in payload["malicious"]
    assert "&lt;img" in payload["malicious"]


def test_checkpoint_controller_distinguishes_critical_error_and_correct_answer() -> None:
    payload = _run_javascript(
        r"""
        const makeOption = (value, correct, critical, feedback) => ({
          value,
          checked: false,
          dataset: {
            trainingMediaCorrect: String(correct),
            trainingMediaCritical: String(critical),
            trainingMediaFeedback: feedback,
          },
          attributes: {},
          setAttribute(name, value) { this.attributes[name] = String(value); },
        });
        const options = [
          makeOption("safe", true, false, "Точный результат можно проверить."),
          makeOption("critical", false, true, "Неверный товар сломает связь с задачей."),
          makeOption("distractor", false, false, "Ссылка на профиль не доказывает результат."),
        ];
        const feedback = { textContent: "", focusCalls: 0, focus() { this.focusCalls += 1; } };
        const buttons = [
          { dataset: { trainingMediaFocusValue: "correct" }, setAttribute() {} },
          { dataset: { trainingMediaFocusValue: "mistake" }, setAttribute() {} },
        ];
        const sides = [
          { dataset: { trainingMediaSide: "correct" }, classList: { toggle() {} } },
          { dataset: { trainingMediaSide: "mistake" }, classList: { toggle() {} } },
        ];
        const status = { textContent: "" };
        const card = {
          dataset: {},
          matches(selector) { return selector === "[data-training-media-card]"; },
          querySelectorAll(selector) {
            if (selector === "[data-training-media-focus-value]") return buttons;
            if (selector === "[data-training-media-side]") return sides;
            if (selector === "[data-training-media-video]") return [];
            return [];
          },
          querySelector(selector) { return selector === "[data-training-media-status]" ? status : null; },
        };
        const checkpoint = {
          dataset: {},
          matches(selector) { return selector === "[data-training-media-checkpoint]"; },
          closest(selector) { return selector === "[data-training-media-card]" ? card : null; },
          querySelectorAll(selector) { return selector === "[data-training-media-checkpoint-option]" ? options : []; },
          querySelector(selector) { return selector === "[data-training-media-checkpoint-feedback]" ? feedback : null; },
        };
        const critical = subject.evaluateTrainingMediaCheckpoint(checkpoint, "critical");
        const criticalState = checkpoint.dataset.trainingMediaCheckpointState;
        const criticalText = feedback.textContent;
        const correct = subject.evaluateTrainingMediaCheckpoint(checkpoint, "safe");
        return {
          critical,
          criticalState,
          criticalText,
          correct,
          correctState: checkpoint.dataset.trainingMediaCheckpointState,
          correctText: feedback.textContent,
          focusCalls: feedback.focusCalls,
          finalCardFocus: card.dataset.trainingMediaFocus,
        };
        """
    )
    assert payload["critical"] == {
        "selectedId": "critical",
        "correct": False,
        "critical": True,
    }
    assert payload["criticalState"] == "critical"
    assert payload["criticalText"].startswith("Критическая ошибка.")
    assert payload["correct"] == {
        "selectedId": "safe",
        "correct": True,
        "critical": False,
    }
    assert payload["correctState"] == "correct"
    assert payload["correctText"].startswith("Верно.")
    assert payload["focusCalls"] == 2
    assert payload["finalCardFocus"] == "correct"


def test_styles_cover_mobile_keyboard_contrast_motion_and_print_fallbacks() -> None:
    for selector in (
        ".training-media-card__comparison",
        ".training-media-side__fallback",
        ".training-media-side__transcript",
        ".training-media-checkpoint__options",
        ".training-media-checkpoint__feedback",
    ):
        assert selector in STYLES
    assert ":focus-visible" in STYLES
    assert "@media (max-width: 760px)" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    assert "@media (forced-colors: active)" in STYLES
    assert "@media print" in STYLES
    mobile = STYLES.split("@media (max-width: 760px)", 1)[1].split("@media", 1)[0]
    assert re.search(r"\.training-media-card__comparison\s*\{[^}]*grid-template-columns:\s*1fr", mobile, flags=re.DOTALL)
