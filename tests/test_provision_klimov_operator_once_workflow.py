from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/provision-klimov-operator-once.yml"
EXACT_CONFIRMATION = "PROVISION_KLIMOV_OPERATOR_WITH_WAIVER_ONCE"
LEGACY_PUSH_CONFIRMATION = "Run protected Klimov onboarding v10"


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


def _selected_by_contract(
    *,
    event_name: str,
    ref: str = "refs/heads/main",
    confirmation: str | None = None,
    head_commit_message: str | None = None,
) -> bool:
    return ref == "refs/heads/main" and (
        (
            event_name == "workflow_dispatch"
            and confirmation == EXACT_CONFIRMATION
        )
        or (
            event_name == "push"
            and head_commit_message == LEGACY_PUSH_CONFIRMATION
        )
    )


def test_manual_dispatch_is_required_and_job_selection_is_exact() -> None:
    workflow = _workflow()
    triggers = _triggers(workflow)
    dispatch = triggers["workflow_dispatch"]
    confirmation = dispatch["inputs"]["confirmation"]
    job = workflow["jobs"]["provision"]

    assert set(triggers) == {"push", "workflow_dispatch"}
    assert triggers["push"] == {
        "branches": ["main"],
        "paths": [".github/workflows/provision-klimov-operator-once.yml"],
    }
    assert set(dispatch) == {"inputs"}
    assert set(dispatch["inputs"]) == {"confirmation"}
    assert confirmation["required"] is True
    assert confirmation["type"] == "string"
    assert "default" not in confirmation
    assert EXACT_CONFIRMATION in confirmation["description"]
    normalized_condition = re.sub(r"\s+", " ", job["if"]).strip()
    assert normalized_condition == (
        "github.ref == 'refs/heads/main' && "
        "( "
        "( github.event_name == 'workflow_dispatch' && "
        "github.event.inputs.confirmation == "
        f"'{EXACT_CONFIRMATION}' ) || "
        "( github.event_name == 'push' && "
        "github.event.head_commit.message == "
        f"'{LEGACY_PUSH_CONFIRMATION}' ) "
        ")"
    )


def test_wrong_or_missing_manual_confirmation_skips_the_job() -> None:
    assert _selected_by_contract(
        event_name="workflow_dispatch",
        confirmation=EXACT_CONFIRMATION,
    )
    for rejected_confirmation in (
        None,
        "",
        "PROVISION_KLIMOV_OPERATOR_ONCE",
        f"{EXACT_CONFIRMATION} ",
        EXACT_CONFIRMATION.lower(),
    ):
        assert not _selected_by_contract(
            event_name="workflow_dispatch",
            confirmation=rejected_confirmation,
        )
    assert not _selected_by_contract(
        event_name="workflow_dispatch",
        ref="refs/heads/not-main",
        confirmation=EXACT_CONFIRMATION,
    )


def test_legacy_exact_push_trigger_remains_narrow() -> None:
    assert _selected_by_contract(
        event_name="push",
        head_commit_message=LEGACY_PUSH_CONFIRMATION,
    )
    assert not _selected_by_contract(
        event_name="push",
        head_commit_message=f"{LEGACY_PUSH_CONFIRMATION} ",
    )
    assert not _selected_by_contract(
        event_name="push",
        ref="refs/heads/not-main",
        head_commit_message=LEGACY_PUSH_CONFIRMATION,
    )


def test_exact_dispatch_selects_only_the_protected_klimov_path() -> None:
    workflow = _workflow()
    source = _source()
    job = workflow["jobs"]["provision"]
    env = job["env"]
    steps = job["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert set(workflow["jobs"]) == {"provision"}
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}
    assert workflow["concurrency"] == {
        "group": "production-klimov-operator-onboarding",
        "cancel-in-progress": False,
    }
    assert job["environment"] == "production"
    assert env["MEMBER_EMAIL"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_EMAIL }}"
    )
    assert env["MEMBER_DISPLAY_NAME"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME }}"
    )
    assert "SUPABASE_MEMBER_KLIMOV_TEMP_PASSWORD" not in source
    assert "inputs.account" not in source
    assert "inputs.email" not in source
    assert re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        source,
    ) is None

    owner_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("id") == "owner"
    )
    onboard_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("id") == "onboard"
    )
    assert owner_index < onboard_index
    assert commands.count("python scripts/bootstrap_supabase_owner.py") == 1
    assert commands.count(
        "python -m scripts.provision_employee_without_training"
    ) == 1
    assert "--email=\"$MEMBER_EMAIL\"" in commands
    assert "--display-name=\"$MEMBER_DISPLAY_NAME\"" in commands
    assert "grant_project" not in commands
    assert "workspace_project_memberships" not in commands
    assert "project_id" not in commands


def test_owner_restore_onboarding_and_reporting_remain_fail_closed() -> None:
    steps = _workflow()["jobs"]["provision"]["steps"]
    by_id = {step["id"]: step for step in steps if "id" in step}
    final_step = steps[-1]

    assert by_id["owner"]["continue-on-error"] is True
    assert by_id["onboard"]["if"] == "steps.owner.outcome == 'success'"
    assert by_id["onboard"]["continue-on-error"] is True
    assert by_id["onboard"]["name"] == (
        "Create or verify employee, waive final test and send password link"
    )
    assert final_step["name"] == (
        "Fail closed when full onboarding is not confirmed"
    )
    assert final_step["if"] == (
        "always() && "
        "(steps.owner.outcome != 'success' || "
        "steps.onboard.outcome != 'success')"
    )
    assert final_step["run"] == "exit 1"
