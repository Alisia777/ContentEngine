# One Video Acceptance

One Video Acceptance is a controlled product-safe UGC render path for a single SKU before scaling generation.

Current target:

- Bombbar Pro Dubai Mango & Kunafa
- 9:16
- 15 seconds
- Russian Wibes/Reels-style UGC
- sporty woman, 25-30
- human review required

## Product Scene Policy

The flow classifies approved references before prompt generation:

- wrapper refs
- edible refs
- style refs
- lifestyle refs
- bitten-bar ref
- bar-in-hand ref

Rules:

- wrapper refs < 2 blocks wrapper close-up unless overlay/end card is used.
- edible refs < 3 blocks bite scenes, AI-generated unwrapped macro, and texture macro.
- missing bitten-bar reference blocks bite/chew close-up.
- missing bar-in-hand reference blocks unwrapped bar in hand.
- label accuracy requires packshot overlay or end card.
- style/lifestyle refs help UGC tone and context, but do not count as edible proof.

## Asset Audit

The plan stores an asset audit matrix inside `product_scene_policy.asset_audit`.

Wrapper refs:

- front packshot
- angled wrapper
- wrapper in hand
- semi-open wrapper
- wrapper + edible product

Edible refs:

- whole unwrapped bar
- cutaway
- bitten bar
- bar in hand
- bar near mouth
- texture macro

Style and lifestyle refs are reported separately. They can support a realistic Wibes/Reels scene, but they never unlock bite, chew, or macro product generation.

## MVP Scorecard

Each plan includes `prompt_preview.mvp_scorecard`:

| Criterion | Weight |
| --- | ---: |
| Product identity stable | 20 |
| Edible identity stable | 20 |
| Scene policy followed | 15 |
| Blogger meaning clear | 15 |
| Proof moment present | 10 |
| CTA/end card present | 10 |
| Human review recorded | 10 |

Score bands:

- 90-100: quality MVP success
- 75-89: usable with fixes
- 60-74: use as background / needs regeneration
- <60: reject

## API

The issue-level API contract is:

- `POST /api/one-video-acceptance/plans/build`
- `GET /api/one-video-acceptance/plans/{id}`
- `POST /api/one-video-acceptance/plans/{id}/prompt-only`
- `POST /api/one-video-acceptance/plans/{id}/run-real`
- `GET /api/one-video-acceptance/results/{id}`
- `POST /api/one-video-acceptance/results/{id}/review`

Allowed with weak edible kit:

- creator talking-head
- closed wrapper in hand
- wrapper reveal
- approved cutaway insert
- packshot overlay
- reaction shot
- end card

Blocked with weak edible kit:

- bite scene
- chew close-up
- AI-generated unwrapped product macro
- generated texture macro

## CLI

Build the plan:

```powershell
python scripts\build_one_video_render_plan.py --product-id 7 --platform "Instagram Reels"
```

Prompt-only:

```powershell
python scripts\one_video_prompt_only.py --plan-id 1
```

Paid smoke:

```powershell
$env:QVF_GENERATION_MODE="real"
$env:QVF_ALLOW_REAL_SPEND="true"
$env:QVF_VIDEO_PROVIDER="runway"
$env:RUNWAYML_API_SECRET="..."

python scripts\one_video_run_real.py --plan-id 1 --video-provider runway --real-run --max-scenes 1
```

If Runway responds that credits are unavailable, the run result is persisted as:

- `status=blocked_by_runway_credits`
- `human_review_status=blocked`
- `next_action=add_runway_credits_then_rerun_one_scene_real_smoke`

This is an operational blocker, not a silent fallback to mock generation.

Human review:

```powershell
python scripts\one_video_review.py --result-id 1 --status needs_regeneration --notes "Wrapper drifted and edible bar became muesli-like."
```

## Acceptance

A candidate can move forward only when human review confirms:

- no muesli/granola visual drift
- no wrapper/logo/label redesign
- product appears only according to scene policy
- proof moment is present
- CTA/end card is present
- no auto-approval happened

Metadata-only checks must not claim visual product identity verification.
