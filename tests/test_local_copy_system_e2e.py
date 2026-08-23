from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"
SCRIPT = ROOT / "scripts" / "local_copy_e2e.py"
WORKBENCH = ROOT / "scripts" / "dev_workbench.py"


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def test_local_mock_copy_actions_are_dual_gated_and_paid_start_stays_blocked() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    enabled = _between(
        edge,
        "function localMockStrategyEnabled()",
        "function validateLocalMockSignedUrl",
    )
    gate = _between(
        edge,
        "const LOCAL_MOCK_STRATEGY_ACTIONS",
        "export default",
    )

    assert 'Deno.env.get("QVF_CREATOR_GENERATE_MOCK_ONLY") === "true"' in enabled
    assert 'Deno.env.get("QVF_ALLOW_REAL_SPEND") === "false"' in enabled
    for action in (
        "strategy_mock_preflight",
        "strategy_mock_start",
        "strategy_mock_status",
    ):
        assert f'"{action}"' in gate
    assert 'if (LOCAL_MOCK_STRATEGY_ACTIONS.has(action)) return null;' in gate
    assert 'action === "strategy_start"' in gate
    assert '"local_mock_strategy_start_blocked"' in gate
    strategy_actions = gate[: gate.index("async function localMockOnlyResponse")]
    assert '"strategy_start"' not in strategy_actions


def test_local_mock_copy_handler_uses_one_rpc_and_no_paid_or_provider_path() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    handler = _between(
        edge,
        "  const localMockUnavailable =",
        "  const loadProviderPolicy = async (",
    )

    assert handler.count('"system_local_mock_generation_strategy"') == 1
    for operation in ("preflight", "complete", "status"):
        assert f'operation: "{operation}"' in handler
    for proof in (
        'mode: "mock"',
        "allow_real_spend: false",
        "provider_call_started: false",
        'confirmation: "LOCAL_MOCK_ONLY"',
        "validateLocalMockSignedUrl",
        "readBoundedBytes(response, MAX_OUTPUT_BYTES)",
        "await sha256Hex(outputBytes)",
        "parseIsoBmffDuration(outputBytes)",
    ):
        assert proof in handler
    for forbidden in (
        "system_claim_generation_strategy_start",
        "system_mark_generation_strategy_dispatch_attempt",
        "system_record_generation_strategy_dispatch_result",
        "generation_strategy_readiness_receipts",
        "RUNWAY_API_ORIGIN",
        "runwaySecret()",
        "fetchProviderJsonWithDeadline(",
        'method: "POST"',
    ):
        assert forbidden not in handler


def test_local_mock_public_projection_redacts_storage_and_media_hashes() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    projector = _between(
        edge,
        "function publicLocalMockGenerationStrategyResult(",
        "function readGenerationStrategyReconcilePayload(",
    )
    complete_output = projector[projector.index(": {") :]

    assert "source_video_sha256" not in projector
    assert "sha256: output.sha256" not in projector
    assert "object_name: output.object_name" in projector
    assert "media_id: output.media_id" in complete_output
    assert "provider_call_started: false" in projector
    assert "spend_ledger_written: false" in projector


def test_copy_system_e2e_is_loopback_only_and_verifies_storage_db_archive() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    system = _between(script, "def run_copy_system_e2e(", "def main()")

    assert "_require_system_mock_only()" in system
    assert system.index("_require_system_mock_only()") < system.index("run_copy_e2e(")
    assert "_storage_upload(" in system
    assert '"strategy_media_probe"' in system
    assert '"creator_prepare_generation_strategy_spec"' in system
    assert '"version": "generation-strategy-spec-prepare-request-v1"' in system
    assert '"project_id": project_id' in system
    assert '"selection": selection' in system
    assert '"mechanics_summary": None' in system
    assert '"generation-strategy-spec-prepare-response-v1"' in system
    assert '"browser_strategy_wrapper_project_scoped"' in system
    assert "prepared_replay = _rpc(" in system
    assert "replay_draft.get(\"spec_id\")" in system
    assert '"creator_control_generation_spec"' in system
    assert '"strategy_bind"' in system
    assert '"strategy_mock_preflight"' in system
    assert '"strategy_mock_start"' in system
    assert '"strategy_mock_status"' in system
    assert '"creator_generation_archive"' in system
    assert "_storage_download(" in system
    assert "hashlib.sha256(downloaded).hexdigest()" in system
    assert '"strategy_spec_idempotent_replay": True' in system
    assert '"provider_call_started": False' in system
    assert '"estimated_cost_minor": 0' in system
    assert '"actual_cost_minor": 0' in system
    assert "api.dev.runwayml.com" not in script
    assert "generativelanguage.googleapis.com" not in script


def test_copy_system_e2e_fails_before_media_without_exact_mock_edge_gate(
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "QVF_ALLOW_REAL_SPEND": "false",
            "QVF_GENERATION_MODE": "mock",
            "QVF_CREATOR_GENERATE_MOCK_ONLY": "false",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/local_copy_e2e.py",
            "--system",
            "--output-root",
            str(tmp_path),
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "QVF_CREATOR_GENERATE_MOCK_ONLY=true" in result.stderr
    assert not list(tmp_path.glob("**/*.mp4"))


def test_dev_test_runs_system_copy_after_local_owner_provisioning() -> None:
    workbench = WORKBENCH.read_text(encoding="utf-8")
    dev_test = _between(workbench, "def dev_test()", "def dev_browser_smoke()")
    system_command = 'run([test_python, "scripts/local_copy_e2e.py", "--system"])'

    assert system_command in dev_test
    assert dev_test.index("provision_local_owner()") < dev_test.index(system_command)
    assert dev_test.index(system_command) < dev_test.index(
        'run([test_python, "scripts/browser_smoke.py"])'
    )
