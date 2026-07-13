# Cloud deployment for creator teams

The production product is a shared HTTPS workspace. `127.0.0.1`, SQLite,
local media storage, and auth bypasses exist only for isolated development and
automated tests.

## Production topology

```text
GitHub main
  -> required CI checks
  -> Render Blueprint
       - FastAPI web service
       - supervised Product UGC worker
  -> Supabase project
       - Auth (one identity per creator)
       - PostgreSQL (organizations, memberships, work, metrics, payouts)
       - private Storage bucket (source images, videos, QA evidence)
```

Creators receive one public HTTPS URL. They never connect to an operator's
computer and never share a local password or filesystem directory.

The web and worker containers are stateless. PostgreSQL is the source of truth
for application/queue state and the private Supabase Storage bucket is the
source of truth for media. A container may use its ephemeral filesystem only
while processing one artifact; a restart must not lose an accepted artifact.
Do not attach a Render disk and do not set `QVF_STORAGE_BACKEND=local`.

The application never reads or writes application rows through the Supabase
Data API (PostgREST). Disable the **Data API** for the project before launch.
This is defense in depth, not the primary boundary: the database migration also
enables non-forced RLS on every public application table and revokes all table
and sequence privileges from `anon`, `authenticated`, and `service_role` when
those roles exist. It leaves schema usage and extension functions intact for
Supabase-managed Auth and Storage, while the direct table-owner SQLAlchemy
connection continues to work.

## Production environment contract

`render.yaml` shares non-secret defaults through
`contentengine-production-defaults`. It deliberately sets both
`QVF_RUNTIME_PROFILE=production` and `QVF_DEPLOYMENT_ENV=production`: the first
enables application readiness checks and the second makes the storage adapter
reject a local backend.

Render derives `QVF_PUBLIC_APP_URL` from the web service's own
`RENDER_EXTERNAL_URL`; there is no placeholder URL to copy during the first
deploy. Enter the remaining values for `contentengine-web` during the initial
Blueprint setup. The worker obtains the same values through Render
`fromService` references, so they are entered once and never committed:

| Variable | Required value |
| --- | --- |
| `QVF_DATABASE_URL` | Supabase PostgreSQL session-pooler URL, with the SQLAlchemy scheme changed to `postgresql+psycopg://` and `sslmode=require` (or stricter `verify-ca`/`verify-full`) |
| `SUPABASE_URL` | Project URL, for example `https://<project-ref>.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | Publishable/anon client key |
| `SUPABASE_SECRET_KEY` | Server-only Supabase secret key (`sb_secret_...` preferred) |
| `QVF_SUPABASE_JWKS_URL` | Exactly `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`; another origin is rejected |
| `QVF_SUPABASE_ISSUER` | Exactly `https://<project-ref>.supabase.co/auth/v1`; another origin is rejected |
| `OPENAI_API_KEY` | Server-only OpenAI key; may remain unused while the provider is `mock` |
| `RUNWAYML_API_SECRET` | Server-only Runway key; may remain unused while the provider is `mock` |
| `QVF_GENERATION_MODE` | `mock` for spend-free acceptance; `real` only after owner approval |
| `QVF_LLM_PROVIDER` | `mock` for acceptance or the explicitly approved production provider |
| `QVF_VIDEO_PROVIDER` | `mock` for acceptance or `runway` after a one-video paid smoke succeeds |
| `QVF_ALLOW_REAL_SPEND` | `false` by default; `true` only as a separate owner budget decision |
| `QVF_MASS_GENERATION_CREDIT_LIMIT` | Non-secret hard cap per mass batch; default `30000`, enough for 50 standard 15-second 720×1280 estimates (`50 × 588 = 29400`) |

Enter one canonical server secret in `SUPABASE_SECRET_KEY`. Auth Admin,
Storage, bootstrap, and readiness all resolve that same value. The legacy
`SUPABASE_SERVICE_ROLE_KEY` remains an unadvertised fallback for an existing
deployment only; do not configure both. Production fails closed if any legacy
alias or storage override contains a different value. Never expose the secret
in HTML, logs, screenshots, or a client-side bundle.

Do not define `QVF_LOCAL_AUTH_EMAIL`, `QVF_LOCAL_AUTH_PASSWORD_HASH`, or
`QVF_LOCAL_SESSION_SECRET` on either production service, including as empty
values. Production startup rejects those local-only settings. The shared
`QVF_SUPABASE_READINESS_TIMEOUT_SECONDS=5` bounds the read-only Auth and
Storage probes performed by `/ready`.

The Blueprint requires an explicit capability selection instead of committing
one production mode. For the first spend-free acceptance deploy, enter
`mock`, `mock`, `mock`, and `false`. Enabling a paid run remains a separate
owner decision: configure the provider, set `QVF_GENERATION_MODE=real`, then
set `QVF_ALLOW_REAL_SPEND=true` only with the committed duration/scene limits
and an explicit real-run confirmation in the product.

## First deployment

1. Reuse the paid dedicated Supabase project (or create one if none exists) in
   the same region as the Render services. Do not create a second paid project
   merely for deployment.
2. Disable the project **Data API** in Supabase API settings. Do not expose the
   `public` schema through PostgREST for this application.
