# Portal product gap roadmap

Updated: 2026-07-17

This roadmap separates shipped software from production readiness. A feature is
not considered ready merely because a form, RPC, or provider call exists.

## P0 — safe daily operation

### 1. Authentication email cutover

Current state:

- the portal has a unified manager access-repair flow and a durable delivery
  journal;
- SMTP readback, versioned templates, webhook-secret validation, and a
  scanner-safe accept page are covered by repository tooling;
- production SMTP credentials, the delivery webhook secret, sender DNS, and a
  completed canary are still absent;
- deploy and health workflows currently skip missing mail settings instead of
  failing the production-readiness gate, and Supabase Auth dispatch does not
  persist an exact provider message ID for webhook correlation.

Done when:

- SPF, DKIM, and DMARC pass for the selected auth sender;
- one invite and one recovery message are observed as delivered by the provider;
- both links are opened successfully from a real mailbox;
- every dispatch stores the provider message ID before delivery events arrive;
- the manager sees the terminal delivery state and a useful failure reason;
- the public forgot-password path also receives a durable, privacy-safe receipt.

### 2. Campaign-level paid-generation controls

Current state:

- the organization and global Runway limits are deployed;
- the repository release now includes first-class organization-scoped
  campaigns, immutable paid-job attribution, manager budget controls, and
  atomic organization/campaign guards;
- the new migration still has to pass the real PostgreSQL pgTAP gate and the
  production deployment before this item can be called operationally closed.

Done when:

- every paid job is bound immutably to one active campaign;
- global, organization, and campaign limits are checked atomically before a
  provider request and again immediately before submission;
- owner/admin can create a campaign, pause it, set limits, and see reserved,
  committed, and remaining amounts;
- missing or stale campaign policy fails closed while mock mode stays available.

### 3. Durable video-review execution

Current state:

- the browser creates a durable content-review run before extracting and
  submitting MP4 evidence;
- if the tab closes between those operations, the run can remain queued;
- the native background worker handles image evidence but intentionally skips
  queued video evidence, while the active-run constraint prevents a clean retry.

Done when:

- MP4 frame extraction and evidence submission are server-owned or atomically
  recoverable;
- a repair worker detects stale queued runs and resumes or dead-letters them;
- retry never creates a second paid provider call for the same review;
- manager health shows video-review queue age, retries, and terminal failures.

### 4. Honest Runway and OpenAI cost accounting

Current state:

- Runway spending is guarded by a provisional SKU estimate;
- the estimate is not a reconciled provider invoice;
- OpenAI product research and content review do not yet reserve a budget or
  persist provider usage and request references.

Done when:

- provider operations use a single append-only cost ledger;
- estimates, reservations, usage reports, corrections, and imported invoices
  are distinct event types;
- Runway and both OpenAI pipelines reserve before the external call;
- ambiguous timeouts freeze the operation instead of charging twice;
- owner/admin sees unreconciled usage, quota failures, and invoice variance.

### 5. Independent incident detection and recovery proof

Current state:

- native background work and an hourly smoke workflow exist;
- there is no independent external error/incident sink;
- backup/restore readiness and Storage restore have not been demonstrated.

Done when:

- a read-only health probe verifies the last successful native Cron dispatch,
  queue age, stalled jobs, and dead letters without creating a fresh heartbeat;
- health covers generation, research, review, mail, Storage cleanup, and cost
  reconciliation queues instead of only Runway jobs;
- critical events reach an external, deduplicated alert channel;
- sanitized SPA and Edge exceptions carry release/environment correlation IDs;
- RPO/RTO are written down and a disposable-project restore drill passes at
  least every 30 days, including Postgres, Auth, Storage, and tenant/RLS probes.

### 6. Production Storage lifecycle

Current state:

- private uploads and registration exist, but Storage policy currently checks
  tenant/path access rather than reserving organization quota before upload;
- a crash between upload and registration, or a direct Storage API call, may
  leave an unregistered orphan object;
