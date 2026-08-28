"""Курс академии «Видео для ИИ: простое и плохое» (28.08.2026, v1).

Академия отставала от продукта; новый модуль учит денежному навыку —
отличать исходник, который ИИ обработает хорошо, от исходника, который
сожжёт запуск, и вести к штатным инструментам («Проанализировать»,
«Создать чистый мастер», ползунок качества, «Гипотеза запуска»).
Прод проверен живой пробой: creator_bootstrap отдаёт 6 модулей, новый
курс с 6 уроками стоит между video_quality и publishing_funnel.
"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/202608280001_training_ai_source_quality_course.sql"
).read_text(encoding="utf-8")
COURSE = json.loads(MIGRATION.split("$course$")[1])


def test_course_json_is_coherent() -> None:
    lesson_ids = {lesson["id"] for lesson in COURSE["lessons"]}
    grouped = [i for group in COURSE["lesson_groups"] for i in group["lesson_ids"]]
    assert set(grouped) == lesson_ids
    assert len(grouped) == len(lesson_ids) == 6
    questions = {q["id"] for q in COURSE["knowledge_check"]["questions"]}
    remediation = COURSE["knowledge_remediation"]
    assert set(remediation) == questions
    assert all(item["lesson_id"] in lesson_ids for item in remediation.values())
    # Аттестация проходима и не пустая.
    assert 1 <= COURSE["knowledge_check"]["pass_score"] <= len(questions)


def test_course_teaches_the_real_product_not_a_generic_theory() -> None:
    text = MIGRATION
    # Уроки ведут к штатным инструментам, а не к абстракциям.
    for marker in (
        "Проанализировать",
        "Создать чистый мастер",
        "Быстрее и дешевле",
        "Гипотеза запуска",
        "Запись экрана",
        "9:16",
    ):
        assert marker in text, marker
    # Денежная рамка: проверка исходника до платного запуска.
    assert "платн" in text
    # Чистый мастер не перезаписывает исходник — как в воркере (202608270003).
    assert "не перезаписывается" in text or "Исходник цел" in text


def test_seed_is_idempotent_and_active_between_neighbours() -> None:
    assert "on conflict (code) do update set" in MIGRATION
    assert "'ai_source_quality'" in MIGRATION
    assert "35," in MIGRATION  # между video_quality (30) и publishing_funnel (40)
    assert "updated_at = now()" in MIGRATION
