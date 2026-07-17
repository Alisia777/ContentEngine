# Auth access and email delivery operations

This runbook covers the production path for team invitations, password
recovery and delivery visibility. The public application remains GitHub Pages;
all privileged actions run through Supabase Auth, PostgreSQL RPCs and narrow
Edge Functions.

## User-facing contract

Managers use one action: **Проверить и восстановить доступ**.

The server inspects the exact organization-scoped account and chooses a safe
result:

- the account is active and needs no message;
- create an invitation for an absent account;
- send recovery for an existing account;
- suppress a duplicate request during the server cooldown;
- stop on a banned, deleted, provider-failed, suppressed, bounced, complained
  or cross-organization target.

The manager never receives an action token, generated link, Auth UUID, password
or provider payload.

## Stored states

Dispatch and inbox delivery are deliberately separate.

Dispatch:

- `reserved`;
- `accepted`;
- `failed`;
- `suppressed`.

Delivery:

- `unknown`;
- `accepted_unconfirmed`;
- `deferred`;
- `delivered`;
- `failed`;
- `bounced`;
- `suppressed`;
- `complained`.

`accepted_unconfirmed` means only that Supabase/Auth accepted the request. It
must never be displayed as inbox delivery.

Provider events are append-only and idempotent. Duplicate event IDs with the
same normalized fields are harmless replays. A reused event ID with different
normalized fields is a conflict. Out-of-order events cannot downgrade a later
delivery state; provider failure, suppression, bounce and complaint remain
terminal safety signals.

## 1. Verify the sending domain

Use a dedicated authentication subdomain such as `auth.example.com`.

At the DNS provider:

1. publish the SMTP provider's exact SPF authorization;
2. publish its exact DKIM record;
3. publish one DMARC record;
4. wait for public DNS propagation;
5. verify the domain in the mail provider dashboard.

Do not copy example DNS values. Use the exact selector, include token and target
given for the selected provider.

## 2. Store protected production values

In the GitHub `production` environment configure:

- `SMTP_ADMIN_EMAIL`;
- `SMTP_HOST`;
- `SMTP_PORT`;
- `SMTP_USER`;
- `SMTP_PASS`;
- variable `SMTP_SENDER_NAME`;
- for Resend delivery events, `RESEND_WEBHOOK_SECRET`.

For daily DNS drift monitoring, also add these non-secret environment
variables:

- `AUTH_EMAIL_SENDING_DOMAIN`;
- `AUTH_EMAIL_DKIM_SELECTOR`;
- `AUTH_EMAIL_EXPECTED_SPF_INCLUDE`;
- `AUTH_EMAIL_DKIM_RECORD_TYPE`;
- `AUTH_EMAIL_EXPECTED_DKIM_VALUE`.

The scheduled **Monitor Auth email DNS** workflow stays a harmless no-op until
all five values exist. Once configured, any SPF, DKIM or DMARC drift fails the
daily run instead of remaining invisible until the next invitation problem.

Never add these values to `web/app/config.js`, repository variables, workflow
inputs, issue comments or logs.

## 3. Configure Supabase Auth SMTP

Run the protected workflow **Configure production Auth SMTP** from `main`.
Provide only the public DNS expectations requested by the workflow. It checks
SPF, DKIM and DMARC before applying the Auth configuration.

After completion, run the normal production deploy once so the optional signed
webhook secret is synchronized to the Edge runtime.

Removing `RESEND_WEBHOOK_SECRET` from the protected environment and running the
normal deploy explicitly unsets any previously synchronized Edge secret. This
is the supported fail-closed disable/rotation path; deleting only the provider
webhook is not sufficient evidence that the old signing key was revoked.

## 4. Configure delivery events

For Resend, use:

```text
https://<project-ref>.supabase.co/functions/v1/auth-email-webhook
```

Enable the provider's sent, delivered, delayed, failed, suppressed, bounced and
complained events.
The endpoint:

- accepts only `POST`;
- limits the raw body;
- verifies the Svix signature and timestamp before parsing JSON;
- stores only normalized safe fields, never the raw payload;
- does not enable browser CORS;
- never stores the email body, action link or token.

If the provider does not include an application correlation ID, matching is
limited to a bounded recipient/time window. More than one candidate is marked
`ambiguous`; no attempt is falsely marked delivered.

## 5. Canary procedure

Use two controlled mailboxes, not a 50-person batch.

1. From the team screen invite the first mailbox.
2. Confirm the portal first shows `accepted_unconfirmed`.
3. Confirm the provider log and mailbox receive the message.
4. Confirm the portal advances to `delivered`.
5. Complete the first login and password change.
6. Use **Проверить и восстановить доступ** for the second mailbox.
7. Confirm recovery delivery and successful password update.
8. Send a provider test delayed/bounce event and confirm the portal shows the
   corresponding safe state without offering an unsafe retry.
9. Repeat a webhook event and confirm no duplicate attempt/event is created.

Only after this canary should the Auth and provider rate limits be raised for
larger batches.

## Failure handling

- `accepted_unconfirmed`: inspect the provider log before retrying.
- `deferred`: wait for the provider's next attempt; do not create a mail burst.
- `failed`: inspect the provider configuration, domain and quota before retrying.
- `bounced`: verify/correct the address before another send.
- `suppressed`: stop automatic retries and inspect the provider suppression list.
- `complained`: stop automated mail and escalate to an administrator.
- `ambiguous`: inspect the provider log; the portal intentionally refuses to
  guess which attempt was delivered.
- expired link: use the single access-repair action; only the newest email
  should be used.

## Required release evidence

Before claiming production email is ready, retain:

- green CI including pgTAP and both Edge Function checks;
- successful production deployment;
- public SPF/DKIM/DMARC verification;
- one delivered invitation;
- one delivered recovery;
- one replay-safe webhook test;
- portal evidence that delivery states are visible and organization-scoped.
