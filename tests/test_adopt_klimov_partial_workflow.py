from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    ROOT / ".github/workflows/adopt-klimov-partial-onboarding-once.yml"
)
EXACT_CONFIRMATION = "ADOPT_KLIMOV_PARTIAL_FROM_RUN_31526654618_ONCE"
OLD_CONFIRMATION = "PROVISION_KLIMOV_OPERATOR_WITH_WAIVER_ONCE"


def _source() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict:
    payload = yaml.safe_load(_source())
    assert isinstance(payload, dict)
    return payload


def _triggers(workflow: dict) -> dict:
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def test_workflow_is_manual_only_with_a_distinct_exact_token() -> None:
    workflow = _workflow()
    triggers = _triggers(workflow)
    dispatch = triggers["workflow_dispatch"]
    confirmation = dispatch["inputs"]["confirmation"]

    assert set(triggers) == {"workflow_dispatch"}
    assert set(dispatch) == {"inputs"}
    assert set(dispatch["inputs"]) == {"confirmation"}
    assert confirmation["required"] is True
    assert confirmation["type"] == "string"
    assert "default" not in confirmation
    assert EXACT_CONFIRMATION in confirmation["description"]
    assert "one-off name repair and adoption" in confirmation["description"]
    assert EXACT_CONFIRMATION != OLD_CONFIRMATION
    assert OLD_CONFIRMATION not in _source()


def test_job_is_bound_to_manual_main_production_and_exact_token() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["adopt"]
    normalized = re.sub(r"\s+", " ", job["if"]).strip()

    assert set(workflow["jobs"]) == {"adopt"}
    assert job["name"] == (
        "Repair exact identity name, adopt, waive training and send recovery"
    )
    assert normalized == (
        "github.event_name == 'workflow_dispatch' && "
        "github.ref == 'refs/heads/main' && "
        "github.event.inputs.confirmation == "
        f"'{EXACT_CONFIRMATION}'"
    )
    assert job["environment"] == "production"
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "production-klimov-operator-onboarding",
        "cancel-in-progress": False,
    }


def test_workflow_has_only_fixed_secret_identity_and_no_state_inputs() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["adopt"]
    env = job["env"]
    source = _source()

    assert set(env) == {
        "SUPABASE_PROJECT_REF",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_OWNER_EMAIL",
        "SUPABASE_MEMBER_KLIMOV_EMAIL",
        "SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME",
    }
    assert env["SUPABASE_MEMBER_KLIMOV_EMAIL"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_EMAIL }}"
    )
    assert env["SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME }}"
    )
    assert env["SUPABASE_OWNER_EMAIL"] == (
        "${{ secrets.SUPABASE_OWNER_EMAIL }}"
    )
    for forbidden in (
        "inputs.email",
        "inputs.display",
        "inputs.user",
        "inputs.uuid",
        "inputs.organization",
        "inputs.owner",
        "inputs.membership",
        "inputs.project",
        "project_id",
        "grant_project",
        "workspace_project_memberships",
    ):
        assert forbidden not in source.casefold()
    assert re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        source,
    ) is None


def test_workflow_checks_out_exact_sha_and_runs_only_dedicated_apply() -> None:
    steps = _workflow()["jobs"]["adopt"]["steps"]
    checkout = steps[0]
    commands = "\n".join(
        str(step.get("run", "")) for step in steps
    )

    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": False,
    }
    assert commands.count(
        "python -m scripts.adopt_klimov_partial_onboarding --apply"
    ) == 1
    assert "provision_employee_without_training" not in commands
    assert "bootstrap_supabase_owner" not in commands
    assert "grant_training_access_waiver" not in commands
    assert "--email" not in commands
    assert "--display-name" not in commands
    assert "--user-id" not in commands
    assert "--membership-id" not in commands
    assert "--organization-id" not in commands
    assert "--project-id" not in commands
