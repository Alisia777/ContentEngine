# Local workbench and staging contour status

Updated: 2026-08-16. Branch: `codex/local-workbench-v1`.

ContentEngine is the first-priority project. The worktree now carries persistent local and staging-preview contours so the product, migrations, Edge Functions, media pipeline, and browser routes can be exercised without exchanging full archives. The remote branch existed at the original base revision; all changes described here remain uncommitted and unpushed in the E-drive worktree, and this work created no pull request.

## Project 1 — Copy / Product Swap

Status: adaptive compact form, deterministic mock E2E, and the single-item real-provider path are implemented.

The Copy form asks only for the inputs required by this strategy: one source MP4, 3–5 replacement-product references, audio on/off, the server-owned Product Swap recipe, source rights, and one editable recommendation. The recommendation uses the existing AI Center draft bridge; it does not introduce a second prompt store.

The deterministic local pipeline is `MP4 -> storyboard -> original-product frame -> new-product references -> viral_product_swap -> preflight -> mock generation -> archive`. FFmpeg/FFprobe perform the local media work. A second system pass uploads the assets through local Storage, prepares and replays the real project-scoped browser strategy wrapper, approves and binds the spec, calls strict `strategy_mock_preflight/start/status` actions inside the sole `creator-generate` Edge Function, writes canonical zero-cost mock media/batch/job records, reads the existing archive RPC, downloads the result, and verifies its SHA-256. It creates no paid claim, dispatch attempt/result, readiness receipt, or spend-ledger row. Artifacts remain under ignored `.dev-artifacts/copy-e2e/` and `.dev-artifacts/copy-system-e2e/`.

One Product Swap can proceed from the adaptive form through exact spec review, human approval, asset binding, preflight, exact price confirmation, start-once protection, status reconciliation, and archive using `supabase/functions/creator-generate` as the only paid authority. The code path is ready for a separately authorized controlled paid smoke; no paid smoke or real provider call is claimed as completed here.

## Project 2 — Avatar / Character Performance

Status: adaptive compact form is implemented; generation remains feature-gated.

The Avatar form asks for one source MP4 plus either an avatar photo or an avatar description, likeness consent, source rights, and the same editable AI Center-backed recommendation. Product Swap-only fields and the full Strategy questionnaire are not shown on this route.

Character Performance remains visible for browser and UX verification but fail-closed with `QVF_CHARACTER_PERFORMANCE_ENABLED=false`. It must not be enabled until the exact provider adapter, request schema, pricing, reconciliation behavior, and archive contract are independently confirmed.

## Project 3 — Strategy / Viral Rebuild

Status: the full six-step form and local mock preflight are implemented.

The Strategy route retains the complete guided workflow for a new video rebuilt from a reference: method, product, audience, concept, sources, and review/launch. It reuses the existing AI Center recommendation field and keeps Copy- and Avatar-specific compact controls inactive. Local execution remains mock-only; any future paid start must still use `creator-generate` and the existing spend ledger.

## Shared local and staging contours

- Docker Compose profile: `docker-compose.local.yml`, with mock providers and FFmpeg/FFprobe. Application media and SQLite now use project-relative E-drive bind mounts at `.local/docker/media/` and `.local/docker/data/qharisma.db`; the overlay no longer attaches the old `local-media` or `local-data` named volumes. Those old volumes are deliberately left untouched, and Supabase CLI volumes are not overridden.
- Generated local browser overlay: `.local/site/config.js`; production `web/app/config.js` is untouched.
- Supabase overlay: `.local/supabase/`, generated from `supabase/config.local.toml` plus committed migrations, Storage policies, pgTAP tests, and Edge Functions.
- The local Edge environment is generated at `.local/supabase/functions/.env`, the location loaded by the Supabase Edge runtime. It pins mock-only mode, real spend false, and Character Performance false.
- `creator-generate` runs mock-only in the local profile. The safe default is always `QVF_ALLOW_REAL_SPEND=false`; enabling a controlled paid smoke requires separate, explicit human authorization and a deliberately configured non-local environment.
- Local addresses: application API `8014`, browser workbench `8767`, Supabase API `54321`, Studio `54323`, and Mailpit/Inbucket `54324`.
- Operator commands: `dev-up`, `dev-down`, `dev-reset`, `dev-test`, `dev-browser-smoke`, and `dev-status` through `python scripts/dev_workbench.py <command>` (or the matching Make target where Make is installed).
- Browser-smoke Chrome profiles are created under `.dev-artifacts/browser-smoke/profiles/` inside this project and removed after the run; screenshots and Copy E2E artifacts remain under the ignored `.dev-artifacts/` tree.
- Browser smoke uses the real Desktop and project. It verifies compact Copy, compact feature-gated Avatar, full six-step Strategy with a ready three-item server catalog, plus Finder's Organization, List, and Add Material controls.
- Authenticated browser read RPCs that refresh the local profile are explicitly `VOLATILE` as of migration `202608160004`, so PostgREST keeps their transactions writable; the former `SQLSTATE 25006` / `cannot execute INSERT in a read-only transaction` failure is covered by pgTAP, Python contracts, authenticated HTTP smoke, and the real browser smoke.
- A separate static staging preview is generated under `.local/staging/site/` and served at loopback port `8768`. Its strict three-field env accepts only a separate HTTPS Supabase project ref/origin and browser-safe publishable key, rejects the production ref and credential-shaped values, and never performs remote link/push/deploy operations. Paid generation stays hard-disabled in this preview.
- Required pre-push gate: full pytest, Node parsing, Supabase migration reset/lint, pgTAP, browser smoke for Copy/Avatar/Strategy/Finder, deterministic and system Copy mock E2E, staging contract tests, and `git diff --check` through `dev-test` plus `staging-test`.
- Final local release evidence is green: `dev-test` completed with exit code 0; all 4,180 pytest cases passed across six isolated E-drive shards, Node parsed 112 JavaScript files, the local database reset applied migrations through `202608160004`, lint returned no errors, pgTAP passed 3,085 assertions in 86 files, both Copy mock pipelines passed, all eight browser routes passed, and `git diff --check` passed. The separate staging contract gate also passed 15 tests plus Compose and Node validation.
- Remaining before controlled paid smoke: provision and validate a separate remote staging Supabase project outside this scaffold, deploy the reviewed migrations/Functions through the controlled release process, configure the exact provider secret and spend-enabled server environment, verify the quoted price and budget reservation, then obtain explicit permission for exactly one Product Swap provider start. Character Performance remains excluded.
