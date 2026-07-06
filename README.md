# ContentEngine

Qharisma Video Factory MVP.

Local MVP for an internal product content factory workflow:

Product -> Script -> Video -> Review -> Package -> Schedule -> Upload -> Analytics.

The MVP is compliance-first. It uses mock providers by default and does not implement platform abuse, anti-detection, proxy rotation, fingerprint rotation, captcha bypass, fake engagement, mass account creation, scraping-based publishing, or hidden rate-limit bypass.

## What Is Included

- FastAPI app with server-rendered Jinja admin pages.
- SQLite database through SQLAlchemy models.
- Product, brand guide, creative template, review, video, publishing, warm-up, upload, analytics, and export models.
- MockLLMClient for strict JSON script generation and validation.
- MockVideoProvider and FFmpeg-based assembly when FFmpeg is available.
- Clear placeholder artifacts when FFmpeg is not available.
- Publishing package generator with UTM links, hashtags, CTA, AI flag, and safety metadata.
- Owned-account registry and compliance-first warm-up scheduler.
- MockUploadProvider plus manual-upload-required flow for unconfigured providers.
- Fake analytics collection.
- Pytest coverage for the required MVP workflow.

## Run Locally

Use Python 3.12 for the pinned dependency set.

```bash
python -m pip install -r requirements.txt
python scripts/seed.py
python -m uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Fast Demo

Run the full mock/local MVP workflow from one command:

```bash
python scripts/seed.py
python scripts/run_demo_pipeline.py
python -m uvicorn app.main:app --reload
```

Then open http://localhost:8000/engine to trigger the same demo pipeline from the admin UI.

The fast demo is local-first and mock-provider based. It generates a script, auto-approves demo review steps, creates a mock video artifact, creates and approves a publishing package, schedules within warm-up limits, runs mock upload, and collects fake analytics. It does not call real LLM, video, or upload APIs.

## Real Generator Flow

The primary product page is `/generator`. It is the data-driven generation path for ContentEngine:

1. Import product and performance data.
2. Build `CreativeIntelligencePack` from product facts, marketplace metrics, creative performance, review insights, market signals, and brand rules.
3. Build `ScriptBrief` with source-backed allowed claims.
4. Generate a structured script with the selected LLM provider.
5. Build a scene-level `PromptPack`.
6. Generate a video with the selected video provider.
7. Poll/download/assemble outputs.
8. Review final video.

Local no-cost verification:

```bash
python scripts/seed.py
python scripts/import_sample_data.py
python scripts/generate_video.py --product-id 1 --build-prompts-only
```

Real providers are selected explicitly with environment variables. If a real provider is selected and its key is missing, the app fails clearly instead of silently falling back to mock. Paid video generation also requires both `QVF_GENERATION_MODE=real` and `QVF_ALLOW_REAL_SPEND=true`.

```env
QVF_LLM_PROVIDER=openai
OPENAI_API_KEY=
QVF_OPENAI_MODEL=gpt-5.5

QVF_GENERATION_MODE=mock
QVF_ALLOW_REAL_SPEND=false
QVF_MAX_VIDEO_SECONDS_PER_RUN=5
QVF_MAX_SCENES_PER_REAL_RUN=1
QVF_MAX_PROVIDER_POLL_SECONDS=600

