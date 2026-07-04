# Working Video Generator

Sprint 08 connects demand generation to the existing video generator.

Main path:

```text
Product data + marketplace/content signals
-> Demand Generator
-> Demand Hypothesis
-> CreativeSpec
-> First Frame Options
-> Creative Variants
-> Selected CreativeVariant
-> Product References
-> PromptPack
-> prompt-only run or spend-gated one-scene real smoke
```

`prepare()` never calls paid providers.

## CLI

Prepare the working path:

```bash
python scripts/prepare_working_video.py --product-id 1 --platform "Instagram Reels" --duration 15 --variant-count 5
```

Prompt-only run from the selected variant:

```bash
python scripts/run_working_video.py --selected-variant-id 1 --build-prompts-only
```

Spend-gated one-scene smoke:

```bash
python scripts/run_working_video.py --selected-variant-id 1 --video-provider runway --real-run --max-scenes 1
```

Real smoke reuses Sprint 07 gates:

- `QVF_GENERATION_MODE=real`
- `QVF_ALLOW_REAL_SPEND=true`
- explicit `--real-run`
- Runway selected
- `RUNWAYML_API_SECRET` configured
- selected CreativeVariant exists
- approved primary product reference exists
- provider reference bundle is included

## API

```text
POST /api/working-video/prepare
POST /api/working-video/prompt-only
POST /api/working-video/real-smoke
GET  /api/working-video/status/{selected_variant_id}
```

Prepare payload:

```json
{
  "product_id": 1,
  "platform": "Instagram Reels",
  "duration_seconds": 15,
  "variant_count": 5
}
```

Real smoke payload:

```json
{
  "selected_variant_id": 1,
  "video_provider": "runway",
  "real_run": true,
  "allow_real_spend": true,
  "max_scenes": 1
}
```

## UI

The guided page is:

```text
/working-video-generator
```

It shows:

- product selector;
- buyer need;
- trigger;
- objection;
- safe promise;
- source refs;
- missing data;
- creative spec;
- selected hook;
- first-frame logic;
- asset/reference readiness;
- selected variant and score;
- prompt pack;
- prompt-only action;
- real smoke action disabled unless product and spend gates are ready.

## Result Contract

`WorkingVideoGenerator.prepare()` returns:

- `buyer_need`
- `selected_hook`
- `selected_variant_id`
- `prompt_pack_id`
- `real_smoke_eligible`
- demand validation details
- reference readiness details

The prompt-only path builds a prompt pack from the selected variant and does not call a video provider.

The real-smoke path delegates to `RealSmokeRunner`, so it keeps the same no-silent-fallback, no-spend-bypass behavior as Sprint 07.

## Acceptance Checklist

Prompt-only acceptance:

- `python scripts/import_sample_data.py` completes.
- `prepare_working_video.py` prints actual `Demand Hypothesis ID`, `Creative Spec ID`, `Selected Variant ID`, `Prompt Pack ID`, and `Generation Variant ID`.
- The operator copies the printed `Selected Variant ID`; no assumed id is required.
- `run_working_video.py --selected-variant-id <printed_id> --build-prompts-only` completes.
- The output shows `buyer_need`, selected hook, `prompt_pack_id`, reference readiness, `real_smoke_eligible`, and real smoke blockers.
- `/working-video-generator` shows `buyer_need`, `safe_promise`, `selected_variant_id`, `prompt_pack_id`, `real_smoke_eligible`, missing reference blockers, and spend gate blockers.

Reference readiness acceptance:

- A real packshot/reference image is attached with `attach_product_asset.py`.
- `check_product_references.py` prints a real `Reference Bundle ID`, primary reference asset id, status, blockers, and warnings.
- If references are blocked, real smoke remains ineligible.

Real smoke acceptance:

- `QVF_GENERATION_MODE=real`, `QVF_ALLOW_REAL_SPEND=true`, `QVF_VIDEO_PROVIDER=runway`, and `RUNWAYML_API_SECRET` are configured.
- `run_working_video.py --selected-variant-id <printed_id> --video-provider runway --real-run --max-scenes 1` starts only after gates pass.
- Provider job id, video job id, output path, generation report path, and quality review id are printed.
- The generation report contains no API keys, signed URL secrets, or authorization tokens.
- The video is downloaded locally, non-empty, and remains `needs_human_review`.
- A person checks the video visually before any merge/approval claim.
