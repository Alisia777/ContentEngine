from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CONTEXT = (APP / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-project-covers-v1.css").read_text(encoding="utf-8")
INDEX = (APP / "index.html").read_text(encoding="utf-8")


def test_project_cover_choice_is_local_project_scoped_presentation_state() -> None:
    assert 'PROJECT_COVER_STORAGE_PREFIX = "contentengine.desktop-v4.project-covers.v1"' in CORE
    assert "function projectCoverPreferenceKey()" in CORE
    assert "function writeProjectCoverPreference(projectId, cover)" in CORE
    assert "function applyProjectCoverPreferences(root = document)" in CORE
    assert 'card.dataset.ceV4ProjectCover = cover' in CORE
    assert "Это меняет только оформление, не файлы проекта." in CORE


def test_project_context_menu_opens_accessible_cover_picker() -> None:
    assert 'menuAction("Выбрать обложку…", "eye"' in CONTEXT
    assert "openProjectCoverPicker?.(shell.key, shell.title, shell.node)" in CONTEXT
    assert "function openProjectCoverPicker(" in CORE
    assert 'grid.setAttribute("role", "radiogroup")' in CORE
    assert 'button.setAttribute("role", "radio")' in CORE
    assert "openProjectCoverPicker," in CORE


def test_cover_atlas_has_four_explicit_choices_and_responsive_picker() -> None:
    for key in ("campaign", "digital", "product", "editorial"):
        assert f'data-ce-v4-project-cover="{key}"' in CSS
    assert 'url("./assets/content-factory-project-covers-v2.png")' in CSS
    assert "background-size: 100% 100%, 200% 200%" in CSS
    assert "@media (max-width: 640px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS


def test_project_cover_css_is_loaded() -> None:
    assert "./workspace-project-covers-v1.css" in INDEX
