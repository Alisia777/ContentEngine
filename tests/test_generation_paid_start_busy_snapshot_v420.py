from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def _function(name: str, next_name: str) -> str:
    start = APP.index(f"function {name}")
    end = APP.index(f"function {next_name}", start)
    return APP[start:end]


def test_paid_start_prepares_from_the_enabled_form_snapshot() -> None:
    control = APP[
        APP.index("async function runGenerationSpecControl") :
        APP.index("async function ensurePreparedGenerationSpecForPaidStart")
    ]
    ensure = APP[
        APP.index("async function ensurePreparedGenerationSpecForPaidStart") :
        APP.index("function generationLearningOptOut")
    ]
    submit = APP[
        APP.index("async function submitRealGeneration") :
        APP.index("async function submitMockBatch")
    ]
    assert "preparedPayload: preparedPayloadOverride = null" in control
    assert "preparedPayloadOverride\n    || generationSpecPreparePayload(form)" in control
    assert 'runGenerationSpecControl(form, "prepare", {\n      preparedPayload,' in ensure
    assert 'runGenerationSpecControl(form, "patch", {\n      preparedPayload,' in ensure
    before_ensure = submit[: submit.index("ensurePreparedGenerationSpecForPaidStart(form)")]
    assert "setFormBusy(form, true" not in before_ensure[-250:]


def test_nested_busy_updates_do_not_overwrite_original_control_state() -> None:
    busy = _function("setFormBusy", "withUiTimeout")
    assert 'const wasBusy = form.dataset.busy === "true"' in busy
    assert "if (!wasBusy)" in busy
    assert "if (!submit.dataset.originalLabel)" in busy


def test_free_prepare_failure_restores_content_but_resets_spend_consent() -> None:
    submit = APP[
        APP.index("async function submitRealGeneration") :
        APP.index("async function submitMockBatch")
    ]
    prepare_catch = submit[
        submit.index("ensurePreparedGenerationSpecForPaidStart(form)") :
        submit.index("const brief = String(preparedSpec.compiled_prompt")
    ]
    assert "restoreGenerationLaunchSnapshot(form, launchSnapshot)" in prepare_catch
    assert "form.elements.real_spend_confirmation.checked = false" in prepare_catch


def test_generation_spec_reads_validate_only_the_exact_reference_object() -> None:
    for method, next_method in (
        ("generationSpecStatus", "prepareGenerationSpec"),
        ("generationSpecEffectivePolicy", "savePracticalProject"),
    ):
        block = API[
            API.index(f"  {method}(") :
            API.index(f"  {next_method}(", API.index(f"  {method}("))
        ]
        assert "normalizeGenerationSpecReference({" in block
        assert "spec_id: context.spec_id" in block
        assert "spec_version: context.spec_version" in block
        assert "spec_hash: context.spec_hash" in block
        assert "normalizeGenerationSpecReference(context)" not in block
