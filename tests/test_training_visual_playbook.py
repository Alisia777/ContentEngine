import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202607140005_training_visual_playbook.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")

EXPECTED_COURSES = {
    "factory_basics",
    "video_quality",
    "publishing_funnel",
    "security_wb",
}
EXPECTED_BLOCK_LABELS = {
    "factory_basics": "Блок 1 · Что делать в портале",
    "video_quality": "Блок 2 · Как снять и создать ролик",
    "publishing_funnel": "Блок 3 · Instagram и YouTube",
    "security_wb": "Блок 4 · Контроль и безопасность",
}
VISUAL_TYPES = {
    "workflow",
    "annotated_ui",
    "timeline",
    "comparison",
    "decision",
    "metrics",
}
VISUAL_COLLECTIONS = {
    "workflow": "steps",
    "annotated_ui": "panels",
    "timeline": "segments",
    "comparison": "columns",
    "decision": "branches",
    "metrics": "cards",
}
UNSAFE_CONTENT_KEYS = {"html", "raw_html", "inner_html", "src", "url"}


def _dollar_quoted_json() -> dict[str, dict[str, Any]]:
    matches = list(
        re.finditer(
            r"\$(?P<tag>[a-z][a-z0-9_]*_json)\$"
            r"(?P<body>.*?)"
            r"\$(?P=tag)\$\s*::jsonb",
            SQL,
            flags=re.DOTALL,
        )
    )
    assert len(matches) == 4
    assert SQL.count("::jsonb") == len(matches)

    parsed: dict[str, dict[str, Any]] = {}
    for match in matches:
        course_code = match.group("tag").removesuffix("_json")
        parsed[course_code] = json.loads(match.group("body"))
    return parsed


