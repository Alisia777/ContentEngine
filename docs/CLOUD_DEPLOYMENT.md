# Supabase-native deployment for creator teams

Production ContentEngine is a browser-only workspace at one public HTTPS URL.
Creators do not install Python, open `127.0.0.1`, share a local password, or
exchange folders with generated files.

## Production topology

```text
GitHub main
  -> required CI checks
  -> versioned SQL from supabase/migrations
       -> existing paid Supabase project
            - Auth
            - PostgreSQL schemas and narrow RPC functions
            - private Storage bucket contentengine-private
            - authenticated creator-invite Edge Function
  -> static artifact from web/app
       -> GitHub Pages
            - login and mandatory training
            - final operator exam
            - generation, placement, stats, payouts, tasks and feedback
```

The browser talks directly to Supabase with a publishable key. It never receives
a database password, personal access token, secret/service-role key, or provider
credential. Every business mutation goes through a narrow `public.creator_*`
RPC that derives the caller from `auth.uid()`. Durable state lives in PostgreSQL
and private media lives in Supabase Storage.

There is no general production application server or container. Narrow,
authenticated Supabase Edge Functions provide the server-only boundaries for
invitations, password setup, paid video generation, and product research. The
Python/FastAPI monolith in `app/`, `scripts/`, `migrations/`, and `Dockerfile`
remains a reference implementation and regression harness only.

## Current MVP capability boundary

The Supabase-native portal supports both free mock tasks and explicitly
confirmed paid provider operations. Paid video generation and paid product
research remain behind authenticated Edge Functions, role/certification gates,
idempotent database commands, quotas, and a human confirmation in the portal.
Provider keys are server-only Supabase secrets and never enter the Pages
artifact. Product research produces source-backed editable drafts and a
heuristic creative-potential score; it does not promise views or sales and does
not create creator tasks until a person approves the draft.

## Repository contract

- `web/app/` is the only production frontend artifact.
- `supabase/migrations/*.sql` is the only production database change stream.
- `supabase/functions/creator-invite/` is deployed after migrations with JWT
  verification explicitly enabled; deployment never uses `--no-verify-jwt` or
  `--prune`.
- `supabase/config.toml` owns the hosted Auth/API settings. Production deploy
  runs `supabase config push` against the reviewed project ref, so the Pages Site URL, closed
  signup, password policy and redirect allowlist cannot drift into an
  undocumented dashboard-only state.
- `.github/workflows/supabase-pages.yml` starts automatically only after the
  `CI` workflow succeeds for `main`. It applies immutable SQL migrations through
  the official Supabase Management API, records their SHA-256 checksums in the
  private `contentengine_deploy.schema_migrations` table, provisions private
  exam grading material entirely in memory with command output withheld, and
  publishes the Pages artifact only after the database job succeeds. Missing,
  malformed or changed migration material fails closed. Pull-request/fork
  completions are rejected; manual recovery runs are accepted only from the
  `main` ref.
- `.github/workflows/ci.yml` starts a local Supabase database, applies every SQL
  migration, lints it, runs the committed pgTAP security/workflow contract,
  formats/lints/type-checks the invitation Function, and also keeps the Python
  reference suite green.
- Production schema changes are never made manually in the Table Editor or SQL
  Editor after migration ownership is established.

The browser adapter calls these authenticated functions, each with exactly one
`p_payload jsonb` argument:

```text
creator_bootstrap
creator_complete_module
creator_submit_exam
creator_workspace_section
creator_create_mock_batch
creator_confirm_placement
creator_record_metric
creator_set_wb_alias
creator_decide_payout
creator_transition_task
creator_create_feedback
creator_register_media
creator_capture_event
```

The RPC layer owns organization scope, role checks, the training/exam gate,
idempotency, state transitions, and safe response shapes. The browser must not
write application tables directly.

