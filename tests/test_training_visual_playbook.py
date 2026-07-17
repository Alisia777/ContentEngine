import json
import hashlib
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_MIGRATION = ROOT / "supabase/migrations/202607140005_training_visual_playbook.sql"
BASE_SQL = BASE_MIGRATION.read_text(encoding="utf-8")
LANGUAGE_MIGRATION = ROOT / "supabase/migrations/202607150001_premium_training_language.sql"
LANGUAGE_SQL = LANGUAGE_MIGRATION.read_text(encoding="utf-8")
SQL = LANGUAGE_SQL
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
    "publishing_funnel": "Блок 3 · Instagram, YouTube и VK",
    "security_wb": "Блок 4 · Подменный артикул и деньги",
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
    # Four authored course updates plus one fail-closed bulk sanitization of
    # those same course questions before the transaction commits.
    assert SQL.casefold().count("update content_factory.training_modules") == 5
    assert "from rewritten_questions rewritten" in SQL.casefold()


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

        knowledge_check = content["knowledge_check"]
        questions = knowledge_check["questions"]
        assert isinstance(knowledge_check["title"], str) and len(knowledge_check["title"]) >= 8
        assert isinstance(questions, list) and len(questions) >= 3
        assert knowledge_check["pass_score"] == len(questions)
        assert len({question["id"] for question in questions}) == len(questions)
        for question in questions:
            assert re.fullmatch(r"[a-z0-9_]{3,80}", question["id"])
            assert isinstance(question["prompt"], str) and len(question["prompt"]) >= 20
            assert isinstance(question["explanation"], str) and len(question["explanation"]) >= 30
            assert len(question["options"]) >= 3
            option_values = {option["value"] for option in question["options"]}
            assert question["correct_value"] in option_values
            assert all(option["label"] for option in question["options"])

        lessons = content["lessons"]
        assert isinstance(lessons, list) and len(lessons) >= 5
        assert len({lesson["id"] for lesson in lessons}) == len(lessons)
        if course_code == "publishing_funnel":
            assert len(lessons) >= 12
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


def test_first_block_starts_with_invitation_and_a_zero_experience_route() -> None:
    factory = _dollar_quoted_json()["factory_basics"]
    first_lesson = factory["lessons"][0]
    copy = json.dumps(first_lesson, ensure_ascii=False).casefold()

    assert first_lesson["id"] == "first_access_route"
    for required in (
        "самостоятельной регистрации",
        "рабочую почту",
        "приглашение",
        "временным персональным паролем",
        "пароль",
        "четыре блока",
        "экзамен",
        "материалы",
        "создание видео",
        "последние запуски",
    ):
        assert required in copy


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
    assert lessons["shoot_vertical_source"]["visual"]["window_title"] == "Камера телефона"
    assert len(lessons["shoot_vertical_source"]["visual"]["panels"]) == 6
    assert lessons["shoot_vertical_source"]["practice"]["eyebrow"] == "Практика с телефоном"
    assert len(lessons["shoot_vertical_source"]["practice"]["steps"]) >= 4


def test_publishing_course_teaches_instagram_youtube_and_vk_end_to_end() -> None:
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
        "ссылка на пост",
        "views",
        "reach",
        "interactions",
        "9:16",
        "720p",
        "30 кадров в секунду",
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
        "ссылка на пост",
        "views",
        "engaged views",
        "watch time",
        "до 3 минут",
    ):
        assert required in youtube

    access = json.dumps(lessons["social_account_access"], ensure_ascii=False).casefold()
    for required in ("instagram", "youtube", "vk", "руководитель", "роль", "общий пароль"):
        assert required in access

    vk_setup = json.dumps(
        lessons["vk_id_and_business_community"], ensure_ascii=False
    ).casefold()
    assert lessons["vk_id_and_business_community"]["reviewed_at"] == "2026-07-14"
    for required in (
        "vk id",
        "vk.com/groups?w=groups_create_new",
        "бизнес-сообщество",
        "клипы",
        "видео",
        "роль",
        "общий пароль",
    ):
        assert required in vk_setup

    vk = json.dumps(lessons["vk_clips_step_by_step"], ensure_ascii=False).casefold()
    assert lessons["vk_clips_step_by_step"]["reviewed_at"] == "2026-07-14"
    for required in (
        "профиль",
        "сообщество",
        "клипы",
        "одобрен",
        "описание",
        "обложк",
        "9:16",
        "1080p",
        "стен",
        "опубликовать",
        "ссылка на пост",
        "показател",
    ):
        assert required in vk


