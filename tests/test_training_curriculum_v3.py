from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202607180006_training_curriculum_v3_metadata.sql"
)
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
JOURNEY = (ROOT / "web/app/training-journey.js").read_text(encoding="utf-8")


def test_curriculum_v3_migration_is_transactional_and_forward_only() -> None:
    assert MIGRATION.startswith("begin;")
    assert MIGRATION.rstrip().endswith("commit;")
    assert MIGRATION.count("update content_factory.training_modules") >= 7
    assert "do $$" in MIGRATION
    assert "alter table" not in MIGRATION.lower()
    assert "delete from content_factory.training_modules" not in MIGRATION.lower()


def test_curriculum_v3_keeps_stable_course_codes_and_private_grading() -> None:
    for code in (
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    ):
        assert f"where module.code = '{code}'" in MIGRATION
    assert "operator_final_exam" not in MIGRATION
    assert "correct_value" not in MIGRATION
    assert "correct_answer" not in MIGRATION
    assert "content_factory_private" not in MIGRATION


def test_every_course_receives_role_groups_achievement_and_glossary() -> None:
    assert MIGRATION.count("'version', 3") == 4
    assert MIGRATION.count("'role_tracks'") >= 4
    assert MIGRATION.count("'lesson_groups'") >= 4
    assert MIGRATION.count("'achievement'") >= 5
    assert MIGRATION.count("'glossary'") >= 5
    assert MIGRATION.count("'audiences'") >= 30
    assert MIGRATION.count("'required_core'") >= 30
    assert MIGRATION.count("'phase'") >= 30
    assert "training_curriculum_v3_metadata_invalid" in MIGRATION
    assert "training_curriculum_v3_duplicate_lesson" in MIGRATION
    assert "training_curriculum_v3_lesson_group_topology_invalid" in MIGRATION
    assert "training_curriculum_v3_course_order_invalid" in MIGRATION
    assert "not (module.content -> 'role_tracks' ? 'review')" in MIGRATION


def test_social_course_has_explicit_instagram_youtube_and_vk_groups() -> None:
    for platform in ("instagram", "youtube", "vk"):
        assert f"'platform', '{platform}'" in MIGRATION
    assert "advertising_classification_and_labeling" in MIGRATION
    assert "Безопасный публикатор" in MIGRATION


def test_frontend_consumes_server_audience_and_achievement_metadata() -> None:
    assert "meta.audience_label" in APP
    assert "meta.achievement" in APP
    assert "course.achievement.icon" in APP
    assert "course.achievement.name" in APP
    assert "export function roleAwareLessonPath(" in JOURNEY
    assert "roleAwareLessonPath," in APP
    assert "meta.lesson_groups" in APP
    assert "lesson.requiredCore" in JOURNEY
    assert "lesson.audiences.includes(selectedTrack)" in JOURNEY


def test_curriculum_v3_reorders_the_novice_route_and_keeps_common_practice() -> None:
    assert "when 'security_wb' then 20" in MIGRATION
    assert "when 'video_quality' then 30" in MIGRATION
    assert "when 'publishing_funnel' then 40" in MIGRATION
    assert "Блок 2 · товар, безопасность и деньги" in MIGRATION
    assert "Блок 3 · создание и проверка ролика" in MIGRATION
    assert "Блок 4 · публикация и результат" in MIGRATION
    assert "Всем, кто создаёт или проверяет ролик" in MIGRATION
    assert "Всем участникам до передачи на публикацию" in MIGRATION
