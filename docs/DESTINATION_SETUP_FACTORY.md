# Destination Setup Factory

v1.3 converts launch capacity gaps into safe destination setup work that an operator can execute.

## Workflow

```text
Launch readiness capacity gap
-> DestinationSetupRequirement
-> DestinationProfilePack
-> DestinationSetupTask
-> operator marks complete with final URL or handle
-> internal PublishingDestination is created
```

## Safety Boundary

ContentEngine only plans and tracks owned destinations. It does not register external accounts, verify accounts on third-party platforms, bypass platform rules, create fake engagement, use proxy or anti-detect logic, or publish unapproved videos.

For platforms with official upload APIs, setup packs mark official API/OAuth as preferred when `token_valid`. Until that exists, the destination remains manual-assisted.

## CLI

```bash
python scripts/destination_setup_requirements.py --campaign-id 1
python scripts/generate_destination_profile_packs.py --campaign-id 1
python scripts/create_destination_setup_tasks.py --campaign-id 1
python scripts/complete_destination_setup_task.py --task-id 1 --url "https://example.com/account" --handle "@example"
```

After completion, the operator can create an internal destination record from the setup task through `/destination-setup` or `POST /api/destination-setup/tasks/{task_id}/create-destination`.

## API

- `POST /api/destination-setup/campaigns/{campaign_id}/requirements`
- `GET /api/destination-setup/campaigns/{campaign_id}/requirements`
- `POST /api/destination-setup/campaigns/{campaign_id}/profile-packs`
- `GET /api/destination-setup/profile-packs/{id}`
- `POST /api/destination-setup/profile-packs/{id}/create-task`
- `GET /api/destination-setup/tasks`
- `PATCH /api/destination-setup/tasks/{id}`
- `POST /api/destination-setup/tasks/{id}/mark-complete`
- `POST /api/destination-setup/tasks/{id}/create-destination`
