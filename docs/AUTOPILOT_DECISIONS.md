# Autopilot Decisions

`AutopilotDecision` stores each rules-based next-action recommendation.

The decision engine evaluates one `ContentStateSnapshot` and returns one primary action:

- `prepare_content_run`
- `add_product_reference`
- `add_geometry_lock`
- `build_prompt_pack`
- `run_prompt_only`
- `run_real_smoke`
- `human_review`
- `request_regeneration`
- `request_geometry_regeneration`
- `create_publishing_package`
- `schedule_publishing_task`
- `import_performance_stats`
- `scale_variant`
- `pause_variant`

The decision stores confidence, reasons, blockers, the input snapshot, output metadata, and whether human review is required.

## Safety Gates

Default safe execution is limited to no-paid and no-publish actions.

`run_real_smoke` is a paid action and is blocked without an explicit paid gate.

`schedule_publishing_task` and manual publishing are publishing actions and are blocked unless explicitly allowed and approval gates are satisfied.

The decision engine is metadata/rules-based. It does not claim visual product identity or geometry verification without human review or a future computer-vision layer.
