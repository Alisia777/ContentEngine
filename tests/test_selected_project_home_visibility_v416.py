"""Runtime regression for the selected-project Home surface.

The project chooser and the selected-project next-action view share the
``/workspace/home`` route, but only the chooser may receive the
``ce-v4-project-home`` CSS mode.  Giving that mode to the next-action view
matches a production selector that hides its only child and leaves the user
with an empty desktop.
"""

from __future__ import annotations

from pathlib import Path
import json
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
CORE_CSS = (APP_DIR / "workspace-os-v4.css").read_text(encoding="utf-8")


def _function(source: str, declaration: str) -> str:
    """Extract a JavaScript function without depending on line numbers."""

    start = source.index(declaration)
    opening = source.index("{", start)
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


def _run_mount_home(*, chooser_present: bool) -> dict[str, object]:
    mount_home = _function(CORE, "function mountHome()")
    script = f"""
const assert = require("node:assert/strict");

function classList(...initial) {{
  const values = new Set(initial);
  return {{
    add: (...items) => items.forEach((item) => values.add(item)),
    remove: (...items) => items.forEach((item) => values.delete(item)),
    toggle: (item, force) => {{
      if (force === true) values.add(item);
      else if (force === false) values.delete(item);
      else if (values.has(item)) values.delete(item);
      else values.add(item);
      return values.has(item);
    }},
    contains: (item) => values.has(item),
    values,
  }};
}}

const chooser = {{ dataset: {{}} }};
const action = {{ classList: classList("home-single-action") }};
const page = {{
  classList: classList("page-wrap", "workspace-home", "workspace-home--single-action"),
  firstElementChild: action,
}};
function routePath() {{ return "/workspace/home"; }}
function currentPage() {{ return page; }}
function q(selector, root) {{
  if (selector === ":scope > .ce-v4-home") return null;
  if (selector === "[data-ce-v4-project-home]" && root === page) {{
    return {str(chooser_present).lower()} ? chooser : null;
  }}
  return null;
}}

{mount_home}
mountHome();

// Model the production selector:
// .ce-v4-home-page.ce-v4-project-home >
//   :not(.home-project-switcher):not(.refresh-indicator):not(.home-project-retry)
const projectMode = page.classList.contains("ce-v4-home-page")
  && page.classList.contains("ce-v4-project-home");
const selectorAllowsAction = [
  "home-project-switcher",
  "refresh-indicator",
  "home-project-retry",
].some((name) => action.classList.contains(name));
const actionDisplay = projectMode && !selectorAllowsAction ? "none" : "grid";

process.stdout.write(JSON.stringify({{
  projectMode,
  actionDisplay,
  chooserSurface: chooser.dataset.ceV4Surface || "",
}}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_selected_project_home_keeps_its_single_action_visible() -> None:
    assert (
        ".ce-v4-home-page.ce-v4-project-home > "
        ":not(.home-project-switcher):not(.refresh-indicator):not(.home-project-retry)"
    ) in CORE_CSS

    mounted = _run_mount_home(chooser_present=False)

    assert mounted["projectMode"] is False, (
        "mountHome must only enable ce-v4-project-home when the native "
        "[data-ce-v4-project-home] chooser exists; otherwise the production "
        "CSS hides .home-single-action and /workspace/home?project_id=... is blank"
    )
    assert mounted["actionDisplay"] == "grid"


def test_project_chooser_home_still_owns_the_project_surface() -> None:
    mounted = _run_mount_home(chooser_present=True)

    assert mounted["projectMode"] is True
    assert mounted["chooserSurface"] == "true"
