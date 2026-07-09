# Bombbar One-Video Acceptance Report

Date: 2026-07-08

Scope:

- SKU: `UGC-BOMBBAR-PRO-DUBAI-MANGO-KUNAFA-45G`
- Flow: post-merge v2.7.1 Bombbar one-video acceptance
- UI: `/one-video-acceptance`
- Platform: Instagram Reels
- Provider target: Runway

## Prompt-Only Acceptance

Latest local acceptance run:

- Plan ID: `3`
- Selected Variant ID: `73`
- Prompt Pack ID: `81`
- Generation Variant ID: `70`
- Video provider call: skipped
- Provider job: none
- Output video: none

Policy result:

- `bite_scene_allowed=false`
- `texture_macro_allowed=false`
- `unwrapped_product_allowed=false`
- `packshot_overlay_required=true`
- `end_card_required=true`

Blocked scenes:

- `bite_scene`
- `texture_macro`
- `ai_generated_unwrapped_product`
- `bite_or_chew_closeup`
- `unwrapped_bar_in_hand`

Asset audit decision:

- `safe_prompt_only_or_overlay_until_edible_refs_ready`

MVP scorecard:

- `80/100`
- `usable_with_fixes`

Prompt preview is persisted in local DB fields:

- `OneVideoRenderPlan.prompt_preview_json`
- `DirectorPromptPack.provider_prompt_json`
- `PromptPack.prompt_pack_json`

## Real Smoke Status

Real smoke was not re-run in this acceptance pass because available Runway credits were not confirmed in-session.

If Runway returns a credit error during paid smoke, the one-video result is now persisted as:

- `status=blocked_by_runway_credits`
- `human_review_status=blocked`
- `next_action=add_runway_credits_then_rerun_one_scene_real_smoke`

This is an operational blocker, not a mock fallback and not an auto-approval.

## Next Action

Run one-scene paid smoke only after spend gates and Runway credits are confirmed:

```powershell
$env:QVF_GENERATION_MODE="real"
$env:QVF_ALLOW_REAL_SPEND="true"
$env:QVF_VIDEO_PROVIDER="runway"
$env:RUNWAYML_API_SECRET="..."

python scripts\one_video_run_real.py --plan-id 3 --video-provider runway --real-run --max-scenes 1
```

After a generated video:

```powershell
python scripts\extract_video_frames.py --video-job-id <id>
python scripts\one_video_review.py --result-id <id> --status needs_review --notes "Manual review required."
```

Acceptance remains incomplete until either:

- output exists and OutputAcceptance records a human decision; or
- the run is explicitly blocked by provider credits and the next action is recorded.