Two additional RPCs are administrative boundaries and are never granted to a
browser role: `system_initialize_owner(p_payload jsonb)` creates the first
organization/owner exactly once, and
`system_provision_invited_member(p_payload jsonb)` attaches an Auth user as a
trainee after an authorized invitation. Both are `service_role`-only,
idempotent and audited. `creator_bootstrap` never creates or restores a
membership; an Auth user without one receives `membership_required`.

## One-time GitHub configuration

In repository **Settings -> Pages**, select **GitHub Actions** as the publishing
source. The workflow deploys to the `github-pages` environment.

Create a protected GitHub environment named `production`. Configure these
encrypted secrets in that environment:

| Secret | Purpose |
| --- | --- |
| `SUPABASE_ACCESS_TOKEN` | Revocable Supabase personal access token used only by the production migration/configuration steps |
| `SUPABASE_EXAM_KEYS_B64` | Base64-encoded, idempotent SQL payload that provisions the private exam grading keys after migrations |
| `SUPABASE_OWNER_EMAIL` | Exact email that receives the one-time first-owner password setup link; consumed only by the protected production job |
| `RUNWAYML_API_SECRET` | Server-only provider key synchronized to Supabase for explicitly confirmed paid video generation |
| `OPENAI_API_KEY` | Server-only provider key synchronized to Supabase for explicitly confirmed product research with web search and image analysis |
| `CONTENTENGINE_WORKER_SECRET` | Random 32+ character secret synchronized to the private Edge worker and Supabase Vault for native Cron dispatch |

Configure these as repository **Variables**, because the independent Pages
build job must read them:

| Variable | Required value |
| --- | --- |
| `SUPABASE_PROJECT_REF` | Project reference from the Supabase dashboard URL |
| `SUPABASE_PUBLISHABLE_KEY` | Browser-safe key beginning with `sb_publishable_` |

The workflow also compares `SUPABASE_PROJECT_REF` with the reviewed production
project reference committed in the workflow. A missing or different value
stops both migration and Pages build instead of targeting another project.

Never configure `sb_secret_*`, `service_role`, a database URL, or a provider key
as a Pages variable. The build creates `_site/config.js` at release time and
fails if the key is not a publishable key or if the artifact contains a server
secret/local endpoint marker.

Prepare `SUPABASE_EXAM_KEYS_B64` outside the repository and paste it directly
into the environment-secret form. Do not place the decoded grading SQL in a
commit, issue, Actions input, screenshot, artifact or chat. The provisioning
step scopes the secret to one step, decodes and validates it only in process
memory, withholds all database-command output and blocks the release if
validation or application fails.

Being signed in to the Supabase dashboard does not authorize a GitHub runner.
The dashboard session is for the human operator; `SUPABASE_ACCESS_TOKEN`
provides the separate, revocable Management API and CLI boundary used by
Actions. No database password is stored in GitHub.

The invitation Function receives the standard Supabase runtime credentials in
its managed server environment; no service-role/secret key is copied into
GitHub variables or the Pages artifact. The first-owner step uses the protected
Management API token to reveal one service-role server key only in runner
memory (preferring a scoped `sb_secret_*` key over the legacy JWT), creates a
confirmed identity only when `SUPABASE_OWNER_EMAIL` does not exist, calls the
service-role-only initializer, sends one password-recovery link, and marks that
delivery idempotently. The key and recovery token are never printed or stored.
An existing unconfirmed identity fails closed for manual review instead of
being admin-confirmed, because it may carry an attacker-selected password from
earlier configuration drift.
The owner job depends on the successful Pages deployment, so the password link
is not sent until the committed `/auth/accept/` bridge is live at the canonical
URL.
Subsequent invitations must authenticate the caller and enforce owner/admin
organization scope before using Auth Admin operations.

### Durable background work and notification delivery

Supabase Cron runs `contentengine-background-worker-v1` every two minutes and
uses `pg_net` plus two named Vault secrets to invoke the private Edge worker.
The browser and GitHub scheduler are not in the production processing path.
The GitHub `Watch background content health` workflow remains an hourly
provider-free Edge endpoint/outbox smoke and a manual smoke entrypoint. It does
not validate or replace the native Cron schedule. The
worker polls only already-submitted Runway task IDs; it never calls the paid
generation start action and never selects `queued` or `starting` generation
rows for a paid retry.

