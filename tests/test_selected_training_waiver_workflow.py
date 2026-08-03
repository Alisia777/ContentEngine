from __future__ import annotations

from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/grant-selected-training-waivers.yml"
SOURCE = WORKFLOW_PATH.read_text(encoding="utf-8")


def _workflow() -> dict:
    payload = yaml.safe_load(SOURCE)
    assert isinstance(payload, dict)
    return payload


def test_workflow_is_manual_main_only_and_fixed_to_three_slots() -> None:
    workflow = _workflow()
    trigger = workflow.get("on", workflow.get(True))
    dispatch = trigger["workflow_dispatch"]
    job = workflow["jobs"]["grant"]

    assert dispatch["inputs"]["confirm"] == {
        "description": "Grant workspace access to guest, klimov and artiukhins",
        "required": True,
        "type": "boolean",
        "default": False,
    }
    assert job["if"] == (
        "github.ref == 'refs/heads/main' && inputs.confirm == true"
    )
    assert job["environment"] == "production"
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "production-selected-training-waivers",
        "cancel-in-progress": False,
    }


def test_workflow_uses_only_existing_protected_identity_secrets() -> None:
    job = _workflow()["jobs"]["grant"]
    env = job["env"]
    steps = {step["name"]: step for step in job["steps"]}
    validation_env = steps["Validate protected production binding"]["env"]
    grant_env = steps["Grant all three waivers atomically"]["env"]

    assert env == {
        "SUPABASE_PROJECT_REF": "${{ vars.SUPABASE_PROJECT_REF }}",
        "EXPECTED_SUPABASE_PROJECT_REF": "iyckwryrucqrxwlowxow",
    }
    assert validation_env == grant_env
    assert grant_env["SUPABASE_MEMBER_GUEST_EMAIL"] == (
        "${{ secrets.SUPABASE_MEMBER_GUEST_EMAIL }}"
    )
    assert grant_env["SUPABASE_MEMBER_KLIMOV_EMAIL"] == (
        "${{ secrets.SUPABASE_MEMBER_KLIMOV_EMAIL }}"
    )
    assert grant_env["SUPABASE_OWNER_EMAIL"] == (
        "${{ secrets.SUPABASE_OWNER_EMAIL }}"
    )
    assert grant_env["SUPABASE_ACCESS_TOKEN"] == (
        "${{ secrets.SUPABASE_ACCESS_TOKEN }}"
    )
    assert "SUPABASE_MEMBER_ARTIUKHINS_EMAIL" not in SOURCE
    assert "SUPABASE_MEMBER_PAVLENKO" not in SOURCE
    assert re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        SOURCE,
    ) is None
    assert "inputs.email" not in SOURCE


def test_workflow_runs_only_one_atomic_grant_helper_at_the_reviewed_sha() -> None:
    steps = _workflow()["jobs"]["grant"]["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    checkout = next(step for step in steps if step["name"].startswith("Check out"))

    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert "bootstrap_supabase_owner.py" not in commands
    assert commands.count(
        "python -m scripts.grant_selected_training_access_waivers"
    ) == 1
    assert "provision_employee_without_training" not in commands
    assert "grant_training_access_waiver.py --email" not in commands
    assert "send-recovery" not in commands
    assert "SUPABASE_MEMBER_GUEST_EMAIL" in commands
    assert "SUPABASE_MEMBER_KLIMOV_EMAIL" in commands
    assert "SUPABASE_OWNER_EMAIL" in commands
