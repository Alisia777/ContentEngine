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

Real providers are selected explicitly with environment variables. If a real provider is selected and its key is missing, the app fails clearly instead of silently falling back to mock.

```env
QVF_LLM_PROVIDER=openai
OPENAI_API_KEY=
QVF_OPENAI_MODEL=gpt-5.5

QVF_VIDEO_PROVIDER=runway
RUNWAYML_API_SECRET=
QVF_RUNWAY_MODEL=gen4.5
QVF_VIDEO_RATIO=720:1280
QVF_VIDEO_SCENE_DURATION=5
```

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

- Real LLM, video, and upload providers are stubs. They do not call external APIs.
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
