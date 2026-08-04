"""Release contracts for the Academy-to-workspace handoff.

These checks deliberately live outside the broad Desktop-v4 contracts.  The
Academy route does not mount ``body.contentengine-desktop-v4``, so a workspace-
only CSS rule must not be allowed to make an Academy accessibility check pass.
"""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
CORE_CSS = (APP_DIR / "workspace-os-v4.css").read_text(encoding="utf-8")
STYLES_CSS = (APP_DIR / "styles.css").read_text(encoding="utf-8")
TRAINING_CSS = (APP_DIR / "training-journey.css").read_text(encoding="utf-8")
ACADEMY_CSS = f"{STYLES_CSS}\n{TRAINING_CSS}"


def _js_function(source: str, declaration: str) -> str:
    """Return one JavaScript function without relying on its next neighbour."""

    start = source.index(declaration)
    body_match = re.search(r"\)\s*\{", source[start:])
    assert body_match is not None, f"Missing function body: {declaration}"
    opening = start + body_match.end() - 1
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unbalanced JavaScript function: {declaration}")


def _css_rules(source: str) -> list[tuple[str, str]]:
    return [
        (" ".join(match.group("selector").split()), match.group("body"))
        for match in re.finditer(
            r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}",
            source,
            flags=re.DOTALL,
        )
    ]


def _unscoped_rule_bodies(source: str, selector_fragment: str) -> list[str]:
    return [
        body
        for selector, body in _css_rules(source)
        if selector_fragment in selector
        and "body.contentengine-desktop-v4" not in selector
    ]


def _numeric_font_sizes(source: str, selector_fragment: str) -> list[float]:
    sizes: list[float] = []
    for selector, body in _css_rules(source):
        if selector_fragment not in selector:
            continue
        for match in re.finditer(
            r"font-size\s*:\s*(?P<value>\d+(?:\.\d+)?)(?P<unit>px|rem)",
            body,
            flags=re.IGNORECASE,
        ):
            value = float(match.group("value"))
            sizes.append(value if match.group("unit").lower() == "px" else value * 16)
    return sizes


def _has_scoped_font_floor(
    source: str,
    selector_fragment: str,
    variable: str,
) -> bool:
    return any(
        ".learning-gate-shell" in selector
        and "body.contentengine-desktop-v4" not in selector
        and selector_fragment in selector
        and re.search(
            rf"font-size\s*:\s*var\({re.escape(variable)}\)\s*!important",
            body,
        )
        is not None
        for selector, body in _css_rules(source)
    )


def test_background_access_approval_opens_the_first_project_next_action() -> None:
    refresh = _js_function(APP, "async function refreshBootstrapAccessState(")

    bootstrap_index = refresh.index("await loadBootstrap(")
    project_open_index = refresh.index("await openFirstAvailableWorkspaceProject(")
    assert bootstrap_index < project_open_index
    assert (
        "hasWorkspaceAccess()" in refresh
        or re.search(r"startPath\s*===\s*WORKSPACE_START_PATH", refresh)
    )

    # The generic start route is only a fallback.  Once approval appears, the
    # project helper owns navigation to the server-provided first next action.
    compatible_index = refresh.index("authenticatedRouteCompatible(")
    assert project_open_index < compatible_index
    assert "return bootstrap" in refresh[project_open_index:]


def test_pending_access_request_and_responsible_are_bootstrap_state() -> None:
    normalize = _js_function(APP, "function normalizeBootstrap(")
    assert "workspace_access_request" in normalize
    assert re.search(r"\bworkspaceAccessRequest\s*(?::|,)", normalize)

    load = _js_function(APP, "async function loadBootstrap(")
    direct_hydration = re.search(
        r"state\.workspaceAccessRequest\.result\s*=\s*"
        r"(?:state\.)?bootstrap\.workspaceAccessRequest",
        load,
    )
    helper_call = re.search(
        r"(?P<name>[A-Za-z0-9_]*WorkspaceAccessRequest[A-Za-z0-9_]*)"
        r"\(\s*(?:state\.)?bootstrap\.workspaceAccessRequest\s*\)",
        load,
    )
    helper = _js_function(APP, f"function {helper_call.group('name')}(") if helper_call else ""
    assert direct_hydration or (
        "state.workspaceAccessRequest.result" in helper
        and "state.workspaceAccessRequest.status" in helper
    ), "loadBootstrap must hydrate request result/status from normalized bootstrap state"
    normalizer = _js_function(APP, "function normalizeWorkspaceAccessRequestResult(")
    assert "responsible_manager" in normalizer
    assert "workspace_access_request" in normalizer
    assert "readStoredWorkspaceAccessRequest()" in helper
    persist = _js_function(APP, "function persistWorkspaceAccessRequest(")
    assert "window.sessionStorage" in persist
    request_handler = APP[APP.index('if (action === "request-workspace-access")') :]
    request_handler = request_handler[: request_handler.index("\n  if (action ===", 10)]
    assert "persistWorkspaceAccessRequest(response)" in request_handler


