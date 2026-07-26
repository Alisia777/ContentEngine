begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(11);

select ok(
  content_factory_private.valid_content_review_timeline_atlas_metrics(
    '{}'::jsonb
  ),
  'historical evidence without an atlas remains readable'
);

select ok(
  content_factory_private.valid_content_review_timeline_atlas_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'frame_count', 5,
      'sampled_at_seconds', jsonb_build_array(0.2, 1, 2, 5.76, 7.98),
      'temporal_scan_frame_count', 24,
      'temporal_scan_first_second', 0.02,
      'temporal_scan_last_second', 7.98,
      'temporal_scan_coverage_ratio', 0.995,
      'timeline_atlas_status', 'completed',
      'timeline_atlas_version', 'dense_full_duration_v1',
      'timeline_atlas_frame_ordinal', 5,
      'timeline_atlas_frame_count', 24,
      'timeline_atlas_first_second', 0.02,
      'timeline_atlas_last_second', 7.98,
      'timeline_atlas_coverage_ratio', 0.995,
      'timeline_atlas_max_gap_seconds', 0.3461,
      'timeline_atlas_sample_rate_fps', 3,
      'timeline_atlas_columns', 8,
      'timeline_atlas_rows', 3,
      'timeline_atlas_order', 'row_major_chronological',
      'timeline_atlas_dense_short_video', true
    )
  ),
  'four control frames plus a dense fifth timeline atlas are valid'
);

select ok(
  not content_factory_private.valid_content_review_timeline_atlas_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'frame_count', 4,
      'sampled_at_seconds', jsonb_build_array(0.2, 1, 2, 7.98),
      'timeline_atlas_status', 'completed'
    )
  ),
  'an atlas cannot replace the required fifth evidence image'
);

select ok(
  not content_factory_private.valid_content_review_timeline_atlas_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'frame_count', 5,
      'sampled_at_seconds', jsonb_build_array(0.2, 1, 2, 5.76, 7.98),
      'temporal_scan_frame_count', 24,
      'temporal_scan_first_second', 0.02,
      'temporal_scan_last_second', 7.98,
      'temporal_scan_coverage_ratio', 0.995,
      'timeline_atlas_status', 'completed',
      'timeline_atlas_version', 'dense_full_duration_v1',
      'timeline_atlas_frame_ordinal', 4,
      'timeline_atlas_frame_count', 24,
      'timeline_atlas_first_second', 0.02,
      'timeline_atlas_last_second', 7.98,
      'timeline_atlas_coverage_ratio', 0.995,
      'timeline_atlas_max_gap_seconds', 0.3461,
      'timeline_atlas_sample_rate_fps', 3,
      'timeline_atlas_columns', 8,
      'timeline_atlas_rows', 3,
      'timeline_atlas_order', 'row_major_chronological',
      'timeline_atlas_dense_short_video', true
    )
  ),
  'the atlas must be the fifth chronological evidence image'
);

select ok(
  not content_factory_private.valid_content_review_timeline_atlas_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'frame_count', 5,
      'sampled_at_seconds', jsonb_build_array(0.2, 1, 2, 5.76, 7.98),
      'temporal_scan_frame_count', 24,
      'temporal_scan_first_second', 0.02,
      'temporal_scan_last_second', 7.98,
      'temporal_scan_coverage_ratio', 0.995,
      'timeline_atlas_status', 'completed',
      'timeline_atlas_version', 'dense_full_duration_v1',
      'timeline_atlas_frame_ordinal', 5,
      'timeline_atlas_frame_count', 24,
      'timeline_atlas_first_second', 0.02,
      'timeline_atlas_last_second', 7.98,
      'timeline_atlas_coverage_ratio', 0.995,
      'timeline_atlas_max_gap_seconds', 1.5,
      'timeline_atlas_sample_rate_fps', 3,
      'timeline_atlas_columns', 8,
      'timeline_atlas_rows', 3,
      'timeline_atlas_order', 'row_major_chronological',
      'timeline_atlas_dense_short_video', false
    )
  ),
  'a forged maximum timeline gap is rejected'
);

select ok(
  not content_factory_private.valid_content_review_timeline_atlas_metrics(
    jsonb_build_object(
      'duration_seconds', 8,
      'frame_count', 5,
      'sampled_at_seconds', jsonb_build_array(0.2, 1, 2, 5.76, 7.98),
      'timeline_atlas_status', 'completed',
      'timeline_atlas_payload', 'invented'
    )
  ),
  'unapproved timeline atlas payload fields are rejected'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
        'content_factory.content_review_evidence_sets'::regclass
      and constraint_row.conname =
        'content_review_evidence_timeline_atlas_metrics_valid'
      and constraint_row.convalidated
  ),
  'validated timeline atlas evidence constraint is installed'
);

select ok(
  to_regprocedure(
    'public.creator_commit_content_review_evidence(jsonb)'
  ) is not null,
  'public evidence commit remains available through the atlas gate'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_commit_content_review_evidence_without_atlas_gate_v3(jsonb)'
  ) is not null,
  'the previous evidence implementation is private behind the atlas gate'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_commit_content_review_evidence(jsonb)',
    'execute'
  ),
  'authenticated creators may execute the public atlas-gated commit'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_commit_content_review_evidence_without_atlas_gate_v3(jsonb)',
    'execute'
  ),
  'browser sessions cannot bypass the timeline atlas evidence gate'
);

select * from finish();

rollback;
