from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_PATH = (
    ROOT / "supabase" / "functions" / "creator-product-research" / "index.ts"
)
EDGE_TEST_PATH = (
    ROOT
    / "supabase"
    / "functions"
    / "creator-product-research"
    / "index_test.ts"
)
VIEW_PATH = ROOT / "web" / "app" / "product-research-view.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_credit_balance_failure_points_only_to_openai_api_billing() -> None:
    edge = read(EDGE_PATH)
    failure = edge.split(
        "export function providerTerminalFailure", 1
    )[1].split("function providerResponsePending", 1)[0]
    view = read(VIEW_PATH)

    for marker in (
        'diagnostic.code === "credit_balance_exhausted"',
        'failureCode = "provider_configuration_error"',
        "Баланс OpenAI API исчерпан",
        "OpenAI Platform → Billing",
        "GitHub Pro",
        "PayPal",
        "GitHub Actions",
        "Автоматического повтора не было",
    ):
        assert marker in failure
    assert (
        'provider_configuration_error: '
        '"требуется настройка или пополнение баланса OpenAI API"'
    ) in view


def test_bounded_provider_configuration_and_policy_codes_are_executable() -> None:
    edge = read(EDGE_PATH)
    tests = read(EDGE_TEST_PATH)
    safe = edge.split("const SAFE_PROVIDER_ERROR_CODES", 1)[1].split(
        "]);", 1
    )[0]
    configuration = edge.split(
        "const PROVIDER_CONFIGURATION_DIAGNOSTIC_CODES", 1
    )[1].split("]);", 1)[0]
    rejected = edge.split(
        "const PROVIDER_REJECTED_DIAGNOSTIC_CODES", 1
    )[1].split("]);", 1)[0]

    configuration_codes = (
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "data_residency_mismatch",
    )
    for code in configuration_codes:
        assert f'"{code}"' in safe
        assert f'"{code}"' in configuration
        assert f'code: "{code}"' in tests
    assert '"bio_policy"' in safe
    assert '"bio_policy"' in rejected
    assert 'code: "bio_policy"' in tests
    assert "SAFE_PROVIDER_NONFAILED_ERROR_CODES" in edge
    assert '"responses_cancelled.unclassified"' in tests
    assert '"responses_incomplete.content_filter"' in tests
    assert (
        'Deno.test("billing residency and policy codes produce bounded actionable failures"'
        in tests
    )
