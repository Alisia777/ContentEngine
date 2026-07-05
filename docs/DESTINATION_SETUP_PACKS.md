# Destination Setup Packs

Destination setup packs are internal operator packs for owned or partner destinations.

They include:

- suggested account name;
- handle options;
- bio text;
- avatar/reference guidance;
- content pillars;
- first 9 post ideas;
- setup checklist;
- platform;
- SKU or theme focus;
- status.

Statuses:

- `needs_manual_setup`
- `ready`
- `active`
- `paused`

## Boundary

ContentEngine does not create accounts on external platforms. It prepares the setup pack, readiness metadata, manual upload task, and final URL tracking. Operators or approved platform APIs handle the actual destination setup and publishing.

## Publishing Policy

Destination setup packs create draft records in the generic destination registry so CampaignDistributionPlanner can calculate capacity. Only approved publishing packages can become publishing tasks. Prompt-only output stays blocked until a video exists and human approval is recorded.
