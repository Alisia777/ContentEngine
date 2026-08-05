from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240009_generation_prompt_autopilot_training.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web/app/catalog.js").read_text(encoding="utf-8")


def test_training_teaches_all_paid_content_modes_and_current_prices() -> None:
    for expected in (
        "квадратное фото 2K примерно за $0.04",
        "5 секунд без речи примерно за $0.25",
        "8 секунд с голосом примерно за $2.32",
        "безопасное ТЗ",
        "Где находится создание контента",
        "Статус «Готово» означает наличие файла, но не его одобрение",
    ):
        assert expected in MIGRATION
    assert "Платный запуск на 148 ₽" not in MIGRATION


def test_training_preserves_assessment_identity_while_updating_the_scenario() -> None:
    assert "course_check_factory_basics_paid_start" in MIGRATION
    assert "stop_correct_confirm" in MIGRATION
    assert "Восстановить безопасное авто-ТЗ" in MIGRATION
    assert "update content_factory.training_questions" in MIGRATION
    assert "'{knowledge_check,questions}'" in MIGRATION
    assert "'{knowledge_remediation,course_check_factory_basics_paid_start,tip}'" in MIGRATION


def test_training_navigation_maps_to_the_simplified_generation_action() -> None:
    assert '["generation", "Создание контента", "✦"]' in CATALOG
    assert 'label: "Создать"' in APP
    assert 'data-action="restore-auto-generation-brief"' not in APP
    assert "Портал сам подготовит техническое ТЗ при запуске" in APP
    assert "ensureApprovedGenerationSpecForPaidStart" in APP
    assert "compileSafeGenerationBrief" in APP
    assert "generationPromptInspection(form)" in APP


def test_training_migration_is_transactional_and_self_checks() -> None:
    normalized = MIGRATION.lower()
    assert normalized.startswith("begin;")
    assert normalized.rstrip().endswith("commit;")
    assert "generation prompt autopilot training contract failed" in normalized
    assert "generation prompt autopilot assessment contract failed" in normalized
