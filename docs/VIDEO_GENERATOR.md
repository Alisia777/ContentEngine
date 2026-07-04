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

The prompt pack includes scene role, duration, prompt text, negative prompt, reference images, first-frame requirements, camera motion, composition, lighting, product accuracy rules, caption text, voiceover text, and provider params.

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
