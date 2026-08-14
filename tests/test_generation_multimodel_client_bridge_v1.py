from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
GUIDED = (ROOT / "web/app/workspace-os-v4-generation-guided.js").read_text(
    encoding="utf-8"
)
SHARED_SNAPSHOT = (
    ROOT / "supabase/functions/_shared/generation-selection-snapshot.js"
).read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    opening = source.index("{", start)
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        character = source[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'", "`"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"function {name} did not close")


def _array_literal(source: str, declaration: str) -> list[str]:
    match = re.search(
        rf"{re.escape(declaration)}\s*=\s*Object\.freeze\(\[(.*?)\]\);",
        source,
        re.DOTALL,
    )
    assert match, declaration
    return re.findall(r'"([a-z0-9_]+)"', match.group(1))


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the canonical form tamper contract")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "contract.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_browser_snapshot_field_list_has_static_parity_with_shared_authority() -> None:
    assert _array_literal(APP, "const GENERATION_SELECTION_SNAPSHOT_FIELDS") == (
        _array_literal(
            SHARED_SNAPSHOT,
            "export const GENERATION_SELECTION_SNAPSHOT_FIELDS",
        )
    )


def test_exact_controls_fail_closed_under_tampering_and_capability_mismatch() -> None:
    boolean_control = _function_source(APP, "generationBooleanControl")
    canonical_selection = _function_source(APP, "canonicalGenerationSelection")
    result = _run_node(
        f"""
        class HTMLInputElement {{}}
        class HTMLSelectElement {{}}
        {boolean_control}
        const catalog = {{
          version: "2026-08-13.v1",
          models: [{{
            provider: "google",
            model: "veo-3.1-lite-generate-preview",
            publicLabel: "Veo 3.1 Lite",
            contentKind: "video",
            enabled: true,
            executionSupported: true,
            launchEnabled: true,
            allowedDurations: [4, 6, 8],
            allowedRatios: ["16:9", "9:16"],
            allowedResolutions: ["720p", "1080p"],
            audioModes: [true],
            lastFrameSupported: true,
            promptLimit: 1000,
            pricingVersion: "google-veo-2026-08-13.v1",
            inputCapabilities: {{image: {{
              allowedRatios: ["16:9", "9:16"],
              allowedResolutions: ["720p", "1080p"],
              allowedDurationsByResolution: {{"720p": [4, 6, 8], "1080p": [8]}},
              supportsLastFrame: true,
              lastFrameDurationSeconds: 8,
            }}}},
          }}],
        }};
        const state = {{generationModelCatalog: catalog}};
        {canonical_selection}
        const controls = {{
          generation_provider: {{value: "google"}},
          generation_model_id: {{value: "veo-3.1-lite-generate-preview"}},
          generation_input_mode: {{value: "image"}},
          duration_seconds: {{value: "8"}},
          format: {{value: "16:9"}},
          generation_resolution: {{value: "720p"}},
          generation_audio: {{value: "true"}},
          generation_last_frame: {{value: "false"}},
          generation_launch_enabled: {{value: "true"}},
          generation_catalog_version: {{value: catalog.version}},
          generation_pricing_version: {{value: catalog.models[0].pricingVersion}},
          generation_content_kind: {{value: "video"}},
          generation_prompt_limit: {{value: "1000"}},
          generation_selection_source: {{value: "manual_choice"}},
        }};
        const form = {{elements: controls}};
        const attempt = (patch) => {{
          const before = Object.fromEntries(Object.entries(controls).map(([key, item]) => [key, item.value]));
          Object.entries(patch).forEach(([key, value]) => {{ controls[key].value = value; }});
          const selected = canonicalGenerationSelection(form);
          Object.entries(before).forEach(([key, value]) => {{ controls[key].value = value; }});
          return selected;
        }};
        const valid = canonicalGenerationSelection(form);
        const output = {{
          valid: Boolean(valid),
          exact: valid && [valid.provider, valid.model, valid.durationSeconds, valid.format],
          launchTamper: attempt({{generation_launch_enabled: "false"}}),
          catalogTamper: attempt({{generation_catalog_version: "stale"}}),
          pricingTamper: attempt({{generation_pricing_version: "stale"}}),
          sourceTamper: attempt({{generation_selection_source: "manual"}}),
          resolutionDurationTamper: attempt({{
            duration_seconds: "6", generation_resolution: "1080p",
          }}),
          lastFrameDurationTamper: attempt({{
            duration_seconds: "6", generation_last_frame: "true",
          }}),
        }};
        process.stdout.write(JSON.stringify(output));
        """
    )
    assert result["valid"] is True
    assert result["exact"] == [
        "google",
        "veo-3.1-lite-generate-preview",
        8,
        "16:9",
    ]
    for key in (
        "launchTamper",
        "catalogTamper",
        "pricingTamper",
        "sourceTamper",
        "resolutionDurationTamper",
        "lastFrameDurationTamper",
    ):
        assert result[key] is None


def test_one_form_bridge_owns_submit_and_forwards_only_authoritative_fields() -> None:
    assert APP.count('id="mock-batch-form"') == 1
    assert 'document.addEventListener("submit", handleSubmit)' in APP
    assert "document.createElement(\"form\")" not in GUIDED
    assert "requestSubmit" not in GUIDED
    assert 'name = "generation_model"' in GUIDED
    assert 'name = "generation_resolution"' in GUIDED
    assert 'name = "generation_audio"' in GUIDED
    assert 'name = "generation_last_frame"' in GUIDED
    assert "inputCapabilities?.image" in GUIDED
    assert "allowedDurationsByResolution" in GUIDED
    assert "lastFrameDurationSeconds" in GUIDED

    paid_start = API[
        API.index("  startRealGeneration(batch)") :
        API.index("  realGenerationPreflight(", API.index("  startRealGeneration"))
    ]
    assert "prompt_max_length: _clientPromptMaxLength" in paid_start
    assert "...serverBatchPayload" in paid_start
    assert "...batchPayload," not in paid_start[paid_start.index("const invocationPayload") :]
    assert "provider_readiness_receipt_id" in paid_start
    assert "generation_selection_snapshot" in paid_start


def test_strategy_bind_is_a_separate_free_idempotent_transport() -> None:
    bind_start = API.index("  bindGenerationStrategy(input = {})")
    bind_end = API.index("  realGenerationStatus(", bind_start)
    bind = API[bind_start:bind_end]
    invoke_start = API.index("  async invokeRealGeneration(")
    invoke_end = API.index("  recordMetric(", invoke_start)
    invoke = API[invoke_start:invoke_end]

    assert 'this.invokeRealGeneration("strategy_bind"' in bind
    assert 'confirmation: true' in bind
    assert 'generation_strategy: selection' in bind
    assert 'spec_id: specContext.spec_id' in bind
    assert 'spec_hash: specContext.spec_hash' in bind
    assert "startRealGeneration" not in bind
    assert "spend_confirmation" not in bind
    assert "estimated_cost_minor" not in bind
    assert '"strategy_bind"' in invoke
    assert '"start", "reconcile", "strategy_bind"' in invoke
    assert 'if (action === "strategy_bind")' in invoke
    assert "delete this.mutationKeys[fingerprint]" in invoke


def test_google_reconciliation_is_provider_specific_without_loosening_runway_id() -> None:
    reconcile = API[
        API.index("  reconcileRealGeneration(") :
        API.index("  async invokeRealGeneration(", API.index("  reconcileRealGeneration("))
    ]
    assert 'new Set(["runway", "google"])' in reconcile
    assert "models\\/veo-3\\.1-lite-generate-preview\\/operations" in reconcile
    assert "/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u" in reconcile
    assert '"GOOGLE_OPERATION_ID_VERIFIED"' in reconcile
    assert '"GOOGLE_NO_OPERATION_VERIFIED"' in reconcile
    assert '"RUNWAY_TASK_ID_VERIFIED"' in reconcile
    assert '"RUNWAY_NO_TASK_VERIFIED"' in reconcile