def test_server_terminal_access_request_clears_stale_pending_cache() -> None:
    helper = _js_function(APP, "function hydrateWorkspaceAccessRequest(")
    authoritative = helper[
        helper.index("if (bootstrapRequest !== null") :
        helper.index("const current = normalizeWorkspaceAccessRequestResult")
    ]
    assert 'fromBootstrap?.request?.status !== "pending"' in authoritative
    assert "persistWorkspaceAccessRequest(null)" in authoritative
    assert "state.workspaceAccessRequest.result = fromBootstrap" in authoritative
    assert 'state.workspaceAccessRequest.status = fromBootstrap ? "ready" : "idle"' in authoritative


def test_post_academy_primary_cta_uses_the_exact_work_admission_copy() -> None:
    access = _js_function(APP, "function renderWorkspaceAccessRequired(")
    button = re.search(
        r"<button[^>]+data-action=[\"']request-workspace-access[\"'][^>]*>"
        r"(?P<label>.*?)</button>",
        access,
        flags=re.DOTALL,
    )
    assert button is not None
    assert "Запросить рабочий допуск" in button.group("label")
    assert 'data-primary-action="true"' in button.group(0)


def test_active_academy_main_is_the_single_vertical_scroll_owner() -> None:
    shell = "\n".join(_unscoped_rule_bodies(ACADEMY_CSS, ".learning-gate-shell[data-learning-route]"))
    main = "\n".join(_unscoped_rule_bodies(ACADEMY_CSS, "#main-content.learning-gate-main"))

    assert re.search(r"(?:^|;)\s*height\s*:\s*100(?:s|d)vh", shell)
    assert re.search(r"grid-template-rows\s*:\s*auto\s+minmax\(\s*0\s*,\s*1fr\s*\)", shell)
    assert re.search(r"overflow\s*:\s*hidden", shell)
    assert re.search(r"min-height\s*:\s*0", main)
    assert re.search(r"overflow-x\s*:\s*hidden", main)
    assert re.search(r"overflow-y\s*:\s*auto", main)

    # Academy content itself must grow inside main.  Horizontal timelines are
    # fine, but no learning/course child may create a second vertical owner.
    for source in (CORE_CSS, STYLES_CSS, TRAINING_CSS):
        for selector, body in _css_rules(source):
            academy_child = re.search(
                r"\.(?:learning|course|lesson|training|academy)-",
                selector,
            )
            if not academy_child or ".learning-gate-main" in selector:
                continue
            assert not re.search(r"overflow-y\s*:\s*(?:auto|scroll)", body), (
                f"{selector} creates a second Academy vertical scroll owner"
            )


def test_active_academy_readability_has_12px_helpers_and_14px_controls() -> None:
    assert re.search(r"--ce-v4-font-helper\s*:\s*var\(--ce-v4-meta-font-size\)", CORE_CSS)
    assert re.search(r"--ce-v4-meta-font-size\s*:\s*12px", CORE_CSS)
    assert re.search(r"--ce-v4-font-control\s*:\s*var\(--ce-v4-ui-font-size\)", CORE_CSS)
    assert re.search(r"--ce-v4-ui-font-size\s*:\s*14px", CORE_CSS)

    control_guards = [
        (selector, body)
        for selector, body in _css_rules(ACADEMY_CSS)
        if ".learning-gate-shell" in selector
        and "body.contentengine-desktop-v4" not in selector
        and "button" in selector
        and "input" in selector
        and "select" in selector
        and "textarea" in selector
    ]
    assert control_guards, "Academy needs its own control-size guard"
    assert any(
        re.search(
            r"font-size\s*:\s*max\(\s*14px\s*,\s*0\.875rem\s*\)",
            body,
        )
        for _selector, body in control_guards
    )

    link_sizes = _numeric_font_sizes(
        f"{STYLES_CSS}\n{TRAINING_CSS}",
        ".training-achievement-shelf__grid a",
    )
    assert link_sizes
    assert min(link_sizes) >= 14 or _has_scoped_font_floor(
        ACADEMY_CSS,
        ".training-achievement-shelf__grid a",
        "--ce-v4-font-control",
    ), f"Academy action link renders below the 14px control floor: {link_sizes}"

    # These are real labels and instructions in the active Academy markup, not
    # miniature screenshots or decorative example diagrams.
    helper_selectors = (
        ".learning-track-picker__focus::before",
        ".course-roadmap .course-roadmap-group",
        ".course-achievement-preview small",
        ".course-mastery-coach__score span",
        ".lesson-step-rail small",
        ".lesson-kicker > span",
    )
    for selector in helper_selectors:
        sizes = _numeric_font_sizes(f"{STYLES_CSS}\n{TRAINING_CSS}", selector)
        assert sizes, f"Missing visible Academy helper rule: {selector}"
        assert min(sizes) >= 12 or _has_scoped_font_floor(
            ACADEMY_CSS,
            selector,
            "--ce-v4-font-helper",
        ), f"{selector} renders below the 12px helper floor: {sizes}"

    # A Desktop-v4-only rule is irrelevant on /learn and must not satisfy the
    # Academy contract by itself.
    desktop_guard = re.search(
        r"body\.contentengine-desktop-v4\s+:is\([^{}]*button[^{}]*\)\s*"
        r"\{[^{}]*--ce-v4-font-control",
        CORE_CSS,
        flags=re.DOTALL,
    )
    assert desktop_guard is not None
