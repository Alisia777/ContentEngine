# Destination Control Statuses

Each tower row summarizes one destination or setup slot.

Status fields:

- `setup_status`: `complete`, `setup_needed`, `needs_manual_setup`, or the current setup/destination status.
- `readiness_status`: latest Destination CRM readiness, usually `ready`, `blocked`, `paused`, or `unknown`.
- `connection_status`: `connected`, `needs_auth`, `no_connection`, or connector status.
- `publishing_status`: `published`, task status, or `no_posts`.
- `metrics_status`: `synced`, `no_metrics`, or `sync_needed`.
- `performance_status`: `strong`, `neutral`, `weak`, or `unknown`.

Next actions:

- `complete_destination_setup`
- `refresh_readiness`
- `add_connection`
- `import_metrics`
- `sync_metrics`
- `pause_destination`
- `activate_destination`
- `increase_capacity`
- `create_publishing_task`
- `investigate_low_performance`
- `monitor`

Rows may include blockers from Destination CRM, capacity checks, connection gaps, missing metrics, or weak performance.
