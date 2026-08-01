from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADVISOR = (ROOT / "web/app/workspace-generation-learning-advisor.js").read_text(
    encoding="utf-8"
)
LOADER = (ROOT / "web/app/workspace-os-v4-loader.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/workspace-generation-learning-advisor.css").read_text(
    encoding="utf-8"
)


def test_generation_advisor_exposes_all_supported_durations_without_eight_second_lock() -> None:
    for token in (
        "allowed: Object.freeze([2, 5, 8, 10])",
        "coldStart: Object.freeze([5, 8])",
        "allowed: Object.freeze([4, 8, 12, 15])",
        "coldStart: Object.freeze([8, 12])",
        "Восемь секунд — один arm, а не обязательный результат",
    ):
        assert token in ADVISOR


def test_generation_advisor_never_calls_business_api_or_submits_generation() -> None:
    forbidden = (
        "fetch(",
        ".functions.invoke",
        "requestSubmit(",
        ".submit(",
        "startRealGeneration",
        "allow_real_spend",
    )
    for token in forbidden:
        assert token not in ADVISOR
    assert "eligible_for_direct_prompt" not in ADVISOR


def test_generation_advisor_accepts_only_a_server_issued_policy_hint() -> None:
    for token in (
        'value.source !== "creator_generation_learning_policy"',
        "POLICY_HASH.test",
        "generationDurationPolicy",
        "Чужая категория не передаёт winner",
    ):
        assert token in ADVISOR
    assert "value.signed" not in ADVISOR


def test_advisor_buttons_are_not_nested_inside_the_duration_label() -> None:
    assert "durationField.after(panel)" in ADVISOR
    assert "durationField.append(panel)" not in ADVISOR


def test_advisor_observer_cannot_loop_on_its_own_attribute_updates() -> None:
    assert "panel.dataset.renderSignature" in ADVISOR
    assert 'observer.observe(form, { childList: true, subtree: true })' in ADVISOR
    assert "attributes: true" not in ADVISOR


def test_generation_route_loads_advisor_lazily() -> None:
    assert '"workspace-generation-learning-advisor.css?v=20260801.1"' in LOADER
    assert '"workspace-generation-learning-advisor.js?v=20260801.1"' in LOADER
    assert ".generation-duration-advisor" in STYLES
    assert "prefers-reduced-motion" in STYLES
