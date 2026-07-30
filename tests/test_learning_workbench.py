from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "web/app/learning-workbench.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/learning-workbench.css").read_text(encoding="utf-8")


def test_learning_workbench_assets_are_versioned_and_loaded_last() -> None:
    assert './learning-workbench.css?v=20260730.1' in INDEX
    assert './learning-workbench.js?v=20260730.1' in INDEX
    assert INDEX.index("interface-system.css") < INDEX.index(
        "learning-workbench.css"
    )
    assert INDEX.index("app.js") < INDEX.index("learning-workbench.js")


def test_learning_home_becomes_a_keyboard_accessible_desktop() -> None:
    assert '"learning-workbench"' in SCRIPT
    assert 'role: "tablist"' in SCRIPT
    assert 'role: "tabpanel"' in SCRIPT
    assert "aria-selected" in SCRIPT
    assert "ArrowDown" in SCRIPT
    assert "ArrowRight" in SCRIPT
    assert "Home" in SCRIPT
    assert "End" in SCRIPT
    assert "document.startViewTransition" in SCRIPT


def test_current_task_advances_only_after_confirmed_course_completion() -> None:
    assert 'data-action="complete-course"' in SCRIPT
    assert "courseIsConfirmedComplete" in SCRIPT
    assert "homeCourseIsConfirmedComplete" in SCRIPT
    assert "COURSE_ADVANCE_PENDING_KEY" in SCRIPT
    assert "FORCE_TASK_PANEL_KEY" in SCRIPT
    assert 'window.location.hash = "#/learn"' in SCRIPT
    assert "setTimeout" in SCRIPT


def test_failed_completion_cannot_fake_the_next_desk() -> None:
    assert "completionButton.dataset.moduleCode" in SCRIPT
    assert "writeStorage(COURSE_ADVANCE_PENDING_KEY, courseCode)" in SCRIPT
    assert "const pendingCourseCode = readStorage(COURSE_ADVANCE_PENDING_KEY);" in SCRIPT
    assert (
        "const completedCourseReturn = homeCourseIsConfirmedComplete("
        "root, pendingCourseCode);"
    ) in SCRIPT
    assert SCRIPT.count("removeStorage(COURSE_ADVANCE_PENDING_KEY);") >= 2
    assert "pendingCourseCode !== currentCourseCode" in SCRIPT
    assert "taskChanged || forcedTaskPanel ? \"task\" : savedPanel" in SCRIPT


def test_files_are_presented_as_openable_folders_and_tools_as_apps() -> None:
    folders = (
        "Мой маршрут",
        "Схема производства",
        "Правила качества",
        "Мои достижения",
    )
    applications = (
        "Материалы",
        "Генератор",
        "Проверка",
        "Публикация",
        "Результаты",
        "Выплаты",
    )
    for folder in folders:
        assert folder in SCRIPT
    for application in applications:
        assert application in SCRIPT
    assert "data-lwb-folder" in SCRIPT
    assert "data-lwb-app" in SCRIPT
    assert ".lwb-folder__shape" in STYLES
    assert ".lwb-dock__apps" in STYLES


def test_dynamic_course_copy_is_written_as_text_not_reparsed_as_markup() -> None:
    assert '[data-lwb-menubar-task]").textContent' in SCRIPT
    assert '[data-lwb-menubar-progress]").textContent' in SCRIPT
    assert '[data-lwb-course-title]").textContent' in SCRIPT
    assert '[data-lwb-course-status]").textContent' in SCRIPT
    assert "${taskTitle" not in SCRIPT
    assert "${status ||" not in SCRIPT


def test_motion_is_progressive_and_respects_reduced_motion() -> None:
    assert "MutationObserver" in SCRIPT
    assert "prefers-reduced-motion: reduce" in STYLES
    assert "lwb-task-arrive" in STYLES
    assert "lwb-course-advance" in STYLES
    assert "animation: none !important" in STYLES