QVF_VIDEO_PROVIDER=runway
RUNWAYML_API_SECRET=
QVF_RUNWAY_MODEL=gen4.5
QVF_VIDEO_RATIO=720:1280
QVF_VIDEO_SCENE_DURATION=5
```

OpenAI-only prompt build:

```powershell
$env:QVF_LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="..."
python scripts\generate_video.py --product-id 1 --llm-provider openai --build-prompts-only
```

First paid one-scene smoke run:

```powershell
$env:QVF_GENERATION_MODE="real"
$env:QVF_ALLOW_REAL_SPEND="true"
$env:QVF_LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="..."
$env:QVF_VIDEO_PROVIDER="runway"
$env:RUNWAYML_API_SECRET="..."
python scripts\generate_video.py --product-id 1 --llm-provider openai --video-provider runway --real-run --max-scenes 1
```

Full-video real generation requires `--full-video` and still obeys the configured max scene and duration caps.

## Hook-Driven Video Generator

The `/video-generator` page adds the Sprint 04 product layer:

```text
Product + metrics + reviews + market signals + brand rules
-> Creative Intelligence Pack
-> Hook Strategy
-> VideoCreativeSpec
-> Scene Plan
-> Provider Prompt Pack
-> Real/mock video generation
-> Metadata Quality Score
```

Local prompt-only verification:

```bash
python scripts/build_creative_spec.py --product-id 1 --platform "Instagram Reels" --duration 15
python scripts/generate_from_spec.py --creative-spec-id 1 --build-prompts-only
```

One-scene real smoke still requires the Sprint 03 spend gates:

```powershell
$env:QVF_GENERATION_MODE="real"
$env:QVF_ALLOW_REAL_SPEND="true"
$env:QVF_VIDEO_PROVIDER="runway"
$env:RUNWAYML_API_SECRET="..."
python scripts\generate_from_spec.py --creative-spec-id 1 --video-provider runway --real-run --max-scenes 1
```

Batch generation remains out of scope until the one-SKU real video path is proven.

## Asset Kit & Creative Variants

Sprint 05 adds a controllable pre-generation quality layer:

```text
Product
-> Product Asset Kit
-> Creative Intelligence Pack
-> VideoCreativeSpec
-> First Frame Options
-> Creative Variants
-> Variant Score
-> Selected Variant
-> PromptPack from variant
-> Video generation through existing provider gates
```

Local verification:

```bash
python scripts/build_asset_kit.py --product-id 1
python scripts/build_creative_variants.py --creative-spec-id 1 --count 5
python scripts/generate_from_variant.py --creative-variant-id 1 --build-prompts-only
```

The asset kit and variant scorer are metadata/rules-based. They do not inspect videos visually, do not generate images, do not call paid providers, and do not bypass Sprint 03 spend gates.

## Preparing Product References

Before a selected variant is eligible for real one-scene smoke:

1. Upload or attach a packshot/reference image.
2. Mark it as the primary reference.
3. Approve the asset.
4. Rebuild or refresh the asset kit if needed.
5. Run the readiness check.
6. Build a prompt pack from the selected variant.
7. Only then run one-scene real smoke with the Sprint 03 spend gates enabled.

CLI flow:

```bash
python scripts/attach_product_asset.py --product-id 1 --url https://example.com/packshot.png --asset-type packshot --primary
python scripts/check_product_references.py --product-id 1 --provider runway
python scripts/generate_from_variant.py --creative-variant-id 1 --build-prompts-only
```

Reference readiness blocks real generation when no approved primary reference exists. Missing label closeup or lifestyle assets are warnings, not blockers. Provider reference bundles use clean internal payloads and avoid signed/private URL leakage.

## Selected Variant Real Smoke

Sprint 07 adds the first real-smoke eligible path from a selected creative variant:

```text
Product -> approved primary reference -> selected CreativeVariant -> PromptPack with reference bundle -> Runway one-scene job -> download -> generation report -> metadata quality review
```

Safe local failure without spend gates:

```bash
python scripts/run_variant_real_smoke.py --creative-variant-id 1 --video-provider runway --real-run --max-scenes 1
```

Paid manual acceptance uses the same command after `QVF_GENERATION_MODE=real`, `QVF_ALLOW_REAL_SPEND=true`, `QVF_VIDEO_PROVIDER=runway`, and `RUNWAYML_API_SECRET` are configured. The report path is `media/generation_reports/variant_{creative_variant_id}_video_{video_job_id}.json`, and the resulting quality review remains `needs_human_review` until a person checks the file.

Full runbook: `docs/REAL_SMOKE_FROM_VARIANT.md`.

## Product Geometry / Scale Lock

v0.2.1 adds prompt-level protection against product size and proportion drift. `VideoCreativeSpec` and selected-variant prompt packs now include product geometry, scale, and visibility rules, plus negative prompts for changed product size, wrong proportions, stretched/squashed bottle, oversized/miniature product, changed silhouette, wrong cap size, and label area changes.

Human feedback can request a prompt-only scene fix:

```bash
python scripts/request_regeneration.py --video-job-id 11 --scene-number 1 --reason product_geometry_mismatch --feedback "Product size/proportions drifted; preserve exact bottle silhouette, height-width ratio, cap/dropper size and label area."
python scripts/regenerate_scene_from_feedback.py --regeneration-request-id 1 --build-prompts-only
```

This is not visual identity verification. It improves provider instructions and regeneration prompts, while generated videos still require manual approval before publishing.

## Run the Working Generator

Sprint 08 connects the demand generator to the selected-variant video generator:

```text
Product data + marketplace/content signals
-> Demand Hypothesis
-> CreativeSpec
-> Selected CreativeVariant
-> Product References
-> PromptPack
-> prompt-only or spend-gated one-scene smoke
```

The main guided page is `/working-video-generator`.

End-to-end prompt-only acceptance:

```bash
python scripts/import_sample_data.py
python scripts/prepare_working_video.py --product-id 1 --platform "Instagram Reels" --duration 15 --variant-count 5
```

Copy the actual `Selected Variant ID` printed by `prepare_working_video.py`, then run:

```bash
python scripts/run_working_video.py --selected-variant-id <printed_id> --build-prompts-only
```

Before paid real smoke, attach a real product reference image and check references:

```bash
python scripts/attach_product_asset.py --product-id 1 --file "C:\path\to\real_packshot.png" --asset-type packshot --primary
python scripts/check_product_references.py --product-id 1 --provider runway
```

When `QVF_GENERATION_MODE=real`, `QVF_ALLOW_REAL_SPEND=true`, `QVF_VIDEO_PROVIDER=runway`, and `RUNWAYML_API_SECRET` are configured, run one-scene real smoke with the actual selected variant id:

```bash
python scripts/run_working_video.py --selected-variant-id <printed_id> --video-provider runway --real-run --max-scenes 1
```

The real-smoke command reuses Sprint 07 gates and does not bypass spend controls.

Docs: `docs/DEMAND_GENERATOR.md` and `docs/WORKING_VIDEO_GENERATOR.md`.

## AI Content Factory Cabinet

v0.4 adds `/content-factory` as the AI-led production workspace:

```text
SKU / product
-> AI Demand Agent
-> AI Creative Brief Agent
-> AI Variant Agent
-> AI Video Agent
-> AI Review Agent
-> AI Publishing Prep Agent
-> Performance Analytics
-> Next Action Recommendations
```

It automates creator logic while keeping humans in the approval and exception loop. It does not add external account creation, Telegram bot workflow, batch generation, approval bypasses, or auto-publishing of unreviewed videos.

### AI Factory Control Loop

`/content-factory` now acts as the automated control loop for one SKU at a time. A prepared run returns the demand hypothesis, safe promise, CreativeSpec, selected variant, prompt pack, reference readiness, geometry/scale readiness, AI review status, publishing readiness, and next recommended action.

The AI review is rules-based and checks product identity constraints, Product Geometry / Scale Lock fields, negative prompt drift blockers, generated output metadata when a video exists, quality review status, and publishing package readiness. Missing geometry adds `geometry_lock_missing` and recommends `add_geometry_lock`. Human feedback about size/proportion drift adds `product_geometry_mismatch` and recommends `request_geometry_regeneration`.

The system does not claim visual identity or packaging geometry verification without human review or a future computer-vision layer.

CLI:

```bash
python scripts/prepare_content_run.py --product-id 1 --platform "Instagram Reels" --duration 15 --variant-count 5
python scripts/run_content_prompt_only.py --content-run-id 1
python scripts/review_content_run.py --content-run-id 1
python scripts/content_factory_dashboard.py
python scripts/import_content_stats.py --csv sample_data/content_performance.csv
```

Docs: `docs/AI_CONTENT_FACTORY_CABINET.md`, `docs/AI_CONTENT_RUNS.md`, and `docs/CONTENT_FACTORY_STATS.md`.

## Campaign Autopilot

v0.6.0 adds `/campaign-autopilot`, a campaign-scale layer above the AI Content Factory:

```text
Product Matrix
-> Campaign
-> target videos per SKU
-> Content Autopilot runs
-> prompt-ready / blocked / needs-review state
-> approved publishing package backlog
-> distribution plan
-> calendar tasks
-> performance feedback
```

Operator CLI:

```bash
python scripts/import_product_matrix.py --csv sample_data/product_matrix.csv
python scripts/create_campaign.py --name "Bombar Launch Wave 1" --import-id 1 --target-videos 350 --target-destinations 120
python scripts/prepare_campaign.py --campaign-id 1
python scripts/campaign_state.py --campaign-id 1
python scripts/run_campaign_prompt_only.py --campaign-id 1
python scripts/campaign_report.py --campaign-id 1
python scripts/generate_campaign_distribution_plan.py --campaign-id 1
```

Campaign Autopilot supports 40 SKU, 300-350 target videos, and 120 destinations without paid calls by default. It orchestrates the existing `ContentRunOrchestrator`; it does not replace the AI Content Factory, bypass approval gates, or publish unreviewed videos.

Docs: `docs/CAMPAIGN_AUTOPILOT.md`, `docs/PRODUCT_MATRIX_IMPORT.md`, and `docs/CAMPAIGN_DISTRIBUTION_PLAN.md`.

## Bombar Launch Adapter

`/bombar-launch` is a Bombar-specific adapter on top of Campaign Autopilot:

```text
Bombar matrix
-> ProductMatrixImport
-> Campaign
-> CampaignRunner content preparation
-> destination setup packs
-> CampaignDistributionPlanner
-> dashboard linked to Campaign state/report
```

Operator CLI:

```bash
python scripts/import_bombar_matrix.py --file data/bombar_matrix.xlsx
python scripts/create_bombar_campaign.py --import-id 1 --target-videos 350 --target-destinations 120
python scripts/prepare_bombar_content.py --campaign-id 1
python scripts/generate_destination_setup_packs.py --campaign-id 1
python scripts/generate_bombar_distribution_plan.py --campaign-id 1
python scripts/bombar_launch_dashboard.py --campaign-id 1
```

The adapter supports 40 SKU, 300-350 target videos, and 120 destination setup packs while keeping Campaign Autopilot as the single campaign core. It does not create external platform accounts, use proxy/anti-detect logic, bypass approvals, or publish unreviewed videos.

Docs: `docs/BOMBAR_LAUNCH_AUTOPILOT.md`, `docs/BOMBAR_MATRIX_FORMAT.md`, and `docs/DESTINATION_SETUP_PACKS.md`.

## Campaign Execution Control Center

v0.7.0 adds `/campaign-execution`, the execution dashboard above Campaign Autopilot:

```text
Campaign
-> execution snapshot
-> exact SKU blockers
-> deduplicated action queue
-> safe execution / human task resolution
-> publishing readiness
-> distribution readiness
-> JSON and CSV report summary
```

Operator CLI:

```bash
python scripts/campaign_execution_snapshot.py --campaign-id 1
python scripts/campaign_execution_refresh.py --campaign-id 1
python scripts/campaign_execution_actions.py --campaign-id 1
python scripts/campaign_execution_report.py --campaign-id 1
python scripts/campaign_execution_report.py --campaign-id 1 --format csv
```

The control center keeps Campaign Autopilot and Bombar as the source of campaign state. It does not create platform accounts, bypass paid gates, publish unapproved videos, or run paid provider calls in tests.

Docs: `docs/CAMPAIGN_EXECUTION_CONTROL_CENTER.md` and `docs/CAMPAIGN_ACTION_QUEUE.md`.

## Campaign Batch Executor

v0.8.0 adds `/campaign-batch`, a controlled batch executor for safe Campaign Execution actions:

```text
Campaign Execution action queue
-> safe action selection
-> dry run
-> execute safe batch
-> batch run/item result log
-> refreshed execution snapshot
-> JSON and CSV batch report
```

Operator CLI:

```bash
python scripts/campaign_batch_dry_run.py --campaign-id 1 --action-type run_prompt_only
python scripts/campaign_batch_execute.py --campaign-id 1 --action-type run_prompt_only
python scripts/campaign_batch_report.py --batch-run-id 1
python scripts/campaign_batch_report.py --batch-run-id 1 --format csv
```

Batch execution uses the v0.7 action queue. It does not run paid providers, approve publishing packages, schedule live publishing, publish/manual upload, mark published, create external accounts, or execute human-required actions in bulk.

Docs: `docs/CAMPAIGN_BATCH_EXECUTOR.md`.

## Campaign Performance Loop

v0.9.0 adds `/campaign-performance`, a manual metrics feedback loop for scaling decisions:

```text
published final URLs
-> CSV metrics import
-> campaign aggregation
-> SKU / variant / hook / destination scores
-> scale / pause / regenerate recommendations
-> safe action queue items
-> JSON and CSV report
```

Operator CLI:

```bash
python scripts/import_campaign_performance.py --campaign-id 1 --csv sample_data/campaign_performance.csv
python scripts/campaign_performance_summary.py --campaign-id 1
python scripts/campaign_performance_recommendations.py --campaign-id 1
python scripts/campaign_performance_report.py --campaign-id 1
```

The loop uses manual CSV import and `PublishingTask.final_url` links. It does not scrape platforms, require external API credentials, auto-publish, bypass approvals, run paid providers, or create external accounts.

Docs: `docs/CAMPAIGN_PERFORMANCE_LOOP.md`, `docs/CAMPAIGN_METRICS_IMPORT.md`, and `docs/SCALING_RECOMMENDATIONS.md`.

## v1 AI Content Factory Operating System

v1 adds `/factory-os`, one operator workflow that connects the existing modules end to end:

```text
product matrix
-> campaign
-> content autopilot
-> execution snapshot
-> safe prompt-only batch
-> distribution plan
-> performance import
-> scaling recommendations
-> acceptance report and runbook
```

Operator CLI:

```bash
python scripts/factory_health_check.py
python scripts/factory_prompt_only_launch.py --matrix sample_data/product_matrix.csv --campaign-name "Demo Launch" --target-videos 350 --target-destinations 120
python scripts/factory_acceptance_report.py --campaign-id 1
python scripts/factory_runbook.py --campaign-id 1
```

Factory OS does not scrape platforms, create external accounts, run paid providers, auto-publish, or bypass human review gates.

Docs: `docs/FACTORY_OS.md`, `docs/FACTORY_ACCEPTANCE_RUNBOOK.md`, and `docs/V1_PROMPT_ONLY_LAUNCH.md`.

## v1.1 Bombar Production Dry Run

v1.1 adds `/bombar-production-dry-run`, an operator checkpoint for running a real-style Bombar CSV/XLSX matrix through the no-paid Factory OS path:

```text
Bombar matrix
-> strict matrix validation
-> Factory OS prompt-only launch
-> production readiness report
-> blockers by SKU
-> next actions
-> JSON/CSV/XLSX exports
```

Operator CLI:

```bash
python scripts/bombar_production_dry_run.py --matrix path/to/bombar_matrix.xlsx --target-videos 350 --target-destinations 120
```

The dry run reports imported SKU, ready/blocked SKU, prompt packs, missing references, missing price, missing stock, approved packages, distribution blockers, next actions, and report paths. It does not call paid providers, register external accounts, auto-publish, or bypass approval gates.

Docs: `docs/BOMBAR_PRODUCTION_DRY_RUN.md`.

## v1.2 Launch Operations Hub

v1.2 adds `/launch-operations`, one control layer for campaign launch readiness:

```text
campaign
-> quality gates
-> approved video readiness
-> destination capacity
-> distribution readiness
-> launch blockers
-> action plan
-> operator runbook export
```

Operator CLI:

```bash
python scripts/launch_readiness.py --campaign-id 1
python scripts/launch_quality_gates.py --campaign-id 1
python scripts/launch_destination_capacity.py --campaign-id 1
python scripts/launch_action_plan.py --campaign-id 1
python scripts/export_launch_runbook.py --campaign-id 1
```

Launch Operations separates safe, human, paid, and publishing actions. It does not auto-publish unreviewed videos, create external social accounts, bypass approvals, or run paid providers in tests.

Docs: `docs/LAUNCH_OPERATIONS_HUB.md`, `docs/LAUNCH_READINESS.md`, `docs/DESTINATION_CAPACITY.md`, and `docs/QUALITY_GATES.md`.

## v1.3 Destination Setup Factory

v1.3 turns Launch Operations capacity gaps into operator-ready destination setup work:

```text
capacity gap
-> setup requirement
-> profile/account setup pack
-> first 9 post ideas
-> setup checklist
-> operator task
-> completed owned destination
```

Operator CLI:

```bash
python scripts/destination_setup_requirements.py --campaign-id 1
python scripts/generate_destination_profile_packs.py --campaign-id 1
python scripts/create_destination_setup_tasks.py --campaign-id 1
python scripts/complete_destination_setup_task.py --task-id 1 --url "https://example.com/account" --handle "@example"
```

Open `/destination-setup` to review capacity gaps, profile packs, first posts, checklists, setup tasks, and create internal publishing destinations after operator confirmation. ContentEngine does not auto-register external accounts, use proxy/anti-detect flows, bypass platform rules, or publish unapproved videos.

Docs: `docs/DESTINATION_SETUP_FACTORY.md`, `docs/DESTINATION_PROFILE_PACKS.md`, and `docs/ACCOUNT_SETUP_CHECKLIST.md`.

## v1.4 Destination Readiness CRM

v1.4 manages owned destinations after setup:

```text
internal destination
-> readiness snapshot
-> warmup/posting mode
-> campaign capacity
-> destination health
-> next actions
```

Operator CLI:

```bash
python scripts/destination_crm_readiness.py --destination-id 1
python scripts/destination_crm_refresh.py --destination-id 1
python scripts/destination_crm_campaign_capacity.py --campaign-id 1
python scripts/destination_crm_health.py --campaign-id 1
```

Open `/destination-crm` to inspect ready/manual/API/paused/blocked destinations, warmup phases, remaining capacity, health, and next operator actions. The CRM does not register external accounts, bypass platform rules, or publish unapproved videos.

Docs: `docs/DESTINATION_READINESS_CRM.md`, `docs/DESTINATION_WARMUP_PLANS.md`, and `docs/DESTINATION_CAPACITY_RULES.md`.

## v1.5 Connected Destinations & Metrics Collection

v1.5 connects owned destinations to metric collection without adding external account creation or unsafe upload automation:

```text
destination
-> connection
-> credential readiness
-> final URL / publishing task
-> metrics collection
-> campaign performance loop
```

Operator CLI:

```bash
python scripts/add_destination_connection.py --destination-id 1 --type manual
python scripts/add_destination_connection.py --destination-id 1 --type telegram_bot --credential-ref TELEGRAM_BOT_TOKEN
python scripts/check_destination_connection.py --connection-id 1
python scripts/sync_destination_metrics.py --connection-id 1 --period-start 2026-07-01 --period-end 2026-07-07
python scripts/import_destination_metrics.py --csv sample_data/destination_metrics.csv
python scripts/destination_metrics_summary.py --campaign-id 1
```

Open `/destination-connectors` to review connection status, credential configured yes/no, recent syncs, CSV import results, matched/unmatched URLs, and campaign metrics summaries.

Docs: `docs/DESTINATION_CONNECTORS.md`, `docs/METRICS_COLLECTION.md`, `docs/YOUTUBE_ANALYTICS_CONNECTOR.md`, `docs/TELEGRAM_CONNECTOR.md`, and `docs/MANUAL_METRICS_IMPORT.md`.

## v1.6 Destination Control Tower

v1.6 combines the destination/account operating modules into one control view:

```text
destination network
-> setup status
-> readiness status
-> connection status
-> publishing status
-> metrics status
-> performance status
-> next action
```

Operator CLI:

```bash
python scripts/destination_control_snapshot.py --campaign-id 1
python scripts/destination_control_refresh.py --campaign-id 1
python scripts/destination_control_report.py --campaign-id 1
```

Open `/destination-control-tower` for the campaign overview, destination table, blockers, and safe/manual/gated action queue.

Docs: `docs/DESTINATION_CONTROL_TOWER.md` and `docs/DESTINATION_CONTROL_STATUSES.md`.

## v1.7 Participant Portal

v1.7 adds a personal workspace for creators, publishers, partners, reviewers, and operators:

```text
participant
-> linked destinations
-> assigned brief cards
-> submissions
-> publishing status
-> metrics
-> payout ledger
-> recommendations
```

Operator CLI:

```bash
python scripts/add_participant.py --name "Creator One" --role creator --platforms reels,shorts
python scripts/link_participant_destination.py --participant-id 1 --destination-id 1 --relationship owner
python scripts/create_participant_assignment.py --participant-id 1 --content-run-id 1 --assignment-type create_video
python scripts/participant_dashboard.py --participant-id 1
python scripts/participant_payouts.py --participant-id 1
python scripts/participant_recommendations.py --participant-id 1
```

Open `/participant-portal` for onboarding, briefs, channels, submissions, stats, payout ledger, and recommendations. The portal does not execute real payments, store payout secrets, create external accounts, or bypass publishing/review gates.

Docs: `docs/PARTICIPANT_PORTAL.md`, `docs/CREATOR_BRIEF_CARDS.md`, `docs/PARTICIPANT_STATS.md`, and `docs/PAYOUT_LEDGER.md`.

## v1.8 Metrics Intake & Attribution

v1.8 adds the metrics intake layer that makes stats traceable from a published post back to campaign, SKU, destination, participant, payouts, and recommendations:

```text
PublishingTask / final_url
-> TrackingLink
-> click tracking
-> CSV/manual/API metrics
-> attribution
-> FunnelSnapshot
-> CampaignPerformanceMetric
-> Participant dashboard
```

Operator CLI:

```bash
python scripts/create_tracking_links.py --campaign-id 1
python scripts/import_metrics_csv.py --csv sample_data/metrics_intake.csv --campaign-id 1
python scripts/attribute_metrics_batch.py --batch-id 1
python scripts/funnel_snapshot.py --campaign-id 1
```

Open `/metrics-intake` for the platform matrix, sources, tracking links, CSV imports, attribution, funnel snapshots, and unmatched rows. Facebook, Instagram, YouTube, TikTok, Telegram, VK, marketplace, and partner-slot data can come from official connectors when authorized, or from CSV/manual/partner reports. ContentEngine does not scrape platforms, use unofficial login, store raw tokens, bypass OAuth, or call real external APIs in tests.

Docs: `docs/METRICS_INTAKE_ATTRIBUTION.md`.

## Human Operating Rules

Human-facing rules keep publishing, stats, payouts, and recommendations traceable:

```text
assignment
-> approved video
-> tracking link in post
-> final URL saved
-> metrics uploaded by posted_url/tracking_slug
-> payout ledger
```

Participant Portal shows a "How to work" block, assignment brief cards include a publish checklist, Metrics Intake shows CSV column guidance, and Publishing Task pages warn when `final_url` or a tracking link is missing. `per_published_post` payouts require a traceable publishing task with `final_url`.

Docs: `docs/HUMAN_OPERATING_RULES.md`, `docs/PUBLISHING_RULES_FOR_PARTICIPANTS.md`, `docs/METRICS_SUBMISSION_RULES.md`, and `docs/PAYOUT_RULES_FOR_PARTICIPANTS.md`.

## v1.9 Training Academy

v1.9 adds `/training-academy`, an in-product onboarding layer for creators, publishers, operators, reviewers, partners, and admins:

```text
role course
-> lessons / checklists / examples
-> quiz attempt
-> certification
-> advisory or strict gate
```

Default courses cover Creator Basics, Publisher Basics, Metrics Basics, Payout Basics, and Reviewer Basics. The academy links back into Participant Portal, Metrics Intake, Publishing, and Destination Control Tower.

Operator CLI:

```bash
python scripts/seed_training_academy.py
python scripts/training_progress.py --participant-id 1
python scripts/submit_training_quiz.py --participant-id 1 --course-code metrics_basics --answers sample_data/training_answers.json
```

Training gates are advisory by default: publishing recommends `publisher_basics`, metrics submission recommends `metrics_basics`, and reviewer approval recommends `reviewer_basics`. Strict mode is available in the service layer for workflows that need to block uncertified actions.

Docs: `docs/TRAINING_ACADEMY.md`, `docs/PUBLISHER_TRAINING.md`, `docs/METRICS_TRAINING.md`, and `docs/PAYOUT_TRAINING.md`.

## Publishing Workflow

v0.3 adds a safe manual publishing layer after video generation:

```text
approved video artifact
-> publishing package
-> owned destination registry
-> calendar task
-> manual upload
-> final post URL
-> published_manual
```

ContentEngine does not create platform accounts, auto-publish unreviewed generated videos, bypass authorization, add fake engagement, or use proxy/anti-detect upload logic.

Operator CLI:

```bash
python scripts/add_publishing_destination.py --platform telegram --name "Altea Telegram" --posting-mode manual
python scripts/import_publishing_destinations.py --file destinations.csv
python scripts/create_publishing_package.py --video-job-id 11 --platform telegram
python scripts/approve_publishing_package.py --package-id 1
python scripts/schedule_publishing_task.py --package-id 1 --destination-id 1 --scheduled-at "2026-07-05T12:00:00"
python scripts/bulk_schedule_publishing_tasks.py --package-ids "1,2,3" --destination-ids "1,2" --start-at "2026-07-05T12:00:00" --dry-run
python scripts/mark_manual_published.py --task-id 1 --url "https://example.com/post"
```

Open `/publishing` for destination CSV import, packages, calendar tasks, bulk scheduling, and manual upload final URL capture.

Docs: `docs/PUBLISHING_WORKFLOW.md`, `docs/MANUAL_UPLOAD_FLOW.md`, and `docs/PUBLISHING_DESTINATIONS.md`.

## Docker Compose

```bash
docker compose up --build
```

The Docker image installs FFmpeg. Without FFmpeg, the app still writes clear placeholder artifacts and sidecar caption files.

## Tests

```bash
python -m pytest
```

## Demo Flow

1. Seed demo data with `python scripts/seed.py`.
2. Open `/products` and choose or create a product.
3. Create a script from `/scripts/new`.
4. Review the generated JSON on `/scripts/{id}` and approve the script variant.
5. Create a video job from `/videos/new`.
6. Run mock generation on `/videos/{id}` and approve the video.
7. Create a publishing package from `/publishing-packages/new`.
8. Approve the package on `/publishing-packages/{id}`.
9. Schedule it to an owned account. The scheduler enforces daily and weekly warm-up limits.
10. Open the publishing job and run upload.
11. For mock provider jobs, the status becomes `published` with a fake post URL.
12. For manual provider jobs, open `/manual-upload/{job_id}`, paste the post URL, and mark it uploaded.
13. Collect fake analytics from the publishing job page and review `/analytics`.

## Useful API Examples

```bash
curl http://localhost:8000/api/products
curl -X POST http://localhost:8000/api/script-jobs/generate \
  -H "Content-Type: application/json" \
  -d '{"product_id":1,"template_id":1,"brand_guide_id":1}'
```

## Limitations

- OpenAI and Runway adapters can call external APIs only when explicitly selected and configured; normal tests do not require real provider keys.
- Gemini/Veo and upload providers remain scaffolded or manual.
- Authentication is not implemented in this MVP.
- FFmpeg text burn-in is intentionally conservative; captions are stored as sidecar files.
- Background jobs are synchronous in-process calls for local demo simplicity.
- SQLite is used locally; models are structured to move to PostgreSQL later.

## Checkpoints

- Checkpoint 1: scaffold, FastAPI app, database setup, templates, README.
- Checkpoint 2: models, schemas, seed data, CRUD routes.
- Checkpoint 3: mock script generation and review.
- Checkpoint 4: mock video generation and assembly.
- Checkpoint 5: publishing packages, accounts, warm-up calendar.
- Checkpoint 6: mock/manual upload and analytics.
- Checkpoint 7: tests and docs.
