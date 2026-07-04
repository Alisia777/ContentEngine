# Publishing Workflow

v0.3 adds a safe publishing layer after video generation. It does not create platform accounts and it does not auto-publish unreviewed generated videos.

Core flow:

```text
approved video artifact
-> publishing package
-> owned destination registry
-> publishing calendar
-> manual upload task
-> final post URL saved
-> published_manual
```

## Safety Rules

- Platform accounts are created or confirmed manually outside ContentEngine.
- ContentEngine stores owned destinations only.
- A package cannot be scheduled until it is approved.
- The video file must exist and be non-empty.
- A destination must be active.
- Manual posting works without API credentials.
- API posting fails clearly until official credentials are configured.
- Daily and weekly destination limits are enforced.
- A generated video with an unapproved `QualityReview` cannot be package-approved without explicit manual override.
- Manual override is logged in package metadata and review records.

## CLI

```bash
python scripts/add_publishing_destination.py --platform telegram --name "Altea Telegram" --posting-mode manual
python scripts/import_publishing_destinations.py --file destinations.csv
python scripts/create_publishing_package.py --video-job-id 11 --platform telegram
python scripts/approve_publishing_package.py --package-id 1
python scripts/schedule_publishing_task.py --package-id 1 --destination-id 1 --scheduled-at "2026-07-05T12:00:00"
python scripts/bulk_schedule_publishing_tasks.py --package-ids "1,2,3" --destination-ids "1,2" --start-at "2026-07-05T12:00:00" --interval-minutes 90
python scripts/mark_manual_published.py --task-id 1 --url "https://example.com/post"
```

If a `QualityReview` is still `needs_human_review`, approval requires:

```bash
python scripts/approve_publishing_package.py --package-id 1 --manual-override --notes "Human checked the artifact."
```

## API

```text
POST /api/publishing/destinations
GET  /api/publishing/destinations
GET  /api/publishing/destinations/{id}
PATCH /api/publishing/destinations/{id}
POST /api/publishing/destinations/{id}/readiness-check

POST /api/publishing/packages
GET  /api/publishing/packages
GET  /api/publishing/packages/{id}
POST /api/publishing/packages/{id}/approve
POST /api/publishing/packages/{id}/reject

POST /api/publishing/tasks/schedule
GET  /api/publishing/tasks
GET  /api/publishing/tasks/{id}
POST /api/publishing/tasks/{id}/run
POST /api/publishing/tasks/{id}/mark-manual-uploaded
POST /api/publishing/tasks/{id}/cancel
GET  /api/publishing/calendar
```

## UI

Open `/publishing`.

The page shows:

- destinations / owned accounts;
- publishing packages;
- calendar tasks;
- manual upload tasks with final URL capture.

## Scale Operations

For 40 SKUs, 120 owned destinations, and hundreds of videos:

1. Import destinations from CSV.
2. Create packages only from approved local video artifacts.
3. Approve packages after human review.
4. Bulk-schedule approved package ids across destination ids.
5. Operators work through manual upload tasks and paste final URLs.

Bulk scheduling uses round-robin distribution across destination ids and still enforces every normal gate:

- package must be `approved`;
- destination must be `active`;
- video file must exist and be non-empty;
- daily and weekly limits must not be exceeded.

Use `--dry-run` before creating tasks:

```bash
python scripts/bulk_schedule_publishing_tasks.py --package-ids "1,2,3" --destination-ids "1,2" --start-at "2026-07-05T12:00:00" --dry-run
```