- Supabase production has no full archive/restore/purge lifecycle.

Done when:

- quota-reserving upload intents are mandatory in Storage policy and make
  upload/register recovery idempotent;
- expired orphan objects are swept safely;
- archive, restore, retention, legal hold, and two-phase purge are auditable;
- referenced media cannot be purged;
- storage usage and remaining organization quota are visible in the portal.

### 7. Official production connectors

The deployed Supabase portal still needs OAuth/token-refresh/webhook or polling
workers for Instagram, YouTube, and VK. Documentation or legacy Python connector
code is not proof that production data is arriving. This remains P0 while the
portal promises automatic metrics or payout calculations; until then the UI must
label the source honestly as manual data.

Done when each connector has:

- an organization-scoped OAuth connection and encrypted server-only credentials;
- refresh-token rotation and revocation handling;
- idempotent metric ingestion with source timestamps and raw-evidence references;
- health, stale-data, quota, and reauthorization states in the manager UI;
- a canary account and an end-to-end production sync test.

## P1 — real automation and scale

### 8. 100k-object performance gate

Current keyset pagination is a good base, but it is not a load proof. Search,
folder counts, and the browser's unbounded accumulated card list need measurement.

Done when:

- a deterministic mixed 100k-object fixture runs in scheduled CI;
- root, folder, search, owner, and participant queries publish p50/p95/p99 and
  reviewed `EXPLAIN (ANALYZE, BUFFERS)` plans;
- search uses an appropriate trigram/FTS index;
- folder counts do not rescan all visible objects on every page request;
- the browser virtualizes/window-renders cards and keeps a bounded page cache;
- Materials, Tasks, Feedback, Team, Placement, Stats, and Payout screens are
  fully paged or retired; employee selectors are not limited to the first page.

### 9. Frontend modularity and browser quality gates

`web/app/app.js` is approximately 499 KB and 10,138 lines. It is now an
operational risk, not merely a style concern. Login also executes Supabase JS
directly from a public CDN, creating a supply-chain and availability dependency.

Done when:

- auth/app shell/router are separated from lazy route controllers;
- login does not download training, generation, review, and workspace modules;
- poll/notification updates do not replace the full section markup;
- the entry module is below 250 KB raw;
- browser dependencies are locally bundled from a lockfile, scanned, and listed
  in an SBOM rather than executed from a mutable external CDN URL;
- CI includes Playwright keyboard/mobile smoke, accessibility checks, Lighthouse
  budgets, and asset-size regression checks.

## P2 — quality and learning advantage

### 10. Training content completion

The interactive walkthrough engine is present, but only two walkthroughs have
real video assets; the remaining walkthroughs are storyboard placeholders.

Done when every core beginner route has a short real example, a bad/good
comparison, an interactive decision, and a block-level test: first login,
Instagram, YouTube, VK, filming, portal work, substitute SKU, publication,
calculation, and payout.

### 11. Deeper content QA and recommendation feedback loop

Add measurable checks for audio intelligibility, speech/script agreement,
product/label persistence, safe-zone violations, duplication, brand claims,
mandatory advertising/synthetic-content disclosures, and evidence-backed legal
review. Recommendations must learn from approved outcomes and imported platform
metrics, while retaining the human decision and its reason.

## Recommended execution order

1. Ship campaign budgets through pgTAP and production deployment.
2. Make queued video review recoverable and dead-letter stale runs.
3. Select and configure the production mail provider, DNS, exact message-ID
   correlation, webhook, mandatory readiness gate, and canaries.
4. Require quota-reserving Storage upload intents and sweep existing orphans.
5. Build the unified provider-cost ledger and OpenAI budget guards.
6. Add independent health alerts and run the first restore drill.
7. Add official connector canaries, or explicitly label metrics as manual.
8. Run the 100k performance programme and split/bundle the SPA by route.
9. Complete real training videos, deeper QA, and the recommendation feedback loop.
