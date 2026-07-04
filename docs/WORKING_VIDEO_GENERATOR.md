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
