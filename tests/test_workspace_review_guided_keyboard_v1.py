"""Keyboard and accessibility contract for the completed-review tab wizard."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_workspace_notification_center_v491 import _run_exact_viewport  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
SCRIPT = (APP_DIR / "workspace-os-v4-review-guided.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-os-v4-review-guided.css").read_text(encoding="utf-8")
HARNESS = ROOT / "tests" / "fixtures" / "workspace_review_guided_keyboard_v1_harness.html"


def _function(source: str, declaration: str) -> str:
    start = source.index(declaration)
    opening = source.index(") {", start) + 2
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


def test_review_result_uses_a_complete_horizontal_tab_contract() -> None:
    guide = _function(SCRIPT, "function createGuide(")
    panel = _function(SCRIPT, "function createPanel(")

    for marker in (
        'guide.setAttribute("role", "tablist")',
        'guide.setAttribute("aria-orientation", "horizontal")',
        'button.setAttribute("role", "tab")',
        'button.setAttribute("aria-controls", panelId(result, step))',
        'button.setAttribute("aria-selected", "false")',
        "button.tabIndex = -1",
    ):
        assert marker in guide

    assert 'panel.setAttribute("role", "tabpanel")' in panel
    assert 'panel.setAttribute("aria-labelledby", tabId(result, step))' in panel


def test_review_tabs_rover_wraps_and_supports_home_and_end() -> None:
    keydown = _function(SCRIPT, "function handleGuideKeydown(")
    bind = _function(SCRIPT, "function bindResult(")

    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert f'event.key === "{key}"' in keydown

    assert "(currentIndex + 1) % tabs.length" in keydown
    assert "(currentIndex - 1 + tabs.length) % tabs.length" in keydown
    assert "event.preventDefault()" in keydown
    assert "event.stopPropagation()" in keydown
    assert "{ focusTab: true }" in keydown
    assert 'result.addEventListener("keydown"' in bind


def test_review_step_state_keeps_focus_and_inactive_panels_out_of_the_tree() -> None:
    show = _function(SCRIPT, "function showStep(")

    for marker in (
        "panel.hidden = !active",
        'panel.setAttribute("aria-hidden", active ? "false" : "true")',
        'panel.removeAttribute("inert")',
        'panel.setAttribute("inert", "")',
        'tab.setAttribute("aria-selected", active ? "true" : "false")',
        "tab.tabIndex = active ? 0 : -1",
        'else tab.removeAttribute("aria-current")',
        "activeTab.focus?.({ preventScroll: true })",
    ):
        assert marker in show


def test_narrow_review_guide_centers_the_active_step_without_page_zoom() -> None:
    align = _function(SCRIPT, "function alignActiveTab(")

    assert 'window.matchMedia("(max-width: 760px)")' in SCRIPT
    assert "NARROW_REVIEW_GUIDE.matches" in align
    assert "tab.scrollIntoView?.({" in align
    assert 'block: "nearest"' in align
    assert 'inline: "center"' in align
    assert "scroll-snap-type: inline proximity" in CSS
    assert "scroll-snap-align: center" in CSS


def test_review_tablist_runtime_focus_visibility_and_narrow_alignment() -> None:
    expression = r"""
(async () => {
  const result = document.querySelector(".content-review-result");
  const tabs = [...result.querySelectorAll(".ce-v4-review-guide > [role='tab']")];
  const panels = [...result.querySelectorAll(":scope > [role='tabpanel']")];
  const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));
  const snapshot = () => {
    const activeTab = tabs.find((tab) => tab.getAttribute("aria-selected") === "true");
    const activePanel = panels.find((panel) => !panel.hidden);
    return {
      step: result.dataset.reviewGuidedStep,
      focusStep: document.activeElement?.dataset?.ceV4ReviewStepTarget || "",
      selectedCount: tabs.filter((tab) => tab.getAttribute("aria-selected") === "true").length,
      tabbableCount: tabs.filter((tab) => tab.tabIndex === 0).length,
      visibleCount: panels.filter((panel) => !panel.hidden).length,
      inactivePanelsClosed: panels.filter((panel) => panel !== activePanel).every((panel) => (
        panel.hidden
        && panel.hasAttribute("inert")
        && panel.getAttribute("aria-hidden") === "true"
      )),
      activePanelOpen: !activePanel.hasAttribute("inert")
        && activePanel.getAttribute("aria-hidden") === "false",
      linked: activeTab.getAttribute("aria-controls") === activePanel.id
        && activePanel.getAttribute("aria-labelledby") === activeTab.id,
    };
  };

  tabs[0].focus();
  tabs[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  await frame();
  await frame();
  const right = snapshot();

  document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
  await frame();
  const end = snapshot();
  document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }));
  await frame();
  const home = snapshot();
  document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
  await frame();
  const leftWrap = snapshot();

  tabs[1].click();
  await frame();
  const clickFocus = document.activeElement === tabs[1];
  panels[1].querySelector(".ce-v4-review-next").click();
  await frame();
  const nextFocusesPanelHeading = document.activeElement
    === panels[2].querySelector(":scope > .ce-v4-review-panel__intro h3");

  return JSON.stringify({
    right,
    end,
    home,
    leftWrap,
    clickFocus,
    nextFocusesPanelHeading,
    narrowCentered: window.__reviewGuideScrolls.some((entry) => (
      entry.step === "2" && entry.inline === "center" && entry.block === "nearest"
    )),
  });
})()
"""
    result = _run_exact_viewport(390, 820, expression, HARNESS)

    assert result["right"] == {
        "step": "2",
        "focusStep": "2",
        "selectedCount": 1,
        "tabbableCount": 1,
        "visibleCount": 1,
        "inactivePanelsClosed": True,
        "activePanelOpen": True,
        "linked": True,
    }
    assert result["end"]["step"] == result["end"]["focusStep"] == "4"
    assert result["home"]["step"] == result["home"]["focusStep"] == "1"
    assert result["leftWrap"]["step"] == result["leftWrap"]["focusStep"] == "4"
    assert result["clickFocus"] is True
    assert result["nextFocusesPanelHeading"] is True
    assert result["narrowCentered"] is True
