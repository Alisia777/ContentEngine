# YouTube Shorts Playbook

Publish the assigned Short and keep the tracking link in the description, comment, pinned comment, or assigned link location.

Use YouTube Analytics connector when OAuth is configured. Use CSV/manual fallback when OAuth is not configured.

Return:

- `final_url`
- views
- likes
- comments
- watch time when available
- retention when available
- clicks through `tracking_link`

Watch time and retention are quality signals; clicks still need the ContentEngine tracking link.
