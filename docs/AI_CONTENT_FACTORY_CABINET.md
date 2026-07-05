# AI Content Factory Cabinet

`/content-factory` is the main workspace for the AI-led production loop.

Flow:

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

The cabinet automates creator logic. Human users remain owners, reviewers, and exception handlers for visual review, paid smoke decisions, approve/reject, and final publishing decisions.

The sprint does not add external account creation, Telegram bot workflow, batch generation, approval bypasses, or auto-publishing of unreviewed videos.

## AI Factory Control Loop

The factory is the primary automated control loop:

```text
Product / SKU
-> AI Demand Agent
-> AI Creative Brief Agent
-> AI Variant Agent
-> AI Prompt Producer
-> AI Review Agent
-> AI Publishing Prep Agent
-> Performance Analytics
-> Next Action Recommendation
```

Each prepared run returns the fields an owner needs to decide the next step:

- `content_run_id`
- `demand_hypothesis_id`
- `creative_spec_id`
- `selected_variant_id`
- `prompt_pack_id`
- reference readiness
- geometry/scale readiness
- AI review status
- publishing readiness
- next recommended action

AI review checks demand, safe promise, creative spec, selected variant, prompt pack, reference readiness, product identity constraints, product geometry rules, product scale rules, negative prompt drift blockers, generated output metadata when a video exists, quality review status, and publishing package readiness.

If prompt-level geometry data is missing, the review adds `geometry_lock_missing` and recommends `add_geometry_lock`. If human feedback or quality review reports product size/proportion drift, the review adds `product_geometry_mismatch` and recommends `request_geometry_regeneration`.

The review remains metadata/rules-based. It does not claim visual product identity, package geometry, or final video quality is correct without human review or a future computer-vision layer.

## Workspace Sections

- Factory Overview
- Run Builder
- Run Actions
- AI Review Queue
- Performance
- Recent Runs

The screen is linked from the main navigation as `AI Factory`.