3. Enable an asymmetric Auth signing key and verify that the JWKS endpoint
   returns a non-empty `keys` array before inviting users.
4. Create a private Storage bucket named `contentengine-private`.
5. Connect the GitHub repository to a Render Blueprint using `render.yaml`.
6. Enter every `sync: false` value in the Render dashboard. Never commit those
   values to GitHub.
7. Use the Supabase session-pooler connection string for `QVF_DATABASE_URL`.
   URL-encode special characters in the password, use
   `postgresql+psycopg://`, and append `?sslmode=require`. Missing TLS mode and
   `disable`, `allow`, or `prefer` are rejected before the process serves.
8. Confirm both serialized pre-deploy migrations succeed and `/ready` returns
   HTTP 200. Readiness verifies the exact Alembic head, fetches a usable
   ES256/RS256 JWKS, checks the publishable key with the read-only Auth settings
   endpoint, and reads only the configured bucket metadata with the canonical
   server key. It also checks RLS and effective API-role table privileges on
   every critical application table. It fails if the schema is behind, a key
   is rejected, the bucket is missing, `public` is not exactly `false`, RLS is
   missing, or an API role can access a critical table. It never writes a
   probe object.
9. Confirm the generation worker heartbeat is current in the control room.
10. Before sending any invite, set the Supabase Auth **Invite user** email
   template link to
   `<PUBLIC_APP_URL>/auth/accept#token_hash={{ .TokenHash }}&type=invite`.
   The fragment is never sent to Render request logs: the browser bridge clears
   it immediately and submits the one-time hash in a same-site POST. The
   default fragment redirect is insufficient for this server-rendered
   confirmation flow.
11. Bootstrap the first cloud owner once, using the command below. Then use the
    authenticated **Команда** page for subsequent creator invitations.
12. Sign in as a creator in a private browser session and verify that another
   organization is neither listed nor addressable by a guessed URL.

### One-time first-owner bootstrap

Run this only from a Render shell for `contentengine-web`, after its Alembic
pre-deploy step has reached `head`:

```bash
python scripts/bootstrap_cloud_owner.py \
  --email "owner@example.com" \
  --display-name "First Owner" \
  --organization-name "Content Factory" \
  --organization-slug "content-factory"
```

The script refuses SQLite and a database that is not at the current Alembic
head. It reads `SUPABASE_URL` and `SUPABASE_SECRET_KEY` only from the server
environment, finds the exact Supabase identity or sends one invite, and then
creates the active organization, profile, and owner membership in one database
transaction. It never runs `init_db`, `create_all`, or an Alembic upgrade.

Re-running the exact command is safe even after other creators have joined the
bootstrapped organization: it does not duplicate the organization, profile,
membership, or invite. While the target owner bootstrap is incomplete, any
unrelated organization/profile/membership fails closed; inactive state, role
mismatch, a foreign membership for the target profile, or Supabase ID/email
mismatch always fails closed. The command prints only status values and numeric
database IDs; it never prints the email, token, server key, provider response,
or database credentials.

Without an organization claim, the resolver considers database-authoritative
active memberships in active organizations. Exactly one active membership is
selected; with multiple active memberships, it selects the active organization
derived from `QVF_PUBLIC_PILOT_DEFAULT_ORG`. If no eligible scope is unique,
sign-in fails closed with HTTP 403. An explicit trusted
`app_metadata.organization_slug` claim never falls back to another membership,
and the profile, claimed organization, and membership must all be active. The
resolver never creates a membership from token claims.

## Release flow

Every pull request parses deployment YAML, runs the Python suite, checks a real
PostgreSQL migration, and performs a clean Docker build. After CI succeeds on
`main`, the container workflow publishes a SHA-tagged image and provenance to
GitHub Container Registry. Render only deploys commits whose checks pass. Web
and worker run the same pre-deploy step; a PostgreSQL advisory lock serializes
them. The worker also refuses to start unless the database is at the exact
repository head. Schema changes are never made from an active worker loop.

Release verification is complete only when `/ready` is green, the worker
heartbeat is current, a signed media URL opens for an authorized member, and
the same object is denied to a user from another organization. Roll back the
application image on failure; never restore state from a container filesystem.

## Scaling rules

- Add web instances for HTTP traffic; all state remains in PostgreSQL/object
  storage.
- Add generation worker instances only after validating provider concurrency
  and spend limits. Queue leases and idempotency protect paid submissions.
- Keep `QVF_ALLOW_REAL_SPEND=false` until an owner deliberately enables a
  bounded production run.
- Videos are private objects. The application checks organization membership
  before issuing a short-lived signed URL; signed URLs are never persisted.
- A creator sees their own tasks and artifacts. Owners/admins see the team
  queue and aggregate metrics.
- Keep the Render Blueprint free of `disk` declarations. Local paths are
  disposable staging space, not backups or durable media storage.

## Local profile

`docker-compose.yml` remains a developer convenience only. It is not a hosting
method, a creator login surface, or the source of production data.

## References

- [Render Blueprint YAML reference](https://render.com/docs/blueprint-spec)
- [Supabase PostgreSQL connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase JWT verification and JWKS](https://supabase.com/docs/guides/auth/jwts)
- [Supabase API key security](https://supabase.com/docs/guides/getting-started/api-keys)
