from __future__ import annotations

import json

from app.product_telemetry.service import _sanitize_string
from app.publishing.destination_service import PublishingDestinationService
from app.routers.pages import redirect
from app.team import TeamService, TeamValidationError


def test_shared_page_redirect_fails_closed_for_external_url_parser_bypasses() -> None:
    assert redirect("/control-room?tab=team").headers["location"] == "/control-room?tab=team"
    for malicious in (
        "https://attacker.test",
        "//attacker.test",
        "/\\attacker.test",
        "/%5c%5cattacker.test",
        "/%255c%255cattacker.test",
        "/%2f%2fattacker.test",
        "/safe\r\nX-Injected: yes",
    ):
        assert redirect(malicious).headers["location"] == "/"


def test_email_sanitizers_are_linear_and_keep_expected_behavior() -> None:
    assert TeamService._email(" Creator+ugc@Example.CO.UK ") == "creator+ugc@example.co.uk"
    try:
        TeamService._email("!" * 20_000)
    except TeamValidationError:
        pass
    else:  # pragma: no cover - documents the fail-closed contract
        raise AssertionError("adversarial email must be rejected")

    adversarial = "+" * 20_000 + "!"
    assert _sanitize_string(adversarial).endswith("…")
    assert _sanitize_string("write to creator+ugc@example.co.uk") == "write to [redacted-email]"


def test_destination_csv_errors_never_echo_raw_rows_or_exception_text() -> None:
    class FailingDestinationService(PublishingDestinationService):
        def create(self, **_values):
            raise ValueError("secret-from-provider-stack")

    result = FailingDestinationService(None).import_csv_text(
        "platform,name,daily_limit\ninstagram,secret-row,not-a-number\n"
    )

    encoded = json.dumps(result)
    assert result["error_count"] == 1
    assert result["errors"] == [
        {"row": 2, "error": "Destination row contains invalid numeric limits."}
    ]
    assert "secret-row" not in encoded
    assert "secret-from-provider-stack" not in encoded