def _walk_safe_content(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert key.casefold() not in UNSAFE_CONTENT_KEYS
            _walk_safe_content(child)
    elif isinstance(value, list):
        for child in value:
            _walk_safe_content(child)
    elif isinstance(value, str):
        lowered = value.casefold()
        assert "<script" not in lowered
        assert "javascript:" not in lowered
        assert "data:text/html" not in lowered


def test_visual_playbook_updates_exactly_the_four_existing_courses() -> None:
    catalog = _dollar_quoted_json()
    assert set(catalog) == EXPECTED_COURSES

    updated_codes = set(
        re.findall(
            r"where\s+code\s*=\s*'([a-z0-9_]+)'"
            r"\s+and\s+module_type\s*=\s*'course'",
            SQL,
            flags=re.IGNORECASE,
        )
    )
    assert updated_codes == EXPECTED_COURSES
    assert SQL.casefold().count("update content_factory.training_modules") == 4


def test_every_course_has_v2_metadata_and_at_least_five_safe_visual_lessons() -> None:
    catalog = _dollar_quoted_json()
    used_visual_types: set[str] = set()

    for course_code, content in catalog.items():
        assert content["version"] == 2, course_code
        assert content["block_label"] == EXPECTED_BLOCK_LABELS[course_code]
        assert isinstance(content["duration_minutes"], int)
        assert content["duration_minutes"] >= 15
        assert isinstance(content["outcome"], str) and len(content["outcome"]) >= 40

        checklist = content["completion_checklist"]
        assert isinstance(checklist, list) and len(checklist) >= 4
        assert all(isinstance(item, str) and len(item) >= 12 for item in checklist)

        lessons = content["lessons"]
        assert isinstance(lessons, list) and len(lessons) >= 5
        assert len({lesson["id"] for lesson in lessons}) == len(lessons)
        if course_code == "publishing_funnel":
            assert len(lessons) >= 6
        assert sum(lesson["duration_minutes"] for lesson in lessons) == content["duration_minutes"]

        for lesson in lessons:
            assert re.fullmatch(r"[a-z0-9_]{3,80}", lesson["id"])
            assert isinstance(lesson["title"], str) and len(lesson["title"]) >= 8
            assert isinstance(lesson["body"], str) and len(lesson["body"]) >= 80
            assert isinstance(lesson["takeaway"], str) and len(lesson["takeaway"]) >= 30
            assert isinstance(lesson["duration_minutes"], int)
            assert 2 <= lesson["duration_minutes"] <= 10

            visual = lesson["visual"]
            visual_type = visual["type"]
            used_visual_types.add(visual_type)
            assert visual_type in VISUAL_TYPES
            assert isinstance(visual["title"], str) and len(visual["title"]) >= 8

            collection_name = VISUAL_COLLECTIONS[visual_type]
            collection = visual[collection_name]
            assert isinstance(collection, list) and len(collection) >= 2
            assert all(isinstance(item, dict) and item for item in collection)
            if visual_type == "decision":
                assert isinstance(visual["question"], str) and len(visual["question"]) >= 20
            if visual_type == "comparison":
                assert len(collection) == 2
                assert all(isinstance(column.get("items"), list) for column in collection)

        _walk_safe_content(content)

    assert used_visual_types == VISUAL_TYPES


def test_video_course_teaches_a_beginner_to_shoot_a_clean_phone_source() -> None:
    video = _dollar_quoted_json()["video_quality"]
    lessons = {lesson["id"]: lesson for lesson in video["lessons"]}
    shooting = json.dumps(lessons["shoot_vertical_source"], ensure_ascii=False).casefold()

    for required in (
        "свет",
        "9:16",
        "звук",
        "фокус",
        "этикет",
        "дубл",
        "вертикально",
        "телефон",
    ):
        assert required in shooting

    assert lessons["shoot_vertical_source"]["visual"]["type"] == "annotated_ui"
    assert len(lessons["shoot_vertical_source"]["visual"]["panels"]) == 6
    assert len(lessons["shoot_vertical_source"]["practice"]["steps"]) >= 4


def test_publishing_course_teaches_instagram_reels_and_youtube_shorts_end_to_end() -> None:
    publishing = _dollar_quoted_json()["publishing_funnel"]
    lessons = {lesson["id"]: lesson for lesson in publishing["lessons"]}

    instagram = json.dumps(
        lessons["instagram_reels_step_by_step"], ensure_ascii=False
    ).casefold()
    assert lessons["instagram_reels_step_by_step"]["reviewed_at"] == "2026-07-14"
    for required in (
        "аккаунт",
        "upload",
        "caption",
        "аудитори",
        "publish",
        "final url",
        "views",
        "reach",
        "interactions",
        "9:16",
        "720p",
        "30 fps",
    ):
        assert required in instagram

    youtube = json.dumps(
        lessons["youtube_shorts_step_by_step"], ensure_ascii=False
    ).casefold()
    assert lessons["youtube_shorts_step_by_step"]["reviewed_at"] == "2026-07-14"
    for required in (
        "канал",
        "create → upload",
        "title",
        "audience",
        "visibility",
        "publish",
        "final url",
        "views",
        "engaged views",
        "watch time",
        "до 3 минут",
    ):
        assert required in youtube


def test_paid_generation_copy_is_current_and_does_not_claim_paid_ai_is_off() -> None:
    lowered = SQL.casefold()
    stale_phrases = (
        "пока платный ии выключен",
        "платный ии выключен",
        "платная генерация выключена",
        "реальная ии-генерация выключена",
        "provider=mock. денежных списаний нет",
    )
    for phrase in stale_phrases:
        assert phrase not in lowered

    factory_copy = json.dumps(
        _dollar_quoted_json()["factory_basics"],
        ensure_ascii=False,
    ).casefold()
    assert "платные режимы" in factory_copy
    assert "явного подтверждения расхода" in factory_copy


def test_migration_fails_closed_if_course_or_exam_contract_drifts() -> None:
    lowered = SQL.casefold()
    assert "training_visual_catalog_contract_failed" in lowered
    assert "active_course_codes is distinct from expected_course_codes" in lowered
    assert "invalid_content_count <> 0" in lowered
    assert "active_exam_count <> 1" in lowered
    assert "active_exam_code <> 'operator_final_exam'" in lowered
    assert "active_exam_pass_score <> 10" in lowered
    assert "active_exam_declared_questions <> 12" in lowered
    assert "active_exam_actual_questions <> 12" in lowered
    assert "jsonb_array_length(module.content -> 'lessons')" in lowered


def test_spa_consumes_the_v2_schema_without_raw_markup_or_hash_router_regressions() -> None:
    for metadata_key in (
        "duration_minutes",
        "block_label",
        "outcome",
        "completion_checklist",
    ):
        assert f"meta.{metadata_key}" in APP
    assert "? content.meta : content" in APP

    for collection_key in VISUAL_COLLECTIONS.values():
        assert f"visual.{collection_key}" in APP
    for visual_type in VISUAL_TYPES:
        assert f'type === "{visual_type}"' in APP or f"{visual_type}: visual." in APP

    assert "escapeHtml(course.level)" in APP
    assert "escapeHtml(course.blockLabel)" in APP
    assert "escapeHtml(lesson.takeaway)" in APP
    assert "escapeHtml(item?.condition" in APP
    assert "item?.value || item?.formula" in APP
    assert "item?.note || item?.why" in APP
    assert "escapeHtml(visual.question)" in APP
    assert "innerHTML = visual" not in APP
    assert "outerHTML = visual" not in APP

    handle_click = APP[
        APP.index("async function handleClick(event)") : APP.index(
            "async function handleSubmit(event)"
        )
    ]
    submit_generation = APP[
        APP.index("async function submitGenerationBatch(form)") : APP.index(
            "async function submitRealGeneration(form"
        )
    ]
    assert handle_click.count('action === "scroll-to"') == 1
    assert 'action === "scroll-to"' not in submit_generation
    assert 'href="#work-map"' not in APP
    assert 'href="#lesson-' not in APP
    assert 'data-action="scroll-to"' in APP
    assert 'tabindex="-1"' in APP
    assert "prefers-reduced-motion: reduce" in APP

    assert 'role="progressbar"' in APP
    assert 'aria-live="polite"' in APP
    assert 'aria-current="page"' in APP
    assert 'aria-controls="mobile-navigation"' in APP

    for asset in ("styles.css", "config.js", "app.js"):
        assert f'./{asset}?v=20260714.3' in INDEX
    assert './supabase-api.js?v=20260714.3' in APP
    assert './catalog.js?v=20260714.3' in APP
