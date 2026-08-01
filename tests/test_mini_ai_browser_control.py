from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
ENGINE_V1 = (APP_DIR / "mini-ai-control-plane-v1.js").read_text(encoding="utf-8")
ENGINE_V2 = (APP_DIR / "mini-ai-control-plane-v2.js").read_text(encoding="utf-8")
DESK = (APP_DIR / "workspace-mini-ai-control-v3.js").read_text(encoding="utf-8")
JOB_SIGNATURE = (APP_DIR / "workspace-generation-job-signature-v1.js").read_text(
    encoding="utf-8"
)
CATEGORY_SCOPE = (APP_DIR / "workspace-mini-ai-category-scope-v1.js").read_text(
    encoding="utf-8"
)
BASE_CSS = (APP_DIR / "workspace-mini-ai-control-v1.css").read_text(
    encoding="utf-8"
)
WAVE_CSS = (APP_DIR / "workspace-mini-ai-control-v3.css").read_text(
    encoding="utf-8"
)
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CONFIG = (APP_DIR / "config.js").read_text(encoding="utf-8")
EXAMPLE_CONFIG = (APP_DIR / "config.example.js").read_text(encoding="utf-8")
RELEASE_BUILDER = (ROOT / "scripts" / "build_pages_release.py").read_text(
    encoding="utf-8"
)


def test_mini_ai_is_loaded_only_on_generation_and_has_a_kill_switch() -> None:
    for marker in (
        'route === "/workspace/generation"',
        "MINI_AI_CONTROL_ENABLED === true",
        '"workspace-mini-ai-control-v1.css?v=20260801.5"',
        '"workspace-mini-ai-control-v3.css?v=20260801.5"',
        '"workspace-generation-job-signature-v1.js?v=20260801.5"',
        '"workspace-mini-ai-control-v3.js?v=20260801.5"',
        '"workspace-mini-ai-category-scope-v1.js?v=20260801.5"',
    ):
        assert marker in LOADER
    assert LOADER.index("workspace-generation-job-signature-v1.js") < LOADER.index(
        "workspace-mini-ai-control-v3.js"
    )
    assert LOADER.index("workspace-mini-ai-control-v3.js") < LOADER.index(
        "workspace-mini-ai-category-scope-v1.js"
    )
    assert "MINI_AI_CONTROL_ENABLED: true" in CONFIG
    assert "MINI_AI_CONTROL_ENABLED: false" in EXAMPLE_CONFIG
    assert '"MINI_AI_CONTROL_ENABLED": True' in RELEASE_BUILDER
    assert "workspace-mini-ai-control-v1.js" not in LOADER
    assert "workspace-mini-ai-control-v2.js" not in LOADER


def test_browser_engine_is_deterministic_and_does_not_use_business_transport() -> None:
    for marker in (
        "function canonicalize(value)",
        "Object.keys(value).sort()",
        "canonicalMiniAiHash(identity)",
        'context.categoryIsNew ? ""',
        "viewsCanSelectWinner: false",
        "crossCategoryTransferAllowed: false",
        "humanApprovalRequiredForScale: true",
        "function failClosedContext(rawContext)",
        "approvedWinnerDuration: null",
        "durationPolicy: null",
    ):
        assert marker in ENGINE_V1 + ENGINE_V2
    for forbidden in (
        "fetch(",
        ".functions.invoke",
        "XMLHttpRequest",
        "startRealGeneration",
        "allow_real_spend",
        "source_url",
        "caption_text",
    ):
        assert forbidden not in ENGINE_V2


def test_desk_uses_one_real_form_and_never_calls_provider_directly() -> None:
    for marker in (
        'const FORM_SELECTOR = "#mock-batch-form"',
        "form.requestSubmit(submit)",
        'form.querySelector("#generation-submit, button[type=\'submit\']")',
        "prepareNative(form, plan, arm, state.baseBrief)",
        "form.checkValidity()",
        "real_spend_confirmation",
    ):
        assert marker in DESK
    for forbidden in (
        "fetch(",
        ".functions.invoke",
        "XMLHttpRequest",
        ".api.",
        "Runway",
        "service_role",
    ):
        assert forbidden not in DESK


def test_mass_generation_is_wave_gated_instead_of_unbounded_autopilot() -> None:
    for marker in (
        "wave += 1",
        'execution.status = "awaiting_qa"',
        "Следующая оплата заблокирована",
        "mini_ai_wave_product_ok",
        "mini_ai_wave_technical_ok",
        "ПРОВЕРЕНО ${execution.awaitingWave}",
        "Остановить пакет по дефекту",
        "if (continueWave) scheduleNext()",
    ):
        assert marker in DESK
    assert "await runNext()" not in DESK
    assert "MutationObserver" not in DESK


