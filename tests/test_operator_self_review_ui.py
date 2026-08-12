from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/content-review-view.js").read_text(encoding="utf-8")
REVIEW_CSS = (
    ROOT / "web/app/workspace-os-v4-review-guided.css"
).read_text(encoding="utf-8")


def _node(script: str) -> None:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_operator_decision_authority_is_exact_server_assignment_not_role_only() -> None:
    module_url = (ROOT / "web/app/content-review-view.js").resolve().as_uri()
    script = f"""
import {{
  contentReviewDecisionAllowed,
  normalizeContentReviewRun,
}} from {json.dumps(module_url)};

for (const role of ["owner", "admin", "producer", "reviewer"]) {{
  if (!contentReviewDecisionAllowed(role, null)) {{
    throw new Error(`manager role changed: ${{role}}`);
  }}
}}
if (contentReviewDecisionAllowed("operator", null)) throw new Error("role-only operator");
if (contentReviewDecisionAllowed("trainee", {{
  independentAssignment: {{
    status: "assigned", assignedToMe: true, decisionEligible: true,
  }},
}})) throw new Error("non-operator forged assignment");

const normalize = (assignment) => normalizeContentReviewRun({{
  id: "11111111-1111-4111-8111-111111111111",
  status: "completed",
  independent_assignment: assignment,
}});
const exact = normalize({{
  status: "assigned",
  assigned_to_me: true,
  decision_eligible: true,
}});
if (!contentReviewDecisionAllowed("operator", exact)) throw new Error("exact assignment denied");
const exactRoundTrip = normalizeContentReviewRun(exact);
if (!contentReviewDecisionAllowed("operator", exactRoundTrip)) {{
  throw new Error("authoritative assignment lost on normalized render round-trip");
}}

for (const assignment of [
  {{ status: "assigned", assigned_to_me: false, decision_eligible: true }},
  {{ status: "assigned", assigned_to_me: true, decision_eligible: false }},
  {{ status: "unassigned", assigned_to_me: true, decision_eligible: true }},
  {{ status: "completed", assigned_to_me: true, decision_eligible: true }},
  {{ status: "assigned", assigned_to_me: "true", decision_eligible: true }},
  {{ status: "assigned", assigned_to_me: true, decision_eligible: "true" }},
]) {{
  if (contentReviewDecisionAllowed("operator", normalize(assignment))) {{
    throw new Error(`inexact server assignment allowed: ${{JSON.stringify(assignment)}}`);
  }}
}}
"""
    _node(script)


def test_exact_eligible_operator_gets_controls_but_role_only_operator_does_not() -> None:
    module_url = (ROOT / "web/app/content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://portal.test/" }} }};
const subject = await import({json.dumps(module_url)});
const raw = {{
  id: "11111111-1111-4111-8111-111111111111",
  status: "completed",
  independent_assignment: {{
    status: "assigned",
    assigned_to_me: true,
    decision_eligible: true,
  }},
  input: {{
    platform: "vk",
    content_kind: "advertising",
    product_category: "electronics",
  }},
  result: {{
    overall_score: 90,
    blockers_count: 0,
    warnings_count: 0,
    compliance_status: "allow",
    findings: [],
    recommendations: [],
  }},
  media: {{
    id: "22222222-2222-4222-8222-222222222222",
    name: "generated.png",
    mime_type: "image/png",
    kind: "generated_image",
    status: "ready",
    signed_url: "https://example.test/generated.png",
  }},
}};
const run = subject.normalizeContentReviewRun(raw);
const eligible = subject.contentReviewDecisionAllowed("operator", run);
const allowed = subject.contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [run] }},
  currentRun: run,
  canDecide: eligible,
  view: "current",
}});
if (!eligible) throw new Error("eligible signal lost during normalization");
if (!allowed.includes("content-review-decision-form")) throw new Error("decision form hidden");
if (!allowed.includes('name="decision" value="needs_changes"')) {{
  throw new Error("negative decision control hidden");
}}

const roleOnlyRun = subject.normalizeContentReviewRun({{ ...raw, independent_assignment: undefined }});
const denied = subject.contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [roleOnlyRun] }},
  currentRun: roleOnlyRun,
  canDecide: subject.contentReviewDecisionAllowed("operator", roleOnlyRun),
  view: "current",
}});
if (denied.includes("content-review-decision-form")) throw new Error("role-only form rendered");
if (denied.includes('name="decision" value="needs_changes"')) throw new Error("role-only control rendered");

const assignedElsewhere = subject.normalizeContentReviewRun({{
  ...raw,
  independent_assignment: {{
    status: "assigned",
    assigned_to_me: false,
    decision_eligible: true,
  }},
}});
const managerBlocked = subject.contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [assignedElsewhere] }},
  currentRun: assignedElsewhere,
  canDecide: true,
  view: "current",
}});
if (managerBlocked.includes("content-review-decision-form")) {{
  throw new Error("normalized assignment-to-other was lost before render");
}}
"""
    _node(script)


def test_render_and_submit_recheck_the_same_current_run_predicate() -> None:
    helper = APP[
        APP.index("function canDecideContentReview("):
        APP.index("function generatedVideoQaStorageKey(")
    ]
    assert "contentReviewDecisionAllowed(" in helper
    assert "state.bootstrap?.membership?.role" in helper
    assert "run," in helper
    assert 'includes(state.bootstrap?.membership?.role)' not in helper

    render = APP[
        APP.index("function renderContentReviewSection("):
        APP.index("function selectPendingContentReviewMedia(")
    ]
    assert "canDecideContentReview(state.contentReview.record)" in render

    submit = APP[
        APP.index("async function submitContentReviewDecision("):
        APP.index("function exactYoutubeMediaRouteIntent(")
    ]
    assert "const review = state.contentReview;" in submit
    assert "if (!canDecideContentReview(review.record))" in submit
    assert submit.index("if (!canDecideContentReview(review.record))") < submit.index(
        "readContentReviewDecision(form, submitter)"
    )


def test_mouse_actions_are_above_and_outside_the_sticky_preview_grid_area() -> None:
    preview_rule = re.search(
        r"\.content-review-decision-form > \.content-review-decision-preview\s*\{([^}]*)\}",
        REVIEW_CSS,
        re.S,
    )
    actions_rule = re.search(
        r"\.content-review-decision-form > \.content-review-decision-actions\s*\{([^}]*)\}",
        REVIEW_CSS,
        re.S,
    )
    assert preview_rule and actions_rule
    assert "grid-column: 1" in preview_rule.group(1)
    assert "z-index: 1" in preview_rule.group(1)
    assert "overflow: hidden" in preview_rule.group(1)
    assert "grid-column: 2" in actions_rule.group(1)
    assert "grid-row: auto" in actions_rule.group(1)
    assert "z-index: 2" in actions_rule.group(1)
    assert "pointer-events" not in actions_rule.group(1)
