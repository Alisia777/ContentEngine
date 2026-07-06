# Destination Connectors

v1.5 connects internal owned destinations to safe metric collection paths:

```text
destination
-> connection state
-> credential readiness
-> final URL / publishing task
-> metric import or provider-ready sync
-> campaign performance feedback
```

Supported connection types:

- `manual`: operator-managed metrics.
- `csv`: bulk metrics import.
- `telegram_bot`: provider-ready bot connection, using mock clients in tests.
- `youtube_oauth`: provider-ready analytics connection, using mock clients in tests.
- `instagram_stub`: manual/CSV until an official app is ready.
- `tiktok_stub`: manual/CSV until an official app is ready.

Credentials are stored as `credential_ref` only. The DB never stores token values. UI, API responses, and audit payloads show only configured/not configured status.

Operator CLI:

```bash
python scripts/add_destination_connection.py --destination-id 1 --type manual
python scripts/add_destination_connection.py --destination-id 1 --type telegram_bot --credential-ref TELEGRAM_BOT_TOKEN
python scripts/check_destination_connection.py --connection-id 1
python scripts/sync_destination_metrics.py --connection-id 1 --period-start 2026-07-01 --period-end 2026-07-07
```

UI: open `/destination-connectors`.

Safety boundaries:

- no external account registration;
- no bypass of OAuth, app review, or permissions;
- no unapproved auto-publish path;
- no raw secrets in reports, logs, UI, or DB;
- no real external calls in normal tests.
