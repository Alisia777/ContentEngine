# YouTube Analytics Connector

The v1.5 YouTube connector is provider-ready and safe by default.

Connection type: `youtube_oauth`.

Behavior:

- requires a `credential_ref`;
- reads the actual OAuth credential only from the configured environment or future secret backend;
- reports `needs_auth` when the reference is missing or not configured;
- uses `MockYouTubeAnalyticsClient` in normal tests;
- does not perform real external calls during pytest.

Example:

```bash
python scripts/add_destination_connection.py --destination-id 1 --type youtube_oauth --credential-ref YOUTUBE_ANALYTICS_OAUTH_REF
python scripts/check_destination_connection.py --connection-id 1
```

Future production wiring should use the official YouTube Analytics OAuth/app flow and keep token material outside the application database.
