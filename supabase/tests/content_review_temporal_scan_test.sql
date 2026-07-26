begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(10);

select ok(
  content_factory_private.valid_content_review_temporal_metrics('{}'::jsonb),
  'historical evidence without a temporal scan remains readable'
);

select ok(
  content_factory_private.valid_content_review_temporal_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'temporal_scan_status', 'completed',
      'temporal_scan_strategy', 'uniform_full_duration_v1',
      'temporal_scan_frame_count', 24,
      'temporal_scan_first_second', 0.02,
      'temporal_scan_last_second', 7.98,
      'temporal_scan_coverage_ratio', 0.995,
      'temporal_black_frame_ratio', 0.0417,
      'temporal_frozen_transition_ratio', 0.087,
      'temporal_mean_frame_difference', 0.112
    )
  ),
  'bounded full-duration local scan metrics are valid'
);

select ok(
  not content_factory_private.valid_content_review_temporal_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'temporal_scan_status', 'completed',
      'temporal_scan_strategy', 'uniform_full_duration_v1',
      'temporal_scan_frame_count', 5,
      'temporal_scan_first_second', 0.02,
      'temporal_scan_last_second', 7.98,
      'temporal_scan_coverage_ratio', 0.995,
      'temporal_black_frame_ratio', 0,
      'temporal_frozen_transition_ratio', 0,
      'temporal_mean_frame_difference', 0.1
    )
  ),
  'the five externally retained frames cannot impersonate the dense scan'
);

select ok(
  not content_factory_private.valid_content_review_temporal_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'temporal_scan_status', 'completed',
      'temporal_scan_strategy', 'uniform_full_duration_v1',
      'temporal_scan_frame_count', 24,
      'temporal_scan_first_second', 3,
      'temporal_scan_last_second', 7,
      'temporal_scan_coverage_ratio', 0.95,
      'temporal_black_frame_ratio', 0,
      'temporal_frozen_transition_ratio', 0,
      'temporal_mean_frame_difference', 0.1
    )
  ),
  'reported coverage must match the first and last sampled points'
);

select ok(
  not content_factory_private.valid_content_review_temporal_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'temporal_scan_status', 'completed',
      'temporal_scan_strategy', 'uniform_full_duration_v1',
      'temporal_scan_frame_count', 24,
      'temporal_scan_first_second', 0.02,
      'temporal_scan_last_second', 7.98,
      'temporal_scan_coverage_ratio', 0.995,
      'temporal_black_frame_ratio', 0,
      'temporal_frozen_transition_ratio', 0,
      'temporal_mean_frame_difference', 0.1,
      'temporal_frame_payload', 'invented'
    )
  ),
  'unapproved temporal payload fields are rejected'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
        'content_factory.content_review_evidence_sets'::regclass
      and constraint_row.conname =
        'content_review_evidence_temporal_metrics_valid'
      and constraint_row.convalidated
  ),
  'validated temporal evidence constraint is installed'
);

select ok(
  to_regprocedure(
    'public.creator_commit_content_review_evidence(jsonb)'
  ) is not null,
  'public evidence commit remains available through the temporal gate'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_commit_content_review_evidence_without_temporal_gate_v2(jsonb)'
  ) is not null,
  'the audio-gated implementation is private behind the temporal gate'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_commit_content_review_evidence(jsonb)',
    'execute'
  ),
  'authenticated creators may execute the public temporal-gated commit'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_commit_content_review_evidence_without_temporal_gate_v2(jsonb)',
    'execute'
  ),
  'browser sessions cannot bypass the temporal evidence gate'
);

select * from finish();

rollback;