def test_unknown_provider_outcome_is_fail_closed_and_never_retried() -> None:
    for marker in (
        'savedTask.status = "unknown"',
        "Не повторяйте оплату",
        "За две минуты не найден job",
        "fresh.autopilot = false",
        "execution.autopilot = false",
    ):
        assert marker in DESK


def test_new_job_must_match_both_exact_sku_and_duration() -> None:
    for marker in (
        "function newMatchingJob(before, sku, duration)",
        "text.includes(targetSku)",
        "text.includes(durationText)",
        "waitForJob(",
        "plan.context.sku",
        "arm.durationSeconds",
    ):
        assert marker in DESK


def test_native_job_signature_normalizes_short_russian_duration_copy() -> None:
    for marker in (
        "DURATION_PATTERN",
        'const SIGNATURE_ATTR = "data-mini-ai-job-signature"',
        "miniAiDurationMarker",
        "(?=$|[\\s·|,;])",
        "секунд",
        "function normalizeJob(element)",
        "element.hasAttribute(SIGNATURE_ATTR)",
        "item.matches(JOB_SELECTOR)",
    ):
        assert marker in JOB_SIGNATURE
    assert "\\b/iu" not in JOB_SIGNATURE
    assert "fetch(" not in JOB_SIGNATURE
    assert ".functions.invoke" not in JOB_SIGNATURE


def test_learning_category_is_narrow_persistent_and_never_falls_back_to_compliance() -> None:
    for marker in (
        'const POINTER_KEY = "contentengine.mini-ai-learning-category-pointer.v1"',
        '"electronics"',
        '"cosmetics"',
        "Compliance-категория слишком широка для обучения",
        "car_audio_amplifier",
        'input.value = " "',
        "pointers[baseScope(form)] = category",
        'source: "mini-ai-category-scope"',
    ):
        assert marker in CATEGORY_SCOPE
    for forbidden in (
        "fetch(",
        ".functions.invoke",
        "requestSubmit(",
        "service_role",
    ):
        assert forbidden not in CATEGORY_SCOPE


def test_safe_brief_and_exact_product_are_checked_before_queue() -> None:
    for marker in (
        "Сначала подготовьте безопасное ТЗ",
        "ТЗ не содержит точный SKU",
        "ТЗ не содержит точное название товара",
        "точный товар:",
        "baseBriefHash",
        "Базовое ТЗ повреждено",
    ):
        assert marker in DESK


def test_result_screen_uses_business_outcomes_and_keeps_views_diagnostic() -> None:
    for marker in (
        "Зрелых результатов",
        "Заказы",
        "Корзины",
        "Продажи, ₽",
        "Расход, ₽",
        "Просмотры · диагност.",
        "evaluateMiniAiPlan",
        "Наблюдение не объявляется причинностью",
    ):
        assert marker in DESK
    assert "viewsCanSelectWinner: false" in ENGINE_V1


def test_no_fake_risk_control_is_rendered_in_the_live_desk() -> None:
    assert "mini_ai_risk" not in DESK
    assert 'riskPreset: "balanced"' in DESK


def test_reload_recovery_marks_inflight_task_unknown() -> None:
    for marker in (
        "function recoverExecution(state)",
        'task.status = "unknown"',
        "Вкладка закрылась до подтверждения job",
        'execution.status = "paused"',
    ):
        assert marker in DESK


def test_mini_ai_javascript_parses_when_node_is_available() -> None:
    node_binary = shutil.which("node")
    if not node_binary:
        pytest.skip("Node.js is not installed in this test environment")
    for path in (
        APP_DIR / "mini-ai-control-plane-v1.js",
        APP_DIR / "mini-ai-control-plane-v2.js",
        APP_DIR / "workspace-generation-job-signature-v1.js",
        APP_DIR / "workspace-mini-ai-control-v3.js",
        APP_DIR / "workspace-mini-ai-category-scope-v1.js",
    ):
        subprocess.run(
            [node_binary, "--check", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )


def test_mini_ai_css_is_balanced_and_has_wave_gate() -> None:
    assert BASE_CSS.count("{") == BASE_CSS.count("}")
    assert WAVE_CSS.count("{") == WAVE_CSS.count("}")
    assert ".mini-ai-wave-gate" in WAVE_CSS
    assert "@media (max-width: 720px)" in WAVE_CSS
    assert "@media (prefers-reduced-motion: reduce)" in BASE_CSS