Each invocation first obtains a database-owned lease and records a durable run
and heartbeat. Generation poll timing, attempts, last failure and stalled state
are also server-owned. Overlapping invocations do not claim the same work, and
a stalled provider task creates one deduplicated operator notification instead
of silently polling forever or repeating the paid POST.

Before dispatch, the worker calls the service-role-only lease reconciler.
Expired product-research and content-review leases become terminal
`processing_lease_expired` failures in one database transaction. They are not
requeued because the provider may already have accepted the paid request. A
human must inspect the history and explicitly create a new run.

Terminal generation, research and review transitions write a transactional
notification outbox row. Delivery uses short database leases, an idempotent
notification key and bounded exponential retry. If notification insertion
commits but the RPC response is lost, the next cycle observes the existing
notification and marks the outbox row delivered. After 12 failed attempts the
row remains as a visible failed outbox item; it is never silently deleted.

The smoke workflow prints only aggregate queue and outbox counts. Endpoint,
authentication, database or unresolved-notification failures make it fail; the
manager health RPC separately reports stale heartbeats and stalled generation.
Never put the worker secret, recipient identifiers or notification bodies into
workflow output. The complete rotation, incident and verification procedure is in
[`BACKGROUND_WORKER_OPERATIONS.md`](BACKGROUND_WORKER_OPERATIONS.md).

## Existing paid Supabase project

Reuse the paid project; do not create another paid project merely to host this
MVP. Before the first migration:

1. Back up the project and confirm its region and owner access.
2. Confirm that the project is intended for ContentEngine. Do not apply these
   migrations blindly to a project whose `content_factory` schemas or
   `contentengine-private` bucket belong to another application.
3. Inspect `contentengine_deploy.schema_migrations` before adopting a project
   that already has manually applied copies of these objects. Reconcile that
   history deliberately; never fabricate a checksum row. The deployer refuses
   to continue when a recorded migration checksum differs from Git.
4. Keep the Supabase Data API enabled and keep `public` exposed: the SPA uses
   PostgREST only for the narrow `public.creator_*` functions. Do not expose the
   `content_factory_private` schema.
5. Confirm Auth email/password is enabled, public sign-up is disabled, and the
   minimum password policy matches `supabase/config.toml`.
6. Set the Auth Site URL to
   `https://alisia777.github.io/ContentEngine/` and allow redirects under
   `https://alisia777.github.io/ContentEngine/**`. These values are committed in
   `supabase/config.toml` and applied by `supabase config push`; localhost is
   not part of the production Auth redirect allowlist.

The migrations create the private bucket `contentengine-private`. Its
`public` flag must remain `false`. Creator object names use this authority
shape:

```text
<organization-uuid>/<creator-auth-uuid>/<folder>/<filename>
```

Storage RLS requires active membership and the final operator certification.
A creator can manage their own prefix; an owner/admin can inspect the team's
prefixes within the same organization. Signed/object URLs do not grant another
organization access through the application contract.

## First production release

1. Review the SQL migrations and take a Supabase backup.
2. Add both GitHub environment secrets and both repository variables above
   without pasting them into issues, commits, screenshots, or chat.
3. Merge the reviewed branch into `main`.
4. Wait for **CI** on `main`, then watch **Deploy Supabase and GitHub Pages**.
   A failed or pull-request CI run cannot start production. The `migrate` job
   must finish before `deploy-pages` can publish the interface.
5. If the Management API deployer reports an immutable checksum mismatch or a
   failed migration, stop and inspect `contentengine_deploy.schema_migrations`.
   Do not publish a frontend against a partially migrated RPC contract.
6. Confirm the protected owner-bootstrap step created or reconciled the exact
   `SUPABASE_OWNER_EMAIL`, called the service-role-only
   `system_initialize_owner`, and reported `recovery=sent` (or
   `recovery=not_required` on a safe replay). Open the recovery email and set a
   strong password through the committed `/auth/accept/` route. Never expose
   the service-role credential or initializer to Pages.
   The invariant after initialization is **Exactly one active membership** for
   the first owner. Bootstrap never falls back to a sole-organization autojoin
   or silently restores an inactive membership.
