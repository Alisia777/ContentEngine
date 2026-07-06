# Quality Gates

Quality gates decide whether generated video can move toward a publishing package.

`QualityGateService` reads existing ContentRun, VideoJob, VideoGenerationVariant, VideoQualityReview, and SceneRegenerationRequest records. It does not run providers or inspect pixels itself.

## Blocking Rules

- Prompt-only content is not publishable video.
- Video without `VideoQualityReview` is blocked.
- `needs_human_review` blocks publishing.
- Open regeneration requests block publishing.
- Product identity mismatch blocks publishing.
- Product geometry or scale mismatch blocks publishing.
- Missing geometry lock blocks production-ready status.

## Passing Rule

A gate allows publishing only when:

- the video exists;
- the latest quality review is approved;
- human visual status is approved;
- product identity status is ready;
- geometry status is ready;
- no required fixes remain.

The service persists `LaunchQualityGate` rows so Launch Operations can explain exactly why each video is or is not publishable.
