# Destination Warmup Plans

Warmup plans reduce destination capacity while an owned account is being prepared or scaled.

Default phases:

- `phase_0_setup`: 0 posts/day, 0 posts/week
- `phase_1_soft_start`: 1 post/day, 7 posts/week
- `phase_2_regular`: 2 posts/day, 14 posts/week
- `phase_3_scaled`: 3 posts/day, 21 posts/week

Readiness uses the lower value between the destination's configured limit and the current warmup phase limit. This keeps campaign capacity conservative while still letting operators see what a destination could handle after warmup.

Warmup plans are internal controls. They do not perform external platform actions and do not publish content.