def test_four_blocks_have_their_own_story_checks() -> None:
    catalog = _dollar_quoted_json()
    expected_topics = {
        "factory_basics": ("приглаш", "материал", "платн"),
        "video_quality": ("телефон", "8 секунд", "видео готово"),
        "publishing_funnel": ("instagram", "youtube", "vk", "накрут", "реклам"),
        "security_wb": ("подмен", "начислен", "выплачен"),
    }
    expected_question_counts = {
        "factory_basics": 3,
        "video_quality": 3,
        "publishing_funnel": 5,
        "security_wb": 3,
    }

    for course_code, topics in expected_topics.items():
        check_copy = json.dumps(
            catalog[course_code]["knowledge_check"], ensure_ascii=False
        ).casefold()
        assert (
            len(catalog[course_code]["knowledge_check"]["questions"])
            == expected_question_counts[course_code]
        )
        assert all(topic in check_copy for topic in topics)


def test_new_account_safety_rejects_fake_warmup_and_ban_evasion() -> None:
    publishing = _dollar_quoted_json()["publishing_funnel"]
    lessons = {lesson["id"]: lesson for lesson in publishing["lessons"]}
    safety = json.dumps(lessons["new_account_safe_start"], ensure_ascii=False).casefold()

    assert lessons["new_account_safe_start"]["reviewed_at"] == "2026-07-14"
    for required in (
        "двухфактор",
        "оригинальн",
        "покупк",
        "бот",
        "follow-unfollow",
        "массов",
        "account status",
        "апелляц",
        "не создавайте клон",
    ):
        assert required in safety


def test_advertising_lesson_stops_unclassified_or_prohibited_placement() -> None:
    publishing = _dollar_quoted_json()["publishing_funnel"]
    lessons = {lesson["id"]: lesson for lesson in publishing["lessons"]}
    advertising = json.dumps(
        lessons["advertising_classification_and_labeling"], ensure_ascii=False
    ).casefold()

    assert lessons["advertising_classification_and_labeling"]["reviewed_at"] == "2026-07-14"
    for required in (
        "справочно-информационный материал",
        "отсутствие оплаты",
        "не означает, что публикация не реклама",
        "внутреннее решение",
        "не обязательное заключение для фас или суда",
        "руководитель или юрист",
        "пометку «реклама»",
        "полное фио рекламодателя-физлица",
        "полное наименование юридического лица",
        "оператором рекламных данных",
        "идентификатор рекламы присваивает оператор рекламных данных",
        "сама по себе не заменяет",
        "проверена на дату выхода",
        "проверка должна быть зафиксирована на дату публикации",
        "не публиковать",
        "платное партнёрство",
        "не отключайте обязательную бирку платформы",
        "ресурс нежелательной организации",
        "экстремизм либо терроризм",
        "доступ к которому ограничен по закону",
        "маркировка не легализует запрещённое размещение",
    ):
        assert required in advertising

    check = {
        question["id"]: question
        for question in publishing["knowledge_check"]["questions"]
    }["advertising_gate"]
    check_copy = json.dumps(check, ensure_ascii=False).casefold()
    assert check["correct_value"] == "stop"
    for required in (
        "оплаты, призыва, промокода и ссылки для перехода нет",
        "не проверил площадку на дату публикации",
        "не означает, что публикация не реклама",
        "не обязательное заключение для фас или суда",
    ):
        assert required in check_copy


