# Real Smoke From Selected Variant

Sprint 07 proves one paid provider output from the selected creative variant path.

Scope:

```text
Product
-> approved primary product reference
-> asset kit ready
-> Creative TZ
-> selected CreativeVariant
-> PromptPack with provider reference bundle
-> spend-gated Runway one-scene generation
-> polling
-> download
-> assembly
-> variant generation report
-> metadata quality review
-> human review
```

This is not batch generation, auto-posting, full-video generation, computer vision scoring, or a new provider integration.

## Gates

A real smoke run must pass all gates before a provider call:

1. `QVF_GENERATION_MODE=real`
2. `QVF_ALLOW_REAL_SPEND=true`
3. Explicit `--real-run` or API `real_run=true`
4. Runway selected through request/provider
5. `RUNWAYML_API_SECRET` configured
6. CreativeVariant exists
7. CreativeVariant is selected
8. PromptPack can be built from the variant
9. Product reference readiness is `ready`
10. Approved primary reference exists
11. Provider reference bundle is included
12. One scene by default
13. Full video requires explicit `--full-video`

Normal tests use a fake Runway provider and do not make paid calls.

## CLI

Safe failure check without spend env/key:

```powershell
python scripts\run_variant_real_smoke.py --creative-variant-id 1 --video-provider runway --real-run --max-scenes 1
```

Expected result without gates:

```text
Error: Real smoke requires QVF_GENERATION_MODE=real.
```

Manual paid smoke after references and selected variant are ready:

```powershell
$env:QVF_GENERATION_MODE="real"
$env:QVF_ALLOW_REAL_SPEND="true"
$env:QVF_VIDEO_PROVIDER="runway"
$env:RUNWAYML_API_SECRET="..."

python scripts\run_variant_real_smoke.py --creative-variant-id 1 --video-provider runway --real-run --max-scenes 1
```

The command prints product/SKU, creative spec id, creative variant id, prompt pack id, reference bundle id, video job id, provider job ids, provider status, local output paths, generation report path, quality review id, and the manual review instruction.

## API

```text
POST /api/video-generator/variants/{creative_variant_id}/real-smoke
GET  /api/video-generator/real-smoke/{video_job_id}
POST /api/video-generator/real-smoke/{video_job_id}/poll
POST /api/video-generator/real-smoke/{video_job_id}/download
POST /api/video-generator/real-smoke/{video_job_id}/score
```

Start payload:

```json
{
  "provider": "runway",
  "real_run": true,
  "allow_real_spend": true,
  "max_scenes": 1,
  "full_video": false
}
```

## Generation Report

Reports are written to:

```text
media/generation_reports/variant_{creative_variant_id}_video_{video_job_id}.json
```

The report includes run type, product/spec/variant/prompt/video ids, provider job ids, reference bundle data, prompt summary, scrubbed provider request/response, local output paths, final video path, quality review id, warnings/errors, and `created_at`.

Reports must not contain API keys, secret tokens, signed URL query params, or authorization values.

## Quality Review

The review is metadata-only. It can mark:

- `needs_human_review`
- `failed_generation`
- `needs_regeneration`

It checks provider status, output file existence and size, generation report existence, first-frame metadata, approved reference inclusion, captions, CTA, and forbidden-claim metadata. It does not verify visual product identity or packaging correctness.
