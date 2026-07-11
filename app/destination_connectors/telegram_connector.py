from __future__ import annotations

from datetime import date
from app import models
from app.destination_connectors.credential_status import CredentialStatusService
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.types import CredentialCheckResult

class TelegramConnector:
    def __init__(self):
        self.client = None
        self.credentials = CredentialStatusService()

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        return self.credentials.check(connection)

    def collect_metrics(self, connection: models.DestinationConnection, period_start: date | None, period_end: date | None) -> list[dict[str, object]]:
        raise DestinationConnectorDataError(
            "Telegram official metrics adapter is unavailable; use explicit manual or CSV import."
        )