def test_substitute_article_and_payout_are_explained_without_hidden_formula() -> None:
    security = _dollar_quoted_json()["security_wb"]
    lessons = {lesson["id"]: lesson for lesson in security["lessons"]}

    alias = json.dumps(lessons["wb_alias_history"], ensure_ascii=False).casefold()
    for required in ("подменный артикул", "того же товара", "вкус", "объём", "исполнитель не выбирает"):
        assert required in alias

    payout = json.dumps(lessons["calculation_and_payout"], ensure_ascii=False).casefold()
    for required in (
        "фиксирован",
        "0 ₽",
        "ссылкой на пост",
        "ожидает проверки",
        "выплачено",
        "вне портала",
        "просмотры",
    ):
        assert required in payout


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


def test_training_copy_matches_the_current_workspace_and_updates_existing_cloud_rows() -> None:
    assert hashlib.sha256(BASE_MIGRATION.read_bytes()).hexdigest() == (
        "e67cbf8a17e03c69f1e3d6b8a2523b119f0dc254994b79f424793636497daac0"
    )
    catalog_copy = json.dumps(_dollar_quoted_json(), ensure_ascii=False)
    for stale in (
        "Медиатека",
        "Final URL",
        "final URL",
        "SUCCEEDED",
        "approved MP4",
        "Approved MP4",
    ):
        assert stale not in catalog_copy

    for current in (
        "Материалы",
        "Создание видео",
        "Публикации",
        "Результаты",
        "ссылка на пост",
        "проверка качества",
    ):
        assert current.casefold() in catalog_copy.casefold()

    lowered = LANGUAGE_SQL.casefold()
    assert LANGUAGE_SQL.lstrip().casefold().startswith("begin;")
    assert LANGUAGE_SQL.rstrip().casefold().endswith("commit;")
    assert "forward-only authoritative snapshot" in lowered
    assert lowered.index("drop constraint if exists training_modules_no_public_course_answer_keys") < lowered.index(
        "update content_factory.training_modules"
    )
    assert "update content_factory.training_modules" in lowered
    assert "insert into content_factory.training_questions" in lowered
    assert "insert into content_factory_private.training_answer_keys" in lowered
    assert "from rewritten_questions rewritten" in lowered
    assert "premium_training_language_contract_failed" in lowered


def test_migration_fails_closed_if_course_or_exam_contract_drifts() -> None:
    lowered = SQL.casefold()
    assert "premium_training_language_contract_failed" in lowered
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
        "knowledge_check",
    ):
        assert f"meta.{metadata_key}" in APP
    assert "? content.meta : content" in APP

    for collection_key in VISUAL_COLLECTIONS.values():
        assert f"visual.{collection_key}" in APP
    for visual_type in VISUAL_TYPES:
        assert f'type === "{visual_type}"' in APP or f"{visual_type}: visual." in APP

    assert "escapeHtml(course.level)" in APP
    assert "escapeHtml(course.blockLabel)" in APP
    assert "escapeHtml(question.prompt)" in APP
    assert "escapeHtml(option.label)" in APP
    assert "escapeHtml(item)" in APP
    assert "escapeHtml(windowTitle)" in APP
    assert 'escapeHtml(practice.eyebrow || "Попробуйте в кабинете")' in APP
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
    assert 'id="course-check-form"' in APP
    assert 'form.id === "course-check-form"' in APP
    assert "state.courseCheckResults[moduleCode]?.passed" in APP
    assert "syncCourseCompletionButton()" in APP
    assert "Начать с блока 1" in APP
    assert "Подменный артикул" in APP
    assert "payout_minor" in APP
    assert 'tabindex="-1"' in APP
    assert "prefers-reduced-motion: reduce" in APP

    assert 'role="progressbar"' in APP
    assert 'aria-live="polite"' in APP
    assert 'aria-current="page"' in APP
    assert 'aria-controls="mobile-navigation"' in APP

    assert './styles.css?v=20260716.4' in INDEX
    assert './config.js?v=20260716.2' in INDEX
    assert './app.js?v=20260717.1' in INDEX
    assert './supabase-api.js?v=20260717.1' in APP
    assert './catalog.js?v=20260716.3' in APP
