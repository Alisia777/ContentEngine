# Publishing Destinations

A publishing destination is an owned or authorized account/channel/page where an operator can publish approved video content.

Fields:

- `brand`
- `platform`
- `name`
- `handle`
- `url`
- `owner_name`
- `status`: `draft`, `active`, `paused`, `disabled`
- `posting_mode`: `manual`, `api`, `disabled`
- `auth_status`: `manual_only`, `not_configured`, `token_valid`, `token_expired`, `needs_review`
- `allowed_formats_json`
- `daily_limit`
- `weekly_limit`
- `notes`

## Readiness

Manual mode is ready when:

- destination status is `active`;
- posting mode is `manual`;
- daily and weekly limits are positive.

API mode is blocked until `auth_status=token_valid`. v0.3 keeps API providers provider-ready only; manual upload is the working default.

## Limits

The scheduler counts tasks with these statuses:

- `scheduled`
- `manual_upload_required`
- `published_manual`
- `published_api`

If the count reaches `daily_limit` or `weekly_limit`, scheduling is blocked.
