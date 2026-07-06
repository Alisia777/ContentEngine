# Destination Capacity

Destination capacity measures whether a campaign has enough owned/manual/API-ready placement points for its launch target.

`DestinationCapacityService` counts only active destinations.

## Rules

- `status=active` destinations count.
- `paused`, `draft`, and `disabled` destinations do not count as active capacity.
- Manual destinations count when `posting_mode=manual`.
- API destinations count only when `posting_mode=api` and `auth_status=token_valid`.
- Daily and weekly limits define usable capacity.
- If active destinations are below the campaign target, `destination_gap` is added.
- If required slots exceed weekly capacity, `capacity_gap` is added.

## Output

The service persists `DestinationCapacitySnapshot` with:

- total destinations;
- active destinations;
- manual/API-ready split;
- daily and weekly capacity;
- required slots;
- capacity gap;
- blockers and warnings.
