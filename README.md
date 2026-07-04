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

## Working Demand + Video Generator

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

```bash
python scripts/prepare_working_video.py --product-id 1 --platform "Instagram Reels" --duration 15 --variant-count 5
python scripts/run_working_video.py --selected-variant-id 1 --build-prompts-only
```

The real-smoke command reuses Sprint 07 gates and does not bypass spend controls:

```bash
python scripts/run_working_video.py --selected-variant-id 1 --video-provider runway --real-run --max-scenes 1
```

Docs: `docs/DEMAND_GENERATOR.md` and `docs/WORKING_VIDEO_GENERATOR.md`.

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
