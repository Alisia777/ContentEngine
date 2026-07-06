from __future__ import annotations

from datetime import date
from typing import Any

from app import models
from app.destination_connectors.credential_status import CredentialStatusService
from app.destination_connectors.types import CredentialCheckResult


class MockTelegramClient:
    def check(self, *, token_configured: bool, chat_id: str | None = None) -> dict[str, Any]:
        return {"ready": token_configured, "chat_id_present": bool(chat_id)}

    def collect_metrics(self, settings: dict[str, Any], period_start: date | None, period_end: date | None) -> list[dict[str, Any]]:
        return list(settings.get("mock_metrics") or [])


class TelegramConnector:
    def __init__(self, client: MockTelegramClient | None = None):
        self.client = client or MockTelegramClient()
        self.credentials = CredentialStatusService()

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        base = self.credentials.check(connection)
        if base.status != "connected":
            return base
        client_status = self.client.check(
            token_configured=base.credential_configured,
            chat_id=(connection.settings_json or {}).get("chat_id"),
        )
        return CredentialCheckResult(
            status="connected" if client_status["ready"] else "needs_auth",
            auth_status="bot_ready" if client_status["ready"] else "needs_auth",
            credential_required=True,
            credential_configured=base.credential_configured,
            message="Telegram mock client is ready." if client_status["ready"] else "Telegram credential is not configured.",
        )

    def collect_metrics(self, connection: models.DestinationConnection, period_start: date | None, period_end: date | None) -> list[dict[str, Any]]:
        return self.client.collect_metrics(connection.settings_json or {}, period_start, period_end)
