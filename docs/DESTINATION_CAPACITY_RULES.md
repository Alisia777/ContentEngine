# Destination Capacity Rules

Campaign destination capacity is calculated from readiness snapshots.

Counted as ready:

- active manual destinations with handle or URL and remaining capacity;
- active API destinations with `token_valid` or `api_ready` and remaining capacity;
- active Telegram/manual destinations with final handle or URL and remaining capacity.

Not counted:

- paused or disabled destinations;
- destinations with missing handle/URL;
- API destinations without valid auth;
- destinations with zero daily or weekly capacity;
- destinations whose warmup phase leaves no remaining capacity.

Campaign capacity compares available weekly capacity against `campaign.target_video_count`. If available capacity is lower, the CRM reports a capacity gap and recommends adding, activating, or warming up destinations.
