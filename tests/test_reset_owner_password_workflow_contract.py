from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/reset-owner-password.yml"
EXPECTED_PROJECT_REF = "iyckwryrucqrxwlowxow"
EXACT_CONFIRMATION = "RESET_PRODUCTION_OWNER_PASSWORD_ONCE"
CHECKOUT_PIN = "df4cb1c069e1874edd31b4311f1884172cec0e10"
SETUP_PYTHON_PIN = "ece7cb06caefa5fff74198d8649806c4678c61a1"


def _source() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict:
    payload = yaml.safe_load(_source())
    assert isinstance(payload, dict)
    return payload


def _dispatch(workflow: dict) -> dict:
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    dispatch = triggers.get("workflow_dispatch")
    assert isinstance(dispatch, dict)
    return dispatch


def test_owner_password_reset_is_manual_main_only_and_exactly_confirmed() -> None:
    workflow = _workflow()
    dispatch = _dispatch(workflow)
    confirmation = dispatch["inputs"]["confirmation"]
    job = workflow["jobs"]["reset-owner-password"]

    assert set(dispatch) == {"inputs"}
    assert confirmation["required"] is True
    assert confirmation["type"] == "string"
    assert "default" not in confirmation
    assert "ONE-SHOT WARNING" in confirmation["description"]
    assert EXACT_CONFIRMATION in confirmation["description"]
    assert job["if"] == (
        "github.ref == 'refs/heads/main' && "
        "github.event.inputs.confirmation == "
        f"'{EXACT_CONFIRMATION}'"
    )


def test_owner_password_reset_uses_protected_production_scope() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["reset-owner-password"]

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "production-owner-password-reset",
        "cancel-in-progress": False,
    }
    assert job["environment"] == "production"
    assert job["timeout-minutes"] == 10
    assert job["env"] == {
        "SUPABASE_PROJECT_REF": "${{ vars.SUPABASE_PROJECT_REF }}",
    }
    assert "SUPABASE_ACCESS_TOKEN" not in job["env"]
    assert "SUPABASE_OWNER_EMAIL" not in job["env"]
    assert "SUPABASE_OWNER_TEMP_PASSWORD" not in job["env"]


def test_owner_password_reset_uses_only_pinned_checkout_and_python_actions() -> None:
    job = _workflow()["jobs"]["reset-owner-password"]
    external_steps = [step for step in job["steps"] if "uses" in step]

    assert [step["uses"] for step in external_steps] == [
        f"actions/checkout@{CHECKOUT_PIN}",
        f"actions/setup-python@{SETUP_PYTHON_PIN}",
    ]
    assert all(
        re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
        for step in external_steps
    )
    checkout, setup_python = external_steps
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "persist-credentials": False,
    }
    assert setup_python["with"] == {"python-version": "3.12"}


def test_owner_password_reset_masks_secret_before_one_module_call() -> None:
    job = _workflow()["jobs"]["reset-owner-password"]
    reset_step = next(
        step
        for step in job["steps"]
        if step.get("name", "").startswith("ONE-SHOT WARNING:")
    )
    command = reset_step["run"]

    assert reset_step["env"] == {
        "SUPABASE_ACCESS_TOKEN": "${{ secrets.SUPABASE_ACCESS_TOKEN }}",
        "SUPABASE_OWNER_EMAIL": "${{ secrets.SUPABASE_OWNER_EMAIL }}",
        "SUPABASE_OWNER_TEMP_PASSWORD": (
            "${{ secrets.SUPABASE_OWNER_TEMP_PASSWORD }}"
        ),
    }
    mask = 'echo "::add-mask::$SUPABASE_OWNER_TEMP_PASSWORD"'
    invocation = "python -m scripts.reset_supabase_owner_password"
    assert command.count(mask) == 1
    assert command.count(invocation) == 1
    assert command.index(mask) < command.index(invocation)
    assert f'[ "$SUPABASE_PROJECT_REF" != "{EXPECTED_PROJECT_REF}" ]' in command
    assert "set -x" not in command
    assert "--password" not in command
    assert "printenv" not in command
    assert "env |" not in command


def test_confirmation_and_secrets_never_flow_through_logs_or_artifacts() -> None:
    workflow = _workflow()
    source = _source()
    job = workflow["jobs"]["reset-owner-password"]
    reset_step = job["steps"][-1]

    assert "${{ inputs.confirmation }}" not in source
    assert "${{ github.event.inputs.confirmation }}" not in source
    assert EXACT_CONFIRMATION not in reset_step["run"]
    assert "actions/upload-artifact" not in source
    assert "actions/cache" not in source
    assert "GITHUB_OUTPUT" not in source
    assert "GITHUB_STEP_SUMMARY" not in source
    assert "tee " not in reset_step["run"]
    assert "echo $SUPABASE" not in reset_step["run"]
