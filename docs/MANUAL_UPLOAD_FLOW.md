# Manual Upload Flow

Manual upload is the v0.3 default because it is always useful, even before official platform APIs are configured.

## Operator Steps

1. Create or confirm the account on the real platform.
2. Add it to ContentEngine as a publishing destination.
3. Create a publishing package from an approved local video artifact.
4. Approve the package.
5. Schedule a publishing task.
6. Open the manual upload task.
7. Upload the file and metadata on the platform.
8. Paste the final post URL into ContentEngine.
9. Mark the task as `published_manual`.

## Task Payload

The task page exposes:

- local video path;
- title;
- description;
- hashtags;
- CTA;
- destination;
- scheduled time;
- final URL input.

ContentEngine does not automate login, account creation, bypasses, fake engagement, or unofficial upload flows.
