# Telegram Connector

The v1.5 Telegram connector is provider-ready and safe by default.

Connection type: `telegram_bot`.

Behavior:

- requires a `credential_ref`, usually `TELEGRAM_BOT_TOKEN`;
- reads the actual token from the environment;
- reports `needs_auth` when the env value is missing;
- uses `MockTelegramClient` in normal tests;
- metric sync can import configured mock rows for acceptance tests.

Example:

```bash
set TELEGRAM_BOT_TOKEN=...
python scripts/add_destination_connection.py --destination-id 1 --type telegram_bot --credential-ref TELEGRAM_BOT_TOKEN
python scripts/check_destination_connection.py --connection-id 1
```

Publishing remains gated by the existing approved publishing flow. v1.5 does not add a path that publishes unreviewed videos.
