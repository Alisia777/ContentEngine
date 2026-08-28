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


def test_old_courses_no_longer_teach_july_modes() -> None:
    """Актуализация 28.08 (202608280002/0003, применено в прод, проверено
    SQL-сверкой: ни 2K, ни Gen-4/Seedance, ни июльских цен в уроках): уроки
    описывают стратегии «Копия»/«Создание»/«Дуэт» и ползунок качества."""
    refresh = (
        ROOT / "supabase/migrations/202608280002_training_courses_refresh_strategies.sql"
    ).read_text(encoding="utf-8")
    visual = (
        ROOT / "supabase/migrations/202608280003_training_factory_basics_decision_visual.sql"
    ).read_text(encoding="utf-8")
    for text, name in ((refresh, "refresh"), (visual, "visual")):
        assert "«Копия»" in text, name
        assert "Дуэт" in text, name
        assert "ползунок" in text.lower(), name
        # Fail-closed: без старого текста миграция падает, а не молчит.
        assert "raise exception" in text, name
        assert "not like '%2K%'" in text or "not ilike '%2K%'" in text, name


def test_academy_palette_is_cold_not_copper_brown() -> None:
    """Перекраска академии (фидбек владельца 28.08: «коричневый — это
    старый»): холст и акценты #/learn приведены к рабочему столу. Старые
    медно-коричневые литералы в learn-CSS запрещены."""
    app = ROOT / "web" / "app"
    banned = (
        "#e78345", "#ffad73", "#a94c20", "#0c0a09", "#191512", "#fff8ef",
        "#8c6722", "#a67820", "rgba(231, 131, 69", "rgba(240, 154, 96",
        "rgba(24, 21, 18", "rgba(244, 226, 202",
    )
    for name in (
        "learning-premium.css", "learning-premium-components.css",
        "learning-premium-motion.css", "training-journey.css",
        "training-media-cards.css", "training-interactive.css",
        "training-platform-simulators.css", "training-practical-review.css",
        "workspace-academy-lab-v3.css", "workspace-academy-os-v2.css",
    ):
        css = (app / name).read_text(encoding="utf-8").lower()
        for literal in banned:
            assert literal not in css, (name, literal)
    premium = (app / "learning-premium.css").read_text(encoding="utf-8")
    assert "--learn-canvas: #070b12" in premium
    assert "--learn-copper: #d7ad59" in premium
