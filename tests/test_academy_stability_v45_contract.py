from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")


def _source_between(start: str, end: str) -> str:
    match = re.search(
        rf"{re.escape(start)}(?P<body>.*?){re.escape(end)}",
        APP,
        flags=re.DOTALL,
    )
    assert match is not None, f"Missing Academy stability contract: {start!r}"
    return match.group("body")


def test_same_academy_route_patches_content_without_restarting_main_motion() -> None:
    source = _source_between(
        "function renderLearningScaffold(content, activePath) {",
        "\n}\n\nfunction renderWorkspaceBoardSection",
    )

    assert "const sameRoute = existingShell.dataset.learningRoute === activePath" in source
    assert "if (sameRoute) patchWorkspaceContent(existingContent, content)" in source
    assert "else existingContent.innerHTML = content" in source
    assert "if (!sameRoute) {" in source
    assert 'main.className = ["learning-gate-main", consumeRouteTransitionClass()]' in source
    assert "main.className = `learning-gate-main ${consumeRouteTransitionClass()}`" not in source


def test_academy_focus_identity_distinguishes_repeated_lessons_and_timelines() -> None:
    capture = _source_between(
        "function captureWorkspaceFocus(container) {",
        "\n}\n\nfunction restoreWorkspaceFocus",
    )
    restore = _source_between(
        "function restoreWorkspaceFocus(container, identity, section) {",
        "\n}\n\nfunction workspaceInitialLoadingMarkup",
    )

    for marker in (
        "courseLessonId",
        "courseLessonIndex",
        "courseRoadmapLessonIndex",
        "lessonTargetIndex",
        "trainingWalkthroughId",
        "trainingStepTarget",
        "actionIndex",
    ):
        assert marker in capture
        assert marker in restore
    assert "actionCandidates[identity.actionIndex]" in restore


def test_academy_horizontal_scroll_owners_have_stable_semantic_keys() -> None:
    scroll_owners = _source_between(
        "const WORKSPACE_SCROLL_OWNERS = [",
        "\n].join(\",\");",
    )
    scroll_key = _source_between(
        "function workspaceScrollKey(node, index) {",
        "\n}\n\nfunction captureWorkspaceScroll",
    )

    assert '".course-roadmap ol"' in scroll_owners
    assert '"[data-training-timeline]"' in scroll_owners
    assert "training-timeline:${walkthroughId}" in scroll_key
    assert "course-roadmap:${learningRoute}" in scroll_key


def test_bootstrap_refresh_keeps_the_existing_academy_shell_and_main() -> None:
    loading = _source_between(
        "function renderBootstrapLoading() {",
        "\n}\n\nfunction renderBootstrapError",
    )
    scaffold = _source_between(
        "function renderLearningScaffold(content, activePath) {",
        "\n}\n\nfunction renderWorkspaceBoardSection",
    )

    assert "academyShell instanceof HTMLElement" in loading
    assert 'academyMain.setAttribute("aria-busy", "true")' in loading
    assert "academyMain.append(status)" in loading
    assert loading.index("return;") < loading.index("app.innerHTML = `")
    assert "clearAcademyBootstrapLoading(existingShell)" in scaffold
    assert scaffold.index("clearAcademyBootstrapLoading(existingShell)") < scaffold.index(
        "existingContent.dataset.ceV4RenderSignature === signature"
    )


def test_training_media_hydration_is_latest_request_wins_and_idempotent() -> None:
    source = _source_between(
        "async function hydrateTrainingMediaCards(courseCode) {",
        "\n}\n\nfunction restoreTrainingWalkthroughState",
    )

    assert "const trainingMediaBindingCleanups = new WeakMap()" in APP
    assert "const trainingMediaHydrationEpochs = new WeakMap()" in APP
    assert "trainingMediaHydrationEpochs.get(host) !== hydrationEpoch" in source
    assert "trainingMediaBindingCleanups.get(host)?.()" in source
    assert "trainingMediaBindingCleanups.set(host, cleanup)" in source
    assert "data.trainingMediaHydrationSignature" not in source
    assert "host.dataset.trainingMediaHydrationSignature" in source


def test_practical_file_input_survives_same_route_async_patch_without_filelist_rewrite() -> None:
    capture = _source_between(
        "function captureDirtyWorkspaceForms(container) {",
        "\n}\n\nfunction restoreDirtyWorkspaceForms",
    )
    restore = _source_between(
        "function restoreDirtyWorkspaceForms(container, snapshots) {",
        "\n}\n\nfunction workspaceNavLinkMarkup",
    )
    scaffold = _source_between(
        "function renderLearningScaffold(content, activePath) {",
        "\n}\n\nfunction renderWorkspaceBoardSection",
    )

    assert 'form.querySelectorAll(\'input[type="file"]\')' in capture
    assert ".some((input) => (input.files?.length || 0) > 0)" in capture
    assert "if (saved.node === field) return" in restore
    assert "if (sameRoute) patchWorkspaceContent(existingContent, content)" in scaffold
    assert "restoreDirtyWorkspaceForms(existingContent, dirtyForms)" in scaffold


def test_academy_stability_does_not_change_start_policy_or_asset_generation() -> None:
    render = _source_between(
        "function render() {",
        "\n}\n\nfunction renderLogin",
    )

    assert "if (academyRequired())" in render
    assert 'navigate("/learn", true)' in render
    assert 'if (path === "/learn" || path.startsWith("/learn/"))' in render
    assert "navigate(authenticatedStartPath(), true)" in render
    assert './workspace-dom-patch.js?v=20260826.rebuild-clean.48' in APP