7. Invite subsequent creators through the **Team** tab. The authenticated Edge
   Function uses Auth Admin and then calls `system_provision_invited_member` to
   create a `trainee` membership in the caller's organization. A separately
   created Auth user is not auto-enrolled and receives `membership_required`.
8. For a demonstration guest, use the same Auth Admin plus provisioning path,
   keep the temporary password out of Git, and give the account no owner/admin
   or paid-generation capability.

### Protected limited-member provisioning

When custom SMTP is not yet available and an explicitly authorized external
member must be created, use the manual **Provision limited Supabase member**
workflow. Put a strong one-time value in the production environment secret
`SUPABASE_MEMBER_TEMP_PASSWORD`, dispatch the workflow from `main` with the
exact email, display name, and either `viewer` or `trainee`, then delete the
secret immediately after a successful run. The password is never accepted as
a workflow input, committed, uploaded as an artifact, or printed to Actions
logs.

Use `viewer` for a stable guest account and `trainee` for a participant who is
expected to complete training and become an operator. The workflow calls the
dedicated service-role-only `system_provision_limited_member` RPC. It rejects
privileged roles and fails closed for an unconfirmed, unrelated, inactive,
role-mismatched, or cross-organization identity. An idempotent replay never
resets the password. Deliver the temporary password through a separate trusted
channel and require the recipient to change it after the first sign-in.

The workflow is intentionally serialized with `cancel-in-progress: false` so
two pushes cannot cancel or overlap a production migration.

## Release acceptance

A release is complete only when all of the following are verified against the
hosted project:

- GitHub Pages responds over HTTPS and contains no localhost link;
- an invited creator can sign in and an unknown account cannot self-enroll;
- the workspace remains closed until four course modules and the final exam are
  passed;
- after certification, Generation, Placement, Statistics, Payouts, Tasks and
  What to add load through the RPC boundary;
- a mock batch of 50 is accepted and 51 is rejected;
- `mode=real` and `allow_real_spend=true` are rejected by PostgreSQL;
- a creator can access only their private media prefix;
- an owner/admin can inspect the team scope but another organization cannot;
- placement, metric, payout and feedback events remain organization-scoped and
  auditable.

If database deployment succeeds but Pages deployment fails, fix/retry the
static artifact; do not roll back durable data by editing production manually.
If a migration fails, Pages is not published by the workflow.

## Scaling for 50+ creators

GitHub Pages serves static assets and does not hold sessions or files. Supabase
handles Auth, database concurrency, RLS, object storage, and the narrow
provider-facing Edge Functions. Add indexes and RPC pagination based on measured
query latency; do not add client-side table access or shared secrets to improve
speed. Every paid action must keep its explicit confirmation, quota,
idempotency, and audit trail as capacity grows.

An owner/admin uses the **Команда** tab, which calls the authenticated
`creator-invite` Edge Function for batches of at most 50 unique addresses. The
Function rechecks organization role and `workspace_open` through the caller's
RLS-scoped RPC before using Auth Admin, then provisions the exact invited Auth
user through the service-role-only system RPC. Every invited account starts as
a `trainee` and must independently complete all four modules plus the
12-scenario final exam; a bulk invite never grants operator access. Creating an
Auth user outside this path does not create a membership.

Configure the Supabase **Invite user** email template to return the one-time
token to the public application, where it is exchanged server-side by Auth:

```text
<PUBLIC_APP_URL>/auth/accept#token_hash={{ .TokenHash }}&type=invite
```

Replace `<PUBLIC_APP_URL>` with the canonical HTTPS application origin. Do not
put access tokens, service-role keys, or database credentials into the template.
The default fragment redirect is insufficient because GitHub Pages must first
serve the committed `/auth/accept` bridge without discarding the token hash.

