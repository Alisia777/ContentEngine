# Product Geometry / Scale Lock

This layer fixes the first real-smoke issue where the product stayed recognizable, but size and proportions drifted.

It adds explicit geometry and scale rules to `VideoCreativeSpec` and to every provider prompt pack:

- keep the same size and proportions as the primary reference image
- preserve bottle silhouette
- preserve height-to-width ratio
- preserve cap/dropper size and placement
- preserve label area size and placement
- keep natural cosmetic bottle scale relative to hand/table
- do not stretch, squash, shrink, enlarge, or redesign the product

The negative prompt blocks size/proportion drift terms such as changed product size, wrong proportions, stretched bottle, oversized product, miniature product, changed silhouette, wrong cap size, and label area changed.

## Human Feedback Regeneration

When a human review finds product geometry drift, create a request:

```bash
python scripts/request_regeneration.py --video-job-id 11 --scene-number 1 --reason product_geometry_mismatch --feedback "Product size/proportions drifted; preserve exact bottle silhouette, height-width ratio, cap/dropper size and label area."
```

Then build the corrected prompt only:

```bash
python scripts/regenerate_scene_from_feedback.py --regeneration-request-id 1 --build-prompts-only
```

This does not call a paid provider. It updates the prompt pack for the affected scene and keeps the video in human-review flow.

## Content Factory Integration

`/content-factory` reads the geometry lock from the generated prompt pack and exposes it as `geometry_readiness`.

The AI review checks:

- `product_geometry_rules`
- `product_scale_rules`
- negative prompt blockers for size/proportion drift
- human feedback or quality review signals with `product_geometry_mismatch`

If geometry data is missing, the content run receives the blocker `geometry_lock_missing` and the next action `add_geometry_lock`. If human review reports size/proportion drift, the content run receives `product_geometry_mismatch`, moves to `needs_regeneration`, and recommends `request_geometry_regeneration`.

## Honesty Boundary

This is prompt-level protection, not computer vision verification. The metadata score must not claim that visual product identity or geometry is correct. Generated videos still require manual approval before publishing.
