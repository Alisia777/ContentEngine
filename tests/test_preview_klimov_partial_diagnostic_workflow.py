from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = (
    ROOT
    / ".github/workflows/preview-klimov-partial-onboarding-diagnostic.yml"
)
EXACT_CONFIRMATION = "PREVIEW_KLIMOV_PARTIAL_SNAPSHOT_DIAGNOSTIC_ONCE"
APPLY_CONFIRMATION = "ADOPT_KLIMOV_PARTIAL_FROM_RUN_31526654618_ONCE"


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


def test_preview_is_manual_only_with_its_own_exact_token() -> None:
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
    assert EXACT_CONFIRMATION != APPLY_CONFIRMATION
    assert APPLY_CONFIRMATION not in _source()


def test_preview_is_bound_to_manual_main_and_production() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["preview"]
    normalized = re.sub(r"\s+", " ", job["if"]).strip()

    assert set(workflow["jobs"]) == {"preview"}
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


def test_preview_has_only_fixed_secret_identity_and_read_credentials() -> None:
    workflow = _workflow()
    env = workflow["jobs"]["preview"]["env"]
    source = _source()

    assert set(env) == {
        "SUPABASE_PROJECT_REF",
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_OWNER_EMAIL",
        "SUPABASE_MEMBER_KLIMOV_EMAIL",
        "SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME",
    }
    assert env["SUPABASE_PROJECT_REF"] == (
        "${{ vars.SUPABASE_PROJECT_REF }}"
    )
    assert env["SUPABASE_ACCESS_TOKEN"] == (
        "${{ secrets.SUPABASE_ACCESS_TOKEN }}"
    )
    assert env["SUPABASE_OWNER_EMAIL"] == (
        "${{ secrets.SUPABASE_OWNER_EMAIL }}"
    )
    assert env["SUPABASE_MEMBER_KLIMOV_EMAIL"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_EMAIL }}"
    )
    assert env["SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME }}"
    )
    assert "SUPABASE_PUBLISHABLE_KEY" not in source
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


def test_preview_checks_out_exact_sha_and_runs_only_read_only_module() -> None:
    steps = _workflow()["jobs"]["preview"]["steps"]
    checkout = steps[0]
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": False,
    }
    assert commands.count(
        "python -m scripts.adopt_klimov_partial_onboarding"
    ) == 1
    for forbidden in (
        "--apply",
        "provision_employee_without_training",
        "bootstrap_supabase_owner",
        "grant_training_access_waiver",
        "send_password_recovery",
        "SupabaseAuthClient",
        "--email",
        "--display-name",
        "--user-id",
        "--membership-id",
        "--organization-id",
        "--project-id",
    ):
        assert forbidden not in commands