Do not promise external invitation delivery until custom SMTP is configured.
Supabase's built-in sender is for exploration only: it sends only to addresses
pre-authorized as members of the Supabase organization and is currently limited
to 2 messages per hour. After custom SMTP is enabled, Supabase initially applies
a 30-messages-per-hour limit. Before inviting 50+ people, raise the Auth rate
limit and the provider limit together, verify SPF/DKIM/DMARC, and roll out in
controlled batches rather than creating an email spike.

### Production Auth SMTP cutover

The repository contains a protected manual workflow,
`Configure production Auth SMTP`. Use it only after the chosen mail provider
has verified a dedicated authentication sending domain (for example,
`auth.example.com`) and published its DNS records.

Add these values to the protected GitHub `production` environment:

| Name | Kind | Purpose |
| --- | --- | --- |
| `SMTP_ADMIN_EMAIL` | secret | Exact From address, for example `no-reply@auth.example.com` |
| `SMTP_HOST` | secret | Provider SMTP hostname |
| `SMTP_PORT` | secret | Provider SMTP port, normally `587` |
| `SMTP_USER` | secret | Provider SMTP user |
| `SMTP_PASS` | secret | Provider SMTP password or token |
| `SMTP_SENDER_NAME` | variable | Human-readable sender name |
| `RESEND_WEBHOOK_SECRET` | secret | Optional Resend/Svix signing secret for delivery events |

Dispatch the workflow from `main` and enter the exact domain after `@`, the
provider's DKIM selector, its exact SPF `include:` token, the DKIM record type,
and the exact DKIM CNAME target or complete TXT value. The workflow rejects
multiple SPF/DMARC records, an SPF record that does not authorize the reviewed
provider, a revoked/empty DKIM key, and any DKIM value that differs from the
provider instructions. Only after those checks does it validate the protected
SMTP values and patch the official Supabase Auth configuration through the
Management API. It never accepts SMTP credentials as workflow inputs and never
prints them.

A successful configuration means Supabase handed future Auth mail to the
chosen provider. It does **not** prove inbox delivery. Verify one invite and one
recovery message in the provider delivery log and the recipient mailbox.

The deployed portal includes the unauthenticated but signature-protected
`auth-email-webhook` Edge Function. For Resend, configure this HTTPS target:

```text
https://<SUPABASE_PROJECT_REF>.supabase.co/functions/v1/auth-email-webhook
```

Subscribe it to sent/delivered/delayed/failed/suppressed/bounced/complained
events and store the
provider signing secret as `RESEND_WEBHOOK_SECRET` in the protected GitHub
`production` environment. The ordinary production deployment synchronizes that
secret into Supabase without printing it. When the secret is absent the endpoint
fails closed and the honest UI status remains `accepted_unconfirmed`.

SMTP handoff does not guarantee that the provider will expose an application
correlation ID. The event journal therefore distinguishes exact, ambiguous and
unmatched correlation. Ambiguous events are retained for diagnostics but never
silently upgrade a particular user's message to `delivered`.

Use [AUTH_ACCESS_OPERATIONS.md](AUTH_ACCESS_OPERATIONS.md) for the complete
cutover, webhook and canary procedure.

## Local/reference profile

The Python commands, SQLite databases, local media folders, Dockerfile, and
`127.0.0.1` routes are developer/reference tools. They are not the creator
login surface and are not a production deployment method.

The historical reference bootstrap remains available as
`python scripts/bootstrap_cloud_owner.py`; it is not the Supabase-native
production initializer and must not be used in the GitHub Pages release path.

For local Supabase contract work, use the CLI against the local stack and apply
the committed migrations:

```bash
supabase db start
supabase db reset
supabase db lint --local --level error
```

## References

- [Supabase database migrations](https://supabase.com/docs/guides/deployment/database-migrations)
- [Supabase environment deployment](https://supabase.com/docs/guides/deployment/managing-environments)
- [Supabase custom SMTP and delivery limits](https://supabase.com/docs/guides/auth/auth-smtp)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
