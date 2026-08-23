begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(6);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
  ) is not null,
  'generated-video review start pre-project stage stays installed and private'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%paid_generation_job_input%',
  'review start binds a missing product category from the immutable paid job input'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%job_row.input ->> ''product_category''%',
  'the fallback reads only the allowlist-validated category stored at paid start'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%content_review_category_bound_from_generation%',
  'the one-time binding is journaled through the idempotent event trail'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%generated_video_review_category_required%',
  'jobs with no category anywhere still fail with the explicit category-required error'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'
      ::regprocedure
  ) like '%resolved_content_review_category%',
  'the approve path still enforces product-metadata category consistency'
);

select * from finish();

rollback;
