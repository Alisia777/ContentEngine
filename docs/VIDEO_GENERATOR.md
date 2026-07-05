# Spec-Driven Video Generator

Sprint 04 video generation consumes `VideoCreativeSpecRecord`, not free-form script text.

Main flow:

```text
VideoCreativeSpec
-> PromptPack from spec
-> VideoGenerationVariant
-> VideoJob through Sprint 03 provider gates
-> provider polling/download/assembly
-> metadata-only quality score
-> review-ready artifact
```

The prompt pack includes scene role, duration, prompt text, negative prompt, reference images, first-frame requirements, camera motion, composition, lighting, product accuracy rules, product geometry/scale/visibility rules, caption text, voiceover text, and provider params.

Sprint 06 adds prompt packs from selected creative variants with product reference bundles. When a provider-ready bundle exists, the prompt pack includes:

- `reference_bundle_id`
- `reference_images`
- `primary_reference_asset`
- internal provider reference bundle payload
- product accuracy rules
- negative prompts against product distortion

When the product has no approved primary reference, prompt-only generation still works, but the prompt pack records blockers and is not real-smoke eligible.

Sprint 07 adds the selected-variant real smoke runner. It starts only from a selected `CreativeVariant`, requires product reference readiness `ready`, builds a prompt pack with a provider reference bundle, runs a spend-gated Runway one-scene job, downloads and assembles the output, writes `media/generation_reports/variant_{creative_variant_id}_video_{video_job_id}.json`, and creates a metadata-only quality review with `needs_human_review`.

Manual CLI:

```bash
python scripts/run_variant_real_smoke.py --creative-variant-id 1 --video-provider runway --real-run --max-scenes 1
```

See `docs/REAL_SMOKE_FROM_VARIANT.md` for the full acceptance runbook.

Real provider execution still uses the Sprint 03 gates:

- no silent mock fallback
- no paid provider call without explicit real-run action
- `QVF_GENERATION_MODE=real`
- `QVF_ALLOW_REAL_SPEND=true`
- provider key configured
- one-scene smoke by default unless full video is explicit

Quality scoring v1 is intentionally honest and metadata-based. It checks file presence, non-empty output, generation report presence, provider status, captions, CTA, reference image inclusion when present, forbidden claims, and first-frame requirements.

It does not claim visual quality, packaging correctness, or product identity verification because computer vision inspection is not implemented in this sprint.

Scene regeneration targets one scene prompt only and preserves the existing claim refs and product accuracy rules.

v0.2.1 adds Product Geometry / Scale Lock. The prompt pack now explicitly tells the provider to keep the product the same size and proportions as the primary reference image, preserve silhouette, preserve height-to-width ratio, preserve cap/dropper and label placement, and keep natural cosmetic bottle scale relative to hand/table. See `docs/PRODUCT_GEOMETRY_SCALE_LOCK.md`.
